#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find Minecraft's default "Max Framerate" value.

Why this matters: the user reports Sodium + our backend holding at ~120 FPS on
a 120 Hz panel and not going higher even with vsync off. If that 120 is
Minecraft's OWN frame limiter (not the display and not our backend), then the
measurement says nothing about our headroom, and the fix is a video setting
rather than any code change.

Minecraft keeps it in net.minecraft.client.Options as `framerateLimit`.
This tool disassembles that class and prints the bytecode around it, so the
default can be read off directly instead of remembered.

Self-locating; no args.
"""
import glob
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
if not os.path.isfile(JAR):
    print("jar not found:", JAR)
    sys.exit(1)

CLS = "net/minecraft/client/Options.class"
tmp = tempfile.mkdtemp(prefix="opt_")
dest = os.path.join(tmp, CLS.replace("/", os.sep))
os.makedirs(os.path.dirname(dest), exist_ok=True)
with zipfile.ZipFile(JAR) as z:
    with open(dest, "wb") as fh:
        fh.write(z.read(CLS))
    for n in z.namelist():
        if n.startswith("net/minecraft/client/Options$"):
            p = os.path.join(tmp, n.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(z.read(n))

env = dict(os.environ)
env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"
r = subprocess.run(
    [JAVAP, "-J-Duser.language=en", "-c", "-p", "-cp", tmp,
     "net.minecraft.client.Options"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    env=env, timeout=300)
lines = (r.stdout or r.stderr or "").splitlines()
print("javap rc=%d, %d lines" % (r.returncode, len(lines)))

# 1) strings mentioning framerate
print()
print("=" * 74)
print("引用 framerateLimit / maxFps 的常量池项")
print("=" * 74)
for i, ln in enumerate(lines):
    if re.search(r"framerate|maxFps|vsync|VSync", ln, re.I):
        print("  %5d| %s" % (i, ln.strip()[:150]))

# 2) bytecode around the framerateLimit construction
print()
print("=" * 74)
print("framerateLimit 构造处附近的字节码（读默认值）")
print("=" * 74)
shown = 0
for i, ln in enumerate(lines):
    if "framerateLimit" in ln or "options.framerateLimit" in ln:
        lo, hi = max(0, i - 6), min(len(lines), i + 26)
        print("-" * 74)
        for k in range(lo, hi):
            mark = " <<<" if k == i else ""
            print("  %5d| %s%s" % (k, lines[k], mark))
        shown += 1
        if shown >= 2:
            break
if shown == 0:
    print("  (未找到；改为打印所有 bipush/sipush 120 附近)")
    for i, ln in enumerate(lines):
        if re.search(r"\b(120|260)\b", ln) and ("int" in ln or "bipush" in ln
                                               or "sipush" in ln):
            lo, hi = max(0, i - 5), min(len(lines), i + 6)
            for k in range(lo, hi):
                print("  %5d| %s" % (k, lines[k]))
            print()
            break
