#!/bin/bash
# makes the live initramfs, everything taken from the image ROOT
# usage: build-initrd.sh ROOT KVER OUTPUT [BUILD_ID]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(readlink -f "${1:?usage: build-initrd.sh ROOT KVER OUTPUT [BUILD_ID]}"); KVER=${2:?}; OUT=${3:?}; BUILD_ID=${4:-}
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
R=$W/root
mkdir -p "$R"/usr/bin "$R"/usr/lib "$R"/{proc,sys,dev,mnt,newroot,overlay,etc}
ln -s usr/bin "$R/bin"; ln -s usr/bin "$R/sbin"; ln -s usr/lib "$R/lib"; ln -s usr/lib "$R/lib64"
ln -s lib "$R/usr/lib64"   # the loader looks in /usr/lib64

# follow symlinks inside the image
resolve() {
    local p=$1 t i
    for i in 1 2 3 4 5 6 7 8 9 10; do
        [ -L "$ROOT$p" ] || break
        t=$(readlink "$ROOT$p"); case "$t" in /*) p=$t ;; *) p=$(dirname "$p")/$t ;; esac
    done
    [ -e "$ROOT$p" ] && printf '%s\n' "$p"
}
# copy a binary and the libs it needs
seen=" "
copy_elf() {
    local p real lib interp
    real=$(resolve "$1") || { echo "initrd: $1 is not in the image" >&2; exit 1; }
    case "$seen" in *" $real "*) return 0 ;; esac
    seen="$seen$real "
    mkdir -p "$R$(dirname "$1")"; cp -L "$ROOT$real" "$R$1"
    interp=$(readelf -l "$ROOT$real" 2>/dev/null | sed -n 's/.*Requesting program interpreter: \(.*\)]/\1/p')
    [ -z "$interp" ] || copy_elf "$interp"
    for lib in $(readelf -d "$ROOT$real" 2>/dev/null | sed -n 's/.*NEEDED.*\[\(.*\)\]/\1/p'); do
        p=$(resolve "/usr/lib/$lib") || { echo "initrd: $1 needs $lib, which is not in the image" >&2; exit 1; }
        copy_elf "/usr/lib/$lib"
    done
}

echo "== busybox and cryptsetup from the image"
copy_elf /usr/bin/busybox
copy_elf /usr/bin/cryptsetup
BB() { "$ROOT/usr/lib/ld-linux-x86-64.so.2" --library-path "$ROOT/usr/lib" "$ROOT/usr/bin/busybox" "$@" 2>/dev/null \
       || "$ROOT/usr/bin/busybox" "$@"; }
applets=$(BB --list)
[ -n "$applets" ] || { echo "initrd: cannot list busybox's applets" >&2; exit 1; }
for a in $applets; do [ -e "$R/usr/bin/$a" ] || ln -s busybox "$R/usr/bin/$a"; done
echo "$applets" | grep -x modprobe >/dev/null || { echo "initrd: busybox has no modprobe applet" >&2; exit 1; }
# plymouth
if [ -x "$ROOT/usr/bin/plymouthd" ]; then
    echo "== plymouth"
    copy_elf /usr/bin/plymouthd
    copy_elf /usr/bin/plymouth
    copy_elf /usr/bin/udevd
    copy_elf /usr/bin/udevadm
    install -Dm644 "$ROOT/usr/lib/udev/rules.d/71-plymouth-seat.rules" "$R/usr/lib/udev/rules.d/71-plymouth-seat.rules"
    for p in script text details label renderers/frame-buffer renderers/drm; do
        [ -e "$ROOT/usr/lib/plymouth/$p.so" ] && copy_elf "/usr/lib/plymouth/$p.so"
    done
    theme=$(sed -n 's/^Theme=//p' "$ROOT/etc/plymouth/plymouthd.conf" 2>/dev/null)
    mkdir -p "$R/usr/share/plymouth/themes" "$R/etc/plymouth"
    cp "$ROOT/usr/share/plymouth/plymouthd.defaults" "$R/usr/share/plymouth/"
    cp "$ROOT/etc/plymouth/plymouthd.conf" "$R/etc/plymouth/" 2>/dev/null || true
    [ -n "$theme" ] && cp -a "$ROOT/usr/share/plymouth/themes/$theme" "$R/usr/share/plymouth/themes/"
    # a font for the passphrase prompt
    cp -a "$ROOT/etc/fonts" "$R/etc/" 2>/dev/null || true
    font=$(find "$ROOT/usr/share/fonts" -name DejaVuSans.ttf 2>/dev/null | head -n1 || true)
    [ -n "$font" ] && install -Dm644 "$font" "$R/usr/share/fonts/DejaVuSans.ttf"
fi

install -m755 "$HERE/init" "$R/init"
[ -z "$BUILD_ID" ] || echo "$BUILD_ID" > "$R/build-id"

echo "== kernel modules for finding the medium and the root ($KVER)"
MODDIR=$ROOT/usr/lib/modules/$KVER
[ -f "$MODDIR/modules.dep" ] || { echo "initrd: no modules.dep for $KVER in the image" >&2; exit 1; }
INITRD_MODULES=${INITRD_MODULES:-"isofs udf squashfs overlay loop sr_mod cdrom sd_mod usb_storage uas
    xhci_pci xhci_hcd ehci_pci ehci_hcd ohci_pci ohci_hcd uhci_hcd ahci libahci nvme nvme_core mmc_block
    virtio_blk virtio_scsi virtio_pci virtio virtio_ring scsi_mod scsi_common libata ata_piix ata_generic pata_acpi
    vmw_pvscsi mptspi mptsas BusLogic hv_storvsc hv_vmbus vfat fat exfat ext4 xfs btrfs f2fs nls_cp437 nls_ascii nls_utf8
    dm_mod dm_crypt"}
# whole driver dirs, the stick could be behind any controller
INITRD_MODDIRS=${INITRD_MODDIRS:-"kernel/drivers/ata/ kernel/drivers/scsi/ kernel/drivers/nvme/host/ kernel/drivers/mmc/host/
    kernel/drivers/usb/storage/ kernel/drivers/usb/host/ kernel/drivers/block/virtio_blk kernel/drivers/cdrom/
    kernel/drivers/virtio/ kernel/drivers/hv/"}
INITRD_EXCLUDE=${INITRD_EXCLUDE:-"scsi_debug null_blk brd ublk_drv zram"}
DEST=$R/usr/lib/modules/$KVER
mkdir -p "$DEST"
wanted=$(awk -v mods="$INITRD_MODULES" -v dirs="$INITRD_MODDIRS" -v excl="$INITRD_EXCLUDE" '
    BEGIN { n = split(mods, a, /[ \t\n]+/); for (i = 1; i <= n; i++) if (a[i] != "") want[a[i]] = 1
            n = split(excl, a, /[ \t\n]+/); for (i = 1; i <= n; i++) if (a[i] != "") skip[a[i]] = 1
            nd = split(dirs, dl, /[ \t\n]+/) }
    { split($0, kv, ":"); f = kv[1]; b = f; sub(/.*\//, "", b); sub(/\.ko.*/, "", b); gsub(/-/, "_", b)
      if (!(b in want) && !(b in skip)) for (i = 1; i <= nd; i++) if (dl[i] != "" && index(f, dl[i]) == 1) want[b] = 1
      if ((b in want) && !(b in skip)) { print f; m = split(kv[2], d, " "); for (i = 1; i <= m; i++) print d[i] } }' \
    "$MODDIR/modules.dep" | sort -u)
count=0
for f in $wanted; do
    src=$MODDIR/$f; [ -f "$src" ] || continue
    out=$DEST/${f%.ko*}.ko; mkdir -p "$(dirname "$out")"
    case "$src" in
        *.ko)     cp "$src" "$out" ;;
        *.ko.zst) zstd -dqc "$src" > "$out" ;;
        *.ko.xz)  xz -dc "$src" > "$out" ;;
        *.ko.gz)  gzip -dc "$src" > "$out" ;;
        *) continue ;;
    esac
    count=$((count + 1))
done
cp "$MODDIR"/modules.order "$MODDIR"/modules.builtin "$MODDIR"/modules.builtin.modinfo "$DEST/" 2>/dev/null || true
depmod -b "$R/usr" "$KVER" 2>/dev/null || depmod -b "$R" "$KVER"
[ "$count" -gt 0 ] || { echo "initrd: no kernel modules copied" >&2; exit 1; }
echo "   $count kernel modules"

( cd "$R" && find . | sort | cpio -o -H newc -R 0:0 --quiet ) | zstd -q -19 -T0 > "$OUT"
ls -lh "$OUT"
