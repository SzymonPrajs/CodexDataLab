from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import polars as pl

from .utils import hash_file, utc_now_iso
from .workspace import Workspace

PromptCallback = Callable[[str], str]


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    path: Path
    kind: str
    format: str


def import_dataset(
    workspace: Workspace,
    source_path: Path,
    *,
    link: bool = False,
    force_copy: bool = False,
    prompt: PromptCallback | None = None,
    source_label: str | None = None,
    import_mode: str | None = None,
    display_name: str | None = None,
) -> DatasetRecord:
    source_path = source_path.expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(str(source_path))

    ext = source_path.suffix.lower().lstrip(".")
    if ext not in {"csv", "parquet"}:
        raise ValueError(f"Unsupported file type: {source_path.suffix}")

    size_bytes = source_path.stat().st_size
    if not link and not force_copy and size_bytes > workspace.settings.max_copy_bytes:
        if prompt is None:
            raise ValueError("File exceeds max copy size; confirmation required.")
        choice = prompt(
            f"File exceeds max-copy size ({size_bytes} bytes). "
            "Choose: [l]ink / [c]opy anyway / [x] cancel: "
        )
        choice = choice.strip().lower()
        if choice.startswith("l"):
            link = True
        elif choice.startswith("c"):
            force_copy = True
        else:
            raise ValueError("Import cancelled.")

    sha256 = hash_file(source_path)
    dataset_id = f"ds_{sha256[:12]}"

    raw_dir = workspace.project_root() / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest_path = raw_dir / f"{dataset_id}.{ext}"

    if not dest_path.exists():
        if link:
            try:
                dest_path.symlink_to(source_path)
            except OSError:
                dest_path.write_bytes(source_path.read_bytes())
        else:
            dest_path.write_bytes(source_path.read_bytes())

    manifest = workspace.load_manifest()
    datasets = manifest.setdefault("datasets", {})
    created_at = utc_now_iso()
    project_id = workspace.project_id()
    if dataset_id not in datasets:
        datasets[dataset_id] = {
            "id": dataset_id,
            "kind": "raw",
            "path": str(dest_path.relative_to(workspace.root)),
            "paths_by_project": {project_id: str(dest_path.relative_to(workspace.root))},
            "projects": [project_id],
            "format": ext,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "sources": [],
            "created_at": created_at,
            "name": display_name or source_path.name,
        }
    else:
        entry = datasets[dataset_id]
        entry.setdefault("paths_by_project", {})
        entry.setdefault("projects", [])
        entry["paths_by_project"][project_id] = str(dest_path.relative_to(workspace.root))
        if project_id not in entry["projects"]:
            entry["projects"].append(project_id)
        if "path" not in entry:
            entry["path"] = str(dest_path.relative_to(workspace.root))

    source_entry = {
        "source": source_label or str(source_path),
        "imported_at": created_at,
        "import_mode": import_mode or ("link" if link else "copy"),
    }
    sources = datasets[dataset_id].setdefault("sources", [])
    if not any(entry.get("source") == source_entry["source"] for entry in sources):
        sources.append(source_entry)
    workspace.save_manifest(manifest)
    workspace.commit(
        f"Import dataset {dataset_id}",
        paths=[str(dest_path.relative_to(workspace.root)), ".codexdatalab/manifest.json"],
    )

    return DatasetRecord(dataset_id=dataset_id, path=dest_path, kind="raw", format=ext)


def list_datasets(workspace: Workspace) -> list[dict]:
    manifest = workspace.load_manifest()
    datasets = list(manifest.get("datasets", {}).values())
    project_id = workspace.project_id()
    filtered = []
    for item in datasets:
        projects = item.get("projects")
        if projects and project_id not in projects:
            continue
        filtered.append(item)
    return sorted(
        filtered,
        key=lambda item: (
            0 if item.get("kind") == "cleaned" else 1,
            item.get("created_at", ""),
        ),
    )


def get_dataset(workspace: Workspace, dataset_id: str) -> dict | None:
    manifest = workspace.load_manifest()
    dataset = manifest.get("datasets", {}).get(dataset_id)
    if not dataset:
        return None
    project_id = workspace.project_id()
    paths_by_project = dataset.get("paths_by_project", {})
    if project_id in paths_by_project:
        dataset = dict(dataset)
        dataset["path"] = paths_by_project[project_id]
        return dataset
    if dataset.get("path"):
        return dataset
    if paths_by_project:
        dataset = dict(dataset)
        dataset["path"] = next(iter(paths_by_project.values()))
        return dataset
    return dataset


def load_dataset_lazy(workspace: Workspace, dataset_id: str) -> pl.LazyFrame:
    dataset = get_dataset(workspace, dataset_id)
    if dataset is None:
        raise KeyError(f"Unknown dataset: {dataset_id}")
    path = workspace.root / dataset["path"]
    if dataset.get("format") == "parquet":
        return pl.scan_parquet(path)
    return pl.scan_csv(path)


def preview_dataset(
    workspace: Workspace, dataset_id: str, *, max_rows: int = 50, max_cols: int = 12
) -> pl.DataFrame:
    lazy = load_dataset_lazy(workspace, dataset_id)
    df = lazy.limit(max_rows).collect()
    if df.width > max_cols:
        df = df.select(df.columns[:max_cols])
    return df
