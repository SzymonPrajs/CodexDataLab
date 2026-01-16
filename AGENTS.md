# Repository Guidelines

## Project Structure & Module Organization

- Application code lives in `src/codexdatalab/`.
- The CLI entry point is `src/codexdatalab/__main__.py`.
- Textual styling is in `src/codexdatalab/app.tcss`.
- Packaging metadata is in `setup.cfg`, `pyproject.toml`, and `setup.py`.
- Tests are not present yet; add them under `tests/` when introduced.

## Build, Test, and Development Commands

- Create and activate a virtual environment:
  - `python -m venv .venv`
  - `source .venv/bin/activate`
- Install dependencies (editable):
  - `pip install -U pip`
  - `pip install -e .`
- Run the app:
  - `codexdatalab`
  - `python -m codexdatalab`
- Build a wheel (optional):
  - `python -m build`

## Dev Utilities (Local Skills)

### `terminal-shot`

Use during development to capture deterministic PNG screenshots of the real terminal UI (Textual) at scripted moments (PR evidence / visual regression).

- Setup (one-time per machine):
  - `cd .codex/skills/terminal-shot`
  - `npm install`
  - `npx playwright install`
- Run with a tape:
  - `node scripts/terminal-shot.js --cmd "python -m codexdatalab" --tape tapes/demo.yaml`
- Artifacts:
  - `/tmp/tui-shot/frames/*.png`
  - `/tmp/tui-shot/last.png`
- Notes:
  - Default terminal size is 120×34; override with `--cols` / `--rows` (or edit `.codex/skills/terminal-shot/config.json`).
  - Use `--headed` to watch the run live.
  - Tape format is documented in `.codex/skills/terminal-shot/SKILL.md`.

### `git-stats`

Use during development to answer “how many lines changed?” for a commit range or time window by aggregating `git log --numstat`.

- Range:
  - `python3 .codex/skills/git-stats/scripts/git-stats.py HEAD~20..HEAD`
- Time window:
  - `python3 .codex/skills/git-stats/scripts/git-stats.py HEAD --since "2026-01-01" --until "2026-01-31"`
- Limit to paths:
  - `python3 .codex/skills/git-stats/scripts/git-stats.py HEAD~50..HEAD -- src/`
- Reporting:
  - Use `changed = additions + deletions`.
  - Merges are excluded by default to avoid double counting (pass `--include-merges` to include them).

## App Controls (Planned / Reserved)

These key bindings are intended to be implemented for automation later:

- Ctrl+G: Full plot
- Ctrl+T: Full chat
- Ctrl+B: Split view
- Ctrl+F: Toggle menu
- Tab: Toggle focus (menu/chat)
- Arrow Up/Down: Navigate plot list
- Enter: Pin plot / send chat

## Coding Style & Naming Conventions

- Python 3.10+ with 4-space indentation and PEP 8 naming.
- Use `snake_case` for functions/variables and `PascalCase` for classes.
- Keep module names short and descriptive (e.g., `app.py`, `widgets.py`).
- No formatter is configured yet; keep diffs small and consistent with existing style.

## Testing Guidelines

- No test framework is configured yet.
- If adding tests, prefer `pytest` with files named `tests/test_*.py`.
- Document new test commands in `README.md` and this file.

## Commit & Pull Request Guidelines

- There is no established commit convention in history; use concise, imperative summaries.
- Keep commits focused on a single change.
- PRs should include a short summary, validation steps (commands run), and screenshots for UI changes to the Textual app.

## Security & Configuration Notes

- Do not commit secrets or local-only configuration.
- If adding environment-based settings, document them in `README.md` and provide a `.env.example`.
