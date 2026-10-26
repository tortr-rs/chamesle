#!/usr/bin/python3
# first boot setup: time zone, wi-fi, user account
import re
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

sys.path.insert(0, "/usr/lib/jiggity")
import account
import ui
from account import zones, online


class FirstBoot(ui.SetupWindow):
    def __init__(self):
        super().__init__("Chamesle")
        self.pages = [self.page_zone(), self.page_wifi(), self.page_account(), self.page_wait()]
        self.show_page(0)

    # time zone
    def page_zone(self):
        box = ui.page("Let's start with your time zone. Is this the right one?",
                      "It sets your clock. Type a city to find yours.")
        self.zone_filter = Gtk.SearchEntry(margin_top=10)
        box.pack_start(self.zone_filter, False, False, 0)
        self.zone_store = Gtk.ListStore(str, str)
        for z in zones():
            self.zone_store.append([z.replace("_", " ").replace("/", " / "), z])
        filt = self.zone_store.filter_new()
        filt.set_visible_func(lambda m, it, d: self.zone_filter.get_text().lower() in m[it][0].lower())
        self.zone_filter.connect("search-changed", lambda *a: filt.refilter())
        view = Gtk.TreeView(model=filt, headers_visible=False)
        view.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=0))
        self.zone_sel = view.get_selection()
        self.zone_sel.connect("changed", lambda s: self.set_button_sensitive("Yes", s.get_selected()[1] is not None))
        scroll = Gtk.ScrolledWindow(min_content_height=260)
        scroll.add(view)
        scroll.get_style_context().add_class("table")
        box.pack_start(scroll, True, True, 6)
        return box, [("Yes", self.after_zone)]

    def after_zone(self, *a):
        model, it = self.zone_sel.get_selected()
        self.zone = model[it][1]
        self.show_page(2 if online() else 1)

    # wi-fi
    def page_wifi(self):
        box = ui.page("Let's connect you to a network", "You need the internet for updates and the app store.")
        self.wifi_store = Gtk.ListStore(str, str, str)
        view = Gtk.TreeView(model=self.wifi_store, headers_visible=False)
        view.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=0))
        view.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(xalign=1), text=1))
        self.wifi_sel = view.get_selection()
        self.wifi_sel.connect("changed", self.on_wifi)
        scroll = Gtk.ScrolledWindow(min_content_height=200, margin_top=10)
        scroll.add(view)
        scroll.get_style_context().add_class("table")
        box.pack_start(scroll, True, True, 0)
        row = Gtk.Box(spacing=10, margin_top=8)
        row.pack_start(Gtk.Label(label="Password:"), False, False, 0)
        self.wifi_pass = Gtk.Entry(visibility=False, width_chars=28)
        row.pack_start(self.wifi_pass, False, False, 0)
        box.pack_start(row, False, False, 0)
        self.wifi_note = Gtk.Label(xalign=0, wrap=True)
        self.wifi_note.get_style_context().add_class("note")
        box.pack_start(self.wifi_note, False, False, 0)
        return box, [("Connect", self.on_connect), ("Skip for now", lambda *a: self.show_page(2))]

    def fill_wifi(self):
        self.wifi_store.clear()
        r = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        seen = set()
        for line in r.stdout.splitlines():
            f = re.split(r"(?<!\\):", line)
            if len(f) < 3 or not f[0] or f[0] in seen:
                continue
            seen.add(f[0])
            self.wifi_store.append([f[0].replace("\\:", ":"), "%s%%%s" % (f[1], "  \U0001F512" if f[2] else ""), f[2]])
        self.wifi_note.set_text("" if len(self.wifi_store) else "No Wi-Fi networks found. You can skip this and connect later.")
        self.on_wifi()

    def on_wifi(self, *a):
        self.set_button_sensitive("Connect", self.wifi_sel.get_selected()[1] is not None)

    def on_connect(self, *a):
        model, it = self.wifi_sel.get_selected()
        ssid, secure = model[it][0], model[it][2]
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if secure:
            cmd += ["password", self.wifi_pass.get_text()]
        self.wifi_note.set_text("Connecting to %s..." % ssid)

        def go():
            ok = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            GLib.idle_add(lambda: self.show_page(2) if ok else
                          self.wifi_note.set_text("Couldn't connect to %s. Check the password and try again." % ssid))
        threading.Thread(target=go, daemon=True).start()

    # the account
    def page_account(self):
        box = ui.page("Who's going to use this PC?", "")
        grid = Gtk.Grid(column_spacing=12, row_spacing=10, margin_top=14)
        self.name = Gtk.Entry(width_chars=30, placeholder_text="Your name")
        self.user = Gtk.Entry(width_chars=30)
        self.pw1 = Gtk.Entry(width_chars=30, visibility=False)
        self.pw2 = Gtk.Entry(width_chars=30, visibility=False)
        for r, (text, e) in enumerate([("Name:", self.name), ("Username:", self.user), ("Password:", self.pw1),
                                       ("Confirm password:", self.pw2)]):
            grid.attach(Gtk.Label(label=text, xalign=1), 0, r, 1, 1)
            grid.attach(e, 1, r, 1, 1)
            e.connect("changed", self.on_account)
        self.user_edited = False
        self.user.connect("key-press-event", lambda *a: setattr(self, "user_edited", True))
        box.pack_start(grid, False, False, 0)
        self.account_note = Gtk.Label(xalign=0, wrap=True, margin_top=10)
        self.account_note.get_style_context().add_class("note")
        box.pack_start(self.account_note, False, False, 0)
        return box, [("Next", self.on_done), ("Back", lambda *a: self.show_page(0))]

    def on_account(self, entry):
        if entry is self.name and not self.user_edited:
            self.user.set_text(account.username_from(self.name.get_text()))
        u, p1, p2 = self.user.get_text(), self.pw1.get_text(), self.pw2.get_text()
        note = account.bad_username(u)
        ok = not note
        if ok and p2 and p1 != p2:
            note, ok = "The passwords don't match.", False
        self.account_note.set_text(note)
        self.set_button_sensitive("Next", ok and bool(u and p1 and p1 == p2))

    def on_done(self, *a):
        self.show_page(3)
        threading.Thread(target=self.make_account, daemon=True).start()

    # just a moment
    def page_wait(self):
        box = ui.page("Just a moment...", "")
        spinner = Gtk.Spinner(margin_top=40, halign=Gtk.Align.CENTER)
        spinner.set_size_request(48, 48)
        spinner.start()
        box.pack_start(spinner, False, False, 0)
        return box, []

    def make_account(self):
        account.make(self.zone, self.user.get_text(), self.name.get_text(), self.pw1.get_text())
        GLib.idle_add(Gtk.main_quit)

    def show_page(self, n):
        super().show_page(n)
        if n == 1:
            GLib.idle_add(self.fill_wifi)
        if n == 0:
            self.set_button_sensitive("Yes", False)
        if n == 2:
            self.set_button_sensitive("Next", False)
            self.name.grab_focus()


if __name__ == "__main__":
    FirstBoot()
    Gtk.main()
