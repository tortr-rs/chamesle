#!/usr/bin/env python3
# the default wallpaper from 0.8: one teal, the ring in the middle. like a computer just after
# you installed it, around 2001. python3 artwork/teal.py
import os, sys, importlib.util
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import cairo
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..')
spec = importlib.util.spec_from_file_location('m', os.path.join(HERE, 'logo', 'make.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

TEAL = (36, 96, 112)

def wallpaper(w, h):
	n = h * 8 // 27   # the ring is 640 tall on a 2160 screen
	svg = m.svg('flat', n, 'w').replace('viewBox="-16 -16 544 560"', 'viewBox="0 0 512 512"')
	s = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
	v = Rsvg.Rectangle(); v.x = v.y = 0; v.width = v.height = n
	Rsvg.Handle.new_from_data(svg.encode()).render_document(cairo.Context(s), v)
	ring = Image.frombuffer('RGBA', (n, n), bytes(s.get_data()), 'raw', 'BGRa', 0, 1)
	im = Image.new('RGB', (w, h), TEAL)
	im.paste(ring, ((w - n) // 2, (h - n) // 2), ring)
	return im

big = wallpaper(3840, 2160)
for p in ('tools/pkg/chamesle-artwork/files/usr/share/backgrounds/chamesle/teal.jpg',
		'tools/pkg/chamesle-kde/files/usr/share/wallpapers/Chamesle/contents/images/3840x2160.jpg'):
	big.save(os.path.join(REPO, p), quality=94)
big.resize((400, 225), Image.LANCZOS).save(
	os.path.join(REPO, 'tools/pkg/chamesle-kde/files/usr/share/wallpapers/Chamesle/contents/screenshot.jpg'), quality=90)
print('wallpaper done')
