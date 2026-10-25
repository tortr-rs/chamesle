#!/usr/bin/env python3
# makes the chamesle boot menu theme in files/usr/share/grub/themes/chamesle: the pictures, and the fonts as grub's
# pf2 (void's grub comes without grub-mkfont, so they're drawn here with pillow)
#   make-theme.py INTER_DIR      the folder with Inter-Regular.ttf and Inter-Bold.ttf
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'files/usr/share/grub/themes/chamesle')
ART = os.path.join(HERE, '../chamesle-artwork/files/usr/share/backgrounds/chamesle/grub.png')
# ascii, latin-1 for names in other languages, and the arrows and dot of the hints. grub wants them in order
CHARS = sorted([c for c in range(0x20, 0x7f)] + [c for c in range(0xa0, 0x100)] + [0x2191, 0x2193, 0x2022, 0x2026, 0x2013, 0x2014])


def pf2(ttf, size, family, weight, path):
    font = ImageFont.truetype(ttf, size)
    ascent, descent = font.getmetrics()
    glyphs = []
    for cp in CHARS:
        ch = chr(cp)
        if font.getmask(ch).getbbox() is None and cp != 0x20 and cp != 0xa0:
            continue
        adv = round(font.getlength(ch))
        l, t, r, b = font.getbbox(ch, anchor='ls')
        w, h = max(r - l, 0), max(b - t, 0)
        bits = b''
        if w and h:
            img = Image.new('L', (w, h), 0)
            d = ImageDraw.Draw(img)
            d.fontmode = '1'
            d.text((-l, -t), ch, font=font, fill=255, anchor='ls')
            px = img.load()
            # the rows one after another, no padding between them, most significant bit first
            acc, n, out = 0, 0, bytearray()
            for y in range(h):
                for x in range(w):
                    acc = acc << 1 | (px[x, y] > 127)
                    n += 1
                    if n == 8:
                        out.append(acc); acc, n = 0, 0
            if n:
                out.append(acc << (8 - n))
            bits = bytes(out)
        # yoffset: from the baseline up to the bitmap's bottom row
        glyphs.append((cp, struct.pack('>HHhhh', w, h, l, -b, adv) + bits))
    name = '%s %s %d' % (family, weight.capitalize(), size)

    def sec(tag, data):
        return tag + struct.pack('>I', len(data)) + data

    head = (sec(b'FILE', b'PFF2') + sec(b'NAME', name.encode() + b'\0') + sec(b'FAMI', family.encode() + b'\0') +
            sec(b'WEIG', weight.encode() + b'\0') + sec(b'SLAN', b'normal\0') + sec(b'PTSZ', struct.pack('>H', size)) +
            sec(b'MAXW', struct.pack('>H', max(struct.unpack('>H', g[1][:2])[0] for g in glyphs))) +
            sec(b'MAXH', struct.pack('>H', max(struct.unpack('>H', g[1][2:4])[0] for g in glyphs))) +
            sec(b'ASCE', struct.pack('>H', ascent)) + sec(b'DESC', struct.pack('>H', descent)))
    # the index points at each glyph by its place in the file
    pos = len(head) + 8 + 9 * len(glyphs) + 8
    index, data = b'', b''
    for cp, g in glyphs:
        index += struct.pack('>IBI', cp, 0, pos + len(data))
        data += g
    with open(path, 'wb') as f:
        f.write(head + b'CHIX' + struct.pack('>I', len(index)) + index + b'DATA' + b'\xff\xff\xff\xff' + data)
    return name


def box(prefix, fill, radius, border=None):
    # a rounded box in grub's nine pieces: corners, edges and the middle, which grub stretches
    s = radius * 2 + 1
    big = Image.new('RGBA', (s * 4, s * 4), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, s * 4 - 1, s * 4 - 1), radius * 4, fill=fill,
                                          outline=border, width=4 if border else 0)
    img = big.resize((s, s), Image.LANCZOS)
    r = radius
    parts = {'nw': (0, 0, r, r), 'n': (r, 0, r + 1, r), 'ne': (r + 1, 0, s, r),
             'w': (0, r, r, r + 1), 'c': (r, r, r + 1, r + 1), 'e': (r + 1, r, s, r + 1),
             'sw': (0, r + 1, r, s), 's': (r, r + 1, r + 1, s), 'se': (r + 1, r + 1, s, s)}
    for k, b in parts.items():
        img.crop(b).save(os.path.join(OUT, '%s_%s.png' % (prefix, k)))


def main():
    inter = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    # what this makes, theme.txt is written by hand
    for f in os.listdir(OUT):
        if f.endswith(('.png', '.pf2')):
            os.remove(os.path.join(OUT, f))
    names = [pf2(os.path.join(inter, 'Inter-Regular.ttf'), 16, 'Inter', 'regular', os.path.join(OUT, 'inter-16.pf2')),
             pf2(os.path.join(inter, 'Inter-Regular.ttf'), 20, 'Inter', 'regular', os.path.join(OUT, 'inter-20.pf2')),
             pf2(os.path.join(inter, 'Inter-Bold.ttf'), 32, 'Inter', 'bold', os.path.join(OUT, 'inter-bold-32.pf2'))]
    # the wallpaper a little darker and softer, so the menu reads well on it. small: grub decodes it slowly, blurred
    # it loses nothing when stretched
    bg = Image.open(ART).convert('RGB').resize((1280, 720), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2))
    ImageEnhance.Brightness(bg).enhance(0.8).save(os.path.join(OUT, 'background.png'), optimize=True)
    box('menu', (12, 20, 40, 170), 14, border=(255, 255, 255, 40))
    box('select', (255, 255, 255, 235), 10)
    # the same size, invisible: grub moves an item by its box's border, this way every item moves the same
    box('item', (0, 0, 0, 0), 10)
    print('\n'.join(names))


main()
