#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print META-INF/neoforge.mods.toml from the built jar, filtering to the
[[dependencies.*]] blocks so the Sodium/Embeddium ranges are easy to read."""
import glob
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

for p in glob.glob(r"build\libs\*.jar"):
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():
            if not n.endswith("neoforge.mods.toml"):
                continue
            print("=" * 70)
            print(p, "::", n)
            print("=" * 70)
            txt = z.read(n).decode("utf-8", errors="replace")
            lines = txt.splitlines()
            show = False
            for i, l in enumerate(lines):
                s = l.strip()
                if s.startswith("[[dependencies"):
                    show = True
                    print()
                if show:
                    print("%4d| %s" % (i + 1, l))
                if show and s.startswith("side"):
                    show = False
            print()
