#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the shader sources that our library dumped into a real-device log.

The native library now prints, on compile failure:
    [GLESMod] ===== BEGIN 该 shader 收到 glShaderSource 的原始源码 =====
    [GLESMod]      0| <line>
    ...
    [GLESMod] ===== END 该 shader 收到 glShaderSource 的原始源码 (163 行) =====
    [GLESMod] ===== BEGIN 该 shader 实际被送入驱动的源码（转换后） =====
    ...
and the driver's own message:
    [GLESMod] ===== 驱动返回的着色器编译错误 (glGetShaderInfoLog) =====
    [GLESMod]   <text>

This tool pulls those blocks back out so the exact failing shader can be
reproduced and fixed on the host, with real glslang.

Self-locating; takes the newest fcl-latest*.log by default.
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "fromlog")
os.makedirs(OUT, exist_ok=True)

logs = sorted(glob.glob("fcl-latest*.log"), key=os.path.getmtime)
if not logs:
    print("no fcl-latest*.log found")
    sys.exit(1)
log = logs[-1]
print("reading:", log)

raw = open(log, encoding="utf-8", errors="replace").read()

# Strip the "[GLESMod] " prefix that our logger adds, and keep the rest.
PREFIX = re.compile(r"^\[GLESMod\] ?", re.M)

blocks = {}
# BEGIN ... END pairs (label may contain non-ASCII)
pat = re.compile(
    r"^\[GLESMod\] ===== BEGIN (?P<label>.+?) =====\s*$"
    r"(?P<body>.*?)"
    r"^\[GLESMod\] ===== END (?P=label) \((?P<n>\d+) 行\) =====\s*$",
    re.M | re.S)

for m in pat.finditer(raw):
    label = m.group("label").strip()
    body = m.group("body")
    lines = []
    for ln in body.splitlines():
        # each body line looks like: [GLESMod]      12| content
        mm = re.match(r"^\[GLESMod\]\s*(\d+)\|\s?(.*)$", ln)
        if mm:
            lines.append(mm.group(2))
    blocks[label] = lines
    print("  found block: %-55s %d lines" % (label, len(lines)))

# Also capture the driver error text that follows the InfoLog banner.
drv = re.search(
    r"^\[GLESMod\] ===== (?P<label>[^=]*glGetShaderInfoLog[^=]*) =====\s*$"
    r"(?P<body>(?:\n(?!\[22:|\d\d:\d\d:\d\d).*)*)", raw, re.M)
if drv:
    print()
    print("=" * 74)
    print("驱动原话 (%s):" % drv.group("label").strip())
    print("=" * 74)
    txt = drv.group("body")
    if txt.strip():
        for ln in txt.splitlines():
            if ln.strip():
                print("   ", ln.strip()[:160])
    else:
        print("   (空 —— 说明我们的日志转发仍有问题，见下文说明)")

# Save the two shader variants for reproduction.
saved = {}
for label, lines in blocks.items():
    if "原始源码" in label:
        p = os.path.join(OUT, "shader_raw.vert")
    elif "转换后" in label:
        p = os.path.join(OUT, "shader_converted.vert")
    else:
        continue
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    saved[label] = p
    print()
    print("saved:", p)

print()
print("out dir:", OUT)
