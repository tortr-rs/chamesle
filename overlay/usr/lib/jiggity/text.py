#!/usr/bin/python3
# jiggity in text, for editions without a desktop: blue like windows setup used to be
#   text.py install      from the usb's Install entry. on the netinst it asks everything, then installs
#   text.py firstboot    the first start: time zone, network, account
import curses
import locale
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, "/usr/lib/jiggity")
import account
import disks
import install
from choices import LANGUAGES, STEPS, keyboards

scr = None
# the console font has latin letters only: these languages by their english names
ENGLISH = {"ru_RU": "Russian", "uk_UA": "Ukrainian", "el_GR": "Greek", "ar_MA": "Arabic", "ar_EG": "Arabic (Egypt)",
           "hi_IN": "Hindi", "ja_JP": "Japanese", "ko_KR": "Korean", "zh_CN": "Chinese (Simplified)",
           "zh_TW": "Chinese (Traditional)"}


def frame(title, keys):
    scr.bkgd(" ", curses.color_pair(1))
    scr.erase()
    h, w = scr.getmaxyx()
    scr.addstr(0, 1, " Chamesle Setup", curses.A_BOLD)
    scr.hline(1, 1, curses.ACS_HLINE, w - 2)
    scr.addstr(3, 4, title[:w - 6], curses.A_BOLD)
    scr.attron(curses.color_pair(2))
    scr.hline(h - 1, 0, " ", w)
    scr.addstr(h - 1, 2, keys[:w - 4])
    scr.attroff(curses.color_pair(2))


def text(y, s):
    h, w = scr.getmaxyx()
    words, line = s.split(), ""
    for word in words:
        if len(line) + len(word) + 1 > w - 10:
            scr.addstr(y, 4, line)
            y, line = y + 1, ""
        line = (line + " " + word).strip()
    if line:
        scr.addstr(y, 4, line)
    return y + 2


# a list to pick from. type to jump. returns the index, or None for esc
def choose(title, note, items, sel=0, disabled=()):
    top, typed = 0, ""
    while True:
        frame(title, "ENTER=Continue  ESC=Back  Type to search")
        y = text(5, note) if note else 5
        h, w = scr.getmaxyx()
        rows = h - y - 3
        if sel < top:
            top = sel
        if sel >= top + rows:
            top = sel - rows + 1
        for i in range(top, min(len(items), top + rows)):
            attr = curses.color_pair(3) if i == sel else curses.color_pair(1)
            if i in disabled:
                attr |= curses.A_DIM
            scr.addstr(y + i - top, 6, items[i][:w - 12].ljust(w - 12), attr)
        k = scr.get_wch()
        if k in ("\n", curses.KEY_ENTER) and sel not in disabled:
            return sel
        if k == "\x1b":
            return None
        if k == curses.KEY_UP:
            sel = max(0, sel - 1)
        elif k == curses.KEY_DOWN:
            sel = min(len(items) - 1, sel + 1)
        elif k == curses.KEY_PPAGE:
            sel = max(0, sel - rows)
        elif k == curses.KEY_NPAGE:
            sel = min(len(items) - 1, sel + rows)
        elif isinstance(k, str) and k.isprintable():
            typed += k.lower()
            for i, it in enumerate(items):
                if typed in it.lower():
                    sel = i
                    break
            else:
                typed = k.lower()
        elif k in (curses.KEY_BACKSPACE, "\x7f"):
            typed = typed[:-1]


# a line of input. returns the text, or None for esc
def ask(title, note, label, secret=False, value=""):
    curses.curs_set(1)
    while True:
        frame(title, "ENTER=Continue  ESC=Back")
        y = text(5, note) if note else 5
        scr.addstr(y, 4, label)
        x = 6 + len(label)
        shown = "*" * len(value) if secret else value
        scr.addstr(y, x, shown.ljust(32), curses.color_pair(4))
        scr.move(y, x + len(shown))
        k = scr.get_wch()
        if k in ("\n", curses.KEY_ENTER):
            curses.curs_set(0)
            return value
        if k == "\x1b":
            curses.curs_set(0)
            return None
        if k in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            value = value[:-1]
        elif isinstance(k, str) and k.isprintable() and len(value) < 64:
            value += k


def say(title, note, keys="ENTER=Continue"):
    frame(title, keys)
    text(5, note)
    scr.refresh()
    return scr.get_wch()


def yes(title, note):
    while True:
        k = say(title, note, "Y=Yes  N=No")
        if k in ("y", "Y"):
            return True
        if k in ("n", "N", "\x1b"):
            return False


def netinst():
    try:
        return open("/usr/share/chamesle/edition").read().strip() == "netinst"
    except OSError:
        return False


# what the netinst offers: the editions, the way the website lists them
DESKTOPS = [
    ("xfce", "Light and quick, set up like Windows. The one to start with."),
    ("mate", "Very light and rock solid, for older machines."),
    ("cinnamon", "Linux Mint's desktop, the most polished Windows-style one."),
    ("gnome", "Modern and clean, with an overview of your windows and a dock."),
    ("kde", "Familiar at first, and you can change almost anything about it."),
    ("astro", "GNOME with the sky apps: Stellarium, KStars, Siril and Gpredict."),
    ("ranni", "KDE Plasma set up to feel like a Mac."),
    ("play", "KDE Plasma for games, with Steam, GameMode and controllers."),
    ("tty", "The console, with floating windows on top, on ttywm."),
    ("server", "No desktop. SSH is on from the first start."),
]


def edition_name(e):
    try:
        for line in open("/usr/share/chamesle/editions/%s/edition" % e):
            if line.startswith("name="):
                return line[5:].strip()
    except OSError:
        pass
    return e


def nm(*args):
    return subprocess.run(["nmcli"] + list(args), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def wifi_list():
    r = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    seen, out = set(), []
    for line in r.stdout.splitlines():
        f = re.split(r"(?<!\\):", line)
        if len(f) < 3 or not f[0] or f[0] in seen:
            continue
        seen.add(f[0])
        out.append((f[0].replace("\\:", ":"), int(f[1] or 0), f[2]))
    return sorted(out, key=lambda n: -n[1])


# online by cable, or by the wi-fi picked here. False for esc
def network():
    while True:
        frame("Connecting to the internet", "")
        text(5, "Looking for a connection...")
        scr.refresh()
        for _ in range(10):
            if account.online():
                say("Connected", "Chamesle is online, so it can download the desktop you pick.")
                return True
            time.sleep(0.5)
        nets = wifi_list()
        items = ["%-40s %3d%%%s" % (n[:40], sig, "  locked" if sec else "") for n, sig, sec in nets]
        items += ["Look again", "I plugged in a cable"]
        i = choose("Connecting to the internet", "Chamesle downloads your desktop while it installs, so it needs the "
                   "internet. Plug in a cable, or pick your Wi-Fi.", items)
        if i is None:
            return False
        if i >= len(nets):
            continue
        ssid, sig, sec = nets[i]
        cmd = ["device", "wifi", "connect", ssid]
        if sec:
            pw = ask("Connecting to %s" % ssid, "", "Wi-Fi password:", True)
            if pw is None:
                continue
            cmd += ["password", pw]
        frame("Connecting to %s" % ssid, "")
        text(5, "Connecting...")
        scr.refresh()
        if nm(*cmd).returncode:
            say("Couldn't connect to %s" % ssid, "Check the password and try again.")


def run_netinst():
    kbds = keyboards()
    us = next((i for i, k in enumerate(kbds) if k[1] == "us" and not k[2]), 0)
    zs = account.zones()
    zone_names = [z.replace("_", " ").replace("/", " / ") for z in zs]
    c = {"lang": 0, "kb": us, "zone": zs.index("Europe/London") if "Europe/London" in zs else 0, "name": "",
         "user": "", "pw": "", "host": "", "row": None, "passphrase": None, "desktop": 0}

    def p_lang():
        i = choose("Language to install", "", [ENGLISH.get(code, n) for n, code in LANGUAGES], c["lang"])
        if i is None:
            return False
        c["lang"] = i
        return True

    def p_keyboard():
        i = choose("Keyboard", "", [k[0] for k in kbds], c["kb"])
        if i is None:
            return False
        c["kb"] = i
        layout, variant = kbds[i][1:]
        subprocess.run(["loadkeys", layout + ("-" + variant if variant else "")], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return True

    def p_zone():
        i = choose("Your time zone", "It sets your clock. Type a city to find yours.", zone_names, c["zone"])
        if i is None:
            return False
        c["zone"] = i
        return True

    def p_you():
        name = ask("Who's going to use this PC?", "", "Your name:", value=c["name"])
        if name is None:
            return False
        while True:
            user = ask("Who's going to use this PC?", "Lowercase letters and numbers, starting with a letter.",
                       "Username:", value=c["user"] or account.username_from(name))
            if user is None:
                return False
            bad = account.bad_username(user)
            if user and not bad:
                break
            say("Who's going to use this PC?", bad or "Pick a username.")
        while True:
            pw = ask("Who's going to use this PC?", "", "Password:", True)
            if pw is None:
                return False
            if not pw:
                continue
            if ask("Who's going to use this PC?", "Type it again.", "Confirm:  ", True) == pw:
                break
            say("Who's going to use this PC?", "The passwords don't match.")
        while True:
            host = ask("Name this computer", "How it shows up to other computers on the network.",
                       "Computer name:", value=c["host"] or account.hostname_from(user))
            if host is None:
                return False
            bad = account.bad_hostname(host)
            if not bad:
                break
            say("Name this computer", bad)
        c.update(name=name, user=user, pw=pw, host=host)
        return True

    def p_disk():
        while True:
            rows = disks.scan()
            if not rows:
                say("No drives found", "Check that the drive is connected, then press ENTER to look again.")
                continue
            items = []
            for r in rows:
                free = "  %s free" % disks.size_text(r.free) if r.kind != "drive" else ""
                items.append("%s%-40s %9s%s  %s" % ("" if r.kind == "drive" else "  ", r.label[:40],
                                                  disks.size_text(r.total), free, r.type_text))
            off = [i for i, r in enumerate(rows) if not r.usable]
            first = next((i for i in range(len(rows)) if i not in off), 0)
            i = choose("Where do you want to install Chamesle?",
                       "Pick a drive to use all of it, or its unallocated space to keep what's on it. Chamesle needs "
                       "at least %s. Nothing changes until the last step." % disks.size_text(disks.MIN_SIZE),
                       items, first, off)
            if i is None:
                return False
            c["row"] = rows[i]
            break
        c["passphrase"] = None
        if yes("Encrypt Chamesle?", "With a passphrase you type every time the computer starts. If you forget it, "
                                    "your files can't be recovered."):
            while True:
                p1 = ask("Encrypt Chamesle", "At least 8 characters.", "Passphrase:", True)
                if p1 is None:
                    break
                if len(p1) < 8:
                    say("Encrypt Chamesle", "The passphrase needs at least 8 characters.")
                    continue
                if ask("Encrypt Chamesle", "Type it again.", "Confirm:   ", True) != p1:
                    say("Encrypt Chamesle", "The passphrases don't match.")
                    continue
                c["passphrase"] = p1
                break
        return True

    def p_desktop():
        items = ["%-12s %s" % (edition_name(e), d) for e, d in DESKTOPS]
        i = choose("Pick your desktop", "You can add another one later with: sudo chamesle-desktop NAME", items,
                   c["desktop"])
        if i is None:
            return False
        c["desktop"] = i
        return True

    def p_summary():
        row = c["row"]
        where = ("all of %s (everything on it is erased)" % row.label.split(":")[0] if row.kind == "drive"
                 else "the unallocated space on %s" % row.label.split(":")[0])
        lines = [("Language", ENGLISH.get(LANGUAGES[c["lang"]][1], LANGUAGES[c["lang"]][0])),
                 ("Keyboard", kbds[c["kb"]][0]), ("Time zone", zone_names[c["zone"]]),
                 ("You", "%s (%s)" % (c["name"] or c["user"], c["user"])), ("Computer name", c["host"]),
                 ("Install on", where), ("Encrypted", "yes" if c["passphrase"] else "no"),
                 ("Desktop", edition_name(DESKTOPS[c["desktop"]][0]))]
        while True:
            frame("Ready to install", "ENTER=Install  ESC=Back")
            y = text(5, "Check this. When you press ENTER, Chamesle installs and the disk is changed. It needs nothing "
                        "more from you until it's done.")
            for k, v in lines:
                scr.addstr(y, 6, "%-15s %s" % (k + ":", v))
                y += 1
            scr.refresh()
            k = scr.get_wch()
            if k in ("\n", curses.KEY_ENTER):
                return True
            if k == "\x1b":
                return False

    pages = [p_lang, p_keyboard, network, p_zone, p_you, p_disk, p_desktop, p_summary]
    n = 0
    while n < len(pages):
        if pages[n]():
            n += 1
        else:
            n = max(0, n - 1)

    desktop = DESKTOPS[c["desktop"]][0]
    user = {"zone": zs[c["zone"]], "user": c["user"], "name": c["name"], "password": c["pw"], "host": c["host"]}
    steps = STEPS[:2] + ["Downloading and installing %s" % edition_name(desktop)] + STEPS[2:]
    work(steps, c["row"], c["passphrase"], LANGUAGES[c["lang"]][1], kbds[c["kb"]][1:], desktop, user)
    say("Chamesle is installed", "Take out the USB stick, then press ENTER to restart into your new %s desktop."
        % edition_name(desktop) if desktop != "server" else
        "Take out the USB stick, then press ENTER to restart. Sign in with your username, or over SSH.")
    subprocess.run(["reboot"])


# installs with a screen of steps. returns when it's done, or says what went wrong and restarts
def work(steps, row, passphrase, language, keyboard, desktop=None, user=None):
    state = {"step": 0, "percent": 0, "error": None, "done": False}

    def go():
        try:
            install.install(row, passphrase, language, keyboard, progress=progress, desktop=desktop, user=user)
        except Exception as e:
            print("jiggity: the installation failed:", e, file=sys.stderr)
            state["error"] = str(e)
        state["done"] = True

    def progress(step, percent):
        state["step"], state["percent"] = step, percent

    threading.Thread(target=go, daemon=True).start()
    scr.timeout(500)
    while not state["done"]:
        frame("Installing Chamesle", "Please wait")
        for i, s in enumerate(steps):
            if i < state["step"] or (i == state["step"] and state["percent"] >= 100):
                line = "[x] " + s
            elif i == state["step"]:
                line = "[ ] " + s + (" (%d%%)" % state["percent"] if s.startswith(("Copying", "Downloading")) else "...")
            else:
                line = "[ ] " + s
            scr.addstr(6 + i, 6, line, curses.A_BOLD if i == state["step"] else 0)
        scr.refresh()
        try:
            scr.get_wch()
        except curses.error:
            pass
    scr.timeout(-1)
    if state["error"]:
        say("Chamesle couldn't be installed", "%s. The details are in /var/log/jiggity.log. Press ENTER to restart."
            % state["error"].rstrip("."))
        subprocess.run(["reboot"])
        sys.exit(1)


def run_install():
    if netinst():
        return run_netinst()
    lang = choose("Language to install", "", [ENGLISH.get(c, n) for n, c in LANGUAGES])
    if lang is None:
        lang = 0
    kbds = keyboards()
    us = next((i for i, k in enumerate(kbds) if k[1] == "us" and not k[2]), 0)
    kb = choose("Keyboard", "", [k[0] for k in kbds], us)
    if kb is None:
        kb = us
    while True:
        rows = disks.scan()
        if not rows:
            say("No drives found", "Check that the drive is connected, then press ENTER to look again.")
            continue
        items = []
        for r in rows:
            free = "  %s free" % disks.size_text(r.free) if r.kind != "drive" else ""
            items.append("%s%-40s %9s%s  %s" % ("" if r.kind == "drive" else "  ", r.label[:40],
                                              disks.size_text(r.total), free, r.type_text))
        off = [i for i, r in enumerate(rows) if not r.usable]
        first = next((i for i in range(len(rows)) if i not in off), 0)
        i = choose("Where do you want to install Chamesle?",
                   "Pick a drive to use all of it, or its unallocated space to keep what's on it. Chamesle needs at "
                   "least %s." % disks.size_text(disks.MIN_SIZE), items, first, off)
        if i is None:
            continue
        row = rows[i]
        if row.kind == "drive" and not yes("Erase %s?" % row.label.split(":")[0],
                                           "Everything on this drive will be deleted, and Chamesle will be installed "
                                           "on it. This can't be undone."):
            continue
        break
    passphrase = None
    if yes("Encrypt Chamesle?", "With a passphrase you type every time the computer starts. If you forget it, your "
                                "files can't be recovered."):
        while True:
            p1 = ask("Encrypt Chamesle", "At least 8 characters.", "Passphrase:", True)
            if p1 is None:
                break
            if len(p1) < 8:
                say("Encrypt Chamesle", "The passphrase needs at least 8 characters.")
                continue
            if ask("Encrypt Chamesle", "Type it again.", "Confirm:   ", True) != p1:
                say("Encrypt Chamesle", "The passphrases don't match.")
                continue
            passphrase = p1
            break

    work(STEPS, row, passphrase, LANGUAGES[lang][1], kbds[kb][1:])
    say("Chamesle needs to restart to continue", "Take out the USB stick when the screen goes dark. After the "
                                                 "restart you'll set up your account. Press ENTER to restart.")
    subprocess.run(["reboot"])


def run_firstboot():
    zs = account.zones()
    names = [z.replace("_", " ").replace("/", " / ") for z in zs]
    while True:
        z = choose("Let's start with your time zone", "It sets your clock. Type a city to find yours.", names)
        if z is not None:
            break
    if not account.online() and yes("Not connected", "You need the internet for updates. Set up a network now?"):
        curses.endwin()
        subprocess.run(["nmtui-connect"])
        scr.refresh()
    while True:
        name = ask("Who's going to use this PC?", "", "Your name:") or ""
        user = ask("Who's going to use this PC?", "Lowercase letters and numbers, starting with a letter.",
                   "Username:", value=account.username_from(name))
        if not user:
            continue
        bad = account.bad_username(user)
        if bad:
            say("Who's going to use this PC?", bad)
            continue
        pw = ask("Who's going to use this PC?", "", "Password:", True)
        if not pw:
            continue
        if ask("Who's going to use this PC?", "Type it again.", "Confirm:  ", True) != pw:
            say("Who's going to use this PC?", "The passwords don't match.")
            continue
        break
    frame("Just a moment...", "")
    scr.refresh()
    account.make(zs[z], user, name, pw)


def main(s):
    global scr
    scr = s
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.curs_set(0)
    scr.keypad(True)
    if sys.argv[1:2] == ["install"]:
        run_install()
    else:
        run_firstboot()


if __name__ == "__main__":
    # what the install prints goes to the log, not over the screen
    log = open("/var/log/jiggity.log", "a", buffering=1)
    os.dup2(log.fileno(), 2)
    sys.stdout = sys.stderr = log
    locale.setlocale(locale.LC_ALL, "")
    curses.set_escdelay(25)
    curses.wrapper(main)
