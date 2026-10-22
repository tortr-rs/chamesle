#!/bin/bash
# build one of our own packages into the repo: tools/pkg/build.sh python3-parted
# a recipe sets name version rel desc url license source sha256 makedeps depends and build(),
# which runs in a clean root and installs into $pkgdir
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/../..
APK=${APK:-apk}
REPO=${REPO:-$TOP/work/repo}
SRC=${SRC_CACHE:-$HOME/.cache/chamesle-src}
KEYDIR=${KEYDIR:-$HOME/.config/chamesle}
KEY=$(ls "$KEYDIR"/chamesle-*.rsa | head -n1)
ARCH=x86_64

[ $# = 1 ] && [ -f "$HERE/$1/recipe" ] || { echo "usage: $0 NAME   (one of: $(cd "$HERE" && ls */recipe | sed 's|/recipe||' | tr '\n' ' '))" >&2; exit 1; }
. "$HERE/$1/recipe"

# no source means the package is made of files that live here, in NAME/files
if [ -n "${source:-}" ]; then
    mkdir -p "$SRC"
    file=$SRC/${source##*/}
    [ -f "$file" ] || curl -fL -o "$file" "$source"
    echo "$sha256  $file" | sha256sum -c --quiet
fi

W=$TOP/work/pkg/$name
unshare --map-root-user --map-auto rm -rf "$W"
ROOT=$W/root
mkdir -p "$ROOT/etc/apk/keys" "$ROOT/build/src" "$ROOT/build/pkg"
cp "$TOP"/keys/apk/*.pub "$ROOT/etc/apk/keys/"
echo "v3 $REPO" > "$ROOT/etc/apk/repositories"
if [ -n "${source:-}" ]; then
    tar -xf "$file" -C "$ROOT/build/src"
else
    cp -r "$HERE/$1/files" "$ROOT/build/src/files"
fi
cp "$HERE/$1/recipe" "$ROOT/build/"
[ -d "$HERE/$1/patches" ] && cp -r "$HERE/$1/patches" "$ROOT/build/"

unshare --map-root-user --map-auto --mount --pid --fork bash -euo pipefail -c '
APK=$1 ROOT=$2 IN=$3 makedeps=$4
"$APK" --root "$ROOT" --arch x86_64 add --initdb --no-cache --quiet --no-scripts base-files bash coreutils sed grep findutils
"$APK" --root "$ROOT" --arch x86_64 fix --no-cache --quiet --reinstall $("$APK" --root "$ROOT" info --quiet)
[ -z "$makedeps" ] || "$APK" --root "$ROOT" --arch x86_64 add --no-cache --quiet $makedeps
cat > "$ROOT/build/run" <<"EOF"
set -euo pipefail
. /build/recipe
pkgdir=/build/pkg
cd /build/src/*/
for p in /build/patches/*.patch; do [ -e "$p" ] && patch -p1 < "$p"; done
export MAKEFLAGS=-j$(nproc) CFLAGS="-O2 -pipe" CXXFLAGS="-O2 -pipe"
build
EOF
"$IN" "$ROOT" /bin/bash /build/run
' - "$APK" "$ROOT" "$TOP/tools/in-image.sh" "$makedeps"

# shared libraries it links to, minus the ones it brings itself
PKG=$ROOT/build/pkg
own=$(find "$PKG" -type f -name '*.so*' -exec basename {} \; | sort -u)
sodeps=$(find "$PKG" -type f \( -perm -u+x -o -name '*.so*' \) -exec readelf -d {} + 2>/dev/null |
    sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | sort -u | grep -vxF "$own" | sed 's/^/so:/' | tr '\n' ' ' || true)
provides=$(for f in $own; do case $f in *.so.[0-9]*) echo "so:$f=${f#*.so.}" | sed 's/=\([0-9]*\).*/=\1/';; esac; done | tr '\n' ' ')

out=$REPO/$ARCH/$name-$version-r$rel.apk
info=(--info "name:$name" --info "version:$version-r$rel" --info "arch:$ARCH" --info "description:$desc"
      --info "url:$url" --info "license:$license" --info "maintainer:Chamesle Linux <packages@chamesle.org>")
d=$(echo $depends $sodeps)
[ -z "$d" ] || info+=(--info "depends:$d")
[ -z "${provides// }" ] || info+=(--info "provides:$(echo $provides)")
[ -z "${replaces:-}" ] || info+=(--info "replaces:$replaces")
# install scripts, if the package has any (NAME/post-install and so on); @VERSION@ becomes the package's version
for k in pre-install post-install pre-upgrade post-upgrade pre-deinstall post-deinstall; do
    [ -f "$HERE/$1/$k" ] || continue
    sed "s/@VERSION@/$version/g" "$HERE/$1/$k" > "$W/$k"
    info+=(--script "$k:$W/$k")
done
# packed as namespace root so the files are root's
unshare --map-root-user --map-auto "$APK" mkpkg --files "$PKG" --output "$out" --sign-key "$KEY" "${info[@]}"
"$APK" mkndx --keys-dir "$TOP/keys/apk" --sign-key "$KEY" --description "chamesle $(date +%Y-%m-%d)" \
    --index "$REPO/$ARCH/Packages.adb" --output "$REPO/$ARCH/Packages.adb.new" "$REPO/$ARCH"/*.apk
mv "$REPO/$ARCH/Packages.adb.new" "$REPO/$ARCH/Packages.adb"
echo "built $out"
