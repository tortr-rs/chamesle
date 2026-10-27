#!/usr/bin/env python3
# needs fonts/Nunito.ttf (google fonts, OFL)
# glass logo into every png the repo ships, plus the light banner
import gi, os, importlib.util
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import cairo
from PIL import Image, ImageFont, ImageDraw, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..', '..')
spec = importlib.util.spec_from_file_location('m', os.path.join(HERE, 'make.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# icons: tight box, a shadow only where there is room for one
def svgtext(n):
	s = m.svg('glass', n, 'g')
	if n <= 32:
		s = s.replace(' filter="url(#gdrop)"', '').replace('viewBox="-16 -16 544 560"', 'viewBox="-4 -4 520 520"')
	else:
		s = s.replace('viewBox="-16 -16 544 560"', 'viewBox="-12 -8 536 544"')
	return s

def png(n, out=None):
	h = Rsvg.Handle.new_from_data(svgtext(n).encode())
	s = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
	v = Rsvg.Rectangle(); v.x = v.y = 0; v.width = v.height = n
	h.render_document(cairo.Context(s), v)
	p = os.path.join(HERE, 'out', '%d.png' % n)
	s.write_to_png(p)
	im = Image.open(p).convert('RGBA')
	if out:
		im.save(out)
	return im

def font(sz, w):
	f = ImageFont.truetype(os.path.join(HERE, 'fonts', 'Nunito.ttf'), sz)
	f.set_variation_by_name(w)
	return f

def vgrad(w, h, stops):
	g = Image.new('RGBA', (w, h))
	px = g.load()
	for y in range(h):
		t = y / max(h - 1, 1)
		for i in range(len(stops) - 1):
			if stops[i][0] <= t <= stops[i + 1][0]:
				a, b = stops[i], stops[i + 1]
				k = (t - a[0]) / max(b[0] - a[0], 1e-6)
				c = tuple(int(a[1][j] + (b[1][j] - a[1][j]) * k) for j in range(3))
				break
		for x in range(w):
			px[x, y] = c + (255,)
	return g

# ring, "Chamesle" in shiny dark gel letters, LINUX in blue, and the wet floor
def banner(scale=2):
	ring = png(116 * scale)
	big, sub = font(80 * scale, b'ExtraBold'), font(21 * scale, b'SemiBold')
	word = 'Chamesle'
	bb = big.getbbox(word)
	tw, th = bb[2], bb[3]
	mask = Image.new('L', (tw, th)); ImageDraw.Draw(mask).text((0, 0), word, font=big, fill=255)
	text = vgrad(tw, th, [(0, (74, 88, 104)), (.52, (28, 38, 50)), (.53, (11, 17, 24)), (1, (44, 56, 70))])
	text.putalpha(mask)
	gap = 22 * scale
	W = ring.width + gap + tw + 8 * scale
	ty = int(ring.height * .12)
	H = max(ring.height, ty + th + int(sub.size * 1.5))
	top = Image.new('RGBA', (W, H))
	top.alpha_composite(ring, (0, (H - ring.height) // 2))
	tx = ring.width + gap
	top.alpha_composite(text, (tx, ty))
	d = ImageDraw.Draw(top)
	x = tx + 4 * scale
	for ch in 'LINUX':
		d.text((x, ty + th + 2 * scale), ch, font=sub, fill=(61, 142, 224, 255))
		x += sub.getlength(ch) + 6 * scale
	fl = 40 * scale
	out = Image.new('RGBA', (W, H + fl + 4 * scale))
	out.alpha_composite(top, (0, 0))
	r = top.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, W, fl))
	fade = Image.new('L', (W, fl))
	for y in range(fl):
		ImageDraw.Draw(fade).line([(0, y), (W, y)], fill=int(55 * (1 - y / fl) ** 2))
	r.putalpha(ImageChops.darker(r.getchannel('A'), fade))
	out.alpha_composite(r, (0, H + 4 * scale))
	return out

if __name__ == '__main__':
	os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
	open(os.path.join(REPO, 'artwork', 'logo.svg'), 'w').write(m.svg('glass', 512, 'g'))
	for n in (16, 22, 24, 32, 48, 64, 128, 256):
		for d in ('overlay/usr/share/icons/hicolor/%dx%d/apps/chamesle-start.png',
				'tools/pkg/chamesle-kde/files/usr/share/icons/hicolor/%dx%d/apps/chamesle-start.png',
				'tools/pkg/chamesle-artwork/files/usr/share/icons/Chamesle/%dx%d/places/start-here.png'):
			p = os.path.join(REPO, d % (n, n))
			if os.path.exists(p):
				png(n, p)
	for p in ('artwork/logo.png', 'docs/img/logo.png', 'overlay/usr/share/live-installer/logo.png',
			'overlay/usr/share/live-installer/slideshow/logo.png'):
		png(524, os.path.join(REPO, p))
	png(168, os.path.join(REPO, 'tools/pkg/chamesle-plymouth/files/usr/share/plymouth/themes/chamesle/logo.png'))
	big = Image.new('RGB', (2000, 2000), 'white'); big.paste(i := png(2000), mask=i)
	big.save(os.path.join(REPO, 'artwork/logo.jpeg'), quality=92)
	# greeter: dark screen, so new ring and the old white word
	g = Image.open(os.path.join(HERE, 'greeter-word.png')).convert('RGBA')
	g.paste((0, 0, 0, 0), (0, 0, 73, 80))
	g.alpha_composite(png(72), (0, 4))
	g.save(os.path.join(REPO, 'tools/pkg/chamesle-artwork/files/usr/share/chamesle/greeter-logo.png'))
	b = banner()
	b.save(os.path.join(REPO, 'artwork/banner.png'))
	b.resize((b.width // 2, b.height // 2), Image.LANCZOS).save(os.path.join(REPO, 'docs/img/banner.png'))
	print('logo out', b.size)
