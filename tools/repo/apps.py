#!/usr/bin/env python3
# the store's list of apps in our repo: every package with a .desktop file, its name, summary, categories and icon
# usage: apps.py REPO_DIR      (writes REPO_DIR/apps.json and REPO_DIR/icons/, only looks at packages it hasn't seen)
import configparser, json, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

APK = os.environ.get("APK", "apk")
repo = sys.argv[1]
out_json = os.path.join(repo, "apps.json")
icons = os.path.join(repo, "icons")
cache_file = os.path.join(repo, "..", "apps-cache.json")
os.makedirs(icons, exist_ok=True)
cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}

# which packages have desktop files, from the index (no need to open every package)
dump = subprocess.run([APK, "adbdump", os.path.join(repo, "Packages.adb")], capture_output=True, text=True).stdout
pkgs, cur = {}, None
for line in dump.splitlines():
    m = re.match(r"  - name: (.+)$", line)
    if m:
        cur = {"name": m.group(1)}
        continue
    m = re.match(r"    (version|description): (.+)$", line)
    if m and cur is not None:
        cur[m.group(1)] = m.group(2)
        if "version" in cur and "name" in cur:
            pkgs[cur["name"]] = cur


def has_desktop(path):
    r = subprocess.run([APK, "adbdump", path], capture_output=True, text=True).stdout
    return "usr/share/applications" in r and ".desktop" in r


def real(root, p):
    # a file inside the unpacked package, following symlinks that point inside it too
    for _ in range(10):
        if not os.path.islink(p):
            return p if os.path.isfile(p) else None
        t = os.readlink(p)
        p = root + t if os.path.isabs(t) else os.path.join(os.path.dirname(p), t)
    return None


def icon_file(root, name):
    if not name:
        return None
    if os.path.isabs(name):
        return real(root, root + name)
    best = None
    for size in ("128x128", "256x256", "96x96", "64x64", "48x48", "scalable", "512x512", "32x32"):
        for ext in ("png", "svg"):
            p = real(root, "%s/usr/share/icons/hicolor/%s/apps/%s.%s" % (root, size, name, ext))
            if p:
                return p
    for ext in ("png", "svg", "xpm"):
        p = real(root, "%s/usr/share/pixmaps/%s.%s" % (root, name, ext))
        if p:
            best = p
    return best


def look(name):
    try:
        return look1(name)
    except Exception as e:
        print("%s: %s" % (name, e), file=sys.stderr)
        return "%s-%s.apk" % (name, pkgs[name]["version"]), []


def look1(name):
    p = pkgs[name]
    f = "%s-%s.apk" % (name, p["version"])
    path = os.path.join(repo, f)
    if f in cache:
        return f, cache[f]
    if not os.path.exists(path) or not has_desktop(path):
        return f, []
    tmp = tempfile.mkdtemp()
    try:
        subprocess.run([APK, "extract", "--allow-untrusted", "--no-chown", "--destination", tmp, path],
                       capture_output=True)
        d = os.path.join(tmp, "usr/share/applications")
        apps = []
        for desk in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if not desk.endswith(".desktop"):
                continue
            c = configparser.RawConfigParser(strict=False, interpolation=None)
            try:
                c.read(os.path.join(d, desk), encoding="utf-8")
                e = c["Desktop Entry"]
            except Exception:
                continue
            if e.get("NoDisplay", "").lower() == "true" or e.get("Type", "Application") != "Application":
                continue
            if e.get("Terminal", "").lower() == "true":
                continue
            app = {"id": desk[:-8], "pkg": name, "name": e.get("Name", name),
                   "summary": e.get("Comment") or e.get("GenericName") or p.get("description", ""),
                   "categories": [x for x in e.get("Categories", "").split(";") if x]}
            ic = icon_file(tmp, e.get("Icon", ""))
            if ic:
                dest = app["id"] + os.path.splitext(ic)[1]
                shutil.copy(ic, os.path.join(icons, dest))
                app["icon"] = dest
            apps.append(app)
        return f, apps
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


with ThreadPoolExecutor(os.cpu_count() or 4) as ex:
    results = list(ex.map(look, sorted(pkgs)))
cache = {f: apps for f, apps in results}
json.dump(cache, open(cache_file, "w"))
apps = [a for _, lst in results for a in lst]
json.dump(apps, open(out_json, "w"), separators=(",", ":"))
print("%d apps from %d packages" % (len(apps), len({a["pkg"] for a in apps})))
