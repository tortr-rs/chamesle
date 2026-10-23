# Chamesle Linux

A Linux desktop for people who just want their computer to work. Boot it, it looks like what you're used to,
apps come from Flathub, and there's a real package manager underneath if you want it.

- **pkgimport**: double-click any `.deb` or `.rpm` and it installs, with the libraries it needs
- glibc, **dinit** for init, **apk** for packages
- the Chamesle repo: almost 15,000 packages, all signed
- an installer based on Linux Mint's: whole disk (with encryption or LVM) or your own partitions, GParted built in
- linux-firmware, Mesa, os-prober and Firefox out of the box

Editions: **Xfce**, **MATE** and **Cinnamon**, set up like Windows, and **GNOME**. KDE Plasma later.

Website: [chamesle.org](https://chamesle.org) · downloads and the package repo:
[SourceForge](https://sourceforge.net/projects/chameslerepos/)


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
tools/pkg/build.sh python3-parted   # one of our own packages, built from source
```

Without the whole repo here, `tools/pkg/build.sh` builds against the public one, and
`tools/repo/merge-index.sh work/repo/x86_64/NAME-*.apk` puts the result in the published index;
`tools/repo/upload.sh publish` uploads just that. The packages already on SourceForge stay as they are.

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

## Credits

The installer is Linux Mint's [live-installer](https://github.com/linuxmint/live-installer) (GPL-2.0-or-later,
Clement Lefebvre and the Mint team), changed to install Chamesle.

## Helping out

Try it, break it, [open an issue](https://github.com/tortr-rs/chamesle/issues). Small pull requests are easier
to review than big ones.
