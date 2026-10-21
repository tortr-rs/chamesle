#!/bin/sh
# renders the wallpaper, logo icons and boot splash into overlay/
# logo.png is the cut out logo (cutout.py), logo.jpeg the original
set -eu
cd "$(dirname "$0")"
out=../overlay/usr/share
resvg=${RESVG:-resvg}

mkdir -p $out/backgrounds/chamesle $out/plymouth/themes/chamesle
$resvg -w 1920 -h 1080 wallpaper.svg $out/backgrounds/chamesle/default.png

tmp=$(mktemp -d)
cp logo.png $tmp/
printf '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="512" height="512"><image width="512" height="512" xlink:href="logo.png"/></svg>\n' > $tmp/logo.svg
for s in 16 24 32 48 64 128 256; do
    mkdir -p $out/icons/hicolor/${s}x$s/apps
    $resvg --resources-dir $tmp -w $s -h $s $tmp/logo.svg $out/icons/hicolor/${s}x$s/apps/chamesle-start.png
done
$resvg --resources-dir $tmp -w 512 -h 512 $tmp/logo.svg $out/plymouth/themes/chamesle/logo.png
rm -rf $tmp
