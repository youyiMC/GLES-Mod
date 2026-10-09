#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print a line range of a file with 1-based numbering.

Usage: py native\\tools\\show_range.py <file> <from> <to> [out]
Writes to <out> (default showrange.txt) so the terminal never truncates.
"""
import io
import sys

path = sys.argv[1]
a = int(sys.argv[2])
b = int(sys.argv[3])
out = sys.argv[4] if len(sys.argv) > 4 else "showrange.txt"

with io.open(path, encoding="utf-8", errors="replace") as f:
    lines = f.read().splitlines()

a = max(1, a)
b = min(len(lines), b)

with io.open(out, "w", encoding="utf-8") as o:
    o.write("%s  total=%d  range=%d..%d\n\n" % (path, len(lines), a, b))
    width = len(str(b))
    for i in range(a, b + 1):
        o.write("%*d | %s\n" % (width, i, lines[i - 1]))

sys.stdout.write("wrote %s (%d lines)\n" % (out, b - a + 1))
