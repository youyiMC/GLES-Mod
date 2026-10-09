#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print the converted source of a failing shader from glesmod native.log.

native.log line format is:  [HH:MM:SS.mmm] <content>
(no line-number prefix -- that is added by dump_log_range.py, not by the logger)

Usage: py native\\tools\\show_failed_shader.py <log> <shaderid> <out>
"""
import io
import re
import sys

log, sid, out = sys.argv[1], sys.argv[2], sys.argv[3]

with io.open(log, "rb") as f:
    lines = [l.decode("utf-8", errors="replace").rstrip("\r\n") for l in f]

# find the "编译失败的着色器 ... GL 名称=<sid>" line
idx = None
for i, s in enumerate(lines):
    if "编译失败的着色器" in s and ("GL 名称=%s" % sid) in s:
        idx = i
        break
if idx is None:
    print("not found:", sid)
    sys.exit(1)

# END marker of the converted block, walking back from idx
end = None
for i in range(idx, max(0, idx - 500), -1):
    if "END 该 shader 实际被送入驱动的源码" in lines[i]:
        end = i
        break

begin = None
if end is not None:
    for i in range(end, max(0, end - 500), -1):
        if "BEGIN 该 shader 实际被送入驱动的源码" in lines[i]:
            begin = i
            break

strip = re.compile(r"^\[\d\d:\d\d:\d\d\.\d+\]\s?")

with io.open(out, "w", encoding="utf-8") as o:
    o.write("shader %s  begin=%s end=%s idx=%s\n\n" % (sid, begin, end, idx))
    if begin is None or end is None:
        o.write("markers not found; dumping -60..+6 around idx\n")
        for i in range(max(0, idx - 60), min(len(lines), idx + 6)):
            o.write("%d: %s\n" % (i, lines[i]))
    else:
        seen = set()
        for i in range(begin + 1, end):
            t = strip.sub("", lines[i])
            if t in seen:
                continue
            seen.add(t)
            o.write(t + "\n")
    o.write("\n===== info log bytes (idx-2 .. idx+12) =====\n")
    for i in range(max(0, idx - 2), min(len(lines), idx + 12)):
        o.write("%d repr: %r\n" % (i, lines[i][:200]))
        o.write("%d hex : %s\n" % (i, lines[i][:100].encode("utf-8", "replace").hex(" ")))

print("wrote", out)
