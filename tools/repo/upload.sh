#!/bin/sh
# upload the repo and the isos to sourceforge (needs your ssh key on sourceforge)
#   tools/repo/upload.sh            everything
#   tools/repo/upload.sh core       the index and what the editions use (~2G), the rest can follow later
#   tools/repo/upload.sh iso        just the isos
# run it again if it stops, it carries on where it was
set -eu
cd "$(dirname "$0")/../.."
DEST=${DEST:-torter@frs.sourceforge.net:/home/frs/project/chameslerepos}
R=work/repo/x86_64

case "${1:-}" in
iso)
    ;;
core)
    # names from the editions' package lists plus everything they pull in, then their files
    list=$(mktemp)
    python3 - "$R" work/repo/first.list tools/pkg > "$list" <<'EOF'
import os, re, sys
repo, first, pkgs = sys.argv[1:]
names = set(open(first).read().split()) | set(os.listdir(pkgs))
for f in sorted(os.listdir(repo)):
    if f == "Packages.adb" or re.sub(r"-[^-]+-r[0-9]+\.apk$", "", f) in names:
        print(f)
EOF
    rsync -av --partial --progress -e ssh --files-from="$list" "$R/" "$DEST/x86_64/"
    rm -f "$list"
    ;;
*)
    rsync -av --partial --progress -e ssh "$R/" "$DEST/x86_64/"
    ;;
esac
rsync -av --partial --progress -e ssh out/*.iso out/*.iso.sha256 "$DEST/iso/"
