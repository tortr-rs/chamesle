#!/bin/sh
# fluent gtk theme and icons (vinceliuice) into an image
# usage: themes.sh ROOT
set -eu
ROOT=${1:?usage: themes.sh ROOT}
GTK_TAG=2025-04-17
GTK_SHA256=bedc51e07ca4edaeb3bdd50e9e2a27c10f1b049f460b10e3b5668d11ff2b03cd
ICONS_TAG=2026-07-27
ICONS_SHA256=24a8aca29a5b652a0e60ff8e5f12b86fe4b9c4c969565fad7c3fa7c1742b3631
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
fetch() { # REPO TAG SHA256
    curl -fsSL --retry 5 --retry-all-errors -o "$W/$1.tar.gz" "https://github.com/vinceliuice/$1/archive/refs/tags/$2.tar.gz"
    [ "$(sha256sum "$W/$1.tar.gz" | cut -d' ' -f1)" = "$3" ] || { echo "themes: checksum mismatch for $1" >&2; exit 1; }
    tar -xzf "$W/$1.tar.gz" -C "$W"
}
fetch Fluent-gtk-theme "$GTK_TAG" "$GTK_SHA256"
fetch Fluent-icon-theme "$ICONS_TAG" "$ICONS_SHA256"
mkdir -p "$ROOT/usr/share/themes" "$ROOT/usr/share/icons"
(cd "$W/Fluent-gtk-theme-$GTK_TAG" && bash install.sh -d "$ROOT/usr/share/themes" >/dev/null)
(cd "$W/Fluent-icon-theme-$ICONS_TAG" && bash install.sh -d "$ROOT/usr/share/icons" >/dev/null)
echo "themes: Fluent GTK/Xfwm4 themes and Fluent icons installed"
