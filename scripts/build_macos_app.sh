#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
APP_NAME="中文转粤语声调.app"
OUT_DIR="$REPO_DIR/dist"
APP_DIR="$OUT_DIR/$APP_NAME"
RES_DIR="$APP_DIR/Contents/Resources"
MACOS_DIR="$APP_DIR/Contents/MacOS"
mkdir -p "$OUT_DIR"
if [ -d "$APP_DIR" ]; then
  mv "$APP_DIR" "$OUT_DIR/$APP_NAME.old-$(date +%s)"
fi
mkdir -p "$RES_DIR" "$MACOS_DIR"
cp "$REPO_DIR/app-template/Contents/Info.plist" "$APP_DIR/Contents/Info.plist"
cp "$REPO_DIR/app-template/Contents/MacOS/CantoneseTranslatorTone" "$MACOS_DIR/CantoneseTranslatorTone"
chmod +x "$MACOS_DIR/CantoneseTranslatorTone"
cp "$REPO_DIR/src/cantonese_tone_offline/app.py" "$RES_DIR/app.py"
cp "$REPO_DIR/src/cantonese_tone_offline/lexicon.json" "$RES_DIR/lexicon.json"
cp "$REPO_DIR/src/cantonese_tone_offline/s2t_opencc.json" "$RES_DIR/s2t_opencc.json"
cd "$OUT_DIR"
ditto -c -k --keepParent "$APP_NAME" chinese-to-cantonese-tone-app-expanded.zip
printf '已生成：%s
' "$APP_DIR"
printf '已生成：%s
' "$OUT_DIR/chinese-to-cantonese-tone-app-expanded.zip"
