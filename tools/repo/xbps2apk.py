#!/usr/bin/env python3
# turn a void .xbps into an apk v3 package
# usage: xbps2apk.py PKG.xbps OUTDIR   (APK=path/to/apk, SIGN_KEY=key.rsa)
import os, plistlib, re, shutil, subprocess, sys, tempfile

APK = os.environ.get('APK', 'apk')
src, outdir = sys.argv[1], sys.argv[2]


def ver(v):
    # void: 1.2.3_4  ->  apk: 1.2.3-r4
    v, _, rev = v.rpartition('_')
    v = v.lower().replace('+', '').replace('~', '_')
    # 1.4rc5 -> 1.4_rc5, 0.99.beta20 -> 0.99_beta20, 10.6p1 -> 10.6_p1
    v = re.sub(r'\.?(alpha|beta|pre|rc|p)([0-9]+)', r'_\1\2', v)
    if not re.fullmatch(r'[0-9]+(\.[0-9]+)*[a-z]?(_(alpha|beta|pre|rc|cvs|svn|git|hg|p)[0-9]*)*', v):
        v = re.match(r'[0-9]+(\.[0-9]+)*', v).group(0) + '_p0'
    return f'{v}-r{rev}'


def dep(d):
    # glibc>=2.41_1, foo-1.0_1, foo<2, bar>=0
    d = re.sub(r'(.)[<>]=?[^<>=]*$', r'\1', d) if re.search(r'[<>=].*[<>]', d) else d
    m = re.match(r'^([^<>=]+?)([<>]=?|=)(.+)$', d)
    if m:
        name, op, v = m.groups()
        if '_' in v and re.match(r'^[0-9]', v):
            v = ver(v)
        elif op == '>=' and v == '0':
            return name
        return f'{name}{op}{v}'
    m = re.match(r'^(.+)-([^-]+_[0-9]+)$', d)
    if m:
        return f'{m.group(1)}={ver(m.group(2))}'
    return d


def soname(lib):
    m = re.search(r'\.so\.([0-9]+)', lib)
    return f'so:{lib}={m.group(1) if m else 0}'


tmp = tempfile.mkdtemp(prefix='x2a.')
try:
    root = os.path.join(tmp, 'root')
    os.mkdir(root)
    subprocess.run(['tar', '-xpf', src, '-C', root], check=True)
    with open(os.path.join(root, 'props.plist'), 'rb') as f:
        p = plistlib.load(f)
    for meta in ('props.plist', 'files.plist'):
        os.remove(os.path.join(root, meta))

    name = p['pkgname']
    v = ver(p['version'])
    arch = p.get('architecture', 'noarch')
    deps = [dep(d) for d in p.get('run_depends', [])]
    deps += ['so:' + l for l in p.get('shlib-requires', [])]
    provides = [soname(l) for l in p.get('shlib-provides', [])]
    provides += [dep(x).replace('>=', '=') for x in p.get('provides', [])]
    replaces = [re.split(r'[<>=]', x)[0] for x in p.get('replaces', [])]

    info = {
        'name': name, 'version': v, 'arch': arch,
        'description': p.get('short_desc', name),
        'license': p.get('license', 'unknown'),
        'url': p.get('homepage', ''),
        'origin': p.get('sourcepkg', name),
        'maintainer': 'Chamesle Linux <packages@chamesle.org>',
    }
    args = [APK, 'mkpkg', '--files', root, '--output', os.path.join(outdir, f'{name}-{v}.apk')]
    for k, val in info.items():
        if val:
            args += ['--info', f'{k}:{val}']
    for k, lst in (('depends', deps), ('provides', provides), ('replaces', replaces)):
        lst = [x for x in dict.fromkeys(lst) if x and x != name]
        if lst:
            args += ['--info', f'{k}:' + ' '.join(lst)]

    # void's INSTALL/REMOVE take "pre"/"post" as the first argument
    for script, kinds in (('INSTALL', ('pre-install', 'post-install', 'pre-upgrade', 'post-upgrade')),
                          ('REMOVE', ('pre-deinstall', 'post-deinstall'))):
        path = os.path.join(root, script)
        if not os.path.exists(path):
            continue
        body = open(path).read()
        os.remove(path)
        for kind in kinds:
            when = kind.split('-')[0]
            upd = 'yes' if kind.endswith('upgrade') else 'no'
            out = os.path.join(tmp, kind)
            with open(out, 'w') as f:
                f.write(f'#!/bin/sh\nset -- {when} {name} {p["version"]} {upd} no x86_64\n'
                        f'export XBPS_TARGET_ARCH=x86_64\n{body}')
            os.chmod(out, 0o755)
            args += ['--script', f'{kind}:{out}']

    if os.environ.get('SIGN_KEY'):
        args += ['--sign-key', os.environ['SIGN_KEY']]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'{os.path.basename(src)}: {r.stderr.strip() or r.stdout.strip()}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)
