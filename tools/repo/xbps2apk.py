#!/usr/bin/env python3
# turn an .xbps package into an apk v3 package
# usage: xbps2apk.py PKG.xbps OUTDIR   (APK=path/to/apk, SIGN_KEY=key.rsa)
#        xbps2apk.py --todo CACHEDIR OUTDIR   prints the .xbps files that have no .apk yet
import functools, os, plistlib, re, shutil, subprocess, sys, tempfile

APK = os.environ.get('APK', 'apk')

# these alternatives are real symlinks in the package, so /usr/bin/sh is there before any script runs.
# the others get made by post-install, first come first served like xbps does
OWNS = {'sh': 'bash', 'awk': 'gawk'}

# upstream's own branding, docs and repo setup: not ours to ship
SKIP = re.compile(r'^(void-|runit-void|socklog-void|slim-void-theme|lxdm-theme-vdojo|fortune-mod-void|base-voidstrap|tmplgen-)')


def desc(d):
    d = re.sub(r'Void Linux|voidlinux', 'Chamesle Linux', d)
    d = re.sub(r'\bVoid cross toolchain', 'Cross toolchain', d)
    return re.sub(r'\b(for|on) Void\b', r'\1 Chamesle', d)

# names more than one package provides, from --multi (MULTI_PROVIDES=file)
MULTI = set(open(os.environ['MULTI_PROVIDES']).read().split()) if os.environ.get('MULTI_PROVIDES') else set()

OS_RELEASE = '''NAME="Chamesle Linux"
PRETTY_NAME="Chamesle Linux"
ID=chamesle
HOME_URL="https://chamesle.org/"
BUG_REPORT_URL="https://github.com/tortr-rs/chamesle/issues"
LOGO=chamesle-start
'''


def ver(v):
    # xbps: 1.2.3_4  ->  apk: 1.2.3-r4
    v, _, rev = v.rpartition('_')
    # 14.2.1+20250405 -> 14.2.1_p20250405
    v = re.sub(r'\+[a-z]*', '_p', v.lower()).replace('~', '_')
    # 1.4rc5 -> 1.4_rc5, 0.99.beta20 -> 0.99_beta20, 10.6p1 -> 10.6_p1
    v = re.sub(r'\.?(alpha|beta|pre|rc|p)([0-9]+)', r'_\1\2', v)
    if not re.fullmatch(r'[0-9]+(\.[0-9]+)*[a-z]?(_(alpha|beta|pre|rc|cvs|svn|git|hg|p)[0-9]*)*', v):
        m = re.match(r'[0-9]+(\.[0-9]+)*', v)
        v = (m.group(0) if m else '0') + '_p0'
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


def apkname(xbps):
    # foo-1.2_3.x86_64.xbps -> foo-1.2-r3.apk
    b = re.sub(r'\.(x86_64|noarch)\.xbps$', '', os.path.basename(xbps))
    n, _, v = b.rpartition('-')
    return f'{n}-{ver(v)}.apk'


def alternatives(p, root):
    # "sh:/usr/bin/bash" means /usr/bin/sh -> bash. returns shell to add and to remove the links
    links = []
    for group, items in p.get('alternatives', {}).items():
        for it in items:
            link, target = it.split(':', 1)
            if not link.startswith('/'):
                link = os.path.join(os.path.dirname(target), link)
            if not target.startswith('/'):
                target = os.path.join(os.path.dirname(link), target)
            rel = os.path.relpath(target, os.path.dirname(link))
            if OWNS.get(group) == p['pkgname']:
                dst = root + link
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not os.path.lexists(dst):
                    os.symlink(rel, dst)
            else:
                links.append((link, rel))
    add = ''.join(f'[ -e {l} ] || [ -L {l} ] || {{ mkdir -p {os.path.dirname(l)}; ln -s {t} {l}; }}\n'
                  for l, t in links)
    rm = ''.join(f'[ "$(readlink {l})" = {t} ] && rm -f {l}\n' for l, t in links)
    return add, rm


def convert(src, outdir):
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
        if name == 'base-files':
            for f in ('etc/os-release', 'usr/lib/os-release'):
                f = os.path.join(root, f)
                if os.path.lexists(f):
                    os.remove(f)
                    with open(f, 'w') as o:
                        o.write(OS_RELEASE)
            with open(os.path.join(root, 'etc/issue'), 'w') as o:
                o.write('Chamesle Linux \\r (\\l)\n\n')
        arch = p.get('architecture', 'noarch')
        deps = [dep(d) for d in p.get('run_depends', []) if not SKIP.match(d)]
        deps += ['so:' + l for l in p.get('shlib-requires', [])]
        provides = [soname(l) for l in p.get('shlib-provides', [])]
        # things several packages provide (cmd:sh, awk) have to be unversioned for apk, the rest keep theirs
        for x in p.get('provides', []):
            x = dep(x).replace('>=', '=')
            provides.append(x.split('=')[0] if x.split('=')[0] in MULTI else x)
        replaces = [re.split(r'[<>=]', x)[0] for x in p.get('replaces', [])]

        info = {
            'name': name, 'version': v, 'arch': arch,
            'description': desc(p.get('short_desc', name)),
            'license': p.get('license', 'unknown'),
            'url': p.get('homepage', ''),
            'origin': p.get('sourcepkg', name),
            'maintainer': 'Chamesle Linux <packages@chamesle.org>',
        }
        args = [APK, 'mkpkg', '--files', root, '--output', os.path.join(outdir, f'{name}-{v}.apk')]
        for k, val in info.items():
            if val:
                args += ['--info', f'{k}:{val}']
        if any(re.split(r'[<>=]', dep(x))[0] in MULTI for x in p.get('provides', [])):
            args += ['--info', 'provider-priority:10']
        for k, lst in (('depends', deps), ('provides', provides), ('replaces', replaces)):
            lst = [x for x in dict.fromkeys(lst) if x and x != name]
            if lst:
                args += ['--info', f'{k}:' + ' '.join(lst)]

        # xbps INSTALL/REMOVE take "pre"/"post" as the first argument
        add, rm = alternatives(p, root)
        for script, kinds in (('INSTALL', ('pre-install', 'post-install', 'pre-upgrade', 'post-upgrade')),
                              ('REMOVE', ('pre-deinstall', 'post-deinstall'))):
            path = os.path.join(root, script)
            body = ''
            if os.path.exists(path):
                body = open(path).read()
                os.remove(path)
            for kind in kinds:
                extra = {'post-install': add, 'post-upgrade': add, 'pre-deinstall': rm}.get(kind, '')
                if not body and not extra:
                    continue
                when = kind.split('-')[0]
                upd = 'yes' if kind.endswith('upgrade') else 'no'
                out = os.path.join(tmp, kind)
                with open(out, 'w') as f:
                    f.write('#!/bin/sh\n')
                    if body:
                        # subshell: some of these scripts exit early
                        f.write(f'(\nset -- {when} {name} {p["version"]} {upd} no x86_64\n'
                                f'export XBPS_TARGET_ARCH=x86_64\n{body}\n) || exit $?\n')
                    f.write(extra + 'exit 0\n')
                os.chmod(out, 0o755)
                args += ['--script', f'{kind}:{out}']

        if os.environ.get('SIGN_KEY'):
            args += ['--sign-key', os.environ['SIGN_KEY']]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f'{os.path.basename(src)}: {r.stderr.strip() or r.stdout.strip()}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def newest(files):
    # {name: [(version, file), ...]} -> the newest of each, using apk's own ordering
    def cmp(a, b):
        r = subprocess.run([APK, 'version', '-t', a[0], b[0]], capture_output=True, text=True).stdout.strip()
        return {'<': -1, '>': 1}.get(r, 0)
    out = {}
    for name, vs in files.items():
        if len(vs) > 1:
            vs.sort(key=functools.cmp_to_key(cmp))
        out[name] = vs
    return out


def split(f):
    m = re.match(r'^(.+)-([^-]+-r[0-9]+)\.apk$', f)
    return m.groups() if m else (None, None)


def closure(indexes, names):
    # everything the given packages pull in, going by the upstream index
    pkgs, shlibs, virtual = {}, {}, {}
    for i in indexes:
        with open(i, 'rb') as f:
            pkgs.update(plistlib.load(f))
    for n, p in pkgs.items():
        for l in p.get('shlib-provides', []):
            shlibs.setdefault(l, n)
        for v in p.get('provides', []):
            virtual.setdefault(re.split(r'[<>=]|-[0-9]', v)[0], n)
    seen, todo = set(), list(names)
    while todo:
        n = todo.pop()
        n = n if n in pkgs else virtual.get(n)
        if not n or n in seen or SKIP.match(n):
            continue
        seen.add(n)
        p = pkgs[n]
        for d in p.get('run_depends', []):
            d = re.split(r'[<>=]', d)[0]
            m = re.match(r'^(.+)-[^-]+_[0-9]+$', d)
            todo.append(m.group(1) if m else d)
        todo += [shlibs[l] for l in p.get('shlib-requires', []) if l in shlibs]
    return seen


if __name__ == '__main__':
    if sys.argv[1] == '--multi':
        seen = {}
        for i in sys.argv[2:]:
            with open(i, 'rb') as f:
                for n, p in plistlib.load(f).items():
                    for x in p.get('provides', []):
                        seen.setdefault(re.split(r'[<>=]', dep(x))[0], set()).add(n)
        print('\n'.join(sorted(k for k, v in seen.items() if len(v) > 1)))
    elif sys.argv[1] == '--closure':
        print('\n'.join(sorted(closure(sys.argv[2:], sys.stdin.read().split()))))
    elif sys.argv[1] == '--todo':
        # newest .xbps of each package that has no .apk yet, the ones in FIRST (a list of names) first
        have = set(os.listdir(sys.argv[3]))
        first = set(open(sys.argv[4]).read().split()) if len(sys.argv) > 4 else set()
        byname = {}
        for f in os.listdir(sys.argv[2]):
            if f.endswith('.xbps') and not SKIP.match(f):
                n, v = split(apkname(f))
                byname.setdefault(n, []).append((v, f))
        for name, vs in sorted(newest(byname).items(), key=lambda kv: (kv[0] not in first, kv[0])):
            f = vs[-1][1]
            if apkname(f) not in have:
                print(os.path.join(sys.argv[2], f))
    elif sys.argv[1] in ('--prune', '--prune-list'):
        byname = {}
        for f in os.listdir(sys.argv[2]):
            n, v = split(f)
            if n:
                byname.setdefault(n, []).append((v, f))
        for name, vs in newest(byname).items():
            for _, old in vs[:-1]:
                if sys.argv[1] == '--prune-list':
                    print(old)
                else:
                    os.remove(os.path.join(sys.argv[2], old))
    else:
        convert(sys.argv[1], sys.argv[2])
