#!/usr/bin/env bash
set -euo pipefail

REPO="SzymonPrajs/CodexDataLab"
REPO_URL="https://github.com/${REPO}.git"
DEFAULT_REF="main"

INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
INSTALL_DIR="$INSTALL_ROOT/codexdatalab"
VENV_DIR="$INSTALL_DIR/.venv"

REF="$DEFAULT_REF"
USE_LATEST=true

if [ "${1:-}" = "--nightly" ]; then
  REF="$DEFAULT_REF"
  USE_LATEST=false
fi

if [ "${1:-}" = "--help" ]; then
  echo "Usage: install.sh [--nightly]"
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but not found in PATH." >&2
  exit 1
fi

if $USE_LATEST && command -v curl >/dev/null 2>&1; then
  TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tag_name", ""))')
  if [ -n "$TAG" ]; then
    REF="$TAG"
  else
    REF="$DEFAULT_REF"
  fi
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --upgrade "git+$REPO_URL@$REF"

cat > "$BIN_DIR/codexdatalab" <<EOF_WRAPPER
#!/usr/bin/env bash
exec "$VENV_DIR/bin/codexdatalab" "\$@"
EOF_WRAPPER

cat > "$BIN_DIR/codala" <<EOF_WRAPPER
#!/usr/bin/env bash
exec "$VENV_DIR/bin/codala" "\$@"
EOF_WRAPPER

chmod +x "$BIN_DIR/codexdatalab" "$BIN_DIR/codala"

echo "Installed to $INSTALL_DIR"
if [ "$REF" = "$DEFAULT_REF" ]; then
  echo "Source: $REPO@$DEFAULT_REF"
else
  echo "Source: $REPO@$REF"
fi

echo "Commands: codexdatalab, codala"
echo "Ensure $BIN_DIR is on your PATH."
