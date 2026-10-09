#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump a line range of glesmod native.log with UTF-8 decoding.

Usage: py native\\tools\\dump_log_range.py <log> <from> <to> <out>
"""
import io
import sys

src = sys.argv[1]
a = int(sys.argv[2])
b = int(sys.argv[3])
out = sys.argv[4]

with io.open(src, "rb") as f:
    lines = f.readlines()

a = max(0, a)
b = min(len(lines), b)

with io.open(out, "w", encoding="utf-8") as o:
    o.write("range %d..%d of %d\n\n" % (a, b, len(lines)))
    for i in range(a, b):
        o.write("%d: %s\n" % (i, lines[i].decode("utf-8", errors="replace").rstrip()))

print("wrote", out, "lines", b - a)
