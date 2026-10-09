#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List candidate MC client jars under the neoformruntime cache."""
import glob
import os
import sys

roots = [
    os.path.expanduser(r"~\.gradle\caches\neoformruntime\intermediate_results"),
    os.path.expanduser(r"~\.gradle\caches\neoformruntime\artifacts"),
]
sys.stdout.reconfigure(encoding="utf-8")
for r in roots:
    for p in glob.glob(os.path.join(r, "**", "*.jar"), recursive=True):
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz > 5 * 1024 * 1024:
            print("%10.1f MB  %s" % (sz / 1048576.0, p))
