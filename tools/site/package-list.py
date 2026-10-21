#!/usr/bin/env python3
# writes docs/packages.json from the repo index, for the search on the packages page
# usage: apk adbdump work/repo/x86_64/Packages.adb | tools/site/package-list.py > docs/packages.json
import json, sys

pkgs, cur, block = [], None, False
for line in sys.stdin:
    if block:
        # the rest of a multi-line description
        if line.startswith('      '):
            cur['d'] = (cur.get('d', '') + ' ' + line.strip()).strip()
            continue
        block = False
    if line.startswith('  - name: '):
        cur = {'n': line[10:].strip()}
        pkgs.append(cur)
    elif cur is not None and line.startswith('    ') and not line.startswith('      '):
        k, _, v = line.strip().partition(': ')
        if k == 'version':
            cur['v'] = v
        elif k == 'description':
            block = v in ('|', '>', '|-', '>-')
            cur['d'] = '' if block else v
        elif k == 'installed-size':
            cur['s'] = int(v)
json.dump(pkgs, sys.stdout, separators=(',', ':'))
