#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m py_compile "$REPO_DIR/src/cantonese_tone_offline/app.py"
"$PYTHON_BIN" "$REPO_DIR/src/cantonese_tone_offline/app.py" --self-test
