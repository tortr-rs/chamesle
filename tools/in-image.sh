#!/bin/sh
# Run a command inside an image tree (chroot) with the host's /dev and a /proc, so it runs with the image's own
# programs and C library whatever the build host runs.
# usage: in-image.sh ROOT COMMAND...   (as root, or as root of a user namespace with its own pid namespace)
set -eu
ROOT=${1:?usage: in-image.sh ROOT COMMAND...}; shift
mkdir -p "$ROOT/dev" "$ROOT/proc" "$ROOT/tmp" "$ROOT/var/tmp"
chmod 1777 "$ROOT/tmp" "$ROOT/var/tmp"
# rslave: the host /dev is a shared mount, so without it unmounting the copy would unmount the host /dev/pts too
mount --rbind /dev "$ROOT/dev"
mount --make-rslave "$ROOT/dev"
mount -t proc proc "$ROOT/proc"
unmount() { umount "$ROOT/proc" 2>/dev/null || true; umount -lR "$ROOT/dev" 2>/dev/null || true; }
trap unmount EXIT INT TERM
# the command's own exit status, not the unmounts' (an EXIT trap's status leaks out in dash)
rc=0
chroot "$ROOT" /usr/bin/env -i PATH=/usr/bin:/usr/sbin:/bin:/sbin HOME=/root TERM="${TERM:-linux}" "$@" || rc=$?
trap - EXIT INT TERM
unmount
exit $rc
