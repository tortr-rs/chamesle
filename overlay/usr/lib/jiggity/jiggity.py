#!/usr/bin/python3
# jiggity - the chamesle installer
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

sys.path.insert(0, "/usr/lib/jiggity")
import disks
import install
import ui

LANGUAGES = [
    ("English (United States)", "en_US"), ("English (United Kingdom)", "en_GB"), ("Français", "fr_FR"),
    ("Deutsch", "de_DE"), ("Español", "es_ES"), ("Español (México)", "es_MX"), ("Italiano", "it_IT"),
    ("Português (Brasil)", "pt_BR"), ("Português", "pt_PT"), ("Nederlands", "nl_NL"), ("Polski", "pl_PL"),
    ("Türkçe", "tr_TR"), ("Русский", "ru_RU"), ("Українська", "uk_UA"), ("العربية", "ar_MA"), ("العربية (مصر)", "ar_EG"),
    ("Svenska", "sv_SE"), ("Norsk bokmål", "nb_NO"), ("Dansk", "da_DK"), ("Suomi", "fi_FI"), ("Čeština", "cs_CZ"),
    ("Magyar", "hu_HU"), ("Română", "ro_RO"), ("Ελληνικά", "el_GR"), ("日本語", "ja_JP"), ("한국어", "ko_KR"),
    ("中文 (简体)", "zh_CN"), ("中文 (繁體)", "zh_TW"), ("हिन्दी", "hi_IN"), ("Bahasa Indonesia", "id_ID"),
    ("Tiếng Việt", "vi_VN"),
]
STEPS = ["Getting the drive ready", "Copying files", "Getting files ready for installation",
         "Installing the boot menu", "Finishing up"]


def keyboards():
    out, section = [], None
    try:
        lines = open("/usr/share/X11/xkb/rules/base.lst").read().splitlines()
    except OSError:
        return [("English (US)", "us", "")]
    for line in lines:
        if line.startswith("!"):
            section = line[1:].strip()
            continue
        if not line.strip():
            continue
        name, desc = line.split(None, 1)
        if section == "layout":
            out.append((desc.strip(), name, ""))
        elif section == "variant":
            layout, desc = desc.split(":", 1)
            out.append((desc.strip(), layout, name))
    return sorted(out, key=lambda k: k[0].lower())


class Jiggity(ui.SetupWindow):
    def __init__(self):
        super().__init__("Chamesle Setup")
        self.rows = []
        self.pages = [self.page_language(), self.page_start(), self.page_where(), self.page_installing(), self.page_done()]
        self.show_page(0)

    # language and keyboard
    def page_language(self):
        box = ui.page("", "")
        box.pack_start(ui.logo_line("Chamesle"), False, False, 12)
        grid = Gtk.Grid(column_spacing=16, row_spacing=14, halign=Gtk.Align.CENTER, margin_top=24)
        self.language = Gtk.ComboBoxText()
        for name, code in LANGUAGES:
            self.language.append(code, name)
        self.language.set_active_id("en_US")
        self.keyboard = Gtk.ComboBoxText()
        self.kbds = keyboards()
        for i, (desc, layout, variant) in enumerate(self.kbds):
            self.keyboard.append(str(i), desc)
            if layout == "us" and not variant:
                self.keyboard.set_active(i)
        self.keyboard.connect("changed", self.on_keyboard)
        for r, (text, w) in enumerate([("Language to install:", self.language), ("Keyboard or input method:", self.keyboard)]):
            l = Gtk.Label(label=text, xalign=1)
            grid.attach(l, 0, r, 1, 1)
            w.set_size_request(320, -1)
            grid.attach(w, 1, r, 1, 1)
        box.pack_start(grid, False, False, 0)
        hint = Gtk.Label(label="Enter your language and other preferences and click \"Next\" to continue.", margin_top=40)
        hint.get_style_context().add_class("dim")
        box.pack_start(hint, False, False, 0)
        return box, [("Next", lambda *a: self.show_page(1))]

    def on_keyboard(self, combo):
        desc, layout, variant = self.kbds[int(combo.get_active_id())]
        subprocess.run(["setxkbmap", layout] + (["-variant", variant] if variant else []))

    # install now
    def page_start(self):
        box = ui.page("", "")
        box.pack_start(ui.logo_line("Chamesle"), False, False, 40)
        button = Gtk.Button(label="Install now", halign=Gtk.Align.CENTER)
        button.get_style_context().add_class("big")
        button.connect("clicked", lambda *a: self.show_page(2))
        box.pack_start(button, False, False, 0)
        return box, [("Back", lambda *a: self.show_page(0))]

    # where
    def page_where(self):
        box = ui.page("Where do you want to install Chamesle?", "")
        self.store = Gtk.ListStore(str, str, str, str, bool, int)
        view = Gtk.TreeView(model=self.store, headers_visible=True)
        for i, (title, xalign) in enumerate([("Name", 0), ("Total size", 1), ("Free space", 1), ("Type", 0)]):
            cell = Gtk.CellRendererText(xalign=xalign)
            col = Gtk.TreeViewColumn(title, cell, text=i, sensitive=4)
            col.set_expand(i == 0)
            view.append_column(col)
        self.selection = view.get_selection()
        self.selection.set_select_function(lambda sel, model, path, selected: model[path][4])
        self.selection.connect("changed", self.on_where)
        scroll = Gtk.ScrolledWindow(min_content_height=220)
        scroll.add(view)
        scroll.get_style_context().add_class("table")
        box.pack_start(scroll, True, True, 0)
        tools = Gtk.Box(spacing=18, margin_top=6)
        refresh = Gtk.LinkButton(label="Refresh", uri="")
        refresh.connect("activate-link", lambda *a: self.fill_where() or True)
        tools.pack_start(refresh, False, False, 0)
        box.pack_start(tools, False, False, 0)
        self.where_note = Gtk.Label(xalign=0, wrap=True, margin_top=6)
        self.where_note.get_style_context().add_class("note")
        box.pack_start(self.where_note, False, False, 0)
        self.encrypt = Gtk.CheckButton(label="Encrypt Chamesle with a passphrase", margin_top=10)
        box.pack_start(self.encrypt, False, False, 0)
        self.pass_grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin_start=28, no_show_all=True)
        self.pass1 = Gtk.Entry(visibility=False, width_chars=28)
        self.pass2 = Gtk.Entry(visibility=False, width_chars=28)
        for r, (text, e) in enumerate([("Passphrase:", self.pass1), ("Confirm:", self.pass2)]):
            self.pass_grid.attach(Gtk.Label(label=text, xalign=1), 0, r, 1, 1)
            self.pass_grid.attach(e, 1, r, 1, 1)
            e.connect("changed", self.on_where)
        warn = Gtk.Label(label="You type it every time the computer starts. If you forget it, your files can't be "
                               "recovered.", xalign=0, wrap=True, max_width_chars=60)
        warn.get_style_context().add_class("note")
        self.pass_grid.attach(warn, 0, 2, 2, 1)
        box.pack_start(self.pass_grid, False, False, 0)
        self.encrypt.connect("toggled", self.on_encrypt)
        return box, [("Next", self.on_install), ("Back", lambda *a: self.show_page(1))]

    def fill_where(self):
        self.store.clear()
        self.rows = disks.scan()
        for i, r in enumerate(self.rows):
            name = r.label if r.kind == "drive" else "    " + r.label
            free = disks.size_text(r.free) if r.kind != "drive" else ""
            self.store.append([name, disks.size_text(r.total), free, r.type_text, r.usable, i])
        if not self.rows:
            self.where_note.set_text("No drives were found. Check that the drive is connected, then click Refresh.")
        self.on_where()

    def on_encrypt(self, check):
        self.pass_grid.set_visible(check.get_active())
        if check.get_active():
            self.pass_grid.show_all()
        self.on_where()

    def chosen(self):
        model, it = self.selection.get_selected()
        return self.rows[model[it][5]] if it else None

    def on_where(self, *a):
        row = self.chosen()
        ok = row is not None
        if row is None:
            if self.rows:
                self.where_note.set_text("Pick a drive (to use all of it) or its unallocated space (to keep what's on "
                                         "the drive). Chamesle needs at least %s." % disks.size_text(disks.MIN_SIZE))
        elif row.kind == "drive":
            self.where_note.set_text("Everything on %s will be erased." % row.label.split(":")[0])
        else:
            self.where_note.set_text("Chamesle goes in the unallocated space. Nothing else on the drive changes. "
                                     "When the computer starts, you choose between Chamesle and what's already there.")
        if self.encrypt.get_active():
            p1, p2 = self.pass1.get_text(), self.pass2.get_text()
            ok = ok and len(p1) >= 8 and p1 == p2
            if p1 and len(p1) < 8:
                self.where_note.set_text("The passphrase needs at least 8 characters.")
            elif p2 and p1 != p2:
                self.where_note.set_text("The passphrases don't match.")
        self.set_button_sensitive("Next", ok)

    def on_install(self, *a):
        row = self.chosen()
        if row.kind == "drive":
            if not ui.confirm(self, "Erase %s?" % row.label.split(":")[0],
                              "Everything on this drive will be deleted, and Chamesle will be installed on it. "
                              "This can't be undone."):
                return
        passphrase = self.pass1.get_text() if self.encrypt.get_active() else None
        language = self.language.get_active_id()
        desc, layout, variant = self.kbds[int(self.keyboard.get_active_id())]
        self.show_page(3)
        threading.Thread(target=self.run_install, args=(row, passphrase, language, (layout, variant)), daemon=True).start()

    # installing
    def page_installing(self):
        box = ui.page("Installing Chamesle", "")
        box.pack_start(Gtk.Label(label="Status", xalign=0, margin_top=10), False, False, 0)
        self.step_labels = []
        for s in STEPS:
            l = Gtk.Label(label=s, xalign=0, margin_start=12, margin_top=6)
            l.get_style_context().add_class("step")
            box.pack_start(l, False, False, 0)
            self.step_labels.append(l)
        return box, []

    def progress(self, step, percent):
        def show():
            for i, l in enumerate(self.step_labels):
                ctx = l.get_style_context()
                ctx.remove_class("now")
                if i < step or (i == step and percent >= 100):
                    l.set_text("✓  " + STEPS[i])
                    ctx.add_class("done")
                elif i == step:
                    l.set_text("      " + STEPS[i] + (" (%d%%)" % percent if i == 1 else "..."))
                    ctx.add_class("now")
                else:
                    l.set_text("      " + STEPS[i])
        GLib.idle_add(show)

    def run_install(self, *args):
        try:
            install.install(*args, progress=self.progress)
        except Exception as e:
            print("jiggity: the installation failed:", e)
            GLib.idle_add(self.failed, str(e))
            return
        GLib.idle_add(self.show_page, 4)
        GLib.idle_add(self.countdown, 10)

    def failed(self, why):
        ui.message(self, "Chamesle couldn't be installed",
                   "%s\n\nThe details are in /var/log/jiggity.log. Click OK to restart." % why)
        subprocess.run(["reboot"])

    # restart
    def page_done(self):
        box = ui.page("Chamesle needs to restart to continue", "")
        self.count_label = Gtk.Label(xalign=0, margin_top=20)
        box.pack_start(self.count_label, False, False, 0)
        note = Gtk.Label(label="Take out the USB stick when the screen goes dark. After the restart you'll set up "
                               "your account.", xalign=0, wrap=True, margin_top=12)
        note.get_style_context().add_class("dim")
        box.pack_start(note, False, False, 0)
        return box, [("Restart now", lambda *a: subprocess.run(["reboot"]))]

    def countdown(self, n):
        self.count_label.set_text("Restarting in %d seconds" % n)
        if n == 0:
            subprocess.run(["reboot"])
            return False
        GLib.timeout_add_seconds(1, self.countdown, n - 1)
        return False

    def show_page(self, n):
        super().show_page(n)
        if n == 2:
            self.fill_where()


if __name__ == "__main__":
    Jiggity()
    Gtk.main()
