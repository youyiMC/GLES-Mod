#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Definitive scan: walk ~/.gradle/caches and search every .jar for needles.

Prints only 'BASENAME :: ENTRY' lines (capped) so output stays readable.
Self-locating: no command line args needed.
"""
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

NEEDLES = [
    b"only supports",
    b"Currently, %s is",
    b"Currently, ",
]
SKIP_NAMES = ("sources", "javadoc")

home = os.path.expanduser("~")
roots = [
    os.path.join(home, ".gradle", "caches"),
]

jars = []
for r in roots:
    for dirpath, dirnames, filenames in os.walk(r):
        for f in filenames:
            if not f.endswith(".jar"):
                continue
            if any(s in f for s in SKIP_NAMES):
                continue
            jars.append(os.path.join(dirpath, f))

jars = sorted(set(jars))
print("scanning %d jars under %s" % (len(jars), roots[0]))
print()

CAP = 60
hits = 0
for j in jars:
    try:
        z = zipfile.ZipFile(j)
    except Exception:
        continue
    with z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            try:
                data = z.read(name)
            except Exception:
                continue
            for pat in NEEDLES:
                if pat in data:
                    hits += 1
                    line = "HIT  %-52s :: %s   [%s]" % (
                        os.path.basename(j), name, pat.decode())
                    print(line)
                    if pat == b"only supports":
                        m = re.search(re.escape(pat), data)
                        lo = max(0, m.start() - 200)
                        hi = min(len(data), m.end() + 260)
                        txt = data[lo:hi].decode("latin-1")
                        txt = "".join(c if 32 <= ord(c) < 127 else "." for c in txt)
                        print("       ...%s..." % txt)
                    break
    if hits > CAP:
        print("(capped)")
        break

print()
print("total hits:", hits)
