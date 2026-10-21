#!/bin/sh
# after building packages with tools/pkg/build.sh: drop the versions they replace and sign a new index
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/../..
R=${1:-$TOP/work/repo/x86_64}
APK=${APK:-apk}
KEY=$(ls "$HOME"/.config/chamesle/chamesle-*.rsa | head -n1)
python3 "$HERE/xbps2apk.py" --prune "$R"
"$APK" mkndx --keys-dir "$TOP/keys/apk" --sign-key "$KEY" --description "chamesle $(date +%Y-%m-%d)" \
    --index "$R/Packages.adb" --output "$R/Packages.adb.new" "$R"/*.apk
mv "$R/Packages.adb.new" "$R/Packages.adb"
