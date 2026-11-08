#!/usr/bin/env python3
# the little 88x31 buttons at the bottom of the website, drawn a pixel at a time like they were.
# python3 artwork/buttons.py  ->  docs/img/buttons/*.png
import os, subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'docs', 'img', 'buttons')

def font(name, size):
	path = subprocess.run(['fc-match', '-f', '%{file}', name], capture_output=True, text=True).stdout
	return ImageFont.truetype(path, size)

def button(bg, light, dark):
	im = Image.new('RGB', (88, 31), bg)
	d = ImageDraw.Draw(im)
	d.fontmode = '1'   # no smoothing, hard pixels
	d.rectangle((0, 0, 87, 30), outline='#000')
	d.line((1, 1, 86, 1), fill=light); d.line((1, 1, 1, 29), fill=light)
	d.line((1, 29, 86, 29), fill=dark); d.line((86, 1, 86, 29), fill=dark)
	return im, d

# a line of text, centred between x0 and the right edge, a size smaller until it fits
def text(d, xy, s, f, fill, x0=None):
	x, y = xy
	left = x if x0 is None else x0
	room = 84 - left
	size = f.size
	while d.textlength(s, font=f) > room and size > 7:
		size -= 1
		f = f.font_variant(size=size)
	d.text((left + (room - d.textlength(s, font=f)) // 2, y), s, font=f, fill=fill)

os.makedirs(OUT, exist_ok=True)
bold = lambda n: font('Liberation Sans:bold', n)
small = lambda n: font('Liberation Sans', n)

# ours, for anyone who wants to link here
im, d = button('#ffffff', '#ffffff', '#808080')
ring = Image.open(os.path.join(HERE, 'logo.png')).convert('RGBA').resize((25, 25), Image.LANCZOS)
im.paste(ring, (4, 3), ring)
text(d, (31, 4), 'CHAMESLE', bold(10), '#000')
text(d, (31, 16), 'get it here', small(10), '#0000ee')
im.save(os.path.join(OUT, 'chamesle.png'))

# any browser will do
im, d = button('#000080', '#6060ff', '#000030')
text(d, (4, 3), 'best viewed with', small(9), '#ffffff')
text(d, (4, 14), 'ANY BROWSER', bold(11), '#ffff00')
im.save(os.path.join(OUT, 'anybrowser.png'))

# what it's made from
im, d = button('#e8f4ec', '#ffffff', '#5d7d68')
text(d, (4, 3), 'built on', small(10), '#000')
text(d, (4, 14), 'VOID LINUX', bold(11), '#2f6b46')
im.save(os.path.join(OUT, 'void.png'))

# nothing watching you here
im, d = button('#ffffe0', '#ffffff', '#9a9a60')
text(d, (4, 3), 'this site has', small(10), '#000')
text(d, (4, 14), 'NO TRACKERS', bold(11), '#c00000')
im.save(os.path.join(OUT, 'notrackers.png'))
print('buttons in', os.path.normpath(OUT))
