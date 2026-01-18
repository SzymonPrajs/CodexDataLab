from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable

CORE_DIRS: tuple[str, ...] = (
    "raw",
    "data",
    "transforms",
    "plots",
    "results",
    "reports",
)

WORKSPACE_DIRS: tuple[str, ...] = CORE_DIRS + (
    ".codexdatalab",
    "projects",
)


def create_workspace_skeleton(
    workspace_root: Path,
    *,
    schema_version: int = 0,
    include_meta: bool = True,
    include_projects_dir: bool = True,
) -> None:
    """Create the standard workspace folder layout and base JSON metadata files.

    This is intentionally minimal scaffolding for development and tests. It
    creates missing files/directories but does not overwrite existing ones.
    """

    workspace_root.mkdir(parents=True, exist_ok=True)
    for dir_name in CORE_DIRS:
        (workspace_root / dir_name).mkdir(parents=True, exist_ok=True)
    if include_projects_dir:
        (workspace_root / "projects").mkdir(parents=True, exist_ok=True)
    if not include_meta:
        return
    (workspace_root / ".codexdatalab").mkdir(parents=True, exist_ok=True)

    meta_dir = workspace_root / ".codexdatalab"
    _write_json_if_missing(
        meta_dir / "manifest.json",
        {
            "schema_version": schema_version,
            "datasets": {},
            "transforms": {},
            "recipes": {},
            "reports": {},
        },
    )
    _write_json_if_missing(
        meta_dir / "lineage.json",
        {
            "schema_version": schema_version,
            "edges": [],
        },
    )
    _write_json_if_missing(
        meta_dir / "plots.json",
        {
            "schema_version": schema_version,
            "plots": {},
        },
    )
    _write_json_if_missing(
        meta_dir / "qa.json",
        {
            "schema_version": schema_version,
            "answers": {},
        },
    )
    _write_json_if_missing(
        meta_dir / "state.json",
        {
            "schema_version": schema_version,
            "ui": {},
        },
    )


def populate_raw_from_fixtures(
    workspace_root: Path, fixtures: Iterable[Path], *, overwrite: bool = False
) -> None:
    """Copy fixture files into the workspace raw/ directory.

    By default this is non-destructive (it won't overwrite existing files). Use
    `overwrite=True` to replace existing fixture files.
    """

    raw_dir = workspace_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for fixture in fixtures:
        destination = raw_dir / fixture.name
        if destination.exists() and not overwrite:
            continue
        shutil.copy2(fixture, destination)


def _write_json_if_missing(path: Path, data: object) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
