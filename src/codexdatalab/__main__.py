from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .app import CodexDataLabApp
from .data_ops import import_dataset
from .settings import load_settings
from .transform_ops import init_transform, run_transform
from .workspace import find_workspace_root, init_workspace, load_workspace


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="codexdatalab")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize a workspace.")
    init_parser.add_argument("path", nargs="?", default=".", help="Workspace path.")
    init_parser.add_argument("--no-git", action="store_true", help="Disable git init.")

    import_parser = subparsers.add_parser("import", help="Import a local dataset.")
    import_parser.add_argument("path", help="Path to a CSV or Parquet file.")
    import_parser.add_argument("--link", action="store_true", help="Link instead of copy.")
    import_parser.add_argument(
        "--force-copy", action="store_true", help="Copy even if the file is large."
    )
    import_parser.add_argument(
        "--workspace",
        "-w",
        default=None,
        help="Workspace path to use (defaults to current directory).",
    )

    transform_parser = subparsers.add_parser("transform", help="Manage transforms.")
    transform_sub = transform_parser.add_subparsers(dest="transform_command")
    transform_init = transform_sub.add_parser("init", help="Create a transform template.")
    transform_init.add_argument("dataset_id", help="Input dataset id.")
    transform_init.add_argument("name", help="Name for the transform.")
    transform_init.add_argument("--why", default="", help="Rationale for this transform.")

    transform_run = transform_sub.add_parser("run", help="Run a transform.")
    transform_run.add_argument("path", help="Path to the transform script.")
    transform_run.add_argument("--input", dest="input_id", help="Input dataset id.")
    transform_run.add_argument("--why", default="", help="Rationale for this run.")
    transform_parser.add_argument(
        "--workspace",
        "-w",
        default=None,
        help="Workspace path to use (defaults to current directory).",
    )

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
    if args.command == "import":
        start_path = Path(args.workspace or Path.cwd()).resolve()
        workspace_root = find_workspace_root(start_path)
        if workspace_root is None:
            raise SystemExit("No workspace found. Run `codexdatalab init` first.")
        workspace = load_workspace(workspace_root, settings)

        def prompt(message: str) -> str:
            return input(message)

        record = import_dataset(
            workspace,
            Path(args.path),
            link=args.link,
            force_copy=args.force_copy,
            prompt=prompt,
        )
        print(f"Imported dataset {record.dataset_id} -> {record.path}")
        return
    if args.command == "transform":
        start_path = Path(args.workspace or Path.cwd()).resolve()
        workspace_root = find_workspace_root(start_path)
        if workspace_root is None:
            raise SystemExit("No workspace found. Run `codexdatalab init` first.")
        workspace = load_workspace(workspace_root, settings)
        if args.transform_command == "init":
            path = init_transform(workspace, args.dataset_id, args.name, why=args.why)
            print(f"Transform created at {path}")
            return
        if args.transform_command == "run":
            outputs = run_transform(
                workspace,
                Path(args.path),
                input_dataset_id=args.input_id,
                why=args.why,
            )
            print(f"Transform produced {len(outputs)} dataset(s).")
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
    CodexDataLabApp(workspace).run()


if __name__ == "__main__":
    main()
