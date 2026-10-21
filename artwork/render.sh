#!/bin/sh
# Render the artwork the editions ship (the PNGs are committed; run this after changing an SVG). Needs resvg.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/../overlay/usr/share
RESVG=${RESVG:-resvg}
mkdir -p "$OUT/backgrounds/chamesle" "$OUT/icons/hicolor/scalable/apps"
$RESVG -w 1920 -h 1080 "$HERE/wallpaper.svg" "$OUT/backgrounds/chamesle/default.png"
cp "$HERE/start.svg" "$OUT/icons/hicolor/scalable/apps/chamesle-start.svg"
echo "rendered into $OUT"
