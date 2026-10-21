#!/bin/sh
# run a command chrooted in an image, with /dev and /proc
# usage: in-image.sh ROOT COMMAND...
set -eu
ROOT=${1:?usage: in-image.sh ROOT COMMAND...}; shift
mkdir -p "$ROOT/dev" "$ROOT/proc" "$ROOT/tmp" "$ROOT/var/tmp"
chmod 1777 "$ROOT/tmp" "$ROOT/var/tmp"
# rslave or umount takes the host's /dev/pts with it
mount --rbind /dev "$ROOT/dev"
mount --make-rslave "$ROOT/dev"
mount -t proc proc "$ROOT/proc"
unmount() { umount "$ROOT/proc" 2>/dev/null || true; umount -lR "$ROOT/dev" 2>/dev/null || true; }
trap unmount EXIT INT TERM
rc=0
chroot "$ROOT" /usr/bin/env -i PATH=/usr/bin:/usr/sbin:/bin:/sbin HOME=/root TERM="${TERM:-linux}" "$@" || rc=$?
trap - EXIT INT TERM
unmount
exit $rc
