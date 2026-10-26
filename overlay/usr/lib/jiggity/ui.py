# shared by jiggity and firstboot. runs without a window manager
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

CSS = b"""
* { font-family: Inter, "Noto Sans", sans-serif; }
window.setup { background: linear-gradient(160deg, #0f1a2e 0%, #17407f 55%, #1f5fc4 100%); }
.dialog { background: #ffffff; color: #1a1f2b; border-radius: 6px; box-shadow: 0 12px 40px rgba(0,0,0,.45); }
.titlebar { background: #f3f4f6; border-bottom: 1px solid #e3e6eb; border-radius: 6px 6px 0 0; padding: 8px 14px; }
.titlebar label { font-size: 13px; color: #1a1f2b; }
.heading { font-size: 20px; font-weight: 600; color: #174c9f; }
.dim { color: #5d6677; }
.note { color: #5d6677; font-size: 13px; }
.brand { font-size: 34px; font-weight: 300; color: #1a1f2b; }
.footer { border-top: 1px solid #e3e6eb; padding: 12px 16px; }
button { padding: 6px 22px; border-radius: 4px; }
button.big { padding: 14px 40px; font-size: 17px; background: #1f5fc4; color: #ffffff; border: none; }
button.big:hover { background: #174c9f; }
.step { font-size: 15px; color: #5d6677; }
.step.now { color: #1a1f2b; font-weight: 600; }
.step.done { color: #1a1f2b; }
.table { border: 1px solid #c9ced6; }
treeview.view:selected { background: #cce0ff; color: #1a1f2b; }
treeview.view:disabled { color: #9aa1ad; }
entry { min-height: 30px; }
"""


def page(title, text):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=28)
    if title:
        h = Gtk.Label(label=title, xalign=0, wrap=True)
        h.get_style_context().add_class("heading")
        box.pack_start(h, False, False, 0)
    if text:
        t = Gtk.Label(label=text, xalign=0, wrap=True)
        t.get_style_context().add_class("dim")
        box.pack_start(t, False, False, 0)
    return box


def logo_line(name):
    row = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER)
    row.pack_start(Gtk.Image.new_from_icon_name("chamesle-start", Gtk.IconSize.DIALOG), False, False, 0)
    l = Gtk.Label(label=name)
    l.get_style_context().add_class("brand")
    row.pack_start(l, False, False, 0)
    return row


class SetupWindow(Gtk.Window):
    # pages: [(box, [(label, callback), ...])], first button is the default
    def __init__(self, title):
        super().__init__()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-theme-name", "Adwaita")
        settings.set_property("gtk-application-prefer-dark-theme", False)
        self.get_style_context().add_class("setup")
        self.set_decorated(False)
        screen = Gdk.Screen.get_default()
        mon = screen.get_display().get_primary_monitor() or screen.get_display().get_monitor(0)
        geo = mon.get_geometry()
        self.move(geo.x, geo.y)
        self.set_default_size(geo.width, geo.height)
        self.connect("delete-event", lambda *a: True)

        outer = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        dialog = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dialog.get_style_context().add_class("dialog")
        dialog.set_size_request(min(800, geo.width - 40), min(560, geo.height - 40))
        bar = Gtk.Box(spacing=8)
        bar.get_style_context().add_class("titlebar")
        bar.pack_start(Gtk.Image.new_from_icon_name("chamesle-start", Gtk.IconSize.MENU), False, False, 0)
        bar.pack_start(Gtk.Label(label=title), False, False, 0)
        dialog.pack_start(bar, False, False, 0)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        dialog.pack_start(self.stack, True, True, 0)
        self.buttons = Gtk.Box(spacing=10, halign=Gtk.Align.END)
        footer = Gtk.Box()
        footer.get_style_context().add_class("footer")
        footer.pack_end(self.buttons, False, False, 0)
        dialog.pack_start(footer, False, False, 0)
        outer.add(dialog)
        self.add(outer)
        self.show_all()
        self.button_widgets = {}
        # no wm, so nobody sets a cursor on the root window
        cursor = Gdk.Cursor.new_from_name(screen.get_display(), "default")
        screen.get_root_window().set_cursor(cursor)
        self.get_window().set_cursor(cursor)

    def show_page(self, n):
        box, buttons = self.pages[n]
        if box.get_parent() is None:
            self.stack.add_named(box, str(n))
            box.show_all()
        self.stack.set_visible_child_name(str(n))
        for child in self.buttons.get_children():
            self.buttons.remove(child)
        self.button_widgets = {}
        for i, (label, callback) in reversed(list(enumerate(buttons))):
            b = Gtk.Button(label=label)
            b.connect("clicked", callback)
            if i == 0:
                b.get_style_context().add_class("suggested-action")
            self.buttons.pack_start(b, False, False, 0)
            self.button_widgets[label] = b
        self.buttons.show_all()
        self.buttons.get_parent().set_visible(bool(buttons))

    def set_button_sensitive(self, label, on):
        if label in self.button_widgets:
            self.button_widgets[label].set_sensitive(on)


def _dialog(parent, title, text, buttons):
    d = Gtk.Dialog(transient_for=parent, modal=True, decorated=False)
    d.get_style_context().add_class("dialog")
    box = d.get_content_area()
    box.set_spacing(10)
    box.set_margin_top(20), box.set_margin_start(24), box.set_margin_end(24), box.set_margin_bottom(10)
    h = Gtk.Label(label=title, xalign=0)
    h.get_style_context().add_class("heading")
    box.pack_start(h, False, False, 0)
    box.pack_start(Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=52), False, False, 0)
    for label, response in buttons:
        d.add_button(label, response)
    d.set_default_response(buttons[-1][1])
    d.show_all()
    pw, ph = parent.get_size()
    w, h_ = d.get_size()
    d.move((pw - w) // 2, (ph - h_) // 2)
    r = d.run()
    d.destroy()
    return r


def confirm(parent, title, text):
    return _dialog(parent, title, text, [("Cancel", Gtk.ResponseType.CANCEL), ("OK", Gtk.ResponseType.OK)]) == Gtk.ResponseType.OK


def message(parent, title, text):
    _dialog(parent, title, text, [("OK", Gtk.ResponseType.OK)])
