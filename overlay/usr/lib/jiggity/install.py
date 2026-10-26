# progress(step, percent): 0 partition, 1 copy, 2 configure, 3 bootloader, 4 cleanup
import glob
import os
import subprocess
import time

import disks
from disks import run

SOURCE = "/run/chamesle/rootfs/"
T = "/target"
# live session only
LIVE_ONLY = ["/etc/sudoers.d/live", "/etc/polkit-1/rules.d/49-live.rules", "/etc/lightdm/lightdm.conf.d/90-live.conf",
             "/etc/sddm.conf.d/90-live.conf", "/usr/share/applications/chamesle-install.desktop", "/usr/bin/chamesle-install",
             "/usr/bin/live-installer", "/usr/lib/live-installer", "/usr/share/live-installer",
             "/usr/share/icons/live-installer-progress-dot-on.png", "/usr/share/icons/live-installer-progress-dot-off.png",
             "/var/lib/AccountsService/users/live", "/usr/bin/jiggity", "/etc/chamesle/autologin"]


def chroot(*cmd, input=None):
    return run("chroot", T, *cmd, input=input)


def uuid(dev):
    return subprocess.run(["blkid", "-s", "UUID", "-o", "value", dev], text=True, stdout=subprocess.PIPE).stdout.strip()


def set_grub(key, value):
    path = T + "/etc/default/grub"
    lines = open(path).read().split("\n") if os.path.exists(path) else []
    line = '%s="%s"' % (key, value)
    for i, l in enumerate(lines):
        if l.lstrip("#").startswith(key + "="):
            lines[i] = line
            break
    else:
        lines.append(line)
    with open(path, "w") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")


def install(row, passphrase, language, keyboard, progress):
    os.makedirs(T, exist_ok=True)
    progress(0, 0)
    plan = disks.make(row, passphrase is not None)
    progress(0, 40)
    root = plan.root
    if passphrase is not None:
        run("cryptsetup", "luksFormat", "--batch-mode", "--type", "luks2", "--key-file=-", plan.root, input=passphrase)
        run("cryptsetup", "open", "--key-file=-", plan.root, "chamesle", input=passphrase)
        root = "/dev/mapper/chamesle"
    if plan.format_efi:
        run("mkfs.fat", "-F", "32", "-n", "EFI", plan.efi)
    if plan.boot:
        run("mkfs.ext4", "-F", "-q", "-L", "boot", plan.boot)
    run("mkfs.btrfs", "-f", "-L", "Chamesle", root)
    run("mount", root, T)
    run("btrfs", "subvolume", "create", T + "/@", T + "/@home")
    run("umount", T)
    run("mount", "-o", "subvol=@,compress=zstd:1", root, T)
    os.makedirs(T + "/home", exist_ok=True)
    run("mount", "-o", "subvol=@home,compress=zstd:1", root, T + "/home")
    if plan.boot:
        os.makedirs(T + "/boot", exist_ok=True)
        run("mount", plan.boot, T + "/boot")
    if plan.efi:
        os.makedirs(T + "/boot/efi", exist_ok=True)
        run("mount", plan.efi, T + "/boot/efi")
    progress(0, 100)

    # progress = files copied / inodes used on the live root
    total = int(subprocess.run(["df", "--output=iused", SOURCE], text=True, stdout=subprocess.PIPE).stdout.split()[-1])
    excludes = []
    for d in "home/* dev/* proc/* sys/* tmp/* run/* mnt/* media/* lost+found".split():
        excludes += ["--exclude=/" + d]
    p = subprocess.Popen(["rsync", "--archive", "--hard-links", "--acls", "--xattrs", "--no-D", "--out-format=%n"]
                         + excludes + [SOURCE, T + "/"], text=True, errors="ignore", stdout=subprocess.PIPE)
    done = 0
    for _ in p.stdout:
        done += 1
        if done % 200 == 0:
            progress(1, min(99, done * 100 // max(total, 1)))
    if p.wait():
        raise RuntimeError("copying the files failed")
    progress(1, 100)

    for d in ("dev", "proc", "sys", "run"):
        os.makedirs(T + "/" + d, exist_ok=True)
        run("mount", "--rbind", "/" + d, T + "/" + d)
        run("mount", "--make-rslave", T + "/" + d)
    for path in LIVE_ONLY:
        run("rm", "-rf", T + path)
    if os.path.exists(T + "/etc/gdm/custom.conf"):
        run("sed", "-i", "/^# the live session only$/d; /^AutomaticLogin/d", T + "/etc/gdm/custom.conf")
    chroot("userdel", "-r", "live")
    chroot("passwd", "-dl", "root")
    open(T + "/etc/chamesle/firstboot", "w").close()
    progress(2, 30)

    with open(T + "/etc/fstab", "w") as f:
        r = uuid(root)
        f.write("# made by Jiggity\nproc /proc proc defaults 0 0\n")
        f.write("UUID=%s / btrfs defaults,subvol=@,compress=zstd:1 0 0\n" % r)
        f.write("UUID=%s /home btrfs defaults,subvol=@home,compress=zstd:1 0 0\n" % r)
        if plan.boot:
            f.write("UUID=%s /boot ext4 defaults 0 2\n" % uuid(plan.boot))
        if plan.efi:
            f.write("UUID=%s /boot/efi vfat umask=0077 0 2\n" % uuid(plan.efi))
    if passphrase is not None:
        with open(T + "/etc/crypttab", "a") as f:
            f.write("chamesle UUID=%s none luks,discard,tries=3\n" % uuid(plan.root))
    progress(2, 50)

    locale = language + ".UTF-8"
    path = T + "/etc/default/libc-locales"
    lines = open(path).read().split("\n") if os.path.exists(path) else []
    if locale + " UTF-8" not in [l.lstrip("#").strip() for l in lines]:
        lines.append(locale + " UTF-8")
    lines = [locale + " UTF-8" if l.lstrip("#").strip() == locale + " UTF-8" else l for l in lines]
    with open(path, "w") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")
    chroot("locale-gen")
    with open(T + "/etc/locale.conf", "w") as f:
        f.write("LANG=%s\n" % locale)
    layout, variant = keyboard
    os.makedirs(T + "/etc/X11/xorg.conf.d", exist_ok=True)
    with open(T + "/etc/X11/xorg.conf.d/00-keyboard.conf", "w") as f:
        f.write('Section "InputClass"\n    Identifier "system-keyboard"\n    MatchIsKeyboard "on"\n'
                '    Option "XkbLayout" "%s"\n    Option "XkbVariant" "%s"\nEndSection\n' % (layout, variant or ""))
    with open(T + "/etc/vconsole.conf", "w") as f:
        f.write("KEYMAP=%s\n" % (layout + ("-" + variant if variant else "")))
    progress(2, 100)

    if passphrase is not None:
        set_grub("GRUB_CMDLINE_LINUX", "rd.luks.uuid=%s" % uuid(plan.root))
    chroot("dracut", "--force", "--regenerate-all")
    progress(3, 40)
    cmdline = "quiet splash loglevel=3 drm.panic_screen=qr_code"
    if os.path.exists(T + "/usr/lib/chamesle/init"):
        cmdline += " init=/usr/lib/chamesle/init"
    set_grub("GRUB_DISTRIBUTOR", "Chamesle")
    set_grub("GRUB_CMDLINE_LINUX_DEFAULT", cmdline)
    set_grub("GRUB_DISABLE_OS_PROBER", "false")
    # our kernel first, void's below it for when ours doesn't start
    ours = sorted(glob.glob(T + "/boot/vmlinuz-*-cachyos-lts"))
    if ours:
        set_grub("GRUB_TOP_LEVEL", ours[-1][len(T):])
    set_grub("GRUB_GFXMODE", "auto")
    set_grub("GRUB_GFXPAYLOAD_LINUX", "keep")
    if os.path.exists(T + "/usr/share/grub/themes/chamesle/theme.txt"):
        set_grub("GRUB_THEME", "/usr/share/grub/themes/chamesle/theme.txt")
    if disks.efi():
        chroot("grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi", "--bootloader-id=chamesle")
        # some firmware only boots the fallback path
        chroot("grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi", "--removable", "--no-nvram")
    else:
        chroot("grub-install", "--target=i386-pc", row.disk)
    progress(3, 70)
    chroot("grub-mkconfig", "-o", "/boot/grub/grub.cfg")
    if "Chamesle" not in open(T + "/boot/grub/grub.cfg").read():
        raise RuntimeError("the boot menu came out without Chamesle in it")
    progress(3, 100)

    os.sync()
    subprocess.run(["umount", "-R", T])
    if passphrase is not None:
        subprocess.run(["cryptsetup", "close", "chamesle"])
    progress(4, 100)
