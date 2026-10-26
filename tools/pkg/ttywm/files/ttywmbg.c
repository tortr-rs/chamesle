/* ttywmbg - a picture or a colour behind the windows
 *
 *   ttywmbg ~/pictures/sea.png [fill|fit|centre|tile]
 *   ttywmbg '#000000'   or   ttywmbg black
 *
 * png and jpeg. it stays after ttywmbg is gone, and programs that look for the
 * wallpaper (_XROOTPMAP_ID) find it */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <setjmp.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <png.h>
#include <jpeglib.h>

#define MIN(A, B)       ((A) < (B) ? (A) : (B))
#define MAX(A, B)       ((A) > (B) ? (A) : (B))

enum { Fill, Fit, Centre, Tile };

static Display *dpy;
static int scr, sw, sh;

static void
die(const char *msg)
{
	fprintf(stderr, "ttywmbg: %s\n", msg);
	exit(1);
}

static int
parsecolour(const char *name, unsigned int *rgb)
{
	static const char *names[][2] = {
		{ "black", "000000" }, { "blue", "0000aa" }, { "green", "00aa00" }, { "cyan", "00aaaa" },
		{ "red", "aa0000" }, { "magenta", "aa00aa" }, { "brown", "aa5500" }, { "grey", "aaaaaa" },
		{ "gray", "aaaaaa" }, { "darkgrey", "555555" }, { "darkgray", "555555" },
		{ "lightblue", "5555ff" }, { "lightgreen", "55ff55" }, { "lightcyan", "55ffff" },
		{ "lightred", "ff5555" }, { "pink", "ff55ff" }, { "yellow", "ffff55" }, { "white", "ffffff" },
	};
	char s[32];
	size_t i, n = 0;

	for (; *name && n < sizeof s - 1; name++)
		if (!isspace((unsigned char)*name))
			s[n++] = tolower((unsigned char)*name);
	s[n] = '\0';
	for (i = 0; i < sizeof names / sizeof names[0]; i++)
		if (!strcmp(s, names[i][0]))
			return sscanf(names[i][1], "%x", rgb) == 1;
	return s[0] == '#' && strlen(s) == 7 && sscanf(s + 1, "%x", rgb) == 1;
}

/* ---- pictures, into 0xRRGGBB ---- */

static unsigned int *
loadpng(const char *path, int *w, int *h)
{
	png_image pi;
	unsigned int *px;

	memset(&pi, 0, sizeof pi);
	pi.version = PNG_IMAGE_VERSION;
	if (!png_image_begin_read_from_file(&pi, path))
		return NULL;
	pi.format = PNG_FORMAT_BGRA;
	if (!(px = malloc(PNG_IMAGE_SIZE(pi))) || !png_image_finish_read(&pi, NULL, px, 0, NULL)) {
		free(px);
		png_image_free(&pi);
		return NULL;
	}
	*w = pi.width, *h = pi.height;
	return px;
}

struct jerr {
	struct jpeg_error_mgr mgr;
	jmp_buf jb;
};

static void
jpegfail(j_common_ptr c)
{
	longjmp(((struct jerr *)c->err)->jb, 1);
}

static unsigned int *
loadjpeg(const char *path, int *w, int *h)
{
	struct jpeg_decompress_struct c;
	struct jerr e;
	unsigned char *row = NULL;
	unsigned int *px = NULL;
	FILE *f;
	int x, y;

	if (!(f = fopen(path, "rb")))
		return NULL;
	c.err = jpeg_std_error(&e.mgr);
	e.mgr.error_exit = jpegfail;
	if (setjmp(e.jb)) {
		jpeg_destroy_decompress(&c);
		fclose(f);
		free(row);
		free(px);
		return NULL;
	}
	jpeg_create_decompress(&c);
	jpeg_stdio_src(&c, f);
	jpeg_read_header(&c, TRUE);
	c.out_color_space = JCS_RGB;
	jpeg_start_decompress(&c);
	*w = c.output_width, *h = c.output_height;
	px = malloc((size_t)*w * *h * 4);
	row = malloc((size_t)*w * 3);
	for (y = 0; px && row && c.output_scanline < c.output_height; y++) {
		jpeg_read_scanlines(&c, &row, 1);
		for (x = 0; x < *w; x++)
			px[y * *w + x] = row[x * 3] << 16 | row[x * 3 + 1] << 8 | row[x * 3 + 2];
	}
	jpeg_finish_decompress(&c);
	jpeg_destroy_decompress(&c);
	fclose(f);
	free(row);
	return px;
}

/* one pixel of the picture at (x, y) in its own size, averaged over the box it covers on screen */
static unsigned int
sample(const unsigned int *px, int w, int h, double x0, double y0, double x1, double y1)
{
	unsigned long r = 0, g = 0, b = 0, n = 0;
	int x, y, xa = x0, ya = y0, xb = MAX(xa + 1, (int)x1), yb = MAX(ya + 1, (int)y1);
	unsigned int p;

	xb = MIN(xb, w), yb = MIN(yb, h);
	/* no more than 4x4 samples: big pictures shrunk a lot still look smooth enough */
	for (y = ya; y < yb; y += MAX(1, (yb - ya) / 4))
		for (x = xa; x < xb; x += MAX(1, (xb - xa) / 4)) {
			p = px[y * w + x];
			r += p >> 16 & 255, g += p >> 8 & 255, b += p & 255, n++;
		}
	return n ? (r / n) << 16 | (g / n) << 8 | b / n : 0;
}

static void
paint(unsigned int *out, const unsigned int *px, int w, int h, int how, unsigned int bg)
{
	double scale, ox, oy;
	int x, y, dw, dh;

	for (x = 0; x < sw * sh; x++)
		out[x] = bg;
	if (how == Tile) {
		for (y = 0; y < sh; y++)
			for (x = 0; x < sw; x++)
				out[y * sw + x] = px[(y % h) * w + x % w];
		return;
	}
	if (how == Centre)
		scale = 1;
	else if (how == Fit)
		scale = MIN((double)sw / w, (double)sh / h);
	else
		scale = MAX((double)sw / w, (double)sh / h);
	dw = w * scale, dh = h * scale;
	ox = (sw - dw) / 2, oy = (sh - dh) / 2;
	for (y = MAX(0, (int)oy); y < MIN(sh, (int)oy + dh); y++)
		for (x = MAX(0, (int)ox); x < MIN(sw, (int)ox + dw); x++)
			out[y * sw + x] = sample(px, w, h, (x - ox) / scale, (y - oy) / scale,
			                         (x + 1 - ox) / scale, (y + 1 - oy) / scale);
}

/* ---- onto the root window ---- */

static void
setroot(Pixmap pm)
{
	Window root = RootWindow(dpy, scr);
	Atom xroot = XInternAtom(dpy, "_XROOTPMAP_ID", False), eset = XInternAtom(dpy, "ESETROOT_PMAP_ID", False);
	Atom type;
	int fmt;
	unsigned long n, after;
	unsigned char *data;

	/* the one before: whoever made it kept it on the server, so it goes now */
	if (XGetWindowProperty(dpy, root, eset, 0, 1, False, XA_PIXMAP, &type, &fmt, &n, &after, &data) == Success && data) {
		if (type == XA_PIXMAP && n == 1)
			XKillClient(dpy, *(Pixmap *)data);
		XFree(data);
	}
	XChangeProperty(dpy, root, xroot, XA_PIXMAP, 32, PropModeReplace, (unsigned char *)&pm, 1);
	XChangeProperty(dpy, root, eset, XA_PIXMAP, 32, PropModeReplace, (unsigned char *)&pm, 1);
	XSetWindowBackgroundPixmap(dpy, root, pm);
	XClearWindow(dpy, root);
}

int
main(int argc, char *argv[])
{
	unsigned int *px = NULL, *out, bg = 0;
	const char *how = argc > 2 ? argv[2] : "fill", *ext;
	XImage *xi;
	Pixmap pm;
	GC gc;
	int w, h, mode;

	if (argc < 2 || argc > 3)
		die("usage: ttywmbg picture [fill|fit|centre|tile] | ttywmbg colour");
	/* the wallpaper must outlive us: the server keeps it when we close */
	if (!(dpy = XOpenDisplay(NULL)))
		die("can't open the display");
	XSetCloseDownMode(dpy, RetainPermanent);
	scr = DefaultScreen(dpy);
	sw = DisplayWidth(dpy, scr);
	sh = DisplayHeight(dpy, scr);
	if (DefaultDepth(dpy, scr) < 24)
		die("needs a 24 bit screen");

	mode = !strcmp(how, "fit") ? Fit : !strcmp(how, "centre") || !strcmp(how, "center") ? Centre :
	       !strcmp(how, "tile") ? Tile : Fill;
	if (!parsecolour(argv[1], &bg)) {
		ext = strrchr(argv[1], '.');
		if (ext && (!strcasecmp(ext, ".jpg") || !strcasecmp(ext, ".jpeg")))
			px = loadjpeg(argv[1], &w, &h);
		else
			px = loadpng(argv[1], &w, &h);
		if (!px && !(px = loadjpeg(argv[1], &w, &h)))
			die("can't read the picture: png or jpeg only");
		bg = 0;
	}
	if (!(out = malloc((size_t)sw * sh * 4)))
		die("out of memory");
	if (px)
		paint(out, px, w, h, mode, bg);
	else
		for (w = 0; w < sw * sh; w++)
			out[w] = bg;
	free(px);

	pm = XCreatePixmap(dpy, RootWindow(dpy, scr), sw, sh, DefaultDepth(dpy, scr));
	gc = XCreateGC(dpy, pm, 0, NULL);
	xi = XCreateImage(dpy, DefaultVisual(dpy, scr), DefaultDepth(dpy, scr), ZPixmap, 0, (char *)out, sw, sh, 32, 0);
	XPutImage(dpy, pm, gc, xi, 0, 0, 0, 0, sw, sh);
	XDestroyImage(xi);
	XFreeGC(dpy, gc);
	setroot(pm);
	XCloseDisplay(dpy);
	return 0;
}
