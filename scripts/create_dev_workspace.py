#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from codexdatalab.data_ops import import_dataset
    from codexdatalab.settings import load_settings
    from codexdatalab.workspace import load_workspace
    from codexdatalab.workspace_scaffold import create_workspace_skeleton

    parser = argparse.ArgumentParser(description="Create a local dev/test workspace (gitignored).")
    parser.add_argument(
        "--path",
        type=Path,
        default=repo_root / ".codexdatalab_test_workspace",
        help="Workspace path to create (default: repo/.codexdatalab_test_workspace).",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=repo_root / "tests" / "fixtures",
        help="Directory containing raw-data fixtures to copy into raw/.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate the workspace directory before populating fixtures.",
    )
    parser.add_argument(
        "--overwrite-fixtures",
        action="store_true",
        help="Re-import fixtures even if already present (without deleting the whole workspace).",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Create the workspace skeleton but skip importing fixtures.",
    )
    args = parser.parse_args()

    if args.reset and args.path.exists():
        shutil.rmtree(args.path)

    create_workspace_skeleton(args.path)

    if not args.skip_import:
        settings = load_settings()
        workspace = load_workspace(args.path, settings)
        fixtures_dir = args.fixtures_dir
        if fixtures_dir.is_dir():
            fixtures = sorted(p for p in fixtures_dir.iterdir() if p.is_file())
            for fixture in fixtures:
                try:
                    import_dataset(
                        workspace,
                        fixture,
                        link=False,
                        force_copy=args.overwrite_fixtures,
                        prompt=lambda _: "c",
                    )
                except Exception:
                    if not args.overwrite_fixtures:
                        continue

    print(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
