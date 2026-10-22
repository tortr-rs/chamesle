#!/usr/bin/env python3
# drive a headless test vm through its qemu monitor socket
#   mon.py SOCK "shot FILE.png" | "key KEYS" | "type TEXT" | any monitor command
import socket, sys, time
sock, cmd = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_UNIX); s.connect(sock); s.settimeout(2)
def send(c):
    s.sendall((c + "\n").encode()); time.sleep(0.15)
    try: s.recv(65536)
    except socket.timeout: pass
send("")
w, *a = cmd.split(" ", 1)
if w == "shot":
    send("screendump %s -f png" % a[0]); time.sleep(0.8)
elif w == "key":
    send("sendkey " + a[0])
elif w == "type":
    m = {" ": "spc", "-": "minus", ".": "dot", "/": "slash", ",": "comma", ";": "semicolon", "=": "equal",
         "'": "apostrophe", "\\": "backslash", "[": "bracket_left", "]": "bracket_right", "`": "grave_accent",
         "~": "shift-grave_accent", "!": "shift-1", "@": "shift-2", "#": "shift-3", "$": "shift-4", "%": "shift-5",
         "^": "shift-6", "&": "shift-7", "*": "shift-8", "(": "shift-9", ")": "shift-0", "_": "shift-minus",
         "+": "shift-equal", "|": "shift-backslash", ":": "shift-semicolon", '"': "shift-apostrophe",
         "<": "shift-comma", ">": "shift-dot", "?": "shift-slash", "{": "shift-bracket_left", "}": "shift-bracket_right"}
    for ch in a[0]:
        send("sendkey " + (("shift-" + ch.lower()) if ch.isupper() else m.get(ch, ch)))
else:
    send(cmd)
