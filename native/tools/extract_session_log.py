#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the shader-pack-session portion of glesmod native.log.

Why a script file: the integrated terminal keeps old scrollback, so inline
py -c output gets polluted.  We always write results to a file instead.
"""
import sys
import io

SRC = sys.argv[1] if len(sys.argv) > 1 else "native(1).log"
OUT = sys.argv[2] if len(sys.argv) > 2 else "native_session.txt"
MARK = sys.argv[3] if len(sys.argv) > 3 else "20:31:38"

with io.open(SRC, "rb") as f:
    lines = f.readlines()

start = 0
for i, raw in enumerate(lines):
    if MARK in raw.decode("utf-8", errors="replace"):
        start = i
        break

want = ("FBO 不完整", "INCOMPLETE", "被驱动拒绝", "降级: FBO", "无存储")

with io.open(OUT, "w", encoding="utf-8") as o:
    o.write("source=%s total=%d start_line=%d marker=%s\n\n" % (SRC, len(lines), start, MARK))
    o.write("===== FBO / texture-reject records =====\n")
    seen = set()
    for i in range(start, len(lines)):
        s = lines[i].decode("utf-8", errors="replace").rstrip()
        if not any(k in s for k in want):
            continue
        key = s.split("] ", 1)[-1]
        if key in seen:
            continue
        seen.add(key)
        o.write("%d: %s\n" % (i, s))
    o.write("\n===== tail of session (last 40 lines) =====\n")
    for i in range(max(start, len(lines) - 40), len(lines)):
        o.write("%d: %s\n" % (i, lines[i].decode("utf-8", errors="replace").rstrip()))

print("wrote", OUT)
