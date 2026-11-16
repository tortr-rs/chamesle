#!/usr/bin/env python3
# a png as a coloured text logo for fastfetch ($1 green, $2 red, $3 blue, $9 the terminal's own colour)
# usage: ascii.py logo.png COLS > logo.txt    the mark on its own, drawn with #
#        ascii.py banner.png COLS ROWS > logo.txt    the banner, half blocks, ROWS text rows tall
import sys
from cutout import read_png

w, h, px = read_png(sys.argv[1])
cols = int(sys.argv[2])
half = len(sys.argv) > 3
rows = int(sys.argv[3]) if half else cols // 2
sub = 2 if half else 1


def kind(x0, x1, y0, y1):
    votes = {}
    for y in range(y0, max(y1, y0 + 1), 2):
        for x in range(x0, max(x1, x0 + 1), 2):
            R, G, B, A = px[y * w + x]
            if A < 128:
                k = None
            elif max(R, G, B) < 110:
                k = '9'
            elif G > R and G > B:
                k = '1'
            elif R > G and R > B:
                k = '2'
            else:
                k = '3'
            votes[k] = votes.get(k, 0) + 1
    k = max(votes, key=votes.get)
    return None if k is None or votes[k] < sum(votes.values()) * 0.4 else k


out = []
for r in range(rows):
    line, cur = '', None
    for c in range(cols):
        x0, x1 = c * w // cols, (c + 1) * w // cols
        parts = [kind(x0, x1, (r * sub + s) * h // (rows * sub), (r * sub + s + 1) * h // (rows * sub)) for s in range(sub)]
        if half:
            top, bot = parts
            if top and bot:
                ch, k = '█', top
            elif top:
                ch, k = '▀', top
            elif bot:
                ch, k = '▄', bot
            else:
                line += ' '
                continue
        elif parts[0]:
            ch, k = '#', parts[0]
        else:
            line += ' '
            continue
        if k != cur:
            line += '$' + k
            cur = k
        line += ch
    out.append(line.rstrip())
while out and not out[-1].replace('$1', '').replace('$2', '').replace('$3', '').replace('$9', '').strip():
    out.pop()
print('\n'.join(out))
