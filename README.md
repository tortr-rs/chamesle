# Chamesle Linux

A Linux desktop for people who just want their computer to work. Boot it, it looks like what you're used to,
apps come from Flathub, and there's a real package manager underneath if you want it.

- glibc, **dinit** for init, **apk** for packages
- our own repo, almost 15,000 packages, all signed
- `.deb` and `.rpm` files install with a double-click (`pkgimport`)
- Calamares installer: next to Windows, whole disk or manual, optional encryption
- linux-firmware, Mesa, os-prober and Firefox out of the box

Editions: **Xfce** (set up like Windows) now, MATE, Cinnamon, GNOME and KDE Plasma later.

Website: [chamesle.org](https://chamesle.org) · downloads and the package repo:
[SourceForge](https://sourceforge.net/projects/chameslerepos/)

## Status

0.1 is out (live only). 0.2 is being tested: the installer, the switch to apk, and deb/rpm support.
The store, update notifier and driver manager are for 0.3.

## Building an ISO

You need apk-tools 3, squashfs-tools, xorriso, GRUB (i386-pc and x86_64-efi), zstd, cpio and kmod.

```sh
sudo EDITION=xfce ./build.sh
```

The ISO ends up in `out/`. Packages come from `work/repo` if you built the repo yourself, otherwise from the
public one.

## The repo

```sh
ALL=1 tools/repo/build-repo.sh     # the whole repo, takes a while and ~60G
tools/pkg/build.sh calamares       # one of our own packages, built from source
```

Signing needs a key in `~/.config/chamesle/` (made on the first run). Keep it to yourself, only the `.pub`
goes in `keys/apk/`.

## What's where

| path | what |
| --- | --- |
| `build.sh` | builds an edition's ISO |
| `editions/base.packages` | packages every edition has |
| `editions/NAME/` | one edition: packages, name, look |
| `overlay/` | shared files: dinit services, installer config, branding, pkgimport |
| `tools/initrd/` | the live initramfs |
| `tools/repo/` | builds and signs the package repo |
| `tools/pkg/` | recipes for packages we build ourselves |
| `tools/themes.sh` | Fluent theme and icons |
| `artwork/` | wallpaper and logo (`render.sh`) |
| `docs/` | the website |
| `keys/apk/` | public signing key |

## Helping out

Try it, break it, [open an issue](https://github.com/tortr-rs/chamesle/issues). Small pull requests are easier
to review than big ones.
