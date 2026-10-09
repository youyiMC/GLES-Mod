#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Disassemble com.mojang.blaze3d.platform.TextureUtil and show the bytecode
around the constant 34049 (0x8501 = GL_TEXTURE_LOD_BIAS).

We want to know:
  * which call receives it (glTexParameterf / glTexParameteri)
  * what VALUE is passed

If the value is 0.0f, dropping the call is semantically a no-op, so our
backend can safely filter it out (removing both log noise and the spurious
GL error the driver leaves in the queue).

Self-locating; no args.
"""
import os
import re
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JAVAP = r"C:\Program Files\Java\jdk-21.0.12\bin\javap.exe"
if not os.path.isfile(JAVAP):
    JAVAP = "javap"

JAR = os.path.join("build", "moddev", "artifacts",
                   "neoforge-21.1.241-merged.jar")
CLS = "com/mojang/blaze3d/platform/TextureUtil.class"

if not os.path.isfile(JAR):
    print("jar not found:", JAR)
    sys.exit(1)

tmp = tempfile.mkdtemp(prefix="tu_")
# Keep the package directory so javap can resolve the class by FQN.
dest = os.path.join(tmp, CLS.replace("/", os.sep))
os.makedirs(os.path.dirname(dest), exist_ok=True)
with zipfile.ZipFile(JAR) as z:
    with open(dest, "wb") as fh:
        fh.write(z.read(CLS))
    # pull nested classes too
    for n in z.namelist():
        if n.startswith("com/mojang/blaze3d/platform/TextureUtil$"):
            p = os.path.join(tmp, n.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(z.read(n))

env = dict(os.environ)
env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"

r = subprocess.run(
    [JAVAP, "-J-Duser.language=en", "-c", "-p", "-cp", tmp,
     "com.mojang.blaze3d.platform.TextureUtil"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    env=env, timeout=240)

lines = (r.stdout or r.stderr or "").splitlines()
print("javap returncode:", r.returncode, " output lines:", len(lines))
print()

found = 0
for i, ln in enumerate(lines):
    if "34049" in ln:
        lo, hi = max(0, i - 12), min(len(lines), i + 8)
        print("=" * 74)
        print("命中 34049 @ line %d" % i)
        print("=" * 74)
        for k in range(lo, hi):
            mark = " <<<" if k == i else ""
            print("  %5d| %s%s" % (k, lines[k], mark))
        print()
        found += 1
        if found >= 3:
            break

if not found:
    print("未在反汇编中直接找到 34049；改为列出所有 texParameter 调用：")
    for i, ln in enumerate(lines):
        if "texParameter" in ln.lower():
            print("  %5d| %s" % (i, ln))
