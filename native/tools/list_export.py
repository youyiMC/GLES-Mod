#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List files under a patched_shaders export with sizes.

Usage: py native\\tools\\list_export.py <dir>
"""
import io
import os
import sys

root = sys.argv[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

rows = []
for dirpath, _dirnames, filenames in os.walk(root):
    for fn in filenames:
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, root)
        rows.append((rel, os.path.getsize(full)))

rows.sort()
print("files:", len(rows))
for rel, size in rows:
    print("  %-46s %8d" % (rel.replace("\\", "/"), size))
