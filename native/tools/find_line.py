#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Grep a file for a substring and write numbered matches.

Usage: py native\\tools\\find_line.py <file> <needle> [out]
"""
import io
import sys

path = sys.argv[1]
needle = sys.argv[2]
out = sys.argv[3] if len(sys.argv) > 3 else "findline.txt"

with io.open(path, encoding="utf-8", errors="replace") as f:
    lines = f.read().splitlines()

with io.open(out, "w", encoding="utf-8") as o:
    o.write("%s  total=%d  needle=%r\n\n" % (path, len(lines), needle))
    for i, s in enumerate(lines, 1):
        if needle in s:
            o.write("%4d | %s\n" % (i, s))

sys.stdout.write("wrote %s\n" % out)
