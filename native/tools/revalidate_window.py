#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate ONLY the shaders that failed during a single session window.

The whole native.log spans many runs and many shaderpacks; lumping them
together makes the failure list look far worse than the session being debugged.

Usage: py native\\tools\\revalidate_window.py <log> <start-marker> <outdir>
  e.g. py native\\tools\\revalidate_window.py "native(1).log" "20:31:38" shader_dump
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shader_from_log import (find_block, find_failing_shaders,  # noqa: E402
                             load_lines, write_src)

GLSLC = r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
IGNORE = re.compile(
    r"layout\(location=L\)"
    r"|SPIR-V requires"
    r"|non-opaque uniform variables"
    r"|not allowed when generating SPIR-V"
    r"|uniform/buffer blocks require layout"
)

log = sys.argv[1]
marker = sys.argv[2]
outdir = sys.argv[3]
os.makedirs(outdir, exist_ok=True)

lines = load_lines(log)

# session start = first line containing the marker
start = None
for i, s in enumerate(lines):
    if marker in s:
        start = i
        break
if start is None:
    print("marker not found:", marker)
    sys.exit(1)

fails = [t for t in find_failing_shaders(lines) if t[0] >= start]
print("session starts at line %d (%s) of %d" % (start, marker, len(lines)))
print("failure entries inside this session:", len(fails))

real, ok, missing = [], [], []
for idx, sid, stage in fails:
    data = find_block(lines, idx, "实际被送入驱动的源码（转换后）")
    if data is None:
        missing.append(sid)
        continue
    p = os.path.join(outdir, "w%d.%s" % (sid, stage))
    write_src(p, data)
    r = subprocess.run(
        [GLSLC, "--target-env=opengl", "-fshader-stage=" + stage, p,
         "-o", p + ".spv"],
        capture_output=True, text=True, errors="replace")
    errs = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ": error:" in ln and not IGNORE.search(ln)]
    (real if errs else ok).append((sid, stage, p, errs))

print()
print("=" * 72)
print("  compiles fine (false alarm) : %d  %s"
      % (len(ok), [s for s, _, _, _ in ok]))
print("  REAL failures               : %d  %s"
      % (len(real), [s for s, _, _, _ in real]))
print("  no converted block          : %d  %s" % (len(missing), missing))
print("=" * 72)
for sid, stage, p, errs in real:
    print("\n shader %d (%s)" % (sid, stage))
    for e in errs[:6]:
        print("     " + e.strip())
