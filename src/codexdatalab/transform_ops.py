from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .data_ops import get_dataset
from .utils import generate_id, hash_file, utc_now_iso
from .workspace import Workspace


def init_transform(workspace: Workspace, dataset_id: str, name: str, *, why: str = "") -> Path:
    transform_id = generate_id("tf")
    safe_name = "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_"}).strip() or "transform"
    filename = f"{transform_id}_{safe_name}.py"
    transform_path = workspace.project_root() / "transforms" / filename
    transform_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = get_dataset(workspace, dataset_id)
    if dataset is None:
        raise ValueError(f"Unknown dataset: {dataset_id}")
    input_path = workspace.root / dataset["path"]

    project_root = workspace.project_root()
    template = f"""from __future__ import annotations

import polars as pl
from pathlib import Path

WORKSPACE_ROOT = Path(r\"{workspace.root}\")
PROJECT_ROOT = Path(r\"{project_root}\")
INPUT_PATH = WORKSPACE_ROOT / r\"{input_path.relative_to(workspace.root)}\"

df = pl.read_csv(INPUT_PATH) if INPUT_PATH.suffix == \".csv\" else pl.read_parquet(INPUT_PATH)

# TODO: edit the transform below
cleaned = df

output_path = PROJECT_ROOT / \"data\" / \"{dataset_id}_cleaned.csv\"
cleaned.write_csv(output_path)
print(output_path)
"""

    transform_path.write_text(template)

    manifest = workspace.load_manifest()
    transforms = manifest.setdefault("transforms", {})
    transforms[transform_id] = {
        "id": transform_id,
        "path": str(transform_path.relative_to(workspace.root)),
        "created_at": utc_now_iso(),
        "why": why,
        "input_dataset_ids": [dataset_id],
        "project": workspace.project_id(),
    }
    workspace.save_manifest(manifest)
    workspace.commit("Create transform", paths=[transform_path.as_posix(), ".codexdatalab/manifest.json"])
    return transform_path


def run_transform(
    workspace: Workspace,
    transform_path: Path,
    *,
    input_dataset_id: str | None = None,
    why: str = "",
) -> list[str]:
    transform_path = transform_path.resolve()
    if not transform_path.exists():
        raise FileNotFoundError(str(transform_path))

    before = {p.resolve() for p in (workspace.project_root() / "data").iterdir() if p.is_file()}
    result = subprocess.run(
        [sys.executable, str(transform_path)],
        cwd=workspace.root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Transform failed.")

    after = {p.resolve() for p in (workspace.project_root() / "data").iterdir() if p.is_file()}
    new_files = sorted(after - before)
    output_dataset_ids: list[str] = []

    manifest = workspace.load_manifest()
    datasets = manifest.setdefault("datasets", {})
    project_id = workspace.project_id()

    for output_path in new_files:
        ext = output_path.suffix.lower().lstrip(".")
        if ext not in {"csv", "parquet"}:
            continue
        sha256 = hash_file(output_path)
        dataset_id = f"ds_{sha256[:12]}"
        output_dataset_ids.append(dataset_id)
        if dataset_id not in datasets:
            datasets[dataset_id] = {
                "id": dataset_id,
                "kind": "cleaned",
                "path": str(output_path.relative_to(workspace.root)),
                "paths_by_project": {project_id: str(output_path.relative_to(workspace.root))},
                "projects": [project_id],
                "format": ext,
                "sha256": sha256,
                "size_bytes": output_path.stat().st_size,
                "sources": [],
                "created_at": utc_now_iso(),
                "name": output_path.name,
                "parent_dataset_id": input_dataset_id,
                "produced_by_transform_id": transform_path.stem.split("_")[0],
            }
        else:
            entry = datasets[dataset_id]
            entry.setdefault("paths_by_project", {})
            entry.setdefault("projects", [])
            entry["paths_by_project"][project_id] = str(output_path.relative_to(workspace.root))
            if project_id not in entry["projects"]:
                entry["projects"].append(project_id)

    workspace.save_manifest(manifest)

    if input_dataset_id:
        for dataset_id in output_dataset_ids:
            workspace.add_lineage_edge(input_dataset_id, dataset_id, "cleaned")

    workspace.commit(
        "Run transform",
        paths=[
            str((workspace.project_root() / "data").relative_to(workspace.root)),
            ".codexdatalab/manifest.json",
            ".codexdatalab/lineage.json",
        ],
    )
    return output_dataset_ids
