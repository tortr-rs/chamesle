#!/bin/sh
# upload the repo and the isos to sourceforge (needs your ssh key on sourceforge)
#   tools/repo/upload.sh            repo and isos
#   tools/repo/upload.sh iso        just the isos
# run it again if it stops, it carries on where it was
set -eu
cd "$(dirname "$0")/../.."
DEST=${DEST:-torter@frs.sourceforge.net:/home/frs/project/chameslerepos}

if [ "${1:-}" != iso ]; then
    rsync -av --partial --progress -e ssh work/repo/x86_64/ "$DEST/x86_64/"
fi
rsync -av --partial --progress -e ssh out/*.iso out/*.iso.sha256 "$DEST/iso/"
