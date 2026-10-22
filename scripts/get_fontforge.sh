#!/bin/sh
# No-sudo fallback: fetch the official FontForge AppImage into tools/ and unpack it (no FUSE needed).
set -e
cd "$(dirname "$0")/../tools"
url=$(curl -s https://api.github.com/repos/fontforge/fontforge/releases/latest | grep browser_download_url | grep -i appimage | grep -v sha | head -1 | cut -d'"' -f4)
curl -L "$url" -o FontForge.AppImage && chmod +x FontForge.AppImage && ./FontForge.AppImage --appimage-extract >/dev/null && rm FontForge.AppImage
./squashfs-root/AppRun -lang=py -c "import fontforge; print('FontForge', fontforge.version())"
