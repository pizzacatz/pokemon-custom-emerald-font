#!/bin/sh
# Run a FontForge python script: prefer the distro package, fall back to the project AppImage.
# usage: scripts/ff.sh <script.py> [args]
DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$1"; shift
case "$SCRIPT" in /*) ;; *) SCRIPT="$(pwd)/$SCRIPT";; esac
if command -v fontforge >/dev/null 2>&1; then
  exec fontforge -lang=py -script "$SCRIPT" "$@"
elif [ -x "$DIR/tools/squashfs-root/AppRun" ]; then
  exec "$DIR/tools/squashfs-root/AppRun" -lang=py -script "$SCRIPT" "$@"
else
  echo "FontForge not found: sudo apt install fontforge python3-fontforge, or run scripts/get_fontforge.sh" >&2; exit 1
fi
