#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
APP_NAME="中文转粤语声调.app"
if [ ! -d "$REPO_DIR/dist/$APP_NAME" ]; then
  "$SCRIPT_DIR/build_macos_app.sh"
fi
osascript -e 'tell application "中文转粤语声调" to quit' >/dev/null 2>&1 || true
ditto "$REPO_DIR/dist/$APP_NAME" "/Applications/$APP_NAME"
open "/Applications/$APP_NAME"
