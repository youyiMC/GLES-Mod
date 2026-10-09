#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract a converted shader source + the raw info-log bytes from native.log.

Usage:
  py native\\tools\\extract_shader_dump.py <log> <shaderid> <outdir>

Writes:
  <outdir>/shader_<id>.glsl   -- the converted source actually sent to driver
  <outdir>/infolog_<id>.txt   -- hex dump of the driver info-log lines
"""
import io
import os
import re
import sys

log = sys.argv[1]
sid = sys.argv[2]
outdir = sys.argv[3]
os.makedirs(outdir, exist_ok=True)

with io.open(log, "rb") as f:
    lines = f.readlines()

# locate "编译失败的着色器 —— 阶段=..，GL 名称=<sid>"
idx = None
for i, raw in enumerate(lines):
    s = raw.decode("utf-8", errors="replace")
    if "编译失败的着色器" in s and ("GL 名称=%s" % sid) in s:
        idx = i
        break

if idx is None:
    print("shader id not found:", sid)
    sys.exit(1)

# The converted source block ends a bit before idx (the END marker).
src_lines = []
srcdir = os.path.join(outdir, "shader_%s.glsl" % sid)
indir = os.path.join(outdir, "infolog_%s.txt" % sid)

# Walk backwards to find BEGIN ... END converted block
end_marker = None
for i in range(idx, max(0, idx - 400), -1):
    s = lines[i].decode("utf-8", errors="replace")
    if "END 该 shader 实际被送入驱动的源码" in s:
        end_marker = i
        break

begin_marker = None
if end_marker is not None:
    for i in range(end_marker, max(0, end_marker - 400), -1):
        s = lines[i].decode("utf-8", errors="replace")
        if "BEGIN 该 shader 实际被送入驱动的源码" in s:
            begin_marker = i
            break

if begin_marker is not None:
    seen = set()
    for i in range(begin_marker + 1, end_marker):
        s = lines[i].decode("utf-8", errors="replace").rstrip("\r\n")
        m = re.match(r"^\d+: \[\S+\]\s?(.*)$", s)
        if not m:
            continue
        t = m.group(1)
        if t in seen:
            continue          # native.log writes each line twice
        seen.add(t)
        src_lines.append(t)

with io.open(srcdir, "w", encoding="utf-8") as o:
    o.write("\n".join(src_lines) + "\n")

# hex dump the info log lines following idx
with io.open(indir, "w", encoding="utf-8") as o:
    o.write("=== raw bytes of info-log lines after line %d ===\n" % idx)
    for i in range(idx, min(len(lines), idx + 14)):
        raw = lines[i]
        o.write("line %d\n" % i)
        o.write("  repr: %r\n" % raw[:200])
        o.write("  hex : %s\n" % raw[:120].hex(" "))

print("shader src ->", srcdir, "(%d lines)" % len(src_lines))
print("info log  ->", indir)
