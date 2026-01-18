from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .data_ops import import_dataset, PromptCallback
from .settings import Settings
from .utils import generate_id, utc_now_iso
from .workspace import Workspace

SUPPORTED_FORMATS = {"csv", "parquet"}


@dataclass(frozen=True)
class FetchResult:
    dataset_id: str
    path: Path
    receipt_path: Path


def is_allowed_url(url: str, allowed_domains: Iterable[str]) -> bool:
    host = urlparse(url).hostname
    if not host:
        return False
    host = host.lower()
    for entry in allowed_domains:
        entry = entry.strip()
        if not entry:
            continue
        entry_host = urlparse(entry).hostname or entry
        entry_host = entry_host.lower()
        if host == entry_host or host.endswith(f".{entry_host}"):
            return True
    return False


def fetch_url(
    workspace: Workspace,
    url: str,
    *,
    display_name: str | None = None,
    format_hint: str | None = None,
    metadata: dict[str, Any] | None = None,
    prompt: PromptCallback | None = None,
    timeout: int = 60,
) -> FetchResult:
    settings = workspace.settings
    if settings.offline_mode:
        raise RuntimeError("Offline mode is enabled; web fetch is disabled.")

    if not is_allowed_url(url, settings.allowed_domains):
        raise ValueError("Domain not allowed for web download. Update allowed_domains in settings.")

    ext = _infer_extension(url, _normalize_format(format_hint))
    if not ext:
        raise ValueError("Unsupported file type; only CSV/Parquet are supported.")

    temp_path = _download_url(url, suffix=f".{ext}", timeout=timeout)
    try:
        size_bytes = temp_path.stat().st_size
        if size_bytes > settings.max_copy_bytes and settings.prompt_on_large_file:
            if prompt is None:
                raise ValueError("Downloaded file exceeds max copy size; confirmation required.")
            reply = prompt(
                f"Downloaded file is {size_bytes} bytes (max {settings.max_copy_bytes}). "
                "Keep and import? [y/N]: "
            ).strip().lower()
            if reply not in {"y", "yes"}:
                raise ValueError("Fetch cancelled.")

        name = display_name or _display_name_from_url(url, ext)
        record = import_dataset(
            workspace,
            temp_path,
            link=False,
            force_copy=True,
            prompt=None,
            source_label=url,
            import_mode="download",
            display_name=name,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    receipt_path = _write_receipt(
        workspace,
        dataset_id=record.dataset_id,
        source_url=url,
        metadata=metadata or {},
    )
    _attach_receipt(workspace, record.dataset_id, receipt_path)
    workspace.commit(
        f"Record fetch receipt for {record.dataset_id}",
        paths=[receipt_path.as_posix(), ".codexdatalab/manifest.json", ".codexdatalab/lineage.json"],
    )

    return FetchResult(dataset_id=record.dataset_id, path=record.path, receipt_path=receipt_path)


def _display_name_from_url(url: str, ext: str) -> str:
    path_name = Path(urlparse(url).path).name
    if not path_name:
        return f"dataset.{ext}"
    if not path_name.lower().endswith(f".{ext}"):
        return f"{path_name}.{ext}"
    return path_name


def _download_url(url: str, *, suffix: str, timeout: int) -> Path:
    try:
        request = Request(url, headers={"User-Agent": "CodexDataLab/0.2"})
        with urlopen(request, timeout=timeout) as response:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                shutil.copyfileobj(response, handle)
                return Path(handle.name)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


def _infer_extension(url: str, format_hint: str | None) -> str | None:
    ext = Path(urlparse(url).path).suffix.lower().lstrip(".")
    if ext in SUPPORTED_FORMATS:
        return ext
    if format_hint in SUPPORTED_FORMATS:
        return format_hint
    return None


def _normalize_format(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if "parquet" in lowered or lowered == "pq":
        return "parquet"
    if "csv" in lowered:
        return "csv"
    return None


def _write_receipt(
    workspace: Workspace,
    *,
    dataset_id: str,
    source_url: str,
    metadata: dict[str, Any],
) -> Path:
    receipt_id = generate_id("res")
    receipt_path = workspace.root / "results" / f"{receipt_id}.json"
    receipt = {
        "id": receipt_id,
        "dataset_id": dataset_id,
        "source_url": source_url,
        "fetched_at": utc_now_iso(),
        "metadata": metadata,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt_path


def _attach_receipt(workspace: Workspace, dataset_id: str, receipt_path: Path) -> None:
    manifest = workspace.load_manifest()
    datasets = manifest.get("datasets", {})
    dataset = datasets.get(dataset_id)
    if dataset is None:
        return
    receipts = dataset.setdefault("receipts", [])
    record = {
        "id": receipt_path.stem,
        "path": str(receipt_path.relative_to(workspace.root)),
        "created_at": utc_now_iso(),
    }
    receipts.append(record)
    workspace.save_manifest(manifest)
    workspace.add_lineage_edge(dataset_id, receipt_path.stem, "receipt")
