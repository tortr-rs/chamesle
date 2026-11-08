#!/usr/bin/env python3
# the flat logo into every png the repo ships, plus the banner. STYLE=glass for the 0.7 one
import gi, os, importlib.util, subprocess
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import cairo
from PIL import Image, ImageFont, ImageDraw, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..', '..')
spec = importlib.util.spec_from_file_location('m', os.path.join(HERE, 'make.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
STYLE = os.environ.get('STYLE', 'flat')

# icons: tight box, a shadow only where there is room for one
def svgtext(n):
	s = m.svg(STYLE, n, 'g')
	if STYLE == 'flat':
		# no shadow to make room for: the same margin all round, like the first logo.png
		return s.replace('viewBox="-16 -16 544 560"', 'viewBox="-6 -6 524 524"')
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

def font(name, sz):
	path = subprocess.run(['fc-match', '-f', '%{file}', name], capture_output=True, text=True).stdout
	return ImageFont.truetype(path, sz)

# ring, then "Chamesle" in bold serif and LINUX spaced out under it, black on nothing
def banner(scale=2):
	ring = png(116 * scale)
	big, sub = font('Liberation Serif:bold', 76 * scale), font('Liberation Sans:bold', 20 * scale)
	word = 'Chamesle'
	bb = big.getbbox(word)
	tw, th = bb[2], bb[3]
	gap = 22 * scale
	W = ring.width + gap + tw + 8 * scale
	ty = int(ring.height * .1)
	H = max(ring.height, ty + th + int(sub.size * 1.6))
	out = Image.new('RGBA', (W, H))
	out.alpha_composite(ring, (0, (H - ring.height) // 2))
	tx = ring.width + gap
	d = ImageDraw.Draw(out)
	d.text((tx, ty), word, font=big, fill=(0, 0, 0, 255))
	x = tx + 4 * scale
	for ch in 'LINUX':
		d.text((x, ty + th + 4 * scale), ch, font=sub, fill=(0, 0, 0, 255))
		x += sub.getlength(ch) + 9 * scale
	return out

if __name__ == '__main__':
	os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
	open(os.path.join(REPO, 'artwork', 'logo.svg'), 'w').write(m.svg(STYLE, 512, 'g'))
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
	print('logo out', b.size)
