#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find which class in the NeoForge jar(s) references a given lang key.

Hardcoded needles (task-runner shell strips quotes).
Prints: BASENAME :: ENTRY  plus a printable context window.
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

NEEDLES = [
    "fml.modloading.missingdependency.optional",
    "fml.modloading.missingdependency",
]

home = os.path.expanduser("~")
pats = [
    r"%s\.gradle\caches\modules-2\files-2.1\net.neoforged\**\*.jar" % home,
    "build/moddev/artifacts/neoforge*.jar",
]
jars = []
for p in pats:
    jars.extend(glob.glob(p, recursive=True))
jars = sorted(set(j for j in jars if "sources" not in j and "javadoc" not in j))
print("scanning %d jars" % len(jars))

hits = 0
for j in jars:
    try:
        z = zipfile.ZipFile(j)
    except Exception:
        continue
    with z:
        for name in z.namelist():
            if name.endswith("/") or not name.endswith(".class"):
                continue
            try:
                data = z.read(name)
            except Exception:
                continue
            for pat in NEEDLES:
                pb = pat.encode()
                if pb in data:
                    hits += 1
                    print("=" * 72)
                    print("HIT %s :: %s   [%s]" % (os.path.basename(j), name, pat))
                    m = re.search(re.escape(pb), data)
                    lo = max(0, m.start() - 260)
                    hi = min(len(data), m.end() + 320)
                    txt = data[lo:hi].decode("latin-1")
                    txt = "".join(c if 32 <= ord(c) < 127 else "." for c in txt)
                    print("     ...%s..." % txt)
                    break
print()
print("total:", hits)
