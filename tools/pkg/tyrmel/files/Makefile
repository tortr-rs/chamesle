# tyrmel
VERSION = 0.1
PREFIX = /usr/local

PKGS = x11 xft xrender fontconfig vterm libpng zlib
CFLAGS += -std=c99 -Wall -Os -D_DEFAULT_SOURCE -D_GNU_SOURCE -DVERSION=\"$(VERSION)\" `pkg-config --cflags $(PKGS)`
LDLIBS += `pkg-config --libs $(PKGS)` -lutil

tyrmel: tyrmel.c
	$(CC) $(CFLAGS) -o $@ tyrmel.c $(LDFLAGS) $(LDLIBS)

install: tyrmel
	mkdir -p $(DESTDIR)$(PREFIX)/bin $(DESTDIR)/usr/share/applications $(DESTDIR)/usr/share/fonts/tyrmel
	install -m 755 tyrmel $(DESTDIR)$(PREFIX)/bin/
	install -m 644 vga.ttf $(DESTDIR)/usr/share/fonts/tyrmel/
	sed 's|@PREFIX@|$(PREFIX)|' tyrmel.desktop > $(DESTDIR)/usr/share/applications/tyrmel.desktop

uninstall:
	rm -rf $(DESTDIR)$(PREFIX)/bin/tyrmel $(DESTDIR)/usr/share/fonts/tyrmel $(DESTDIR)/usr/share/applications/tyrmel.desktop

clean:
	rm -f tyrmel

.PHONY: install uninstall clean
