#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from codexdatalab.workspace_scaffold import (
        create_workspace_skeleton,
        populate_raw_from_fixtures,
    )

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
        help="Overwrite existing fixture files in raw/ (without deleting the whole workspace).",
    )
    args = parser.parse_args()

    if args.reset and args.path.exists():
        shutil.rmtree(args.path)

    create_workspace_skeleton(args.path)

    fixtures_dir = args.fixtures_dir
    if fixtures_dir.is_dir():
        fixtures = sorted(p for p in fixtures_dir.iterdir() if p.is_file())
        populate_raw_from_fixtures(args.path, fixtures, overwrite=args.overwrite_fixtures)

    print(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
