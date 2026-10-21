# install next to windows: find it, shrink it, make a partition in the space freed up
import json
import os
import re
import subprocess
import time

GB = 1000 ** 3
MIB = 1024 * 1024
MIN_CHAMESLE = 20 * GB
# windows needs room to breathe after we take our share
WINDOWS_SPARE = 10 * GB
ESP_GUID = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
MOUNT = "/tmp/alongside"


def run(cmd, input=None):
    return subprocess.run(cmd, input=input, capture_output=True, text=True)


def lsblk():
    out = run(["lsblk", "-J", "-b", "-o", "NAME,PATH,FSTYPE,SIZE,TYPE,PKNAME,PTTYPE,PARTTYPE,PARTN,MOUNTPOINT"]).stdout
    found = []

    def walk(devs):
        for d in devs:
            found.append(d)
            walk(d.get("children", []))
    walk(json.loads(out)["blockdevices"])
    return found


def has_windows(path):
    os.makedirs(MOUNT, exist_ok=True)
    if run(["mount", "-o", "ro", path, MOUNT]).returncode != 0:
        return False
    try:
        return os.path.isdir(os.path.join(MOUNT, "Windows", "System32"))
    finally:
        run(["umount", MOUNT])


def min_size(path):
    # the smallest ntfsresize says the filesystem can go, None if it can't be resized (hibernated, dirty...)
    r = run(["ntfsresize", "--info", "--force", "--no-progress-bar", path])
    m = re.search(r"You might resize at (\d+) bytes", r.stdout)
    return int(m.group(1)) if m else None


def find_windows():
    """the biggest ntfs partition with windows on it, as a dict, or None"""
    devs = lsblk()
    best = None
    for d in devs:
        if d.get("type") != "part" or d.get("fstype") != "ntfs" or d.get("mountpoint"):
            continue
        disk = "/dev/" + d["pkname"]
        parts = [p for p in devs if p.get("pkname") == d["pkname"] and p.get("type") == "part"]
        if d.get("pttype") == "dos" and len(parts) >= 4:
            continue  # no room for another primary partition
        if not has_windows(d["path"]):
            continue
        smallest = min_size(d["path"])
        if smallest is None:
            continue
        size = int(d["size"])
        room = size - smallest - WINDOWS_SPARE
        if room < MIN_CHAMESLE:
            continue
        if best is None or size > best["size"]:
            best = {"path": d["path"], "disk": disk, "partn": int(d["partn"]), "name": d["name"],
                    "size": size, "min": smallest + WINDOWS_SPARE, "pttype": d.get("pttype")}
    return best


def find_esp(disk):
    for d in lsblk():
        if d.get("type") == "part" and "/dev/" + (d.get("pkname") or "") == disk:
            if (d.get("parttype") or "").lower() in (ESP_GUID, "0xef"):
                return d["path"]
    return None


def shrink_and_make_room(win, chamesle_bytes):
    """shrink windows so chamesle gets chamesle_bytes after it, returns the new partition's path"""
    sector = 512
    with open("/sys/class/block/%s/start" % win["name"]) as f:
        start = int(f.read())
    with open("/sys/class/block/%s/size" % win["name"]) as f:
        old_sectors = int(f.read())

    keep = (win["size"] - chamesle_bytes) // MIB * MIB
    if keep < win["min"]:
        raise Exception("Windows can't be made that small")

    # the filesystem first, then the partition around it (1 MiB bigger, to be safe)
    r = run(["ntfsresize", "--force", "--no-progress-bar", "--size", str(keep), win["path"]], input="y\n")
    if r.returncode != 0:
        raise Exception("Couldn't shrink Windows:\n" + r.stdout + r.stderr +
                        "\nStart Windows, turn off Fast Startup and shut it down fully, then try again.")
    part_sectors = (keep + MIB) // sector
    r = run(["sfdisk", "--no-reread", "--no-tell-kernel", "-N", str(win["partn"]), win["disk"]],
            input=",%d\n" % part_sectors)
    if r.returncode != 0:
        raise Exception("Couldn't resize the Windows partition:\n" + r.stderr)

    # the new one goes in the space that was freed, lined up on 1 MiB
    new_start = (start + part_sectors + 2047) // 2048 * 2048
    new_sectors = start + old_sectors - new_start
    before = {d["path"] for d in lsblk()}
    kind = "L" if win["pttype"] == "gpt" else "83"
    r = run(["sfdisk", "--no-reread", "--no-tell-kernel", "--append", win["disk"]],
            input="%d,%d,%s\n" % (new_start, new_sectors, kind))
    if r.returncode != 0:
        raise Exception("Couldn't create the new partition:\n" + r.stderr)
    run(["partx", "-u", win["disk"]])
    run(["udevadm", "settle"])
    for _ in range(20):
        new = [d["path"] for d in lsblk() if d["path"] not in before and d.get("type") == "part"]
        if new:
            return new[0]
        time.sleep(0.5)
    raise Exception("The new partition didn't show up")
