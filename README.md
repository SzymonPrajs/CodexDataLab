# CodexDataLab

CodexDataLab is a Textual TUI for a data lab workspace with plot and chat panels.

## Requirements

- Python 3.10+

## Install (one command)

Default installs the latest GitHub release into `~/.local/share/codexdatalab` and exposes `codexdatalab` and `codala` in `~/.local/bin`.

```bash
curl -fsSL https://raw.githubusercontent.com/SzymonPrajs/CodexDataLab/main/scripts/install.sh | bash
```

Nightly (from `main`):

```bash
curl -fsSL https://raw.githubusercontent.com/SzymonPrajs/CodexDataLab/main/scripts/install.sh | bash -s -- --nightly
```

If `~/.local/bin` is not in your `PATH`, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Run

```bash
codexdatalab
```

Alias:

```bash
codala
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Run locally:

```bash
codexdatalab
```

## Release (manual)

Releases are created manually via GitHub Actions:

1. Go to Actions → `release` workflow.
2. Click “Run workflow”.
3. Provide a tag (for example `0.1.0`) and optional title.

The workflow builds `sdist`/`wheel` artifacts and publishes a GitHub Release.
