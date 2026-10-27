#!/usr/bin/env python3
# chamesle glass: window frames, buttons and panels for every desktop
#   make.py SHARE   writes SHARE/themes, SHARE/aurorae, SHARE/plasma, SHARE/color-schemes
import os, sys, math
from PIL import Image, ImageDraw

NAME = 'Chamesle-Glass'
TINT = (60, 145, 215)
TH = 30           # title height, top border included
B = 6             # side and bottom borders
R = 7             # corner radius
BH = 20           # caption buttons hang this far down
BW = {'hide': 28, 'maximize': 27, 'close': 48}
ORDER = ['hide', 'maximize', 'close']
MW = {'hide': 30, 'maximize': 30, 'close': 30}   # metacity has one width for all

# one row of glass: tint under a shine that stops sharp at the middle
def glass(y, h, a, x=0):
	t = y / max(1, h - 1)
	w = .46 - .30 * t / .5 if t < .5 else .10 * (t - .5) / .5
	if (x + y * .47) % 120 < 18:
		w += .07
	al = w + a * (1 - w)
	c = [int((255 * w + TINT[i] * a * (1 - w)) / max(al, .001)) for i in range(3)]
	return (*c, int(255 * al))

def mix(p, q, k):
	return tuple(int(p[i] * (1 - k) + q[i] * k) for i in range(4))

# the whole frame at size w x h, cut into pieces later
def frame(w, h, active):
	a = .60 if active else .33
	im = Image.new('RGBA', (w, h))
	px = im.load()
	for y in range(h):
		for x in range(w):
			px[x, y] = glass(min(y, TH - 1), TH, a, x)
	mb = Image.new('L', (w, h), 0)
	ImageDraw.Draw(mb).rounded_rectangle((0, 0, w - 1, h - 1), R, fill=255)
	k = Image.composite(im, Image.new('RGBA', (w, h)), mb)
	d = ImageDraw.Draw(k)
	d.rounded_rectangle((0, 0, w - 1, h - 1), R, outline=(0, 0, 0, 150))
	d.rounded_rectangle((1, 1, w - 2, h - 2), R - 1, outline=(255, 255, 255, 115 if active else 70))
	# the window sits in a hole; a thin dark line and a white one around it
	d.rectangle((B - 1, TH - 1, w - B, h - B), outline=(255, 255, 255, 90))
	d.rectangle((B, TH, w - B - 1, h - B - 1), fill=(0, 0, 0, 0), outline=(0, 0, 0, 120))
	return k

def glyph(d, kind, x, y, w, h, s=1):
	cx, cy = x + w / 2, y + h / 2
	dk, wh = (20, 30, 45, 230), (255, 255, 255, 255)
	def box(x0, y0, x1, y1, c, wd=0, f=None):
		d.rectangle((cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s), fill=f, outline=c, width=int(wd * s))
	if kind == 'hide':
		box(-5.5, 1.5, 5.5, 5.5, None, 0, dk); box(-4.5, 2.5, 4.5, 4.5, None, 0, wh)
	elif kind == 'maximize':
		box(-6.5, -5.5, 6.5, 5.5, dk, 4); box(-5.5, -4.5, 5.5, 4.5, wh, 2)
	elif kind == 'restore':
		for ox, oy in ((2, -3), (-2, 1)):
			box(-4.5 + ox, -3.5 + oy, 4.5 + ox, 3.5 + oy, dk, 3); box(-3.5 + ox, -2.5 + oy, 3.5 + ox, 2.5 + oy, wh, 1.2)
	elif kind == 'close':
		xs = [((cx - 5 * s, cy - 4 * s), (cx + 5 * s, cy + 4 * s)), ((cx - 5 * s, cy + 4 * s), (cx + 5 * s, cy - 4 * s))]
		for p in xs:
			d.line(p, fill=dk, width=int(5 * s))
		for p in xs:
			d.line(p, fill=wh, width=int(2.6 * s))

def fill(state, red, active):
	if red:
		top, bot = {'prelight': ((255, 190, 170), (232, 72, 40)), 'pressed': ((190, 110, 90), (150, 35, 20))}.get(state, ((238, 160, 140), (200, 60, 40)))
		al = 240 if active or state != 'normal' else 130
	else:
		top, bot = {'prelight': ((225, 245, 255), (90, 175, 240)), 'pressed': ((150, 190, 225), (60, 110, 165))}.get(state, ((235, 245, 252), (150, 185, 215)))
		al = 255 if state != 'normal' else (150 if active else 90)
	return top, bot, al

# the three buttons are drawn as one strip and cut apart, so they join
def button(kind, state, active, w=None, widths=None):
	base = 'maximize' if kind == 'restore' else kind
	ws = dict(widths or BW)
	if w:
		ws[base] = w
	tw = sum(ws[k] for k in ORDER)
	im = Image.new('RGBA', (tw, BH))
	px = im.load()
	x0 = 0
	for k in ORDER:
		top, bot, al = fill(state if k == base else 'normal', k == 'close', active)
		for y in range(BH):
			t = y / (BH - 1)
			c = [int(top[i] + (bot[i] - top[i]) * t) for i in range(3)]
			if t < .5:
				c = [int(v + (255 - v) * .45) for v in c]
			for x in range(x0, x0 + ws[k]):
				px[x, y] = (*c, al)
		x0 += ws[k]
	m = Image.new('L', (tw, BH), 0)
	ImageDraw.Draw(m).rounded_rectangle((0, -8, tw - 1, BH - 1), 6, fill=255)
	im = Image.composite(im, Image.new('RGBA', (tw, BH)), m)
	d = ImageDraw.Draw(im)
	d.rounded_rectangle((0, -8, tw - 1, BH - 1), 6, outline=(0, 0, 0, 170))
	d.rounded_rectangle((1, -8, tw - 2, BH - 2), 5, outline=(255, 255, 255, 120))
	x0 = 0
	for k in ORDER:
		if k == base:
			break
		x0 += ws[k]
	if x0:
		d.line((x0, 0, x0, BH - 2), fill=(0, 0, 0, 150))
		d.line((x0 + 1, 1, x0 + 1, BH - 3), fill=(255, 255, 255, 90))
	if base != ORDER[-1]:
		e = x0 + ws[base]
		d.line((e, 0, e, BH - 2), fill=(0, 0, 0, 150))
	# symbols at 4x, scaled down so they come out smooth
	S = 4
	g = Image.new('RGBA', (ws[base] * S, BH * S))
	glyph(ImageDraw.Draw(g), kind, 0, 0, ws[base] * S, BH * S, S)
	im.alpha_composite(g.resize((ws[base], BH), Image.LANCZOS), (x0, 0))
	return im.crop((x0, 0, x0 + ws[base], BH))

# window managers without alpha in frames: glass over a sky colour, edges cut sharp
def flat(im):
	w, h = im.size
	back = Image.new('RGBA', (w, h))
	px = back.load()
	for y in range(h):
		t = min(y, TH) / TH
		c = tuple(int(a + (b - a) * t) for a, b in zip((150, 188, 222), (104, 150, 196)))
		for x in range(w):
			px[x, y] = (*c, 255)
	back.alpha_composite(im)
	m = im.getchannel('A').point(lambda v: 255 if v > 40 else 0)
	back.putalpha(m)
	return back

def save(im, *p):
	f = os.path.join(*p)
	os.makedirs(os.path.dirname(f), exist_ok=True)
	im.save(f)

# a button on its piece of title, for window managers that don't blend them
def on_title(btn, active, x0, h=TH):
	a = .60 if active else .33
	im = Image.new('RGBA', (btn.width, h))
	px = im.load()
	for y in range(h):
		for x in range(btn.width):
			px[x, y] = glass(y, TH, a, x0 + x)
	ImageDraw.Draw(im).line((0, 0, btn.width, 0), fill=(0, 0, 0, 150))
	ImageDraw.Draw(im).line((0, 1, btn.width, 1), fill=(255, 255, 255, 115 if active else 70))
	im.alpha_composite(btn, (0, 1))
	return im

STATES = {'normal': 'active', 'prelight': 'prelight', 'pressed': 'pressed'}

def xfwm4(out):
	d = os.path.join(out, 'themes', NAME, 'xfwm4')
	W, H = 240, 120
	for act in (True, False):
		f = flat(frame(W, H, act))
		s = 'active' if act else 'inactive'
		save(f.crop((0, 0, R + 1, TH)), d, 'top-left-%s.png' % s)
		save(f.crop((W - R - 1, 0, W, TH)), d, 'top-right-%s.png' % s)
		for i in range(1, 6):
			save(f.crop((R + 1, 0, R + 1 + 120, TH)), d, 'title-%d-%s.png' % (i, s))
		save(f.crop((0, TH, B, TH + 20)), d, 'left-%s.png' % s)
		save(f.crop((W - B, TH, W, TH + 20)), d, 'right-%s.png' % s)
		save(f.crop((0, H - B, R + 1, H)), d, 'bottom-left-%s.png' % s)
		save(f.crop((W - R - 1, H - B, W, H)), d, 'bottom-right-%s.png' % s)
		save(f.crop((R + 1, H - B, R + 21, H)), d, 'bottom-%s.png' % s)
		x = 0
		for k in ORDER + ['maximize-toggled']:
			kind = 'restore' if k == 'maximize-toggled' else k
			for st, name in STATES.items():
				if not act and st != 'normal':
					continue
				b = flat(on_title(button(kind, st, act), act, x))
				save(b, d, '%s-%s.png' % (k, name if act else 'inactive'))
			if k != 'maximize-toggled':
				x += BW[k]
	open(os.path.join(d, 'themerc'), 'w').write('''button_offset=0
button_spacing=0
full_width_title=true
title_alignment=left
title_horizontal_offset=6
title_vertical_offset_active=1
title_vertical_offset_inactive=1
title_shadow_active=false
title_shadow_inactive=false
active_text_color=#0f2030
inactive_text_color=#3a4b5c
maximized_offset=0
shadow_delta_height=2
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=-4
shadow_opacity=45
''')

# marco and muffin read the same metacity theme
def metacity(out):
	d = os.path.join(out, 'themes', NAME, 'metacity-1')
	W, H = 240, 120
	for act in (True, False):
		f = flat(frame(W, H, act))
		s = 'active' if act else 'inactive'
		for n, box in {'tl': (0, 0, R + 1, TH), 'title': (R + 1, 0, R + 121, TH), 'tr': (W - R - 1, 0, W, TH),
				'l': (0, TH, B, TH + 20), 'r': (W - B, TH, W, TH + 20),
				'bl': (0, H - B, R + 1, H), 'b': (R + 1, H - B, R + 21, H), 'br': (W - R - 1, H - B, W, H)}.items():
			save(f.crop(box), d, '%s-%s.png' % (n, s))
		for k in ORDER + ['restore']:
			for st in ('normal', 'prelight', 'pressed'):
				save(flat(on_title(button(k, st, act, widths=MW), act, 0, BH + 1)), d, '%s-%s-%s.png' % (k, st, s))
	def img(f, x, y, w, h, fill='tile'):
		return '<image filename="%s" x="%s" y="%s" width="%s" height="%s" fill_type="%s"/>' % (f, x, y, w, h, fill)
	def ops(s):
		return ''.join([
			img('tl-%s.png' % s, 0, 0, R + 1, TH),
			img('title-%s.png' % s, R + 1, 0, 'width-%d' % (2 * R + 2), TH),
			img('tr-%s.png' % s, 'width-%d' % (R + 1), 0, R + 1, TH),
			img('l-%s.png' % s, 0, TH, B, 'height-%d' % (TH + B)),
			img('r-%s.png' % s, 'width-%d' % B, TH, B, 'height-%d' % (TH + B)),
			img('bl-%s.png' % s, 0, 'height-%d' % B, R + 1, B),
			img('b-%s.png' % s, R + 1, 'height-%d' % B, 'width-%d' % (2 * R + 2), B),
			img('br-%s.png' % s, 'width-%d' % (R + 1), 'height-%d' % B, R + 1, B)])
	def btn(fn, k):
		o = []
		for st in ('normal', 'prelight', 'pressed'):
			o.append('<button function="%s" state="%s"><draw_ops>%s</draw_ops></button>' % (fn, st,
				img('%s-%s-active.png' % (k, st), 0, 0, 'width', 'height', 'scale')))
		return ''.join(o)
	def btn_in(fn, k):
		return ''.join('<button function="%s" state="%s"><draw_ops>%s</draw_ops></button>' % (fn, st,
			img('%s-normal-inactive.png' % k, 0, 0, 'width', 'height', 'scale')) for st in ('normal', 'prelight', 'pressed'))
	none = ''.join('<button function="%s" state="%s"><draw_ops></draw_ops></button>' % (f, s)
		for f in ('menu', 'shade', 'unshade', 'above', 'unabove', 'stick', 'unstick',
			'left_left_background', 'left_middle_background', 'left_right_background',
			'right_left_background', 'right_middle_background', 'right_right_background') for s in ('normal', 'prelight', 'pressed'))
	xml = '''<?xml version="1.0"?>
<metacity_theme>
<info><name>%s</name><author>Chamesle</author><copyright>GPL-3.0-or-later</copyright><date>2026</date><description>Chamesle Glass</description></info>
<frame_geometry name="normal" title_scale="medium" rounded_top_left="%d" rounded_top_right="%d" rounded_bottom_left="%d" rounded_bottom_right="%d">
<distance name="left_width" value="%d"/><distance name="right_width" value="%d"/><distance name="bottom_height" value="%d"/>
<distance name="left_titlebar_edge" value="8"/><distance name="right_titlebar_edge" value="8"/>
<distance name="title_vertical_pad" value="4"/>
<border name="title_border" left="2" right="2" top="1" bottom="0"/>
<border name="button_border" left="0" right="0" top="0" bottom="0"/>
<distance name="button_width" value="30"/><distance name="button_height" value="%d"/>
</frame_geometry>
<frame_geometry name="max" parent="normal" rounded_top_left="false" rounded_top_right="false" rounded_bottom_left="false" rounded_bottom_right="false">
<distance name="left_width" value="0"/><distance name="right_width" value="0"/><distance name="bottom_height" value="0"/>
</frame_geometry>
<draw_ops name="title_active"><title x="2" y="(height - title_height) / 2" color="#0f2030"/></draw_ops>
<draw_ops name="title_inactive"><title x="2" y="(height - title_height) / 2" color="#3a4b5c"/></draw_ops>
<draw_ops name="frame_active">%s</draw_ops>
<draw_ops name="frame_inactive">%s</draw_ops>
<frame_style name="active" geometry="normal">
<piece position="entire_background" draw_ops="frame_active"/><piece position="title" draw_ops="title_active"/>
%s%s%s%s
</frame_style>
<frame_style name="inactive" geometry="normal">
<piece position="entire_background" draw_ops="frame_inactive"/><piece position="title" draw_ops="title_inactive"/>
%s%s%s%s
</frame_style>
<frame_style name="max_active" geometry="max" parent="active"/>
<frame_style name="max_inactive" geometry="max" parent="inactive"/>
<frame_style_set name="normal">
<frame focus="yes" state="normal" resize="both" style="active"/><frame focus="no" state="normal" resize="both" style="inactive"/>
<frame focus="yes" state="maximized" style="max_active"/><frame focus="no" state="maximized" style="max_inactive"/>
<frame focus="yes" state="shaded" style="active"/><frame focus="no" state="shaded" style="inactive"/>
<frame focus="yes" state="maximized_and_shaded" style="max_active"/><frame focus="no" state="maximized_and_shaded" style="max_inactive"/>
</frame_style_set>
<window type="normal" style_set="normal"/><window type="dialog" style_set="normal"/><window type="modal_dialog" style_set="normal"/>
<window type="menu" style_set="normal"/><window type="utility" style_set="normal"/><window type="border" style_set="normal"/>
</metacity_theme>
''' % (NAME, R, R, 0, 0, B, B, B, BH, ops('active'), ops('inactive'),
		btn('close', 'close'), btn('maximize', 'maximize'), btn('minimize', 'hide'), none,
		btn_in('close', 'close'), btn_in('maximize', 'maximize'), btn_in('minimize', 'hide'), none)
	# restore uses its own glyph
	xml = xml.replace('<frame_style name="max_active" geometry="max" parent="active"/>',
		'<frame_style name="max_active" geometry="max" parent="active">%s</frame_style>' % btn('maximize', 'restore'))
	xml = xml.replace('<frame_style name="max_inactive" geometry="max" parent="inactive"/>',
		'<frame_style name="max_inactive" geometry="max" parent="inactive">%s</frame_style>' % btn_in('maximize', 'restore'))
	for v in ('2', '3'):
		open(os.path.join(d, 'metacity-theme-%s.xml' % v), 'w').write(xml)

GTK = '''@import url("resource:///org/gtk/libgtk/theme/Adwaita/gtk-contained.css");
/* chamesle glass: adwaita underneath, 2007 on top */
@define-color theme_selected_bg_color #3d8ee0;
@define-color accent #3d8ee0;
@define-color glass rgba(60, 145, 215, .6);

button, .button {
	border: 1px solid #7a8a99;
	border-radius: 3px;
	background-image: linear-gradient(to bottom, #fbfcfd 0%, #eef1f4 48%, #dde3e9 50%, #cfd6dd 100%);
	box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .7);
	text-shadow: none;
}
button:hover {
	border-color: #3c7fb1;
	background-image: linear-gradient(to bottom, #eaf6fd 0%, #d9f0fc 48%, #bee6fd 50%, #a7d9f5 100%);
}
button:active, button:checked {
	border-color: #2c628b;
	background-image: linear-gradient(to bottom, #c2e4f6 0%, #a9d9f2 48%, #90cbeb 50%, #6fb8e0 100%);
	box-shadow: inset 0 1px 2px rgba(0, 0, 0, .25);
}
button.suggested-action {
	border-color: #2c628b; color: #fff;
	background-image: linear-gradient(to bottom, #8fd0f7 0%, #4ea6e6 48%, #2f87d0 50%, #3b98dc 100%);
}
button.destructive-action {
	border-color: #8b2c1d; color: #fff;
	background-image: linear-gradient(to bottom, #f5a48c 0%, #e0583e 48%, #c2341b 50%, #db4d30 100%);
}
button.flat, button.titlebutton, .sidebar button, headerbar button.image-button:not(:hover) { background-image: none; border-color: transparent; box-shadow: none; }

entry {
	border: 1px solid #abadb3; border-top-color: #707070; border-radius: 2px;
	background-color: #fff; box-shadow: inset 0 1px 2px rgba(0, 0, 0, .12);
}
entry:focus { border-color: #3d8ee0; box-shadow: inset 0 1px 2px rgba(0, 0, 0, .12), 0 0 0 1px rgba(61, 142, 224, .35); }

headerbar, .titlebar:not(headerbar) {
	border-bottom: 1px solid rgba(0, 0, 0, .45);
	background-image: linear-gradient(to bottom, rgba(255,255,255,.46) 0%, rgba(255,255,255,.16) 46%, rgba(255,255,255,0) 50%, rgba(255,255,255,.1) 100%);
	background-color: #5aa3dc;
	box-shadow: inset 0 1px rgba(255, 255, 255, .45);
	color: #0f2030;
}
headerbar:backdrop { background-color: #a9c6dc; }
headerbar .title { font-weight: normal; }

menu, .menu, .context-menu, popover.menu > contents {
	border: 1px solid #979797; border-radius: 0;
	background-color: #f0f0f0;
	background-image: linear-gradient(to right, transparent 28px, #e2e3e3 28px, #e2e3e3 29px, #fff 29px, #fff 30px, transparent 30px);
	padding: 2px;
}
menu menuitem:hover, .menu menuitem:hover, popover.menu modelbutton:hover {
	border: 1px solid #a8d8eb; border-radius: 3px; color: #000;
	background-image: linear-gradient(to bottom, #f1f8fb, #d6ecf6);
}

progressbar trough { border: 1px solid #8a8a8a; border-radius: 3px; background-image: linear-gradient(to bottom, #f3f3f3, #dcdcdc 50%, #cfcfcf 50%, #e6e6e6); min-height: 14px; }
progressbar progress {
	border: 1px solid #1d8a1d; border-radius: 2px; min-height: 12px;
	background-image: radial-gradient(circle at 20% 50%, rgba(255,255,255,.7) 1px, transparent 2px),
		radial-gradient(circle at 60% 30%, rgba(255,255,255,.6) 1px, transparent 2px),
		linear-gradient(to bottom, #a8f0a0 0%, #3fd23a 48%, #1fb31a 50%, #39cc33 100%);
	background-size: 24px 12px, 34px 12px, auto;
}

scale trough { border: 1px solid #a0a0a0; border-radius: 3px; background-image: linear-gradient(to bottom, #e7eaea, #fff); min-height: 4px; }
scale highlight { border-radius: 3px; background-image: linear-gradient(to bottom, #8fd0f7, #3b98dc); }
scale slider { border: 1px solid #3c7fb1; border-radius: 50%%; background-image: radial-gradient(circle at 50%% 30%%, #fff, #bfe6ff 55%%, #4ea6e6); min-width: 16px; min-height: 16px; }

check, radio { border: 1px solid #8e8f8f; background-image: linear-gradient(to bottom, #f4f4f4, #dedede); }
check:checked, radio:checked { border-color: #3c7fb1; background-color: #3d8ee0; }

notebook > header tab { border: 1px solid #898c95; border-bottom: none; border-radius: 3px 3px 0 0; margin: 0 1px; background-image: linear-gradient(to bottom, #f2f2f2, #ebebeb 50%, #dddddd 50%, #cfcfcf); }
notebook > header tab:checked { background-image: none; background-color: #fff; }

selection, *:selected, row:selected, treeview.view:selected, iconview:selected, flowboxchild:selected {
	color: #000;
	background-color: #cce8ff;
	background-image: linear-gradient(to bottom, #dcebfc, #c1dcfc);
}
row:hover:not(:selected) { background-image: linear-gradient(to bottom, #fafbfd, #ebf3fd); }
.sidebar, placessidebar list { background-color: #f1f5fb; }

tooltip.background { border: 1px solid #767676; border-radius: 2px; background-image: linear-gradient(to bottom, #fff, #e4e5f0); color: #3a3a3a; }
tooltip * { color: #3a3a3a; }

/* caption buttons hang from the top edge, joined, close in red */
window headerbar button.titlebutton.titlebutton, window .titlebar button.titlebutton.titlebutton {
	margin: -6px 0 0 0; padding: 0 6px; min-height: 18px; min-width: 16px;
	border: 1px solid rgba(0, 0, 0, .6); border-top: none; border-radius: 0;
	background-image: linear-gradient(to bottom, #f3f8fc 0%, #dfe9f2 50%, #b5cadd 50%, #96b9d7 100%);
	box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .45);
	color: #fff; -gtk-icon-shadow: 0 0 2px #141e2d, 0 0 1px #141e2d;
}
window headerbar button.titlebutton.titlebutton:hover, window .titlebar button.titlebutton.titlebutton:hover { background-image: linear-gradient(to bottom, #e1f5ff 0%, #b8e1fa 50%, #6fbaf0 50%, #5aaee8 100%); }
window headerbar button.titlebutton.titlebutton.minimize, window .titlebar button.titlebutton.titlebutton.minimize { border-radius: 0 0 0 5px; }
window headerbar button.titlebutton.titlebutton.close, window .titlebar button.titlebutton.titlebutton.close {
	min-width: 30px; border-radius: 0 0 5px 0;
	background-image: linear-gradient(to bottom, #f5c1b2 0%, #e8907a 50%, #d0442a 50%, #c8432b 100%);
}
window headerbar button.titlebutton.titlebutton.close:hover, window .titlebar button.titlebutton.titlebutton.close:hover { background-image: linear-gradient(to bottom, #ffd3c6 0%, #f8a088 50%, #e8481f 50%, #e05a3a 100%); }
window headerbar button.titlebutton.titlebutton + button.titlebutton, window .titlebar button.titlebutton.titlebutton + button.titlebutton { border-left: none; }

/* panels: dark glass */
.xfce4-panel.background, PanelToplevel, .mate-panel-menu-bar, #PanelApplet, panel-toplevel, .mate-panel {
	background-color: rgba(25, 50, 75, .62);
	background-image: linear-gradient(to bottom, rgba(255,255,255,.32) 0%, rgba(255,255,255,.08) 48%, rgba(255,255,255,0) 50%, rgba(255,255,255,.06) 100%);
	border-top: 1px solid rgba(0, 0, 0, .55);
	box-shadow: inset 0 1px rgba(255, 255, 255, .35);
	color: #fff;
}
.xfce4-panel button, .mate-panel-menu-bar button, PanelToplevel button { background-image: none; border-color: transparent; box-shadow: none; color: #fff; }
.xfce4-panel button:hover, PanelToplevel button:hover {
	border-color: rgba(255, 255, 255, .45);
	background-image: linear-gradient(to bottom, rgba(255,255,255,.3), rgba(255,255,255,.08) 50%, rgba(255,255,255,0) 50%, rgba(255,255,255,.12));
}
.xfce4-panel button:checked, PanelToplevel button:checked {
	border-color: rgba(255, 255, 255, .55);
	background-image: radial-gradient(ellipse at 50% 120%, rgba(60,145,215,1) 0%, rgba(60,145,215,.35) 55%, rgba(255,255,255,.12) 100%);
}
.xfce4-panel label, PanelToplevel label, .mate-panel label { color: #fff; text-shadow: 0 0 4px rgba(0, 0, 0, .8); }
'''.replace('%%', '%')

def gtk(out):
	d = os.path.join(out, 'themes', NAME)
	os.makedirs(os.path.join(d, 'gtk-3.0'), exist_ok=True)
	open(os.path.join(d, 'gtk-3.0', 'gtk.css'), 'w').write(GTK)
	open(os.path.join(d, 'index.theme'), 'w').write('''[Desktop Entry]
Type=X-GNOME-Metatheme
Name=%s
Comment=Glass frames and glossy buttons, like 2007

[X-GNOME-Metatheme]
GtkTheme=%s
MetacityTheme=%s
IconTheme=Chamesle-Glass
''' % (NAME, NAME, NAME))

CINNAMON = '''@import url("file:///usr/share/cinnamon/theme/cinnamon.css");
/* chamesle glass for the cinnamon panel and menus */
#panel, .panel-bottom, .panel-top, .panel-left, .panel-right {
	background-gradient-direction: vertical;
	background-gradient-start: rgba(90, 140, 185, .62);
	background-gradient-end: rgba(15, 35, 55, .78);
	border-top: 1px solid rgba(0, 0, 0, .6);
	box-shadow: inset 0 1px 0 rgba(255, 255, 255, .35);
	color: #fff;
}
.window-list-item-box, .grouped-window-list-item-box { border-radius: 3px; border: 1px solid transparent; }
.window-list-item-box:hover, .grouped-window-list-item-box:hover { border-color: rgba(255, 255, 255, .45); background-color: rgba(255, 255, 255, .15); }
.window-list-item-box:focus, .window-list-item-box:active, .grouped-window-list-item-box:focus, .grouped-window-list-item-box:active {
	border-color: rgba(255, 255, 255, .55);
	background-gradient-direction: vertical;
	background-gradient-start: rgba(255, 255, 255, .25);
	background-gradient-end: rgba(60, 145, 215, .85);
}
.menu, .popup-menu-boxpointer, .applet-box .popup-menu {
	-arrow-background-color: rgba(25, 50, 75, .9);
	-arrow-border-color: rgba(0, 0, 0, .6);
	-arrow-border-width: 1px;
	-arrow-border-radius: 6px;
	color: #fff;
}
.popup-menu-item:active, .popup-menu-item:hover { background-color: rgba(255, 255, 255, .2); border-radius: 3px; }
.menu-applications-outer-box, .menu-favorites-box, .menu-places-box { color: #fff; }
'''

def cinnamon(out):
	d = os.path.join(out, 'themes', NAME, 'cinnamon')
	os.makedirs(d, exist_ok=True)
	open(os.path.join(d, 'cinnamon.css'), 'w').write(CINNAMON)

# svg frames for plasma and aurorae: nine pieces, each a plain shape with an id
# (qt's svg renderer skips nested svgs and rgba(), so fills are hex plus an opacity)
def paint(c):
	return 'fill="#%02x%02x%02x" fill-opacity="%.2f"' % (c[0], c[1], c[2], c[3])

def svgframe(prefix, w, h, t, sd, bt, r, rb, base, edge, hi, gloss=None):
	p = prefix + '-' if prefix else ''
	gid = 'g' + (prefix or 'f').replace('-', '')
	defs = ''
	if gloss == 'top':
		defs = ('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="%d">'
			'<stop offset="0" stop-color="#fff" stop-opacity=".46"/><stop offset=".46" stop-color="#fff" stop-opacity=".16"/>'
			'<stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".1"/></linearGradient>' % (gid, t))
	elif gloss == 'center':
		defs = ('<linearGradient id="%s" x1="0" y1="0" x2="0" y2="1">'
			'<stop offset="0" stop-color="#fff" stop-opacity=".32"/><stop offset=".48" stop-color="#fff" stop-opacity=".08"/>'
			'<stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".06"/></linearGradient>' % gid)
	def corner(i, cw, ch, rr, mx, my):
		X = lambda x: w - x if mx else x
		Y = lambda y: h - y if my else y
		if rr > i:
			sw = 1 if mx == my else 0
			return 'M%g %gL%g %gA%g %g 0 0 %d %g %gL%g %gL%g %gZ' % (X(i), Y(ch), X(i), Y(rr), rr - i, rr - i, sw, X(rr), Y(i), X(cw), Y(i), X(cw), Y(ch))
		return 'M%g %gL%g %gL%g %gL%g %gZ' % (X(i), Y(ch), X(i), Y(i), X(cw), Y(i), X(cw), Y(ch))
	def band(path_of, fillc):
		return '<path fill-rule="evenodd" d="%s %s" %s/>' % (path_of(0), path_of(1), paint(fillc))
	o = []
	for n, cw, ch, rr, mx, my in (('topleft', sd, t, r, 0, 0), ('topright', sd, t, r, 1, 0), ('bottomleft', sd, bt, rb, 0, 1), ('bottomright', sd, bt, rb, 1, 1)):
		f = lambda i, cw=cw, ch=ch, rr=rr, mx=mx, my=my: corner(i, cw, ch, rr, mx, my)
		g = '<path d="%s" %s/>' % (f(0), paint(base))
		if gloss == 'top' and n.startswith('top'):
			g += '<path d="%s" fill="url(#%s)"/>' % (f(0), gid)
		g += band(f, edge) + band(lambda i, f=f: f(i + 1), hi)
		o.append('<g id="%s%s">%s</g>' % (p, n, g))
	def rect(x, y, rw, rh, c):
		return '<rect x="%g" y="%g" width="%g" height="%g" %s/>' % (x, y, rw, rh, paint(c))
	mid = h - t - bt
	gl = lambda x, y, rw, rh: '<rect x="%g" y="%g" width="%g" height="%g" fill="url(#%s)"/>' % (x, y, rw, rh, gid)
	top = rect(sd, 0, w - 2 * sd, t, base) + (gl(sd, 0, w - 2 * sd, t) if gloss == 'top' else '') + rect(sd, 0, w - 2 * sd, 1, edge) + rect(sd, 1, w - 2 * sd, 1, hi)
	bot = rect(sd, h - bt, w - 2 * sd, bt, base) + rect(sd, h - 1, w - 2 * sd, 1, edge) + rect(sd, h - 2, w - 2 * sd, 1, hi)
	cg = gloss == 'center'
	left = rect(0, t, sd, mid, base) + (gl(0, t, sd, mid) if cg else '') + rect(0, t, 1, mid, edge) + rect(1, t, 1, mid, hi)
	right = rect(w - sd, t, sd, mid, base) + (gl(w - sd, t, sd, mid) if cg else '') + rect(w - 1, t, 1, mid, edge) + rect(w - 2, t, 1, mid, hi)
	center = rect(sd, t, w - 2 * sd, mid, base) + (gl(sd, t, w - 2 * sd, mid) if cg else '')
	for n, g in (('top', top), ('bottom', bot), ('left', left), ('right', right), ('center', center)):
		o.append('<g id="%s%s">%s</g>' % (p, n, g))
	return defs, o

def svgdoc(w, h, defs, els):
	return '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d"><defs>%s</defs>%s</svg>\n' % (w, h, defs, ''.join(els))

def mask(prefix, w, h, t, sd, bt, r, rb):
	k = (0, 0, 0, 1)
	_, o = svgframe(prefix, w, h, t, sd, bt, r, rb, k, k, k)
	return o

PLASMA_COLORS = '''[Colors:Window]
BackgroundNormal=24,52,76
ForegroundNormal=255,255,255
ForegroundInactive=200,215,228
DecorationFocus=110,190,255
DecorationHover=150,210,255

[Colors:View]
BackgroundNormal=24,52,76
ForegroundNormal=255,255,255
ForegroundInactive=200,215,228
DecorationFocus=110,190,255
DecorationHover=150,210,255

[Colors:Button]
BackgroundNormal=60,145,215
ForegroundNormal=255,255,255
DecorationFocus=110,190,255
DecorationHover=150,210,255

[Colors:Selection]
BackgroundNormal=60,145,215
ForegroundNormal=255,255,255

[Colors:Tooltip]
BackgroundNormal=24,52,76
ForegroundNormal=255,255,255

[Colors:Complementary]
BackgroundNormal=24,52,76
ForegroundNormal=255,255,255
'''

def plasma(out):
	d = os.path.join(out, 'plasma', 'desktoptheme', 'chamesle-glass')
	dark, edge, hi = (15, 36, 54, .62), (0, 0, 0, .6), (255, 255, 255, .35)
	for sub in ('', 'translucent/'):
		# the panel: dark glass, shine to the middle
		defs, els = '', []
		for side, r in (('', 3), ('south', 0), ('north', 0), ('east', 0), ('west', 0)):
			df, o = svgframe(side, 96, 48, 3, 3, 3, r, r, dark, edge, hi, 'center')
			defs += df; els += o
			els += mask('mask-' + side if side else 'mask', 96, 48, 3, 3, 3, r, r)
		save_text(svgdoc(96, 48, defs, els), d, sub + 'widgets/panel-background.svg')
		# menus, popups, the start menu
		defs, o = svgframe('', 96, 96, 8, 8, 8, 7, 7, (20, 48, 72, .74), edge, (255, 255, 255, .4), 'top')
		els = o + mask('mask', 96, 96, 8, 8, 8, 7, 7)
		els.append('<rect id="hint-top-margin" x="0" y="0" width="1" height="8" fill="none"/>')
		save_text(svgdoc(96, 96, defs, els), d, sub + 'dialogs/background.svg')
		defs, o = svgframe('', 64, 64, 5, 5, 5, 4, 4, (20, 48, 72, .85), edge, hi)
		save_text(svgdoc(64, 64, defs, o + mask('mask', 64, 64, 5, 5, 5, 4, 4)), d, sub + 'widgets/tooltip.svg')
		defs, o = svgframe('', 96, 96, 8, 8, 8, 7, 7, (60, 145, 215, .45), (0, 0, 0, .5), (255, 255, 255, .4), 'top')
		save_text(svgdoc(96, 96, defs, o + mask('mask', 96, 96, 8, 8, 8, 7, 7)), d, sub + 'widgets/background.svg')
	# open windows on the taskbar; the active one glows
	defs, els = '', []
	for pre, fill, ed, h2, gl in (('focus', (60, 145, 215, .85), (0, 0, 0, .45), (255, 255, 255, .55), 'center'),
			('hover', (255, 255, 255, .16), (0, 0, 0, .4), (255, 255, 255, .45), 'center'),
			('normal', (255, 255, 255, .06), (0, 0, 0, .3), (255, 255, 255, .2), None),
			('attention', (255, 160, 40, .55), (0, 0, 0, .4), (255, 220, 160, .7), 'center'),
			('minimized', (255, 255, 255, 0), (0, 0, 0, 0), (255, 255, 255, 0), None)):
		df, o = svgframe(pre, 48, 48, 4, 4, 4, 3, 3, fill, ed, h2, gl)
		defs += df; els += o
	save_text(svgdoc(48, 48, defs, els), d, 'widgets/tasks.svg')
	save_text('''{
    "KPlugin": {
        "Authors": [{"Name": "Chamesle"}],
        "Description": "Glass panels and menus with the wallpaper showing through",
        "Id": "chamesle-glass",
        "License": "GPL-3.0-or-later",
        "Name": "Chamesle Glass",
        "Version": "0.7"
    },
    "X-Plasma-API": "5.0"
}
''', d, 'metadata.json')
	save_text(PLASMA_COLORS, d, 'colors')

def save_text(text, *p):
	f = os.path.join(*p)
	os.makedirs(os.path.dirname(f), exist_ok=True)
	open(f, 'w').write(text)

def aurorae(out):
	d = os.path.join(out, 'aurorae', 'themes', 'ChamesleGlass')
	W, H = 120, 120
	def piece(prefix, a, shine):
		return svgframe(prefix, W, H, TH, B, B, R, 0, (*TINT, a), (0, 0, 0, .6), (255, 255, 255, .45 if shine else .28), 'top')
	defs1, a = piece('decoration', .45, True)
	defs2, b = piece('decoration-inactive', .22, False)
	defs3, c = piece('decoration-maximized', .45, True)
	defs4, e = piece('decoration-maximized-inactive', .22, False)
	m = mask('mask', W, H, TH, B, B, R, 0)
	save_text(svgdoc(W, H, defs1 + defs2 + defs3 + defs4, a + b + c + e + m), d, 'decoration.svg')
	# buttons: each svg has active, hover, pressed, inactive, deactivated
	# buttons in vectors: kwin skips images inside svgs
	def bsvg(kind, w):
		base = 'maximize' if kind == 'restore' else kind
		h, cx, cy = BH, w / 2, BH / 2
		r = 6
		if base == ORDER[0]:
			shape = 'M0 0H%g V%g H%g A%g %g 0 0 1 0 %g Z' % (w, h, r, r, r, h - r)
			edge = 'M0.5 0V%g A%g %g 0 0 0 %g %g H%g' % (h - r, r - .5, r - .5, r, h - .5, w)
		elif base == ORDER[-1]:
			shape = 'M0 0H%g V%g A%g %g 0 0 1 %g %g H0 Z' % (w, h - r, r, r, w - r, h)
			edge = 'M0 %gH%g A%g %g 0 0 0 %g %g V0' % (h - .5, w - r, r - .5, r - .5, w - .5, h - r)
		else:
			shape = 'M0 0H%g V%g H0 Z' % (w, h)
			edge = 'M0 %gH%g' % (h - .5, w)
		dk, wh = '#141e2d', '#ffffff'
		if kind == 'hide':
			gl = '<rect x="%g" y="%g" width="11" height="4" fill="%s" stroke="%s" stroke-width="1"/>' % (cx - 5.5, cy + 1.5, wh, dk)
		elif kind == 'maximize':
			gl = ''.join('<rect x="%g" y="%g" width="12" height="10" fill="none" stroke="%s" stroke-width="%g"/>' % (cx - 6, cy - 5, c, sw) for c, sw in ((dk, 4), (wh, 2)))
		elif kind == 'restore':
			gl = ''.join('<rect x="%g" y="%g" width="8" height="6" fill="none" stroke="%s" stroke-width="%g"/>' % (cx - 4 + ox, cy - 3 + oy, c, sw)
				for ox, oy in ((2, -3), (-2, 1)) for c, sw in ((dk, 3), (wh, 1.4)))
		else:
			ln = 'M%g %gL%g %gM%g %gL%g %g' % (cx - 5, cy - 4, cx + 5, cy + 4, cx - 5, cy + 4, cx + 5, cy - 4)
			gl = ''.join('<path d="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="round"/>' % (ln, c, sw) for c, sw in ((dk, 5), (wh, 2.6)))
		els, defs = [], []
		for st, pst, act in (('active', 'normal', True), ('hover', 'prelight', True), ('pressed', 'pressed', True),
				('inactive', 'normal', False), ('deactivated', 'normal', False)):
			top, bot, al = fill(pst, base == 'close', act)
			mid = [(top[i] + bot[i]) // 2 for i in range(3)]
			lift = lambda c: '#%02x%02x%02x' % tuple(int(v + (255 - v) * .45) for v in c)
			hexc = lambda c: '#%02x%02x%02x' % tuple(c)
			gid = 'b' + st
			defs.append('<linearGradient id="%s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s"/><stop offset=".5" stop-color="%s"/>'
				'<stop offset=".5" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>' % (gid, lift(top), lift(mid), hexc(mid), hexc(bot)))
			sep = '<rect x="0" y="0" width="1" height="%g" fill="#000" fill-opacity=".55"/>' % (h - 1) if base != ORDER[0] else ''
			els.append('<g id="%s-center" opacity="%.2f"><path d="%s" fill="url(#%s)"/><path d="%s" fill="none" stroke="#000" stroke-opacity=".65"/>%s%s</g>'
				% (st, al / 255, shape, gid, edge, sep, gl))
		return svgdoc(w, h, ''.join(defs), els)
	save_text(bsvg('close', BW['close']), d, 'close.svg')
	save_text(bsvg('maximize', BW['maximize']), d, 'maximize.svg')
	save_text(bsvg('restore', BW['maximize']), d, 'restore.svg')
	save_text(bsvg('hide', BW['hide']), d, 'minimize.svg')
	save_text('''[General]
ActiveTextColor=15,32,48
InactiveTextColor=58,75,92
UseTextShadow=true
ActiveTextShadowColor=255,255,255,190
InactiveTextShadowColor=255,255,255,90
TextShadowOffsetX=0
TextShadowOffsetY=0
HaloActive=true
HaloInactive=false
TitleAlignment=Left
TitleVerticalAlignment=Center
Animation=150
Shadow=true

[Layout]
BorderLeft=%d
BorderRight=%d
BorderBottom=%d
BorderTop=0
TitleEdgeTop=1
TitleEdgeBottom=4
TitleEdgeLeft=8
TitleEdgeRight=8
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=2
TitleEdgeLeftMaximized=6
TitleEdgeRightMaximized=0
TitleBorderLeft=4
TitleBorderRight=8
TitleHeight=%d
ButtonWidth=%d
ButtonWidthMinimize=%d
ButtonWidthMaximizeRestore=%d
ButtonWidthClose=%d
ButtonHeight=%d
ButtonSpacing=0
ButtonMarginTop=0
ButtonMarginTopMaximized=0
ExplicitButtonSpacer=10
PaddingTop=0
PaddingBottom=0
PaddingLeft=0
PaddingRight=0
''' % (B, B, B, TH - 5, BW['hide'], BW['hide'], BW['maximize'], BW['close'], BH), d, 'ChamesleGlassrc')
	save_text('''[Desktop Entry]
Name=Chamesle Glass
Comment=Glass window frames with buttons hanging from the top edge
X-KDE-PluginInfo-Author=Chamesle
X-KDE-PluginInfo-Name=ChamesleGlass
X-KDE-PluginInfo-Version=0.7
X-KDE-PluginInfo-License=GPL-3.0-or-later
''', d, 'metadata.desktop')

def colors(out):
	save_text('''[General]
ColorScheme=ChamesleGlass
Name=Chamesle Glass

[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Enable=false

[Colors:Button]
BackgroundAlternate=221,227,233
BackgroundNormal=238,241,244
DecorationFocus=61,142,224
DecorationHover=60,127,177
ForegroundActive=61,142,224
ForegroundInactive=110,118,126
ForegroundLink=0,102,204
ForegroundNegative=200,50,30
ForegroundNeutral=200,120,0
ForegroundNormal=16,22,30
ForegroundPositive=30,140,30
ForegroundVisited=102,51,153

[Colors:Selection]
BackgroundAlternate=193,220,252
BackgroundNormal=204,232,255
DecorationFocus=61,142,224
DecorationHover=60,127,177
ForegroundActive=0,0,0
ForegroundInactive=58,75,92
ForegroundLink=0,80,160
ForegroundNegative=180,40,20
ForegroundNeutral=160,100,0
ForegroundNormal=0,0,0
ForegroundPositive=20,110,20
ForegroundVisited=90,40,140

[Colors:Tooltip]
BackgroundAlternate=228,229,240
BackgroundNormal=250,250,252
DecorationFocus=61,142,224
DecorationHover=60,127,177
ForegroundNormal=58,58,58
ForegroundInactive=110,118,126

[Colors:View]
BackgroundAlternate=245,248,252
BackgroundNormal=255,255,255
DecorationFocus=61,142,224
DecorationHover=60,127,177
ForegroundActive=61,142,224
ForegroundInactive=110,118,126
ForegroundLink=0,102,204
ForegroundNegative=200,50,30
ForegroundNeutral=200,120,0
ForegroundNormal=16,22,30
ForegroundPositive=30,140,30
ForegroundVisited=102,51,153

[Colors:Window]
BackgroundAlternate=233,238,244
BackgroundNormal=240,243,247
DecorationFocus=61,142,224
DecorationHover=60,127,177
ForegroundActive=61,142,224
ForegroundInactive=110,118,126
ForegroundLink=0,102,204
ForegroundNegative=200,50,30
ForegroundNeutral=200,120,0
ForegroundNormal=16,22,30
ForegroundPositive=30,140,30
ForegroundVisited=102,51,153

[Colors:Complementary]
BackgroundNormal=24,52,76
ForegroundNormal=255,255,255
DecorationFocus=110,190,255
DecorationHover=150,210,255

[Colors:Header]
BackgroundNormal=226,236,246
ForegroundNormal=16,22,30
DecorationFocus=61,142,224
DecorationHover=60,127,177

[WM]
activeBackground=90,163,220
activeForeground=15,32,48
inactiveBackground=169,198,220
inactiveForeground=58,75,92
''', out, 'color-schemes', 'ChamesleGlass.colors')

if __name__ == '__main__':
	out = sys.argv[1] if len(sys.argv) > 1 else 'share'
	gtk(out); xfwm4(out); metacity(out); cinnamon(out); plasma(out); aurorae(out); colors(out)
	print('chamesle glass written to', out)
