from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .git_utils import commit_if_needed, ensure_git_repo, ensure_workspace_gitignore
from .settings import Settings
from .workspace_scaffold import WORKSPACE_DIRS, create_workspace_skeleton

SCHEMA_VERSION = 0
WORKSPACE_MARKER = ".codexdatalab"


@dataclass
class Workspace:
    root: Path
    settings: Settings

    def meta_dir(self) -> Path:
        return self.root / WORKSPACE_MARKER

    def metadata_path(self, name: str) -> Path:
        return self.meta_dir() / name

    def load_json(self, name: str, default: dict[str, Any]) -> dict[str, Any]:
        path = self.metadata_path(name)
        if not path.exists():
            self.save_json(name, default)
            return default
        return json.loads(path.read_text())

    def save_json(self, name: str, data: dict[str, Any]) -> None:
        path = self.metadata_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    def load_state(self) -> dict[str, Any]:
        return self.load_json("state.json", {"schema_version": SCHEMA_VERSION, "ui": {}})

    def update_ui_state(self, key: str, value: Any) -> None:
        state = self.load_state()
        state.setdefault("ui", {})[key] = value
        self.save_json("state.json", state)


def find_workspace_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        marker = current / WORKSPACE_MARKER
        if marker.exists() and marker.is_dir():
            return current
        if current.parent == current:
            return None
        current = current.parent


def init_workspace(root: Path, settings: Settings, *, git_enabled: bool = True) -> Workspace:
    create_workspace_skeleton(root, schema_version=SCHEMA_VERSION)
    if git_enabled and ensure_git_repo(root):
        ensure_workspace_gitignore(root, ["raw/"])
        commit_if_needed(root, "Initialize workspace")
    return load_workspace(root, settings)


def load_workspace(root: Path, settings: Settings) -> Workspace:
    create_workspace_skeleton(root, schema_version=SCHEMA_VERSION)
    return Workspace(root=root, settings=settings)


def is_workspace_root(path: Path) -> bool:
    return (path / WORKSPACE_MARKER).is_dir()


def workspace_dirs(root: Path) -> dict[str, Path]:
    return {name: root / name for name in WORKSPACE_DIRS}

