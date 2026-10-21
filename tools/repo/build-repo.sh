#!/bin/bash
# build the chamesle apk repo from upstream xbps packages
#   tools/repo/build-repo.sh                 everything the editions use (from the xbps cache)
#   ALL=1 tools/repo/build-repo.sh           the whole upstream repo (big, ~50G)
# needs apk-tools 3. the signing key lives outside the repo, in ~/.config/chamesle/
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
APK=${APK:-apk}
UPSTREAM=${UPSTREAM:-https://repo-default.voidlinux.org/current}
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
    # every package in the upstream index, fetched one by one (skips what's cached)
    for r in "$UPSTREAM" "$UPSTREAM/nonfree"; do
        f=$OUT/index-${r##*/}.plist
        curl -sfL "$r/$ARCH-repodata" | tar -xO --zstd index.plist > "$f" 2>/dev/null
        python3 -c '
import plistlib, sys
r = sys.argv[1]
for name, p in plistlib.load(open(sys.argv[2], "rb")).items():
    print(r + "/" + p["pkgver"] + "." + p["architecture"] + ".xbps")' "$r" "$f"
    done > "$OUT/upstream.list"
    echo "$(wc -l < "$OUT/upstream.list") packages upstream"
    while read -r u; do [ -e "$CACHE/${u##*/}" ] || echo "$u"; done < "$OUT/upstream.list" > "$OUT/fetch.list"
    echo "$(wc -l < "$OUT/fetch.list") to download"
    (cd "$CACHE" && xargs -r -a "$OUT/fetch.list" -P 8 -n 20 curl -sfL --remote-name-all --retry 3) || true
fi

# only convert what isn't there yet, what the editions need first
todo=$OUT/todo.list
FIRST=
if ls "$OUT"/index-*.plist >/dev/null 2>&1; then
    FIRST=$OUT/first.list
    # the editions' packages and what our own packages (tools/pkg) depend on
    { sed 's/#.*//' "$HERE"/../../editions/*.packages "$HERE"/../../editions/*/packages
      sed -n 's/^depends="\(.*\)"/\1/p' "$HERE"/../pkg/*/recipe; } | tr ' \t' '\n\n' | grep -v '^$' |
        python3 "$HERE/xbps2apk.py" --closure "$OUT"/index-*.plist > "$FIRST"
fi
python3 "$HERE/xbps2apk.py" --todo "$CACHE" "$OUT/$ARCH" $FIRST > "$todo"
if ls "$OUT"/index-*.plist >/dev/null 2>&1; then
    python3 "$HERE/xbps2apk.py" --multi "$OUT"/index-*.plist > "$OUT/multi.list"
fi
[ -s "$OUT/multi.list" ] && export MULTI_PROVIDES=$OUT/multi.list
echo "$(wc -l < "$todo") packages to convert"
# big packages don't fit in a tmpfs /tmp
export TMPDIR=$OUT/tmp
mkdir -p "$TMPDIR"
: > "$OUT/errors.log"
# as root of a user namespace, so files keep their real owners
unshare --map-root-user --map-auto xargs -a "$todo" -P "$JOBS" -I{} python3 "$HERE/xbps2apk.py" {} "$OUT/$ARCH" \
    2>> "$OUT/errors.log" || true

# drop old versions, then index
python3 "$HERE/xbps2apk.py" --prune "$OUT/$ARCH"
"$APK" mkndx --keys-dir "$HERE/../../keys/apk" --sign-key "$KEY" --description "chamesle $(date +%Y-%m-%d)" \
    --output "$OUT/$ARCH/Packages.adb" "$OUT/$ARCH"/*.apk
echo "$(ls "$OUT/$ARCH"/*.apk | wc -l) packages in $OUT/$ARCH"
python3 "$HERE/apps.py" "$OUT/$ARCH"
unshare --map-root-user --map-auto rm -rf "$TMPDIR"
python3 "$HERE/xbps2apk.py" --todo "$CACHE" "$OUT/$ARCH" > "$OUT/failed.list"
n=$(wc -l < "$OUT/failed.list")
[ "$n" -gt 0 ] && echo "$n failed (names in $OUT/failed.list, details in $OUT/errors.log)"
true
