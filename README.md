# CodexDataLab

CodexDataLab provides a terminal-based environment for data analysis and visualization, with Codex integrated to support exploratory analysis and rapid iteration.

## Quick Start

Install the latest release with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/SzymonPrajs/CodexDataLab/main/scripts/install.sh | bash
```

Once installed, launch the application:

```bash
codexdatalab
# Or use the short alias:
codala
```

### Installation Details

**Prerequisites:** Python 3.10 or higher.

The script installs the application to `~/.local/share/codexdatalab` and links binaries in `~/.local/bin`. If the command is not found after installation, ensure your local bin is in your path:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Nightly Builds**
To install the latest changes from the `main` branch, use the nightly flag:

```bash
curl -fsSL https://raw.githubusercontent.com/SzymonPrajs/CodexDataLab/main/scripts/install.sh | bash -s -- --nightly
```

## Development

To set up the project locally for contribution or modification:

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install -U pip
pip install -e .

# Run locally
codexdatalab
```
