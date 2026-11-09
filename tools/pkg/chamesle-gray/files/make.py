#!/usr/bin/env python3
# chamesle gray: window frames and panels for every desktop, the way workstations looked around 2001.
# black title bar on the window you're in, dark gray on the others, gray buttons raised one pixel,
# a thin black line round the window and a gray bar along the bottom to resize it by.
# nothing here is copied from anyone's theme, it's all drawn below.
#   make.py SHARE   writes SHARE/themes, SHARE/aurorae, SHARE/plasma, SHARE/color-schemes
import os, sys
from PIL import Image, ImageDraw

NAME = 'Chamesle-Gray'
TH = 22           # title bar height, the black line on top included
B = 1             # sides: just the black line
BB = 7            # the bar along the bottom
GRIP = 28         # its corner pieces, which resize both ways
BS = 16           # buttons are this square
BP = 3            # and sit this far in from their slot's edges

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
FACE = (174, 174, 174)       # the gray everything's made of
LIGHT = (222, 222, 222)
DARK = (85, 85, 85)
TITLE = {True: (0, 0, 0), False: (76, 76, 76)}
TITLE_HI = {True: (52, 52, 52), False: (110, 110, 110)}
TEXT = {True: '#ffffff', False: '#c8c8c8'}

def hexc(c):
	return '#%02x%02x%02x' % c

def save(im, *p):
	f = os.path.join(*p)
	os.makedirs(os.path.dirname(f), exist_ok=True)
	im.save(f)

def save_text(text, *p):
	f = os.path.join(*p)
	os.makedirs(os.path.dirname(f), exist_ok=True)
	open(f, 'w').write(text)

# a raised box: white on the top and left, dark then black on the bottom and right. pressed is the other way round
def bevel(d, x0, y0, x1, y1, face, pressed=False):
	d.rectangle((x0, y0, x1, y1), fill=face)
	hi, lo, edge = (DARK, LIGHT, WHITE) if pressed else (WHITE, DARK, BLACK)
	if pressed:
		d.line((x0, y0, x1, y0), fill=BLACK); d.line((x0, y0, x0, y1), fill=BLACK)
		d.line((x0 + 1, y0 + 1, x1 - 1, y0 + 1), fill=DARK); d.line((x0 + 1, y0 + 1, x0 + 1, y1 - 1), fill=DARK)
		d.line((x0, y1, x1, y1), fill=WHITE); d.line((x1, y0, x1, y1), fill=WHITE)
	else:
		d.line((x0, y0, x1, y0), fill=WHITE); d.line((x0, y0, x0, y1), fill=WHITE)
		d.line((x0, y1, x1, y1), fill=BLACK); d.line((x1, y0, x1, y1), fill=BLACK)
		d.line((x0 + 1, y1 - 1, x1 - 1, y1 - 1), fill=DARK); d.line((x1 - 1, y0 + 1, x1 - 1, y1 - 1), fill=DARK)

# the little pictures on the buttons, in black, inside a box at x, y of size s
def glyph(d, kind, x, y, s, col=BLACK):
	m = s // 4
	if kind == 'close':
		for k in (0, 1):
			d.line((x + m + k, y + m, x + s - m - 1 + k - 1, y + s - m - 1), fill=col)
			d.line((x + m + k, y + s - m - 1, x + s - m - 1 + k - 1, y + m), fill=col)
	elif kind == 'hide':
		d.rectangle((x + m, y + s - m - 3, x + s - m - 1, y + s - m - 1), outline=col)
	elif kind == 'maximize':
		d.rectangle((x + m, y + m, x + s - m - 1, y + s - m - 1), outline=col)
		d.line((x + m, y + m + 1, x + s - m - 1, y + m + 1), fill=col)
	elif kind == 'restore':
		d.rectangle((x + m + 2, y + m, x + s - m - 1, y + s - m - 3), outline=col)
		d.rectangle((x + m, y + m + 3, x + s - m - 3, y + s - m - 1), outline=col, fill=FACE)
		d.line((x + m, y + m + 4, x + s - m - 3, y + m + 4), fill=col)
	elif kind == 'menu':
		d.rectangle((x + m, y + s // 2 - 1, x + s - m - 1, y + s // 2 + 1), outline=col)
	elif kind == 'shade':
		d.line((x + m, y + m + 2, x + s - m - 1, y + m + 2), fill=col)
		d.line((x + m, y + m + 3, x + s - m - 1, y + m + 3), fill=col)
	elif kind == 'stick':
		d.rectangle((x + s // 2 - 2, y + s // 2 - 2, x + s // 2 + 1, y + s // 2 + 1), fill=col)

# a piece of title bar, w wide
def title(w, active, h=TH):
	im = Image.new('RGB', (w, h), TITLE[active])
	d = ImageDraw.Draw(im)
	d.line((0, 0, w, 0), fill=BLACK)
	d.line((0, 1, w, 1), fill=TITLE_HI[active])
	d.line((0, h - 1, w, h - 1), fill=BLACK)
	return im

# a button sitting on its slot of title bar
def button(kind, state, active, w=TH, h=TH):
	im = title(w, active, h)
	d = ImageDraw.Draw(im)
	x0 = (w - BS) // 2; y0 = (h - BS) // 2
	face = {'prelight': (196, 196, 196), 'pressed': (150, 150, 150)}.get(state, FACE)
	if not active and state == 'normal':
		face = (150, 150, 150)
	bevel(d, x0, y0, x0 + BS - 1, y0 + BS - 1, face, state == 'pressed')
	o = 1 if state == 'pressed' else 0
	glyph(d, kind, x0 + 1 + o, y0 + 1 + o, BS - 3, BLACK if active else (60, 60, 60))
	return im

# the bar along the bottom: gray, raised, cut by a line GRIP in from each end
def bottombar(w, active):
	im = Image.new('RGB', (w, BB), FACE)
	d = ImageDraw.Draw(im)
	d.line((0, 0, w, 0), fill=BLACK)                 # the window's own edge
	d.line((0, 1, w, 1), fill=WHITE)
	d.line((0, BB - 1, w, BB - 1), fill=BLACK)
	d.line((0, BB - 2, w, BB - 2), fill=DARK)
	d.line((0, 0, 0, BB), fill=BLACK); d.line((w - 1, 0, w - 1, BB), fill=BLACK)
	return im

def grip(active, right):
	im = bottombar(GRIP, active)
	d = ImageDraw.Draw(im)
	x = 0 if right else GRIP - 1
	d.line((x, 1, x, BB - 2), fill=BLACK)
	d.line((x + (1 if right else -1), 2, x + (1 if right else -1), BB - 3), fill=WHITE if right else DARK)
	return im

# ---------- xfce ----------

XFWM_STATES = {'normal': 'active', 'prelight': 'prelight', 'pressed': 'pressed'}

def xfwm4(out):
	d = os.path.join(out, 'themes', NAME, 'xfwm4')
	for act in (True, False):
		s = 'active' if act else 'inactive'
		t = title(8, act)
		ImageDraw.Draw(t).line((0, 0, 0, TH), fill=BLACK)
		save(t, d, 'top-left-%s.png' % s)
		t = title(8, act)
		ImageDraw.Draw(t).line((7, 0, 7, TH), fill=BLACK)
		save(t, d, 'top-right-%s.png' % s)
		for i in range(1, 6):
			save(title(32, act), d, 'title-%d-%s.png' % (i, s))
		save(Image.new('RGB', (B, 16), BLACK), d, 'left-%s.png' % s)
		save(Image.new('RGB', (B, 16), BLACK), d, 'right-%s.png' % s)
		save(grip(act, False), d, 'bottom-left-%s.png' % s)
		save(grip(act, True), d, 'bottom-right-%s.png' % s)
		save(bottombar(16, act).crop((1, 0, 15, BB)), d, 'bottom-%s.png' % s)
		for k in ('hide', 'maximize', 'close', 'menu', 'shade', 'stick', 'maximize-toggled'):
			kind = 'restore' if k == 'maximize-toggled' else k
			for st, name in XFWM_STATES.items():
				if not act and st != 'normal':
					continue
				save(button(kind, st, act), d, '%s-%s.png' % (k, name if act else 'inactive'))
	save_text('''button_offset=2
button_spacing=0
full_width_title=true
title_alignment=center
title_horizontal_offset=0
title_vertical_offset_active=0
title_vertical_offset_inactive=0
title_shadow_active=false
title_shadow_inactive=false
active_text_color=%s
inactive_text_color=%s
maximized_offset=0
shadow_delta_height=0
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=0
shadow_opacity=0
''' % (TEXT[True], TEXT[False]), d, 'themerc')

# ---------- mate and cinnamon: marco and muffin read the same metacity theme ----------

def metacity(out):
	d = os.path.join(out, 'themes', NAME, 'metacity-1')
	# buttons as images, so they match xfce's exactly
	for act in (True, False):
		s = 'active' if act else 'inactive'
		for kind in ('hide', 'maximize', 'restore', 'close', 'menu'):
			for st in ('normal', 'prelight', 'pressed'):
				save(button(kind, st, act), d, '%s-%s-%s.png' % (kind, st, s))
	def ops(kind):
		xml = ''
		for act in (True, False):
			s = 'active' if act else 'inactive'
			for st in ('normal', 'prelight', 'pressed'):
				xml += '''<draw_ops name="%s_%s_%s"><image filename="%s-%s-%s.png" x="0" y="0" width="width" height="height"/></draw_ops>
''' % (kind, st, s, kind, st, s)
		return xml
	frame_ops = ''
	for act in (True, False):
		s = 'active' if act else 'inactive'
		frame_ops += '''<draw_ops name="frame_%(s)s">
  <rectangle color="#000000" x="0" y="0" width="width-1" height="height-1" filled="false"/>
</draw_ops>
<draw_ops name="title_%(s)s">
  <rectangle color="%(bg)s" x="0" y="0" width="width" height="height" filled="true"/>
  <line color="%(hi)s" x1="0" y1="1" x2="width" y2="1"/>
  <line color="#000000" x1="0" y1="height-1" x2="width" y2="height-1"/>
  <title color="%(fg)s" x="(width - title_width) / 2 `max` 2" y="(height - title_height) / 2"/>
</draw_ops>
<draw_ops name="bottom_%(s)s">
  <rectangle color="%(face)s" x="0" y="height-%(bb)d" width="width" height="%(bb)d" filled="true"/>
  <line color="#000000" x1="0" y1="height-%(bb)d" x2="width" y2="height-%(bb)d"/>
  <line color="#ffffff" x1="1" y1="height-%(bb1)d" x2="width-2" y2="height-%(bb1)d"/>
  <line color="%(dark)s" x1="1" y1="height-2" x2="width-2" y2="height-2"/>
  <line color="#000000" x1="0" y1="height-1" x2="width" y2="height-1"/>
  <line color="#000000" x1="%(g)d" y1="height-%(bb)d" x2="%(g)d" y2="height-1"/>
  <line color="#ffffff" x1="%(g1)d" y1="height-%(bb1)d" x2="%(g1)d" y2="height-2"/>
  <line color="#000000" x1="width-%(g1)d" y1="height-%(bb)d" x2="width-%(g1)d" y2="height-1"/>
  <line color="%(dark)s" x1="width-%(g2)d" y1="height-%(bb1)d" x2="width-%(g2)d" y2="height-2"/>
  <line color="#000000" x1="0" y1="0" x2="0" y2="height"/>
  <line color="#000000" x1="width-1" y1="0" x2="width-1" y2="height"/>
</draw_ops>
''' % dict(s=s, bg=hexc(TITLE[act]), hi=hexc(TITLE_HI[act]), fg=TEXT[act], face=hexc(FACE),
	           dark=hexc(DARK), bb=BB, bb1=BB - 1, g=GRIP, g1=GRIP + 1, g2=GRIP + 2)
	buttons = ''
	for act in (True, False):
		s = 'active' if act else 'inactive'
		buttons += '<frame_style name="normal_%s" geometry="normal">\n' % s
		buttons += '  <piece position="entire_background" draw_ops="frame_%s"/>\n' % s
		buttons += '  <piece position="titlebar" draw_ops="title_%s"/>\n' % s
		buttons += '  <piece position="overlay" draw_ops="bottom_%s"/>\n' % s
		for kind, mc in (('hide', 'minimize'), ('maximize', 'maximize'), ('close', 'close'), ('menu', 'menu')):
			for st in ('normal', 'prelight', 'pressed'):
				buttons += '  <button function="%s" state="%s" draw_ops="%s_%s_%s"/>\n' % (mc, st, kind, st, s)
		for st in ('normal', 'prelight', 'pressed'):
			for f in ('shade', 'unshade', 'above', 'unabove', 'stick', 'unstick'):
				buttons += '  <button function="%s" state="%s"><draw_ops></draw_ops></button>\n' % (f, st)
			for f in ('left_left_background', 'left_middle_background', 'left_right_background',
			          'right_left_background', 'right_middle_background', 'right_right_background'):
				buttons += '  <button function="%s" state="%s"><draw_ops></draw_ops></button>\n' % (f, st)
		buttons += '</frame_style>\n'
		buttons += '<frame_style name="max_%s" geometry="max" parent="normal_%s">\n' % (s, s)
		for st in ('normal', 'prelight', 'pressed'):
			buttons += '  <button function="maximize" state="%s" draw_ops="restore_%s_%s"/>\n' % (st, st, s)
		buttons += '  <piece position="overlay"><draw_ops></draw_ops></piece>\n'
		buttons += '</frame_style>\n'
	xml = '''<?xml version="1.0"?>
<metacity_theme>
<info>
  <name>%(name)s</name>
  <author>Chamesle Linux</author>
  <copyright>GPL-3.0-or-later</copyright>
  <date>2026</date>
  <description>Black title bars, gray raised buttons, a resize bar along the bottom</description>
</info>
<frame_geometry name="normal" title_scale="medium" rounded_top_left="false" rounded_top_right="false">
  <distance name="left_width" value="%(b)d"/>
  <distance name="right_width" value="%(b)d"/>
  <distance name="bottom_height" value="%(bb)d"/>
  <distance name="left_titlebar_edge" value="2"/>
  <distance name="right_titlebar_edge" value="2"/>
  <distance name="title_vertical_pad" value="4"/>
  <aspect_ratio name="button" value="1.0"/>
  <border name="title_border" left="2" right="2" top="2" bottom="2"/>
  <border name="button_border" left="0" right="0" top="0" bottom="0"/>
</frame_geometry>
<frame_geometry name="max" parent="normal" has_title="true">
  <distance name="left_width" value="0"/>
  <distance name="right_width" value="0"/>
  <distance name="bottom_height" value="0"/>
</frame_geometry>
<frame_geometry name="small" parent="normal">
  <distance name="bottom_height" value="%(b)d"/>
</frame_geometry>
<frame_geometry name="border" parent="normal" has_title="false">
  <distance name="bottom_height" value="%(b)d"/>
  <distance name="title_vertical_pad" value="0"/>
  <border name="title_border" left="0" right="0" top="0" bottom="0"/>
</frame_geometry>
%(ops)s
%(frame_ops)s
%(buttons)s
<frame_style name="border" geometry="border" parent="normal_active">
  <piece position="titlebar"><draw_ops></draw_ops></piece>
  <piece position="overlay"><draw_ops></draw_ops></piece>
</frame_style>
<frame_style_set name="normal">
  <frame focus="yes" state="normal" resize="both" style="normal_active"/>
  <frame focus="no" state="normal" resize="both" style="normal_inactive"/>
  <frame focus="yes" state="maximized" style="max_active"/>
  <frame focus="no" state="maximized" style="max_inactive"/>
  <frame focus="yes" state="shaded" style="normal_active"/>
  <frame focus="no" state="shaded" style="normal_inactive"/>
  <frame focus="yes" state="maximized_and_shaded" style="max_active"/>
  <frame focus="no" state="maximized_and_shaded" style="max_inactive"/>
</frame_style_set>
<frame_style_set name="border">
  <frame focus="yes" state="normal" resize="both" style="border"/>
  <frame focus="no" state="normal" resize="both" style="border"/>
  <frame focus="yes" state="maximized" style="border"/>
  <frame focus="no" state="maximized" style="border"/>
  <frame focus="yes" state="shaded" style="border"/>
  <frame focus="no" state="shaded" style="border"/>
  <frame focus="yes" state="maximized_and_shaded" style="border"/>
  <frame focus="no" state="maximized_and_shaded" style="border"/>
</frame_style_set>
<window type="normal" style_set="normal"/>
<window type="dialog" style_set="normal"/>
<window type="modal_dialog" style_set="normal"/>
<window type="menu" style_set="normal"/>
<window type="utility" style_set="normal"/>
<window type="border" style_set="border"/>
</metacity_theme>
''' % dict(name=NAME, b=B, bb=BB, ops=''.join(ops(k) for k in ('hide', 'maximize', 'restore', 'close', 'menu')),
	           frame_ops=frame_ops, buttons=buttons)
	for v in (2, 3):
		save_text(xml, d, 'metacity-theme-%d.xml' % v)

# ---------- cinnamon's own panel and menus ----------

CINNAMON = '''@import url("file:///usr/share/cinnamon/theme/cinnamon.css");
/* chamesle gray for the cinnamon panel and menus: gray, raised, square */
#panel, .panel-bottom, .panel-top, .panel-left, .panel-right {
	background-color: #aeaeae;
	background-gradient-direction: none;
	border-top: 1px solid #ffffff;
	box-shadow: none;
	color: #000000;
	font-weight: normal;
}
.panel-bottom { border-top: 1px solid #ffffff; }
#panel StLabel, .panel-bottom StLabel, .applet-label { color: #000000; text-shadow: none; }
.applet-box { color: #000000; }
.applet-box:hover, .applet-box:checked { background-color: #c4c4c4; }
.window-list-item-box, .grouped-window-list-item-box {
	border-radius: 0;
	background-color: #aeaeae;
	border-top: 1px solid #ffffff; border-left: 1px solid #ffffff;
	border-bottom: 1px solid #000000; border-right: 1px solid #000000;
	color: #000000;
	margin: 2px 1px;
}
.window-list-item-box:hover, .grouped-window-list-item-box:hover { background-color: #c4c4c4; }
.window-list-item-box:focus, .window-list-item-box:active, .window-list-item-box:checked,
.grouped-window-list-item-box:focus, .grouped-window-list-item-box:active, .grouped-window-list-item-box:checked {
	background-color: #969696;
	background-gradient-direction: none;
	border-top: 1px solid #000000; border-left: 1px solid #000000;
	border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff;
}
.window-list-item-box StLabel, .grouped-window-list-item-box StLabel { color: #000000; }
.menu, .popup-menu-boxpointer, .applet-box .popup-menu, .popup-menu {
	-arrow-background-color: #aeaeae;
	-arrow-border-color: #000000;
	-arrow-border-width: 1px;
	-arrow-border-radius: 0;
	-arrow-base: 0;
	-arrow-rise: 0;
	color: #000000;
}
.popup-menu-content, .menu-context-menu { background-color: #aeaeae; border: 1px solid #000000; border-radius: 0; box-shadow: none; }
.popup-menu-item { color: #000000; }
.popup-menu-item:active, .popup-menu-item:hover { background-color: #000000; color: #ffffff; border-radius: 0; }
.popup-menu-item:active StLabel, .popup-menu-item:hover StLabel { color: #ffffff; }
.popup-separator-menu-item { -gradient-start: #555555; -gradient-end: #555555; -margin-horizontal: 4px; height: 1px; }
.menu-applications-outer-box, .menu-favorites-box, .menu-places-box, .menu-categories-box { color: #000000; }
.menu-favorites-box { background-color: #9a9a9a; border: 1px solid #555555; border-radius: 0; }
.menu-application-button, .menu-category-button { color: #000000; border-radius: 0; }
.menu-application-button-selected, .menu-category-button-selected, .menu-application-button:hover {
	background-color: #000000; color: #ffffff; border-radius: 0;
}
.menu-application-button-selected StLabel, .menu-category-button-selected StLabel { color: #ffffff; }
#menu-search-entry, .menu-search-entry {
	background-color: #ffffff; color: #000000; border-radius: 0;
	border-top: 1px solid #555555; border-left: 1px solid #555555;
	border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff;
	box-shadow: none;
}
.calendar, .calendar-main-box { color: #000000; }
.notification, .notification-button { background-color: #aeaeae; color: #000000; border: 1px solid #000000; border-radius: 0; }
.switcher-list, .info-osd, .osd-window {
	background-color: #aeaeae; color: #000000; border: 1px solid #000000; border-radius: 0; box-shadow: none;
}
.switcher-list .item-box:selected, .switcher-list .item-box:outlined { background-color: #000000; color: #ffffff; border-radius: 0; }
.tooltip, StTooltip { background-color: #ffffe1; color: #000000; border: 1px solid #000000; border-radius: 0; }
'''

def cinnamon(out):
	save_text(CINNAMON, out, 'themes', NAME, 'cinnamon', 'cinnamon.css')

# ---------- kde: frames as nine-piece svgs, all square and opaque ----------

def h6(c):
	return '#%02x%02x%02x' % c

def rect(x, y, w, h, col):
	return '<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>' % (x, y, w, h, h6(col))

# nine pieces of a w x h frame. top/bottom are lists of row colours from the outside in,
# left/right of column colours from the outside in. a corner pixel takes the colour of whichever
# edge line it's on further out
def nine(prefix, w, h, top, bottom, left, right, center):
	p = prefix + '-' if prefix else ''
	t, b, l, r = len(top), len(bottom), len(left), len(right)
	g = {}
	g['top'] = ''.join(rect(l, i, w - l - r, 1, top[i]) for i in range(t))
	g['bottom'] = ''.join(rect(l, h - 1 - i, w - l - r, 1, bottom[i]) for i in range(b))
	g['left'] = ''.join(rect(i, t, 1, h - t - b, left[i]) for i in range(l))
	g['right'] = ''.join(rect(w - 1 - i, t, 1, h - t - b, right[i]) for i in range(r))
	g['center'] = rect(l, t, w - l - r, h - t - b, center)
	def corner(rows, cols, x0, y0, flipx, flipy):
		o = ''
		for yy in range(len(rows)):
			for xx in range(len(cols)):
				col = cols[xx] if xx < yy or (xx == 0) else rows[yy]
				if yy == 0 and xx > 0:
					col = rows[0]
				X = x0 + (len(cols) - 1 - xx if flipx else xx)
				Y = y0 + (len(rows) - 1 - yy if flipy else yy)
				o += rect(X, Y, 1, 1, col)
		return o
	g['topleft'] = corner(top, left, 0, 0, False, False)
	g['topright'] = corner(top, right, w - r, 0, True, False)
	g['bottomleft'] = corner(bottom, left, 0, h - b, False, True)
	g['bottomright'] = corner(bottom, right, w - r, h - b, True, True)
	return ['<g id="%s%s">%s</g>' % (p, k, v) for k, v in g.items()]

def svgdoc(w, h, els):
	return '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">%s</svg>\n' % (w, h, ''.join(els))

def title_rows(act):
	return [BLACK, TITLE_HI[act]] + [TITLE[act]] * (TH - 3) + [BLACK]

BAR = [BLACK, DARK] + [FACE] * (BB - 3) + [WHITE]   # bottom bar, from the outside in (the window's edge last)

def aurorae(out):
	d = os.path.join(out, 'aurorae', 'themes', 'ChamesleGray')
	W = H = 120
	els = []
	for pre, act in (('decoration', True), ('decoration-inactive', False)):
		els += nine(pre, W, H, title_rows(act), BAR[:-1] + [BLACK], [BLACK], [BLACK], FACE)
	for pre, act in (('decoration-maximized', True), ('decoration-maximized-inactive', False)):
		els += nine(pre, W, H, title_rows(act)[1:], [], [], [], FACE)
	save_text(svgdoc(W, H, els), d, 'decoration.svg')
	S = TH - 4
	def bsvg(kind):
		out_ = []
		for st, pst, act in (('active', 'normal', True), ('hover', 'prelight', True), ('pressed', 'pressed', True),
				('inactive', 'normal', False), ('deactivated', 'normal', False)):
			im = button(kind, pst, act, S, S)
			# kwin skips bitmaps inside svgs, so each pixel of the button becomes a rect, rows merged
			px = im.load(); rs = ''
			for y in range(S):
				x = 0
				while x < S:
					c0 = px[x, y]; x1 = x
					while x1 + 1 < S and px[x1 + 1, y] == c0:
						x1 += 1
					rs += rect(x, y, x1 - x + 1, 1, c0)
					x = x1 + 1
			out_.append('<g id="%s-center">%s</g>' % (st, rs))
		return svgdoc(S, S, out_)
	for kind, fn in (('close', 'close'), ('maximize', 'maximize'), ('restore', 'restore'), ('hide', 'minimize')):
		save_text(bsvg(kind), d, fn + '.svg')
	save_text('''[General]
ActiveTextColor=255,255,255
InactiveTextColor=200,200,200
UseTextShadow=false
HaloActive=false
HaloInactive=false
TitleAlignment=Center
TitleVerticalAlignment=Center
Animation=0
Shadow=false

[Layout]
BorderLeft=%d
BorderRight=%d
BorderBottom=%d
BorderTop=0
TitleEdgeTop=2
TitleEdgeBottom=2
TitleEdgeLeft=3
TitleEdgeRight=3
TitleEdgeTopMaximized=1
TitleEdgeBottomMaximized=1
TitleEdgeLeftMaximized=2
TitleEdgeRightMaximized=2
TitleBorderLeft=6
TitleBorderRight=6
TitleHeight=%d
ButtonWidth=%d
ButtonWidthMinimize=%d
ButtonWidthMaximizeRestore=%d
ButtonWidthClose=%d
ButtonHeight=%d
ButtonSpacing=2
ButtonMarginTop=0
ButtonMarginTopMaximized=0
ExplicitButtonSpacer=8
PaddingTop=0
PaddingBottom=0
PaddingLeft=0
PaddingRight=0
''' % (B, B, BB, S, S, S, S, S, S), d, 'ChamesleGrayrc')
	save_text('''[Desktop Entry]
Name=Chamesle Gray
Comment=Black title bars, gray raised buttons, a resize bar along the bottom
X-KDE-PluginInfo-Author=Chamesle
X-KDE-PluginInfo-Name=ChamesleGray
X-KDE-PluginInfo-Version=0.8.0
X-KDE-PluginInfo-License=GPL-3.0-or-later
''', d, 'metadata.desktop')

PLASMA_COLORS = '''[Colors:Window]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0
ForegroundInactive=60,60,60
DecorationFocus=0,0,0
DecorationHover=255,255,255

[Colors:View]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0
ForegroundInactive=60,60,60
DecorationFocus=0,0,0
DecorationHover=255,255,255

[Colors:Button]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0
DecorationFocus=0,0,0
DecorationHover=255,255,255

[Colors:Selection]
BackgroundNormal=255,255,255
ForegroundNormal=0,0,0

[Colors:Tooltip]
BackgroundNormal=255,255,225
ForegroundNormal=0,0,0

[Colors:Complementary]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0

[Colors:Header]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0
'''

def plasma(out):
	d = os.path.join(out, 'plasma', 'desktoptheme', 'chamesle-gray')
	raised = ([WHITE], [BLACK, DARK], [WHITE], [BLACK, DARK])
	sunk = ([BLACK, DARK], [WHITE], [BLACK, DARK], [WHITE])
	# the panel: gray, a white line where it meets the desktop
	els = []
	for side, (t, b, l, r) in (('', ([WHITE], [DARK], [WHITE], [DARK])), ('south', ([BLACK, WHITE], [FACE], [FACE], [FACE])),
			('north', ([FACE], [DARK, BLACK][::-1], [FACE], [FACE])), ('west', ([FACE], [FACE], [FACE], [BLACK, DARK])),
			('east', ([FACE], [FACE], [BLACK, WHITE], [FACE]))):
		els += nine(side, 64, 32, t, b, l, r, FACE)
	save_text(svgdoc(64, 32, els), d, 'widgets/panel-background.svg')
	# menus and popups: gray with a black line round them
	els = nine('', 64, 64, [BLACK, WHITE], [BLACK, DARK], [BLACK, WHITE], [BLACK, DARK], FACE)
	save_text(svgdoc(64, 64, els), d, 'dialogs/background.svg')
	save_text(svgdoc(64, 64, nine('', 64, 64, [BLACK], [BLACK], [BLACK], [BLACK], (255, 255, 225))), d, 'widgets/tooltip.svg')
	save_text(svgdoc(64, 64, nine('', 64, 64, *raised, FACE)), d, 'widgets/background.svg')
	# the taskbar: each window a raised button, the one you're in pressed in
	els = []
	for pre, fr, col in (('normal', raised, FACE), ('hover', raised, (196, 196, 196)), ('focus', sunk, (150, 150, 150)),
			('attention', raised, (220, 200, 120)), ('minimized', raised, (160, 160, 160))):
		els += nine(pre, 48, 48, *fr, col)
	save_text(svgdoc(48, 48, els), d, 'widgets/tasks.svg')
	save_text('''{
    "KPlugin": {
        "Authors": [{"Name": "Chamesle"}],
        "Description": "Gray panels and menus, raised one pixel",
        "Id": "chamesle-gray",
        "License": "GPL-3.0-or-later",
        "Name": "Chamesle Gray",
        "Version": "0.8.0"
    },
    "X-Plasma-API": "5.0"
}
''', d, 'metadata.json')
	save_text(PLASMA_COLORS, d, 'colors')

def colors(out):
	save_text('''[General]
ColorScheme=ChamesleGray
Name=Chamesle Gray

[ColorEffects:Disabled]
Color=110,110,110
ColorAmount=0
ColorEffect=0
ContrastAmount=0.5
ContrastEffect=1
IntensityAmount=0
IntensityEffect=0

[ColorEffects:Inactive]
ChangeSelectionColor=false
Enable=false

[Colors:Button]
BackgroundAlternate=160,160,160
BackgroundNormal=174,174,174
DecorationFocus=0,0,0
DecorationHover=255,255,255
ForegroundActive=0,0,0
ForegroundInactive=70,70,70
ForegroundLink=0,0,170
ForegroundNegative=170,0,0
ForegroundNeutral=130,90,0
ForegroundNormal=0,0,0
ForegroundPositive=0,110,0
ForegroundVisited=85,26,139

[Colors:Selection]
BackgroundAlternate=240,240,240
BackgroundNormal=255,255,255
DecorationFocus=0,0,0
DecorationHover=85,85,85
ForegroundActive=0,0,0
ForegroundInactive=70,70,70
ForegroundLink=0,0,170
ForegroundNegative=170,0,0
ForegroundNeutral=130,90,0
ForegroundNormal=0,0,0
ForegroundPositive=0,110,0
ForegroundVisited=85,26,139

[Colors:Tooltip]
BackgroundAlternate=255,255,225
BackgroundNormal=255,255,225
DecorationFocus=0,0,0
DecorationHover=0,0,0
ForegroundNormal=0,0,0
ForegroundInactive=70,70,70

[Colors:View]
BackgroundAlternate=240,240,240
BackgroundNormal=255,255,255
DecorationFocus=0,0,0
DecorationHover=85,85,85
ForegroundActive=0,0,0
ForegroundInactive=70,70,70
ForegroundLink=0,0,170
ForegroundNegative=170,0,0
ForegroundNeutral=130,90,0
ForegroundNormal=0,0,0
ForegroundPositive=0,110,0
ForegroundVisited=85,26,139

[Colors:Window]
BackgroundAlternate=160,160,160
BackgroundNormal=174,174,174
DecorationFocus=0,0,0
DecorationHover=255,255,255
ForegroundActive=0,0,0
ForegroundInactive=70,70,70
ForegroundLink=0,0,170
ForegroundNegative=170,0,0
ForegroundNeutral=130,90,0
ForegroundNormal=0,0,0
ForegroundPositive=0,110,0
ForegroundVisited=85,26,139

[Colors:Complementary]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0
DecorationFocus=0,0,0
DecorationHover=255,255,255

[Colors:Header]
BackgroundNormal=174,174,174
ForegroundNormal=0,0,0
DecorationFocus=0,0,0
DecorationHover=255,255,255

[WM]
activeBackground=0,0,0
activeForeground=255,255,255
inactiveBackground=76,76,76
inactiveForeground=200,200,200
''', out, 'color-schemes', 'ChamesleGray.colors')

# ---------- gtk: onestepback, with our title bar ----------
# cinnamon's muffin draws window frames from the gtk theme, not from metacity-1,
# and so do apps that draw their own title bar. everything else is onestepback's

GTK = """@import url("file:///usr/share/themes/OneStepBack/gtk-3.0/gtk.css");
/* chamesle gray: the title bar, the rest is onestepback */
decoration, window.ssd decoration, .titlebar.default-decoration, window { border-radius: 0; }
window.ssd decoration, window.csd decoration { box-shadow: 0 0 0 1px #000000; margin: 4px; }
window.ssd decoration:backdrop, window.csd decoration:backdrop { box-shadow: 0 0 0 1px #000000; }
.titlebar.default-decoration, window.ssd .titlebar, window.ssd headerbar {
	background-color: %(on)s;
	background-image: none;
	color: #ffffff;
	border: none;
	border-radius: 0;
	box-shadow: inset 0 1px %(on_hi)s;
	min-height: 20px;
	padding: 0 2px;
}
.titlebar.default-decoration:backdrop, window.ssd .titlebar:backdrop, window.ssd headerbar:backdrop {
	background-color: %(off)s;
	box-shadow: inset 0 1px %(off_hi)s;
	color: #c8c8c8;
}
.titlebar.default-decoration .title, window.ssd .titlebar .title { color: #ffffff; font-weight: bold; }
.titlebar.default-decoration .title:backdrop, window.ssd .titlebar .title:backdrop { color: #c8c8c8; }
.titlebar.default-decoration button.titlebutton, window.ssd .titlebar button.titlebutton {
	min-width: 14px;
	min-height: 14px;
	padding: 0;
	margin: 2px 1px;
	border-radius: 0;
	border-style: solid;
	border-width: 1px;
	border-color: #ffffff #000000 #000000 #ffffff;
	background-color: %(face)s;
	background-image: none;
	box-shadow: inset -1px -1px %(dark)s;
	color: #000000;
	-gtk-icon-shadow: none;
}
.titlebar.default-decoration button.titlebutton:hover, window.ssd .titlebar button.titlebutton:hover { background-color: #c4c4c4; }
.titlebar.default-decoration button.titlebutton:active, window.ssd .titlebar button.titlebutton:active {
	background-color: #969696;
	border-color: #000000 #ffffff #ffffff #000000;
	box-shadow: inset 1px 1px %(dark)s;
}
.titlebar.default-decoration button.titlebutton:backdrop, window.ssd .titlebar button.titlebutton:backdrop {
	background-color: #969696;
	color: #3c3c3c;
}
"""

def gtk(out):
	d = os.path.join(out, 'themes', NAME)
	save_text(GTK % dict(on=hexc(TITLE[True]), on_hi=hexc(TITLE_HI[True]), off=hexc(TITLE[False]),
		off_hi=hexc(TITLE_HI[False]), face=hexc(FACE), dark=hexc(DARK)), d, 'gtk-3.0', 'gtk.css')
	# gtk 2 and 4 apps get onestepback as it is
	for v in ('gtk-2.0', 'gtk-4.0'):
		l = os.path.join(d, v)
		if not os.path.lexists(l):
			os.symlink('../OneStepBack/' + v, l)

def index(out):
	save_text('''[Desktop Entry]
Type=X-GNOME-Metatheme
Name=%s
Comment=Black title bars and gray raised buttons, like the workstations of 2001
Encoding=UTF-8

[X-GNOME-Metatheme]
GtkTheme=%s
MetacityTheme=%s
IconTheme=Chamesle-Glass
''' % (NAME, NAME, NAME), out, 'themes', NAME, 'index.theme')

if __name__ == '__main__':
	out = sys.argv[1]
	index(out); gtk(out); xfwm4(out); metacity(out); cinnamon(out); aurorae(out); plasma(out); colors(out)
