#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Stats:
    additions: int
    deletions: int
    binary_files: int
    file_entries: int

    @property
    def changed(self) -> int:
        return self.additions + self.deletions


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="git-stats",
        description="Aggregate git --numstat additions/deletions over a revision range or time window.",
    )
    parser.add_argument(
        "rev",
        nargs="?",
        default="HEAD",
        help="Revision or range (e.g. HEAD, main..feature, abc..def). Defaults to HEAD.",
    )
    parser.add_argument("--since", dest="since", help="Only include commits after this date (git log --since).")
    parser.add_argument("--until", dest="until", help="Only include commits before this date (git log --until).")
    parser.add_argument(
        "--include-merges",
        action="store_true",
        help="Include merge commits (default: exclude to avoid double counting).",
    )
    parser.add_argument(
        "--first-parent",
        action="store_true",
        help="Follow only the first parent on merge commits (git log --first-parent).",
    )
    parser.add_argument(
        "paths",
        nargs=argparse.REMAINDER,
        help="Optional pathspec filter (use '-- path/...').",
    )
    return parser.parse_args(argv)


def build_git_log_cmd(args: argparse.Namespace) -> list[str]:
    cmd: list[str] = ["git", "log", "--numstat", "--format="]
    if not args.include_merges:
        cmd.append("--no-merges")
    if args.first_parent:
        cmd.append("--first-parent")
    if args.since:
        cmd.append(f"--since={args.since}")
    if args.until:
        cmd.append(f"--until={args.until}")

    cmd.append(args.rev)

    # Accept either:
    #   - no paths
    #   - paths starting with "--"
    #   - plain paths (we'll still add "--" for safety)
    paths = list(args.paths or [])
    if paths:
        if paths[0] == "--":
            cmd.extend(paths)
        else:
            cmd.append("--")
            cmd.extend(paths)

    return cmd


def run_git_log(cmd: list[str]) -> str:
    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return completed.stdout


def parse_numstat(output: str) -> Stats:
    additions = 0
    deletions = 0
    binary_files = 0
    file_entries = 0

    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        add_s, del_s = parts[0], parts[1]
        file_entries += 1

        if add_s == "-" or del_s == "-":
            binary_files += 1
            continue

        try:
            additions += int(add_s)
            deletions += int(del_s)
        except ValueError:
            # Defensive: ignore malformed lines.
            continue

    return Stats(additions=additions, deletions=deletions, binary_files=binary_files, file_entries=file_entries)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    cmd = build_git_log_cmd(args)
    output = run_git_log(cmd)
    stats = parse_numstat(output)

    print(f"additions: {stats.additions}")
    print(f"deletions: {stats.deletions}")
    print(f"changed: {stats.changed}")
    print(f"file_entries: {stats.file_entries}")
    print(f"binary_files: {stats.binary_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

