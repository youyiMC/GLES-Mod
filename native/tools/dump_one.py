#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump raw + converted source of one shader from native.log (correct dedup).

Usage: py native\\tools\\dump_one.py <log> <shaderid> <stage> <outdir>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shader_from_log import (content, find_block, find_failing_shaders,  # noqa: E402
                             load_lines, write_src)

log, sid, stage, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
os.makedirs(outdir, exist_ok=True)

lines = load_lines(log)
hit = [t for t in find_failing_shaders(lines) if t[1] == sid]
if not hit:
    print("shader %d not present as a failure entry" % sid)
    sys.exit(1)

idx = hit[0][0]
for kind, tag in (("收到 glShaderSource 的原始源码", "raw"),
                  ("实际被送入驱动的源码（转换后）", "conv")):
    data = find_block(lines, idx, kind)
    if data is None:
        print("%s: block not found" % tag)
        continue
    p = os.path.join(outdir, "%d_%s.%s" % (sid, tag, stage))
    write_src(p, data)
    print("%s -> %s (%d lines)" % (tag, p, len(data)))

print("\n--- info log lines around the failure entry ---")
for i in range(idx, min(len(lines), idx + 10)):
    print("%d: %r" % (i, content(lines[i])))
