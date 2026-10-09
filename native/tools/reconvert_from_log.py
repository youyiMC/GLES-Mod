#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-convert every shader recorded in native.log with the CURRENT converter
and re-validate with glslang.

This is the decisive regression test: it answers "does today's converter fix
the failures seen on device?" without needing another device round-trip.

Input source for each shader = the RAW source recorded at glShaderSource time
(that is what the converter receives in production).  We run our CLI on it and
compile the result.

Usage: py native\\tools\\reconvert_from_log.py <log> [outdir]
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shader_from_log import (find_block, find_failing_shaders,  # noqa: E402
                            load_lines, write_src)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = os.path.join(ROOT, "native", "tools", ".cache", "convert_shader_cli.exe")
GLSLC = r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
IGNORE = re.compile(
    r"layout\(location=L\)"
    r"|SPIR-V requires"
    r"|non-opaque uniform variables"
    r"|not allowed when generating SPIR-V"
    r"|uniform/buffer blocks require layout"
)

log = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else "reconv"
os.makedirs(outdir, exist_ok=True)

lines = load_lines(sys.argv[1])
fails = find_failing_shaders(lines)

seen = set()
uniq = []
for idx, sid, st in fails:
    if sid in seen:
        continue
    seen.add(sid)
    uniq.append((idx, sid, st))

before_bad = []
after_bad = []
skipped = []

for idx, sid, stage in uniq:
    raw = find_block(lines, idx, "收到 glShaderSource 的原始源码")
    if raw is None:
        skipped.append(sid)
        continue
    rawp = os.path.join(outdir, "%d.raw" % sid)
    convp = os.path.join(outdir, "%d.%s" % (sid, stage))
    write_src(rawp, raw)

    r = subprocess.run([CLI, rawp, "vertex" if stage == "vert" else "fragment",
                        convp], capture_output=True, text=True, errors="replace")
    if not os.path.exists(convp):
        skipped.append(sid)
        continue

    conv = open(convp, encoding="utf-8", errors="replace").read()

    # (a) is the RAW source itself already valid ES?  (pack-original bug)
    raw_es = os.path.join(outdir, "%d.raw_as_es.%s" % (sid, stage))
    body = [l for l in raw if not l.lstrip().startswith("#version")]
    rr = ["#version 320 es", "precision highp float;", "precision highp int;"] + body
    write_src(raw_es, rr)
    q = subprocess.run([GLSLC, "--target-env=opengl", "-fshader-stage=" + stage,
                        raw_es, "-o", raw_es + ".spv"],
                       capture_output=True, text=True, errors="replace")
    raw_errs = [l for l in (q.stdout + q.stderr).splitlines()
                if ": error:" in l and not IGNORE.search(l)]

    # (b) does OUR converted output compile?
    q = subprocess.run([GLSLC, "--target-env=opengl", "-fshader-stage=" + stage,
                        convp, "-o", convp + ".spv"],
                       capture_output=True, text=True, errors="replace")
    conv_errs = [l for l in (q.stdout + q.stderr).splitlines()
                 if ": error:" in l and not IGNORE.search(l)]

    if raw_errs:
        before_bad.append((sid, stage, raw_errs))
    if conv_errs:
        after_bad.append((sid, stage, convp, conv_errs))

print("=" * 76)
print(" shaders re-converted with the CURRENT converter : %d" % (len(uniq) - len(skipped)))
print("   RAW source already invalid ES (pack bug)      : %d %s"
      % (len(before_bad), [s for s, _, _ in before_bad]))
print("   OUR converted output still invalid            : %d %s"
      % (len(after_bad), [s for s, _, _, _ in after_bad]))
print("   skipped (no raw block)                        : %d %s" % (len(skipped), skipped))
print("=" * 76)

for sid, stage, p, errs in after_bad[:12]:
    print("\n shader %d (%s) <- %s" % (sid, stage, p))
    for e in errs[:5]:
        print("     " + e.strip())
