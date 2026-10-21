#!/bin/bash
# Build a Chamesle Linux live/installer ISO for one edition, from Void Linux's glibc packages (no compiling):
#
#   sudo EDITION=xfce ./build.sh        -> out/chamesle-VERSION-EDITION-x86_64.iso (+ .sha256)
#
# 1. installs editions/base.packages + editions/EDITION/packages into a new root with xbps (runit is blocked:
#    dinit is the init system), from Void's repository, packages cached in XBPS_CACHE
# 2. copies overlay/ (services, branding, Flathub, artwork) and editions/EDITION/overlay/ (the desktop's look) on top
# 3. installs the Fluent theme and icons, sets up the live user, locale and Chamesle branding
# 4. builds the initramfs from the image (tools/initrd), packs the root into a squashfs and masters a hybrid
#    BIOS+UEFI ISO with GRUB
#
# Needs: xbps (xbps-install; Void's static build works on any distribution), mksquashfs, xorriso, grub-mkrescue with
# the i386-pc and x86_64-efi platforms, readelf, zstd, cpio, depmod and curl. Run it as root (sudo).
#   EDITION=...     xfce (default), and later mate, cinnamon, gnome, kde
#   VOID_REPO=...   the Void mirror (default https://repo-default.voidlinux.org/current)
#   XBPS_CACHE=...  downloaded packages, kept between builds (default ~/.cache/chamesle-xbps of the sudo user)
#   WORK=... OUT=... work and output directories (default work/EDITION and out/)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
EDITION=${EDITION:-xfce}
[ -f "$HERE/editions/$EDITION/packages" ] || { echo "build: no edition '$EDITION' (editions/*/packages)" >&2; exit 1; }
VERSION=$(cat "$HERE/VERSION"); CODENAME=$(cat "$HERE/CODENAME" 2>/dev/null || true)
EDITION_NAME=$(sed -n 's/^name=//p' "$HERE/editions/$EDITION/edition" 2>/dev/null || echo "$EDITION")
WORK=${WORK:-$HERE/work/$EDITION}; ROOT=$WORK/root; ISO_DIR=$WORK/iso
OUT=${OUT:-$HERE/out}; ISO=$OUT/chamesle-$VERSION-$EDITION-x86_64.iso
REPO=${VOID_REPO:-https://repo-default.voidlinux.org/current}
home=$(getent passwd "${SUDO_USER:-$(id -un)}" | cut -d: -f6)
CACHE=${XBPS_CACHE:-$home/.cache/chamesle-xbps}
IN=$HERE/tools/in-image.sh

missing=
for t in xbps-install mksquashfs xorriso readelf zstd cpio depmod curl; do command -v "$t" >/dev/null || missing="$missing $t"; done
command -v grub-mkrescue >/dev/null || command -v grub2-mkrescue >/dev/null || missing="$missing grub-mkrescue"
[ -z "$missing" ] || { echo "build: missing tools:$missing" >&2; exit 1; }
GRUB_MKRESCUE=$(command -v grub-mkrescue || command -v grub2-mkrescue)
packages() { sed 's/#.*//' "$HERE/editions/base.packages" "$HERE/editions/$EDITION/packages" | tr ' \t' '\n\n' | grep -v '^$' | sort -u; }

echo "=== [1/5] INSTALLING THE SYSTEM ($EDITION_NAME, from Void Linux's packages)"
rm -rf "$WORK"; mkdir -p "$ROOT/var/db/xbps/keys" "$ROOT/etc/xbps.d" "$CACHE" "$ISO_DIR/live" "$OUT"
cp "$HERE"/keys/*.plist "$ROOT/var/db/xbps/keys/"
cp "$HERE/overlay/etc/xbps.d/00-chamesle.conf" "$ROOT/etc/xbps.d/"
# the packages' install scripts run chrooted in the new root: give them /dev and /proc (Python's bytecode compiler
# and the kernel's hooks need them)
mkdir -p "$ROOT/dev" "$ROOT/proc"
mount --rbind /dev "$ROOT/dev"; mount --make-rslave "$ROOT/dev"; mount -t proc proc "$ROOT/proc"
trap 'umount "$ROOT/proc" 2>/dev/null; umount -lR "$ROOT/dev" 2>/dev/null; true' EXIT
XBPS_ARCH=x86_64 xbps-install -S -y -r "$ROOT" -R "$REPO" -R "$REPO/nonfree" -c "$CACHE" $(packages)
umount "$ROOT/proc"; umount -lR "$ROOT/dev"; trap - EXIT
if [ -e "$ROOT/usr/bin/runit" ]; then echo "build: runit got installed; dinit must be the only init" >&2; exit 1; fi

echo "=== [2/5] CHAMESLE: SERVICES, LOOK AND BRANDING"
cp -a "$HERE/overlay/." "$ROOT/"
cp -a "$HERE/editions/$EDITION/overlay/." "$ROOT/"
"$HERE/tools/themes.sh" "$ROOT"
# Xfce's built-in wallpapers point at Chamesle's, so a monitor of any name gets it before xfce4-desktop.xml knows it
for f in xfce-x.svg xfce-shapes.svg xfce-stripes.png xfce-teal.png xfce-verticals.png; do
    [ -d "$ROOT/usr/share/backgrounds/xfce" ] && ln -sf ../chamesle/default.png "$ROOT/usr/share/backgrounds/xfce/$f"
done
# the Windows key opens the Start menu
KS=$ROOT/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml
if [ -f "$KS" ] && ! grep -q 'xfce4-popup-whiskermenu' "$KS"; then
    sed -i 's|^\( *\)<property name="&lt;Super&gt;e" type="string" value="thunar"/>|&\n\1<property name="Super_L" type="string" value="xfce4-popup-whiskermenu"/>|' "$KS"
fi
# identity
SUFFIX=${CODENAME:+ $CODENAME}
cat > "$ROOT/etc/os-release" <<EOF
NAME="Chamesle Linux"
PRETTY_NAME="Chamesle Linux $VERSION$SUFFIX ($EDITION_NAME)"
ID=chamesle
ID_LIKE=void
VERSION="$VERSION${CODENAME:+ ($CODENAME)}"
VERSION_ID="$VERSION"
${CODENAME:+VERSION_CODENAME=$(echo "$CODENAME" | tr '[:upper:]' '[:lower:]')}
VARIANT="$EDITION_NAME"
VARIANT_ID=$EDITION
HOME_URL="https://chamesle.org/"
LOGO=chamesle-start
EOF
rm -f "$ROOT/usr/lib/os-release"; ln -sf ../../etc/os-release "$ROOT/usr/lib/os-release"
printf 'Chamesle Linux %s%s \\r (\\l)\n\n' "$VERSION" "$SUFFIX" > "$ROOT/etc/issue"
echo chamesle > "$ROOT/etc/hostname"
mkdir -p "$ROOT/usr/share/chamesle"
echo "$VERSION" > "$ROOT/usr/share/chamesle/version"; echo "$EDITION" > "$ROOT/usr/share/chamesle/edition"
# English (US) UTF-8 by default; the installer changes it
grep -qx 'en_US.UTF-8 UTF-8' "$ROOT/etc/default/libc-locales" 2>/dev/null || echo 'en_US.UTF-8 UTF-8' >> "$ROOT/etc/default/libc-locales"
echo 'LANG=en_US.UTF-8' > "$ROOT/etc/locale.conf"
ln -sf /usr/share/zoneinfo/UTC "$ROOT/etc/localtime"
"$IN" "$ROOT" /usr/bin/xbps-reconfigure -f glibc-locales
"$IN" "$ROOT" /usr/bin/fc-cache -f
"$IN" "$ROOT" /usr/bin/gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true

echo "=== [3/5] THE LIVE USER"
# "live", no password, administrator without a password, logged in by LightDM by itself. Only the live image
# has this: the installer removes the autologin and the passwordless sudo, and creates your own user.
"$IN" "$ROOT" /usr/bin/useradd -m -c "Live session" -s /bin/bash -G wheel,audio,video,input,network,storage,optical,scanner,lp,plugdev,users live
"$IN" "$ROOT" /usr/bin/passwd -d live
"$IN" "$ROOT" /usr/bin/passwd -l root
echo 'live ALL=(ALL:ALL) NOPASSWD: ALL' > "$ROOT/etc/sudoers.d/live"; chmod 440 "$ROOT/etc/sudoers.d/live"
SESSION=$(sed -n 's/^session=//p' "$HERE/editions/$EDITION/edition" 2>/dev/null || echo "$EDITION")
printf '# the live session only (the installer removes this file)\n[Seat:*]\nautologin-user=live\nautologin-session=%s\n' "$SESSION" \
    > "$ROOT/etc/lightdm/lightdm.conf.d/90-live.conf"
"$IN" "$ROOT" /usr/bin/xdg-user-dirs-update 2>/dev/null || true
rm -f "$ROOT/etc/machine-id" "$ROOT/var/lib/dbus/machine-id"
rm -rf "$ROOT/var/cache/xbps"/*

echo "=== [4/5] KERNEL AND INITRAMFS"
KVER=$(ls "$ROOT/usr/lib/modules" | sort -V | tail -n1)
BUILD_ID="$VERSION-$EDITION-$(date +%s)"
cp "$ROOT/boot/vmlinuz-$KVER" "$ISO_DIR/live/vmlinuz"
"$HERE/tools/initrd/build-initrd.sh" "$ROOT" "$KVER" "$ISO_DIR/live/initrd.img" "$BUILD_ID"
echo "$BUILD_ID" > "$ISO_DIR/live/build-id"
# installed systems boot with the same initramfs (root=UUID=...)
cp "$ISO_DIR/live/initrd.img" "$ROOT/boot/initramfs-$KVER.img"

echo "=== [5/5] SQUASHFS AND ISO"
mksquashfs "$ROOT" "$ISO_DIR/live/rootfs.squashfs" -comp zstd -Xcompression-level 15 -b 1M -noappend -no-xattrs -quiet
mkdir -p "$ISO_DIR/boot/grub"
TITLE="Chamesle Linux $VERSION$SUFFIX ($EDITION_NAME)"
cat > "$ISO_DIR/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=5
insmod all_video
if [ ! -f /live/vmlinuz ]; then search --no-floppy --set=root --file /live/vmlinuz; fi

menuentry "Try or install $TITLE" {
    linux /live/vmlinuz quiet loglevel=3
    initrd /live/initrd.img
}
menuentry "$TITLE (safe graphics)" {
    linux /live/vmlinuz quiet loglevel=3 nomodeset
    initrd /live/initrd.img
}
menuentry "$TITLE (copy to RAM)" {
    linux /live/vmlinuz chamesle.toram=1 quiet loglevel=3
    initrd /live/initrd.img
}
menuentry "$TITLE (show boot messages)" {
    linux /live/vmlinuz loglevel=4 console=tty0 console=ttyS0,115200
    initrd /live/initrd.img
}
EOF
"$GRUB_MKRESCUE" -o "$ISO" "$ISO_DIR" -volid CHAMESLE
(cd "$OUT" && sha256sum "$(basename "$ISO")" > "$(basename "$ISO").sha256")
ls -lh "$ISO"
echo "SUCCESS: $ISO"
