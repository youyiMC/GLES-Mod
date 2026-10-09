#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find the NeoForge mod-dependency-check messages.

Searches every neoforge*.jar for:
  * lang json entries whose key contains 'dependency' or value contains
    'only supports' / 'is required' / 'Currently'
  * class entries whose raw bytes contain 'only supports'

Prints en_us entries so we can see the exact wording/template.
"""
import glob
import json
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

home = os.path.expanduser("~")
pats = [
    r"%s\.gradle\caches\modules-2\files-2.1\net.neoforged\**\neoforge*.jar" % home,
    r"%s\.gradle\caches\**\neoforge*.jar" % home,
    "build/moddev/artifacts/neoforge*.jar",
]
jars = []
for p in pats:
    jars.extend(glob.glob(p, recursive=True))
jars = sorted(set(os.path.basename(j) + "|" + j for j in jars))
print("neoforge jars found: %d" % len(jars))
for j in jars:
    print("  ", j.split("|")[1])
print()

seen = set()
for key in jars:
    j = key.split("|", 1)[1]
    if os.path.basename(j) in seen:
        continue
    seen.add(os.path.basename(j))
    try:
        z = zipfile.ZipFile(j)
    except Exception:
        continue
    with z:
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            if "/lang/" not in name:
                continue
            if not name.endswith("en_us.json"):
                continue
            try:
                data = z.read(name)
                obj = json.loads(data.decode("utf-8"))
            except Exception as e:
                print("skip", name, e)
                continue
            print("=" * 72)
            print("LANG:", name, "in", os.path.basename(j))
            print("=" * 72)
            for k, v in obj.items():
                if "only supports" in v or "Currently" in v or "dependency" in k:
                    print("  %-70s = %s" % (k, v))
