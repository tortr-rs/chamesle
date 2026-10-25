#!/bin/bash
# our kernel is arch's linux-lts, repacked as apks: chamesle-kernel and chamesle-kernel-headers
#   tools/kernel/arch-kernel.sh            the newest linux-lts arch has
# why arch's: it shows a blue screen with the log when the kernel crashes (CONFIG_DRM_PANIC, white on 0x0000aa),
# void's kernel has that switched off. it's the same lts series void ships, so out-of-tree drivers (nvidia,
# broadcom-wl through dkms) build the same way. a kernel doesn't care about the libc, nothing gets compiled
# the packages call void's kernel hooks like void's kernel does: initramfs (dracut), dkms and the boot menu
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/../..
APK=${APK:-apk}
REPO=${REPO:-$TOP/work/repo}
CACHE=${CACHE:-$TOP/work/kernel}
KEY=$(ls "$HOME"/.config/chamesle/chamesle-*.rsa | sort | tail -n1)
MIRROR=${MIRROR:-https://geo.mirror.pkgbuild.com/core/os/x86_64}
ARCH=x86_64
mkdir -p "$CACHE" "$REPO/$ARCH"

# a big file in 6 pieces at once: one connection is slow on a phone hotspot
fetch() {
    local url=$1 out=$2 n size step i s e
    [ -f "$out" ] && return
    size=$(curl -sIL "$url" | tr -d '\r' | awk 'tolower($1)=="content-length:"{n=$2} END{print n}')
    [ -n "$size" ] || { echo "arch-kernel: can't reach $url" >&2; exit 1; }
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
    [ "$(stat -c%s "$out.new")" = "$size" ] || { echo "arch-kernel: $url came down broken" >&2; exit 1; }
    mv "$out.new" "$out"
}

# signed by an arch packager: the key has to be the one archlinux.org publishes for that address
verify() {
    local f=$1 g fpr email
    g=$(mktemp -d)
    fpr=$(GNUPGHOME=$g gpg --list-packets "$f.sig" 2>/dev/null | sed -n 's/.*issuer fpr v4 \([0-9A-F]*\).*/\1/p' | head -n1)
    GNUPGHOME=$g gpg -q --keyserver hkps://keyserver.ubuntu.com --recv-keys "$fpr" 2>/dev/null
    email=$(GNUPGHOME=$g gpg --with-colons --list-keys "$fpr" | awk -F: '$1=="uid"{print $10}' |
        grep -o '[^<]*@archlinux\.org' | head -n1)
    [ -n "$email" ] || { echo "arch-kernel: $f isn't signed by an arch packager" >&2; exit 1; }
    rm -rf "$g"; g=$(mktemp -d)
    GNUPGHOME=$g gpg -q --auto-key-locate clear,wkd --locate-keys "$email" >/dev/null 2>&1
    GNUPGHOME=$g gpg --with-colons --list-keys "$email" 2>/dev/null | grep -q "^fpr:*$fpr:" ||
        { echo "arch-kernel: archlinux.org doesn't list $fpr for $email" >&2; exit 1; }
    GNUPGHOME=$g gpg -q --verify "$f.sig" "$f" 2>/dev/null || { echo "arch-kernel: bad signature on $f" >&2; exit 1; }
    rm -rf "$g"
    echo "$(basename "$f"): signed by $email"
}

for p in linux-lts linux-lts-headers; do
    file=$(curl -fsSL "https://archlinux.org/packages/core/$ARCH/$p/json/" | python3 -c 'import json,sys; print(json.load(sys.stdin)["filename"])')
    fetch "$MIRROR/$file" "$CACHE/$file"
    [ -f "$CACHE/$file.sig" ] || curl -fsSL -o "$CACHE/$file.sig" "$MIRROR/$file.sig"
    verify "$CACHE/$file"
    eval "${p//-/_}=\$CACHE/\$file"
done

W=$TOP/work/kernel/build
rm -rf "$W"; mkdir -p "$W/k" "$W/h" "$W/scripts"
bsdtar -xf "$linux_lts" -C "$W/k"
bsdtar -xf "$linux_lts_headers" -C "$W/h"
KV=$(ls "$W/k/usr/lib/modules")                       # 6.18.58-1-lts
ver=$(echo "$KV" | sed 's/-\([0-9]*\)-lts$/-r\1/')     # 6.18.58-r1
rm -f "$W"/k/.[A-Z]* "$W"/h/.[A-Z]*
# where void's kernels are and the hooks look: /boot/vmlinuz-VERSION, the config next to it
mkdir -p "$W/k/boot"
mv "$W/k/usr/lib/modules/$KV/vmlinuz" "$W/k/boot/vmlinuz-$KV"
cp "$W/h/usr/lib/modules/$KV/build/.config" "$W/k/boot/config-$KV"
rm -f "$W/k/usr/lib/modules/$KV/pkgbase" "$W/h/usr/lib/modules/$KV/build/../pkgbase"
rm -rf "$W/h/usr/src" "$W/h/usr/share/doc"
# modules.dep and friends in the package: an image built without running scripts can still load modules
depmod -b "$W/k/usr" "$KV" 2>/dev/null || depmod -b "$W/k" "$KV"

hooks() {  # hooks TARGET: what void's kernel package runs, for this kernel
    echo "( cd / && kernel_hooks_version=$KV /usr/libexec/xbps-triggers/kernel-hooks run $1 chamesle-kernel $KV no )"
}
# the crash screen shows the log on blue, not arch's qr code to their bug site. on the boot line, so it's set
# before anything can crash: systems installed before this kernel get it added to their grub settings here
panic() {
    cat <<'P'
g=/etc/default/grub
if [ -f $g ] && ! grep -q 'drm.panic_screen=' $g; then
    sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="[^"]*\)"/\1 drm.panic_screen=kmsg"/' $g
fi
P
}
cat > "$W/scripts/post-install" <<EOF
#!/bin/sh
$(panic)
depmod -a $KV
$(hooks post-install)
exit 0
EOF
# an upgrade brings a new kernel version: hooks for it, and the old one's initramfs and menu entry go.
# leftovers of a removed version (dkms modules, depmod's files) are all that's in its modules folder then
cat > "$W/scripts/post-upgrade" <<EOF
#!/bin/sh
$(panic)
depmod -a $KV
$(hooks post-install)
for d in /usr/lib/modules/*-lts; do
    v=\${d##*/}
    [ "\$v" = $KV ] || [ -e "\$d/modules.order" ] && continue
    rm -rf "\$d" /boot/initramfs-\$v.img
    ( cd / && kernel_hooks_version=\$v /usr/libexec/xbps-triggers/kernel-hooks run post-remove chamesle-kernel \$v no )
done
exit 0
EOF
cat > "$W/scripts/pre-deinstall" <<EOF
#!/bin/sh
$(hooks pre-remove)
exit 0
EOF
cat > "$W/scripts/post-deinstall" <<EOF
#!/bin/sh
rm -f /boot/initramfs-$KV.img
$(hooks post-remove)
exit 0
EOF

pack() {  # pack NAME DIR DESC DEPENDS SCRIPTS...
    local name=$1 dir=$2 desc=$3 deps=$4 info s; shift 4
    info=(--info "name:$name" --info "version:$ver" --info "arch:$ARCH" --info "description:$desc"
          --info "url:https://chamesle.org" --info "license:GPL-2.0-only"
          --info "maintainer:Chamesle Linux <packages@chamesle.org>" --info "depends:$deps")
    for s in "$@"; do info+=(--script "$s:$W/scripts/$s"); done
    unshare --map-root-user --map-auto "$APK" mkpkg --files "$dir" --output "$REPO/$ARCH/$name-$ver.apk" \
        --sign-key "$KEY" "${info[@]}"
    echo "built $REPO/$ARCH/$name-$ver.apk"
}
chmod 755 "$W"/scripts/*
# headers first in the depends: dkms builds drivers in the kernel's post-install, against them
pack chamesle-kernel-headers "$W/h" "Headers to build drivers for the Chamesle kernel" "pahole make"
pack chamesle-kernel "$W/k" "The Chamesle kernel: Linux $KV, with a blue screen and the log on a crash" \
    "chamesle-kernel-headers=$ver kmod dracut linux-firmware" post-install post-upgrade pre-deinstall post-deinstall
