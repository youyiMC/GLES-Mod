#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate EVERY shader that native.log marked as "编译失败" with glslang.

Decisive experiment: if the converted source of each such shader compiles
cleanly under glslang (ignoring SPIR-V-only diagnostics), then those log
entries are FALSE POSITIVES produced by our glGetShaderiv/glGetShaderInfoLog
wrappers, and the real blocker is something else.

Usage: py native\\tools\\validate_failed_shaders.py <log> <stage-map-optional>
"""
import io
import os
import re
import subprocess
import sys

GLSLC = r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
OUT = "shader_dump"

# SPIR-V-only diagnostics that a GLES runtime does NOT require.
IGNORE = re.compile(
    r"layout\(location=L\)|SPIR-V requires|non-opaque uniform variables",
)

log = sys.argv[1]

with io.open(log, "rb") as f:
    lines = [l.decode("utf-8", errors="replace").rstrip("\r\n") for l in f]

TS = re.compile(r"^\[\d\d:\d\d:\d\d\.\d+\]\s?")
PFX = re.compile(r"^\s*\d+\|\s?")

# Collect failing shader ids together with their stage.
fails = []
for i, s in enumerate(lines):
    m = re.search(r"编译失败的着色器 .* 阶段=(\S+)，GL 名称=(\d+)", s)
    if m:
        stage = "vert" if "顶点" in m.group(1) else "frag"
        fails.append((i, int(m.group(2)), stage))

# Native log writes each line twice -> collapse duplicates.
uniq = []
seen = set()
for i, sid, st in fails:
    if sid in seen:
        continue
    seen.add(sid)
    uniq.append((i, sid, st))

print("distinct failing shaders:", len(uniq), uniq)

os.makedirs(OUT, exist_ok=True)
real = 0


def extract(idx, kind):
    label_end = "END 该 shader " + kind
    end = None
    for i in range(idx, max(0, idx - 900), -1):
        if label_end in lines[i]:
            end = i
            break
    if end is None:
        return None
    label_beg = "BEGIN 该 shader " + kind
    begin = None
    for i in range(end, max(0, end - 900), -1):
        if label_beg in lines[i]:
            begin = i
            break
    if begin is None:
        return None
    out = []
    prev = None
    for i in range(begin + 1, end):
        t = PFX.sub("", TS.sub("", lines[i]))
        if t.startswith("===== END 该 shader"):
            break
        if t == prev:
            prev = None
            continue
        prev = t
        out.append(t)
    return out


for idx, sid, stage in uniq:
    data = extract(idx, "实际被送入驱动的源码（转换后）")
    if data is None:
        print("  shader %-4d  <no converted block>" % sid)
        continue
    p = os.path.join(OUT, "f%d.%s" % (sid, stage))
    with io.open(p, "w", encoding="utf-8") as o:
        o.write("\n".join(data) + "\n")

    r = subprocess.run(
        [GLSLC, "--target-env=opengl", "-fshader-stage=" + stage, p,
         "-o", p + ".spv"],
        capture_output=True, text=True, errors="replace",
    )
    errs = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ": error:" in ln and not IGNORE.search(ln)]
    if errs:
        real += 1
        print("  shader %-4d  %s  REAL ERROR (%d):" % (sid, stage, len(errs)))
        for e in errs[:6]:
            print("        " + e.strip())
    else:
        print("  shader %-4d  %s  ok (only SPIR-V-only diagnostics)" % (sid, stage))

print()
print("REAL compile failures:", real, "of", len(uniq))
