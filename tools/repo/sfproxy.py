#!/usr/bin/env python3
# a local cache in front of the public repo on sourceforge, for builds.
#
#   tools/repo/sfproxy.py [PORT]      (8091 if you don't say)
#   PULL=http://127.0.0.1:8091 tools/pkg/build.sh tyrmel
#   sudo REPO=http://127.0.0.1:8091 EDITION=xfce ./build.sh
#
# sourceforge sends every file to a random mirror now, with a token in the link, so there's
# no fast mirror to pin, and some of them crawl or stall and apk waits on them forever.
# this fetches each file once with curl, gives up on a mirror that's slower than 50 KB/s for
# 15 seconds and asks again (which gets a different one), and keeps what it got in
# ~/.cache/chamesle-sf. apk checks every package's signature itself, so the cache can't
# hand it anything it wouldn't take from sourceforge.
import os, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

UPSTREAM = os.environ.get('UPSTREAM', 'https://downloads.sourceforge.net/project/chameslerepos')
CACHE = os.environ.get('SF_CACHE', os.path.expanduser('~/.cache/chamesle-sf'))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8091
INDEX_AGE = 600     # the index changes, packages don't: refetch it after ten minutes
locks = {}
locks_lock = threading.Lock()


def lock_for(path):
    with locks_lock:
        return locks.setdefault(path, threading.Lock())


def fetch(rel, dest):
    tmp = dest + '.part'
    for attempt in range(8):
        r = subprocess.run(['curl', '-fsSL', '--connect-timeout', '15', '--speed-limit', '51200',
                            '--speed-time', '15', '-o', tmp, UPSTREAM + '/' + rel])
        if r.returncode == 0:
            os.replace(tmp, dest)
            return True
        # 22 is a 404 or similar: asking again won't help
        if r.returncode == 22:
            break
        print('sfproxy: %s: try %d failed (curl %d), again' % (rel, attempt + 1, r.returncode), flush=True)
        time.sleep(min(2 * (attempt + 1), 10))
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.serve(True)

    def do_HEAD(self):
        self.serve(False)

    def serve(self, body):
        rel = self.path.split('?', 1)[0].lstrip('/')
        if not rel or '..' in rel.split('/'):
            self.send_error(404)
            return
        dest = os.path.join(CACHE, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with lock_for(dest):
            fresh = os.path.exists(dest) and (not rel.endswith('.adb') or time.time() - os.path.getmtime(dest) < INDEX_AGE)
            if not fresh and not fetch(rel, dest) and not os.path.exists(dest):
                self.send_error(404)
                return
        size = os.path.getsize(dest)
        self.send_response(200)
        self.send_header('Content-Length', str(size))
        self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        if body:
            with open(dest, 'rb') as f:
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    os.makedirs(CACHE, exist_ok=True)
    print('sfproxy: http://127.0.0.1:%d -> %s, cache in %s' % (PORT, UPSTREAM, CACHE), flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
