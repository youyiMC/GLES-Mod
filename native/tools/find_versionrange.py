#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List version-range related classes/strings inside the NeoForge loader jar,
so we can find the parser to invoke directly.
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

home = os.path.expanduser("~")
pats = [
    r"%s\.gradle\caches\**\loader-*.jar" % home,
    r"%s\.gradle\caches\**\fmlloader-*.jar" % home,
]
jars = []
for p in pats:
    jars.extend(glob.glob(p, recursive=True))
jars = sorted(set(j for j in jars if "sources" not in j))
print("jars:", [os.path.basename(j) for j in jars])

for j in jars:
    print("=" * 72)
    print(os.path.basename(j))
    print("=" * 72)
    with zipfile.ZipFile(j) as z:
        for n in sorted(z.namelist()):
            if not n.endswith(".class"):
                continue
            base = os.path.basename(n)
            low = n.lower()
            if ("version" in low and ("range" in low or "adapter" in low
                                      or "maven" in low)) or "MavenVersion" in base:
                print("  ", n)
        # also dump strings from the most likely parser classes
        for n in sorted(z.namelist()):
            if not n.endswith(".class"):
                continue
            if not (("versionrange" in n.lower()) or ("mavenversion" in n.lower())):
                continue
            data = z.read(n)
            strs = [s.decode("ascii", "replace")
                    for s in re.findall(rb"[\x20-\x7e]{4,}", data)]
            uniq = []
            for s in strs:
                if s not in uniq:
                    uniq.append(s)
            print()
            print("  --- strings in %s ---" % n)
            for s in uniq[:70]:
                print("      %s" % s)
