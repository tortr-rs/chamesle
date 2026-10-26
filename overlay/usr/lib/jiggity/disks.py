# drive scanning and partitioning
import json
import os
import subprocess

GiB = 1 << 30
MiB = 1 << 20
MIN_SIZE = 20 * GiB
ESP_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"


def efi():
    return os.path.exists("/sys/firmware/efi")


def run(*cmd, input=None):
    print("jiggity:", " ".join(cmd))
    r = subprocess.run(cmd, input=input, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode:
        raise RuntimeError("%s failed: %s" % (cmd[0], (r.stdout or "").strip().splitlines()[-1:] or ""))
    return r.stdout


def size_text(n):
    if n >= 1000 * GiB:
        return "%.1f TB" % (n / (1024 * GiB))
    if n >= GiB:
        return "%.1f GB" % (n / GiB)
    return "%d MB" % (n // MiB)


def live_medium():
    out = subprocess.run(["lsblk", "-J", "-o", "PATH,PKNAME,LABEL,FSTYPE"], text=True, stdout=subprocess.PIPE).stdout
    for d in json.loads(out)["blockdevices"]:
        for dev in [d] + d.get("children", []):
            if dev.get("label") == "CHAMESLE" or dev.get("fstype") == "iso9660":
                return d["path"]
    return None


def part_path(disk, number):
    return "%s%s%d" % (disk, "p" if disk[-1].isdigit() else "", number)


class Row:
    def __init__(self, kind, disk, label, total, free, type_text, start=0, end=0, number=0):
        self.kind, self.disk, self.label = kind, disk, label
        self.total, self.free, self.type_text = total, free, type_text
        self.start, self.end, self.number = start, end, number

    @property
    def usable(self):
        return self.kind in ("drive", "free") and self.total >= MIN_SIZE


def parted_lines(disk):
    r = subprocess.run(["parted", "-m", "-s", disk, "unit", "B", "print", "free"], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.stdout.splitlines()


def scan():
    skip = live_medium()
    out = subprocess.run(["lsblk", "-J", "-b", "-d", "-o", "PATH,SIZE,TYPE,MODEL,RO,TRAN"], text=True,
                         stdout=subprocess.PIPE).stdout
    rows = []
    n = 0
    for d in json.loads(out)["blockdevices"]:
        # skip zram and empty card readers
        if d["type"] != "disk" or d["ro"] or d["path"] == skip or d["path"].startswith("/dev/zram") or int(d["size"]) < GiB:
            continue
        name = "Drive %d" % n
        model = (d.get("model") or "").strip()
        rows.append(Row("drive", d["path"], "%s%s" % (name, ": " + model if model else ""), int(d["size"]), 0,
                        "Whole drive"))
        lines = parted_lines(d["path"])
        label = lines[1].split(":")[5] if len(lines) > 1 else "unknown"
        if label not in ("gpt", "msdos"):
            rows.append(Row("free", d["path"], "%s Unallocated Space" % name, int(d["size"]), int(d["size"]), "",
                            0, int(d["size"]) - 1))
            n += 1
            continue
        for line in lines[2:]:
            f = line.rstrip(";").split(":")
            start, end, size = (int(x.rstrip("B")) for x in f[1:4])
            if f[4] == "free":
                if size >= 64 * MiB:
                    rows.append(Row("free", d["path"], "%s Unallocated Space" % name, size, size, "", start, end))
            else:
                num = int(f[0])
                fs, pname, flags = f[4], f[5], f[6]
                kind = "System" if "esp" in flags or "boot" in flags and fs.startswith("fat") else \
                    "MSR (Reserved)" if "msftres" in flags else "Recovery" if "msftdata" not in flags and "hidden" in flags \
                    else fs or "Primary"
                free = used_free(part_path(d["path"], num), fs, size)
                rows.append(Row("part", d["path"], "%s Partition %d%s" % (name, num, ": " + pname if pname else ""),
                                size, free, kind, start, end, num))
        n += 1
    return rows


def used_free(path, fs, size):
    r = subprocess.run(["lsblk", "-J", "-b", "-o", "FSAVAIL", path], text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    try:
        avail = json.loads(r.stdout)["blockdevices"][0]["fsavail"]
        return int(avail) if avail is not None else size
    except (ValueError, KeyError, IndexError):
        return size


def numbers(disk):
    nums = set()
    for line in parted_lines(disk)[2:]:
        f = line.rstrip(";").split(":")
        if f[4] != "free":
            nums.add(int(f[0]))
    return nums


def settle():
    subprocess.run(["partprobe"], stderr=subprocess.DEVNULL)
    subprocess.run(["udevadm", "settle"])


def has_esp(disk):
    for line in parted_lines(disk)[2:]:
        f = line.rstrip(";").split(":")
        if f[4] != "free" and "esp" in f[6]:
            return part_path(disk, int(f[0]))
    return None


def has_bios_grub(disk):
    return any("bios_grub" in line for line in parted_lines(disk)[2:])


class Plan:
    # boot is only set with encryption, grub can't read luks2
    efi = boot = root = None
    format_efi = False


def make(row, encrypt):
    disk = row.disk
    plan = Plan()
    if row.kind == "drive" or parted_lines(disk)[1:2] and parted_lines(disk)[1].split(":")[5] not in ("gpt", "msdos"):
        run("wipefs", "-a", disk)
        run("parted", "-s", disk, "mklabel", "gpt")
        start, end = MiB, None
    else:
        start = (row.start + MiB - 1) // MiB * MiB
        end = (row.end + 1) // MiB * MiB
    label = parted_lines(disk)[1].split(":")[5]
    pieces = []
    if efi():
        plan.efi = has_esp(disk)
        if not plan.efi:
            pieces.append(("efi", 512 * MiB))
            plan.format_efi = True
    elif label == "gpt" and not has_bios_grub(disk):
        pieces.append(("bios_grub", MiB))
    if encrypt:
        pieces.append(("boot", GiB))
    pieces.append(("root", None))
    at = start
    for what, size in pieces:
        before = numbers(disk)
        stop = "100%" if size is None and end is None else "%dB" % ((at + size if size else end) - 1)
        if label == "gpt":
            run("parted", "-s", "-a", "optimal", disk, "unit", "B", "mkpart", "chamesle-" + what, "%dB" % at, stop)
        else:
            run("parted", "-s", "-a", "optimal", disk, "unit", "B", "mkpart", "primary", "%dB" % at, stop)
        num = (numbers(disk) - before).pop()
        path = part_path(disk, num)
        if what == "efi":
            run("parted", "-s", disk, "set", str(num), "esp", "on")
            plan.efi = path
        elif what == "bios_grub":
            run("parted", "-s", disk, "set", str(num), "bios_grub", "on")
        elif what == "boot":
            plan.boot = path
        else:
            plan.root = path
        if size:
            at += size
    settle()
    return plan
