#!/usr/bin/env python3
# the chamesle ring, three 2007 finishes. same geometry as artwork/logo.png:
# three 108 degree pieces, 12 degree gaps at the bottom and upper corners, hole half the ring
import math, os, sys

C, R, r = 256, 244, 124
SEGS = [  # start, end (degrees, y down), light, base, dark
	('green', 216, 324, '#6ff0a8', '#00a856', '#005a2e'),
	('blue', -24, 84, '#8f80ff', '#2a12c8', '#0c0057'),
	('red', 96, 204, '#ffb0a0', '#ff3b33', '#a50d0d'),
]

def pt(a, rad):
	return C + rad * math.cos(math.radians(a)), C + rad * math.sin(math.radians(a))

def seg(a0, a1, ro=R, ri=r):
	o0, o1, i1, i0 = pt(a0, ro), pt(a1, ro), pt(a1, ri), pt(a0, ri)
	return 'M%.2f %.2fA%d %d 0 0 1 %.2f %.2fL%.2f %.2fA%d %d 0 0 0 %.2f %.2fZ' % (
		o0[0], o0[1], ro, ro, o1[0], o1[1], i1[0], i1[1], ri, ri, i0[0], i0[1])

RING = ' '.join(seg(a, b) for _, a, b, *_ in SEGS)
# the shine: everything above a soft curve through the middle
SHINE = 'M0 0H512V214Q256 150 0 214Z'

def gel(p):
	d, o = [], []
	d.append('<clipPath id="%sring"><path d="%s"/></clipPath>' % (p, RING))
	d.append('<linearGradient id="%sshine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".5"/><stop offset=".7" stop-color="#fff" stop-opacity=".1"/><stop offset="1" stop-color="#fff" stop-opacity=".04"/></linearGradient>' % p)
	d.append('<filter id="%sdrop" x="-20%%" y="-20%%" width="140%%" height="150%%"><feGaussianBlur in="SourceAlpha" stdDeviation="9"/><feOffset dy="10"/><feComponentTransfer><feFuncA type="linear" slope=".45"/></feComponentTransfer><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>' % p)
	o.append('<g filter="url(#%sdrop)">' % p)
	for n, a, b, lt, bs, dk in SEGS:
		# a tube: light along the middle of the ring, dark at its edges
		d.append('<radialGradient id="%s%s" cx="%d" cy="%d" r="%d" gradientUnits="userSpaceOnUse">'
			'<stop offset="%.3f" stop-color="%s"/><stop offset="%.3f" stop-color="%s"/><stop offset="%.3f" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>'
			% (p, n, C, C, R, r / R, dk, (r / R + 1) / 2 - .06, bs, (r / R + 1) / 2 + .08, bs, dk))
		d.append('<radialGradient id="%s%sglow" cx=".5" cy="1" r=".7"><stop offset="0" stop-color="%s" stop-opacity=".9"/><stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>' % (p, n, lt, lt))
		path = seg(a, b)
		o.append('<path d="%s" fill="url(#%s%s)"/>' % (path, p, n))
		o.append('<path d="%s" fill="url(#%s%sglow)" opacity=".55"/>' % (path, p, n))
		o.append('<path d="%s" fill="none" stroke="%s" stroke-width="3" stroke-linejoin="round"/>' % (path, dk))
		o.append('<path d="%s" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="1.5" stroke-linejoin="round" transform="translate(0 1.5)"/>' % (path))
		# a lip of light just inside the outer edge, brightest on top
		lip = seg(a + 3, b - 3, R - 7, R - 16)
		d.append('<linearGradient id="%s%slip" x1="0" y1="0" x2="0" y2="512" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fff" stop-opacity=".75"/><stop offset=".6" stop-color="#fff" stop-opacity=".1"/><stop offset="1" stop-color="#fff" stop-opacity=".3"/></linearGradient>' % (p, n))
		o.append('<path d="%s" fill="url(#%s%slip)"/>' % (lip, p, n))
	o.append('<path d="%s" fill="url(#%sshine)" clip-path="url(#%sring)"/>' % (SHINE, p, p))
	o.append('</g>')
	return ''.join(d), ''.join(o)

def glass(p):
	d, o = [], []
	d.append('<clipPath id="%sring"><path d="%s"/></clipPath>' % (p, RING))
	d.append('<linearGradient id="%sshine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity=".06"/></linearGradient>' % p)
	d.append('<filter id="%sdrop" x="-20%%" y="-20%%" width="140%%" height="150%%"><feGaussianBlur in="SourceAlpha" stdDeviation="10"/><feOffset dy="12"/><feComponentTransfer><feFuncA type="linear" slope=".3"/></feComponentTransfer><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>' % p)
	o.append('<g filter="url(#%sdrop)">' % p)
	for n, a, b, lt, bs, dk in SEGS:
		d.append('<linearGradient id="%s%s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s" stop-opacity=".86"/><stop offset="1" stop-color="%s" stop-opacity=".97"/></linearGradient>' % (p, n, bs, dk))
		path = seg(a, b)
		o.append('<path d="%s" fill="url(#%s%s)"/>' % (path, p, n))
		# light caught on the inner and outer edges of the glass
		o.append('<path d="%s" fill="none" stroke="%s" stroke-width="10" stroke-opacity=".7" clip-path="url(#%sring)"/>' % (path, lt, p))
		o.append('<path d="%s" fill="none" stroke="#fff" stroke-width="2" stroke-opacity=".9"/>' % path)
		o.append('<path d="%s" fill="none" stroke="%s" stroke-width="1" stroke-opacity=".8" transform="translate(0 1)"/>' % (path, dk))
	o.append('<path d="%s" fill="url(#%sshine)" clip-path="url(#%sring)"/>' % (SHINE, p, p))
	o.append('</g>')
	return ''.join(d), ''.join(o)

def chrome(p):
	d, o = [], []
	d.append('<clipPath id="%sring"><path d="%s"/></clipPath>' % (p, ' '.join(seg(a, b, R - 12, r + 12) for _, a, b, *_ in SEGS)))
	d.append('<linearGradient id="%smetal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#c9d1d9"/><stop offset=".55" stop-color="#8e99a5"/><stop offset="1" stop-color="#e6ebf0"/></linearGradient>' % p)
	d.append('<linearGradient id="%sshine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".6"/><stop offset="1" stop-color="#fff" stop-opacity=".05"/></linearGradient>' % p)
	d.append('<filter id="%sdrop" x="-20%%" y="-20%%" width="140%%" height="150%%"><feGaussianBlur in="SourceAlpha" stdDeviation="9"/><feOffset dy="10"/><feComponentTransfer><feFuncA type="linear" slope=".45"/></feComponentTransfer><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>' % p)
	o.append('<g filter="url(#%sdrop)">' % p)
	for n, a, b, lt, bs, dk in SEGS:
		o.append('<path d="%s" fill="url(#%smetal)" stroke="#5d6873" stroke-width="2.5" stroke-linejoin="round"/>' % (seg(a, b), p))
		d.append('<radialGradient id="%s%s" cx="%d" cy="%d" r="%d" gradientUnits="userSpaceOnUse">'
			'<stop offset="%.3f" stop-color="%s"/><stop offset=".72" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>'
			% (p, n, C, C, R - 12, (r + 12) / (R - 12), dk, bs, dk))
		inner = seg(a + 2.2, b - 2.2, R - 12, r + 12)
		o.append('<path d="%s" fill="url(#%s%s)" stroke="%s" stroke-width="2" stroke-linejoin="round"/>' % (inner, p, n, dk))
	o.append('<path d="%s" fill="url(#%sshine)" clip-path="url(#%sring)"/>' % (SHINE, p, p))
	o.append('</g>')
	return ''.join(d), ''.join(o)

def svg(kind, size, p, extra=''):
	defs, body = {'gel': gel, 'glass': glass, 'chrome': chrome}[kind](p)
	return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="-16 -16 544 560" role="img" aria-label="Chamesle logo">'
		'<defs>%s</defs>%s%s</svg>' % (size, size, defs, body, extra))

if __name__ == '__main__':
	out = sys.argv[1] if len(sys.argv) > 1 else '.'
	for k in ('gel', 'glass', 'chrome'):
		open(os.path.join(out, 'logo-%s.svg' % k), 'w').write(svg(k, 512, k[0]))
