#!/usr/bin/env python3
# chamesle glass icons: builds the icon theme from glossy parts
# usage: make.py OUTDIR   (OUTDIR/Chamesle-Glass gets made)
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))

def svg(body, defs=''):
	return ('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">\n'
		'<defs>' + COMMON + defs + '</defs>\n' + body + '\n</svg>\n')

def lin(id, *stops, x2=0, y2=1):
	s = ''.join('<stop offset="%s" stop-color="%s"%s/>' % (o, c, '' if a is None else ' stop-opacity="%s"' % a)
		for o, c, a in [(st + (None,))[:3] for st in stops])
	return '<linearGradient id="%s" x1="0" y1="0" x2="%s" y2="%s">%s</linearGradient>' % (id, x2, y2, s)

def rad(id, *stops, cx=.5, cy=.5, r=.5):
	s = ''.join('<stop offset="%s" stop-color="%s"%s/>' % (o, c, '' if a is None else ' stop-opacity="%s"' % a)
		for o, c, a in [(st + (None,))[:3] for st in stops])
	return '<radialGradient id="%s" cx="%s" cy="%s" r="%s">%s</radialGradient>' % (id, cx, cy, r, s)

COMMON = (rad('shadow', (0, '#000', .45), (1, '#000', 0)) +
	lin('gloss', (0, '#fff', .85), (1, '#fff', .05)) +
	lin('glossd', (0, '#fff', .55), (.55, '#fff', 0), x2=1) +
	lin('paper', (0, '#ffffff'), (1, '#dde5ec')) +
	lin('metal', (0, '#ffffff'), (.5, '#b9c1ca'), (1, '#6f7a86')) +
	'<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.5"/></filter>' +
	'<filter id="soft"><feGaussianBlur stdDeviation="4"/></filter>')

def shadow(cx=64, cy=114, rx=52, ry=7):
	return '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="url(#shadow)"/>' % (cx, cy, rx, ry)

# a white glyph with a dark edge, readable on any colour
def glyph(d, edge='#0b3866', w=5, fill='none'):
	return ('<path d="%s" fill="%s" stroke="%s" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round"/>'
		'<path d="%s" fill="%s" stroke="#fff" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round"/>'
		% (d, 'none' if fill == 'none' else edge, edge, w + 3, d, fill, w))

# glossy bead, the base for round things
def bead(c0, c1, c2, cx=64, cy=62, r=46, inner=''):
	d = rad('b', (0, c0), (.55, c1), (1, c2), cy=.3, r=.75)
	b = (shadow(cx, cy + r + 6, r, 7) +
		'<circle cx="%d" cy="%d" r="%d" fill="url(#b)" stroke="#0d1a2a" stroke-opacity=".7" stroke-width="1.5"/>' % (cx, cy, r) +
		inner +
		'<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="url(#gloss)" opacity=".8"/>' % (cx, cy - r * .48, r * .72, r * .4))
	return b, d

# folders

FOLDER_BACK = '<path d="M12 26a6 6 0 0 1 6-6h30l8 8h56a6 6 0 0 1 6 6v68a6 6 0 0 1-6 6H18a6 6 0 0 1-6-6z" fill="url(#fb)" stroke="#0b3866" stroke-width="1.5"/>'
FOLDER_FRONT = ('<path d="M8 52a6 6 0 0 1 6-6h100a6 6 0 0 1 6 6l-4 50a6 6 0 0 1-6 6H18a6 6 0 0 1-6-6z" fill="url(#ff)" stroke="#0b3866" stroke-width="1.5"/>'
	'<path d="M11 52a4 4 0 0 1 4-4h98a4 4 0 0 1 4 4l-1.6 20c-34 7-68 7-103 0z" fill="url(#gloss)" opacity=".75"/>'
	'<path d="M14 49h100" stroke="#fff" stroke-opacity=".9" stroke-width="1.5" stroke-linecap="round"/>')
FOLDER_DEFS = (lin('fb', (0, '#3b9be0'), (1, '#11508f')) +
	lin('ff', (0, '#8fdcff'), (.45, '#3fa8ee'), (1, '#1667b8')))
PAPERS = ('<rect x="22" y="32" width="86" height="50" rx="3" fill="url(#paper)" stroke="#9aa9b6" transform="rotate(-4 64 57)"/>'
	'<rect x="26" y="38" width="80" height="46" rx="3" fill="url(#paper)" stroke="#9aa9b6" transform="rotate(3 64 61)"/>')

def folder(emblem='', papers=True, open=False):
	front = FOLDER_FRONT
	if open:
		front = ('<path d="M4 58a6 6 0 0 1 6-6h104a6 6 0 0 1 6 7l-8 43a6 6 0 0 1-6 6H18a6 6 0 0 1-6-6z" fill="url(#ff)" stroke="#0b3866" stroke-width="1.5"/>'
			'<path d="M7 58a4 4 0 0 1 4-4h102a4 4 0 0 1 4 4.5l-2.5 14c-34 7-70 7-104 0z" fill="url(#gloss)" opacity=".75"/>')
	return svg(shadow(64, 114, 54, 8) + FOLDER_BACK + (PAPERS if papers else '') + front + emblem, FOLDER_DEFS)

EMBLEMS = {
	'documents': glyph('M54 66h14l8 8v26H54zM68 66v8h8M59 82h12M59 90h12'),
	'download': glyph('M64 64v24M53 78l11 11 11-11M50 98h28'),
	'music': glyph('M60 96V72l16-4v22', w=4.5) + '<circle cx="56" cy="96" r="5" fill="#fff" stroke="#0b3866" stroke-width="2"/><circle cx="72" cy="90" r="5" fill="#fff" stroke="#0b3866" stroke-width="2"/>',
	'pictures': glyph('M48 68h32v28H48z') + '<path d="M51 93l9-10 6 6 4-4 8 8z" fill="#fff"/><circle cx="72" cy="75" r="3" fill="#fff"/>',
	'videos': glyph('M58 70l18 12-18 12z', fill='#fff'),
	'desktop': glyph('M48 68h32v20H48zM58 96h12M64 88v8'),
	'templates': ('<path d="M52 64h18l8 8v28H52z" fill="none" stroke="#0b3866" stroke-width="7" stroke-linejoin="round"/>'
		'<path d="M52 64h18l8 8v28H52z" fill="#fff" fill-opacity=".25" stroke="#fff" stroke-width="4" stroke-dasharray="6 4" stroke-linejoin="round"/>'
		+ glyph('M64 76v14M57 83h14', w=4)),
	'publicshare': glyph('M56 76a5 5 0 1 0 0.1 0M72 76a5 5 0 1 0 0.1 0M46 98c2-10 18-10 20 0M62 98c2-10 18-10 20 0'),
	'remote': glyph('M64 66a16 16 0 1 0 0.1 0M48 82h32M64 66c7 6 7 26 0 32M64 66c-7 6-7 26 0 32', w=3.5),
	'home': ('<path d="M46 78v22h36V78" fill="url(#wall)" stroke="#2b5d8a" stroke-width="1.5"/>'
		'<rect x="58" y="86" width="12" height="14" rx="1.5" fill="#3a8fd6" stroke="#2b5d8a"/>'
		'<path d="M40 80l24-20 24 20" fill="url(#roof)" stroke="#8c3a10" stroke-width="2" stroke-linejoin="round"/>'
		'<path d="M44 76l20-16.5 20 16.5" fill="none" stroke="#fff" stroke-opacity=".6" stroke-width="1.5" stroke-linejoin="round"/>'),
	'git': glyph('M56 64v34M56 88c0-12 16-8 16-20', w=4) + ''.join('<circle cx="%d" cy="%d" r="5" fill="#fff" stroke="#0b3866" stroke-width="2.5"/>' % p for p in [(56, 62), (56, 98), (72, 66)]),
	'games': glyph('M50 76h28a8 8 0 0 1 8 8v4a6 6 0 0 1-11 3l-3-4H56l-3 4a6 6 0 0 1-11-3v-4a8 8 0 0 1 8-8zM56 80v8M52 84h8'),
}
HOME_DEFS = lin('roof', (0, '#ffb36b'), (1, '#d9601f')) + lin('wall', (0, '#ffffff'), (1, '#dfe9f2'))

def emblem_folder(name):
	s = folder(EMBLEMS[name], papers=False)
	return s.replace('</defs>', HOME_DEFS + '</defs>') if name == 'home' else s

# pages, for file types

PAGE = ('<path d="M28 8h52l24 24v80a6 6 0 0 1-6 6H28a6 6 0 0 1-6-6V14a6 6 0 0 1 6-6z" fill="url(#paper)" stroke="#6f7c89" stroke-width="1.5"/>'
	'<path d="M80 8v18a6 6 0 0 0 6 6h18" fill="#e6edf3" stroke="#6f7c89" stroke-width="1.5" stroke-linejoin="round"/>'
	'<path d="M24 14a6 6 0 0 1 6-4h48v14C60 26 40 40 24 60z" fill="url(#glossd)" opacity=".7"/>')

def lines(x0=34, x1=94, y0=44, n=7, gap=9, col='#8fa0b0'):
	return ''.join('<path d="M%d %dh%d" stroke="%s" stroke-width="3" stroke-linecap="round"/>' % (x0, y0 + i * gap, (x1 - x0) - (14 if i % 3 == 2 else 0), col) for i in range(n))

def band(c0, c1, label='', y=86):
	d = lin('band', (0, c0), (.5, c1), (1, c0))
	t = ('<text x="63" y="%d" text-anchor="middle" font-family="DejaVu Sans, sans-serif" font-weight="700" font-size="17" fill="#fff" stroke="#000" stroke-opacity=".25" stroke-width=".8">%s</text>' % (y + 18, label)) if label else ''
	return ('<rect x="22" y="%d" width="82" height="26" fill="url(#band)" stroke="#000" stroke-opacity=".35"/>' % y +
		'<rect x="22" y="%d" width="82" height="11" fill="#fff" opacity=".35"/>' % y + t), d

def page(inner='', defs=''):
	return svg(shadow(64, 118, 44, 6) + PAGE + inner, defs)

def typed(label, c0, c1, inner=None):
	b, d = band(c0, c1, label)
	return page((lines(n=4) if inner is None else inner) + b, d)

# pictures that go on pages or stand alone

PHOTO_DEFS = (lin('sky', (0, '#2f9bf0'), (1, '#c8efff')) + lin('hill', (0, '#8fe35a'), (1, '#2f8a2a')) +
	lin('hill2', (0, '#b7f07a'), (1, '#4fae36')) + rad('sun', (0, '#fffbe0'), (1, '#ffc21f'), cx=.4, cy=.4, r=.6))

def photo(x, y, w, h):
	return ('<clipPath id="pc"><rect x="%d" y="%d" width="%d" height="%d"/></clipPath>' % (x, y, w, h) +
		'<g clip-path="url(#pc)"><rect x="%d" y="%d" width="%d" height="%d" fill="url(#sky)"/>' % (x, y, w, h) +
		'<circle cx="%d" cy="%d" r="%d" fill="url(#sun)"/>' % (x + w * .75, y + h * .28, h * .15) +
		'<path d="M%d %dc%d %d %d %d %d 0s%d %d %d %dv%dH%dz" fill="url(#hill2)"/>' % (x - 4, y + h * .76, w * .22, -h * .24, w * .45, -h * .2, w * .65, w * .38, h * .1, w * .45, -h * .03, h * .4, x - 4) +
		'<path d="M%d %dc%d %d %d %d %d -3s%d 3 %d 0v%dH%dz" fill="url(#hill)"/>' % (x - 4, y + h * .9, w * .25, -h * .2, w * .55, -h * .2, w * .77, w * .27, w * .32, h * .3, x - 4) +
		'</g><rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#5d6873"/>' % (x, y, w, h))

DISC_DEFS = rad('disc', (.2, '#f4f6f8'), (.9, '#c9d1d9'), (1, '#9aa5b0'))
def disc(cx=64, cy=60, r=48):
	return ('<clipPath id="dc"><circle cx="%d" cy="%d" r="%d"/></clipPath>' % (cx, cy, r) +
		'<circle cx="%d" cy="%d" r="%d" fill="url(#disc)" stroke="#5d6873" stroke-width="1.5"/>' % (cx, cy, r) +
		'<g clip-path="url(#dc)" filter="url(#soft)" opacity=".55" transform="translate(%d %d)">' % (cx - 64, cy - 60) +
		'<path d="M64 60L24 10h32z" fill="#ff5fa2"/><path d="M64 60l48-30v28z" fill="#4fd0ff"/>'
		'<path d="M64 60l42 48H78z" fill="#ffe15a"/><path d="M64 60L14 84V62z" fill="#7cff8a"/></g>' +
		'<circle cx="%d" cy="%d" r="%d" fill="#e8edf2" fill-opacity=".8" stroke="#8a96a2"/>' % (cx, cy, r // 3) +
		'<circle cx="%d" cy="%d" r="%d" fill="#fff" stroke="#6f7a86"/>' % (cx, cy, r // 8) +
		'<path d="M%d %dc10-22 %d-26 %d-6" fill="none" stroke="#fff" stroke-opacity=".8" stroke-width="2" stroke-linecap="round"/>' % (cx - r * .78, cy - r * .42, r * 1.3, r * 1.6))

def note_bubble(cx=92, cy=90, r=26):
	return ('<circle cx="%d" cy="%d" r="%d" fill="url(#note)" stroke="#7d200c" stroke-width="1.5"/>' % (cx, cy, r) +
		'<path d="M%d %dV%dl14-4v20" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>' % (cx - 4, cy + 12, cy - 12) +
		'<ellipse cx="%d" cy="%d" rx="5.5" ry="4.5" fill="#fff"/><ellipse cx="%d" cy="%d" rx="5.5" ry="4.5" fill="#fff"/>' % (cx - 8, cy + 12, cx + 6, cy + 6) +
		'<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="url(#gloss)" opacity=".75"/>' % (cx, cy - r * .55, r * .72, r * .38))
NOTE_DEFS = lin('note', (0, '#ffb08a'), (.5, '#f0602e'), (1, '#b8361a'))

def film(x, y, w, h):
	holes = ''.join('<rect x="%d" y="%d" width="6" height="5" rx="1" fill="#e8edf2"/><rect x="%d" y="%d" width="6" height="5" rx="1" fill="#e8edf2"/>' % (x + 4 + i * 11, y + 3, x + 4 + i * 11, y + h - 8) for i in range(int((w - 4) // 11)))
	return ('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="url(#filmg)" stroke="#000"/>' % (x, y, w, h) + holes +
		'<rect x="%d" y="%d" width="%d" height="%d" fill="url(#screen)"/>' % (x + 4, y + 11, w - 8, h - 22))
FILM_DEFS = lin('filmg', (0, '#4a525c'), (1, '#0d0f12')) + lin('screen', (0, '#1f7fd6'), (.6, '#4fc3e8'), (1, '#bff0d0'))

# the chamesle ring: three thick pieces with gaps, like the logo
def ring(cx=64, cy=64, R=30, r=15):
	import math
	def pt(a, rr):
		return cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a))
	def piece(a0, a1, col):
		o0, o1, i0, i1 = pt(a0, R), pt(a1, R), pt(a0, r), pt(a1, r)
		return ('<path d="M%.1f %.1fA%d %d 0 0 1 %.1f %.1fL%.1f %.1fA%d %d 0 0 0 %.1f %.1fz" fill="%s" stroke="#fff" stroke-width="1.2" stroke-linejoin="round"/>'
			% (o0[0], o0[1], R, R, o1[0], o1[1], i1[0], i1[1], r, r, i0[0], i0[1], col))
	return piece(-143, -37, '#00bf63') + piece(-27, 84, '#1a00a8') + piece(96, 207, '#ff3333')

# hand-drawn ones live in parts/*.svg

def part(name):
	with open(os.path.join(HERE, 'parts', name + '.svg')) as f:
		return f.read()

# icons: name -> svg text

ICONS = {}
def add(cat, name, text):
	ICONS[(cat, name)] = text

def build():
	add('places', 'folder', folder())
	add('places', 'folder-open', folder(open=True))
	for e in EMBLEMS:
		add('places', 'folder-' + e, emblem_folder(e))
	add('places', 'user-trash', part('bin'))
	add('places', 'user-trash-full', part('bin-full'))
	b, d = bead('#ffffff', '#e2f1fa', '#7fa9c8', inner=ring(64, 62, 32, 16))
	add('places', 'start-here', svg(b, d))
	b, d = bead('#bdf1ff', '#2f9be0', '#0f4f96', inner=glyph('M64 26a36 36 0 1 0 0.1 0M28 62h72M64 26c14 10 14 62 0 72M64 26c-14 10-14 62 0 72', w=3.5))
	add('places', 'network-workgroup', svg(b, d))

	add('devices', 'computer', part('pc'))
	add('devices', 'drive-harddisk', part('drive'))
	add('devices', 'drive-removable-media', part('usb'))
	add('devices', 'media-optical', svg(shadow(64, 114, 50, 7) + disc(64, 60, 48), DISC_DEFS))
	add('devices', 'media-flash', part('sdcard'))
	add('devices', 'phone', part('phone'))
	add('devices', 'printer', part('printer'))
	add('devices', 'input-keyboard', part('keyboard'))
	add('devices', 'input-mouse', part('mouse'))
	add('devices', 'input-gaming', part('gamepad'))
	add('devices', 'camera-photo', part('camera'))
	add('devices', 'camera-web', part('webcam'))
	add('devices', 'audio-headphones', part('headphones'))
	add('devices', 'audio-speakers', part('speaker'))
	add('devices', 'battery', part('battery'))
	b, d = bead('#a8ecff', '#2f8de4', '#0f4f96', inner=glyph('M52 46l24 24-12 12V38l12 12-24 24', w=4.5))
	add('devices', 'bluetooth', svg(b, d))
	b, d = bead('#bdf1ff', '#2f9be0', '#0f4f96', inner=glyph('M36 56a40 40 0 0 1 56 0M44 66a28 28 0 0 1 40 0M53 76a14 14 0 0 1 22 0M64 86h.1', w=5))
	add('devices', 'network-wireless', svg(b, d))
	add('devices', 'network-wired', part('ethernet'))

	add('mimetypes', 'text-x-generic', page(lines()))
	add('mimetypes', 'text-x-script', page('<rect x="30" y="38" width="66" height="62" rx="3" fill="#0b1820"/>' +
		'<path d="M38 50l8 6-8 6M50 64h14M38 76h40M38 86h28" stroke="#5cff86" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'))
	add('mimetypes', 'text-x-source', page(
		'<path d="M46 52l-10 12 10 12M80 52l10 12-10 12M70 46l-14 36" stroke="#2f7fe0" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>' + lines(y0=94, n=2)))
	b, d = bead('#bdf1ff', '#2f9be0', '#0f4f96', cx=64, cy=72, r=26, inner=glyph('M64 46a26 26 0 1 0 0.1 0M38 72h52M64 46c10 7 10 45 0 52M64 46c-10 7-10 45 0 52', w=2.5))
	add('mimetypes', 'text-html', page(lines(n=2) + b, d))
	add('mimetypes', 'application-pdf', typed('PDF', '#e0452c', '#b8301c'))
	add('mimetypes', 'image-x-generic', page(photo(32, 40, 62, 50), PHOTO_DEFS))
	add('mimetypes', 'audio-x-generic', page(note_bubble(63, 70, 26), NOTE_DEFS))
	add('mimetypes', 'video-x-generic', page(film(30, 46, 66, 48), FILM_DEFS))
	add('mimetypes', 'package-x-generic', part('box'))
	add('mimetypes', 'application-x-archive', part('zip'))
	add('mimetypes', 'application-x-executable', page(
		'<g transform="translate(26 32) scale(.58)">' + part('settings').split('</defs>')[1].replace('</svg>', '') + '</g>', rad('eye', (0, '#bff0ff'), (.55, '#2f8de4'), (1, '#0f4f96'), cy=.3, r=.75)))
	add('mimetypes', 'application-x-cd-image', svg(shadow(64, 114, 50, 7) + disc(64, 60, 48) +
		'<rect x="70" y="72" width="44" height="28" rx="4" fill="url(#ib)" stroke="#0b3866"/><text x="92" y="92" text-anchor="middle" font-family="DejaVu Sans, sans-serif" font-weight="700" font-size="15" fill="#fff">ISO</text>',
		DISC_DEFS + lin('ib', (0, '#8fdcff'), (.5, '#2f8de4'), (1, '#1667b8'))))
	add('mimetypes', 'font-x-generic', page('<text x="62" y="86" text-anchor="middle" font-family="DejaVu Serif, serif" font-size="46" fill="url(#ink)" stroke="#0b2c5a" stroke-width="1">Aa</text>', lin('ink', (0, '#5fb0ff'), (1, '#0f4f96'))))
	add('mimetypes', 'x-office-document', typed('', '#3f8fe8', '#1d5fb4', lines(y0=40, n=5)))
	add('mimetypes', 'x-office-spreadsheet', page(''.join(
		'<rect x="%d" y="%d" width="15" height="9" fill="%s" stroke="#7fb58a"/>' % (32 + c * 16, 40 + r * 10, '#c9ecd0' if r == 0 else '#ffffff') for r in range(6) for c in range(4)) +
		band('#55c060', '#2a9a3a')[0], band('#55c060', '#2a9a3a')[1]))
	add('mimetypes', 'x-office-presentation', page(
		'<rect x="32" y="40" width="62" height="42" fill="#fff4ea" stroke="#d98a4a"/><path d="M40 74V60M52 74V52M64 74V64M76 74V48" stroke="#f08a2e" stroke-width="7"/>' +
		band('#f6a04a', '#d9601f')[0], band('#f6a04a', '#d9601f')[1]))

	add('apps', 'files', part('files'))
	add('apps', 'terminal', part('term'))
	add('apps', 'store', part('store'))
	add('apps', 'settings', part('settings'))
	add('apps', 'music', part('music'))
	add('apps', 'pictures', part('pics'))
	for p in ['editor', 'viewer', 'calculator', 'screenshot', 'monitor', 'diskusage', 'partitions', 'video',
			'updater', 'drivers', 'wine', 'installer', 'pkgimport', 'tweaks', 'help', 'keys', 'volume', 'clipboard', 'mail', 'calendar']:
		add('apps', p, part(p))
	b, d = bead('#bdf1ff', '#2f9be0', '#0f4f96', inner=glyph('M64 38h.1M58 52h6v34M56 86h16', w=6))
	add('apps', 'info', svg(b, d))
	add('apps', 'archive', part('zip'))
	add('apps', 'display', part('pc'))
	add('apps', 'power', part('battery'))
	add('apps', 'bluetooth', ICONS[('devices', 'bluetooth')])
	add('apps', 'network', ICONS[('devices', 'network-wireless')])
	add('apps', 'printer', ICONS[('devices', 'printer')])
	add('apps', 'menu', ICONS[('places', 'start-here')])

# every name an app or file type looks for, pointing at one drawing
ALIASES = {
	('places', 'folder'): 'inode-directory folder-blue default-folder',
	('places', 'folder-home'): 'user-home folder-home default-user-home',
	('places', 'folder-desktop'): 'user-desktop',
	('places', 'folder-download'): 'folder-downloads',
	('places', 'folder-pictures'): 'folder-images',
	('places', 'folder-videos'): 'folder-video folder-movies',
	('places', 'folder-remote'): 'folder-network network-server',
	('places', 'user-trash'): 'trash-empty user-trash-empty',
	('places', 'user-trash-full'): 'trash-full',
	('places', 'start-here'): 'start-here-kde distributor-logo chamesle xfce4-whiskermenu whiskermenu cinnamon-menu mate-menu',
	('places', 'network-workgroup'): 'network-workgroup folder-network network',
	('devices', 'computer'): 'computer-laptop video-display display preferences-desktop-display',
	('devices', 'drive-harddisk'): 'drive-harddisk-system drive-harddisk-solidstate drive-multidisk',
	('devices', 'drive-removable-media'): 'drive-removable-media-usb media-removable drive-removable-media-usb-pendrive',
	('devices', 'media-optical'): 'drive-optical media-optical-cd media-optical-dvd',
	('devices', 'phone'): 'smartphone phone-android',
	('devices', 'input-gaming'): 'applications-games',
	('devices', 'camera-photo'): 'camera',
	('devices', 'battery'): 'battery-full',
	('devices', 'network-wireless'): 'network-wireless-connected',
	('mimetypes', 'text-x-generic'): 'text-plain text-x-readme text-x-log text-x-markdown',
	('mimetypes', 'text-x-script'): 'application-x-shellscript text-x-sh application-x-perl text-x-python text-x-python3',
	('mimetypes', 'text-x-source'): 'text-x-c text-x-csrc text-x-chdr text-x-c++src text-x-rust text-x-go text-x-java application-javascript text-javascript application-json text-css text-x-makefile',
	('mimetypes', 'text-html'): 'application-xhtml+xml text-xml application-xml',
	('mimetypes', 'image-x-generic'): 'image-png image-jpeg image-gif image-webp image-bmp image-tiff image-svg+xml image-x-xcf image-heif image-avif',
	('mimetypes', 'audio-x-generic'): 'audio-mpeg audio-x-flac audio-flac audio-ogg audio-x-vorbis+ogg audio-x-wav audio-mp4 audio-x-opus+ogg audio-aac',
	('mimetypes', 'video-x-generic'): 'video-mp4 video-x-matroska video-webm video-x-msvideo video-quicktime video-mpeg video-ogg',
	('mimetypes', 'package-x-generic'): 'application-x-apk application-vnd.debian.binary-package application-x-deb application-x-rpm application-x-redhat-package-manager application-vnd.flatpak application-vnd.flatpak.ref application-x-flatpak',
	('mimetypes', 'application-x-archive'): 'application-zip application-x-tar application-x-compressed-tar application-x-xz-compressed-tar application-x-zstd-compressed-tar application-x-bzip-compressed-tar application-gzip application-x-gzip application-x-xz application-x-zstd application-x-7z-compressed application-x-rar application-vnd.rar',
	('mimetypes', 'application-x-executable'): 'application-x-sharedlib application-x-object application-x-msdownload application-x-ms-dos-executable application-x-desktop',
	('mimetypes', 'application-x-cd-image'): 'application-x-iso9660-image application-x-raw-disk-image',
	('mimetypes', 'font-x-generic'): 'font-ttf font-otf application-x-font-ttf font-woff',
	('mimetypes', 'x-office-document'): 'application-vnd.oasis.opendocument.text application-msword application-vnd.openxmlformats-officedocument.wordprocessingml.document application-rtf text-rtf',
	('mimetypes', 'x-office-spreadsheet'): 'application-vnd.oasis.opendocument.spreadsheet application-vnd.ms-excel application-vnd.openxmlformats-officedocument.spreadsheetml.sheet text-csv',
	('mimetypes', 'x-office-presentation'): 'application-vnd.oasis.opendocument.presentation application-vnd.ms-powerpoint application-vnd.openxmlformats-officedocument.presentationml.presentation',
	('apps', 'files'): 'system-file-manager org.kde.dolphin dolphin org.xfce.thunar thunar Thunar org.gnome.Nautilus nautilus nemo caja file-manager',
	('apps', 'terminal'): 'utilities-terminal org.kde.konsole konsole org.xfce.terminal xfce4-terminal org.gnome.Console org.gnome.Terminal gnome-terminal mate-terminal terminal xterm',
	('apps', 'store'): 'system-software-install org.chamesle.Store chamesle-store plasmadiscover org.kde.discover flatpak-discover org.gnome.Software gnome-software',
	('apps', 'settings'): 'preferences-system systemsettings org.kde.systemsettings org.gnome.Settings gnome-control-center org.xfce.settings.manager xfce4-settings-manager mate-control-center cinnamon-settings preferences-desktop',
	('apps', 'music'): 'org.kde.elisa elisa multimedia-audio-player audio-player rhythmbox',
	('apps', 'pictures'): 'org.kde.gwenview gwenview org.xfce.ristretto ristretto org.gnome.Loupe org.gnome.eog eog eom image-viewer multimedia-photo-viewer',
	('apps', 'editor'): 'accessories-text-editor org.kde.kate kate org.xfce.mousepad mousepad org.gnome.TextEditor gnome-text-editor xed pluma text-editor',
	('apps', 'viewer'): 'org.kde.okular okular org.gnome.Evince evince org.gnome.Papers xreader atril document-viewer x-office-document-viewer',
	('apps', 'calculator'): 'accessories-calculator org.kde.kcalc kcalc org.gnome.Calculator gnome-calculator mate-calc galculator',
	('apps', 'screenshot'): 'applets-screenshooter org.kde.spectacle spectacle org.xfce.screenshooter xfce4-screenshooter org.gnome.Screenshot gnome-screenshot accessories-screenshot',
	('apps', 'monitor'): 'utilities-system-monitor org.kde.plasma-systemmonitor plasma-systemmonitor ksysguard org.gnome.SystemMonitor gnome-system-monitor mate-system-monitor org.xfce.taskmanager xfce4-taskmanager',
	('apps', 'diskusage'): 'org.kde.filelight filelight baobab org.gnome.baobab',
	('apps', 'partitions'): 'partitionmanager org.kde.partitionmanager gparted org.gnome.DiskUtility gnome-disks drive-harddisk-system',
	('apps', 'video'): 'io.github.celluloid_player.Celluloid celluloid multimedia-video-player totem vlc mpv',
	('apps', 'updater'): 'chamesle-updater system-software-update software-update-available update-manager',
	('apps', 'drivers'): 'chamesle-drivers jockey',
	('apps', 'wine'): 'chamesle-wine wine wine-config',
	('apps', 'installer'): 'jiggity system-installer live-installer calamares',
	('apps', 'pkgimport'): 'pkgimport pkgimport-gui application-x-deb-import',
	('apps', 'tweaks'): 'org.gnome.tweaks gnome-tweak-tool preferences-desktop-tweaks',
	('apps', 'help'): 'help-browser help-contents org.kde.khelpcenter yelp org.gnome.Yelp',
	('apps', 'keys'): 'kwalletmanager org.kde.kwalletmanager seahorse org.gnome.seahorse.Application dialog-password',
	('apps', 'volume'): 'multimedia-volume-control pavucontrol org.pulseaudio.pavucontrol audio-volume-high preferences-desktop-sound',
	('apps', 'clipboard'): 'xfce4-clipman-plugin clipman edit-paste klipper',
	('apps', 'mail'): 'internet-mail thunderbird mail-client',
	('apps', 'calendar'): 'office-calendar org.gnome.Calendar',
	('apps', 'info'): 'kinfocenter org.kde.kinfocenter dialog-information hwinfo',
	('apps', 'archive'): 'org.kde.ark ark xarchiver org.gnome.FileRoller file-roller engrampa utilities-file-archiver',
	('apps', 'display'): 'preferences-desktop-display kscreen kgamma',
	('apps', 'power'): 'org.xfce.powermanager xfce4-power-manager mate-power-manager preferences-system-power',
	('apps', 'bluetooth'): 'blueman bluedevil preferences-system-bluetooth',
	('apps', 'network'): 'nm-applet network-manager preferences-system-network',
	('apps', 'printer'): 'system-config-printer printer-settings',
	('apps', 'menu'): 'kmenuedit alacarte menulibre',
}

INDEX = '''[Icon Theme]
Name=Chamesle Glass
Comment=Oxygen with Chamesle's own icons on top
Inherits=oxygen,breeze,Adwaita,hicolor
Example=folder
Directories=scalable/apps,scalable/places,scalable/devices,scalable/mimetypes,256/apps,16x16/places,22x22/places,24x24/places,32x32/places,48x48/places,64x64/places

[16x16/places]
Size=16
Context=Places
Type=Fixed

[22x22/places]
Size=22
Context=Places
Type=Fixed

[24x24/places]
Size=24
Context=Places
Type=Fixed

[32x32/places]
Size=32
Context=Places
Type=Fixed

[48x48/places]
Size=48
Context=Places
Type=Fixed

[64x64/places]
Size=64
Context=Places
Type=Fixed

[scalable/apps]
Size=128
MinSize=16
MaxSize=512
Type=Scalable
Context=Applications

[scalable/places]
Size=128
MinSize=16
MaxSize=512
Type=Scalable
Context=Places

[scalable/devices]
Size=128
MinSize=16
MaxSize=512
Type=Scalable
Context=Devices

[scalable/mimetypes]
Size=128
MinSize=16
MaxSize=512
Type=Scalable
Context=MimeTypes

[256/apps]
Size=256
MinSize=16
MaxSize=512
Type=Scalable
Context=Applications
'''

# oxygen draws everything else, these are ours
OURS = {('places', 'start-here'), ('apps', 'store'), ('apps', 'updater'), ('apps', 'drivers'),
	('apps', 'wine'), ('apps', 'installer'), ('apps', 'pkgimport')}

def main(out):
	build()
	for k in list(ICONS):
		if k not in OURS:
			del ICONS[k]
	for k in list(ALIASES):
		if k not in OURS:
			del ALIASES[k]
	root = os.path.join(out, 'Chamesle-Glass')
	shutil.rmtree(root, ignore_errors=True)
	for (cat, name), text in ICONS.items():
		d = os.path.join(root, 'scalable', cat)
		os.makedirs(d, exist_ok=True)
		with open(os.path.join(d, name + '.svg'), 'w') as f:
			f.write(text)
	# the 2007 firefox logo, mozilla's own, under the mpl
	os.makedirs(os.path.join(root, '256', 'apps'), exist_ok=True)
	shutil.copy(os.path.join(HERE, 'firefox.png'), os.path.join(root, '256', 'apps', 'firefox.png'))
	# cinnamon paints any svg named -symbolic white, so its menu gets the orb as pngs
	for n in os.listdir(os.path.join(HERE, 'orb')):
		d = os.path.join(root, '%sx%s' % (n[:-4], n[:-4]), 'places')
		os.makedirs(d, exist_ok=True)
		shutil.copy(os.path.join(HERE, 'orb', n), os.path.join(d, 'cinnamon-symbolic.png'))
	for (cat, name), names in ALIASES.items():
		for n in names.split():
			p = os.path.join(root, 'scalable', cat, n + '.svg')
			if not os.path.lexists(p):
				os.symlink(name + '.svg', p)
	with open(os.path.join(root, 'index.theme'), 'w') as f:
		f.write(INDEX)
	print(len(ICONS), 'drawings,', sum(len(v.split()) for v in ALIASES.values()), 'names')

if __name__ == '__main__':
	main(sys.argv[1] if len(sys.argv) > 1 else '.')
