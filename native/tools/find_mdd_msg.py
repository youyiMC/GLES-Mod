#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate moddev-gradle, extract the "only supports" context from
ModDevRunWorkflow.class.  Self-locating so the task-runner shell can't
mangle the path.
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

pats = [
    os.path.expanduser(r"~\.gradle\caches\modules-2\**\moddev-gradle-*.jar"),
    os.path.expanduser(r"~\.gradle\caches\**\moddev-gradle-*.jar"),
]
jars = set()
for p in pats:
    jars.update(glob.glob(p, recursive=True))

print("found %d moddev-gradle jars" % len(jars))
if not jars:
    sys.exit(1)

jars = sorted(jars, key=os.path.getmtime, reverse=True)
target = jars[0]
print("using:", target)
print()

with zipfile.ZipFile(target) as z:
    for n in z.namelist():
        if "ModDevRunWorkflow" not in n:
            continue
        data = z.read(n)
        strs = [s.decode("ascii", "replace")
                for s in re.findall(rb"[\x20-\x7e]{4,}", data)]
        idx = [i for i, s in enumerate(strs)
               if "only supports" in s or "supports " in s or "Currently," in s]
        if not idx:
            continue
        print("=" * 72)
        print("CLASS:", n)
        print("=" * 72)
        lo = max(0, min(idx) - 10)
        hi = min(len(strs), max(idx) + 11)
        for i in range(lo, hi):
            mark = "  <<<" if i in idx else ""
            print("%4d| %s%s" % (i, strs[i], mark))
