#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Broad search: all jars under ~/.gradle/caches + build/moddev for the
substring 'missingdependency' (FML builds lang keys by concatenation, so the
full key may not appear literally).
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

NEEDLE = b"missingdependency"
SKIP = ("sources", "javadoc")

home = os.path.expanduser("~")
roots = [
    os.path.join(home, ".gradle", "caches"),
    "build/moddev/artifacts",
]
jars = []
for r in roots:
    if os.path.isfile(r):
        jars.append(r)
        continue
    for dirpath, _d, files in os.walk(r):
        for f in files:
            if f.endswith(".jar") and not any(s in f for s in SKIP):
                jars.append(os.path.join(dirpath, f))
jars = sorted(set(jars))
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
            if NEEDLE not in data:
                continue
            hits += 1
            print("HIT %-50s :: %s" % (os.path.basename(j), name))
            # neighbours in the constant pool
            for m in re.finditer(rb"[\x20-\x7e]{8,}", data):
                s = m.group().decode("ascii")
                if "missingdependency" in s or "modloading." in s or "dependency." in s:
                    print("      str: %s" % s)
            break
print()
print("total:", hits)
