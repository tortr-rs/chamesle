#!/usr/bin/env python3
# makes the white around the logo transparent, then crops it square
# usage: cutout.py in.png out.png  (8-bit rgb/rgba png)
import struct, sys, zlib
from collections import deque


def read_png(path):
    data = open(path, 'rb').read()
    pos, idat = 8, b''
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', body[:10])
        elif kind == b'IDAT':
            idat += body
        pos += 12 + n
    bpp = 4 if ctype == 6 else 3
    raw, stride, prev, px = zlib.decompress(idat), w * bpp, bytearray(w * bpp), []
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        for x in range(w):
            r, g, bl = line[x * bpp:x * bpp + 3]
            px.append([r, g, bl, line[x * bpp + 3] if bpp == 4 else 255])
    return w, h, px


def write_png(path, w, h, px):
    raw = b''.join(b'\0' + bytes(v for p in px[y * w:(y + 1) * w] for v in p) for y in range(h))
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(raw, 9)))
        f.write(chunk(b'IEND', b''))


w, h, px = read_png(sys.argv[1])
white = lambda p: min(p[:3]) >= 232

# flood fill from the edges, the hole and the gaps are connected to it
bg = bytearray(w * h)
q = deque(i for i in range(w * h) if (i < w or i >= w * (h - 1) or i % w in (0, w - 1)) and white(px[i]))
for i in q:
    bg[i] = 1
while q:
    i = q.popleft()
    x = i % w
    for j in (i - 1 if x else -1, i + 1 if x < w - 1 else -1, i - w, i + w):
        if 0 <= j < w * h and not bg[j] and white(px[j]):
            bg[j] = 1
            q.append(j)

for i, p in enumerate(px):
    if bg[i]:
        p[3] = 0
        continue
    # soft edge: take the white back out of the blended pixels
    if min(p[:3]) > 150 and any(0 <= j < w * h and bg[j] for j in (i - 1, i + 1, i - w, i + w)):
        a = max(255 - c for c in p[:3]) / 255
        if a < 0.02:
            p[3] = 0
        else:
            p[:3] = [max(0, min(255, round((c - 255 * (1 - a)) / a))) for c in p[:3]]
            p[3] = round(255 * a)

xs = [i % w for i, p in enumerate(px) if p[3]]
ys = [i // w for i, p in enumerate(px) if p[3]]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
side = int(max(x1 - x0, y1 - y0) * 1.04) + 1
ox, oy = (side - (x1 - x0 + 1)) // 2, (side - (y1 - y0 + 1)) // 2
out = [[0, 0, 0, 0] for _ in range(side * side)]
for y in range(y0, y1 + 1):
    for x in range(x0, x1 + 1):
        out[(y - y0 + oy) * side + (x - x0 + ox)] = px[y * w + x]
write_png(sys.argv[2], side, side, out)
