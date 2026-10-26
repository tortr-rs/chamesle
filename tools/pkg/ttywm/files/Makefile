# ttywm
VERSION = 0.6
PREFIX = /usr/local

PKGS = x11 xft fontconfig dbus-1
CFLAGS += -std=c99 -pedantic -Wall -Os -D_DEFAULT_SOURCE -DVERSION=\"$(VERSION)\" `pkg-config --cflags $(PKGS)`
LDLIBS += `pkg-config --libs $(PKGS)` -lpam

all: ttywm ttywmbg

ttywm: ttywm.c
	$(CC) $(CFLAGS) -o $@ ttywm.c $(LDFLAGS) $(LDLIBS)

ttywmbg: ttywmbg.c
	$(CC) -std=c99 -Wall -Os -D_DEFAULT_SOURCE `pkg-config --cflags x11 libpng` -o $@ ttywmbg.c $(LDFLAGS) `pkg-config --libs x11 libpng` -ljpeg

install: ttywm ttywmbg
	@[ -n "$(DESTDIR)" ] || command -v tyrmel >/dev/null || { echo "ttywm needs tyrmel: install it first"; exit 1; }
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	install -m 755 ttywm ttywmbg ttywm-term ttywm-session $(DESTDIR)$(PREFIX)/bin/
	mkdir -p $(DESTDIR)/usr/share/fonts/ttywm
	install -m 644 vga.ttf $(DESTDIR)/usr/share/fonts/ttywm/
	-fc-cache -f $(DESTDIR)/usr/share/fonts/ttywm
	mkdir -p $(DESTDIR)/usr/share/xsessions
	sed 's|@PREFIX@|$(PREFIX)|' ttywm.desktop > $(DESTDIR)/usr/share/xsessions/ttywm.desktop

uninstall:
	rm -rf $(DESTDIR)$(PREFIX)/bin/ttywm $(DESTDIR)$(PREFIX)/bin/ttywmbg $(DESTDIR)$(PREFIX)/bin/ttywm-term $(DESTDIR)$(PREFIX)/bin/ttywm-session $(DESTDIR)/usr/share/fonts/ttywm \
	      $(DESTDIR)/usr/share/xsessions/ttywm.desktop

# fbttywm: the same on the framebuffer, without X. needs nothing but a libc
fbttywm: fbttywm.c
	$(CC) -O2 -Wall -o $@ fbttywm.c

install-fb: fbttywm
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	install -m 755 fbttywm $(DESTDIR)$(PREFIX)/bin/

uninstall-fb:
	rm -f $(DESTDIR)$(PREFIX)/bin/fbttywm

clean:
	rm -f ttywm ttywmbg fbttywm

.PHONY: all install uninstall install-fb uninstall-fb clean
