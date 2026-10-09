#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Count top-level (brace-depth 0) declarations in a shader.

Why: global_names.is_global[] in shader.c is a 64-byte array.  If a shader has
more than 64 globals, global_names_has() reads past the end of that array
(undefined behaviour) and the "is this initializer non-constant?" test becomes
unreliable -- exactly the symptom seen in the 1099-line
020_terrain_translucent.fsh (init not stripped) while the short
007_basic.fsh (init stripped) works.

Usage: py native\\tools\\count_globals.py <file>
"""
import io
import re
import sys

path = sys.argv[1]
src = io.open(path, encoding="utf-8", errors="replace").read()

# strip comments
src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
src = re.sub(r"//[^\n]*", " ", src)

depth = 0
buf = []
stmts = []
for ch in src:
    if ch == "{":
        depth += 1
        if depth == 1:
            buf = []
        continue
    if ch == "}":
        depth -= 1
        continue
    if depth == 0:
        if ch == ";":
            s = "".join(buf).strip()
            if s:
                stmts.append(s)
            buf = []
        else:
            buf.append(ch)

TYPE_RX = re.compile(
    r"^\s*(?:layout\s*\([^)]*\)\s*)?"
    r"(?:(?:uniform|const|in|out|flat|smooth|noperspective|centroid|"
    r"attribute|varying)\s+)*"
    r"(?:lowp|mediump|highp)?\s*"
    r"(sampler2D|sampler3D|samplerCube|sampler2DShadow|sampler2DArray|"
    r"isampler2D|usampler2D|float|int|uint|bool|double|"
    r"vec[234]|ivec[234]|uvec[234]|bvec[234]|mat[234](?:x[234])?)\b")

n = 0
for s in stmts:
    if TYPE_RX.match(s):
        n += 1

print("file      :", path)
print("globals   :", n)
print("tracked   : 64  (global_names.is_global[])")
print("overflow  :", "YES  <-- exceeds the 64-entry table" if n > 64 else "no")
print()
print("-- first 6 --")
for s in stmts[:6]:
    print("   ", s[:100])
