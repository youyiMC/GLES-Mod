#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print the bytecode of Options.<clinit> / <init> around the framerateLimit
OptionInstance construction, so the DEFAULT value is read off the bytecode
instead of remembered.

Also reports UNLIMITED_FRAMERATE_CUTOFF's value.
"""
import os
import re
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JAVAP = r"C:\Program Files\Java\jdk-21.0.12\bin\javap.exe"
JAR = os.path.join("build", "moddev", "artifacts",
                   "neoforge-21.1.241-merged.jar")
CLS = "net/minecraft/client/Options.class"

tmp = tempfile.mkdtemp(prefix="opt2_")
dest = os.path.join(tmp, CLS.replace("/", os.sep))
os.makedirs(os.path.dirname(dest), exist_ok=True)
with zipfile.ZipFile(JAR) as z:
    with open(dest, "wb") as fh:
        fh.write(z.read(CLS))
    # dependencies javap may need for nesting
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
lines = (r.stdout or "").splitlines()

# locate the method that builds framerateLimit (the one containing putfield #25
# preceded by ldc "options.framerateLimit")
print("=" * 74)
print("framerateLimit 赋值处（putfield）前后 40 行")
print("=" * 74)
for i, ln in enumerate(lines):
    if "putfield" in ln and "framerateLimit:Lnet" in ln:
        lo, hi = max(0, i - 40), min(len(lines), i + 3)
        for k in range(lo, hi):
            mark = " <<<" if k == i else ""
            print("  %5d| %s%s" % (k, lines[k], mark))
        print()

print("=" * 74)
print("UNLIMITED_FRAMERATE_CUTOFF 的常量值")
print("=" * 74)
# In <clinit> the static final int is assigned via putstatic; show surrounding
for i, ln in enumerate(lines):
    if "UNLIMITED_FRAMERATE_CUTOFF" in ln:
        lo, hi = max(0, i - 6), min(len(lines), i + 6)
        for k in range(lo, hi):
            print("  %5d| %s" % (k, lines[k]))
        print()
        break

print("=" * 74)
print("所有 bipush/sipush/ldc 触碰 60/75/120/144/240/260 的位置")
print("=" * 74)
pat = re.compile(r"(bipush|sipush|ldc)\s+#?\d+\s*//\s*int\s+(60|75|120|144|240|260)\b")
for i, ln in enumerate(lines):
    m = pat.search(ln)
    if m:
        print("  %5d| %s" % (i, ln.strip()))
