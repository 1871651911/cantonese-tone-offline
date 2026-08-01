#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" "$REPO_DIR/src/cantonese_tone_offline/app.py" "$@"
