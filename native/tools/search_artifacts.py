#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search a set of jars (default: build\\moddev\\artifacts + our own jars)
for a literal byte string, printing class/file where found.
Self-locating: no paths needed on the command line beyond the needle.
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

needle = sys.argv[1] if len(sys.argv) > 1 else "only supports"
extra = sys.argv[2:] if len(sys.argv) > 2 else []

roots = [
    "build/moddev/artifacts",
    "build/libs",
    "build/plugin",
] + extra

jars = []
for r in roots:
    if os.path.isfile(r):
        jars.append(r)
        continue
    for pat in ("**/*.jar", "**/*.zip"):
        jars.extend(glob.glob(os.path.join(r, pat), recursive=True))

nb = needle.encode("utf-8")
print("needle: %r   jars: %d" % (needle, len(jars)))
print()

hits = 0
for j in sorted(set(jars)):
    try:
        with zipfile.ZipFile(j) as z:
            for n in z.namelist():
                if n.endswith("/"):
                    continue
                try:
                    data = z.read(n)
                except Exception:
                    continue
                if nb not in data:
                    continue
                hits += 1
                print("HIT %s :: %s" % (os.path.basename(j), n))
                # show printable context around every occurrence
                for m in re.finditer(re.escape(nb), data):
                    lo = max(0, m.start() - 120)
                    hi = min(len(data), m.end() + 200)
                    chunk = data[lo:hi]
                    txt = chunk.decode("latin-1")
                    txt = "".join(c if 32 <= ord(c) < 127 else "." for c in txt)
                    print("      ...%s..." % txt)
                if hits > 30:
                    print("(stopping early)")
                    break
    except Exception as e:
        pass

print()
print("total hits:", hits)
