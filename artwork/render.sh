#!/bin/sh
# renders the wallpaper, logo icons and boot splash into overlay/
# logo.png is the cut out logo (cutout.py), logo.jpeg the original
set -eu
cd "$(dirname "$0")"
out=../overlay/usr/share
# wallpapers, login screen logo and the start button go in the artwork package
look=../tools/pkg/chamesle-artwork/files/usr/share
resvg=${RESVG:-resvg}

mkdir -p $look/backgrounds/chamesle $out/plymouth/themes/chamesle
python3 wallpaper.py > wallpaper.svg
$resvg -w 3840 -h 2160 wallpaper.svg $look/backgrounds/chamesle/default.png
# the boot menu of an installed system (grub is slow with big images)
$resvg -w 1920 -h 1080 wallpaper.svg $look/backgrounds/chamesle/grub.png

tmp=$(mktemp -d)
cp logo.png $tmp/
printf '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="512" height="512"><image width="512" height="512" xlink:href="logo.png"/></svg>\n' > $tmp/logo.svg
for s in 16 24 32 48 64 128 256; do
    mkdir -p $out/icons/hicolor/${s}x$s/apps
    $resvg --resources-dir $tmp -w $s -h $s $tmp/logo.svg $out/icons/hicolor/${s}x$s/apps/chamesle-start.png
done
$resvg --resources-dir $tmp -w 512 -h 512 $tmp/logo.svg $out/plymouth/themes/chamesle/logo.png
rm -rf $tmp

# text logo for fastfetch
mkdir -p $out/chamesle
python3 ascii.py logo.png 34 > $out/chamesle/logo.txt

# login screen logo: the mark and the name, white text (FONTS=dir with Inter in it)
mkdir -p $look/chamesle
tmp=$(mktemp -d)
cp logo.png $tmp/
cat > $tmp/greeter.svg <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="340" height="80">
  <image xlink:href="logo.png" x="0" y="4" width="72" height="72"/>
  <text x="88" y="54" font-family="Inter, Noto Sans, sans-serif" font-size="40" font-weight="600" fill="#ffffff">Chamesle</text>
</svg>
SVG
$resvg --resources-dir $tmp ${FONTS:+--use-fonts-dir $FONTS} $tmp/greeter.svg $look/chamesle/greeter-logo.png
rm -rf $tmp

# the Chamesle icon theme: Papirus, with the logo as the start button (start-here)
tmp=$(mktemp -d)
cp logo.png $tmp/
printf '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="512" height="512"><image width="512" height="512" xlink:href="logo.png"/></svg>\n' > $tmp/logo.svg
for s in 16 22 24 32 48 64 128 256; do
    mkdir -p $look/icons/Chamesle/${s}x$s/places
    $resvg --resources-dir $tmp -w $s -h $s $tmp/logo.svg $look/icons/Chamesle/${s}x$s/places/start-here.png
done
rm -rf $tmp
