#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip build
python -m build

ls -al dist
