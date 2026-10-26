/* torrent - ttywm on wayland: the same frames, bottom line and settings, without the tty behind */
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <locale.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <linux/input-event-codes.h>
#include <cairo.h>
#include <dbus/dbus.h>
#include <drm_fourcc.h>
#include <libinput.h>
#include <security/pam_appl.h>
#include <wayland-server-core.h>
#include <xkbcommon/xkbcommon.h>
#include <wlr/backend.h>
#include <wlr/backend/libinput.h>
#include <wlr/backend/session.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/render/allocator.h>
#include <wlr/render/wlr_renderer.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_cursor.h>
#include <wlr/types/wlr_cursor_shape_v1.h>
#include <wlr/types/wlr_data_control_v1.h>
#include <wlr/types/wlr_data_device.h>
#include <wlr/types/wlr_export_dmabuf_v1.h>
#include <wlr/types/wlr_fractional_scale_v1.h>
#include <wlr/types/wlr_gamma_control_v1.h>
#include <wlr/types/wlr_idle_notify_v1.h>
#include <wlr/types/wlr_input_device.h>
#include <wlr/types/wlr_keyboard.h>
#include <wlr/types/wlr_layer_shell_v1.h>
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_output_layout.h>
#include <wlr/types/wlr_pointer.h>
#include <wlr/types/wlr_presentation_time.h>
#include <wlr/types/wlr_primary_selection.h>
#include <wlr/types/wlr_primary_selection_v1.h>
#include <wlr/types/wlr_relative_pointer_v1.h>
#include <wlr/types/wlr_scene.h>
#include <wlr/types/wlr_screencopy_v1.h>
#include <wlr/types/wlr_seat.h>
#include <wlr/types/wlr_server_decoration.h>
#include <wlr/types/wlr_single_pixel_buffer_v1.h>
#include <wlr/types/wlr_subcompositor.h>
#include <wlr/types/wlr_viewporter.h>
#include <wlr/types/wlr_xcursor_manager.h>
#include <wlr/types/wlr_xdg_activation_v1.h>
#include <wlr/types/wlr_xdg_decoration_v1.h>
#include <wlr/types/wlr_xdg_output_v1.h>
#include <wlr/types/wlr_xdg_shell.h>
#include <wlr/util/log.h>
#include <wlr/xwayland.h>

#define LENGTH(X)       (sizeof(X) / sizeof(X)[0])
#define MAX(A, B)       ((A) > (B) ? (A) : (B))
#define MIN(A, B)       ((A) < (B) ? (A) : (B))
#define CLEANMASK(mask) ((mask) & ~(WLR_MODIFIER_CAPS|WLR_MODIFIER_MOD2))
#define LISTEN(S, L, F) ((L)->notify = (F), wl_signal_add((S), (L)))
#define NSCR            9
#define SUPER           WLR_MODIFIER_LOGO
#define SHIFT           WLR_MODIFIER_SHIFT

enum { ColBg, ColWindow, ColOther, ColTitle, ColBar, ColLast };
enum { ActRun, ActTerminal, ActMenu, ActClose, ActNext, ActFull, ActQuit, ActView, ActSend, ActVolUp, ActVolDown, ActMute,
       ActLightUp, ActLightDown, ActLeft, ActRight, ActMax, ActRestore, ActLock };
enum { SegNone, SegNet, SegVol, SegLight };
/* what the bottom line can show, in the order it's given */
enum { BarCommands, BarNet, BarVol, BarLight, BarBattery, BarDate, BarClock, BarTty, BarLast };
/* what's under the pointer: the first int of each */
enum { KClient = 1, KLayer, KNotif, KBar };
enum { GrabNone, GrabMove, GrabResize };

typedef struct {
	unsigned int mod;
	xkb_keysym_t keysym;
	int act, n;
	char *cmd;
} Key;

/* pixels we draw with cairo, as something wlroots can show */
typedef struct {
	struct wlr_buffer base;
	cairo_surface_t *s;
} Buf;

typedef struct Notif Notif;
struct Notif {
	int kind;
	unsigned int id;
	char app[64], line[4][128];
	int nlines, w, h;
	time_t until;
	struct wlr_scene_buffer *buf;
	Notif *next;
};

typedef struct Client Client;
struct Client {
	int kind;
	char name[256];
	int x, y, w, h, oldx, oldy, oldw, oldh;
	int scr, isfull, mapped, unmanaged, out, assoc;
	int snapped, sx, sy, sw, sh;	/* where it was before super+arrows */
	int typed, total;		/* the border typing itself in: cells so far, of all */
	long long born;			/* when it started, ms */
	struct wlr_xdg_toplevel *xdg;
	struct wlr_xdg_toplevel_decoration_v1 *deco;
	struct wlr_xwayland_surface *xw;
	struct wlr_scene_tree *tree, *content, *surf;
	struct wlr_scene_buffer *edge[4];	/* top, bottom, left, right */
	struct wlr_scene_rect *back;		/* black behind the window, like the tty was */
	struct wl_listener map, unmap, commit, destroy, fullscreen, maximize, move, resize, title;
	struct wl_listener associate, dissociate, configure, activate, geom, decomode, decodestroy;
	Client *next;
};

typedef struct {
	struct wlr_xdg_popup *p;
	struct wlr_scene_tree *parent;
	struct wl_listener commit, destroy;
} Popup;

typedef struct Layer Layer;
struct Layer {
	int kind;
	struct wlr_layer_surface_v1 *ls;
	struct wlr_scene_layer_surface_v1 *scene;
	struct wl_listener map, unmap, commit, destroy;
	Layer *next;
};

typedef struct Output Output;
struct Output {
	struct wlr_output *wlr;
	struct wl_listener frame, state, destroy;
	Output *next;
};

typedef struct Kbd Kbd;
struct Kbd {
	struct wlr_keyboard *wlr;
	struct wl_listener key, mods, destroy;
	Kbd *next;
};

/* window firefox = tty 2, full screen */
typedef struct {
	char name[64];
	int scr, full;
} Rule;

/* settings, from ~/.config/torrent/config */
static char terminal[256] = "foot", menu[256] = "fuzzel";
static char colname[ColLast][32] = { "black", "white", "grey", "white", "grey" };
static char wallpaper[512], kblayout[64], kbvariant[64];
static int clock24 = 1, showclock = 1, showdate = 1, showbattery = 1, shownetwork = 1, showvolume = 1, showlight = 1, big;
static int typing = 1, typespeed = 600;	/* cells a second */
static int tapclick = 1, natural;
static int barorder[BarLast + 1] = { BarCommands, BarNet, BarVol, BarLight, BarBattery, BarDate, BarClock, BarTty, -1 };
static char barcmd[4][256], barout[4][64];
static int nbarcmds;
static Key *keys;
static int nkeys;
static Rule *rules;
static int nrules;

static const char defaultconfig[] =
"# torrent settings\n"
"# change what's after the = and save. it works right away.\n"
"\n"
"# colours: black blue green cyan red magenta brown grey\n"
"#          dark grey, light blue, light green, light cyan, light red, pink, yellow, white\n"
"#          or #rrggbb\n"
"window colour = white\n"
"other windows colour = grey\n"
"title colour = white\n"
"bottom line colour = grey\n"
"background colour = black\n"
"\n"
"# a png behind the windows, or nothing for just the background colour\n"
"wallpaper = /usr/share/backgrounds/chamesle/default.png\n"
"\n"
"# normal or big. big is for small, sharp screens. changes when you log in again\n"
"text size = normal\n"
"\n"
"# new windows type their border in, closed ones type it away. on or off, and fast, normal or slow\n"
"border typing = on\n"
"typing speed = normal\n"
"\n"
"# what's on the bottom line, in this order. leave out what you don't want:\n"
"#   commands network volume brightness battery date clock tty\n"
"bottom line = commands network volume brightness battery date clock tty\n"
"# 24 hour or 12 hour\n"
"clock = 24 hour\n"
"# your own things on the bottom line: a command, its first line shows. up to 4, every 5 seconds\n"
"# bottom line command = cat /sys/class/thermal/thermal_zone0/temp\n"
"\n"
"# the terminal for new windows, and the apps menu\n"
"terminal = foot\n"
"apps menu = fuzzel\n"
"\n"
"# the keyboard, like us, de or fr. nothing means the one you picked when installing\n"
"keyboard layout =\n"
"keyboard variant =\n"
"# the touchpad. changes when you log in again\n"
"tap to click = on\n"
"natural scrolling = off\n"
"\n"
"# keys. super is the windows key, then shift, ctrl, alt. after the = goes one of:\n"
"#   terminal, apps menu, close window, next window, full screen, log out, lock,\n"
"#   left half, right half, fill screen, put back, tty 1 to tty 9, send to tty 1 to 9,\n"
"#   volume up, volume down, mute, brightness up, brightness down\n"
"# or any program, like firefox\n"
"super+enter = terminal\n"
"super+d = apps menu\n"
"super+q = close window\n"
"super+tab = next window\n"
"super+f = full screen\n"
"super+shift+e = log out\n"
"# these are there unless you put something else on the key:\n"
"# super+1 to 9 = tty 1 to 9, super+shift+1 to 9 = send to tty 1 to 9, super+l = lock,\n"
"# super+left = left half, super+right = right half, super+up = fill screen, super+down = put back\n"
"# ctrl+alt+f1 to f12 go to the consoles, like everywhere\n"
"\n"
"# where windows go, by their name (the app id, or the class for x11 programs): tty 1 to 9, full screen, or both\n"
"# window firefox = tty 2\n"
"# window mpv = full screen\n"
"\n"
"# programs to start when you log in, one per line, like:\n"
"# start = firefox\n"
"\n"
"# more settings from another file, read as if they were here\n"
"# include = ~/.config/torrent/keys\n";

static struct wl_display *dpy;
static struct wl_event_loop *loop;
static struct wlr_backend *backend;
static struct wlr_session *session;
static struct wlr_renderer *renderer;
static struct wlr_allocator *alloc;
static struct wlr_compositor *compositor;
static struct wlr_scene *scene;
static struct wlr_scene_output_layout *sol;
static struct wlr_output_layout *layout;
static struct wlr_xdg_shell *xdgshell;
static struct wlr_layer_shell_v1 *layershell;
static struct wlr_xdg_decoration_manager_v1 *decomgr;
static struct wlr_cursor_shape_manager_v1 *shapemgr;
static struct wlr_xdg_activation_v1 *activation;
static struct wlr_cursor *cursor;
static struct wlr_xcursor_manager *xcm;
static struct wlr_seat *seat;
static struct wlr_xwayland *xwayland;
static struct wlr_idle_notifier_v1 *idle;
/* bottom to top */
static struct wlr_scene_tree *bgtree, *layers[4], *wintree, *bartree, *fulltree, *ortree, *notiftree, *locktree;
static struct wlr_scene_rect *bgrect, *lockrect;
static struct wlr_scene_buffer *wallbuf, *barbuf, *lockbuf;
static struct wl_listener newoutput_l, newinput_l, newtoplevel_l, newpopup_l, newlayer_l, newdeco_l, newxw_l, xwready_l;
static struct wl_listener motion_l, motionabs_l, button_l, axis_l, frame_l;
static struct wl_listener setcursor_l, setsel_l, setpsel_l, shape_l, activate_l;
static Output *outputs;
static Kbd *kbds;
static Layer *layersurfs, *exclusive;	/* exclusive: a layer that wants the keyboard, like the apps menu */
static Client *clients, *sel, *ghosts;	/* ghosts: borders typing themselves away */
static int ox, oy, sw, sh, wh, cw, ch, fontpx, fasc;
static int cur, locked, barkind = KBar;
static float col[ColLast][4];
static cairo_font_options_t *fontopts;
static struct wl_event_source *ticker;
static int grab, gcx, gcy, gcw, gch;
static double gx, gy;
static Client *grabc;
static char lockpw[256];
static int locklen, lockwrong;
static char cfgpath[4096];
static time_t cfgmtime;
static int vol = -1, muted;
static char backlight[256];	/* /sys/class/backlight/..., or empty */
static DBusConnection *bus;
static Notif *notifs;
static unsigned int lastid;
static struct { int x0, x1, seg; } segs[16];
static int nsegs;

static int ulen(const char *);
static void setfullscreen(Client *, int);
static void drawbar(void);
static void focus(Client *);

static void
die(const char *s)
{
	fprintf(stderr, "torrent: %s\n", s);
	exit(1);
}

/* twice, so it's init's child and never our zombie */
static void
run(const char *cmd)
{
	pid_t pid;

	if ((pid = fork()) == 0) {
		if (fork() == 0) {
			setsid();
			execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
			_exit(1);
		}
		_exit(0);
	}
	if (pid > 0)
		waitpid(pid, NULL, 0);
}

/* runs cmd and waits for it, keeping the first line it prints */
static void
runwait(const char *cmd, char *out, size_t n)
{
	FILE *f;

	if (out)
		*out = '\0';
	if (!(f = popen(cmd, "r")))
		return;
	if (out && !fgets(out, n, f))
		*out = '\0';
	while (fgetc(f) != EOF);
	pclose(f);
}

static int
readfile(const char *path, char *buf, size_t n)
{
	FILE *f;
	size_t len;

	if (!(f = fopen(path, "r")))
		return 0;
	len = fread(buf, 1, n - 1, f);
	fclose(f);
	buf[len] = '\0';
	while (len && isspace((unsigned char)buf[len - 1]))
		buf[--len] = '\0';
	return 1;
}

static long
readnum(const char *dir, const char *file)
{
	char path[512], buf[64];

	snprintf(path, sizeof path, "%s/%s", dir, file);
	return readfile(path, buf, sizeof buf) ? atol(buf) : -1;
}

static long long
ms(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}

/* ---- settings ---- */

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

/* "Dark  Grey" -> "darkgrey" */
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
yes(const char *v)
{
	char s[16];

	squash(s, v, sizeof s);
	return !strcmp(s, "on") || !strcmp(s, "yes") || !strcmp(s, "true") || !strcmp(s, "1");
}

static const char *
colourhex(const char *name)
{
	static const char *vga[][2] = {
		{ "black", "#000000" }, { "blue", "#0000aa" }, { "green", "#00aa00" }, { "cyan", "#00aaaa" },
		{ "red", "#aa0000" }, { "magenta", "#aa00aa" }, { "brown", "#aa5500" }, { "grey", "#aaaaaa" },
		{ "gray", "#aaaaaa" }, { "darkgrey", "#555555" }, { "darkgray", "#555555" },
		{ "lightblue", "#5555ff" }, { "lightgreen", "#55ff55" }, { "lightcyan", "#55ffff" },
		{ "lightred", "#ff5555" }, { "pink", "#ff55ff" }, { "yellow", "#ffff55" }, { "white", "#ffffff" },
	};
	char s[32];
	unsigned int i;

	squash(s, name, sizeof s);
	for (i = 0; i < LENGTH(vga); i++)
		if (!strcmp(s, vga[i][0]))
			return vga[i][1];
	return name;
}

/* "window colour" or "window color" */
static int
iskey(const char *key, const char *want)
{
	char alt[64];
	const char *p;

	if (!strcmp(key, want))
		return 1;
	if (!(p = strstr(want, "colour")))
		return 0;
	snprintf(alt, sizeof alt, "%.*scolor%s", (int)(p - want), want, p + 6);
	return !strcmp(key, alt);
}

static xkb_keysym_t
keyname(const char *s)
{
	static const char *names[][2] = {
		{ "enter", "Return" }, { "return", "Return" }, { "tab", "Tab" }, { "space", "space" },
		{ "esc", "Escape" }, { "escape", "Escape" }, { "backspace", "BackSpace" }, { "delete", "Delete" },
		{ "up", "Up" }, { "down", "Down" }, { "left", "Left" }, { "right", "Right" },
		{ "home", "Home" }, { "end", "End" }, { "print", "Print" }, { "printscreen", "Print" },
	};
	char buf[32];
	unsigned int i;
	xkb_keysym_t k;

	for (i = 0; i < LENGTH(names); i++)
		if (!strcmp(s, names[i][0]))
			return xkb_keysym_from_name(names[i][1], 0);
	if (s[0] == 'f' && isdigit((unsigned char)s[1])) {
		snprintf(buf, sizeof buf, "F%s", s + 1);
		return xkb_keysym_from_name(buf, 0);
	}
	if ((k = xkb_keysym_from_name(s, 0)) != XKB_KEY_NoSymbol)
		return k;
	return xkb_keysym_from_name(s, XKB_KEYSYM_CASE_INSENSITIVE);
}

static void
addkey(unsigned int mod, xkb_keysym_t sym, int act, int n, const char *cmd)
{
	Key *k;

	if (!sym || !(k = realloc(keys, (nkeys + 1) * sizeof(Key))))
		return;
	keys = k;
	k = &keys[nkeys++];
	k->mod = mod;
	k->keysym = sym;
	k->act = act;
	k->n = n;
	k->cmd = cmd ? strdup(cmd) : NULL;
}

/* super+shift+e = log out */
static int
parsekey(char *name, char *value)
{
	static const struct { const char *word; int act; } acts[] = {
		{ "terminal", ActTerminal }, { "appsmenu", ActMenu }, { "menu", ActMenu },
		{ "closewindow", ActClose }, { "close", ActClose }, { "nextwindow", ActNext },
		{ "fullscreen", ActFull }, { "logout", ActQuit }, { "quit", ActQuit }, { "lock", ActLock },
		{ "lockscreen", ActLock }, { "lefthalf", ActLeft }, { "righthalf", ActRight },
		{ "fillscreen", ActMax }, { "putback", ActRestore }, { "volumeup", ActVolUp },
		{ "volumedown", ActVolDown }, { "mute", ActMute }, { "brightnessup", ActLightUp },
		{ "brightnessdown", ActLightDown },
	};
	unsigned int mod = 0, i;
	char *tok, *last = NULL, act[64];
	int n;

	if (!strchr(name, '+'))
		return 0;
	for (tok = strtok(name, "+"); tok; tok = strtok(NULL, "+")) {
		tok = trim(tok);
		if (last) {
			if (!strcmp(last, "super") || !strcmp(last, "win") || !strcmp(last, "windows"))
				mod |= WLR_MODIFIER_LOGO;
			else if (!strcmp(last, "shift"))
				mod |= WLR_MODIFIER_SHIFT;
			else if (!strcmp(last, "ctrl") || !strcmp(last, "control"))
				mod |= WLR_MODIFIER_CTRL;
			else if (!strcmp(last, "alt"))
				mod |= WLR_MODIFIER_ALT;
			else
				return 0;
		}
		last = tok;
	}
	if (!last)
		return 0;
	squash(act, value, sizeof act);
	/* tty 3, send to tty 3 */
	if ((!strncmp(act, "tty", 3) && (n = atoi(act + 3)) >= 1 && n <= NSCR)
	|| (!strncmp(act, "sendtotty", 9) && (n = atoi(act + 9)) >= 1 && n <= NSCR)) {
		addkey(mod, keyname(last), act[0] == 't' ? ActView : ActSend, n - 1, NULL);
		return 1;
	}
	for (i = 0; i < LENGTH(acts); i++)
		if (!strcmp(act, acts[i].word)) {
			addkey(mod, keyname(last), acts[i].act, 0, NULL);
			return 1;
		}
	addkey(mod, keyname(last), ActRun, 0, value);
	return 1;
}

static void
addrule(const char *name, char *value)
{
	Rule *r;
	char *w, word[32];

	if (!*name || !(r = realloc(rules, (nrules + 1) * sizeof(Rule))))
		return;
	rules = r;
	r = &rules[nrules++];
	snprintf(r->name, sizeof r->name, "%s", name);
	r->scr = -1;
	r->full = 0;
	for (w = strtok(value, ","); w; w = strtok(NULL, ",")) {
		squash(word, w, sizeof word);
		if (!strncmp(word, "tty", 3) && atoi(word + 3) >= 1 && atoi(word + 3) <= NSCR)
			r->scr = atoi(word + 3) - 1;
		else if (!strcmp(word, "fullscreen"))
			r->full = 1;
	}
}

/* bottom line = network volume clock tty */
static void
setbar(char *value)
{
	static const char *names[] = { "commands", "network", "volume", "brightness", "battery", "date", "clock", "tty" };
	char *w;
	int n = 0, i;

	for (w = strtok(value, " \t,"); w && n < BarLast; w = strtok(NULL, " \t,"))
		for (i = 0; i < BarLast; i++)
			if (!strcasecmp(w, names[i]))
				barorder[n++] = i;
	barorder[n] = -1;
}

static int
haskey(unsigned int mod, xkb_keysym_t sym)
{
	int i;

	for (i = 0; i < nkeys; i++)
		if (keys[i].mod == mod && keys[i].keysym == sym)
			return 1;
	return 0;
}

static void
defkey(unsigned int mod, xkb_keysym_t sym, int act, int n)
{
	if (!haskey(mod, sym))
		addkey(mod, sym, act, n, NULL);
}

static void
readconfig(FILE *f, int firsttime, int depth)
{
	char line[1024], path[4096], *name, *value, *eq, key[64], *home;
	FILE *inc;

	while (fgets(line, sizeof line, f)) {
		if ((eq = strchr(line, '#')))
			*eq = '\0';
		if (!(eq = strchr(line, '=')))
			continue;
		*eq = '\0';
		name = trim(line);
		value = trim(eq + 1);
		for (eq = name; *eq; eq++)
			*eq = tolower((unsigned char)*eq);
		if (parsekey(name, value))
			continue;
		squash(key, name, sizeof key);
		if (!strncmp(name, "window ", 7) && !iskey(key, "windowcolour")) {
			addrule(trim(name + 7), value);
			continue;
		}
		if (iskey(key, "windowcolour"))
			snprintf(colname[ColWindow], sizeof colname[0], "%s", value);
		else if (iskey(key, "otherwindowscolour"))
			snprintf(colname[ColOther], sizeof colname[0], "%s", value);
		else if (iskey(key, "titlecolour"))
			snprintf(colname[ColTitle], sizeof colname[0], "%s", value);
		else if (iskey(key, "bottomlinecolour"))
			snprintf(colname[ColBar], sizeof colname[0], "%s", value);
		else if (iskey(key, "backgroundcolour"))
			snprintf(colname[ColBg], sizeof colname[0], "%s", value);
		else if (!strcmp(key, "wallpaper"))
			snprintf(wallpaper, sizeof wallpaper, "%s", value);
		else if (!strcmp(key, "textsize")) {
			if (firsttime)
				big = !strcasecmp(value, "big");
		}
		else if (!strcmp(key, "bordertyping"))
			typing = yes(value);
		else if (!strcmp(key, "typingspeed")) {
			squash(key, value, sizeof key);
			typespeed = !strcmp(key, "fast") ? 1500 : !strcmp(key, "slow") ? 250 : 600;
		}
		else if (!strcmp(key, "bottomline"))
			setbar(value);
		else if (!strcmp(key, "bottomlinecommand")) {
			if (nbarcmds < (int)LENGTH(barcmd))
				snprintf(barcmd[nbarcmds++], sizeof barcmd[0], "%s", value);
		}
		else if (!strcmp(key, "keyboardlayout"))
			snprintf(kblayout, sizeof kblayout, "%s", value);
		else if (!strcmp(key, "keyboardvariant"))
			snprintf(kbvariant, sizeof kbvariant, "%s", value);
		else if (!strcmp(key, "taptoclick"))
			tapclick = yes(value);
		else if (!strcmp(key, "naturalscrolling"))
			natural = yes(value);
		else if (!strcmp(key, "network"))
			shownetwork = yes(value);
		else if (!strcmp(key, "volume"))
			showvolume = yes(value);
		else if (!strcmp(key, "brightness"))
			showlight = yes(value);
		else if (!strcmp(key, "battery"))
			showbattery = yes(value);
		else if (!strcmp(key, "date"))
			showdate = yes(value);
		else if (!strcmp(key, "clock")) {
			squash(key, value, sizeof key);
			showclock = strcmp(key, "off") != 0;
			clock24 = strncmp(key, "12", 2) != 0;
		} else if (!strcmp(key, "terminal"))
			snprintf(terminal, sizeof terminal, "%s", value);
		else if (!strcmp(key, "appsmenu") || !strcmp(key, "menu"))
			snprintf(menu, sizeof menu, "%s", value);
		else if (!strcmp(key, "start")) {
			if (firsttime)
				run(value);
		}
		else if (!strcmp(key, "include")) {
			/* ~/x, or next to the config */
			if (value[0] == '~' && (home = getenv("HOME")))
				snprintf(path, sizeof path, "%s%s", home, value + 1);
			else if (value[0] != '/')
				snprintf(path, sizeof path, "%.*s/%s", (int)(strrchr(cfgpath, '/') - cfgpath), cfgpath, value);
			else
				snprintf(path, sizeof path, "%s", value);
			if (depth < 4 && (inc = fopen(path, "r"))) {
				readconfig(inc, firsttime, depth + 1);
				fclose(inc);
			} else
				fprintf(stderr, "torrent: can't include %s\n", path);
		}
		else
			fprintf(stderr, "torrent: %s: don't know '%s'\n", cfgpath, name);
	}
}

/* the layout jiggity wrote for x: wayland has no such file of its own */
static void
xkbfromx(void)
{
	char line[256], a[64], b[64];
	FILE *f;

	if (!(f = fopen("/etc/X11/xorg.conf.d/00-keyboard.conf", "r")))
		return;
	while (fgets(line, sizeof line, f))
		if (sscanf(line, " Option \"%63[^\"]\" \"%63[^\"]\"", a, b) == 2) {
			if (!strcmp(a, "XkbLayout") && !kblayout[0])
				snprintf(kblayout, sizeof kblayout, "%s", b);
			else if (!strcmp(a, "XkbVariant") && !kbvariant[0])
				snprintf(kbvariant, sizeof kbvariant, "%s", b);
		}
	fclose(f);
}

static void
loadconfig(int firsttime)
{
	FILE *f;
	int i;
	struct stat st;

	if (stat(cfgpath, &st) < 0 && (f = fopen(cfgpath, "w"))) {
		fputs(defaultconfig, f);
		fclose(f);
	}
	if (stat(cfgpath, &st) == 0)
		cfgmtime = st.st_mtime;

	for (i = 0; i < nkeys; i++)
		free(keys[i].cmd);
	nkeys = 0;
	nrules = 0;
	nbarcmds = 0;
	wallpaper[0] = kblayout[0] = kbvariant[0] = '\0';
	f = fopen(cfgpath, "r");
	if (!f) {
		/* no file and nowhere to write one: the defaults, straight from memory */
		f = fmemopen((void *)defaultconfig, sizeof defaultconfig - 1, "r");
		if (!f)
			return;
	}
	readconfig(f, firsttime, 0);
	fclose(f);
	if (!kblayout[0] && !getenv("XKB_DEFAULT_LAYOUT"))
		xkbfromx();

	/* these are there unless the key does something else */
	for (i = 0; i < NSCR; i++) {
		defkey(SUPER, XKB_KEY_1 + i, ActView, i);
		defkey(SUPER|SHIFT, XKB_KEY_1 + i, ActSend, i);
	}
	defkey(0, XKB_KEY_XF86AudioRaiseVolume, ActVolUp, 0);
	defkey(0, XKB_KEY_XF86AudioLowerVolume, ActVolDown, 0);
	defkey(0, XKB_KEY_XF86AudioMute, ActMute, 0);
	defkey(0, XKB_KEY_XF86MonBrightnessUp, ActLightUp, 0);
	defkey(0, XKB_KEY_XF86MonBrightnessDown, ActLightDown, 0);
	defkey(SUPER, XKB_KEY_Left, ActLeft, 0);
	defkey(SUPER, XKB_KEY_Right, ActRight, 0);
	defkey(SUPER, XKB_KEY_Up, ActMax, 0);
	defkey(SUPER, XKB_KEY_Down, ActRestore, 0);
	defkey(SUPER, XKB_KEY_l, ActLock, 0);
}

static void
loadcolours(void)
{
	unsigned int r, g, b;
	int i;

	for (i = 0; i < ColLast; i++) {
		if (sscanf(colourhex(colname[i]), "#%02x%02x%02x", &r, &g, &b) != 3)
			r = g = b = i == ColBg ? 0 : 0xaa;
		col[i][0] = r / 255.0;
		col[i][1] = g / 255.0;
		col[i][2] = b / 255.0;
		col[i][3] = 1;
	}
}

/* ---- drawing ---- */

static void
bufdestroy(struct wlr_buffer *wb)
{
	Buf *b = wl_container_of(wb, b, base);

	cairo_surface_destroy(b->s);
	free(b);
}

static bool
bufbegin(struct wlr_buffer *wb, uint32_t flags, void **data, uint32_t *format, size_t *stride)
{
	Buf *b = wl_container_of(wb, b, base);

	if (flags & WLR_BUFFER_DATA_PTR_ACCESS_WRITE)
		return false;
	*data = cairo_image_surface_get_data(b->s);
	*format = DRM_FORMAT_ARGB8888;
	*stride = cairo_image_surface_get_stride(b->s);
	return true;
}

static void
bufend(struct wlr_buffer *wb)
{
}

static const struct wlr_buffer_impl bufimpl = {
	.destroy = bufdestroy,
	.begin_data_ptr_access = bufbegin,
	.end_data_ptr_access = bufend,
};

static Buf *
newbuf(int w, int h, cairo_t **cr)
{
	Buf *b;

	if (!(b = calloc(1, sizeof *b)))
		die("calloc failed");
	b->s = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, MAX(w, 1), MAX(h, 1));
	wlr_buffer_init(&b->base, &bufimpl, MAX(w, 1), MAX(h, 1));
	*cr = cairo_create(b->s);
	cairo_set_font_options(*cr, fontopts);
	cairo_select_font_face(*cr, "VGA", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
	cairo_set_font_size(*cr, fontpx);
	return b;
}

/* done drawing: wlroots shows it from now on, and lets go of the old one */
static void
putbuf(struct wlr_scene_buffer *sb, Buf *b, cairo_t *cr)
{
	cairo_destroy(cr);
	cairo_surface_flush(b->s);
	wlr_scene_buffer_set_buffer(sb, &b->base);
	wlr_buffer_drop(&b->base);
}

static void
fill(cairo_t *cr, int c, int x, int y, int w, int h)
{
	cairo_set_source_rgba(cr, col[c][0], col[c][1], col[c][2], col[c][3]);
	cairo_rectangle(cr, x, y, w, h);
	cairo_fill(cr);
}

static void
text(cairo_t *cr, int c, int x, int y, const char *s)
{
	cairo_set_source_rgba(cr, col[c][0], col[c][1], col[c][2], col[c][3]);
	cairo_move_to(cr, x, y + fasc);
	cairo_show_text(cr, s);
}

/* the console's font, cell by cell: no smoothing, like the vga card drew it */
static void
fontsetup(void)
{
	cairo_surface_t *s = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 1, 1);
	cairo_t *cr = cairo_create(s);
	cairo_font_extents_t fe;

	fontpx = big ? 32 : 16;
	fontopts = cairo_font_options_create();
	cairo_font_options_set_antialias(fontopts, CAIRO_ANTIALIAS_NONE);
	cairo_font_options_set_hint_style(fontopts, CAIRO_HINT_STYLE_NONE);
	cairo_font_options_set_hint_metrics(fontopts, CAIRO_HINT_METRICS_ON);
	cairo_set_font_options(cr, fontopts);
	cairo_select_font_face(cr, "VGA", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
	cairo_set_font_size(cr, fontpx);
	cairo_font_extents(cr, &fe);
	cw = MAX((int)(fe.max_x_advance + 0.5), 1);
	ch = MAX((int)(fe.ascent + fe.descent + 0.5), 1);
	fasc = (int)(fe.ascent + 0.5);
	cairo_destroy(cr);
	cairo_surface_destroy(s);
}

static void
kick(void)
{
	Output *o;

	for (o = outputs; o; o = o->next)
		wlr_output_schedule_frame(o->wlr);
}

/* the border, the way it's typed: along the top, down the right, back along the bottom, up the left.
 * cell i of it, as a place and a character */
static void
framecell(Client *c, int i, int *x, int *y, char *ch8, int *colour)
{
	int cols = c->w / cw + 2, rows = c->h / ch;
	int n = MIN((int)strlen(c->name), MAX(cols - 10, 0));
	int bc = c == sel ? ColWindow : ColOther;

	*colour = bc;
	if (i < cols) {
		/* ┌─[ name ]───[x]┐ */
		*x = i, *y = 0;
		if (i == 0) strcpy(ch8, "┌");
		else if (i == 1) strcpy(ch8, "─");
		else if (i == 2) strcpy(ch8, "[");
		else if (i < n + 5) {
			*colour = ColTitle;
			ch8[0] = i == 3 || i == n + 4 ? ' ' : c->name[i - 4];
			ch8[1] = '\0';
		}
		else if (i == n + 5) strcpy(ch8, "]");
		else if (i == cols - 4) strcpy(ch8, "[");
		else if (i == cols - 3) strcpy(ch8, "x");
		else if (i == cols - 2) strcpy(ch8, "]");
		else if (i == cols - 1) strcpy(ch8, "┐");
		else strcpy(ch8, "─");
		return;
	}
	i -= cols;
	if (i < rows) {
		*x = cols - 1, *y = i + 1;
		strcpy(ch8, "│");
		return;
	}
	i -= rows;
	if (i < cols) {
		*x = cols - 1 - i, *y = rows + 1;
		strcpy(ch8, i == 0 ? "┘" : i == cols - 1 ? "└" : "─");
		return;
	}
	i -= cols;
	*x = 0, *y = rows - i;
	strcpy(ch8, "│");
}

/* a cell goes on whichever of the four edges it's on */
static void
putcell(cairo_t **cr, Client *c, int x, int y, const char *g, int colour)
{
	int rows = c->h / ch, e, px = 0, py = 0;

	if (y == 0)
		e = 0, px = x * cw;
	else if (y == rows + 1)
		e = 1, px = x * cw;
	else
		e = x == 0 ? 2 : 3, py = (y - 1) * ch;
	fill(cr[e], ColBg, px, py, cw, ch);
	text(cr[e], colour, px, py, g);
}

/* ┌─[ name ]───[x]┐ : as much of it as is typed, and a cursor after while it types */
static void
drawframe(Client *c)
{
	cairo_t *cr[4];
	Buf *b[4];
	char g[8];
	int cols, rows, i, x, y, colour, n;

	if (!c->tree || c->unmanaged || c->isfull || (!c->mapped && !c->out) || !c->w)
		return;
	cols = c->w / cw + 2;
	rows = c->h / ch;
	c->total = 2 * cols + 2 * rows;
	n = MIN(c->typed, c->total);
	b[0] = newbuf(cols * cw, ch, &cr[0]);
	b[1] = newbuf(cols * cw, ch, &cr[1]);
	b[2] = newbuf(cw, rows * ch, &cr[2]);
	b[3] = newbuf(cw, rows * ch, &cr[3]);
	for (i = 0; i < n; i++) {
		framecell(c, i, &x, &y, g, &colour);
		putcell(cr, c, x, y, g, colour);
	}
	if (n < c->total) {
		framecell(c, n, &x, &y, g, &colour);
		putcell(cr, c, x, y, "█", c == sel ? ColWindow : ColOther);
	}
	for (i = 0; i < 4; i++)
		putbuf(c->edge[i], b[i], cr[i]);
	wlr_scene_node_set_position(&c->edge[1]->node, 0, (rows + 1) * ch);
	wlr_scene_node_set_position(&c->edge[2]->node, 0, ch);
	wlr_scene_node_set_position(&c->edge[3]->node, (cols - 1) * cw, ch);
}

static struct wlr_surface *
csurface(Client *c)
{
	return c->xdg ? c->xdg->base->surface : c->xw ? c->xw->surface : NULL;
}

static void
kbfocus(struct wlr_surface *s)
{
	struct wlr_keyboard *kb = wlr_seat_get_keyboard(seat);

	if (!s)
		wlr_seat_keyboard_notify_clear_focus(seat);
	else if (kb)
		wlr_seat_keyboard_notify_enter(seat, s, kb->keycodes, kb->num_keycodes, &kb->modifiers);
	else
		wlr_seat_keyboard_notify_enter(seat, s, NULL, 0, NULL);
}

/* the border's typed: out comes the window */
static void
showcontent(Client *c)
{
	wlr_scene_node_set_enabled(&c->back->node, true);
	wlr_scene_node_set_enabled(&c->content->node, true);
	if (sel == c && !exclusive && !locked)
		kbfocus(csurface(c));
}

/* the typing, by the clock: 1 while some border is still typing in or away */
static int
animate(void)
{
	Client *c, *g, **pg;
	int busy = 0, want;
	long long now = ms();

	for (c = clients; c; c = c->next) {
		if (!c->mapped || c->typed >= c->total)
			continue;
		want = MIN((now - c->born) * typespeed / 1000, c->total);
		if (want > c->typed) {
			c->typed = want;
			drawframe(c);
		}
		if (c->typed >= c->total) {
			c->typed = INT32_MAX;
			drawframe(c);
			showcontent(c);
		} else
			busy = 1;
	}
	for (pg = &ghosts; (g = *pg);) {
		want = g->total - (now - g->born) * typespeed / 1000;
		if (want <= 0) {
			*pg = g->next;
			wlr_scene_node_destroy(&g->tree->node);
			free(g);
			continue;
		}
		if (want < g->typed) {
			g->typed = want;
			drawframe(g);
		}
		busy = 1;
		pg = &g->next;
	}
	return busy;
}

/* a closed window's border, left behind to type itself away */
static void
ghost(Client *c)
{
	Client *g;
	int i;

	if (!typing || c->scr != cur || c->isfull || c->typed < c->total || !(g = calloc(1, sizeof *g)))
		return;
	memcpy(g->name, c->name, sizeof g->name);
	g->w = c->w;
	g->h = c->h;
	g->scr = cur;
	g->out = 1;
	g->tree = wlr_scene_tree_create(wintree);
	wlr_scene_node_set_position(&g->tree->node, ox + c->x, oy + c->y);
	for (i = 0; i < 4; i++)
		g->edge[i] = wlr_scene_buffer_create(g->tree, NULL);
	g->total = g->typed = 2 * (g->w / cw + 2) + 2 * (g->h / ch);
	g->born = ms();
	g->next = ghosts;
	ghosts = g;
	drawframe(g);
	kick();
}

/* where everything of a window goes, from its place and size */
static void
place(Client *c)
{
	int gx0 = 0, gy0 = 0, full = c->isfull, i;

	if (c->xdg) {
		gx0 = c->xdg->base->geometry.x;
		gy0 = c->xdg->base->geometry.y;
	}
	wlr_scene_node_set_position(&c->tree->node, full ? ox : ox + c->x, full ? oy : oy + c->y);
	for (i = 0; i < 4; i++)
		wlr_scene_node_set_enabled(&c->edge[i]->node, !full);
	wlr_scene_node_set_position(&c->back->node, full ? 0 : cw, full ? 0 : ch);
	wlr_scene_rect_set_size(c->back, full ? sw : c->w, full ? sh : c->h);
	wlr_scene_node_set_position(&c->content->node, (full ? 0 : cw) - gx0, (full ? 0 : ch) - gy0);
	/* a window that's bigger than it was told doesn't spill out of its frame */
	if (c->surf)
		wlr_scene_subsurface_tree_set_clip(&c->surf->node,
			&(struct wlr_box){ gx0, gy0, full ? sw : c->w, full ? sh : c->h });
}

/* tells the program its size, and x11 ones where they are too */
static void
cconfigure(Client *c)
{
	if (c->xdg && c->xdg->base->initialized)
		wlr_xdg_toplevel_set_size(c->xdg, c->isfull ? sw : c->w, c->isfull ? sh : c->h);
	else if (c->xw) {
		if (c->isfull)
			wlr_xwayland_surface_configure(c->xw, ox, oy, sw, sh);
		else
			wlr_xwayland_surface_configure(c->xw, ox + c->x + cw, oy + c->y + ch, c->w, c->h);
	}
}

/* ---- the bottom line ---- */

static void
readvolume(void)
{
	char buf[128];
	float v;

	vol = -1;
	runwait("wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null", buf, sizeof buf);
	if (sscanf(buf, "Volume: %f", &v) == 1) {
		vol = v * 100 + 0.5;
		muted = strstr(buf, "MUTED") != NULL;
	}
}

/* the first backlight there is. the video group may write it */
static void
findbacklight(void)
{
	DIR *d;
	struct dirent *e;

	backlight[0] = '\0';
	if (!(d = opendir("/sys/class/backlight")))
		return;
	while ((e = readdir(d)))
		if (e->d_name[0] != '.') {
			snprintf(backlight, sizeof backlight, "/sys/class/backlight/%s", e->d_name);
			break;
		}
	closedir(d);
}

static int
light(void)
{
	long now, max;

	if (!backlight[0] || (now = readnum(backlight, "brightness")) < 0 || (max = readnum(backlight, "max_brightness")) <= 0)
		return -1;
	return (now * 100 + max / 2) / max;
}

static void
setlight(int step)
{
	char path[300];
	long max;
	int pct = light();
	FILE *f;

	if (pct < 0 || (max = readnum(backlight, "max_brightness")) <= 0)
		return;
	/* 5% steps, but never all the way to black */
	pct = MIN(MAX(pct + step, 1), 100);
	snprintf(path, sizeof path, "%s/brightness", backlight);
	if ((f = fopen(path, "w"))) {
		fprintf(f, "%ld\n", MAX(pct * max / 100, 1));
		fclose(f);
	} else
		fprintf(stderr, "torrent: %s: can't write it, are you in the video group?\n", path);
}

static void
network(char *s, size_t n)
{
	DIR *d;
	struct dirent *e;
	char path[512], state[32];
	int wired = 0, wifi = 0;

	snprintf(s, n, "offline");
	if (!(d = opendir("/sys/class/net")))
		return;
	while ((e = readdir(d))) {
		if (e->d_name[0] == '.' || !strcmp(e->d_name, "lo"))
			continue;
		snprintf(path, sizeof path, "/sys/class/net/%s/operstate", e->d_name);
		if (!readfile(path, state, sizeof state) || strcmp(state, "up"))
			continue;
		snprintf(path, sizeof path, "/sys/class/net/%s/wireless", e->d_name);
		if (access(path, F_OK) == 0)
			wifi = 1;
		else
			wired = 1;
	}
	closedir(d);
	snprintf(s, n, "%s", wired ? "wired" : wifi ? "wifi" : "offline");
}

/* all batteries together: a T480 has two */
static int
battery(char *s, size_t n)
{
	DIR *d;
	struct dirent *e;
	char dir[512], path[600], buf[32];
	long now = 0, full = 0, a, b;
	int charging = 0;

	if (!(d = opendir("/sys/class/power_supply")))
		return 0;
	while ((e = readdir(d))) {
		snprintf(dir, sizeof dir, "/sys/class/power_supply/%s", e->d_name);
		snprintf(path, sizeof path, "%s/type", dir);
		if (!readfile(path, buf, sizeof buf) || strcmp(buf, "Battery"))
			continue;
		snprintf(path, sizeof path, "%s/status", dir);
		if (readfile(path, buf, sizeof buf) && !strcmp(buf, "Charging"))
			charging = 1;
		if ((a = readnum(dir, "energy_now")) < 0 || (b = readnum(dir, "energy_full")) <= 0) {
			a = readnum(dir, "charge_now");
			b = readnum(dir, "charge_full");
		}
		if (a >= 0 && b > 0) {
			now += a;
			full += b;
		}
	}
	closedir(d);
	if (!full)
		return 0;
	snprintf(s, n, "bat %ld%%%s", now * 100 / full, charging ? "+" : "");
	return 1;
}

/* your own bottom line commands, every 5 seconds from tick */
static void
runbarcmds(void)
{
	int i;

	for (i = 0; i < nbarcmds; i++) {
		runwait(barcmd[i], barout[i], sizeof barout[i]);
		barout[i][strcspn(barout[i], "\n")] = '\0';
	}
}

static void
drawbar(void)
{
	char seg[16][64];
	int kind[16], n = 0, i, j, x, len = 0, pct;
	time_t t = time(NULL);
	struct tm *tm = localtime(&t);
	cairo_t *cr;
	Buf *b;

	if (!sw || !cw)
		return;
	for (j = 0; barorder[j] >= 0 && n < (int)LENGTH(seg) - 4; j++)
		switch (barorder[j]) {
		case BarCommands:
			for (i = 0; i < nbarcmds; i++)
				if (barout[i][0]) {
					snprintf(seg[n], sizeof seg[n], "%s", barout[i]);
					kind[n++] = SegNone;
				}
			break;
		case BarNet:
			if (shownetwork) {
				network(seg[n], sizeof seg[n]);
				kind[n++] = SegNet;
			}
			break;
		case BarVol:
			if (showvolume && vol >= 0) {
				snprintf(seg[n], sizeof seg[n], muted ? "vol muted" : "vol %d%%", vol);
				kind[n++] = SegVol;
			}
			break;
		case BarLight:
			if (showlight && (pct = light()) >= 0) {
				snprintf(seg[n], sizeof seg[n], "light %d%%", pct);
				kind[n++] = SegLight;
			}
			break;
		case BarBattery:
			if (showbattery && battery(seg[n], sizeof seg[n]))
				kind[n++] = SegNone;
			break;
		case BarDate:
			if (showdate) {
				strftime(seg[n], sizeof seg[n], "%a %d %b", tm);
				kind[n++] = SegNone;
			}
			break;
		case BarClock:
			if (showclock) {
				strftime(seg[n], sizeof seg[n], clock24 ? "%H:%M" : "%I:%M %p", tm);
				kind[n++] = SegNone;
			}
			break;
		case BarTty:
			snprintf(seg[n], sizeof seg[n], "tty%d", cur + 1);
			kind[n++] = SegNone;
			break;
		}

	for (i = 0; i < n; i++)
		len += ulen(seg[i]) + 2;
	b = newbuf(sw, ch, &cr);
	fill(cr, ColBg, 0, 0, sw, ch);
	x = sw - len * cw;
	nsegs = 0;
	for (i = 0; i < n; i++) {
		text(cr, ColBar, x, 0, seg[i]);
		if (nsegs < (int)LENGTH(segs)) {
			segs[nsegs].x0 = x;
			segs[nsegs].x1 = x + ulen(seg[i]) * cw;
			segs[nsegs++].seg = kind[i];
		}
		x += (ulen(seg[i]) + 2) * cw;
	}
	putbuf(barbuf, b, cr);
}

static void
setvolume(const char *how)
{
	char cmd[128];

	if (!strcmp(how, "mute"))
		snprintf(cmd, sizeof cmd, "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle");
	else
		snprintf(cmd, sizeof cmd, "wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ %s", how);
	runwait(cmd, NULL, 0);
	readvolume();
	drawbar();
}

/* fills the screen with it, cut to fit */
static void
drawwallpaper(void)
{
	cairo_surface_t *img = NULL;
	cairo_t *cr;
	Buf *b;
	char path[4096], *home = getenv("HOME");
	double s;
	int iw, ih;

	if (wallpaper[0] == '~' && home)
		snprintf(path, sizeof path, "%s%s", home, wallpaper + 1);
	else
		snprintf(path, sizeof path, "%s", wallpaper);
	if (!wallpaper[0] || !sw || !(img = cairo_image_surface_create_from_png(path))
	|| cairo_surface_status(img) != CAIRO_STATUS_SUCCESS) {
		if (img)
			cairo_surface_destroy(img);
		wlr_scene_buffer_set_buffer(wallbuf, NULL);
		return;
	}
	iw = cairo_image_surface_get_width(img);
	ih = cairo_image_surface_get_height(img);
	s = MAX((double)sw / iw, (double)sh / ih);
	b = newbuf(sw, sh, &cr);
	cairo_translate(cr, (sw - iw * s) / 2, (sh - ih * s) / 2);
	cairo_scale(cr, s, s);
	cairo_set_source_surface(cr, img, 0, 0);
	cairo_paint(cr);
	putbuf(wallbuf, b, cr);
	wlr_scene_node_set_position(&wallbuf->node, ox, oy);
	cairo_surface_destroy(img);
}

/* ---- notifications: torrent is org.freedesktop.Notifications ---- */

#define NOTIFCOLS 48

/* characters, not bytes */
static int
ulen(const char *s)
{
	int n = 0;

	for (; *s; s++)
		n += (*s & 0xc0) != 0x80;
	return n;
}

/* the first n characters of s */
static void
ucut(char *dst, const char *s, int n, size_t size)
{
	size_t i = 0;

	for (; *s && i < size - 1; s++) {
		if ((*s & 0xc0) != 0x80 && n-- <= 0)
			break;
		dst[i++] = *s;
	}
	dst[i] = '\0';
}

/* <b>bold</b> &amp; co. as plain text */
static void
plain(char *dst, const char *s, size_t size)
{
	static const char *ent[][2] = { { "&amp;", "&" }, { "&lt;", "<" }, { "&gt;", ">" }, { "&quot;", "\"" }, { "&apos;", "'" } };
	size_t i = 0;
	unsigned int e;

	while (*s && i < size - 1) {
		if (*s == '<' && strchr(s, '>')) {
			s = strchr(s, '>') + 1;
			continue;
		}
		for (e = 0; e < LENGTH(ent); e++)
			if (!strncmp(s, ent[e][0], strlen(ent[e][0])))
				break;
		if (e < LENGTH(ent)) {
			dst[i++] = ent[e][1][0];
			s += strlen(ent[e][0]);
		} else
			dst[i++] = *s == '\n' || *s == '\t' ? ' ' : *s, s++;
	}
	dst[i] = '\0';
}

static void
drawnotif(Notif *n)
{
	char buf[1024], *p;
	int cols = n->w / cw, i;
	cairo_t *cr;
	Buf *b = newbuf(n->w, n->h, &cr);

	fill(cr, ColBg, 0, 0, n->w, n->h);
	text(cr, ColWindow, 0, 0, "┌─[");
	snprintf(buf, sizeof buf, " %s ", n->app);
	text(cr, ColTitle, 3 * cw, 0, buf);
	p = buf + sprintf(buf, "]");
	for (i = ulen(n->app) + 6; i < cols - 1; i++)
		p += sprintf(p, "─");
	sprintf(p, "┐");
	text(cr, ColWindow, (ulen(n->app) + 5) * cw, 0, buf);
	for (i = 0; i < n->nlines; i++) {
		text(cr, ColWindow, 0, (i + 1) * ch, "│");
		text(cr, i ? ColWindow : ColTitle, 2 * cw, (i + 1) * ch, n->line[i]);
		text(cr, ColWindow, (cols - 1) * cw, (i + 1) * ch, "│");
	}
	p = buf + sprintf(buf, "└");
	for (i = 2; i < cols; i++)
		p += sprintf(p, "─");
	sprintf(p, "┘");
	text(cr, ColWindow, 0, (n->nlines + 1) * ch, buf);
	putbuf(n->buf, b, cr);
}

/* stacked down from the top right corner, newest last */
static void
placenotifs(void)
{
	Notif *n;
	int y = 0;

	for (n = notifs; n; n = n->next) {
		wlr_scene_node_set_position(&n->buf->node, ox + sw / MAX(cw, 1) * cw - n->w, oy + y);
		drawnotif(n);
		y += n->h;
	}
}

static void
closenotif(Notif *n, unsigned int why)
{
	Notif **pn;
	DBusMessage *m;
	dbus_uint32_t id = n->id, reason = why;

	for (pn = &notifs; *pn != n; pn = &(*pn)->next);
	*pn = n->next;
	wlr_scene_node_destroy(&n->buf->node);
	free(n);
	placenotifs();
	if (bus && (m = dbus_message_new_signal("/org/freedesktop/Notifications",
	    "org.freedesktop.Notifications", "NotificationClosed"))) {
		dbus_message_append_args(m, DBUS_TYPE_UINT32, &id, DBUS_TYPE_UINT32, &reason, DBUS_TYPE_INVALID);
		dbus_connection_send(bus, m, NULL);
		dbus_message_unref(m);
	}
}

static unsigned int
notify(const char *app, unsigned int replaces, const char *summary, const char *body, int timeout)
{
	Notif *n, **pn;
	char buf[1024], word[256], *p, *w;
	int i, len;

	for (n = notifs; n && (!replaces || n->id != replaces); n = n->next);
	if (!n) {
		if (!(n = calloc(1, sizeof *n)))
			return 0;
		n->kind = KNotif;
		n->id = ++lastid;
		n->buf = wlr_scene_buffer_create(notiftree, NULL);
		n->buf->node.data = n;
		for (pn = &notifs; *pn; pn = &(*pn)->next);
		*pn = n;
	}
	ucut(n->app, *app ? app : "notification", NOTIFCOLS - 10, sizeof n->app);
	plain(buf, summary, sizeof buf);
	ucut(n->line[0], buf, NOTIFCOLS - 4, sizeof n->line[0]);
	n->nlines = 1;

	/* the body, a word at a time, in up to 3 lines under the summary */
	plain(buf, body, sizeof buf);
	for (p = buf; (w = strsep(&p, " "));) {
		if (!*w)
			continue;
		ucut(word, w, NOTIFCOLS - 4, sizeof word);
		i = n->nlines - 1;
		if (i > 0 && ulen(n->line[i]) + 1 + ulen(word) <= NOTIFCOLS - 4) {
			len = strlen(n->line[i]);
			snprintf(n->line[i] + len, sizeof n->line[i] - len, " %s", word);
		} else if (n->nlines < 4)
			snprintf(n->line[n->nlines++], sizeof n->line[0], "%s", word);
		else
			break;
	}
	n->w = 0;
	for (i = 0; i < n->nlines; i++)
		n->w = MAX(n->w, ulen(n->line[i]) + 4);
	n->w = MAX(n->w, ulen(n->app) + 10) * cw;
	n->h = (n->nlines + 2) * ch;
	/* -1: the usual 5 seconds. 0: until it's clicked */
	n->until = timeout == 0 ? 0 : time(NULL) + (timeout < 0 ? 5 : (timeout + 999) / 1000);
	placenotifs();
	return n->id;
}

static void
expirenotifs(void)
{
	Notif *n, *next;
	time_t now = time(NULL);

	for (n = notifs; n; n = next) {
		next = n->next;
		if (n->until && n->until <= now)
			closenotif(n, 1);
	}
}

static void
arg(DBusMessageIter *it, int type, void *v)
{
	if (dbus_message_iter_get_arg_type(it) == type)
		dbus_message_iter_get_basic(it, v);
	dbus_message_iter_next(it);
}

static void
dbusmessage(DBusMessage *m)
{
	static const char *iface = "org.freedesktop.Notifications";
	static const char *caps[] = { "body" }, **cp = caps;
	static const char *info[] = { "torrent", "Chamesle", VERSION, "1.2" };
	const char *app = "", *icon = "", *summary = "", *body = "";
	dbus_uint32_t replaces = 0, id;
	dbus_int32_t timeout = -1;
	DBusMessageIter it;
	DBusMessage *r;
	Notif *n;

	if (dbus_message_get_type(m) != DBUS_MESSAGE_TYPE_METHOD_CALL)
		return;
	if (dbus_message_is_method_call(m, iface, "Notify")) {
		dbus_message_iter_init(m, &it);
		arg(&it, DBUS_TYPE_STRING, &app);
		arg(&it, DBUS_TYPE_UINT32, &replaces);
		arg(&it, DBUS_TYPE_STRING, &icon);
		arg(&it, DBUS_TYPE_STRING, &summary);
		arg(&it, DBUS_TYPE_STRING, &body);
		dbus_message_iter_next(&it);	/* actions: not here */
		dbus_message_iter_next(&it);	/* hints */
		arg(&it, DBUS_TYPE_INT32, &timeout);
		id = notify(app, replaces, summary, body, timeout);
		r = dbus_message_new_method_return(m);
		dbus_message_append_args(r, DBUS_TYPE_UINT32, &id, DBUS_TYPE_INVALID);
	} else if (dbus_message_is_method_call(m, iface, "CloseNotification")) {
		dbus_message_iter_init(m, &it);
		id = 0;
		arg(&it, DBUS_TYPE_UINT32, &id);
		for (n = notifs; n && n->id != id; n = n->next);
		if (n)
			closenotif(n, 3);
		r = dbus_message_new_method_return(m);
	} else if (dbus_message_is_method_call(m, iface, "GetCapabilities")) {
		r = dbus_message_new_method_return(m);
		dbus_message_append_args(r, DBUS_TYPE_ARRAY, DBUS_TYPE_STRING, &cp, 1, DBUS_TYPE_INVALID);
	} else if (dbus_message_is_method_call(m, iface, "GetServerInformation")) {
		r = dbus_message_new_method_return(m);
		dbus_message_append_args(r, DBUS_TYPE_STRING, &info[0], DBUS_TYPE_STRING, &info[1],
		                         DBUS_TYPE_STRING, &info[2], DBUS_TYPE_STRING, &info[3], DBUS_TYPE_INVALID);
	} else
		r = dbus_message_new_error(m, DBUS_ERROR_UNKNOWN_METHOD, "torrent only shows notifications");
	if (r) {
		dbus_connection_send(bus, r, NULL);
		dbus_message_unref(r);
	}
}

/* no session bus, or another program shows notifications already (like mako): then not us */
static void
setupbus(void)
{
	DBusError err;

	dbus_error_init(&err);
	if (!(bus = dbus_bus_get(DBUS_BUS_SESSION, &err))) {
		dbus_error_free(&err);
		return;
	}
	dbus_connection_set_exit_on_disconnect(bus, FALSE);
	if (dbus_bus_request_name(bus, "org.freedesktop.Notifications", DBUS_NAME_FLAG_DO_NOT_QUEUE, &err)
	    != DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER) {
		dbus_error_free(&err);
		bus = NULL;
	}
}

static void
readbus(void)
{
	DBusMessage *m;

	if (!bus)
		return;
	dbus_connection_read_write(bus, 0);
	while ((m = dbus_connection_pop_message(bus))) {
		dbusmessage(m);
		dbus_message_unref(m);
	}
	dbus_connection_flush(bus);
}

static int
busready(int fd, uint32_t mask, void *data)
{
	readbus();
	return 0;
}

/* ---- windows ---- */

static Client *
topclient(void)
{
	Client *c;

	for (c = clients; c && (!c->mapped || c->unmanaged || c->scr != cur); c = c->next);
	return c;
}

static void
cactivate(Client *c, int on)
{
	if (c->xdg && c->xdg->base->initialized)
		wlr_xdg_toplevel_set_activated(c->xdg, on);
	else if (c->xw)
		wlr_xwayland_surface_activate(c->xw, on);
}

/* focus(NULL): nothing has the keyboard */
static void
focus(Client *c)
{
	Client *old = sel;

	if (c && (!c->mapped || c->unmanaged))
		return;
	sel = c;
	if (old && old != c) {
		drawframe(old);
		cactivate(old, 0);
	}
	if (!c) {
		if (!exclusive && !locked)
			kbfocus(NULL);
		return;
	}
	wlr_scene_node_raise_to_top(&c->tree->node);
	drawframe(c);
	cactivate(c, 1);
	if (c->typed >= c->total && !exclusive && !locked)
		kbfocus(csurface(c));
}

static void
updatetitle(Client *c)
{
	const char *t = c->xdg ? c->xdg->title : c->xw ? c->xw->title : NULL;

	snprintf(c->name, sizeof c->name, "%s", t ? t : "");
}

/* sizes are whole character cells, like a terminal */
static void
resize(Client *c, int w, int h)
{
	w = MIN(MAX(w / cw, 10), (sw - c->x) / cw - 2) * cw;
	h = MIN(MAX(h / ch, 3), (wh - c->y) / ch - 2) * ch;
	if (w == c->w && h == c->h)
		return;
	c->w = w;
	c->h = h;
	cconfigure(c);
	place(c);
	drawframe(c);
}

static void
move(Client *c, int x, int y)
{
	if (x == c->x && y == c->y)
		return;
	c->x = x;
	c->y = y;
	place(c);
	if (c->xw)
		cconfigure(c);
}

static Rule *
findrule(Client *c)
{
	const char *a = c->xdg ? c->xdg->app_id : c->xw ? c->xw->class : NULL;
	const char *b = c->xw ? c->xw->instance : NULL;
	int i;

	for (i = 0; i < nrules; i++)
		if ((a && !strcasecmp(a, rules[i].name)) || (b && !strcasecmp(b, rules[i].name)))
			return &rules[i];
	return NULL;
}

static Client *
newclient(void)
{
	Client *c;
	int i;

	if (!(c = calloc(1, sizeof *c)))
		die("calloc failed");
	c->kind = KClient;
	c->scr = cur;
	c->tree = wlr_scene_tree_create(wintree);
	c->tree->node.data = c;
	for (i = 0; i < 4; i++)
		c->edge[i] = wlr_scene_buffer_create(c->tree, NULL);
	c->back = wlr_scene_rect_create(c->tree, 1, 1, col[ColBg]);
	c->content = wlr_scene_tree_create(c->tree);
	wlr_scene_node_set_enabled(&c->tree->node, false);
	c->next = clients;
	clients = c;
	return c;
}

static void
freeclient(Client *c)
{
	Client **pc;

	for (pc = &clients; *pc != c; pc = &(*pc)->next);
	*pc = c->next;
	if (sel == c)
		sel = NULL;
	if (grabc == c)
		grab = GrabNone, grabc = NULL;
	wlr_scene_node_destroy(&c->tree->node);
	free(c);
}

/* a window comes up: in the middle, its border typing in first */
static void
manage(Client *c)
{
	Rule *rule = findrule(c);
	int w, h;

	c->mapped = 1;
	if (c->xdg) {
		w = c->xdg->base->geometry.width;
		h = c->xdg->base->geometry.height;
	} else {
		w = c->xw->width;
		h = c->xw->height;
	}
	if (w <= 0 || h <= 0)
		w = 640, h = 480;
	c->scr = rule && rule->scr >= 0 ? rule->scr : cur;
	c->typed = typing && !(rule && rule->full) ? 0 : INT32_MAX;
	c->born = ms();
	updatetitle(c);
	c->w = c->h = 0;
	c->x = MAX(0, (sw - w) / 2 - cw) / cw * cw;
	c->y = MAX(0, (wh - h) / 2 - ch) / ch * ch;
	resize(c, w, h);
	place(c);
	wlr_scene_node_set_enabled(&c->back->node, c->typed >= c->total);
	wlr_scene_node_set_enabled(&c->content->node, c->typed >= c->total);
	wlr_scene_node_set_enabled(&c->tree->node, c->scr == cur);
	if (c->typed < c->total)
		kick();
	if (c->scr == cur)
		focus(c);
	if ((rule && rule->full) || (c->xdg && c->xdg->requested.fullscreen) || (c->xw && c->xw->fullscreen))
		setfullscreen(c, 1);
}

static void
unmanage(Client *c)
{
	if (grabc == c)
		grab = GrabNone, grabc = NULL;
	ghost(c);
	if (c->isfull) {
		c->isfull = 0;
		wlr_scene_node_reparent(&c->tree->node, wintree);
	}
	c->mapped = 0;
	wlr_scene_node_set_enabled(&c->tree->node, false);
	if (sel == c) {
		sel = NULL;
		focus(topclient());
	}
}

/* asks first, like every window manager should */
static void
closeclient(Client *c)
{
	if (c->xdg)
		wlr_xdg_toplevel_send_close(c->xdg);
	else if (c->xw)
		wlr_xwayland_surface_close(c->xw);
}

static void
setfullscreen(Client *c, int full)
{
	if (full == c->isfull || !c->mapped)
		return;
	if (c->typed < c->total) {
		c->typed = INT32_MAX;
		showcontent(c);
	}
	c->isfull = full;
	if (full) {
		c->oldx = c->x; c->oldy = c->y; c->oldw = c->w; c->oldh = c->h;
		/* over the bottom line too */
		wlr_scene_node_reparent(&c->tree->node, fulltree);
	} else {
		wlr_scene_node_reparent(&c->tree->node, wintree);
		c->x = c->oldx; c->y = c->oldy;
		c->w = c->h = 0;
		resize(c, c->oldw, c->oldh);
	}
	if (c->xdg && c->xdg->base->initialized)
		wlr_xdg_toplevel_set_fullscreen(c->xdg, full);
	else if (c->xw)
		wlr_xwayland_surface_set_fullscreen(c->xw, full);
	cconfigure(c);
	place(c);
	drawframe(c);
	wlr_scene_node_raise_to_top(&c->tree->node);
}

/* super+arrows: half the screen, all of it, or back where it was */
static void
snap(Client *c, int how)
{
	int cols = sw / cw, rows = wh / ch, half = cols / 2;

	if (c->isfull)
		return;
	if (how == ActRestore) {
		if (c->snapped) {
			move(c, c->sx, c->sy);
			resize(c, c->sw, c->sh);
		}
		c->snapped = 0;
		return;
	}
	if (!c->snapped) {
		c->sx = c->x; c->sy = c->y; c->sw = c->w; c->sh = c->h;
		c->snapped = 1;
	}
	if (how == ActLeft) {
		move(c, 0, 0);
		resize(c, (half - 2) * cw, (rows - 2) * ch);
	} else if (how == ActRight) {
		move(c, half * cw, 0);
		resize(c, (cols - half - 2) * cw, (rows - 2) * ch);
	} else {
		move(c, 0, 0);
		resize(c, (cols - 2) * cw, (rows - 2) * ch);
	}
}

static void
startgrab(Client *c, int how)
{
	if (!c || c->isfull || !c->mapped)
		return;
	grab = how;
	grabc = c;
	gx = cursor->x;
	gy = cursor->y;
	gcx = c->x;
	gcy = c->y;
	gcw = c->w;
	gch = c->h;
	wlr_seat_pointer_clear_focus(seat);
	wlr_cursor_set_xcursor(cursor, xcm, how == GrabMove ? "grabbing" : "se-resize");
}

/* ---- xdg windows: the wayland ones ---- */

static void
xdgmap(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, map);

	manage(c);
}

static void
xdgunmap(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, unmap);

	unmanage(c);
}

static void
xdgcommit(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, commit);
	struct wlr_xdg_toplevel *t = c->xdg;

	if (t->base->initial_commit) {
		if (wl_resource_get_version(t->resource) >= XDG_TOPLEVEL_WM_CAPABILITIES_SINCE_VERSION)
			wlr_xdg_toplevel_set_wm_capabilities(t, WLR_XDG_TOPLEVEL_WM_CAPABILITIES_FULLSCREEN
			                                     | WLR_XDG_TOPLEVEL_WM_CAPABILITIES_MAXIMIZE);
		/* square corners and no shadows: it's in a frame */
		if (wl_resource_get_version(t->resource) >= XDG_TOPLEVEL_STATE_TILED_LEFT_SINCE_VERSION)
			wlr_xdg_toplevel_set_tiled(t, WLR_EDGE_TOP|WLR_EDGE_BOTTOM|WLR_EDGE_LEFT|WLR_EDGE_RIGHT);
		if (c->deco)
			wlr_xdg_toplevel_decoration_v1_set_mode(c->deco, WLR_XDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE);
		wlr_xdg_toplevel_set_size(t, 0, 0);
		return;
	}
	if (c->mapped)
		place(c);
}

static void
xdgdestroy(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, destroy);

	wl_list_remove(&c->map.link);
	wl_list_remove(&c->unmap.link);
	wl_list_remove(&c->commit.link);
	wl_list_remove(&c->destroy.link);
	wl_list_remove(&c->fullscreen.link);
	wl_list_remove(&c->maximize.link);
	wl_list_remove(&c->move.link);
	wl_list_remove(&c->resize.link);
	wl_list_remove(&c->title.link);
	if (c->deco) {
		wl_list_remove(&c->decomode.link);
		wl_list_remove(&c->decodestroy.link);
	}
	freeclient(c);
}

static void
xdgfullscreen(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, fullscreen);

	setfullscreen(c, c->xdg->requested.fullscreen);
	if (c->xdg->base->initialized)
		wlr_xdg_surface_schedule_configure(c->xdg->base);
}

static void
xdgmaximize(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, maximize);

	if (c->mapped)
		snap(c, c->snapped ? ActRestore : ActMax);
	if (c->xdg->base->initialized)
		wlr_xdg_surface_schedule_configure(c->xdg->base);
}

static void
xdgmove(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, move);

	startgrab(c, GrabMove);
}

static void
xdgresize(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, resize);

	startgrab(c, GrabResize);
}

static void
settitle(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, title);

	updatetitle(c);
	drawframe(c);
}

static void
newtoplevel(struct wl_listener *l, void *data)
{
	struct wlr_xdg_toplevel *t = data;
	Client *c = newclient();

	c->xdg = t;
	c->surf = wlr_scene_xdg_surface_create(c->content, t->base);
	t->base->data = c->surf;
	LISTEN(&t->base->surface->events.map, &c->map, xdgmap);
	LISTEN(&t->base->surface->events.unmap, &c->unmap, xdgunmap);
	LISTEN(&t->base->surface->events.commit, &c->commit, xdgcommit);
	LISTEN(&t->events.destroy, &c->destroy, xdgdestroy);
	LISTEN(&t->events.request_fullscreen, &c->fullscreen, xdgfullscreen);
	LISTEN(&t->events.request_maximize, &c->maximize, xdgmaximize);
	LISTEN(&t->events.request_move, &c->move, xdgmove);
	LISTEN(&t->events.request_resize, &c->resize, xdgresize);
	LISTEN(&t->events.set_title, &c->title, settitle);
}

/* menus and such: kept on the screen */
static void
popupcommit(struct wl_listener *l, void *data)
{
	Popup *p = wl_container_of(l, p, commit);
	struct wlr_box box;
	int lx, ly;

	if (!p->p->base->initial_commit)
		return;
	wlr_scene_node_coords(&p->parent->node, &lx, &ly);
	box = (struct wlr_box){ ox - lx, oy - ly, sw, sh };
	wlr_xdg_popup_unconstrain_from_box(p->p, &box);
	wlr_xdg_surface_schedule_configure(p->p->base);
}

static void
popupdestroy(struct wl_listener *l, void *data)
{
	Popup *p = wl_container_of(l, p, destroy);

	wl_list_remove(&p->commit.link);
	wl_list_remove(&p->destroy.link);
	free(p);
}

static void
newpopup(struct wl_listener *l, void *data)
{
	struct wlr_xdg_popup *xp = data;
	struct wlr_xdg_surface *xs;
	struct wlr_layer_surface_v1 *ls;
	struct wlr_scene_tree *parent = NULL;
	Popup *p;

	if (!xp->parent)
		return;
	if ((xs = wlr_xdg_surface_try_from_wlr_surface(xp->parent)))
		parent = xs->data;
	else if ((ls = wlr_layer_surface_v1_try_from_wlr_surface(xp->parent)))
		parent = ls->data;
	if (!parent || !(p = calloc(1, sizeof *p)))
		return;
	p->p = xp;
	p->parent = parent;
	xp->base->data = wlr_scene_xdg_surface_create(parent, xp->base);
	LISTEN(&xp->base->surface->events.commit, &p->commit, popupcommit);
	LISTEN(&xp->events.destroy, &p->destroy, popupdestroy);
}

/* we draw the frames: programs that can leave theirs out, should */
static void
decomode(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, decomode);

	if (c->xdg->base->initialized)
		wlr_xdg_toplevel_decoration_v1_set_mode(c->deco, WLR_XDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE);
}

static void
decodestroy(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, decodestroy);

	wl_list_remove(&c->decomode.link);
	wl_list_remove(&c->decodestroy.link);
	c->deco = NULL;
}

static void
newdeco(struct wl_listener *l, void *data)
{
	struct wlr_xdg_toplevel_decoration_v1 *d = data;
	Client *c;

	for (c = clients; c && c->xdg != d->toplevel; c = c->next);
	if (!c || c->deco)
		return;
	c->deco = d;
	LISTEN(&d->events.request_mode, &c->decomode, decomode);
	LISTEN(&d->events.destroy, &c->decodestroy, decodestroy);
	decomode(&c->decomode, d);
}

/* ---- x11 windows, through xwayland ---- */

static void
xwmap(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, map);
	struct wlr_xwayland_surface *xs = c->xw;
	int i;

	c->surf = wlr_scene_subsurface_tree_create(c->content, xs->surface);
	c->unmanaged = xs->override_redirect;
	if (!c->unmanaged) {
		manage(c);
		return;
	}
	/* menus and tooltips: where they say, no frame */
	c->mapped = 1;
	wlr_scene_node_reparent(&c->tree->node, ortree);
	for (i = 0; i < 4; i++)
		wlr_scene_node_set_enabled(&c->edge[i]->node, false);
	wlr_scene_node_set_enabled(&c->back->node, false);
	wlr_scene_node_set_position(&c->content->node, 0, 0);
	wlr_scene_node_set_position(&c->tree->node, xs->x, xs->y);
	wlr_scene_node_set_enabled(&c->tree->node, true);
	if (wlr_xwayland_surface_override_redirect_wants_focus(xs))
		kbfocus(xs->surface);
}

static void
xwunmap(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, unmap);

	if (c->unmanaged) {
		c->mapped = 0;
		wlr_scene_node_set_enabled(&c->tree->node, false);
		if (seat->keyboard_state.focused_surface == c->xw->surface)
			focus(sel);
	} else
		unmanage(c);
	if (c->surf) {
		wlr_scene_node_destroy(&c->surf->node);
		c->surf = NULL;
	}
	wlr_scene_node_reparent(&c->tree->node, wintree);
}

static void
xwassociate(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, associate);

	LISTEN(&c->xw->surface->events.map, &c->map, xwmap);
	LISTEN(&c->xw->surface->events.unmap, &c->unmap, xwunmap);
	c->assoc = 1;
}

static void
xwdissociate(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, dissociate);

	wl_list_remove(&c->map.link);
	wl_list_remove(&c->unmap.link);
	c->assoc = 0;
}

static void
xwdestroy(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, destroy);

	if (c->assoc) {
		wl_list_remove(&c->map.link);
		wl_list_remove(&c->unmap.link);
	}
	wl_list_remove(&c->associate.link);
	wl_list_remove(&c->dissociate.link);
	wl_list_remove(&c->destroy.link);
	wl_list_remove(&c->configure.link);
	wl_list_remove(&c->fullscreen.link);
	wl_list_remove(&c->activate.link);
	wl_list_remove(&c->title.link);
	wl_list_remove(&c->geom.link);
	freeclient(c);
}

static void
xwconfigure(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, configure);
	struct wlr_xwayland_surface_configure_event *e = data;

	if (!c->mapped || c->unmanaged) {
		wlr_xwayland_surface_configure(c->xw, e->x, e->y, e->width, e->height);
		return;
	}
	if (c->isfull || (e->width / cw * cw == c->w && e->height / ch * ch == c->h))
		cconfigure(c);
	else
		resize(c, e->width, e->height);
}

static void
xwfullscreen(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, fullscreen);

	setfullscreen(c, c->xw->fullscreen);
}

static void
xwactivate(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, activate);

	if (c->mapped && !c->unmanaged && c->scr == cur)
		focus(c);
}

static void
xwgeom(struct wl_listener *l, void *data)
{
	Client *c = wl_container_of(l, c, geom);

	if (c->mapped && c->unmanaged)
		wlr_scene_node_set_position(&c->tree->node, c->xw->x, c->xw->y);
}

static void
newxw(struct wl_listener *l, void *data)
{
	struct wlr_xwayland_surface *xs = data;
	Client *c = newclient();

	c->xw = xs;
	xs->data = c;
	LISTEN(&xs->events.associate, &c->associate, xwassociate);
	LISTEN(&xs->events.dissociate, &c->dissociate, xwdissociate);
	LISTEN(&xs->events.destroy, &c->destroy, xwdestroy);
	LISTEN(&xs->events.request_configure, &c->configure, xwconfigure);
	LISTEN(&xs->events.request_fullscreen, &c->fullscreen, xwfullscreen);
	LISTEN(&xs->events.request_activate, &c->activate, xwactivate);
	LISTEN(&xs->events.set_title, &c->title, settitle);
	LISTEN(&xs->events.set_geometry, &c->geom, xwgeom);
}

static void
xwready(struct wl_listener *l, void *data)
{
	wlr_xwayland_set_seat(xwayland, seat);
}

/* ---- layer surfaces: the apps menu, wallpaper programs, bars ---- */

static void
arrangelayers(void)
{
	struct wlr_box full = { ox, oy, sw, sh }, usable = full;
	Layer *ly;
	int i;

	for (i = 3; i >= 0; i--)
		for (ly = layersurfs; ly; ly = ly->next)
			if (ly->ls->initialized && (int)ly->ls->current.layer == i)
				wlr_scene_layer_surface_v1_configure(ly->scene, &full, &usable);
}

static void
layermap(struct wl_listener *l, void *data)
{
	Layer *ly = wl_container_of(l, ly, map);

	if (ly->ls->current.keyboard_interactive && ly->ls->current.layer >= ZWLR_LAYER_SHELL_V1_LAYER_TOP && !locked) {
		exclusive = ly;
		kbfocus(ly->ls->surface);
	}
	arrangelayers();
}

static void
layerunmap(struct wl_listener *l, void *data)
{
	Layer *ly = wl_container_of(l, ly, unmap);

	if (exclusive == ly) {
		exclusive = NULL;
		focus(sel);
	}
}

static void
layercommit(struct wl_listener *l, void *data)
{
	Layer *ly = wl_container_of(l, ly, commit);

	if (ly->ls->initial_commit || ly->ls->current.committed) {
		wlr_scene_node_reparent(&ly->scene->tree->node, layers[ly->ls->current.layer]);
		arrangelayers();
	}
}

static void
layerdestroy(struct wl_listener *l, void *data)
{
	Layer *ly = wl_container_of(l, ly, destroy), **pl;

	wl_list_remove(&ly->map.link);
	wl_list_remove(&ly->unmap.link);
	wl_list_remove(&ly->commit.link);
	wl_list_remove(&ly->destroy.link);
	for (pl = &layersurfs; *pl != ly; pl = &(*pl)->next);
	*pl = ly->next;
	if (exclusive == ly) {
		exclusive = NULL;
		focus(sel);
	}
	free(ly);
}

static void
newlayer(struct wl_listener *l, void *data)
{
	struct wlr_layer_surface_v1 *ls = data;
	Layer *ly;

	if (!ls->output) {
		if (!outputs) {
			wlr_layer_surface_v1_destroy(ls);
			return;
		}
		ls->output = outputs->wlr;
	}
	if (!(ly = calloc(1, sizeof *ly)))
		return;
	ly->kind = KLayer;
	ly->ls = ls;
	ly->scene = wlr_scene_layer_surface_v1_create(layers[ls->pending.layer], ls);
	ly->scene->tree->node.data = ly;
	ls->data = ly->scene->tree;
	LISTEN(&ls->surface->events.map, &ly->map, layermap);
	LISTEN(&ls->surface->events.unmap, &ly->unmap, layerunmap);
	LISTEN(&ls->surface->events.commit, &ly->commit, layercommit);
	LISTEN(&ls->events.destroy, &ly->destroy, layerdestroy);
	ly->next = layersurfs;
	layersurfs = ly;
}

/* ---- the lock screen: a login prompt, checked by pam like a real one ---- */

static int
conv(int n, const struct pam_message **msg, struct pam_response **resp, void *pw)
{
	int i;

	if (!(*resp = calloc(n, sizeof **resp)))
		return PAM_BUF_ERR;
	for (i = 0; i < n; i++)
		if (msg[i]->msg_style == PAM_PROMPT_ECHO_OFF || msg[i]->msg_style == PAM_PROMPT_ECHO_ON)
			(*resp)[i].resp = strdup(pw);
	return PAM_SUCCESS;
}

static int
checkpassword(const char *user, const char *pw)
{
	struct pam_conv pc = { conv, (void *)pw };
	pam_handle_t *ph;
	int r;

	if (pam_start("system-local-login", user, &pc, &ph) != PAM_SUCCESS)
		return 0;
	r = pam_authenticate(ph, 0);
	pam_end(ph, r);
	return r == PAM_SUCCESS;
}

static void
drawlock(void)
{
	char host[64] = "", line[256], *user = getenv("USER");
	cairo_t *cr;
	Buf *b;

	if (!sw)
		return;
	gethostname(host, sizeof host);
	b = newbuf(sw, 6 * ch, &cr);
	fill(cr, ColBg, 0, 0, sw, 6 * ch);
	snprintf(line, sizeof line, "Chamesle Linux (tty%d)", cur + 1);
	text(cr, ColBar, 0, 0, line);
	snprintf(line, sizeof line, "%s login: %s", host, user ? user : "");
	text(cr, ColBar, 0, 2 * ch, line);
	text(cr, ColBar, 0, 3 * ch, "Password: ");
	if (lockwrong)
		text(cr, ColBar, 0, 5 * ch, "Login incorrect");
	putbuf(lockbuf, b, cr);
	wlr_scene_node_set_position(&lockbuf->node, ox, oy);
}

static void
lock(void)
{
	if (locked)
		return;
	locked = 1;
	locklen = lockwrong = 0;
	grab = GrabNone;
	grabc = NULL;
	wlr_seat_keyboard_notify_clear_focus(seat);
	wlr_seat_pointer_clear_focus(seat);
	wlr_scene_node_set_enabled(&locktree->node, true);
	drawlock();
}

static void
lockkey(struct wlr_keyboard *kb, uint32_t code)
{
	xkb_keysym_t sym = xkb_state_key_get_one_sym(kb->xkb_state, code);
	char buf[8], *user = getenv("USER");
	int len;

	if (sym == XKB_KEY_Return || sym == XKB_KEY_KP_Enter) {
		lockpw[locklen] = '\0';
		if (user && checkpassword(user, lockpw)) {
			memset(lockpw, 0, sizeof lockpw);
			locked = 0;
			wlr_scene_node_set_enabled(&locktree->node, false);
			focus(sel);
			return;
		}
		memset(lockpw, 0, sizeof lockpw);
		lockwrong = 1;
		locklen = 0;
		drawlock();
	} else if (sym == XKB_KEY_BackSpace) {
		while (locklen && (lockpw[--locklen] & 0xc0) == 0x80);
	} else if (sym == XKB_KEY_Escape)
		locklen = 0;
	else if ((len = xkb_state_key_get_utf8(kb->xkb_state, code, buf, sizeof buf)) > 0
	&& !iscntrl((unsigned char)buf[0]) && locklen + len < (int)sizeof lockpw - 1) {
		memcpy(lockpw + locklen, buf, len);
		locklen += len;
	}
}

/* ---- what keys and clicks do ---- */

static void
view(int n)
{
	Client *c;

	if (n == cur)
		return;
	cur = n;
	for (c = clients; c; c = c->next)
		if (c->mapped && !c->unmanaged)
			wlr_scene_node_set_enabled(&c->tree->node, c->scr == cur);
	drawbar();
	focus(topclient());
}

static void
sendto(int n)
{
	if (!sel || n == cur)
		return;
	sel->scr = n;
	wlr_scene_node_set_enabled(&sel->tree->node, false);
	focus(topclient());
	if (sel && sel->scr != cur)
		sel = NULL;
}

static void
focusnext(void)
{
	Client *c = sel ? sel->next : clients;

	for (; c && (!c->mapped || c->unmanaged || c->scr != cur); c = c->next);
	focus(c);
}

/* foot takes the program as it is, xterm and the rest after -e */
static void
interm(const char *prog)
{
	char cmd[512];

	if (!strncmp(terminal, "foot", 4))
		snprintf(cmd, sizeof cmd, "%s %s", terminal, prog);
	else
		snprintf(cmd, sizeof cmd, "%s -e %s", terminal, prog);
	run(cmd);
}

static void
doaction(Key *k)
{
	switch (k->act) {
	case ActRun:      run(k->cmd); break;
	case ActTerminal: run(terminal); break;
	case ActMenu:     run(menu); break;
	case ActClose:    if (sel) closeclient(sel); break;
	case ActNext:     focusnext(); break;
	case ActFull:     if (sel) setfullscreen(sel, !sel->isfull); break;
	case ActQuit:     wl_display_terminate(dpy); break;
	case ActView:     view(k->n); break;
	case ActSend:     sendto(k->n); break;
	case ActVolUp:    setvolume("5%+"); break;
	case ActVolDown:  setvolume("5%-"); break;
	case ActMute:     setvolume("mute"); break;
	case ActLightUp:  setlight(5); drawbar(); break;
	case ActLightDown: setlight(-5); drawbar(); break;
	case ActLeft: case ActRight: case ActMax: case ActRestore:
		if (sel)
			snap(sel, k->act);
		break;
	case ActLock:     lock(); break;
	}
}

static int
segat(int x)
{
	int i;

	for (i = 0; i < nsegs; i++)
		if (x >= segs[i].x0 && x < segs[i].x1)
			return segs[i].seg;
	return SegNone;
}

static void
barclick(int x, uint32_t button)
{
	int s = segat(x);

	if (button != BTN_LEFT)
		return;
	if (s == SegVol)
		setvolume("mute");
	else if (s == SegNet)
		interm("nmtui");
}

/* up or down on the volume or the brightness */
static void
barscroll(int x, int up)
{
	int s = segat(x);

	if (s == SegVol)
		setvolume(up ? "5%+" : "5%-");
	else if (s == SegLight) {
		setlight(up ? 5 : -5);
		drawbar();
	}
}

/* ---- input ---- */

/* what's at a point: a client, layer, notification or the bar, and the surface there if there is one */
static void *
objat(double lx, double ly, struct wlr_surface **surf, double *sx, double *sy)
{
	struct wlr_scene_node *n = wlr_scene_node_at(&scene->tree.node, lx, ly, sx, sy);
	struct wlr_scene_buffer *b;
	struct wlr_scene_surface *ss;

	*surf = NULL;
	if (!n)
		return NULL;
	if (n->type == WLR_SCENE_NODE_BUFFER && (b = wlr_scene_buffer_from_node(n))
	&& (ss = wlr_scene_surface_try_from_buffer(b)))
		*surf = ss->surface;
	for (; n; n = n->parent ? &n->parent->node : NULL)
		if (n->data)
			return n->data;
	return NULL;
}

static void
motion(uint32_t time)
{
	struct wlr_surface *s;
	double sx, sy;

	wlr_idle_notifier_v1_notify_activity(idle, seat);
	if (grab == GrabMove) {
		/* a cell at a time, like everything else */
		move(grabc, gcx + (int)(cursor->x - gx) / cw * cw, gcy + (int)(cursor->y - gy) / ch * ch);
		return;
	}
	if (grab == GrabResize) {
		resize(grabc, gcw + cursor->x - gx, gch + cursor->y - gy);
		return;
	}
	if (locked)
		return;
	objat(cursor->x, cursor->y, &s, &sx, &sy);
	if (!s) {
		wlr_cursor_set_xcursor(cursor, xcm, "default");
		wlr_seat_pointer_clear_focus(seat);
		return;
	}
	wlr_seat_pointer_notify_enter(seat, s, sx, sy);
	wlr_seat_pointer_notify_motion(seat, time, sx, sy);
}

static void
cmotion(struct wl_listener *l, void *data)
{
	struct wlr_pointer_motion_event *e = data;

	wlr_cursor_move(cursor, &e->pointer->base, e->delta_x, e->delta_y);
	motion(e->time_msec);
}

static void
cmotionabs(struct wl_listener *l, void *data)
{
	struct wlr_pointer_motion_absolute_event *e = data;

	wlr_cursor_warp_absolute(cursor, &e->pointer->base, e->x, e->y);
	motion(e->time_msec);
}

static void
cbutton(struct wl_listener *l, void *data)
{
	struct wlr_pointer_button_event *e = data;
	struct wlr_keyboard *kb = wlr_seat_get_keyboard(seat);
	struct wlr_surface *s;
	double sx, sy;
	void *o;
	Client *c;
	Layer *ly;
	uint32_t mods = kb ? wlr_keyboard_get_modifiers(kb) : 0;
	int x, y, cols;

	wlr_idle_notifier_v1_notify_activity(idle, seat);
	if (e->state == WL_POINTER_BUTTON_STATE_RELEASED) {
		if (grab) {
			grab = GrabNone;
			grabc = NULL;
			wlr_cursor_set_xcursor(cursor, xcm, "default");
			return;
		}
		if (!locked)
			wlr_seat_pointer_notify_button(seat, e->time_msec, e->button, e->state);
		return;
	}
	if (locked)
		return;
	o = objat(cursor->x, cursor->y, &s, &sx, &sy);
	if (o == &barkind) {
		barclick(cursor->x - ox, e->button);
		return;
	}
	if (o && *(int *)o == KNotif) {
		closenotif(o, 2);
		return;
	}
	if (o && *(int *)o == KLayer) {
		ly = o;
		if (ly->ls->current.keyboard_interactive)
			kbfocus(ly->ls->surface);
		goto pass;
	}
	if (!o) {
		focus(NULL);
		goto pass;
	}
	c = o;
	if (c->unmanaged)
		goto pass;
	focus(c);
	if (s) {
		if (CLEANMASK(mods) == SUPER && (e->button == BTN_LEFT || e->button == BTN_RIGHT)) {
			startgrab(c, e->button == BTN_RIGHT ? GrabResize : GrabMove);
			return;
		}
		goto pass;
	}
	if (c->isfull)
		goto pass;
	/* the frame: [x] closes, the title moves, the bottom right corner resizes */
	x = cursor->x - ox - c->x;
	y = cursor->y - oy - c->y;
	cols = c->w / cw + 2;
	if (y < ch && x >= (cols - 4) * cw)
		closeclient(c);
	else if (y < ch)
		startgrab(c, GrabMove);
	else if (y >= c->h + ch && x >= (cols - 2) * cw)
		startgrab(c, GrabResize);
	return;
pass:
	wlr_seat_pointer_notify_button(seat, e->time_msec, e->button, e->state);
}

static void
caxis(struct wl_listener *l, void *data)
{
	static double acc;
	struct wlr_pointer_axis_event *e = data;
	struct wlr_surface *s;
	double sx, sy;

	if (locked)
		return;
	if (objat(cursor->x, cursor->y, &s, &sx, &sy) == &barkind) {
		if (e->orientation != WL_POINTER_AXIS_VERTICAL_SCROLL)
			return;
		/* a wheel click is a step; a touchpad, every so far */
		acc += e->delta;
		if (e->delta_discrete || acc <= -15 || acc >= 15) {
			barscroll(cursor->x - ox, acc < 0);
			acc = 0;
		}
		return;
	}
	wlr_seat_pointer_notify_axis(seat, e->time_msec, e->orientation, e->delta, e->delta_discrete,
	                             e->source, e->relative_direction);
}

static void
cframe(struct wl_listener *l, void *data)
{
	wlr_seat_pointer_notify_frame(seat);
}

static void
setkeymap(struct wlr_keyboard *kb)
{
	struct xkb_rule_names rn = { 0 };
	struct xkb_context *ctx = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
	struct xkb_keymap *km;

	rn.layout = kblayout[0] ? kblayout : NULL;
	rn.variant = kbvariant[0] ? kbvariant : NULL;
	if (!(km = xkb_keymap_new_from_names(ctx, &rn, XKB_KEYMAP_COMPILE_NO_FLAGS))) {
		fprintf(stderr, "torrent: no keyboard layout '%s', using the default\n", kblayout);
		rn.layout = rn.variant = NULL;
		km = xkb_keymap_new_from_names(ctx, &rn, XKB_KEYMAP_COMPILE_NO_FLAGS);
	}
	if (km) {
		wlr_keyboard_set_keymap(kb, km);
		xkb_keymap_unref(km);
	}
	xkb_context_unref(ctx);
}

static void
keykey(struct wl_listener *l, void *data)
{
	Kbd *k = wl_container_of(l, k, key);
	struct wlr_keyboard_key_event *e = data;
	uint32_t code = e->keycode + 8, mods = wlr_keyboard_get_modifiers(k->wlr);
	const xkb_keysym_t *syms;
	xkb_layout_index_t lay;
	int n, i, j, done = 0;

	wlr_idle_notifier_v1_notify_activity(idle, seat);
	if (e->state == WL_KEYBOARD_KEY_STATE_PRESSED) {
		/* ctrl+alt+f1: the consoles, like everywhere else */
		n = xkb_state_key_get_syms(k->wlr->xkb_state, code, &syms);
		for (i = 0; i < n; i++)
			if (syms[i] >= XKB_KEY_XF86Switch_VT_1 && syms[i] <= XKB_KEY_XF86Switch_VT_12) {
				if (session)
					wlr_session_change_vt(session, syms[i] - XKB_KEY_XF86Switch_VT_1 + 1);
				return;
			}
		if (locked) {
			lockkey(k->wlr, code);
			return;
		}
		/* the key as it is without shift, like super+shift+1 */
		lay = xkb_state_key_get_layout(k->wlr->xkb_state, code);
		n = xkb_keymap_key_get_syms_by_level(k->wlr->keymap, code, lay == XKB_LAYOUT_INVALID ? 0 : lay, 0, &syms);
		for (i = 0; i < n && !done; i++)
			for (j = 0; j < nkeys; j++)
				if (syms[i] == keys[j].keysym && CLEANMASK(keys[j].mod) == CLEANMASK(mods)) {
					doaction(&keys[j]);
					done = 1;
					break;
				}
	} else if (locked)
		return;
	if (!done) {
		wlr_seat_set_keyboard(seat, k->wlr);
		wlr_seat_keyboard_notify_key(seat, e->time_msec, e->keycode, e->state);
	}
}

static void
keymods(struct wl_listener *l, void *data)
{
	Kbd *k = wl_container_of(l, k, mods);

	wlr_seat_set_keyboard(seat, k->wlr);
	wlr_seat_keyboard_notify_modifiers(seat, &k->wlr->modifiers);
}

static void
keydestroy(struct wl_listener *l, void *data)
{
	Kbd *k = wl_container_of(l, k, destroy), **pk;

	wl_list_remove(&k->key.link);
	wl_list_remove(&k->mods.link);
	wl_list_remove(&k->destroy.link);
	for (pk = &kbds; *pk != k; pk = &(*pk)->next);
	*pk = k->next;
	free(k);
}

static void
newinput(struct wl_listener *l, void *data)
{
	struct wlr_input_device *d = data;
	struct libinput_device *li;
	Kbd *k;

	if (d->type == WLR_INPUT_DEVICE_KEYBOARD && (k = calloc(1, sizeof *k))) {
		k->wlr = wlr_keyboard_from_input_device(d);
		setkeymap(k->wlr);
		wlr_keyboard_set_repeat_info(k->wlr, 25, 600);
		LISTEN(&k->wlr->events.key, &k->key, keykey);
		LISTEN(&k->wlr->events.modifiers, &k->mods, keymods);
		LISTEN(&d->events.destroy, &k->destroy, keydestroy);
		wlr_seat_set_keyboard(seat, k->wlr);
		k->next = kbds;
		kbds = k;
	} else if (d->type == WLR_INPUT_DEVICE_POINTER) {
		if (wlr_input_device_is_libinput(d) && (li = wlr_libinput_get_device_handle(d))) {
			if (libinput_device_config_tap_get_finger_count(li))
				libinput_device_config_tap_set_enabled(li, tapclick ? LIBINPUT_CONFIG_TAP_ENABLED
				                                                    : LIBINPUT_CONFIG_TAP_DISABLED);
			if (libinput_device_config_scroll_has_natural_scroll(li))
				libinput_device_config_scroll_set_natural_scroll_enabled(li, natural);
		}
		wlr_cursor_attach_input_device(cursor, d);
	}
	wlr_seat_set_capabilities(seat, WL_SEAT_CAPABILITY_POINTER | (kbds ? WL_SEAT_CAPABILITY_KEYBOARD : 0));
}

static void
setcursor(struct wl_listener *l, void *data)
{
	struct wlr_seat_pointer_request_set_cursor_event *e = data;

	if (!grab && e->seat_client == seat->pointer_state.focused_client)
		wlr_cursor_set_surface(cursor, e->surface, e->hotspot_x, e->hotspot_y);
}

static void
setshape(struct wl_listener *l, void *data)
{
	struct wlr_cursor_shape_manager_v1_request_set_shape_event *e = data;

	if (!grab && e->seat_client == seat->pointer_state.focused_client)
		wlr_cursor_set_xcursor(cursor, xcm, wlr_cursor_shape_v1_name(e->shape));
}

static void
setsel(struct wl_listener *l, void *data)
{
	struct wlr_seat_request_set_selection_event *e = data;

	wlr_seat_set_selection(seat, e->source, e->serial);
}

static void
setpsel(struct wl_listener *l, void *data)
{
	struct wlr_seat_request_set_primary_selection_event *e = data;

	wlr_seat_set_primary_selection(seat, e->source, e->serial);
}

/* a program wants a window of its to the front, like a browser opening a link */
static void
activate(struct wl_listener *l, void *data)
{
	struct wlr_xdg_activation_v1_request_activate_event *e = data;
	Client *c;

	for (c = clients; c && csurface(c) != e->surface; c = c->next);
	if (c && c->mapped && c->scr == cur)
		focus(c);
}

/* ---- screens ---- */

/* the first screen is the one: the bottom line, the wallpaper and the windows go there */
static void
arrange(void)
{
	struct wlr_box b;
	Client *c;

	if (!outputs)
		return;
	wlr_output_layout_get_box(layout, outputs->wlr, &b);
	ox = b.x;
	oy = b.y;
	sw = b.width;
	sh = b.height;
	wh = sh - ch;
	wlr_scene_node_set_position(&bgrect->node, ox, oy);
	wlr_scene_rect_set_size(bgrect, sw, sh);
	drawwallpaper();
	wlr_scene_node_set_position(&barbuf->node, ox, oy + wh);
	drawbar();
	arrangelayers();
	wlr_scene_node_set_position(&lockrect->node, ox, oy);
	wlr_scene_rect_set_size(lockrect, sw, sh);
	if (locked)
		drawlock();
	for (c = clients; c; c = c->next)
		if (c->mapped && !c->unmanaged) {
			if (c->isfull)
				cconfigure(c);
			place(c);
		}
	placenotifs();
}

static void
outframe(struct wl_listener *l, void *data)
{
	Output *o = wl_container_of(l, o, frame);
	struct wlr_scene_output *so = wlr_scene_get_scene_output(scene, o->wlr);
	struct timespec now;

	/* the typing goes with the screen's refresh: one step a frame, never torn */
	if (animate())
		wlr_output_schedule_frame(o->wlr);
	wlr_scene_output_commit(so, NULL);
	clock_gettime(CLOCK_MONOTONIC, &now);
	wlr_scene_output_send_frame_done(so, &now);
}

static void
outstate(struct wl_listener *l, void *data)
{
	Output *o = wl_container_of(l, o, state);
	struct wlr_output_event_request_state *e = data;

	wlr_output_commit_state(o->wlr, e->state);
	arrange();
}

static void
outdestroy(struct wl_listener *l, void *data)
{
	Output *o = wl_container_of(l, o, destroy), **po;

	wl_list_remove(&o->frame.link);
	wl_list_remove(&o->state.link);
	wl_list_remove(&o->destroy.link);
	for (po = &outputs; *po != o; po = &(*po)->next);
	*po = o->next;
	free(o);
	arrange();
}

static void
newoutput(struct wl_listener *l, void *data)
{
	struct wlr_output *wo = data;
	struct wlr_output_state st;
	struct wlr_output_mode *m;
	struct wlr_output_layout_output *lo;
	struct wlr_scene_output *so;
	Output *o, **po;

	wlr_output_init_render(wo, alloc, renderer);
	wlr_output_state_init(&st);
	wlr_output_state_set_enabled(&st, true);
	if ((m = wlr_output_preferred_mode(wo)))
		wlr_output_state_set_mode(&st, m);
	wlr_output_commit_state(wo, &st);
	wlr_output_state_finish(&st);
	if (!(o = calloc(1, sizeof *o)))
		return;
	o->wlr = wo;
	LISTEN(&wo->events.frame, &o->frame, outframe);
	LISTEN(&wo->events.request_state, &o->state, outstate);
	LISTEN(&wo->events.destroy, &o->destroy, outdestroy);
	for (po = &outputs; *po; po = &(*po)->next);
	*po = o;
	lo = wlr_output_layout_add_auto(layout, wo);
	so = wlr_scene_output_create(scene, wo);
	wlr_scene_output_layout_add_output(sol, lo, so);
	arrange();
}

/* once a second: the clock, notifications, and the settings file if it changed */
static int
tick(void *data)
{
	static time_t last, lastvol;
	time_t now = time(NULL);
	struct stat st;
	char lay[64], var[64];
	Client *c;
	Kbd *k;

	wl_event_source_timer_update(ticker, 1000);
	readbus();
	expirenotifs();
	if (stat(cfgpath, &st) == 0 && st.st_mtime != cfgmtime) {
		memcpy(lay, kblayout, sizeof lay);
		memcpy(var, kbvariant, sizeof var);
		loadconfig(0);
		loadcolours();
		if (strcmp(lay, kblayout) || strcmp(var, kbvariant))
			for (k = kbds; k; k = k->next)
				setkeymap(k->wlr);
		wlr_scene_rect_set_color(bgrect, col[ColBg]);
		wlr_scene_rect_set_color(lockrect, col[ColBg]);
		for (c = clients; c; c = c->next) {
			wlr_scene_rect_set_color(c->back, col[ColBg]);
			drawframe(c);
		}
		drawwallpaper();
		placenotifs();
		runbarcmds();
		last = 0;
	}
	if (now - lastvol >= 10) {
		readvolume();
		lastvol = now;
	}
	if (now / 5 != last / 5) {
		runbarcmds();
		drawbar();
	}
	last = now;
	return 0;
}

int
main(int argc, char *argv[])
{
	const char *sock;
	char *home, *xdg;
	int bfd = -1, i;

	if (argc == 2 && !strcmp("-v", argv[1]))
		die("torrent-" VERSION);
	else if (argc != 1)
		die("usage: torrent [-v]");
	setlocale(LC_CTYPE, "");
	signal(SIGPIPE, SIG_IGN);
	wlr_log_init(WLR_ERROR, NULL);

	if ((xdg = getenv("XDG_CONFIG_HOME")) && *xdg)
		snprintf(cfgpath, sizeof cfgpath, "%s", xdg);
	else
		snprintf(cfgpath, sizeof cfgpath, "%s/.config", (home = getenv("HOME")) ? home : ".");
	mkdir(cfgpath, 0755);
	strncat(cfgpath, "/torrent", sizeof cfgpath - strlen(cfgpath) - 1);
	mkdir(cfgpath, 0755);
	strncat(cfgpath, "/config", sizeof cfgpath - strlen(cfgpath) - 1);

	dpy = wl_display_create();
	loop = wl_display_get_event_loop(dpy);
	if (!(backend = wlr_backend_autocreate(loop, &session)))
		die("cannot start: run it from a login on a console, or inside another desktop");
	if (!(renderer = wlr_renderer_autocreate(backend)))
		die("cannot make a renderer");
	wlr_renderer_init_wl_display(renderer, dpy);
	if (!(alloc = wlr_allocator_autocreate(backend, renderer)))
		die("cannot make an allocator");
	compositor = wlr_compositor_create(dpy, 6, renderer);
	wlr_subcompositor_create(dpy);
	wlr_data_device_manager_create(dpy);
	wlr_primary_selection_v1_device_manager_create(dpy);
	wlr_data_control_manager_v1_create(dpy);
	wlr_export_dmabuf_manager_v1_create(dpy);
	wlr_screencopy_manager_v1_create(dpy);
	wlr_gamma_control_manager_v1_create(dpy);
	wlr_viewporter_create(dpy);
	wlr_single_pixel_buffer_manager_v1_create(dpy);
	wlr_fractional_scale_manager_v1_create(dpy, 1);
	wlr_presentation_create(dpy, backend, 2);
	wlr_relative_pointer_manager_v1_create(dpy);
	idle = wlr_idle_notifier_v1_create(dpy);

	layout = wlr_output_layout_create(dpy);
	wlr_xdg_output_manager_v1_create(dpy, layout);
	LISTEN(&backend->events.new_output, &newoutput_l, newoutput);
	scene = wlr_scene_create();
	sol = wlr_scene_attach_output_layout(scene, layout);
	bgtree = wlr_scene_tree_create(&scene->tree);
	bgrect = wlr_scene_rect_create(bgtree, 1, 1, (float[4]){ 0, 0, 0, 1 });
	wallbuf = wlr_scene_buffer_create(bgtree, NULL);
	for (i = 0; i < 2; i++)
		layers[i] = wlr_scene_tree_create(&scene->tree);
	wintree = wlr_scene_tree_create(&scene->tree);
	bartree = wlr_scene_tree_create(&scene->tree);
	barbuf = wlr_scene_buffer_create(bartree, NULL);
	barbuf->node.data = &barkind;
	fulltree = wlr_scene_tree_create(&scene->tree);
	ortree = wlr_scene_tree_create(&scene->tree);
	layers[2] = wlr_scene_tree_create(&scene->tree);
	notiftree = wlr_scene_tree_create(&scene->tree);
	layers[3] = wlr_scene_tree_create(&scene->tree);
	locktree = wlr_scene_tree_create(&scene->tree);
	lockrect = wlr_scene_rect_create(locktree, 1, 1, (float[4]){ 0, 0, 0, 1 });
	lockbuf = wlr_scene_buffer_create(locktree, NULL);
	wlr_scene_node_set_enabled(&locktree->node, false);

	xdgshell = wlr_xdg_shell_create(dpy, 6);
	LISTEN(&xdgshell->events.new_toplevel, &newtoplevel_l, newtoplevel);
	LISTEN(&xdgshell->events.new_popup, &newpopup_l, newpopup);
	layershell = wlr_layer_shell_v1_create(dpy, 4);
	LISTEN(&layershell->events.new_surface, &newlayer_l, newlayer);
	decomgr = wlr_xdg_decoration_manager_v1_create(dpy);
	LISTEN(&decomgr->events.new_toplevel_decoration, &newdeco_l, newdeco);
	wlr_server_decoration_manager_set_default_mode(wlr_server_decoration_manager_create(dpy),
	                                               WLR_SERVER_DECORATION_MANAGER_MODE_SERVER);
	activation = wlr_xdg_activation_v1_create(dpy);
	LISTEN(&activation->events.request_activate, &activate_l, activate);

	cursor = wlr_cursor_create();
	wlr_cursor_attach_output_layout(cursor, layout);
	xcm = wlr_xcursor_manager_create(getenv("XCURSOR_THEME"), getenv("XCURSOR_SIZE") ? atoi(getenv("XCURSOR_SIZE")) : 24);
	LISTEN(&cursor->events.motion, &motion_l, cmotion);
	LISTEN(&cursor->events.motion_absolute, &motionabs_l, cmotionabs);
	LISTEN(&cursor->events.button, &button_l, cbutton);
	LISTEN(&cursor->events.axis, &axis_l, caxis);
	LISTEN(&cursor->events.frame, &frame_l, cframe);
	shapemgr = wlr_cursor_shape_manager_v1_create(dpy, 1);
	LISTEN(&shapemgr->events.request_set_shape, &shape_l, setshape);

	seat = wlr_seat_create(dpy, "seat0");
	LISTEN(&backend->events.new_input, &newinput_l, newinput);
	LISTEN(&seat->events.request_set_cursor, &setcursor_l, setcursor);
	LISTEN(&seat->events.request_set_selection, &setsel_l, setsel);
	LISTEN(&seat->events.request_set_primary_selection, &setpsel_l, setpsel);

	if (!(sock = wl_display_add_socket_auto(dpy)))
		die("cannot make a wayland socket");
	setenv("WAYLAND_DISPLAY", sock, 1);
	setenv("XDG_SESSION_TYPE", "wayland", 1);
	setenv("XDG_CURRENT_DESKTOP", "torrent", 0);
	/* x11 programs: xwayland starts the first time one connects */
	if ((xwayland = wlr_xwayland_create(dpy, compositor, true))) {
		LISTEN(&xwayland->events.ready, &xwready_l, xwready);
		LISTEN(&xwayland->events.new_surface, &newxw_l, newxw);
		setenv("DISPLAY", xwayland->display_name, 1);
	} else
		unsetenv("DISPLAY");

	loadconfig(1);
	loadcolours();
	fontsetup();
	wlr_scene_rect_set_color(bgrect, col[ColBg]);
	wlr_scene_rect_set_color(lockrect, col[ColBg]);
	if (!wlr_backend_start(backend))
		die("cannot start the backend");
	wlr_cursor_set_xcursor(cursor, xcm, "default");

	setupbus();
	if (bus && dbus_connection_get_unix_fd(bus, &bfd))
		wl_event_loop_add_fd(loop, bfd, WL_EVENT_READABLE, busready, NULL);
	ticker = wl_event_loop_add_timer(loop, tick, NULL);
	wl_event_source_timer_update(ticker, 1000);
	/* portals and the like learn where the screen is */
	run("dbus-update-activation-environment WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE 2>/dev/null");
	readvolume();
	findbacklight();
	drawbar();

	wl_display_run(dpy);

	if (xwayland)
		wlr_xwayland_destroy(xwayland);
	wl_display_destroy_clients(dpy);
	wlr_scene_node_destroy(&scene->tree.node);
	wlr_xcursor_manager_destroy(xcm);
	wlr_cursor_destroy(cursor);
	wlr_allocator_destroy(alloc);
	wlr_renderer_destroy(renderer);
	wlr_backend_destroy(backend);
	wl_display_destroy(dpy);
	return EXIT_SUCCESS;
}
