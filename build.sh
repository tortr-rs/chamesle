#!/bin/bash
# builds the iso for one edition
#   sudo EDITION=xfce ./build.sh   -> out/chamesle-VERSION-EDITION-x86_64.iso
# REPO= a dir or url with x86_64/Packages.adb (default work/repo, else the public one), WORK= OUT=
# needs apk-tools 3, mksquashfs, xorriso, grub-mkrescue (bios + efi), readelf, zstd, cpio, depmod, curl
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
EDITION=${EDITION:-xfce}
[ -f "$HERE/editions/$EDITION/packages" ] || { echo "build: no edition '$EDITION' (editions/*/packages)" >&2; exit 1; }
VERSION=$(cat "$HERE/VERSION"); CODENAME=$(cat "$HERE/CODENAME" 2>/dev/null || true)
# a flavor (astro) is an edition on top of another one: base=gnome brings that edition's packages, overlay, session and
# login, the flavor adds its own
BASE=$(sed -n 's/^base=//p' "$HERE/editions/$EDITION/edition" 2>/dev/null)
EDS="$BASE $EDITION"
# edval KEY: from the edition file, else from its base's
edval() { local e v; for e in $EDITION $BASE; do v=$(sed -n "s/^$1=//p" "$HERE/editions/$e/edition" 2>/dev/null); [ -n "$v" ] && { echo "$v"; return; }; done; return 0; }
EDITION_NAME=$(sed -n 's/^name=//p' "$HERE/editions/$EDITION/edition" 2>/dev/null); EDITION_NAME=${EDITION_NAME:-$EDITION}
WORK=${WORK:-$HERE/work/$EDITION}; ROOT=$WORK/root; ISO_DIR=$WORK/iso
OUT=${OUT:-$HERE/out}; ISO=$OUT/chamesle-$VERSION-$EDITION-x86_64.iso
PUBLIC_REPO=https://downloads.sourceforge.net/project/chameslerepos
REPO=${REPO:-$( [ -f "$HERE/work/repo/x86_64/Packages.adb" ] && echo "$HERE/work/repo" || echo "$PUBLIC_REPO")}
APK=${APK:-apk}
IN=$HERE/tools/in-image.sh

missing=
for t in "$APK" mksquashfs xorriso readelf zstd cpio depmod curl; do command -v "$t" >/dev/null || missing="$missing $t"; done
command -v grub-mkrescue >/dev/null || command -v grub2-mkrescue >/dev/null || missing="$missing grub-mkrescue"
[ -z "$missing" ] || { echo "build: missing tools:$missing" >&2; exit 1; }
GRUB_MKRESCUE=$(command -v grub-mkrescue || command -v grub2-mkrescue)
packages() { sed 's/#.*//' "$HERE/editions/base.packages" $(for e in $EDS; do echo "$HERE/editions/$e/packages"; done) | tr ' \t' '\n\n' | grep -v '^$' | sort -u; }

echo "=== [1/5] INSTALLING THE SYSTEM ($EDITION_NAME, from $REPO)"
rm -rf "$WORK"; mkdir -p "$ROOT/etc/apk/keys" "$ISO_DIR/live" "$OUT"
cp "$HERE"/keys/apk/*.pub "$ROOT/etc/apk/keys/"
echo "v3 $REPO" > "$ROOT/etc/apk/repositories"
# install scripts need /dev and /proc
mkdir -p "$ROOT/dev" "$ROOT/proc"
mount --rbind /dev "$ROOT/dev"; mount --make-rslave "$ROOT/dev"; mount -t proc proc "$ROOT/proc"
trap 'umount "$ROOT/proc" 2>/dev/null; umount -lR "$ROOT/dev" 2>/dev/null; true' EXIT
pkg() { "$APK" --root "$ROOT" --arch x86_64 --no-cache --no-interactive "$@"; }
# scripts need sh and coreutils, so those go first without scripts
pkg add --initdb --no-scripts base-files bash coreutils sed grep findutils
pkg fix --reinstall $(pkg info --quiet)
# no runit, ever
pkg add '!runit' '!runit-void' $(packages)
# apk runs a package's script right after unpacking it, so many ran before what they need (useradd, icon and
# font caches...) was there. now everything is: run them all again
mkdir -p "$ROOT/tmp/scripts"
tar -xzf "$ROOT/lib/apk/db/scripts.tar.gz" -C "$ROOT/tmp/scripts"
chroot "$ROOT" /bin/sh -c 'cd / && for s in /tmp/scripts/*.post-install; do sh "$s" >/dev/null; done'
rm -rf "$ROOT/tmp/scripts"
umount "$ROOT/proc" 2>/dev/null || true; umount -lR "$ROOT/dev" 2>/dev/null || true; trap - EXIT
# what the installed system updates from
echo "v3 $PUBLIC_REPO" > "$ROOT/etc/apk/repositories"

echo "=== [2/5] CHAMESLE: SERVICES, LOOK AND BRANDING"
cp -a "$HERE/overlay/." "$ROOT/"
for e in $EDS; do [ -d "$HERE/editions/$e/overlay" ] && cp -a "$HERE/editions/$e/overlay/." "$ROOT/"; done
"$HERE/tools/themes.sh" "$ROOT"
# the installer's slideshow starts with this edition's desktop (the website's picture of it) and how to get around
SLIDES=$ROOT/usr/share/live-installer/slideshow
SHOT=; for e in $EDITION $BASE; do [ -z "$SHOT" ] && [ -f "$HERE/docs/img/$e.png" ] && SHOT=$HERE/docs/img/$e.png; done
if [ -n "$SHOT" ]; then cp "$SHOT" "$SLIDES/desktop.png"; else rm -f "$SLIDES/desktop.png"; fi
TOUR=$(edval tour)
if [ -n "$TOUR" ]; then
    sed -i "s|<p id=\"tour\">[^<]*</p>|<p id=\"tour\">${TOUR//&/\\&}</p>|" "$SLIDES/index.html"
fi
# xfce's stock wallpapers -> ours, for monitors xfce4-desktop.xml doesn't name
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
grep -qx 'en_US.UTF-8 UTF-8' "$ROOT/etc/default/libc-locales" 2>/dev/null || echo 'en_US.UTF-8 UTF-8' >> "$ROOT/etc/default/libc-locales"
echo 'LANG=en_US.UTF-8' > "$ROOT/etc/locale.conf"
ln -sf /usr/share/zoneinfo/UTC "$ROOT/etc/localtime"
"$IN" "$ROOT" /usr/bin/locale-gen
"$IN" "$ROOT" /usr/bin/fc-cache -f
"$IN" "$ROOT" /usr/bin/gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true

echo "=== [3/5] THE LIVE USER"
# live user: no password, autologin, sudo. the installer removes all that
"$IN" "$ROOT" /usr/bin/useradd -m -c "Live session" -s /bin/bash -G wheel,audio,video,input,network,storage,optical,scanner,lp,plugdev,users live
"$IN" "$ROOT" /usr/bin/passwd -d live
"$IN" "$ROOT" /usr/bin/passwd -l root
echo 'live ALL=(ALL:ALL) NOPASSWD: ALL' > "$ROOT/etc/sudoers.d/live"; chmod 440 "$ROOT/etc/sudoers.d/live"
# same for the password prompts of the store, drivers and updates: live has no password to type
mkdir -p "$ROOT/etc/polkit-1/rules.d"
printf 'polkit.addRule(function(action, subject) {\n    if (subject.user == "live") return polkit.Result.YES;\n});\n' > "$ROOT/etc/polkit-1/rules.d/49-live.rules"
SESSION=$(edval session); SESSION=${SESSION:-${BASE:-$EDITION}}
LOGIN=$(edval login); LOGIN=${LOGIN:-sddm}
# what an installed system starts: the live one, unless the edition says otherwise (gnome and kde: x11 live, where
# the installer is at home, wayland once installed). the installer reads it for autologin
INSTALLED=$(edval installed-session); INSTALLED=${INSTALLED:-$SESSION}
mkdir -p "$ROOT/etc/chamesle"; echo "$INSTALLED" > "$ROOT/etc/chamesle/session"; echo "$LOGIN" > "$ROOT/etc/chamesle/login"
if [ "$LOGIN" = sddm ]; then
    mkdir -p "$ROOT/etc/sddm.conf.d"
    printf '# the live session only (the installer removes this file)\n[Autologin]\nUser=live\nSession=%s.desktop\n' "$SESSION" \
        > "$ROOT/etc/sddm.conf.d/90-live.conf"
elif [ "$LOGIN" = gdm ]; then
    # gdm has a single config file, the installer takes these lines out again. the session comes from accountsservice
    sed -i 's/^\[daemon\]$/&\n# the live session only\nAutomaticLoginEnable=True\nAutomaticLogin=live/' "$ROOT/etc/gdm/custom.conf"
    mkdir -p "$ROOT/var/lib/AccountsService/users"
    printf '[User]\nSession=%s\nSystemAccount=false\n' "$SESSION" > "$ROOT/var/lib/AccountsService/users/live"
else
    printf '# the live session only (the installer removes this file)\n[Seat:*]\nautologin-user=live\nautologin-session=%s\n' "$SESSION" \
        > "$ROOT/etc/lightdm/lightdm.conf.d/90-live.conf"
fi
"$IN" "$ROOT" /usr/bin/xdg-user-dirs-update 2>/dev/null || true
# installer icon on the desktop, marked trusted at login or xfce and caja ask first
mkdir -p "$ROOT/home/live/Desktop" "$ROOT/home/live/.config/autostart"
install -m755 "$ROOT/usr/share/applications/chamesle-install.desktop" "$ROOT/home/live/Desktop/"
cat > "$ROOT/home/live/.config/autostart/trust-installer.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Trust the installer icon
Exec=sh -c 'f=$HOME/Desktop/chamesle-install.desktop; gio set "$f" metadata::xfce-exe-checksum "$(sha256sum "$f" | cut -d" " -f1)"; gio set "$f" metadata::trusted true'
NoDisplay=true
EOF
# gnome has no desktop icons: the installer goes first in the dock instead
# the dock of a flavor wins over gnome's: its override sorts last
GNOME_LOOK=$(grep -l '^favorite-apps=' "$ROOT"/usr/share/glib-2.0/schemas/*_chamesle-*.gschema.override 2>/dev/null | sort | tail -n1 || true)
if [ -n "$GNOME_LOOK" ]; then
    mkdir -p "$ROOT/home/live/.config/dconf" "$ROOT/tmp/live-dconf"
    { echo '[org/gnome/shell]'; sed -n "s/^favorite-apps=\[/&'chamesle-install.desktop', /p" "$GNOME_LOOK"; } > "$ROOT/tmp/live-dconf/live"
    "$IN" "$ROOT" /usr/bin/dconf compile /home/live/.config/dconf/user /tmp/live-dconf
    rm -rf "$ROOT/tmp/live-dconf"
fi
"$IN" "$ROOT" /usr/bin/chown -R live:live /home/live
rm -f "$ROOT/etc/machine-id" "$ROOT/var/lib/dbus/machine-id"
rm -rf "$ROOT/var/cache/apk"/*

echo "=== [4/5] KERNEL AND INITRAMFS"
KVER=$(ls "$ROOT/usr/lib/modules" | sort -V | tail -n1)
BUILD_ID="$VERSION-$EDITION-$(date +%s)"
cp "$ROOT/boot/vmlinuz-$KVER" "$ISO_DIR/live/vmlinuz"
"$HERE/tools/initrd/build-initrd.sh" "$ROOT" "$KVER" "$ISO_DIR/live/initrd.img" "$BUILD_ID"
echo "$BUILD_ID" > "$ISO_DIR/live/build-id"
cp "$ISO_DIR/live/initrd.img" "$ROOT/boot/initramfs-$KVER.img"

echo "=== [5/5] SQUASHFS AND ISO"
mksquashfs "$ROOT" "$ISO_DIR/live/rootfs.squashfs" -comp zstd -Xcompression-level 15 -b 1M -noappend -no-xattrs -quiet
mkdir -p "$ISO_DIR/boot/grub"
# the same boot menu theme an installed system gets
THEME=$ROOT/usr/share/grub/themes/chamesle
[ -d "$THEME" ] && mkdir -p "$ISO_DIR/boot/grub/themes" && cp -r "$THEME" "$ISO_DIR/boot/grub/themes/"
cat > "$ISO_DIR/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=5
insmod all_video
insmod gfxterm
set gfxmode=1280x800,1024x768,auto
set gfxpayload=keep
terminal_output gfxterm
if [ -f \$prefix/themes/chamesle/theme.txt ]; then
    insmod png
    loadfont \$prefix/fonts/unicode.pf2
    loadfont \$prefix/themes/chamesle/inter-16.pf2
    loadfont \$prefix/themes/chamesle/inter-20.pf2
    loadfont \$prefix/themes/chamesle/inter-bold-32.pf2
    set theme=\$prefix/themes/chamesle/theme.txt
fi
if [ ! -f /live/vmlinuz ]; then search --no-floppy --set=root --file /live/vmlinuz; fi

# two choices, like a Windows USB: try it, or install it. Install starts Jiggity alone on the screen, with no desktop
menuentry "Try Chamesle" {
    linux /live/vmlinuz quiet splash loglevel=3 drm.panic_screen=kmsg
    initrd /live/initrd.img
}
menuentry "Install Chamesle" {
    linux /live/vmlinuz chamesle.install=1 quiet splash loglevel=3 drm.panic_screen=kmsg
    initrd /live/initrd.img
}
submenu "More options" {
    menuentry "Try Chamesle (safe graphics)" {
        linux /live/vmlinuz quiet loglevel=3 nomodeset drm.panic_screen=kmsg
        initrd /live/initrd.img
    }
    menuentry "Install Chamesle (safe graphics)" {
        linux /live/vmlinuz chamesle.install=1 quiet loglevel=3 nomodeset drm.panic_screen=kmsg
        initrd /live/initrd.img
    }
    menuentry "Try Chamesle (copy to RAM)" {
        linux /live/vmlinuz chamesle.toram=1 quiet splash loglevel=3 drm.panic_screen=kmsg
        initrd /live/initrd.img
    }
    menuentry "Try Chamesle (show boot messages)" {
        linux /live/vmlinuz loglevel=4 console=tty0 console=ttyS0,115200 drm.panic_screen=kmsg
        initrd /live/initrd.img
    }
}
EOF
"$GRUB_MKRESCUE" -o "$ISO" "$ISO_DIR" -volid CHAMESLE
(cd "$OUT" && sha256sum "$(basename "$ISO")" > "$(basename "$ISO").sha256")
ls -lh "$ISO"
echo "SUCCESS: $ISO"
