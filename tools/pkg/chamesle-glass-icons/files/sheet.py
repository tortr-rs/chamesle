#!/usr/bin/env python3
# renders every drawing in a theme into one picture, to look at
import os, sys, gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import cairo
from PIL import Image, ImageDraw, ImageFont

root, out = sys.argv[1], sys.argv[2]
size = int(sys.argv[3]) if len(sys.argv) > 3 else 96
items = []
for cat in ['places', 'devices', 'mimetypes', 'apps']:
	d = os.path.join(root, 'scalable', cat)
	for f in sorted(os.listdir(d)):
		p = os.path.join(d, f)
		if not os.path.islink(p):
			items.append((cat, f[:-4], p))
cols = 10
cw, ch = size + 40, size + 34
img = Image.new('RGBA', (cols * cw, ((len(items) + cols - 1) // cols) * ch), (214, 230, 242, 255))
font = ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', 12)
d = ImageDraw.Draw(img)
for i, (cat, name, p) in enumerate(items):
	h = Rsvg.Handle.new_from_file(p)
	s = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
	v = Rsvg.Rectangle(); v.x = v.y = 0; v.width = v.height = size
	h.render_document(cairo.Context(s), v)
	tmp = out + '.tmp.png'
	s.write_to_png(tmp)
	x, y = (i % cols) * cw, (i // cols) * ch
	img.alpha_composite(Image.open(tmp).convert('RGBA'), (x + 20, y + 4))
	t = name if len(name) < 20 else name[:19] + '…'
	d.text((x + cw // 2, y + size + 8), t, font=font, fill=(20, 30, 40), anchor='mt')
os.remove(out + '.tmp.png')
img.save(out)
print(len(items), 'drawn')
