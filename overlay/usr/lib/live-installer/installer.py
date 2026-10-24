from glob import glob
import os
import subprocess
import time
import gettext
import parted
import partitioning
import alongside
import shlex
from functools import cmp_to_key

gettext.install("live-installer", "/usr/share/locale")

class InstallerEngine:
    ''' This is central to the live installer '''

    def __init__(self, setup):
        self.setup = setup
        # the live system image, mounted there by the chamesle initramfs
        self.source = "/run/chamesle/rootfs"

    def set_progress_hook(self, progresshook):
        ''' Set a callback to be called on progress updates '''
        ''' i.e. def my_callback(progress_type, message, current_progress, total) '''
        ''' Where progress_type is any off PROGRESS_START, PROGRESS_UPDATE, PROGRESS_COMPLETE, PROGRESS_ERROR '''
        self.update_progress = progresshook

    def set_error_hook(self, errorhook):
        ''' Set a callback to be called on errors '''
        self.set_critical_error = errorhook

    def setup_user(self):
        print(" --> Adding new user")
        groups = []
        with open("/target/etc/group") as f:
            existing = [line.split(":")[0] for line in f]
        for group in 'wheel audio video input network storage optical scanner lp plugdev bluetooth users kvm'.split():
            if group in existing:
                groups.append(group)
        subprocess.run(["chroot", "/target", "useradd", "-m", "-s", "/bin/bash", "-c", self.setup.real_name,
                        "-G", ",".join(groups), self.setup.username])

        # through stdin: never in a file or on a command line. -c: hash it here, the pam setup for chpasswd
        # doesn't store anything
        subprocess.run(["chroot", "/target", "chpasswd", "-c", "SHA512"],
                       input="%s:%s\n" % (self.setup.username, self.setup.password1), text=True)

        if self.setup.autologin and os.path.exists("/target/etc/gdm/custom.conf"):
            os.system("sed -i 's/^\\[daemon\\]$/&\\nAutomaticLoginEnable=True\\nAutomaticLogin=%s/' /target/etc/gdm/custom.conf"
                      % self.setup.username)
        elif self.setup.autologin:
            os.makedirs("/target/etc/lightdm/lightdm.conf.d", exist_ok=True)
            with open("/target/etc/lightdm/lightdm.conf.d/80-autologin.conf", "w") as f:
                f.write("[Seat:*]\nautologin-user=%s\n" % self.setup.username)

    def setup_hostname(self):
        print(" --> Writing hostname")
        hostnamefh = open("/target/etc/hostname", "w")
        hostnamefh.write("%s\n" % self.setup.hostname)
        hostnamefh.close()
        hostsfh = open("/target/etc/hosts", "w")
        hostsfh.write("127.0.0.1\tlocalhost\n")
        hostsfh.write("127.0.1.1\t%s\n" % self.setup.hostname)
        hostsfh.write("# The following lines are desirable for IPv6 capable hosts\n")
        hostsfh.write("::1     localhost ip6-localhost ip6-loopback\n")
        hostsfh.write("fe00::0 ip6-localnet\n")
        hostsfh.write("ff00::0 ip6-mcastprefix\n")
        hostsfh.write("ff02::1 ip6-allnodes\n")
        hostsfh.write("ff02::2 ip6-allrouters\n")
        hostsfh.write("ff02::3 ip6-allhosts\n")
        hostsfh.close()

    def setup_locale(self):
        print(" --> Setting the locale")
        locale = "%s.UTF-8" % self.setup.language
        path = "/target/etc/default/libc-locales"
        lines = open(path).read().split("\n") if os.path.exists(path) else []
        wanted = "%s UTF-8" % locale
        found = False
        for i, line in enumerate(lines):
            if line.lstrip("#").strip() == wanted:
                lines[i] = wanted
                found = True
        if not found:
            lines.append(wanted)
        with open(path, "w") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
        self.do_run_in_chroot("locale-gen")
        with open("/target/etc/locale.conf", "w") as f:
            f.write("LANG=%s\n" % locale)

    def setup_timezone(self):
        print(" --> Setting the timezone")
        os.system("echo \"%s\" > /target/etc/timezone" % self.setup.timezone)
        os.system("rm -f /target/etc/localtime")
        os.system("ln -s /usr/share/zoneinfo/%s /target/etc/localtime" % self.setup.timezone)

    def setup_localization(self):
        # firefox in your language, if we're online
        if self.setup.language.startswith("en"):
            return
        print(" --> Localizing packages")
        lang = self.setup.language.split("_")[0]
        for pkg in ("firefox-i18n-%s" % self.setup.language.replace("_", "-"), "firefox-i18n-%s" % lang):
            if subprocess.run(["chroot", "/target", "apk", "add", "--quiet", pkg]).returncode == 0:
                break

    def setup_keyboard(self):
        print(" --> Setting the keyboard")
        os.makedirs("/target/etc/X11/xorg.conf.d", exist_ok=True)
        with open("/target/etc/X11/xorg.conf.d/00-keyboard.conf", "w") as f:
            f.write('Section "InputClass"\n'
                    '    Identifier "system-keyboard"\n'
                    '    MatchIsKeyboard "on"\n'
                    '    Option "XkbLayout" "%s"\n'
                    '    Option "XkbModel" "%s"\n'
                    '    Option "XkbVariant" "%s"\n'
                    '    Option "XkbOptions" "grp:win_space_toggle"\n'
                    'EndSection\n' % (self.setup.keyboard_layout, self.setup.keyboard_model,
                                      self.setup.keyboard_variant or ""))
        # the console takes the last layout (the one that isn't "us," for non-latin ones)
        keymap = self.setup.keyboard_layout.split(",")[-1]
        variant = (self.setup.keyboard_variant or "").split(",")[-1]
        if variant and os.system("find /target/usr/share/kbd/keymaps -name '%s-%s.map*' | grep -q ." % (keymap, variant)) == 0:
            keymap = "%s-%s" % (keymap, variant)
        with open("/target/etc/vconsole.conf", "w") as f:
            f.write("KEYMAP=%s\n" % keymap)

    def start_installation(self):

        # mount the media location.
        print(" --> Installation started")
        if(not os.path.exists("/target")):
            if (self.setup.skip_mount):
                self.set_critical_error(message=_("ERROR: You must first manually mount your target filesystem(s) at /target to do a custom install!"))
                return
            os.mkdir("/target")

        os.system("umount --force /target/sys/firmware/efi/efivars")
        os.system("umount --force /target/dev/shm")
        os.system("umount --force /target/dev/pts")
        os.system("umount --force /target/dev/")
        os.system("umount --force /target/sys/")
        os.system("umount --force /target/proc/")
        os.system("umount --force /target/run/")

        print(" --> Mounting partitions")
        self.update_progress(50, False, False, _("Mounting partitions..."))
        if not os.path.isdir(os.path.join(self.source, "usr")) and not __debug__:
            print("Live system expected at %s" % self.source)
            self.set_critical_error(message=_("Live medium not found!"))
            return

        def rootiest_first(parta, partb):
            if parta.mount_as == None or parta.mount_as == "" or \
               partb.mount_as == None or partb.mount_as == "":
                return 0

            if len(parta.mount_as) > len(partb.mount_as):
                return 1
            elif len(partb.mount_as) > len(parta.mount_as):
                return -1
            else:
                return 0

        self.setup.partitions.sort(key=cmp_to_key(rootiest_first))

        print("********** Partition mount order ***")
        for part in self.setup.partitions:
            print(part.mount_as)
        print("************************************")

        if (not self.setup.skip_mount):
            if self.setup.automated:
                self.create_partitions()
            else:
                self.format_partitions()
                self.mount_partitions()

        # Transfer the files
        SOURCE = self.source + "/"
        DEST = "/target/"
        EXCLUDE_DIRS = "home/* dev/* proc/* sys/* tmp/* run/* mnt/* media/* lost+found source target".split()
        num_copied = 0
        # (Valid) assumption: num-of-files-to-copy ~= num-of-used-inodes-on-/
        num_files = int(subprocess.getoutput("df --inodes {src} | awk 'END{{ print $3 }}'".format(src=SOURCE)))
        print(f" --> Copying {num_files} files")
        rsync_filter = ' '.join('--exclude=' + SOURCE + d for d in EXCLUDE_DIRS)
        rsync = subprocess.Popen("rsync --verbose --archive --no-D --acls "
                                 "--hard-links --xattrs {rsync_filter} "
                                 "{src}* {dst}".format(src=SOURCE, dst=DEST, rsync_filter=rsync_filter),
                                 shell=True, encoding='utf-8', errors='ignore', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while rsync.poll() is None:
            line = rsync.stdout.readline()
            if not line:  # still copying the previous file, just wait
                time.sleep(0.1)
            else:
                num_copied = min(num_copied + 1, num_files)
                percentage = int(float(num_copied) / float(num_files) * 100)
                self.update_progress(percentage, False, False, _("Copying files..."))
        print("rsync exited with returncode: " + str(rsync.poll()))

        # chroot
        print(" --> Chrooting")
        self.update_progress(10, False, False, _("Entering the system..."))
        os.system("mount --bind /dev/ /target/dev/")
        os.system("mount --bind /dev/shm /target/dev/shm")
        os.system("mount --bind /dev/pts /target/dev/pts")
        os.system("mount --bind /sys/ /target/sys/")
        os.system("mount --bind /proc/ /target/proc/")
        os.system("mount --bind /run/ /target/run/")
        os.system("mv /target/etc/resolv.conf /target/etc/resolv.conf.bk")
        os.system("cp -f /etc/resolv.conf /target/etc/resolv.conf")

        if os.path.exists("/sys/firmware/efi/efivars"):
            os.system("mkdir -p /target/sys/firmware/efi/efivars")
            os.system("mount --bind /sys/firmware/efi/efivars /target/sys/firmware/efi/efivars/")

        # remove what only the live session has
        print(" --> Removing live configuration")
        self.update_progress(20, False, False, _("Removing live configuration (packages)"))
        for path in ("/etc/sudoers.d/live", "/etc/polkit-1/rules.d/49-live.rules", "/etc/lightdm/lightdm.conf.d/90-live.conf",
                     "/usr/share/applications/chamesle-install.desktop", "/usr/bin/chamesle-install",
                     "/usr/bin/live-installer", "/usr/lib/live-installer", "/usr/share/live-installer",
                     "/usr/share/icons/live-installer-progress-dot-on.png",
                     "/usr/share/icons/live-installer-progress-dot-off.png", "/var/lib/AccountsService/users/live"):
            os.system("rm -rf /target%s" % path)
        # gdm keeps the live autologin in its one config file
        if os.path.exists("/target/etc/gdm/custom.conf"):
            os.system("sed -i '/^# the live session only$/d; /^AutomaticLogin/d' /target/etc/gdm/custom.conf")
        self.do_run_in_chroot("userdel -r live")

        # add new user
        self.update_progress(30, False, False, _("Adding new user to the system"))
        self.setup_user()

        # Lock and delete root password
        self.do_run_in_chroot("passwd -dl root")

        # Set LightDM to show user list by default
        self.do_run_in_chroot(r"sed -i -r 's/^#?(greeter-hide-users)\s*=.*/\1=false/' /etc/lightdm/lightdm.conf")

        # /etc/fstab, mtab and crypttab
        self.update_progress(40, False, False, _("Writing filesystem mount information to /etc/fstab"))
        self.write_fstab()
        self.write_mtab()
        self.write_crypttab()

    def create_partitions(self):
        if self.setup.alongside:
            return self.create_alongside()
        # Create partitions on the selected disk (automated installation)
        partition_prefix = partitioning.get_device_naming_scheme_prefix(self.setup.disk)
        if self.setup.luks:
            if self.setup.gptonefi:
                # EFI+LUKS/LVM
                # sdx1=EFI, sdx2=BOOT, sdx3=ROOT
                self.auto_efi_partition  = self.setup.disk + partition_prefix + "1"
                self.auto_boot_partition = self.setup.disk + partition_prefix + "2"
                self.auto_swap_partition = None
                self.auto_root_partition = self.setup.disk + partition_prefix + "3"
            else:
                # BIOS+LUKS/LVM
                # sdx1=BOOT, sdx2=ROOT
                self.auto_efi_partition  = None
                self.auto_boot_partition = self.setup.disk + partition_prefix + "1"
                self.auto_swap_partition = None
                self.auto_root_partition = self.setup.disk + partition_prefix + "2"
        elif self.setup.lvm:
            if self.setup.gptonefi:
                # EFI+LVM
                # sdx1=EFI, sdx2=ROOT
                self.auto_efi_partition  = self.setup.disk + partition_prefix + "1"
                self.auto_boot_partition = None
                self.auto_swap_partition = None
                self.auto_root_partition = self.setup.disk + partition_prefix + "2"
            else:
                # BIOS+LVM:
                # sdx1=ROOT
                self.auto_efi_partition  = None
                self.auto_boot_partition = None
                self.auto_swap_partition = None
                self.auto_root_partition = self.setup.disk + partition_prefix + "1"
        else:
            if self.setup.gptonefi:
                # EFI
                # sdx1=EFI, sdx2=SWAP, sdx3=ROOT
                self.auto_efi_partition  = self.setup.disk + partition_prefix + "1"
                self.auto_boot_partition = None
                self.auto_swap_partition = self.setup.disk + partition_prefix + "2"
                self.auto_root_partition = self.setup.disk + partition_prefix + "3"
            else:
                # BIOS:
                # sdx1=SWAP, sdx2=ROOT
                self.auto_efi_partition  = None
                self.auto_boot_partition = None
                self.auto_swap_partition = self.setup.disk + partition_prefix + "1"
                self.auto_root_partition = self.setup.disk + partition_prefix + "2"

        self.auto_root_physical_partition = self.auto_root_partition

        # Wipe HDD
        if self.setup.badblocks:
            self.update_progress(25, False, False, _("Filling disk with random data (please be patient, this can take hours...)"))
            print(" --> Filling %s with random data" % self.setup.disk)
            os.system("badblocks -c 10240 -s -w -t random -v %s" % self.setup.disk)

        # Create partitions
        self.update_progress(25, False, False, _("Creating partitions on %s") % self.setup.disk)
        print(" --> Creating partitions on %s" % self.setup.disk)
        disk_device = parted.getDevice(self.setup.disk)
        partitioning.full_disk_format(disk_device, create_boot=(self.auto_boot_partition is not None), create_swap=(self.auto_swap_partition is not None))

        # Encrypt root partition
        if self.setup.luks:
            print(" --> Encrypting root partition %s" % self.auto_root_partition)
            # the passphrase goes in on stdin, where ps can't see it and echo can't eat a leading -n or -e
            subprocess.run(["cryptsetup", "luksFormat", "--batch-mode", "-c", "aes-xts-plain64", "-h", "sha256", "-s", "512",
                            "--key-file=-", self.auto_root_partition], input=self.setup.passphrase1, text=True)
            print(" --> Opening root partition %s" % self.auto_root_partition)
            subprocess.run(["cryptsetup", "luksOpen", "--key-file=-", self.auto_root_partition, "chamesle"],
                           input=self.setup.passphrase1, text=True)
            self.auto_root_partition = "/dev/mapper/chamesle"

        # Setup LVM
        if self.setup.lvm:
            print(" --> LVM: Creating PV")
            os.system("pvcreate -y %s" % self.auto_root_partition)
            print(" --> LVM: Creating VG")
            os.system("vgcreate -y chamesle %s" % self.auto_root_partition)
            print(" --> LVM: Creating LV root")
            os.system("lvcreate -y -n root -L 1GB chamesle")
            print(" --> LVM: Creating LV swap")
            os.system("lvcreate -y -n swap -L 2GB chamesle")
            print(" --> LVM: Extending LV root")
            os.system(r"lvextend -l 100%FREE /dev/chamesle/root")
            print(" --> LVM: Formatting LV swap")
            os.system("mkswap -f /dev/mapper/chamesle-swap")
            print(" --> LVM: Enabling LV swap")
            os.system("swapon /dev/mapper/chamesle-swap")
            self.auto_root_partition = "/dev/mapper/chamesle-root"
            self.auto_swap_partition = "/dev/mapper/chamesle-swap"

        self.make_root_btrfs(self.auto_root_partition)
        if (self.auto_boot_partition is not None):
            os.system("mkdir -p /target/boot")
            self.do_mount(self.auto_boot_partition, "/target/boot", "ext4", None)
        if (self.auto_efi_partition is not None):
            os.system("mkdir -p /target/boot/efi")
            self.do_mount(self.auto_efi_partition, "/target/boot/efi", "vfat", None)

    def make_root_btrfs(self, device):
        # btrfs, with the system in @ and your files in @home: the system gets snapshotted before updates
        # (chamesle-snapshot), your files never
        print(" --> Formatting %s as btrfs (@ and @home)" % device)
        self.exec_cmd("mkfs.btrfs -f %s" % device)
        self.do_mount(device, "/target", "btrfs", None)
        os.system("btrfs subvolume create /target/@ /target/@home")
        os.system("umount /target")
        self.do_mount(device, "/target", "btrfs", "subvol=@")
        os.makedirs("/target/home", exist_ok=True)
        self.do_mount(device, "/target/home", "btrfs", "subvol=@home")

    def create_alongside(self):
        win = self.setup.windows
        self.update_progress(15, True, False, _("Shrinking Windows (this can take a while)"))
        print(" --> Shrinking %s to make room for %d bytes" % (win["path"], self.setup.alongside_size))
        root = alongside.shrink_and_make_room(win, self.setup.alongside_size)
        self.auto_root_partition = self.auto_root_physical_partition = root
        self.auto_boot_partition = self.auto_swap_partition = None
        self.auto_efi_partition = alongside.find_esp(win["disk"]) if self.setup.gptonefi else None
        self.update_progress(25, False, False, _("Formatting partitions..."))
        self.make_root_btrfs(root)
        if self.auto_efi_partition is not None:
            # windows' own EFI partition, shared, not formatted
            os.system("mkdir -p /target/boot/efi")
            self.do_mount(self.auto_efi_partition, "/target/boot/efi", "vfat", None)

    def format_partitions(self):
        for partition in self.setup.partitions:
            if(partition.format_as is not None and partition.format_as != ""):
                # report it. should grab the total count of filesystems to be formatted ..
                self.update_progress(25, True, False, _("Formatting partitions..."))

                #Format it
                if partition.format_as == "swap":
                    cmd = "mkswap %s" % partition.path
                else:
                    if (partition.format_as in ['ext2', 'ext3', 'ext4']):
                        cmd = "mkfs.%s -F %s" % (partition.format_as, partition.path)
                    elif (partition.format_as == "jfs"):
                        cmd = "mkfs.%s -q %s" % (partition.format_as, partition.path)
                    elif (partition.format_as in ["btrfs", "xfs"]):
                        cmd = "mkfs.%s -f %s" % (partition.format_as, partition.path)
                    elif (partition.format_as == "vfat"):
                        cmd = "mkfs.%s %s -F 32" % (partition.format_as, partition.path)
                    else:
                        cmd = "mkfs.%s %s" % (partition.format_as, partition.path) # works with bfs, minix, msdos, ntfs, vfat

                print("EXECUTING: '%s'" % cmd)
                self.exec_cmd(cmd)
                partition.type = partition.format_as

    def mount_partitions(self):
        # Mount the target partition
        for partition in self.setup.partitions:
            if(partition.mount_as is not None and partition.mount_as != ""):
                if partition.mount_as == "/":
                    self.update_progress(75, False, False, _("Mounting %(partition)s on %(mountpoint)s") % {'partition':partition.path, 'mountpoint':"/target/"})
                    print(" ------ Mounting partition %s on %s" % (partition.path, "/target/"))
                    fs = partition.type
                    if fs == "fat32":
                        fs = "vfat"
                    self.do_mount(partition.path, "/target", fs, None)
                    if fs == "btrfs":
                        # Create subvolumes for Btrfs
                        os.system("btrfs subvolume create /target/@")
                        os.system("btrfs subvolume list -p /target")
                        print(" ------ Umount btrfs to remount subvolume @")
                        os.system("umount --force /target")
                        self.do_mount(partition.path, "/target", fs, "subvol=@")
                        if not self.setup_has_dedicated_home():
                            # If there is no dedicated home partition, add a @home subvolume to /
                            os.system("mkdir -p /target/home")
                            self.do_mount(partition.path, "/target/home", fs, None)
                            os.system("btrfs subvolume create /target/home/@home")
                            os.system("btrfs subvolume list -p /target/home")
                            print(" ------- Umount btrfs to remount subvolume @home")
                            os.system("umount --force /target/home")
                            self.do_mount(partition.path, "/target/home", fs, "subvol=@home")
                    break

        # Mount the other partitions
        for partition in self.setup.partitions:
            if(partition.mount_as is not None and partition.mount_as != "" and partition.mount_as != "/" and partition.mount_as != "swap"):
                print(" ------ Mounting %s on %s" % (partition.path, "/target" + partition.mount_as))
                os.system("mkdir -p /target" + partition.mount_as)
                fs = partition.type
                if fs == "fat16" or fs == "fat32":
                    fs = "vfat"
                self.do_mount(partition.path, "/target" + partition.mount_as, fs, None)
                if partition.mount_as == "/home" and fs == "btrfs":
                    # Dedicated home partition with Btrfs, needs a @home subvolume
                    os.system("btrfs subvolume create /target/home/@home")
                    os.system("btrfs subvolume list -p /target/home")
                    print(" ------- Umount btrfs to remount subvolume @home")
                    os.system("umount --force /target/home")
                    self.do_mount(partition.path, "/target/home", fs, "subvol=@home")

    def get_blkid(self, path):
        uuid = path # If we can't find the UUID we use the path
        blkid = subprocess.getoutput('blkid').split('\n')
        for blkid_line in blkid:
            blkid_elements = blkid_line.split(':')
            if blkid_elements[0] == path:
                blkid_mini_elements = blkid_line.split()
                for blkid_mini_element in blkid_mini_elements:
                    if "UUID=" in blkid_mini_element:
                        uuid = blkid_mini_element.replace('"', '').strip()
                        break
                break
        return uuid

    def setup_has_dedicated_home(self):
        # Find out if there is a dedicated home partition
        has_dedicated_home = False
        for partition in self.setup.partitions:
            if partition.mount_as == "/home":
                has_dedicated_home = True
                break
        return has_dedicated_home

    def write_fstab(self, path="/target/etc/fstab"):
        # write the /etc/fstab
        print(" --> Writing fstab")
        # make sure fstab has default /proc and /sys entries
        fstab = open(path, "w")
        fstab.write("#### Static Filesystem Table File\n")
        fstab.write("proc\t/proc\tproc\tdefaults\t0\t0\n")
        if(not self.setup.skip_mount):
            if self.setup.automated:
                fstab.write("# %s\n" % self.auto_root_partition)
                root_uuid = self.get_blkid(self.auto_root_partition)
                fstab.write("%s /  btrfs defaults,subvol=@ 0 0\n" % root_uuid)
                fstab.write("%s /home  btrfs defaults,subvol=@home 0 0\n" % root_uuid)
                if self.auto_swap_partition is not None:
                    fstab.write("# %s\n" % self.auto_swap_partition)
                    fstab.write("%s none   swap sw 0 0\n" % self.get_blkid(self.auto_swap_partition))
                if (self.auto_boot_partition is not None):
                    fstab.write("# %s\n" % self.auto_boot_partition)
                    fstab.write("%s /boot  ext4 defaults 0 1\n" % self.get_blkid(self.auto_boot_partition))
                if (self.auto_efi_partition is not None):
                    fstab.write("# %s\n" % self.auto_efi_partition)
                    fstab.write("%s /boot/efi  vfat defaults 0 1\n" % self.get_blkid(self.auto_efi_partition))
            else:
                for partition in self.setup.partitions:
                    if (partition.mount_as is not None and partition.mount_as != "" and partition.mount_as != "None"):
                        fs = partition.type
                        if fs == "fat16" or fs == "fat32":
                            fs = "vfat"
                        fstab.write("# %s\n" % (partition.path))
                        fstab_fsck_option = "0"
                        if fs != "btrfs" and partition.mount_as in ["/", "/boot", "/boot/efi"]:
                            fstab_fsck_option = "1"
                        if "ext" in fs:
                            fstab_mount_options = "rw,errors=remount-ro"
                        elif fs == "btrfs" and partition.mount_as == "/":
                            fstab_mount_options = "defaults,subvol=@"
                        elif fs == "btrfs" and partition.mount_as == "/home":
                            fstab_mount_options = "defaults,subvol=@home"
                        else:
                            fstab_mount_options = "defaults"

                        partition_uuid = self.get_blkid(partition.path)
                        if fs == "swap":
                            fstab.write("%s\tswap\tswap\tsw\t0\t0\n" % partition_uuid)
                        else:
                            fstab.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (partition_uuid, partition.mount_as, fs, fstab_mount_options, "0", fstab_fsck_option))

                        if fs == "btrfs" and partition.mount_as == "/" and not self.setup_has_dedicated_home():
                            # Special case, if / is btrfs and there is no dedicated /home, add the @home subvolume to /
                            fstab.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (partition_uuid, "/home", "btrfs", "defaults,subvol=@home", "0", "0"))
        fstab.close()

    def write_mtab(self, fstab="/target/etc/fstab", mtab="/target/etc/mtab"):
        if self.setup.lvm:
            os.system(f"grep -v swap {fstab} > {mtab}")

    def write_crypttab(self, path="/target/etc/crypttab"):
        if self.setup.luks:
            os.system(f"echo 'chamesle   {self.get_blkid(self.auto_root_physical_partition)}   none   luks,discard,tries=3' >> {path}")

    def finish_installation(self):

        self.update_progress(50, False, False, _("Setting hostname"))
        self.setup_hostname()

        self.update_progress(55, False, False, _("Setting locale"))
        self.setup_locale()

        self.update_progress(60, False, False, _("Setting timezone"))
        self.setup_timezone()

        self.update_progress(65, False, False, _("Localizing packages"))
        self.setup_localization()

        # set the keyboard options..
        self.update_progress(75, False, False, _("Setting keyboard options"))
        self.setup_keyboard()

        if self.setup.luks:
            uuid = self.get_blkid(self.auto_root_physical_partition).replace("UUID=", "")
            self.set_grub_option("GRUB_CMDLINE_LINUX", "rd.luks.uuid=%s rd.lvm.vg=chamesle" % uuid)
        elif self.setup.lvm:
            self.set_grub_option("GRUB_CMDLINE_LINUX", "rd.lvm.vg=chamesle")

        # the initramfs the installed system boots with
        print(" --> Configuring Initramfs")
        self.update_progress(78, True, False, _("Configuring the initramfs"))
        self.do_run_in_chroot("dracut --force --regenerate-all")

        # boot menu
        print(" --> Configuring Grub")
        if(self.setup.grub_device is not None):
            self.update_progress(80, False, False, _("Installing bootloader"))
            self.set_grub_option("GRUB_DISTRIBUTOR", "Chamesle")
            self.set_grub_option("GRUB_CMDLINE_LINUX_DEFAULT", "quiet splash loglevel=3")
            self.set_grub_option("GRUB_DISABLE_OS_PROBER", "false")
            self.set_grub_option("GRUB_GFXMODE", "auto")
            self.set_grub_option("GRUB_GFXPAYLOAD_LINUX", "keep")
            if os.path.exists("/target/usr/share/backgrounds/chamesle/grub.png"):
                self.set_grub_option("GRUB_BACKGROUND", "/usr/share/backgrounds/chamesle/grub.png")
            print(" --> Running grub-install")
            if os.path.exists("/sys/firmware/efi"):
                self.do_run_in_chroot("grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=chamesle --recheck")
                # also as the fallback loader, some firmware only boots that
                self.do_run_in_chroot("grub-install --target=x86_64-efi --efi-directory=/boot/efi --removable --no-nvram")
            else:
                self.do_run_in_chroot("grub-install --target=i386-pc --force %s" % self.setup.grub_device)
            self.do_configure_grub()
            grub_retries = 0
            while (not self.do_check_grub()):
                self.do_configure_grub()
                grub_retries = grub_retries + 1
                if grub_retries >= 5:
                    self.set_critical_error(message=_("WARNING: The grub bootloader was not configured properly! You need to configure it manually."))
                    break

        # now unmount it
        print(" --> Unmounting partitions")

        if os.path.exists("/target/sys/firmware/efi/efivars"):
            os.system("umount --force /target/sys/firmware/efi/efivars")

        os.system("umount --force /target/dev/shm")
        os.system("umount --force /target/dev/pts")
        if self.setup.gptonefi:
            os.system("umount --force /target/boot/efi")
            os.system("umount --force /target/media/cdrom")
        os.system("umount --force /target/boot")
        os.system("umount --force /target/dev/")
        os.system("umount --force /target/sys/")
        os.system("umount --force /target/proc/")
        os.system("umount --force /target/run/")
        os.system("rm -f /target/etc/resolv.conf")
        os.system("mv /target/etc/resolv.conf.bk /target/etc/resolv.conf")
        if(not self.setup.skip_mount):
            for partition in self.setup.partitions:
                if(partition.mount_as is not None and partition.mount_as != "" and partition.mount_as != "/" and partition.mount_as != "swap"):
                    self.do_unmount("/target" + partition.mount_as)

            # btrfs subvolumes are mounts, but will block unmounting /target. This will
            # unmount the submounts also.
            cmd = "umount -AR /target"
            print("Unmounting the target root: '%s'" % cmd)
            self.exec_cmd(cmd)

        self.update_progress(100, False, True, _("Installation finished"))
        print(" --> All done")

    def set_grub_option(self, key, value):
        path = "/target/etc/default/grub"
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

    def do_run_in_chroot(self, command):
        command = command.replace('"', "'").strip()
        print("chroot /target/ /bin/sh -c \"%s\"" % command)
        os.system("chroot /target/ /bin/sh -c \"%s\"" % command)

    def do_configure_grub(self):
        self.update_progress(85, True, False, _("Configuring bootloader"))
        print(" --> Running grub-mkconfig")
        self.do_run_in_chroot("grub-mkconfig -o /boot/grub/grub.cfg")
        grub_output = subprocess.getoutput("chroot /target/ /bin/sh -c \"grub-mkconfig -o /boot/grub/grub.cfg\"")
        grubfh = open("/var/log/live-installer-grub-output.log", "w")
        grubfh.writelines(grub_output)
        grubfh.close()

    def do_check_grub(self):
        self.update_progress(90, True, False, _("Checking bootloader"))
        print(" --> Checking Grub configuration")
        time.sleep(5)
        found_entry = False
        if os.path.exists("/target/boot/grub/grub.cfg"):
            grubfh = open("/target/boot/grub/grub.cfg", "r")
            for line in grubfh:
                line = line.rstrip("\r\n")
                if "menuentry" in line and "Chamesle" in line:
                    found_entry = True
                    print(" --> Found Grub entry: %s " % line)
            grubfh.close()
            return (found_entry)
        else:
            print("!No /target/boot/grub/grub.cfg file found!")
            return False

    def do_mount(self, device, dest, type, options=None):
        ''' Mount a filesystem '''
        p = None
        if(options is not None):
            cmd = "mount -o %s -t %s %s %s" % (options, type, device, dest)
        else:
            cmd = "mount -t %s %s %s" % (type, device, dest)
        print("EXECUTING: '%s'" % cmd)
        self.exec_cmd(cmd)

    def do_unmount(self, mountpoint):
        ''' Unmount a filesystem '''
        cmd = "umount %s" % mountpoint
        print("EXECUTING: '%s'" % cmd)
        self.exec_cmd(cmd)

    # Execute schell command and return output in a list
    def exec_cmd(self, cmd):
        p = subprocess.Popen(cmd, shell=True, encoding='utf-8', errors='ignore', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lstOut = []
        for line in p.stdout.readlines():
            # Strip the line, also from null spaces (strip() only strips white spaces)
            line = line.strip().strip("\0")
            if line != '':
                lstOut.append(line)
        return lstOut

# Represents the choices made by the user
class Setup(object):
    is_mint = False
    oem_mode = False
    language = None
    timezone = None
    keyboard_model = None
    keyboard_layout = None
    keyboard_variant = None
    partitions = [] #Array of PartitionSetup objects
    username = None
    hostname = None
    autologin = False
    ecryptfs = False
    password1 = None
    password2 = None
    real_name = None
    grub_device = None
    disks = []
    automated = True
    alongside = False
    windows = None
    alongside_size = 0
    disk = None
    diskname = None
    passphrase1 = None
    passphrase2 = None
    lvm = False
    luks = False
    badblocks = False
    target_disk = None
    gptonefi = False
    # Optionally skip all mouting/partitioning for advanced users with custom setups (raid/dmcrypt/etc)
    # Make sure the user knows that they need to:
    #  * Mount their target directory structure at /target
    #  * NOT mount /target/dev, /target/dev/shm, /target/dev/pts, /target/proc, and /target/sys
    #  * Manually create /target/etc/fstab after start_installation has completed and before finish_installation is called
    #  * Install cryptsetup/dmraid/mdadm/etc in target environment (using chroot) between start_installation and finish_installation
    #  * Make sure target is mounted using the same block device as is used in /target/etc/fstab (eg if you change the name of a dm-crypt device between now and /target/etc/fstab, update-initramfs will likely fail)
    skip_mount = False

    #Descriptions (used by the summary screen)
    keyboard_model_description = None
    keyboard_layout_description = None
    keyboard_variant_description = None

    def print_setup(self):
        if __debug__:
            print("-------------------------------------------------------------------------")
            print("Is Mint: %s" % self.is_mint)
            print("OEM mode: %s" % self.oem_mode)
            print("language: %s" % self.language)
            print("timezone: %s" % self.timezone)
            print("keyboard: %s - %s (%s) - %s - %s (%s)" % (self.keyboard_model, self.keyboard_layout, self.keyboard_variant, self.keyboard_model_description, self.keyboard_layout_description, self.keyboard_variant_description))
            print("user: %s (%s)" % (self.username, self.real_name))
            print("autologin: ", self.autologin)
            print("ecryptfs: ", self.ecryptfs)
            print("hostname: %s " % self.hostname)
            print("password: %s" % ("set" if self.password1 else "none"))
            print("grub_device: %s " % self.grub_device)
            print("skip_mount: %s" % self.skip_mount)
            print("automated: %s" % self.automated)
            if self.automated:
                print("disk: %s (%s)" % (self.disk, self.diskname))
                print("luks: %s" % self.luks)
                print("badblocks: %s" % self.badblocks)
                print("lvm: %s" % self.lvm)
                print("passphrase: %s" % ("set" if self.passphrase1 else "none"))
            if (not self.skip_mount):
                print("target_disk: %s " % self.target_disk)
                if self.gptonefi:
                    print("GPT partition table: True")
                else:
                    print("GPT partition table: False")
                print("disks: %s " % self.disks)
                print("partitions:")
                for partition in self.partitions:
                    partition.print_partition()
            print("-------------------------------------------------------------------------")
