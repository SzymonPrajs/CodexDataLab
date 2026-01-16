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
  - Alias: `codala`
- Build a wheel (optional):
  - `python -m build`

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
- There is no established commit convention in history; use concise, imperative summaries (e.g., `Add CLI alias codala`).
- Keep commits focused on a single change.
- PRs should include a short summary, validation steps (commands run), and screenshots for UI changes to the Textual app.

## Security & Configuration Notes
- Do not commit secrets or local-only configuration.
- If adding environment-based settings, document them in `README.md` and provide a `.env.example`.
