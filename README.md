# Chamesle Linux

A user-friendly Linux distribution with **dinit** as the init system and **apk** as the package manager.

- **For everyone:** a ready desktop, Flatpak with Flathub set up, and (coming) the Chamesle Store for apps,
  drivers and updates.
- **For advanced users:** `get`, a source-based package manager, on top.
- **Editions:** Xfce (made to feel like Windows), with MATE, Cinnamon, GNOME and KDE Plasma to follow.

Every edition comes with linux-firmware, the open graphics drivers, os-prober for dual boot, and Firefox.

## Building an ISO

On any Linux host with xbps, squashfs-tools, xorriso, GRUB (i386-pc and x86_64-efi), zstd, cpio and kmod:

```sh
sudo EDITION=xfce ./build.sh
```

The ISO lands in `out/`. Packages are cached in `~/.cache/chamesle-xbps`, so later builds are quick.

## Layout

| path | what |
| --- | --- |
| `build.sh` | builds an edition's ISO |
| `editions/base.packages` | packages every edition has |
| `editions/NAME/` | an edition: its packages, name and look (`overlay/`) |
| `overlay/` | files shared by every edition: dinit services, Flathub, branding, artwork |
| `tools/initrd/` | the initramfs (live medium and installed systems) |
| `tools/themes.sh` | installs the Fluent theme and icons |
| `artwork/` | wallpaper and logo sources (`render.sh` renders them) |
| `keys/apk/` | the public key the packages are signed with |
