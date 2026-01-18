#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "schemas" / "codex_app_server"
    out_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["codex", "app-server", "generate-json-schema", "--out", str(out_dir)],
        check=True,
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
