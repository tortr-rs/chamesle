# torrent
VERSION = 0.1
PREFIX = /usr/local

PKGS = wlroots-0.19 wayland-server xkbcommon pixman-1 cairo dbus-1 libinput libdrm
PROTO = `pkg-config --variable=pkgdatadir wayland-protocols`
SCANNER = `pkg-config --variable=wayland_scanner wayland-scanner`
CFLAGS += -std=c11 -Wall -Os -D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L -DWLR_USE_UNSTABLE -DVERSION=\"$(VERSION)\" \
	-I. `pkg-config --cflags $(PKGS)`
LDLIBS += `pkg-config --libs $(PKGS)` -lpam
HDRS = xdg-shell-protocol.h cursor-shape-v1-protocol.h wlr-layer-shell-unstable-v1-protocol.h

torrent: torrent.c $(HDRS)
	$(CC) $(CFLAGS) -o $@ torrent.c $(LDFLAGS) $(LDLIBS)

xdg-shell-protocol.h:
	$(SCANNER) server-header $(PROTO)/stable/xdg-shell/xdg-shell.xml $@
cursor-shape-v1-protocol.h:
	$(SCANNER) server-header $(PROTO)/staging/cursor-shape/cursor-shape-v1.xml $@
wlr-layer-shell-unstable-v1-protocol.h:
	$(SCANNER) server-header protocols/wlr-layer-shell-unstable-v1.xml $@

install: torrent
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	install -m 755 torrent torrent-session $(DESTDIR)$(PREFIX)/bin/
	mkdir -p $(DESTDIR)/usr/share/fonts/torrent
	install -m 644 vga.ttf $(DESTDIR)/usr/share/fonts/torrent/
	-fc-cache -f $(DESTDIR)/usr/share/fonts/torrent
	mkdir -p $(DESTDIR)/usr/share/wayland-sessions
	sed 's|@PREFIX@|$(PREFIX)|' torrent.desktop > $(DESTDIR)/usr/share/wayland-sessions/torrent.desktop

uninstall:
	rm -rf $(DESTDIR)$(PREFIX)/bin/torrent $(DESTDIR)$(PREFIX)/bin/torrent-session $(DESTDIR)/usr/share/fonts/torrent \
	      $(DESTDIR)/usr/share/wayland-sessions/torrent.desktop

clean:
	rm -f torrent $(HDRS)

.PHONY: install uninstall clean
