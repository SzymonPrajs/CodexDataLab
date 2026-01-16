---
name: git-stats
description: Compute total additions/deletions (and “lines changed”) over a commit range or time window by aggregating `git log --numstat`.
---

# Git Stats

Answer “how many lines changed” questions by summing `git log --numstat` output across the requested span.

## What to use

Prefer the bundled script:

```bash
python3 .codex/skills/git-stats/scripts/git-stats.py <rev-range> -- <pathspec...>
```

Examples:

```bash
# Last 20 commits on current branch
python3 .codex/skills/git-stats/scripts/git-stats.py HEAD~20..HEAD

# Since a date (uses current HEAD)
python3 .codex/skills/git-stats/scripts/git-stats.py HEAD --since "2026-01-01"

# Only count changes under src/
python3 .codex/skills/git-stats/scripts/git-stats.py HEAD~50..HEAD -- src/
```

## Arguments

- `rev` (positional, optional): Revision or range (e.g. `HEAD`, `main..feature`, `abc..def`). Defaults to `HEAD`.
- `--since <date>` / `--until <date>`: Time window filters (passed to `git log`).
- `--include-merges`: Include merge commits (default is to exclude merges to avoid double counting).
- `--first-parent`: Follow only first-parent history.
- `--`: Everything after `--` is treated as a git pathspec filter.

## Output convention

- Report `additions`, `deletions`, and `changed = additions + deletions`.
- Treat binary changes (`-` in numstat) as `0` additions/deletions and report a `binary` count separately.

