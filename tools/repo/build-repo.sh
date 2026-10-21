#!/bin/bash
# build the chamesle apk repo out of void's glibc packages
#   tools/repo/build-repo.sh                 everything the editions use (from the xbps cache)
#   ALL=1 tools/repo/build-repo.sh           the whole void repo (big, ~50G)
# needs apk-tools 3. the signing key lives outside the repo, in ~/.config/chamesle/
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
APK=${APK:-apk}
VOID=${VOID_REPO:-https://repo-default.voidlinux.org/current}
CACHE=${XBPS_CACHE:-$HOME/.cache/chamesle-xbps}
OUT=${OUT:-$HERE/../../work/repo}
KEYDIR=${KEYDIR:-$HOME/.config/chamesle}
JOBS=${JOBS:-$(nproc)}
ARCH=x86_64
export APK

KEY=$(ls "$KEYDIR"/chamesle-*.rsa 2>/dev/null | head -n1 || true)
if [ -z "$KEY" ]; then
    mkdir -p "$KEYDIR"; chmod 700 "$KEYDIR"
    KEY=$KEYDIR/chamesle-$(date +%Y%m%d).rsa
    openssl genrsa -out "$KEY" 4096 2>/dev/null
    openssl rsa -in "$KEY" -pubout -out "$KEY.pub" 2>/dev/null
    echo "new signing key: $KEY (back it up, don't commit it)"
fi
mkdir -p "$HERE/../../keys/apk"
cp "$KEY.pub" "$HERE/../../keys/apk/"
export SIGN_KEY=$KEY

mkdir -p "$OUT/$ARCH" "$CACHE"
if [ "${ALL:-0}" = 1 ]; then
    # every package in void's index, fetched one by one (skips what's cached)
    for r in "$VOID" "$VOID/nonfree"; do
        curl -sfL "$r/$ARCH-repodata" | tar -xO --zstd index.plist 2>/dev/null | python3 -c '
import plistlib, sys
r = sys.argv[1]
for name, p in plistlib.loads(sys.stdin.buffer.read()).items():
    print(r + "/" + p["pkgver"] + "." + p["architecture"] + ".xbps")' "$r"
    done > "$OUT/void.list"
    echo "$(wc -l < "$OUT/void.list") packages in void"
    while read -r u; do [ -e "$CACHE/${u##*/}" ] || echo "$u"; done < "$OUT/void.list" > "$OUT/fetch.list"
    echo "$(wc -l < "$OUT/fetch.list") to download"
    (cd "$CACHE" && xargs -a "$OUT/fetch.list" -P 8 -n 20 curl -sfL --remote-name-all --retry 3) || true
fi

# only convert what isn't there yet
todo=$OUT/todo.list
: > "$todo"
for x in "$CACHE"/*.xbps; do
    b=$(basename "$x" ".$ARCH.xbps"); b=${b%.noarch.xbps}
    v=${b##*-}; n=${b%-*}
    [ -e "$OUT/$ARCH/$n-${v%_*}-r${v##*_}.apk" ] || echo "$x" >> "$todo"
done
echo "$(wc -l < "$todo") packages to convert"
xargs -a "$todo" -P "$JOBS" -I{} python3 "$HERE/xbps2apk.py" {} "$OUT/$ARCH" 2>> "$OUT/errors.log" || true

# drop old versions, then index
python3 - "$OUT/$ARCH" <<'EOF'
import os, re, subprocess, sys
d = sys.argv[1]; latest = {}
for f in sorted(os.listdir(d)):
    m = re.match(r'^(.+)-([^-]+-r[0-9]+)\.apk$', f)
    if m:
        latest.setdefault(m.group(1), []).append(f)
for name, files in latest.items():
    files.sort(key=lambda f: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', f)])
    for old in files[:-1]:
        os.remove(os.path.join(d, old))
EOF
"$APK" mkndx --keys-dir "$HERE/../../keys/apk" --sign-key "$KEY" --description "chamesle $(date +%Y-%m-%d)" \
    --output "$OUT/$ARCH/Packages.adb" "$OUT/$ARCH"/*.apk
echo "$(ls "$OUT/$ARCH"/*.apk | wc -l) packages in $OUT/$ARCH"
[ -s "$OUT/errors.log" ] && echo "failed: $(wc -l < "$OUT/errors.log") (see $OUT/errors.log)"
true
