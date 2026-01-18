from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .app import CodexDataLabApp
from .settings import load_settings
from .workspace import find_workspace_root, init_workspace, load_workspace


def _detect_project(start_path: Path, workspace_root: Path) -> str | None:
    projects_dir = workspace_root / "projects"
    if not projects_dir.is_dir():
        return None
    try:
        relative = start_path.relative_to(projects_dir)
    except ValueError:
        return None
    if relative.parts:
        return relative.parts[0]
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="codexdatalab")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize a workspace.")
    init_parser.add_argument("path", nargs="?", default=".", help="Workspace path.")
    init_parser.add_argument("--no-git", action="store_true", help="Disable git init.")

    parser.add_argument(
        "--workspace",
        "-w",
        default=None,
        help="Workspace path to open (defaults to current directory).",
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()

    if args.command == "init":
        target = Path(args.path).resolve()
        workspace = init_workspace(target, settings, git_enabled=not args.no_git)
        print(f"Initialized workspace at {workspace.root}")
        return
    start_path = Path(args.workspace or Path.cwd()).resolve()
    workspace_root = find_workspace_root(start_path)
    if workspace_root is None:
        prompt = f"No workspace found in {start_path}. Initialize here? [y/N]: "
        reply = input(prompt).strip().lower()
        if reply not in {"y", "yes"}:
            print("Workspace not initialized. Exiting.", file=sys.stderr)
            raise SystemExit(1)
        workspace_root = start_path
        init_workspace(workspace_root, settings, git_enabled=True)

    workspace = load_workspace(workspace_root, settings)
    project_name = _detect_project(start_path, workspace_root)
    if project_name:
        workspace.set_active_project(project_name)
    CodexDataLabApp(workspace).run()


if __name__ == "__main__":
    main()
