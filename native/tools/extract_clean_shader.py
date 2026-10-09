#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract a shader's raw+converted source from native.log, strip the "   N| "
dump prefix, and write clean .glsl files for glslang to compile.

Usage: py native\\tools\\extract_clean_shader.py <log> <shaderid> <outdir>
"""
import io
import os
import re
import sys

log, sid, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(outdir, exist_ok=True)

with io.open(log, "rb") as f:
    lines = [l.decode("utf-8", errors="replace").rstrip("\r\n") for l in f]

idx = None
for i, s in enumerate(lines):
    if "编译失败的着色器" in s and ("GL 名称=%s" % sid) in s:
        idx = i
        break
if idx is None:
    print("not found:", sid)
    sys.exit(1)

TS = re.compile(r"^\[\d\d:\d\d:\d\d\.\d+\]\s?")
PFX = re.compile(r"^\s*\d+\|\s?")


def block(kind, stop):
    """Walk back from `stop` to the BEGIN/END pair for `kind`."""
    end = None
    label = "END 该 shader " + kind
    for i in range(stop, max(0, stop - 600), -1):
        if label in lines[i]:
            end = i
            break
    if end is None:
        return None
    b = "BEGIN 该 shader " + kind
    for i in range(end, max(0, end - 600), -1):
        if b in lines[i]:
            begin = i
            break
    else:
        return None
    # native.log writes each dumped line TWICE IN A ROW.  Deduplicate by
    # position pairing (skip a line identical to the previous one), NOT by a
    # content set -- a content set would collapse repeated braces such as
    # `}` and silently corrupt the source.
    out = []
    prev = None
    for i in range(begin + 1, end):
        t = PFX.sub("", TS.sub("", lines[i]))
        # The END marker is itself written twice, so the first copy lands
        # inside the range.  Stop at it.
        if t.startswith("===== END 该 shader"):
            break
        if t == prev:
            prev = None
            continue
        prev = t
        out.append(t)
    return out


conv = block("实际被送入驱动的源码（转换后）", idx)
raw = block("收到 glShaderSource 的原始源码", idx)

for name, data in (("converted", conv), ("raw", raw)):
    if data is None:
        print("%s: block not found" % name)
        continue
    p = os.path.join(outdir, "shader%s_%s.frag" % (sid, name))
    with io.open(p, "w", encoding="utf-8") as o:
        o.write("\n".join(data) + "\n")
    print("%s -> %s (%d lines)" % (name, p, len(data)))
