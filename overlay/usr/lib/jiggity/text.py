#!/usr/bin/python3
# jiggity in text, for editions without a desktop: blue like windows setup used to be
#   text.py install      from the usb's Install entry
#   text.py firstboot    the first start: time zone, network, account
import curses
import os
import subprocess
import sys
import threading

sys.path.insert(0, "/usr/lib/jiggity")
import account
import disks
import install
from choices import LANGUAGES, STEPS, keyboards

scr = None


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


def run_install():
    lang = choose("Language to install", "", [n for n, c in LANGUAGES])
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

    state = {"step": 0, "percent": 0, "error": None, "done": False}

    def work():
        try:
            install.install(row, passphrase, LANGUAGES[lang][1], kbds[kb][1:], progress=progress)
        except Exception as e:
            print("jiggity: the installation failed:", e, file=sys.stderr)
            state["error"] = str(e)
        state["done"] = True

    def progress(step, percent):
        state["step"], state["percent"] = step, percent

    threading.Thread(target=work, daemon=True).start()
    scr.timeout(500)
    while not state["done"]:
        frame("Installing Chamesle", "Please wait")
        for i, s in enumerate(STEPS):
            if i < state["step"] or (i == state["step"] and state["percent"] >= 100):
                line = "[x] " + s
            elif i == state["step"]:
                line = "[ ] " + s + (" (%d%%)" % state["percent"] if i == 1 else "...")
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
    else:
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
    curses.set_escdelay(25)
    curses.wrapper(main)
