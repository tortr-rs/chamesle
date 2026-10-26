/* tyrmel - a terminal that looks like the console and shows pictures like kitty */
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <locale.h>
#include <pty.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>
#include <X11/extensions/Xrender.h>
#include <X11/Xft/Xft.h>
#include <fontconfig/fontconfig.h>
#include <png.h>
#include <zlib.h>
#include <vterm.h>

#define LENGTH(X)       (sizeof(X) / sizeof(X)[0])
#define MIN(A, B)       ((A) < (B) ? (A) : (B))
#define MAX(A, B)       ((A) > (B) ? (A) : (B))
#define MAXIMAGES       64
#define MAXPLACES       256
#define MAXFALLBACK     32
#define MAXAPC          (256 << 20)

/* a line of the scrollback: only what's needed to draw it again */
typedef struct {
	uint32_t ch;
	uint8_t fg[3], bg[3];
	uint8_t flags, width;
} Cell;
enum { FBold = 1, FUnder = 2, FReverse = 4, FStrike = 8, FDefFg = 16, FDefBg = 32 };

typedef struct {
	int cols;
	Cell *cells;
} Line;

/* pictures sent with kitty's graphics protocol */
typedef struct {
	unsigned int id;
	int w, h;
	uint32_t *argb;	/* premultiplied */
} Image;

typedef struct {
	Image *img;
	unsigned int id, pid;
	long line;	/* counted from the top of the scrollback, so it scrolls with the text */
	int col, cols, rows, alt, z;
	int sx, sy, sw, sh;	/* the part of the image shown */
	Picture pic;
	int pw, ph;
} Place;

typedef struct {
	XftFont *font;
	FcFontSet *set;
	FcPattern *pat;
	struct { XftFont *font; uint32_t ch; } fb[MAXFALLBACK];
	int nfb;
} Fonts;

/* settings, from ~/.config/tyrmel/config */
static char fontname[256] = "VGA";
static int fontsize = 16, scrollmax = 10000, cursorshape = 1;
static char shellcmd[512], bgname[32] = "black", fgname[32] = "grey", cursorname[32] = "grey";
static char palname[16][32];

static const char defaultconfig[] =
"# tyrmel settings\n"
"# change what's after the = and save. it works straight away\n"
"\n"
"font = VGA\n"
"font size = 16\n"
"# lines you can scroll back. shift+page up, or the mouse wheel\n"
"scrollback = 10000\n"
"# block, underline or bar\n"
"cursor = block\n"
"# what runs in it. nothing means your login shell\n"
"shell =\n"
"\n"
"# colours: black blue green cyan red magenta brown grey\n"
"#          dark grey, light blue, light green, light cyan, light red, pink, yellow, white\n"
"#          or #rrggbb\n"
"background colour = black\n"
"text colour = grey\n"
"cursor colour = grey\n"
"# the 16 colours programs use, if you want others:\n"
"# colour 1 = #aa0000\n"
"\n"
"# keys: ctrl+shift+c copy, ctrl+shift+v paste, shift+insert paste the selection,\n"
"# shift+page up and down scroll, ctrl+shift+plus and minus the font size, ctrl+shift+0 back.\n"
"# ctrl+click an address to open it\n";

static const char *vgahex[16] = {
	"#000000", "#aa0000", "#00aa00", "#aa5500", "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa",
	"#555555", "#ff5555", "#55ff55", "#ffff55", "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
};

static Display *dpy;
static Window win;
static Visual *vis;
static Colormap cmap;
static int scr, depth;
static Pixmap buf;
static Picture bufpic;
static XftDraw *draw;
static GC gc;
static XIM xim;
static XIC xic;
static Atom wmdelete, xclipboard, xtargets, xutf8, xprop, netwmname, netwmpid;
static Fonts fonts;
static int cw, ch, ascent, rows = 24, cols = 80, ww, wh;
static int basesize, samewidth;	/* samewidth: the font's letters are a cell wide, so they can go in runs */

static VTerm *vt;
static VTermScreen *vs;
static VTermState *vst;
static int ptyfd = -1;
static pid_t child;

static Line *sb;	/* scrollback ring */
static int sbn, sbhead;
static long scrolled;	/* lines that ever went into the scrollback */
static int view;	/* how far back you're looking */
static int alt, cursorvisible = 1, focused = 1, mousemode;
static VTermPos cursor;
static int dirty = 1;

static Image *images[MAXIMAGES];
static int nimages;
static Place places[MAXPLACES];
static int nplaces;
static char *apc;
static size_t apclen, apcsize;
static int pendingrows, pendingcols;

/* selection, in rows counted from the top of the scrollback */
static struct { long r0, r1; int c0, c1, on, going; } sel;
static char *seltext;
static Time lastclick;
static int clicks;

static char cfgpath[1100];
static time_t cfgmtime;
static const char *wclass = "tyrmel", *wname = "tyrmel", *wtitle;
static char **cmdargv;
static int geomcols = 80, geomrows = 24, holdopen, forcesize;	/* forcesize: -fs, over the settings */

/* ---- small things ---- */

static void
die(const char *msg)
{
	fprintf(stderr, "tyrmel: %s\n", msg);
	exit(1);
}

static char *
trim(char *s)
{
	char *e;

	while (isspace((unsigned char)*s))
		s++;
	for (e = s + strlen(s); e > s && isspace((unsigned char)e[-1]); e--);
	*e = '\0';
	return s;
}

static void
squash(char *dst, const char *src, size_t n)
{
	size_t i = 0;

	for (; *src && i < n - 1; src++)
		if (!isspace((unsigned char)*src))
			dst[i++] = tolower((unsigned char)*src);
	dst[i] = '\0';
}

static int
parsecolour(const char *name, uint8_t rgb[3])
{
	static const char *names[][2] = {
		{ "black", "#000000" }, { "blue", "#0000aa" }, { "green", "#00aa00" }, { "cyan", "#00aaaa" },
		{ "red", "#aa0000" }, { "magenta", "#aa00aa" }, { "brown", "#aa5500" }, { "grey", "#aaaaaa" },
		{ "gray", "#aaaaaa" }, { "darkgrey", "#555555" }, { "darkgray", "#555555" },
		{ "lightblue", "#5555ff" }, { "lightgreen", "#55ff55" }, { "lightcyan", "#55ffff" },
		{ "lightred", "#ff5555" }, { "pink", "#ff55ff" }, { "yellow", "#ffff55" }, { "white", "#ffffff" },
	};
	char s[32];
	const char *hex = NULL;
	unsigned int i, v;

	squash(s, name, sizeof s);
	for (i = 0; i < LENGTH(names); i++)
		if (!strcmp(s, names[i][0]))
			hex = names[i][1];
	if (!hex && s[0] == '#')
		hex = s;
	if (!hex || strlen(hex) != 7 || sscanf(hex + 1, "%x", &v) != 1)
		return 0;
	rgb[0] = v >> 16, rgb[1] = v >> 8, rgb[2] = v;
	return 1;
}

static void
xcolour(const uint8_t rgb[3], XftColor *c)
{
	XRenderColor r = { rgb[0] * 257, rgb[1] * 257, rgb[2] * 257, 0xffff };

	XftColorAllocValue(dpy, vis, cmap, &r, c);
}

static void
writepty(const char *s, size_t n)
{
	ssize_t r;

	while (n > 0) {
		r = write(ptyfd, s, n);
		if (r < 0) {
			if (errno == EINTR || errno == EAGAIN)
				continue;
			return;
		}
		s += r, n -= r;
	}
}

static long
ms(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

/* ---- settings ---- */

static void
loadconfig(void)
{
	char line[1024], key[64], *name, *value, *eq;
	struct stat st;
	FILE *f;
	int i;

	if (stat(cfgpath, &st) < 0 && (f = fopen(cfgpath, "w"))) {
		fputs(defaultconfig, f);
		fclose(f);
	}
	if (stat(cfgpath, &st) == 0)
		cfgmtime = st.st_mtime;
	for (i = 0; i < 16; i++)
		palname[i][0] = '\0';
	if (!(f = fopen(cfgpath, "r")))
		return;
	while (fgets(line, sizeof line, f)) {
		if (*trim(line) == '#' || !(eq = strchr(line, '=')))
			continue;
		*eq = '\0';
		name = trim(line);
		value = trim(eq + 1);
		squash(key, name, sizeof key);
		if (!strcmp(key, "font"))
			snprintf(fontname, sizeof fontname, "%s", *value ? value : "VGA");
		else if (!strcmp(key, "fontsize"))
			fontsize = atoi(value) > 3 ? atoi(value) : 16;
		else if (!strcmp(key, "scrollback"))
			scrollmax = MAX(atoi(value), 0);
		else if (!strcmp(key, "cursor")) {
			squash(key, value, sizeof key);
			cursorshape = !strcmp(key, "underline") ? VTERM_PROP_CURSORSHAPE_UNDERLINE :
			              !strcmp(key, "bar") ? VTERM_PROP_CURSORSHAPE_BAR_LEFT : VTERM_PROP_CURSORSHAPE_BLOCK;
		} else if (!strcmp(key, "shell"))
			snprintf(shellcmd, sizeof shellcmd, "%s", value);
		else if (!strcmp(key, "backgroundcolour") || !strcmp(key, "backgroundcolor"))
			snprintf(bgname, sizeof bgname, "%s", value);
		else if (!strcmp(key, "textcolour") || !strcmp(key, "textcolor"))
			snprintf(fgname, sizeof fgname, "%s", value);
		else if (!strcmp(key, "cursorcolour") || !strcmp(key, "cursorcolor"))
			snprintf(cursorname, sizeof cursorname, "%s", value);
		else if ((!strncmp(key, "colour", 6) || !strncmp(key, "color", 5))
		     && (i = atoi(key + (key[4] == 'u' ? 6 : 5))) >= 0 && i < 16 && isdigit((unsigned char)key[key[4] == 'u' ? 6 : 5]))
			snprintf(palname[i], sizeof palname[i], "%s", value);
		else
			fprintf(stderr, "tyrmel: %s: don't know '%s'\n", cfgpath, name);
	}
	fclose(f);
}

static void
setcolours(void)
{
	VTermColor fg, bg, c;
	uint8_t rgb[3];
	int i;

	for (i = 0; i < 16; i++) {
		if (!parsecolour(palname[i][0] ? palname[i] : vgahex[i], rgb))
			parsecolour(vgahex[i], rgb);
		vterm_color_rgb(&c, rgb[0], rgb[1], rgb[2]);
		vterm_state_set_palette_color(vst, i, &c);
	}
	if (!parsecolour(fgname, rgb))
		parsecolour("grey", rgb);
	vterm_color_rgb(&fg, rgb[0], rgb[1], rgb[2]);
	if (!parsecolour(bgname, rgb))
		parsecolour("black", rgb);
	vterm_color_rgb(&bg, rgb[0], rgb[1], rgb[2]);
	vterm_screen_set_default_colors(vs, &fg, &bg);
	dirty = 1;
}

/* ---- fonts: the one you picked, and others for what it hasn't got ---- */

static void
unloadfonts(void)
{
	int i;

	for (i = 0; i < fonts.nfb; i++)
		XftFontClose(dpy, fonts.fb[i].font);
	fonts.nfb = 0;
	if (fonts.font)
		XftFontClose(dpy, fonts.font);
	if (fonts.set)
		FcFontSetDestroy(fonts.set);
	if (fonts.pat)
		FcPatternDestroy(fonts.pat);
	memset(&fonts, 0, sizeof fonts);
}

static void
loadfonts(int size)
{
	FcPattern *pat, *match;
	FcResult r;
	char name[300];

	unloadfonts();
	snprintf(name, sizeof name, "%s:pixelsize=%d", fontname, size);
	if (!(pat = FcNameParse((FcChar8 *)name)))
		die("can't read the font name");
	FcConfigSubstitute(NULL, pat, FcMatchPattern);
	XftDefaultSubstitute(dpy, scr, pat);
	if (!(match = FcFontMatch(NULL, pat, &r)) || !(fonts.font = XftFontOpenPattern(dpy, match))) {
		if (!(fonts.font = XftFontOpenName(dpy, scr, "monospace:pixelsize=16")))
			die("no font");
	}
	fonts.pat = pat;
	cw = fonts.font->max_advance_width;
	ch = fonts.font->ascent + fonts.font->descent;
	ascent = fonts.font->ascent;
	/* a monospace font's widest glyph is its cell, but some lie */
	{
		XGlyphInfo gi;

		XftTextExtentsUtf8(dpy, fonts.font, (FcChar8 *)"M", 1, &gi);
		if (gi.xOff > 0 && gi.xOff < cw)
			cw = gi.xOff;
		samewidth = gi.xOff == cw;
	}
}

static int
pua(uint32_t c)
{
	return (c >= 0xe000 && c <= 0xf8ff) || c >= 0xf0000;
}

static XftFont *
fontfor(uint32_t c)
{
	static uint32_t missing[64];
	static unsigned int nmissing;
	FcCharSet *cs;
	FcPattern *m;
	FcChar8 *mine = NULL, *fam;
	FcResult r;
	int i, pass;

	/* the private use area is icons: fonts that aren't made for them only pretend */
	if (!pua(c) && XftCharExists(dpy, fonts.font, c))
		return fonts.font;
	for (i = 0; i < fonts.nfb; i++)
		if (fonts.fb[i].ch == c || XftCharExists(dpy, fonts.fb[i].font, c))
			return fonts.fb[i].font;
	/* no font has it: don't look again every frame */
	for (i = 0; i < (int)LENGTH(missing); i++)
		if (missing[i] == c)
			return fonts.font;
	if (!fonts.set)
		fonts.set = FcFontSort(NULL, fonts.pat, 1, NULL, &r);
	/* the closest font to yours that has it, but not yours. icons from a nerd font if there is one */
	m = NULL;
	FcPatternGetString(fonts.font->pattern, FC_FAMILY, 0, &mine);
	for (pass = pua(c) ? 0 : 1; !m && pass < 2; pass++)
		for (i = 0; fonts.set && i < fonts.set->nfont; i++) {
			if (FcPatternGetCharSet(fonts.set->fonts[i], FC_CHARSET, 0, &cs) != FcResultMatch || !FcCharSetHasChar(cs, c))
				continue;
			if (FcPatternGetString(fonts.set->fonts[i], FC_FAMILY, 0, &fam) != FcResultMatch)
				continue;
			if ((mine && !strcmp((char *)fam, (char *)mine)) || (pass == 0 && !strstr((char *)fam, "Nerd")))
				continue;
			m = FcFontRenderPrepare(NULL, fonts.pat, fonts.set->fonts[i]);
			break;
		}
	if (!m) {
		missing[nmissing++ % LENGTH(missing)] = c;
		return fonts.font;
	}
	if (fonts.nfb == MAXFALLBACK) {
		XftFontClose(dpy, fonts.fb[0].font);
		memmove(fonts.fb, fonts.fb + 1, (MAXFALLBACK - 1) * sizeof fonts.fb[0]);
		fonts.nfb--;
	}
	fonts.fb[fonts.nfb].font = XftFontOpenPattern(dpy, m);
	fonts.fb[fonts.nfb].ch = c;
	if (!fonts.fb[fonts.nfb].font) {
		FcPatternDestroy(m);
		return fonts.font;
	}
	return fonts.fb[fonts.nfb++].font;
}

/* ---- the scrollback ---- */

static Line *
sbline(int i)	/* 0 is the oldest */
{
	return &sb[(sbhead + i) % scrollmax];
}

static void
tocell(const VTermScreenCell *v, Cell *c)
{
	VTermColor fg = v->fg, bg = v->bg;

	c->ch = v->chars[0];
	c->width = v->width;
	c->flags = (v->attrs.bold ? FBold : 0) | (v->attrs.underline ? FUnder : 0) |
	           (v->attrs.reverse ? FReverse : 0) | (v->attrs.strike ? FStrike : 0) |
	           (VTERM_COLOR_IS_DEFAULT_FG(&fg) ? FDefFg : 0) | (VTERM_COLOR_IS_DEFAULT_BG(&bg) ? FDefBg : 0);
	vterm_screen_convert_color_to_rgb(vs, &fg);
	vterm_screen_convert_color_to_rgb(vs, &bg);
	c->fg[0] = fg.rgb.red, c->fg[1] = fg.rgb.green, c->fg[2] = fg.rgb.blue;
	c->bg[0] = bg.rgb.red, c->bg[1] = bg.rgb.green, c->bg[2] = bg.rgb.blue;
}

static void
dropplaces(void)
{
	int i, j;

	/* pictures that went off the top of the scrollback */
	for (i = j = 0; i < nplaces; i++) {
		if (!places[i].alt && places[i].line + places[i].rows < scrolled - sbn) {
			if (places[i].pic)
				XRenderFreePicture(dpy, places[i].pic);
			continue;
		}
		places[j++] = places[i];
	}
	nplaces = j;
}

static int
sbpush(int n, const VTermScreenCell *cells, void *user)
{
	Line *l;
	int i;

	scrolled++;
	if (!scrollmax) {
		if (sel.on)
			sel.r0--, sel.r1--;
		return 1;
	}
	/* keep only up to the last thing on the line */
	while (n > 0 && !cells[n - 1].chars[0] && VTERM_COLOR_IS_DEFAULT_BG(&cells[n - 1].bg))
		n--;
	if (sbn == scrollmax) {
		l = sbline(0);
		free(l->cells);
		sbhead = (sbhead + 1) % scrollmax;
		sbn--;
		if (sel.on)
			sel.r0--, sel.r1--;
	}
	l = sbline(sbn++);
	l->cols = n;
	l->cells = n ? malloc(n * sizeof *l->cells) : NULL;
	for (i = 0; i < n; i++)
		tocell(&cells[i], &l->cells[i]);
	dropplaces();
	if (view)
		view = MIN(view + 1, sbn);
	dirty = 1;
	return 1;
}

static int
sbpop(int n, VTermScreenCell *cells, void *user)
{
	Line *l;
	int i;

	if (!sbn)
		return 0;
	l = sbline(--sbn);
	scrolled--;
	for (i = 0; i < n; i++) {
		memset(&cells[i], 0, sizeof cells[i]);
		cells[i].width = 1;
		vterm_state_get_default_colors(vst, &cells[i].fg, &cells[i].bg);
		if (i < l->cols) {
			cells[i].chars[0] = l->cells[i].ch;
			cells[i].width = l->cells[i].width ? l->cells[i].width : 1;
			cells[i].attrs.bold = !!(l->cells[i].flags & FBold);
			cells[i].attrs.underline = !!(l->cells[i].flags & FUnder);
			cells[i].attrs.reverse = !!(l->cells[i].flags & FReverse);
			if (!(l->cells[i].flags & FDefFg))
				vterm_color_rgb(&cells[i].fg, l->cells[i].fg[0], l->cells[i].fg[1], l->cells[i].fg[2]);
			if (!(l->cells[i].flags & FDefBg))
				vterm_color_rgb(&cells[i].bg, l->cells[i].bg[0], l->cells[i].bg[1], l->cells[i].bg[2]);
		}
	}
	free(l->cells);
	l->cells = NULL;
	dirty = 1;
	return 1;
}

static int
sbclear(void *user)
{
	while (sbn)
		free(sbline(--sbn)->cells);
	view = 0;
	dirty = 1;
	return 1;
}

/* row r of what's on the window, as cells. scrollback or screen */
static int
viewrow(int r, Cell *out)
{
	VTermScreenCell v;
	VTermPos p;
	Line *l;
	int c;

	if (r < view) {
		l = sbline(sbn - view + r);
		for (c = 0; c < cols; c++) {
			if (c < l->cols)
				out[c] = l->cells[c];
			else {
				memset(&out[c], 0, sizeof out[c]);
				out[c].width = 1;
				out[c].flags = FDefFg | FDefBg;
			}
		}
		return 1;
	}
	p.row = r - view;
	for (c = 0; c < cols; c++) {
		p.col = c;
		vterm_screen_get_cell(vs, p, &v);
		tocell(&v, &out[c]);
	}
	return 0;
}

/* ---- pictures ---- */

static int
unbase64(const char *s, size_t n, unsigned char *out)
{
	static signed char t[256];
	size_t i;
	int bits = 0, len = 0, v;
	unsigned int acc = 0;

	if (!t['B']) {
		memset(t, -1, sizeof t);
		for (i = 0; i < 64; i++)
			t[(unsigned char)"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[i]] = i;
	}
	for (i = 0; i < n; i++) {
		if ((v = t[(unsigned char)s[i]]) < 0)
			continue;
		acc = acc << 6 | v;
		if ((bits += 6) >= 8) {
			bits -= 8;
			out[len++] = acc >> bits;
		}
	}
	return len;
}

static void
freeimage(Image *im)
{
	int i, j;

	for (i = j = 0; i < nplaces; i++) {
		if (places[i].img == im) {
			if (places[i].pic)
				XRenderFreePicture(dpy, places[i].pic);
			continue;
		}
		places[j++] = places[i];
	}
	nplaces = j;
	for (i = j = 0; i < nimages; i++)
		if (images[i] != im)
			images[j++] = images[i];
	nimages = j;
	free(im->argb);
	free(im);
}

static Image *
findimage(unsigned int id)
{
	int i;

	for (i = 0; id && i < nimages; i++)
		if (images[i]->id == id)
			return images[i];
	return NULL;
}

static void
delplace(int i)
{
	Image *im = places[i].img;
	int j;

	if (places[i].pic)
		XRenderFreePicture(dpy, places[i].pic);
	places[i] = places[--nplaces];
	/* a picture without an id can't be shown again */
	for (j = 0; j < nplaces; j++)
		if (places[j].img == im)
			return;
	if (!im->id)
		freeimage(im);
}

static uint32_t *
loadpng(const unsigned char *data, size_t n, int *w, int *h)
{
	png_image pi;
	uint32_t *px;

	memset(&pi, 0, sizeof pi);
	pi.version = PNG_IMAGE_VERSION;
	if (!png_image_begin_read_from_memory(&pi, data, n))
		return NULL;
	pi.format = PNG_FORMAT_BGRA;
	if (!(px = malloc(PNG_IMAGE_SIZE(pi)))) {
		png_image_free(&pi);
		return NULL;
	}
	if (!png_image_finish_read(&pi, NULL, px, 0, NULL)) {
		free(px);
		return NULL;
	}
	*w = pi.width, *h = pi.height;
	return px;
}

/* the pixels the protocol sends, into premultiplied argb */
static uint32_t *
topixels(int fmt, unsigned char *data, size_t n, int *w, int *h)
{
	uint32_t *px, a, p;
	size_t i, need;
	int bpp = fmt == 24 ? 3 : 4;

	if (fmt == 100) {
		if (!(px = loadpng(data, n, w, h)))
			return NULL;
		for (i = 0; i < (size_t)*w * *h; i++) {
			p = px[i], a = p >> 24;
			px[i] = a << 24 | ((p >> 16 & 255) * a / 255) << 16 | ((p >> 8 & 255) * a / 255) << 8 | (p & 255) * a / 255;
		}
		return px;
	}
	need = (size_t)*w * *h * bpp;
	if (*w <= 0 || *h <= 0 || n < need || !(px = malloc((size_t)*w * *h * 4)))
		return NULL;
	for (i = 0; i < (size_t)*w * *h; i++) {
		a = bpp == 4 ? data[i * 4 + 3] : 255;
		px[i] = a << 24 | (data[i * bpp] * a / 255) << 16 | (data[i * bpp + 1] * a / 255) << 8 | data[i * bpp + 2] * a / 255;
	}
	return px;
}

/* the picture at the size it's shown, as an xrender picture */
static void
makepic(Place *p)
{
	Image *im = p->img;
	XImage *xi;
	Pixmap pm;
	GC pgc;
	uint32_t *px;
	int w, h, x, y, sx, sy;

	w = p->cols * cw, h = p->rows * ch;
	if (p->pic && p->pw == w && p->ph == h)
		return;
	if (p->pic)
		XRenderFreePicture(dpy, p->pic);
	p->pic = None;
	/* shrink to fit the cells it was given, keeping its shape */
	if (p->sw * h > p->sh * w)
		h = MAX(1, (long)p->sh * w / p->sw);
	else
		w = MAX(1, (long)p->sw * h / p->sh);
	if (!(px = malloc((size_t)w * h * 4)))
		return;
	for (y = 0; y < h; y++) {
		sy = p->sy + (long)y * p->sh / h;
		for (x = 0; x < w; x++) {
			sx = p->sx + (long)x * p->sw / w;
			px[y * w + x] = im->argb[sy * im->w + sx];
		}
	}
	pm = XCreatePixmap(dpy, win, w, h, 32);
	pgc = XCreateGC(dpy, pm, 0, NULL);
	xi = XCreateImage(dpy, vis, 32, ZPixmap, 0, (char *)px, w, h, 32, 0);
	XPutImage(dpy, pm, pgc, xi, 0, 0, 0, 0, w, h);
	XDestroyImage(xi);	/* frees px */
	XFreeGC(dpy, pgc);
	p->pic = XRenderCreatePicture(dpy, pm, XRenderFindStandardFormat(dpy, PictStandardARGB32), 0, NULL);
	XFreePixmap(dpy, pm);
	p->pw = p->cols * cw, p->ph = p->rows * ch;
}

static void
reply(unsigned int id, unsigned int pid, int quiet, const char *msg)
{
	char s[256];
	int n;

	if (!id || quiet >= 2 || (quiet == 1 && !strcmp(msg, "OK")))
		return;
	n = pid ? snprintf(s, sizeof s, "\033_Gi=%u,p=%u;%s\033\\", id, pid, msg)
	        : snprintf(s, sizeof s, "\033_Gi=%u;%s\033\\", id, msg);
	writepty(s, n);
}

static void
place(Image *im, unsigned int pid, int c, int r, int nomove, int z, int x, int y, int w, int h)
{
	Place *p;
	int i;

	/* the same picture and placement again replaces it */
	for (i = 0; im->id && pid && i < nplaces; i++)
		if (places[i].img == im && places[i].pid == pid) {
			delplace(i);
			break;
		}
	if (nplaces == MAXPLACES)
		delplace(0);
	p = &places[nplaces++];
	memset(p, 0, sizeof *p);
	p->img = im;
	p->id = im->id;
	p->pid = pid;
	p->sx = MIN(MAX(x, 0), im->w - 1);
	p->sy = MIN(MAX(y, 0), im->h - 1);
	p->sw = w > 0 ? MIN(w, im->w - p->sx) : im->w - p->sx;
	p->sh = h > 0 ? MIN(h, im->h - p->sy) : im->h - p->sy;
	p->cols = c > 0 ? c : (p->sw + cw - 1) / cw;
	p->rows = r > 0 ? r : (p->sh + ch - 1) / ch;
	p->alt = alt;
	p->z = z;
	p->line = (alt ? 0 : scrolled) + cursor.row;
	p->col = cursor.col;
	if (!nomove) {
		pendingrows = p->rows - 1;
		pendingcols = p->cols;
	}
	dirty = 1;
}

static void
delete(int what, unsigned int id, int x, int y)
{
	int i, all = isupper(what);
	long line;
	Image *im;

	switch (tolower(what)) {
	case 'i':
		if ((im = findimage(id))) {
			if (all)
				freeimage(im);
			else
				for (i = nplaces - 1; i >= 0; i--)
					if (places[i].img == im)
						delplace(i);
		}
		break;
	case 'c': case 'p':
		if (tolower(what) == 'c')
			x = cursor.col + 1, y = cursor.row + 1;
		line = (alt ? 0 : scrolled) + y - 1;
		for (i = nplaces - 1; i >= 0; i--)
			if (places[i].alt == alt && line >= places[i].line && line < places[i].line + places[i].rows
			&& x - 1 >= places[i].col && x - 1 < places[i].col + places[i].cols)
				delplace(i);
		break;
	default:
		/* everything on the screen */
		for (i = nplaces - 1; i >= 0; i--)
			if (places[i].alt == alt && places[i].line + places[i].rows > (alt ? 0 : scrolled))
				delplace(i);
		if (all)
			for (i = nimages - 1; i >= 0; i--) {
				int j, used = 0;

				for (j = 0; j < nplaces; j++)
					used |= places[j].img == images[i];
				if (!used)
					freeimage(images[i]);
			}
		break;
	}
	dirty = 1;
}

/* ESC _ G key=value,... ; base64 ESC \ */
static void
graphics(char *s, size_t n)
{
	static struct { unsigned int id, pid; int fmt, w, h, comp, quiet, c, r, nomove, z, x, y, sw, sh; char act, medium; } k;
	static int more;
	static unsigned char *data;
	static size_t datalen;
	char *payload, *kv, *e, *v;
	unsigned char *raw;
	size_t plen, rawlen;
	uLongf zlen;
	Image *im;
	uint32_t *px;
	char path[PATH_MAX];
	FILE *f;
	struct stat st;
	int len, i;

	payload = memchr(s, ';', n);
	plen = payload ? n - (payload - s) - 1 : 0;
	if (payload)
		*payload++ = '\0';
	else
		s[n] = '\0';
	if (!more) {
		memset(&k, 0, sizeof k);
		k.act = 't', k.medium = 'd', k.fmt = 32;
		free(data);
		data = NULL, datalen = 0;
	}
	more = 0;
	for (kv = s + 1; kv && *kv; kv = e) {
		if ((e = strchr(kv, ',')))
			*e++ = '\0';
		if (!(v = strchr(kv, '=')))
			continue;
		*v++ = '\0';
		switch (*kv) {
		case 'a': k.act = *v; break;
		case 't': k.medium = *v; break;
		case 'f': k.fmt = atoi(v); break;
		case 'o': k.comp = *v; break;
		case 'i': k.id = strtoul(v, NULL, 10); break;
		case 'p': k.pid = strtoul(v, NULL, 10); break;
		case 's': k.w = atoi(v); break;
		case 'v': k.h = atoi(v); break;
		case 'c': k.c = atoi(v); break;
		case 'r': k.r = atoi(v); break;
		case 'C': k.nomove = atoi(v); break;
		case 'z': k.z = atoi(v); break;
		case 'x': k.x = atoi(v); break;
		case 'y': k.y = atoi(v); break;
		case 'w': k.sw = atoi(v); break;
		case 'h': k.sh = atoi(v); break;
		case 'q': k.quiet = atoi(v); break;
		case 'm': more = atoi(v); break;
		case 'd': k.medium = *v; break;	/* for a=d, what to delete */
		}
	}
	if (k.act == 'd') {
		more = 0;
		delete(k.medium == 'd' ? 'a' : k.medium, k.id, k.x, k.y);
		return;
	}
	if (k.act == 'p') {
		if (!(im = findimage(k.id)))
			reply(k.id, k.pid, k.quiet, "ENOENT:no such image");
		else {
			place(im, k.pid, k.c, k.r, k.nomove, k.z, k.x, k.y, k.sw, k.sh);
			reply(k.id, k.pid, k.quiet, "OK");
		}
		return;
	}
	/* the picture's bytes, maybe in pieces */
	if (plen && datalen + plen < MAXAPC) {
		data = realloc(data, datalen + plen);
		memcpy(data + datalen, payload, plen);
		datalen += plen;
	}
	if (more)
		return;
	raw = malloc(datalen * 3 / 4 + 4);
	rawlen = raw ? unbase64((char *)data, datalen, raw) : 0;
	free(data);
	data = NULL, datalen = 0;
	if (k.medium == 'f' || k.medium == 't') {
		/* a file's name instead of the picture */
		len = MIN(rawlen, sizeof path - 1);
		memcpy(path, raw, len);
		path[len] = '\0';
		free(raw);
		raw = NULL, rawlen = 0;
		if (stat(path, &st) == 0 && S_ISREG(st.st_mode) && st.st_size < MAXAPC && (f = fopen(path, "rb"))) {
			raw = malloc(st.st_size + 1);
			rawlen = raw ? fread(raw, 1, st.st_size, f) : 0;
			fclose(f);
		}
		if (k.medium == 't' && strstr(path, "tty-graphics-protocol"))
			unlink(path);
	} else if (k.medium != 'd') {
		free(raw);
		reply(k.id, k.pid, k.quiet, "EINVAL:only direct and file");
		return;
	}
	if (k.comp == 'z' && raw && k.fmt != 100) {
		zlen = (uLongf)k.w * k.h * (k.fmt == 24 ? 3 : 4);
		unsigned char *z = malloc(zlen);

		if (!z || uncompress(z, &zlen, raw, rawlen) != Z_OK) {
			free(z);
			free(raw);
			reply(k.id, k.pid, k.quiet, "EINVAL:bad zlib data");
			return;
		}
		free(raw);
		raw = z, rawlen = zlen;
	}
	if (k.act == 'q') {
		/* is anyone there: yes */
		free(raw);
		reply(k.id, k.pid, k.quiet, "OK");
		return;
	}
	px = raw ? topixels(k.fmt, raw, rawlen, &k.w, &k.h) : NULL;
	free(raw);
	if (!px) {
		reply(k.id, k.pid, k.quiet, "EBADPNG:can't read the picture");
		return;
	}
	if ((im = findimage(k.id)))
		freeimage(im);
	if (nimages == MAXIMAGES) {
		/* the oldest one that isn't on the screen goes */
		for (i = 0; i < nimages; i++) {
			int j, used = 0;

			for (j = 0; j < nplaces; j++)
				used |= places[j].img == images[i];
			if (!used)
				break;
		}
		freeimage(images[i < nimages ? i : 0]);
	}
	im = calloc(1, sizeof *im);
	im->id = k.id, im->w = k.w, im->h = k.h, im->argb = px;
	images[nimages++] = im;
	if (k.act == 'T')
		place(im, k.pid, k.c, k.r, k.nomove, k.z, k.x, k.y, k.sw, k.sh);
	reply(k.id, k.pid, k.quiet, "OK");
}

static int
onapc(VTermStringFragment frag, void *user)
{
	if (frag.initial)
		apclen = 0;
	if (apclen + frag.len + 1 > apcsize && apclen + frag.len < MAXAPC) {
		apcsize = (apclen + frag.len + 1) * 2;
		apc = realloc(apc, apcsize);
	}
	if (apclen + frag.len + 1 <= apcsize) {
		memcpy(apc + apclen, frag.str, frag.len);
		apclen += frag.len;
	}
	if (frag.final && apclen && apc[0] == 'G') {
		apc[apclen] = '\0';
		graphics(apc, apclen);
	}
	return 1;
}

/* what libvterm doesn't answer: the window's size in pixels, and who we are */
static int
oncsi(const char *leader, const long args[], int argc, const char *intermed, char cmd, void *user)
{
	char s[64];
	int n = 0;

	if (cmd == 't' && !leader && argc > 0) {
		if (CSI_ARG(args[0]) == 14)
			n = snprintf(s, sizeof s, "\033[4;%d;%dt", rows * ch, cols * cw);
		else if (CSI_ARG(args[0]) == 16)
			n = snprintf(s, sizeof s, "\033[6;%d;%dt", ch, cw);
		else if (CSI_ARG(args[0]) == 18)
			n = snprintf(s, sizeof s, "\033[8;%d;%dt", rows, cols);
	} else if (cmd == 'q' && leader && leader[0] == '>')
		n = snprintf(s, sizeof s, "\033P>|tyrmel " VERSION "\033\\");
	if (n)
		writepty(s, n);
	return n > 0;
}

static VTermStateFallbacks fallbacks = { .csi = oncsi, .apc = onapc };

/* ---- libvterm tells us what changed ---- */

static int
ondamage(VTermRect r, void *user)
{
	dirty = 1;
	return 1;
}

static int
onmovecursor(VTermPos pos, VTermPos old, int visible, void *user)
{
	cursor = pos;
	dirty = 1;
	return 1;
}

static int
onprop(VTermProp prop, VTermValue *val, void *user)
{
	static char title[1024];
	static size_t tlen;
	XTextProperty tp;
	char *t = title;
	int i;

	switch (prop) {
	case VTERM_PROP_TITLE:
		if (val->string.initial)
			tlen = 0;
		if (tlen + val->string.len < sizeof title) {
			memcpy(title + tlen, val->string.str, val->string.len);
			tlen += val->string.len;
		}
		title[tlen] = '\0';
		if (val->string.final && !wtitle) {
			Xutf8TextListToTextProperty(dpy, &t, 1, XUTF8StringStyle, &tp);
			XSetWMName(dpy, win, &tp);
			XFree(tp.value);
			XChangeProperty(dpy, win, netwmname, xutf8, 8, PropModeReplace, (unsigned char *)title, tlen);
		}
		break;
	case VTERM_PROP_ALTSCREEN:
		alt = val->boolean;
		/* pictures on the screen a program was using go with it */
		for (i = nplaces - 1; i >= 0; i--)
			if (places[i].alt)
				delplace(i);
		view = 0;
		dirty = 1;
		break;
	case VTERM_PROP_CURSORVISIBLE:
		cursorvisible = val->boolean;
		dirty = 1;
		break;
	case VTERM_PROP_CURSORSHAPE:
		cursorshape = val->number;
		dirty = 1;
		break;
	case VTERM_PROP_MOUSE:
		mousemode = val->number;
		break;
	default:
		break;
	}
	return 1;
}

static int
onbell(void *user)
{
	XWMHints *h = XGetWMHints(dpy, win);

	if (!focused && h) {
		h->flags |= XUrgencyHint;
		XSetWMHints(dpy, win, h);
	}
	if (h)
		XFree(h);
	return 1;
}

static VTermScreenCallbacks screencb = {
	.damage = ondamage,
	.movecursor = onmovecursor,
	.settermprop = onprop,
	.bell = onbell,
	.sb_pushline = sbpush,
	.sb_popline = sbpop,
	.sb_clear = sbclear,
};

static void
ontermoutput(const char *s, size_t n, void *user)
{
	writepty(s, n);
}

/* ---- drawing ---- */

static int
selected(long r, int c)
{
	long a0 = sel.r0, a1 = sel.r1;
	int b0 = sel.c0, b1 = sel.c1;

	if (!sel.on)
		return 0;
	if (a0 > a1 || (a0 == a1 && b0 > b1)) {
		long t = a0; a0 = a1; a1 = t;
		int u = b0; b0 = b1; b1 = u;
	}
	if (r < a0 || r > a1)
		return 0;
	if (r == a0 && c < b0)
		return 0;
	if (r == a1 && c > b1)
		return 0;
	return 1;
}

static void
drawimages(int under)
{
	long top = (alt ? 0 : scrolled) - view;
	int i, x, y;

	for (i = 0; i < nplaces; i++) {
		if (places[i].alt != alt || (places[i].z < 0) != under)
			continue;
		y = (places[i].line - top) * ch;
		x = places[i].col * cw;
		if (y >= rows * ch || y + places[i].rows * ch <= 0)
			continue;
		makepic(&places[i]);
		if (places[i].pic)
			XRenderComposite(dpy, PictOpOver, places[i].pic, None, bufpic, 0, 0, 0, 0, x, y,
			                 places[i].cols * cw, places[i].rows * ch);
	}
}

/* letters of one colour and font next to each other go in one call */
static void
flushrun(FcChar8 *run, int *len, XftFont *f, XftColor *c, int x, int y)
{
	if (*len)
		XftDrawStringUtf8(draw, c, f, x, y, run, *len);
	*len = 0;
}

static void
redraw(void)
{
	static Cell *grid;
	static int gridsize;
	static FcChar8 run[4096];
	int runlen = 0, runx = 0;
	XftFont *runf = NULL;
	uint8_t runrgb[3] = { 0 };
	const uint8_t *rgb;
	Cell *row;
	XftColor fg, bg, cc;
	uint8_t crgb[3], dfg[3], dbg[3];
	XftFont *f;
	FcChar8 u[8];
	Cell *c;
	int r, x, len, isfg, rev;
	long vr;

	if (gridsize < rows * cols) {
		grid = realloc(grid, rows * cols * sizeof *grid);
		gridsize = rows * cols;
	}
	for (r = 0; r < rows; r++)
		viewrow(r, grid + r * cols);
	if (!parsecolour(fgname, dfg))
		parsecolour("grey", dfg);
	if (!parsecolour(bgname, dbg))
		parsecolour("black", dbg);
	xcolour(dbg, &bg);
	XftDrawRect(draw, &bg, 0, 0, ww, wh);
	/* backgrounds first, then pictures under the text, the text, and pictures over it */
	for (r = 0; r < rows; r++) {
		row = grid + r * cols;
		vr = (long)sbn - view + r;
		for (x = 0; x < cols; x++) {
			c = &row[x];
			rev = !!(c->flags & FReverse) ^ selected(vr, x);
			if (!rev && (c->flags & FDefBg))
				continue;
			xcolour(rev ? (c->flags & FDefFg ? dfg : c->fg) : c->bg, &bg);
			XftDrawRect(draw, &bg, x * cw, r * ch, cw * MAX(c->width, 1), ch);
		}
	}
	drawimages(1);
	for (r = 0; r < rows; r++) {
		row = grid + r * cols;
		vr = (long)sbn - view + r;
		for (x = 0; x < cols; x++) {
			c = &row[x];
			if (!c->ch || c->ch == ' ' || c->ch == (uint32_t)-1) {
				flushrun(run, &runlen, runf, &fg, runx, r * ch + ascent);
				continue;
			}
			rev = !!(c->flags & FReverse) ^ selected(vr, x);
			isfg = !(c->flags & FDefFg);
			rgb = rev ? (c->flags & FDefBg ? dbg : c->bg) : isfg ? c->fg : dfg;
			f = fontfor(c->ch);
			/* a new run when the colour or font changes, or after a wide letter */
			if (runlen && (f != runf || memcmp(rgb, runrgb, 3) || runlen > (int)sizeof run - 8))
				flushrun(run, &runlen, runf, &fg, runx, r * ch + ascent);
			if (!runlen) {
				xcolour(rgb, &fg);
				memcpy(runrgb, rgb, 3);
				runf = f;
				runx = x * cw;
			}
			len = FcUcs4ToUtf8(c->ch, u);
			memcpy(run + runlen, u, len);
			runlen += len;
			if (f != fonts.font || c->width != 1 || !samewidth)
				flushrun(run, &runlen, runf, &fg, runx, r * ch + ascent);
			if (c->flags & FUnder)
				XftDrawRect(draw, &fg, x * cw, r * ch + ascent + 1, cw * MAX(c->width, 1), 1);
			if (c->flags & FStrike)
				XftDrawRect(draw, &fg, x * cw, r * ch + ch / 2, cw * MAX(c->width, 1), 1);
		}
		flushrun(run, &runlen, runf, &fg, runx, r * ch + ascent);
	}
	drawimages(0);
	/* the cursor */
	if (cursorvisible && !view) {
		if (!parsecolour(cursorname, crgb))
			parsecolour("grey", crgb);
		xcolour(crgb, &cc);
		x = cursor.col * cw, r = cursor.row * ch;
		if (!focused) {
			XftDrawRect(draw, &cc, x, r, cw, 1);
			XftDrawRect(draw, &cc, x, r + ch - 1, cw, 1);
			XftDrawRect(draw, &cc, x, r, 1, ch);
			XftDrawRect(draw, &cc, x + cw - 1, r, 1, ch);
		} else if (cursorshape == VTERM_PROP_CURSORSHAPE_UNDERLINE)
			XftDrawRect(draw, &cc, x, r + ch - 2, cw, 2);
		else if (cursorshape == VTERM_PROP_CURSORSHAPE_BAR_LEFT)
			XftDrawRect(draw, &cc, x, r, 2, ch);
		else {
			/* the letter under it, in the background colour */
			XftDrawRect(draw, &cc, x, r, cw, ch);
			c = &grid[cursor.row * cols + cursor.col];
			if (c->ch && c->ch != ' ' && c->ch != (uint32_t)-1) {
				xcolour(dbg, &bg);
				len = FcUcs4ToUtf8(c->ch, u);
				XftDrawStringUtf8(draw, &bg, fontfor(c->ch), x, r + ascent, u, len);
			}
		}
	}
	/* where you are in the scrollback */
	if (view) {
		char s[32];

		snprintf(s, sizeof s, " %d/%d ", view, sbn);
		xcolour(dfg, &fg);
		len = strlen(s);
		XftDrawRect(draw, &fg, ww - len * cw, 0, len * cw, ch);
		xcolour(dbg, &bg);
		XftDrawStringUtf8(draw, &bg, fonts.font, ww - len * cw, ascent, (FcChar8 *)s, len);
	}
	XCopyArea(dpy, buf, win, gc, 0, 0, ww, wh, 0, 0);
	dirty = 0;
}

/* ---- the window ---- */

static void
setsizehints(void)
{
	XSizeHints *h = XAllocSizeHints();

	h->flags = PResizeInc | PBaseSize | PMinSize;
	h->width_inc = cw, h->height_inc = ch;
	h->base_width = h->base_height = 0;
	h->min_width = cw * 2, h->min_height = ch;
	XSetWMNormalHints(dpy, win, h);
	XFree(h);
}

static void
resize(int w, int h)
{
	struct winsize ws;
	int c = MAX(w / cw, 1), r = MAX(h / ch, 1);

	if (w != ww || h != wh || !buf) {
		ww = w, wh = h;
		if (draw)
			XftDrawDestroy(draw);
		if (bufpic)
			XRenderFreePicture(dpy, bufpic);
		if (buf)
			XFreePixmap(dpy, buf);
		buf = XCreatePixmap(dpy, win, ww, wh, depth);
		draw = XftDrawCreate(dpy, buf, vis, cmap);
		bufpic = XRenderCreatePicture(dpy, buf, XRenderFindVisualFormat(dpy, vis), 0, NULL);
	}
	if (c != cols || r != rows) {
		cols = c, rows = r;
		vterm_set_size(vt, rows, cols);
		vterm_screen_flush_damage(vs);
	}
	ws.ws_col = cols, ws.ws_row = rows;
	ws.ws_xpixel = cols * cw, ws.ws_ypixel = rows * ch;
	if (ptyfd >= 0)
		ioctl(ptyfd, TIOCSWINSZ, &ws);
	dirty = 1;
}

static void
zoom(int size)
{
	int i;

	if (size < 6 || size > 96)
		return;
	fontsize = size;
	loadfonts(size);
	for (i = 0; i < nplaces; i++)
		places[i].pw = 0;
	setsizehints();
	resize(ww, wh);
}

/* ---- copy and paste ---- */

static char *
gettext(long r0, int c0, long r1, int c1)
{
	static Cell *row;
	static int rowsize;
	size_t n = 0, size = 256;
	char *s = malloc(size);
	Line *l;
	long r;
	int c, end, last, m;

	if (rowsize < cols) {
		row = realloc(row, cols * sizeof *row);
		rowsize = cols;
	}
	for (r = r0; r <= r1; r++) {
		if (r < 0 || r >= sbn + rows)
			continue;
		if (r < sbn) {
			l = sbline(r);
			end = l->cols;
			for (c = 0; c < end && c < cols; c++)
				row[c] = l->cells[c];
			end = MIN(end, cols);
		} else {
			int sv = view;

			view = 0;
			viewrow(r - sbn, row);
			view = sv;
			end = cols;
		}
		/* no spaces at the end of lines */
		for (last = end; last > 0 && (!row[last - 1].ch || row[last - 1].ch == ' '); last--);
		for (c = r == r0 ? c0 : 0; c < last && (r != r1 || c <= c1); c++) {
			if (n + 8 >= size)
				s = realloc(s, size *= 2);
			if (row[c].width == 0 && c > 0 && row[c - 1].width == 2)
				continue;
			m = FcUcs4ToUtf8(row[c].ch && row[c].ch != (uint32_t)-1 ? row[c].ch : ' ', (FcChar8 *)s + n);
			n += m;
		}
		if (r != r1) {
			if (n + 2 >= size)
				s = realloc(s, size *= 2);
			s[n++] = '\n';
		}
	}
	s[n] = '\0';
	return s;
}

static void
own(Atom which)
{
	long r0 = sel.r0, r1 = sel.r1;
	int c0 = sel.c0, c1 = sel.c1;

	if (r0 > r1 || (r0 == r1 && c0 > c1)) {
		long t = r0; r0 = r1; r1 = t;
		int u = c0; c0 = c1; c1 = u;
	}
	free(seltext);
	seltext = gettext(r0, c0, r1, c1);
	XSetSelectionOwner(dpy, which, win, CurrentTime);
}

static void
selectionrequest(XSelectionRequestEvent *e)
{
	XSelectionEvent ev = { SelectionNotify };
	Atom targets[] = { xtargets, xutf8, XA_STRING };

	ev.requestor = e->requestor;
	ev.selection = e->selection;
	ev.target = e->target;
	ev.time = e->time;
	ev.property = e->property ? e->property : e->target;
	if (e->target == xtargets)
		XChangeProperty(dpy, e->requestor, ev.property, XA_ATOM, 32, PropModeReplace,
		                (unsigned char *)targets, LENGTH(targets));
	else if ((e->target == xutf8 || e->target == XA_STRING) && seltext)
		XChangeProperty(dpy, e->requestor, ev.property, e->target, 8, PropModeReplace,
		                (unsigned char *)seltext, strlen(seltext));
	else
		ev.property = None;
	XSendEvent(dpy, e->requestor, False, 0, (XEvent *)&ev);
}

static void
paste(Atom which)
{
	XConvertSelection(dpy, which, xutf8, xprop, win, CurrentTime);
}

static void
selectionnotify(XSelectionEvent *e)
{
	unsigned char *data;
	unsigned long n, after;
	Atom type;
	int fmt;
	unsigned long i;

	if (e->property == None)
		return;
	if (XGetWindowProperty(dpy, win, e->property, 0, 1 << 20, True, AnyPropertyType, &type, &fmt,
	    &n, &after, &data) != Success)
		return;
	/* new lines are enter keys */
	for (i = 0; i < n; i++)
		if (data[i] == '\n')
			data[i] = '\r';
	vterm_keyboard_start_paste(vt);
	writepty((char *)data, n);
	vterm_keyboard_end_paste(vt);
	XFree(data);
	view = 0;
	dirty = 1;
}

/* ctrl+click: the address under the mouse, opened */
static void
openurl(long r, int c)
{
	static const char *starts[] = { "https://", "http://", "file://", "ftp://" };
	char *line, *p, *q, *url = NULL, cmd[4200];
	unsigned int i;
	int pos = 0, at;

	line = gettext(r, 0, r, cols);
	/* the byte where the click was */
	for (p = line, at = 0; *p && at < c; p++)
		if ((*p & 0xc0) != 0x80)
			at++;
	pos = p - line;
	for (i = 0; i < LENGTH(starts); i++)
		for (p = line; (p = strstr(p, starts[i])); p++) {
			for (q = p; *q && !isspace((unsigned char)*q) && !strchr("<>\"'`", *q); q++);
			if (pos >= p - line && pos < q - line) {
				*q = '\0';
				url = p;
				break;
			}
		}
	if (url && !strchr(url, '\'')) {
		snprintf(cmd, sizeof cmd, "xdg-open '%s' >/dev/null 2>&1 &", url);
		if (system(cmd) < 0)
			fprintf(stderr, "tyrmel: can't open %s\n", url);
	}
	free(line);
}

static int
isword(uint32_t c)
{
	return c && c != ' ' && !strchr("()[]{}<>'\"`|;,", c < 128 ? (int)c : 'a');
}

/* ---- keys and the mouse ---- */

static VTermModifier
mods(unsigned int state)
{
	return (state & ShiftMask ? VTERM_MOD_SHIFT : 0) | (state & ControlMask ? VTERM_MOD_CTRL : 0) |
	       (state & Mod1Mask ? VTERM_MOD_ALT : 0);
}

static void
scrollview(int n)
{
	view = MIN(MAX(view + n, 0), sbn);
	dirty = 1;
}

static void
keypress(XKeyEvent *e)
{
	static const struct { KeySym sym; VTermKey key; } keys[] = {
		{ XK_Return, VTERM_KEY_ENTER }, { XK_KP_Enter, VTERM_KEY_KP_ENTER }, { XK_Tab, VTERM_KEY_TAB },
		{ XK_ISO_Left_Tab, VTERM_KEY_TAB }, { XK_BackSpace, VTERM_KEY_BACKSPACE }, { XK_Escape, VTERM_KEY_ESCAPE },
		{ XK_Up, VTERM_KEY_UP }, { XK_Down, VTERM_KEY_DOWN }, { XK_Left, VTERM_KEY_LEFT }, { XK_Right, VTERM_KEY_RIGHT },
		{ XK_Insert, VTERM_KEY_INS }, { XK_Delete, VTERM_KEY_DEL }, { XK_Home, VTERM_KEY_HOME }, { XK_End, VTERM_KEY_END },
		{ XK_Page_Up, VTERM_KEY_PAGEUP }, { XK_Page_Down, VTERM_KEY_PAGEDOWN },
		{ XK_KP_Up, VTERM_KEY_UP }, { XK_KP_Down, VTERM_KEY_DOWN }, { XK_KP_Left, VTERM_KEY_LEFT },
		{ XK_KP_Right, VTERM_KEY_RIGHT }, { XK_KP_Home, VTERM_KEY_HOME }, { XK_KP_End, VTERM_KEY_END },
		{ XK_KP_Page_Up, VTERM_KEY_PAGEUP }, { XK_KP_Page_Down, VTERM_KEY_PAGEDOWN },
		{ XK_KP_Insert, VTERM_KEY_INS }, { XK_KP_Delete, VTERM_KEY_DEL },
	};
	char text[64];
	KeySym sym;
	Status st;
	VTermModifier m = mods(e->state);
	unsigned int i;
	int n;
	uint32_t c;
	const char *p;

	n = xic ? Xutf8LookupString(xic, e, text, sizeof text - 1, &sym, &st) : XLookupString(e, text, sizeof text - 1, &sym, NULL);
	text[MAX(n, 0)] = '\0';
	/* ours: copy, paste, scrolling, the font size */
	if ((e->state & ControlMask) && (e->state & ShiftMask)) {
		switch (XkbKeycodeToKeysym(dpy, e->keycode, 0, 0)) {
		case XK_c: if (sel.on) own(xclipboard); return;
		case XK_v: paste(xclipboard); return;
		case XK_equal: case XK_plus: zoom(fontsize + 2); return;
		case XK_minus: zoom(fontsize - 2); return;
		case XK_0: zoom(basesize); return;
		}
	}
	if ((e->state & ShiftMask) && !(e->state & ControlMask)) {
		switch (sym) {
		case XK_Page_Up: case XK_KP_Page_Up: scrollview(rows / 2); return;
		case XK_Page_Down: case XK_KP_Page_Down: scrollview(-rows / 2); return;
		case XK_Insert: case XK_KP_Insert: paste(XA_PRIMARY); return;
		}
	}
	if (sym == XK_Shift_L || sym == XK_Shift_R || sym == XK_Control_L || sym == XK_Control_R ||
	    sym == XK_Alt_L || sym == XK_Alt_R || sym == XK_Super_L || sym == XK_Super_R || sym == XK_Caps_Lock)
		return;
	view = 0;
	dirty = 1;
	for (i = 0; i < LENGTH(keys); i++)
		if (keys[i].sym == sym) {
			vterm_keyboard_key(vt, keys[i].key, m);
			return;
		}
	if (sym >= XK_F1 && sym <= XK_F12) {
		vterm_keyboard_key(vt, VTERM_KEY_FUNCTION(sym - XK_F1 + 1), m);
		return;
	}
	if (e->state & ControlMask) {
		/* ctrl+letter: the letter itself, libvterm makes the control code */
		sym = XkbKeycodeToKeysym(dpy, e->keycode, 0, 0);
		c = sym < 0x100 ? sym : (sym & 0xff000000) == 0x01000000 ? sym & 0xffffff : 0;
		if (c) {
			vterm_keyboard_unichar(vt, c, m & ~VTERM_MOD_SHIFT);
			return;
		}
	}
	/* what the keyboard layout made, the shift already in it */
	for (p = text; *p;) {
		FcChar32 u;
		int l = FcUtf8ToUcs4((FcChar8 *)p, &u, strlen(p));

		if (l <= 0)
			break;
		vterm_keyboard_unichar(vt, u, m & VTERM_MOD_ALT);
		p += l;
	}
}

static void
cellat(int x, int y, long *r, int *c)
{
	*c = MIN(MAX(x / cw, 0), cols - 1);
	*r = (long)sbn - view + MIN(MAX(y / ch, 0), rows - 1);
}

static void
buttonpress(XButtonEvent *e)
{
	long r;
	int c;

	/* programs that want the mouse get it, unless shift is held */
	if (mousemode && !(e->state & ShiftMask)) {
		vterm_mouse_move(vt, MIN(e->y / ch, rows - 1), MIN(e->x / cw, cols - 1), mods(e->state));
		vterm_mouse_button(vt, e->button, 1, mods(e->state));
		return;
	}
	if (e->button == Button4) {
		if (alt) vterm_keyboard_key(vt, VTERM_KEY_UP, 0), vterm_keyboard_key(vt, VTERM_KEY_UP, 0), vterm_keyboard_key(vt, VTERM_KEY_UP, 0);
		else scrollview(3);
		return;
	}
	if (e->button == Button5) {
		if (alt) vterm_keyboard_key(vt, VTERM_KEY_DOWN, 0), vterm_keyboard_key(vt, VTERM_KEY_DOWN, 0), vterm_keyboard_key(vt, VTERM_KEY_DOWN, 0);
		else scrollview(-3);
		return;
	}
	if (e->button == Button2) {
		paste(XA_PRIMARY);
		return;
	}
	if (e->button != Button1)
		return;
	cellat(e->x, e->y, &r, &c);
	if (e->state & ControlMask) {
		openurl(r, c);
		return;
	}
	clicks = e->time - lastclick < 400 ? clicks + 1 : 1;
	lastclick = e->time;
	sel.r0 = sel.r1 = r;
	sel.c0 = sel.c1 = c;
	sel.on = 0;
	sel.going = 1;
	if (clicks >= 2) {
		/* two clicks a word, three the line */
		static Cell *row;
		static int rowsize;
		int a = c, b = c;

		if (rowsize < cols) {
			row = realloc(row, cols * sizeof *row);
			rowsize = cols;
		}
		if (r >= sbn) {
			int sv = view;

			view = 0;
			viewrow(r - sbn, row);
			view = sv;
		} else {
			Line *l = sbline(r);
			int i;

			for (i = 0; i < cols; i++)
				row[i] = i < l->cols ? l->cells[i] : (Cell){ 0 };
		}
		if (clicks == 2) {
			while (a > 0 && isword(row[a - 1].ch))
				a--;
			while (b < cols - 1 && isword(row[b + 1].ch))
				b++;
		} else
			a = 0, b = cols - 1;
		sel.c0 = a, sel.c1 = b;
		sel.on = 1;
		own(XA_PRIMARY);
	}
	dirty = 1;
}

static void
buttonrelease(XButtonEvent *e)
{
	if (mousemode && !(e->state & ShiftMask)) {
		vterm_mouse_move(vt, MIN(e->y / ch, rows - 1), MIN(e->x / cw, cols - 1), mods(e->state));
		vterm_mouse_button(vt, e->button, 0, mods(e->state));
		return;
	}
	if (e->button == Button1 && sel.going) {
		sel.going = 0;
		if (sel.on)
			own(XA_PRIMARY);
	}
}

static void
motion(XMotionEvent *e)
{
	long r;
	int c;

	if (mousemode && !(e->state & ShiftMask)) {
		vterm_mouse_move(vt, MIN(e->y / ch, rows - 1), MIN(e->x / cw, cols - 1), mods(e->state));
		return;
	}
	if (!sel.going || clicks > 1)
		return;
	cellat(e->x, e->y, &r, &c);
	/* dragging past the top or bottom scrolls */
	if (e->y < 0)
		scrollview(1);
	else if (e->y >= wh)
		scrollview(-1);
	if (r != sel.r1 || c != sel.c1) {
		sel.r1 = r, sel.c1 = c;
		sel.on = 1;
		dirty = 1;
	}
}

/* ---- the program in it ---- */

static void
spawn(void)
{
	struct winsize ws = { rows, cols, cols * cw, rows * ch };
	const char *sh;
	char wid[32];

	if ((child = forkpty(&ptyfd, NULL, NULL, &ws)) < 0)
		die("can't make a pty");
	if (child == 0) {
		snprintf(wid, sizeof wid, "%lu", win);
		setenv("TERM", "xterm-256color", 1);
		setenv("COLORTERM", "truecolor", 1);
		setenv("TERM_PROGRAM", "tyrmel", 1);
		setenv("TERM_PROGRAM_VERSION", VERSION, 1);
		setenv("WINDOWID", wid, 1);
		unsetenv("COLUMNS");
		unsetenv("LINES");
		signal(SIGCHLD, SIG_DFL);
		signal(SIGPIPE, SIG_DFL);
		if (cmdargv) {
			execvp(cmdargv[0], cmdargv);
			fprintf(stderr, "tyrmel: can't run %s\n", cmdargv[0]);
			_exit(127);
		}
		if (*shellcmd) {
			execl("/bin/sh", "sh", "-c", shellcmd, (char *)NULL);
			_exit(127);
		}
		sh = getenv("SHELL");
		if (!sh || !*sh)
			sh = "/bin/sh";
		execl(sh, sh, (char *)NULL);
		_exit(127);
	}
	fcntl(ptyfd, F_SETFL, fcntl(ptyfd, F_GETFL) | O_NONBLOCK);
}

/* feed what the program wrote, stopping after each picture to move the cursor past it */
static void
feed(const char *s, size_t n)
{
	const char *st, *q;
	size_t k;
	char mv[32];

	while (n > 0) {
		st = memmem(s, n, "\033\\", 2);
		k = st ? (size_t)(st - s) + 2 : n;
		/* "who are you": libvterm would say libvterm, and programs take that for neovim */
		if ((q = memmem(s, k, "\033[>q", 4)) || (q = memmem(s, k, "\033[>0q", 5))) {
			vterm_input_write(vt, s, q - s);
			writepty("\033P>|tyrmel " VERSION "\033\\", strlen("\033P>|tyrmel " VERSION "\033\\"));
			k = (q - s) + (q[3] == 'q' ? 4 : 5);
			s += k, n -= k;
			continue;
		}
		vterm_input_write(vt, s, k);
		if (pendingrows || pendingcols) {
			while (pendingrows-- > 0)
				vterm_input_write(vt, "\n", 1);
			snprintf(mv, sizeof mv, "\033[%dC", pendingcols);
			vterm_input_write(vt, mv, strlen(mv));
			pendingrows = pendingcols = 0;
		}
		/* clearing the screen clears the pictures on it */
		if (memmem(s, k, "\033[2J", 4) || memmem(s, k, "\033[3J", 4))
			delete('a', 0, 0, 0);
		s += k, n -= k;
	}
	vterm_screen_flush_damage(vs);
}

static int
readpty(void)
{
	static char b[1 << 18];
	ssize_t n;
	int got = 0;
	long start = ms();

	/* read for a frame at most, so a flood of output doesn't stop the drawing */
	while ((n = read(ptyfd, b, sizeof b)) > 0) {
		feed(b, n);
		got++;
		if (ms() - start >= 16)
			break;
	}
	if (n == 0 || (n < 0 && errno != EAGAIN && errno != EINTR))
		return -1;
	return got;
}

static void
checkconfig(void)
{
	struct stat st;
	int oldsize = fontsize;
	char oldfont[256];

	if (stat(cfgpath, &st) < 0 || st.st_mtime == cfgmtime)
		return;
	snprintf(oldfont, sizeof oldfont, "%s", fontname);
	loadconfig();
	if (forcesize > 3)
		fontsize = forcesize;
	setcolours();
	if (oldsize != fontsize || strcmp(oldfont, fontname)) {
		basesize = fontsize;
		zoom(fontsize);
	}
}

static void
usage(void)
{
	fputs("usage: tyrmel [-T title] [-class name] [-geometry COLSxROWS] [-fs size] [-hold] [-e command ...]\n", stderr);
	exit(1);
}

int
main(int argc, char *argv[])
{
	XSetWindowAttributes wa;
	XClassHint ch_ = { NULL, NULL };
	XEvent ev;
	fd_set fds;
	struct timeval tv;
	long last = 0, lastcheck = 0, now, pid;
	char cfgdir[1024];
	int i, xfd, status = 0;

	for (i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "-v")) {
			puts("tyrmel-" VERSION);
			return 0;
		} else if ((!strcmp(argv[i], "-T") || !strcmp(argv[i], "-title") || !strcmp(argv[i], "-t")) && i + 1 < argc)
			wtitle = argv[++i];
		else if ((!strcmp(argv[i], "-class") || !strcmp(argv[i], "-c")) && i + 1 < argc)
			wclass = argv[++i];
		else if (!strcmp(argv[i], "-name") && i + 1 < argc)
			wname = argv[++i];
		else if ((!strcmp(argv[i], "-geometry") || !strcmp(argv[i], "-g")) && i + 1 < argc)
			sscanf(argv[++i], "%dx%d", &geomcols, &geomrows);
		else if (!strcmp(argv[i], "-fs") && i + 1 < argc)
			forcesize = atoi(argv[++i]);
		else if (!strcmp(argv[i], "-hold"))
			holdopen = 1;
		else if (!strcmp(argv[i], "-e") && i + 1 < argc) {
			cmdargv = argv + i + 1;
			break;
		} else if (!strcmp(argv[i], "-ls") || !strcmp(argv[i], "+sb") || !strcmp(argv[i], "-sb"))
			;	/* xterm's, no matter here */
		else
			usage();
	}
	setlocale(LC_CTYPE, "");
	XSetLocaleModifiers("");
	if (!(dpy = XOpenDisplay(NULL)))
		die("can't open the display");
	scr = DefaultScreen(dpy);
	vis = DefaultVisual(dpy, scr);
	cmap = DefaultColormap(dpy, scr);
	depth = DefaultDepth(dpy, scr);

	snprintf(cfgdir, sizeof cfgdir, "%s/.config/tyrmel", getenv("HOME") ? getenv("HOME") : ".");
	if (getenv("XDG_CONFIG_HOME") && *getenv("XDG_CONFIG_HOME"))
		snprintf(cfgdir, sizeof cfgdir, "%s/tyrmel", getenv("XDG_CONFIG_HOME"));
	/* ~/.config might not be there yet */
	snprintf(cfgpath, sizeof cfgpath, "%s", cfgdir);
	for (char *p = cfgpath + 1; *p; p++)
		if (*p == '/') {
			*p = '\0';
			mkdir(cfgpath, 0755);
			*p = '/';
		}
	mkdir(cfgdir, 0755);
	snprintf(cfgpath, sizeof cfgpath, "%s/config", cfgdir);
	loadconfig();
	if (forcesize > 3)
		fontsize = forcesize;
	basesize = fontsize;
	loadfonts(fontsize);
	cols = MAX(geomcols, 2), rows = MAX(geomrows, 1);

	wa.background_pixel = BlackPixel(dpy, scr);
	wa.bit_gravity = NorthWestGravity;
	wa.event_mask = KeyPressMask | ButtonPressMask | ButtonReleaseMask | PointerMotionMask | ExposureMask |
	                StructureNotifyMask | FocusChangeMask;
	win = XCreateWindow(dpy, RootWindow(dpy, scr), 0, 0, cols * cw, rows * ch, 0, depth, InputOutput, vis,
	                    CWBackPixel | CWBitGravity | CWEventMask, &wa);
	ch_.res_name = (char *)wname;
	ch_.res_class = (char *)wclass;
	XSetClassHint(dpy, win, &ch_);
	XStoreName(dpy, win, wtitle ? wtitle : cmdargv ? cmdargv[0] : "tyrmel");
	wmdelete = XInternAtom(dpy, "WM_DELETE_WINDOW", False);
	xclipboard = XInternAtom(dpy, "CLIPBOARD", False);
	xtargets = XInternAtom(dpy, "TARGETS", False);
	xutf8 = XInternAtom(dpy, "UTF8_STRING", False);
	xprop = XInternAtom(dpy, "TYRMEL_PASTE", False);
	netwmname = XInternAtom(dpy, "_NET_WM_NAME", False);
	netwmpid = XInternAtom(dpy, "_NET_WM_PID", False);
	XSetWMProtocols(dpy, win, &wmdelete, 1);
	pid = getpid();
	XChangeProperty(dpy, win, netwmpid, XA_CARDINAL, 32, PropModeReplace, (unsigned char *)&pid, 1);
	if (wtitle)
		XChangeProperty(dpy, win, netwmname, xutf8, 8, PropModeReplace, (unsigned char *)wtitle, strlen(wtitle));
	setsizehints();
	gc = XCreateGC(dpy, win, 0, NULL);
	if ((xim = XOpenIM(dpy, NULL, NULL, NULL)))
		xic = XCreateIC(xim, XNInputStyle, XIMPreeditNothing | XIMStatusNothing, XNClientWindow, win,
		                XNFocusWindow, win, NULL);

	vt = vterm_new(rows, cols);
	vterm_set_utf8(vt, 1);
	vterm_output_set_callback(vt, ontermoutput, NULL);
	vs = vterm_obtain_screen(vt);
	vst = vterm_obtain_state(vt);
	vterm_screen_set_callbacks(vs, &screencb, NULL);
	vterm_screen_set_unrecognised_fallbacks(vs, &fallbacks, NULL);
	vterm_screen_enable_altscreen(vs, 1);
	vterm_screen_enable_reflow(vs, 1);
	vterm_screen_set_damage_merge(vs, VTERM_DAMAGE_SCROLL);
	vterm_state_set_bold_highbright(vst, 1);
	setcolours();
	vterm_screen_reset(vs, 1);
	if (scrollmax)
		sb = calloc(scrollmax, sizeof *sb);

	resize(cols * cw, rows * ch);
	signal(SIGPIPE, SIG_IGN);
	spawn();
	XMapWindow(dpy, win);
	xfd = ConnectionNumber(dpy);

	for (;;) {
		while (XPending(dpy)) {
			XNextEvent(dpy, &ev);
			if (XFilterEvent(&ev, None))
				continue;
			switch (ev.type) {
			case KeyPress: keypress(&ev.xkey); break;
			case ButtonPress: buttonpress(&ev.xbutton); break;
			case ButtonRelease: buttonrelease(&ev.xbutton); break;
			case MotionNotify: motion(&ev.xmotion); break;
			case Expose: if (!ev.xexpose.count) XCopyArea(dpy, buf, win, gc, 0, 0, ww, wh, 0, 0); break;
			case ConfigureNotify: resize(ev.xconfigure.width, ev.xconfigure.height); break;
			case SelectionRequest: selectionrequest(&ev.xselectionrequest); break;
			case SelectionNotify: selectionnotify(&ev.xselection); break;
			case SelectionClear: break;
			case FocusIn:
			case FocusOut:
				focused = ev.type == FocusIn;
				if (xic)
					(focused ? XSetICFocus : XUnsetICFocus)(xic);
				if (focused)
					vterm_state_focus_in(vst);
				else
					vterm_state_focus_out(vst);
				if (focused) {
					XWMHints *h = XGetWMHints(dpy, win);

					if (h && (h->flags & XUrgencyHint)) {
						h->flags &= ~XUrgencyHint;
						XSetWMHints(dpy, win, h);
					}
					if (h)
						XFree(h);
				}
				dirty = 1;
				break;
			case ClientMessage:
				if ((Atom)ev.xclient.data.l[0] == wmdelete) {
					kill(child, SIGHUP);
					return 0;
				}
				break;
			}
		}
		now = ms();
		if (dirty && now - last >= 16) {
			redraw();
			last = now;
		}
		XFlush(dpy);
		FD_ZERO(&fds);
		FD_SET(xfd, &fds);
		if (ptyfd >= 0)
			FD_SET(ptyfd, &fds);
		tv.tv_sec = dirty ? 0 : 2;
		tv.tv_usec = dirty ? 16000 : 0;
		if (select(MAX(xfd, ptyfd) + 1, &fds, NULL, NULL, &tv) < 0 && errno != EINTR)
			die("select");
		if (ptyfd >= 0 && FD_ISSET(ptyfd, &fds) && readpty() < 0) {
			waitpid(child, &status, WNOHANG);
			close(ptyfd);
			ptyfd = -1;
			if (!holdopen)
				break;
		}
		/* the settings file, every two seconds */
		if ((now = ms()) - lastcheck > 2000) {
			checkconfig();
			lastcheck = now;
		}
	}
	if (dirty)
		redraw();
	XCloseDisplay(dpy);
	return WIFEXITED(status) ? WEXITSTATUS(status) : 0;
}
