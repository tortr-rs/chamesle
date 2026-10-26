# first start without gtk: the time zones, the network, making the account
import os
import re
import subprocess

MARK = "/etc/chamesle/firstboot"
GROUPS = "wheel audio video input network storage optical scanner lp plugdev bluetooth users kvm".split()


def zones():
    out = []
    try:
        for line in open("/usr/share/zoneinfo/zone1970.tab"):
            if not line.startswith("#"):
                out.append(line.split("\t")[2].strip())
    except OSError:
        out = ["UTC"]
    return sorted(out)


def online():
    r = subprocess.run(["nmcli", "-t", "-f", "STATE", "general"], text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    return r.stdout.strip() == "connected"


def username_from(name):
    return re.sub(r"[^a-z0-9_-]", "", name.split(" ")[0].lower())


# what's wrong with a username, or ""
def bad_username(u):
    if u and not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", u):
        return "A username is lowercase letters and numbers, starting with a letter."
    if u in ("root", "live", "daemon", "bin", "nobody"):
        return "That username is taken by the system. Pick another one."
    return ""


def make(zone, user, name, pw):
    groups = [g.split(":")[0] for g in open("/etc/group")]
    subprocess.run(["useradd", "-m", "-s", "/bin/bash", "-c", name, "-G",
                    ",".join(g for g in GROUPS if g in groups), user])
    subprocess.run(["chpasswd", "-c", "SHA512"], input="%s:%s\n" % (user, pw), text=True)
    subprocess.run(["ln", "-sf", "/usr/share/zoneinfo/" + zone, "/etc/localtime"])
    with open("/etc/timezone", "w") as f:
        f.write(zone + "\n")
    host = re.sub(r"[^a-z0-9-]", "", user.lower())[:20] + "-pc"
    with open("/etc/hostname", "w") as f:
        f.write(host + "\n")
    with open("/etc/hosts", "w") as f:
        f.write("127.0.0.1\tlocalhost\n127.0.1.1\t%s\n::1\tlocalhost ip6-localhost ip6-loopback\n" % host)
    subprocess.run(["hostname", host])
    remember_session(user)
    os.unlink(MARK)


# sddm lists wayland sessions first and would pick one (xfce's isn't ready): the edition's own session is the
# last one used, so it's the one that starts
def remember_session(user):
    try:
        name = open("/etc/chamesle/session").read().strip()
    except OSError:
        return
    for d in ("/usr/share/xsessions", "/usr/share/wayland-sessions"):
        path = "%s/%s.desktop" % (d, name)
        if os.path.exists(path) and os.path.isdir("/var/lib/sddm"):
            with open("/var/lib/sddm/state.conf", "w") as f:
                f.write("[Last]\nSession=%s\nUser=%s\n" % (path, user))
            subprocess.run(["chown", "sddm:sddm", "/var/lib/sddm/state.conf"], stderr=subprocess.DEVNULL)
            return
