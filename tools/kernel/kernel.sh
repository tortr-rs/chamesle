#!/bin/bash
# our kernel is cachyos's linux-cachyos-lts, repacked as apks: chamesle-kernel-cachyos and chamesle-kernel-cachyos-headers
#   tools/kernel/kernel.sh            the newest linux-cachyos-lts cachyos has
# why cachyos's: tuned for desktops (full preemption, 1000 Hz, sched_ext), built for any x86-64 cpu, and on a crash
# a blue screen with a qr code that phone cameras open as a readable report. the same lts series void ships, so
# out-of-tree drivers (nvidia, broadcom-wl through dkms) build the same way. a kernel doesn't care about the libc
# the packages call void's kernel hooks like void's kernel does: initramfs (dracut), dkms and the boot menu.
# void's own kernel stays installed below it in the boot menu, for when this one doesn't start
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/../..
APK=${APK:-apk}
REPO=${REPO:-$TOP/work/repo}
CACHE=${CACHE:-$TOP/work/kernel}
KEY=$(ls "$HOME"/.config/chamesle/chamesle-*.rsa | sort | tail -n1)
MIRROR=${MIRROR:-https://mirror.cachyos.org/repo/x86_64/cachyos}
# the cachyos packaging key, as their cachyos-keyring lists it trusted
FPR=882DCFE48E2051D48E2562ABF3B607488DB35A47
ARCH=x86_64
mkdir -p "$CACHE" "$REPO/$ARCH"

# a big file in 6 pieces at once: one connection is slow on a phone hotspot
fetch() {
    local url=$1 out=$2 n size step i s e
    [ -f "$out" ] && return
    size=$(curl -sIL "$url" | tr -d '\r' | awk 'tolower($1)=="content-length:"{n=$2} END{print n}')
    [ -n "$size" ] || { echo "kernel: can't reach $url" >&2; exit 1; }
    n=6 step=$(( (size + 5) / 6 ))
    for i in $(seq 0 $((n - 1))); do
        s=$((i * step)) e=$((i * step + step - 1)); [ $e -lt $size ] || e=$((size - 1))
        ( for try in 1 2 3 4 5 6 7 8; do
            curl -fsSL --range $s-$e -o "$out.$i" "$url" && [ "$(stat -c%s "$out.$i")" = $((e - s + 1)) ] && break
            sleep 3
          done ) &
    done
    wait
    for i in $(seq 0 $((n - 1))); do cat "$out.$i"; done > "$out.new"
    rm -f "$out".[0-9]
    [ "$(stat -c%s "$out.new")" = "$size" ] || { echo "kernel: $url came down broken" >&2; exit 1; }
    mv "$out.new" "$out"
}

verify() {
    local f=$1 g
    g=$(mktemp -d)
    GNUPGHOME=$g gpg -q --keyserver hkps://keyserver.ubuntu.com --recv-keys $FPR 2>/dev/null
    GNUPGHOME=$g gpg --status-fd 1 --verify "$f.sig" "$f" 2>/dev/null | grep -q "^\[GNUPG:\] VALIDSIG $FPR " ||
        { rm -rf "$g"; echo "kernel: $f isn't signed by cachyos" >&2; exit 1; }
    rm -rf "$g"
    echo "$(basename "$f"): signed by cachyos"
}

curl -fsSL -o "$CACHE/cachyos.db" "$MIRROR/cachyos.db"
DB=$CACHE/db; rm -rf "$DB"; mkdir -p "$DB"; bsdtar -xf "$CACHE/cachyos.db" -C "$DB"
for p in linux-cachyos-lts linux-cachyos-lts-headers; do
    d=$(ls -d "$DB/$p"-[0-9]* | sort -V | tail -n1)
    file=$(sed -n '/^%FILENAME%$/{n;p}' "$d/desc")
    fetch "$MIRROR/$file" "$CACHE/$file"
    [ -f "$CACHE/$file.sig" ] || curl -fsSL -o "$CACHE/$file.sig" "$MIRROR/$file.sig"
    verify "$CACHE/$file"
    eval "${p//-/_}=\$CACHE/\$file"
done

W=$TOP/work/kernel/build
rm -rf "$W"; mkdir -p "$W/k" "$W/h" "$W/e" "$W/scripts"
bsdtar -xf "$linux_cachyos_lts" -C "$W/k"
bsdtar -xf "$linux_cachyos_lts_headers" -C "$W/h"
KV=$(ls "$W/k/usr/lib/modules")                               # 6.18.50-1-cachyos-lts
ver=$(echo "$KV" | sed 's/-\([0-9]*\)-cachyos-lts$/-r\1/')     # 6.18.50-r1
rm -f "$W"/k/.[A-Z]* "$W"/h/.[A-Z]*
# where void's kernels are and the hooks look: /boot/vmlinuz-VERSION, the config next to it
mkdir -p "$W/k/boot"
mv "$W/k/usr/lib/modules/$KV/vmlinuz" "$W/k/boot/vmlinuz-$KV"
cp "$W/h/usr/lib/modules/$KV/build/.config" "$W/k/boot/config-$KV"
rm -f "$W/k/usr/lib/modules/$KV/pkgbase" "$W/h/usr/lib/modules/$KV/build/../pkgbase"
rm -rf "$W/h/usr/src" "$W/h/usr/share/doc"
# modules.dep and friends in the package: an image built without running scripts can still load modules
depmod -b "$W/k/usr" "$KV" 2>/dev/null || depmod -b "$W/k" "$KV"

hooks() {  # hooks TARGET [VERSION]: what void's kernel package runs, for this kernel
    echo "( cd / && kernel_hooks_version=${2:-$KV} /usr/libexec/xbps-triggers/kernel-hooks run $1 chamesle-kernel ${2:-$KV} no )"
}
# boot line and boot menu, before the hooks write the menu: the crash screen is the qr code, and this kernel
# is the first entry even when void's kernel has a higher version
grubsettings() {
    cat <<P
g=/etc/default/grub
if [ -f \$g ]; then
    sed -i 's/drm\.panic_screen=kmsg/drm.panic_screen=qr_code/' \$g
    grep -q 'drm.panic_screen=' \$g || sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\)"/\1 drm.panic_screen=qr_code"/' \$g
    sed -i '/^GRUB_TOP_LEVEL=/d' \$g
    echo 'GRUB_TOP_LEVEL=/boot/vmlinuz-$KV' >> \$g
fi
P
}
# a removed version leaves modules (dkms, depmod's files) and its initramfs behind, without its vmlinuz:
# those go, and its menu entry with them
cleanup() {
    cat <<'P'
for f in /usr/lib/modules/*-lts /boot/initramfs-*-lts.img; do
    [ -e "$f" ] || continue
    v=${f##*/}; v=${v#initramfs-}; v=${v%.img}
    [ -e "/boot/vmlinuz-$v" ] && continue
    rm -rf "/usr/lib/modules/$v" "/boot/initramfs-$v.img"
    ( cd / && kernel_hooks_version=$v /usr/libexec/xbps-triggers/kernel-hooks run post-remove chamesle-kernel $v no )
done
P
}
cat > "$W/scripts/post-install" <<EOF
#!/bin/sh
$(grubsettings)
depmod -a $KV
$(hooks post-install)
exit 0
EOF
cat > "$W/scripts/post-upgrade" <<EOF
#!/bin/sh
$(grubsettings)
depmod -a $KV
$(hooks post-install)
$(cleanup)
exit 0
EOF
cat > "$W/scripts/pre-deinstall" <<EOF
#!/bin/sh
sed -i '/^GRUB_TOP_LEVEL=/d' /etc/default/grub 2>/dev/null
$(hooks pre-remove)
exit 0
EOF
cat > "$W/scripts/post-deinstall" <<EOF
#!/bin/sh
rm -f /boot/initramfs-$KV.img
$(hooks post-remove)
exit 0
EOF
# chamesle-kernel was arch's linux-lts up to 0.5: now empty, it brings the cachyos one and clears arch's away
cat > "$W/scripts/moved" <<EOF
#!/bin/sh
$(cleanup)
exit 0
EOF

pack() {  # pack NAME VERSION DIR DESC DEPENDS SCRIPTS...
    local name=$1 v=$2 dir=$3 desc=$4 deps=$5 info s; shift 5
    info=(--info "name:$name" --info "version:$v" --info "arch:$ARCH" --info "description:$desc"
          --info "url:https://chamesle.org" --info "license:GPL-2.0-only"
          --info "maintainer:Chamesle Linux <packages@chamesle.org>" --info "depends:$deps")
    for s in "$@"; do info+=(--script "${s%%=*}:$W/scripts/${s#*=}"); done
    unshare --map-root-user --map-auto "$APK" mkpkg --files "$dir" --output "$REPO/$ARCH/$name-$v.apk" \
        --sign-key "$KEY" "${info[@]}"
    echo "built $REPO/$ARCH/$name-$v.apk"
}
chmod 755 "$W"/scripts/*
# headers first in the depends: dkms builds drivers in the kernel's post-install, against them
pack chamesle-kernel-cachyos-headers $ver "$W/h" "Headers to build drivers for the Chamesle kernel" "pahole make"
pack chamesle-kernel-cachyos $ver "$W/k" "The Chamesle kernel: CachyOS's Linux $KV, with a blue screen and a qr code on a crash" \
    "chamesle-kernel-cachyos-headers=$ver kmod dracut linux-firmware" \
    post-install=post-install post-upgrade=post-upgrade pre-deinstall=pre-deinstall post-deinstall=post-deinstall
# above arch's last one, 6.18.58-r1, so upgrades take it
pack chamesle-kernel-headers 6.18.58-r2 "$W/e" "Moved to chamesle-kernel-cachyos-headers" "chamesle-kernel-cachyos-headers"
pack chamesle-kernel 6.18.58-r2 "$W/e" "Moved to chamesle-kernel-cachyos" "chamesle-kernel-cachyos" post-upgrade=moved
