#!/usr/bin/env python3
# writes wallpaper.svg: a silk wave made of many thin lines, a glow, a vignette and grain
# usage: wallpaper.py > wallpaper.svg
import math

W, H = 3840, 2160
LINES = 90


def wave(t, x, k=0):
    # height of line t (0..1) at x (0..1), k picks the ribbon
    a = 0.52 + 0.10 * math.sin(2.2 * x + 0.6 + 1.3 * k) - 0.16 * x + 0.11 * k
    b = 0.06 * math.sin(5.5 * x + 3.0 * t + 1.2) * (0.4 + t)
    # the ribbon twists: lines fan out, cross over and come back together
    spread = (t - 0.5) * (0.34 - 0.12 * k) * math.sin(3.4 * x + 0.5 - 1.1 * k) + 0.015 * math.sin(9 * x + 6 * t)
    return (a + b + spread) * H


def path(t, k=0):
    pts = [(i / 60 * (W + 400) - 200, wave(t, i / 60, k)) for i in range(61)]
    d = "M%.1f %.1f" % pts[0]
    # catmull-rom through the points, as cubic beziers
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += " C%.1f %.1f %.1f %.1f %.1f %.1f" % (c1 + c2 + p2)
    return d


out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H), '''<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#06122a"/>
    <stop offset="0.5" stop-color="#0b2552"/>
    <stop offset="1" stop-color="#073a4f"/>
  </linearGradient>
  <linearGradient id="silk" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#3b82f6" stop-opacity="0"/>
    <stop offset="0.25" stop-color="#60a5fa" stop-opacity="0.9"/>
    <stop offset="0.6" stop-color="#38bdf8"/>
    <stop offset="1" stop-color="#2dd4bf" stop-opacity="0.9"/>
  </linearGradient>
  <radialGradient id="glow" cx="0.62" cy="0.48" r="0.5">
    <stop offset="0" stop-color="#2563eb" stop-opacity="0.45"/>
    <stop offset="1" stop-color="#2563eb" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="vignette" cx="0.5" cy="0.5" r="0.75">
    <stop offset="0.6" stop-color="#000" stop-opacity="0"/>
    <stop offset="1" stop-color="#000" stop-opacity="0.45"/>
  </radialGradient>
  <filter id="blur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="40"/></filter>
  <filter id="grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>
    <feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0.06 0"/>
  </filter>
</defs>''', '<rect width="%d" height="%d" fill="url(#sky)"/>' % (W, H),
       '<rect width="%d" height="%d" fill="url(#glow)"/>' % (W, H)]

# a soft blurred copy of the wave underneath, then the lines on top
out.append('<g filter="url(#blur)" opacity="0.25">')
for i in range(0, LINES, 6):
    out.append('<path d="%s" fill="none" stroke="url(#silk)" stroke-width="40"/>' % path(i / (LINES - 1)))
out.append('</g><g fill="none" stroke="url(#silk)">')
for i in range(LINES):
    t = i / (LINES - 1)
    # brighter in the middle of the ribbon
    op = 0.10 + 0.55 * math.exp(-((t - 0.5) / 0.22) ** 2)
    out.append('<path d="%s" stroke-width="%.1f" stroke-opacity="%.3f"/>' % (path(t), 1.6 + 1.4 * (1 - abs(t - 0.5) * 2), op))
out.append('</g>')
# a second, fainter ribbon behind and below
out.append('<g fill="none" stroke="url(#silk)" opacity="0.45">')
for i in range(0, LINES, 2):
    t = i / (LINES - 1)
    out.append('<path d="%s" stroke-width="1.4" stroke-opacity="%.3f"/>' % (path(t, 1), 0.08 + 0.35 * math.exp(-((t - 0.5) / 0.25) ** 2)))
out.append('</g>')
out.append('<rect width="%d" height="%d" fill="url(#vignette)"/>' % (W, H))
out.append('<rect width="%d" height="%d" filter="url(#grain)"/>' % (W, H))
out.append('</svg>')
print('\n'.join(out))
