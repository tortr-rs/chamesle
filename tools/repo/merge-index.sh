#!/bin/bash
# put packages in the published repo without having the whole repo here: the index on sourceforge is taken
# as it is, the new packages replace their old versions in it, and it's signed with your key
#   tools/repo/merge-index.sh work/repo/x86_64/foo-1.0-r1.apk ...   -> work/publish/x86_64/
#   tools/repo/merge-index.sh                                        just re-sign the published index (a new key)
# then upload work/publish/x86_64/ (tools/repo/upload.sh publish). packages already there stay as they are:
# apk trusts them through the hashes in the signed index, their own signatures don't matter
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/../..
APK=${APK:-apk}
INDEX=${INDEX:-https://downloads.sourceforge.net/project/chameslerepos/x86_64/Packages.adb}
KEY=$(ls "$HOME"/.config/chamesle/chamesle-*.rsa | sort | tail -n1)
OUT=${OUT:-$TOP/work/publish/x86_64}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

curl -fsSL -o "$T/old.adb" "$INDEX"
# only an index we signed: one of the keys in keys/apk has to check out
"$APK" adbdump --keys-dir "$TOP/keys/apk" "$T/old.adb" > "$T/old.yaml"
grep -q '^# sig .*: OK$' "$T/old.yaml" || { echo "merge-index: $INDEX isn't signed by a key in keys/apk" >&2; exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"
: > "$T/new.yaml"
if [ $# -gt 0 ]; then
    cp "$@" "$OUT/"
    "$APK" mkndx --keys-dir "$TOP/keys/apk" --output "$T/new.adb" "$@"
    "$APK" adbdump "$T/new.adb" > "$T/new.yaml"
fi

python3 - "$T/old.yaml" "$T/new.yaml" "chamesle $(date +%Y-%m-%d)" > "$T/index.yaml" <<'EOF'
import sys
def entries(path):
    out, cur = {}, None
    for line in open(path):
        if line.startswith('  - name: '):
            cur = line[10:].strip()
            out[cur] = []
        elif not line.startswith('    ') and not line.startswith('  - '):
            cur = None
        if cur:
            out[cur].append(line)
    return out
old, new = entries(sys.argv[1]), entries(sys.argv[2])
for name in new:
    print(('replaced ' if name in old else 'added ') + name, file=sys.stderr)
old.update(new)
# adbgen needs to know what kind of file it's making
print(next(l for l in open(sys.argv[1]) if l.startswith('#%SCHEMA')).strip())
print('description: ' + sys.argv[3])
print('packages: # %d items' % len(old))
for name in sorted(old):
    sys.stdout.write(''.join(old[name]))
EOF
"$APK" adbgen "$T/index.yaml" > "$OUT/Packages.adb"
"$APK" adbsign --allow-untrusted --reset-signatures --sign-key "$KEY" "$OUT/Packages.adb"
"$APK" adbdump --keys-dir "$TOP/keys/apk" "$OUT/Packages.adb" | grep -q '^# sig .*: OK$'
echo "$(grep -c '^  - name: ' "$T/index.yaml") packages, signed with $(basename "$KEY"): $OUT"
