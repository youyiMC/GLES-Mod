#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find Options.UNLIMITED_FRAMERATE_CUTOFF's value, and where it is compared,
so we know the exact slider value that means "unlimited".

Minecraft sets `Window.setFramerateLimit()` from framerateLimit; a special
threshold means "no limit". Knowing the value lets the user pick the right
slider position (or confirms that the top slider step already means unlimited).

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
JAR = os.path.join("build", "moddev", "artifacts",
                   "neoforge-21.1.241-merged.jar")

tmp = tempfile.mkdtemp(prefix="cut_")


def extract(cls):
    n = cls.replace(".", "/") + ".class"
    dest = os.path.join(tmp, n.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with zipfile.ZipFile(JAR) as z:
        names = z.namelist()
        if n not in names:
            return False
        with open(dest, "wb") as fh:
            fh.write(z.read(n))
        # nested
        base = n[:-6]
        for m in names:
            if m.startswith(base + "$"):
                p = os.path.join(tmp, m.replace("/", os.sep))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(z.read(m))
    return True


env = dict(os.environ)
env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"


def disasm(cls):
    extract(cls)
    r = subprocess.run(
        [JAVAP, "-J-Duser.language=en", "-c", "-p", "-cp", tmp, cls],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=300)
    return (r.stdout or r.stderr or "").splitlines()


# Look in Options (static init) and Window (where the limit is applied).
for cls in ("net.minecraft.client.Options",
            "com.mojang.blaze3d.platform.Window"):
    lines = disasm(cls)
    print("=" * 74)
    print(cls, " (%d lines)" % len(lines))
    print("=" * 74)
    for i, ln in enumerate(lines):
        if "UNLIMITED_FRAMERATE_CUTOFF" in ln or "setFramerateLimit" in ln \
                or "framerateLimit" in ln:
            lo, hi = max(0, i - 4), min(len(lines), i + 8)
            print("-" * 60)
            for k in range(lo, hi):
                mark = " <<<" if k == i else ""
                print("  %5d| %s%s" % (k, lines[k], mark))
    print()

# The constant's actual number: find <clinit> putstatic for it.
lines = disasm("net.minecraft.client.Options")
print("=" * 74)
print("Options 中所有 putstatic（静态常量赋值）")
print("=" * 74)
for i, ln in enumerate(lines):
    if "putstatic" in ln:
        lo = max(0, i - 3)
        for k in range(lo, i + 1):
            print("  %5d| %s" % (k, lines[k]))
        print()

# Window.setFramerateLimit implementation + any 260 comparison
wlines = disasm("com.mojang.blaze3d.platform.Window")
print()
print("=" * 74)
print("Window 的 <clinit>（找 UNLIMITED_FRAMERATE_CUTOFF 的常量值）")
print("=" * 74)
for i, ln in enumerate(wlines):
    if "static {}" in ln or "<clinit>" in ln:
        lo, hi = i, min(len(wlines), i + 30)
        for k in range(lo, hi):
            print("  %5d| %s" % (k, wlines[k]))
        print()
        break

print()
print("=" * 74)
print("Window 中所有出现 260 的位置（判断是否就是 cutoff）")
print("=" * 74)
for i, ln in enumerate(wlines):
    if "260" in ln:
        lo, hi = max(0, i - 5), min(len(wlines), i + 5)
        for k in range(lo, hi):
            mark = " <<<" if k == i else ""
            print("  %5d| %s%s" % (k, wlines[k], mark))
        print()
