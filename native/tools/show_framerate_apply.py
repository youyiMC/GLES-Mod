#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print the Options method that calls Window.setFramerateLimit, to reveal the
'Unlimited' threshold (the value at which the limit is not applied).

Self-locating; no args.
"""
import os
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JAVAP = r"C:\Program Files\Java\jdk-21.0.12\bin\javap.exe"
JAR = os.path.join("build", "moddev", "artifacts",
                   "neoforge-21.1.241-merged.jar")

tmp = tempfile.mkdtemp(prefix="opt3_")
n = "net/minecraft/client/Options.class"
dest = os.path.join(tmp, n.replace("/", os.sep))
os.makedirs(os.path.dirname(dest), exist_ok=True)
with zipfile.ZipFile(JAR) as z:
    with open(dest, "wb") as fh:
        fh.write(z.read(n))
    for m in z.namelist():
        if m.startswith("net/minecraft/client/Options$"):
            p = os.path.join(tmp, m.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(z.read(m))

env = dict(os.environ)
env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"
r = subprocess.run(
    [JAVAP, "-J-Duser.language=en", "-c", "-p", "-cp", tmp,
     "net.minecraft.client.Options"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    env=env, timeout=300)
lines = (r.stdout or "").splitlines()

# The slider label mapping: value -> "Unlimited". Shows the threshold where the
# limit stops being applied.
print("=" * 74)
print('framerateLimit.max（值 -> "Unlimited"）附近的字节码')
print("=" * 74)
for i, ln in enumerate(lines):
    if "options.framerateLimit.max" in ln:
        lo, hi = max(0, i - 14), min(len(lines), i + 20)
        for k in range(lo, hi):
            mark = " <<<" if k == i else ""
            print("  %5d| %s%s" % (k, lines[k], mark))
        print()

# Find the enclosing method name for each setFramerateLimit call, print ±22 lines
for i, ln in enumerate(lines):
    if "setFramerateLimit" not in ln:
        continue
    # walk back to the nearest method signature line
    sig = None
    for k in range(i, -1, -1):
        s = lines[k].rstrip()
        if s and not s.startswith(" ") and "(" in s and ")" in s:
            sig = s
            break
    print("=" * 74)
    print("方法:", sig)
    print("=" * 74)
    lo, hi = max(0, i - 22), min(len(lines), i + 6)
    for k in range(lo, hi):
        mark = " <<<" if k == i else ""
        print("  %5d| %s%s" % (k, lines[k], mark))
    print()
