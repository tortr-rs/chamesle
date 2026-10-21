#!/bin/bash
# the weekly sync: stable rolling
#   tools/repo/update.sh                  take upstream versions we've seen for at least HOLD days
#   NOW="php8.4 openssl" tools/repo/update.sh   those go out right away too (security fixes)
#   NOUPLOAD=1 tools/repo/update.sh       everything but the upload
# what it does: fetch the upstream index, note when each new version first showed up, convert the ones that
# waited long enough, check every edition still installs from the new index, then upload and update the website
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/../..
APK=${APK:-apk}
UPSTREAM=${UPSTREAM:-https://repo-default.voidlinux.org/current}
CACHE=${XBPS_CACHE:-$HOME/.cache/chamesle-xbps}
OUT=$TOP/work/repo
R=$OUT/x86_64
HOLD=${HOLD:-7}
KEY=$(ls "$HOME"/.config/chamesle/chamesle-*.rsa | head -n1)
export APK SIGN_KEY=$KEY

echo "== upstream index"
for r in "$UPSTREAM" "$UPSTREAM/nonfree"; do
    curl -sfL "$r/x86_64-repodata" | tar -xO --zstd index.plist > "$OUT/index-${r##*/}.plist"
done
python3 "$HERE/xbps2apk.py" --multi "$OUT"/index-*.plist > "$OUT/multi.list"
export MULTI_PROVIDES=$OUT/multi.list

echo "== what's new, what has waited long enough"
python3 - "$OUT" "$HOLD" "${NOW:-}" "$UPSTREAM" "$HERE" > "$OUT/take.list" <<'EOF'
import json, os, plistlib, sys, time
out, hold, now, upstream = sys.argv[1], float(sys.argv[2]), set(sys.argv[3].split()), sys.argv[4]
sys.path.insert(0, sys.argv[5])
from xbps2apk import SKIP, apkname
seen_file = os.path.join(out, "seen.json")
seen = json.load(open(seen_file)) if os.path.exists(seen_file) else {}
have = set(os.listdir(os.path.join(out, "x86_64")))
today = time.time()
take, waiting = [], []
for name in ("current", "nonfree"):
    base = upstream + ("/nonfree" if name == "nonfree" else "")
    for n, p in plistlib.load(open(os.path.join(out, "index-%s.plist" % name), "rb")).items():
        f = p["pkgver"] + "." + p["architecture"] + ".xbps"
        if SKIP.match(n) or apkname(f) in have:
            continue
        first = seen.setdefault(p["pkgver"], today)
        # NOW names a package or its whole source package (php8.4 takes php8.4-fpm too)
        if n in now or p.get("sourcepkg") in now or today - first >= hold * 86400:
            take.append(base + "/" + f)
        else:
            waiting.append("%s (%d days to go)" % (p["pkgver"], hold - (today - first) // 86400))
# forget versions that are long gone
seen = {k: v for k, v in seen.items() if today - v < 90 * 86400}
json.dump(seen, open(seen_file, "w"))
if take:
    print("\n".join(take))
with open(os.path.join(out, "waiting.list"), "w") as f:
    f.write("".join(w + "\n" for w in sorted(waiting)))
print("%d to take, %d still waiting (waiting.list)" % (len(take), len(waiting)), file=sys.stderr)
EOF
# a week whose check failed is still waiting in Packages.adb.new: try it again
[ -s "$OUT/take.list" ] || [ -e "$R/Packages.adb.new" ] || { echo "nothing to update"; exit 0; }

echo "== download and convert"
mkdir -p "$CACHE"
(cd "$CACHE" && xargs -r -a "$OUT/take.list" -P 8 -n 20 curl -sfL --remote-name-all --retry 3) || true
sed 's|.*/|'"$CACHE"'/|' "$OUT/take.list" > "$OUT/todo.list"
export TMPDIR=$OUT/tmp
mkdir -p "$TMPDIR"
: > "$OUT/errors.log"
unshare --map-root-user --map-auto xargs -a "$OUT/todo.list" -P "$(nproc)" -I{} python3 "$HERE/xbps2apk.py" {} "$R" \
    2>> "$OUT/errors.log" || true
unshare --map-root-user --map-auto rm -rf "$TMPDIR"
unset TMPDIR
# keep the replaced versions until the check passed, so a bad week can be rolled back
old=$(python3 "$HERE/xbps2apk.py" --prune-list "$R")

echo "== index"
"$APK" mkndx --keys-dir "$TOP/keys/apk" --sign-key "$KEY" --description "chamesle $(date +%Y-%m-%d)" \
    --index "$R/Packages.adb" --output "$R/Packages.adb.new" "$R"/*.apk
cp "$R/Packages.adb" "$OUT/Packages.adb.last-week"

echo "== does every edition still install?"
T=$(mktemp -d)
mkdir -p "$T/etc/apk/keys"
cp "$TOP"/keys/apk/*.pub "$T/etc/apk/keys/"
unshare --map-root-user --map-auto "$APK" --root "$T" --arch x86_64 --no-cache --repositories-file /dev/null \
    add --initdb --quiet
# apk only takes an index file that ends in .adb
cp "$R/Packages.adb.new" "$T/Packages.adb"
for e in "$TOP"/editions/*/packages; do
    pkgs=$(sed 's/#.*//' "$TOP/editions/base.packages" "$e" | tr ' \t' '\n\n' | grep -v '^$' | sort -u)
    if ! unshare --map-root-user --map-auto "$APK" --root "$T" --arch x86_64 --no-cache --repositories-file /dev/null \
            -X "$T/Packages.adb" add --simulate --quiet '!runit' '!runit-void' $pkgs; then
        echo "update.sh: $(basename "$(dirname "$e")") doesn't install with this week's packages, nothing published" >&2
        echo "(the new index is $R/Packages.adb.new, last week's is still in place)" >&2
        unshare --map-root-user --map-auto rm -rf "$T"
        exit 1
    fi
done
unshare --map-root-user --map-auto rm -rf "$T"

mv "$R/Packages.adb.new" "$R/Packages.adb"
for f in $old; do rm -f "$R/$f"; done
echo "$(ls "$R"/*.apk | wc -l) packages"
[ -s "$OUT/errors.log" ] && echo "some failed to convert, see $OUT/errors.log"

echo "== website package list"
"$APK" adbdump "$R/Packages.adb" | python3 "$TOP/tools/site/package-list.py" > "$TOP/docs/packages.json"
if ! git -C "$TOP" diff --quiet -- docs/packages.json; then
    git -C "$TOP" add docs/packages.json
    git -C "$TOP" -c user.name=torter -c user.email=koubbamohamedrayan@gmail.com commit -q -m "packages: weekly sync $(date +%Y-%m-%d)"
    git -C "$TOP" push -q origin main || echo "update.sh: couldn't push the package list, push it yourself" >&2
fi

[ -n "${NOUPLOAD:-}" ] && exit 0
echo "== upload"
rsync -av --partial --delete-after -e ssh "$R/" torter@frs.sourceforge.net:/home/frs/project/chameslerepos/x86_64/
