from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence


def is_git_available() -> bool:
    return shutil.which("git") is not None


def ensure_git_repo(root: Path) -> bool:
    if not is_git_available():
        return False

    git_dir = root / ".git"
    if git_dir.exists():
        return True

    result = subprocess.run(
        ["git", "init"],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def ensure_workspace_gitignore(root: Path, patterns: Iterable[str]) -> None:
    gitignore_path = root / ".gitignore"
    existing = set()
    text = ""
    if gitignore_path.exists():
        text = gitignore_path.read_text()
        existing = {line.strip() for line in text.splitlines()}

    to_add = [pattern for pattern in patterns if pattern not in existing]
    if not to_add:
        return

    if not gitignore_path.exists():
        gitignore_path.write_text("\n".join(to_add) + "\n")
        return

    with gitignore_path.open("a", encoding="utf-8") as handle:
        if text and not text.endswith("\n"):
            handle.write("\n")
        for pattern in to_add:
            handle.write(f"{pattern}\n")


def commit_if_needed(root: Path, message: str, paths: Sequence[str] | None = None) -> bool:
    if not is_git_available():
        return False

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not status.stdout.strip():
        return False

    add_cmd = ["git", "add"]
    if paths:
        add_cmd.extend(paths)
    else:
        add_cmd.append("-A")
    subprocess.run(add_cmd, cwd=root, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return commit.returncode == 0
