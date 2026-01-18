from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .git_utils import commit_if_needed, ensure_git_repo, ensure_workspace_gitignore
from .settings import Settings
from .utils import utc_now_iso
from .workspace_scaffold import WORKSPACE_DIRS, create_workspace_skeleton

SCHEMA_VERSION = 0
WORKSPACE_MARKER = ".codexdatalab"
DEFAULT_PROJECT = "__default__"


@dataclass
class Workspace:
    root: Path
    settings: Settings
    git_enabled: bool = False
    project: str | None = None

    def meta_dir(self) -> Path:
        return self.root / WORKSPACE_MARKER

    def project_id(self) -> str:
        return self.project or DEFAULT_PROJECT

    def project_root(self) -> Path:
        if self.project:
            return self.root / "projects" / self.project
        return self.root

    def ensure_project(self, name: str) -> Path:
        project_root = self.root / "projects" / name
        create_workspace_skeleton(project_root, schema_version=SCHEMA_VERSION, include_meta=False, include_projects_dir=False)
        return project_root

    def list_projects(self) -> list[str]:
        projects_dir = self.root / "projects"
        if not projects_dir.is_dir():
            return []
        return sorted(
            [
                entry.name
                for entry in projects_dir.iterdir()
                if entry.is_dir() and not entry.name.startswith(".")
            ]
        )

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

    def set_active_project(self, name: str | None) -> None:
        if name:
            self.ensure_project(name)
        self.project = name
        self.update_ui_state("active_project", name or "")

    def load_manifest(self) -> dict[str, Any]:
        return self.load_json(
            "manifest.json",
            {
                "schema_version": SCHEMA_VERSION,
                "datasets": {},
                "transforms": {},
                "recipes": {},
                "reports": {},
            },
        )

    def save_manifest(self, data: dict[str, Any]) -> None:
        self.save_json("manifest.json", data)

    def load_lineage(self) -> dict[str, Any]:
        return self.load_json("lineage.json", {"schema_version": SCHEMA_VERSION, "edges": []})

    def save_lineage(self, data: dict[str, Any]) -> None:
        self.save_json("lineage.json", data)

    def add_lineage_edge(self, from_id: str, to_id: str, relation: str) -> None:
        lineage = self.load_lineage()
        lineage.setdefault("edges", []).append(
            {"from": from_id, "to": to_id, "type": relation, "created_at": utc_now_iso()}
        )
        self.save_lineage(lineage)

    def lineage_for(self, entity_id: str) -> dict[str, list[str]]:
        lineage = self.load_lineage()
        incoming: list[str] = []
        outgoing: list[str] = []
        for edge in lineage.get("edges", []):
            if edge.get("to") == entity_id:
                incoming.append(f"{edge.get('from')} ({edge.get('type')})")
            if edge.get("from") == entity_id:
                outgoing.append(f"{edge.get('to')} ({edge.get('type')})")
        return {"incoming": incoming, "outgoing": outgoing}

    def load_plots(self) -> dict[str, Any]:
        return self.load_json("plots.json", {"schema_version": SCHEMA_VERSION, "plots": {}})

    def save_plots(self, data: dict[str, Any]) -> None:
        self.save_json("plots.json", data)

    def load_answers(self) -> dict[str, Any]:
        return self.load_json("qa.json", {"schema_version": SCHEMA_VERSION, "answers": {}})

    def save_answers(self, data: dict[str, Any]) -> None:
        self.save_json("qa.json", data)

    def commit(self, message: str, paths: list[str] | None = None) -> None:
        if not self.git_enabled:
            return
        normalized: list[str] | None = None
        if paths:
            normalized = []
            for item in paths:
                path = Path(item)
                if path.is_absolute():
                    normalized.append(str(path.relative_to(self.root)))
                else:
                    normalized.append(item)
        commit_if_needed(self.root, message, paths=normalized)


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
    create_workspace_skeleton(root, schema_version=SCHEMA_VERSION, include_meta=True, include_projects_dir=True)
    repo_ready = False
    if git_enabled and ensure_git_repo(root):
        ensure_workspace_gitignore(root, ["raw/", "projects/*/raw/"])
        repo_ready = True
        commit_if_needed(root, "Initialize workspace")
    workspace = load_workspace(root, settings)
    workspace.git_enabled = repo_ready
    return workspace


def load_workspace(root: Path, settings: Settings) -> Workspace:
    create_workspace_skeleton(root, schema_version=SCHEMA_VERSION, include_meta=True, include_projects_dir=True)
    git_enabled = (root / ".git").is_dir()
    workspace = Workspace(root=root, settings=settings, git_enabled=git_enabled)
    state = workspace.load_state()
    active_project = state.get("ui", {}).get("active_project")
    if isinstance(active_project, str) and active_project:
        workspace.project = active_project
    return workspace


def is_workspace_root(path: Path) -> bool:
    return (path / WORKSPACE_MARKER).is_dir()


def workspace_dirs(root: Path) -> dict[str, Path]:
    return {name: root / name for name in WORKSPACE_DIRS}
