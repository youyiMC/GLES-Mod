#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Definitive search for the FML/NeoForge dependency-rejection message.

Hardcoded needles + hardcoded roots (the VS Code task-runner shell strips
quotes, so passing needles on the command line is unreliable).

Scans EVERY entry in each jar (not just .class) because FML messages may
live in a lang JSON.
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

NEEDLES = [
    "only supports",
    "Currently, ",
    "does not support",
    "unsupported version",
    "Sodium is",
]

def roots():
    home = os.path.expanduser("~")
    out = [
        "build/moddev/artifacts",
        r"%s\.gradle\caches\modules-2\files-2.1\net.neoforged" % home,
        r"%s\.gradle\caches\modules-2\files-2.1\net.minecraftforge" % home,
        r"%s\.gradle\caches\neoformruntime" % home,
    ]
    return out


jars = []
for r in roots():
    for pat in ("**/*.jar", "**/*.zip"):
        jars.extend(glob.glob(os.path.join(r, pat), recursive=True))
jars = sorted(set(jars))
print("candidate jars:", len(jars))

nb = [(n, n.encode("utf-8")) for n in NEEDLES]

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
            for orig, pat in nb:
                if pat in data:
                    hits += 1
                    print("HIT  %-55s :: %s" % (os.path.basename(j), name))
                    for m in re.finditer(re.escape(pat), data):
                        lo = max(0, m.start() - 160)
                        hi = min(len(data), m.end() + 220)
                        txt = data[lo:hi].decode("latin-1")
                        txt = "".join(c if 32 <= ord(c) < 127 else "." for c in txt)
                        print("       [%s] ...%s..." % (orig, txt))
                    break
    if hits > 40:
        print("(stopping early)")
        break

print()
print("total hits:", hits)
