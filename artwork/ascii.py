#!/usr/bin/env python3
# logo.png as a coloured text logo for fastfetch ($1 green, $2 red, $3 blue)
# usage: ascii.py logo.png COLS > logo.txt
import sys
from cutout import read_png

w, h, px = read_png(sys.argv[1])
cols = int(sys.argv[2])
rows = cols // 2
out = []
for r in range(rows):
    line, cur = '', None
    for c in range(cols):
        votes = {}
        for y in range(r * h // rows, (r + 1) * h // rows, 3):
            for x in range(c * w // cols, (c + 1) * w // cols, 3):
                R, G, B, A = px[y * w + x]
                if A < 128:
                    k = None
                elif G > R and G > B:
                    k = '1'
                elif R > G and R > B:
                    k = '2'
                else:
                    k = '3'
                votes[k] = votes.get(k, 0) + 1
        k = max(votes, key=votes.get)
        if k is None or votes[k] < sum(votes.values()) * 0.4:
            line += ' '
            continue
        if k != cur:
            line += '$' + k
            cur = k
        line += '#'
    out.append(line.rstrip())
while out and not out[-1].replace('$1', '').replace('$2', '').replace('$3', '').strip():
    out.pop()
print('\n'.join(out))
