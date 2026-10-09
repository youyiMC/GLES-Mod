#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find which Minecraft classes use the constant 34049 (0x8501 = GL_TEXTURE_LOD_BIAS)
and print the surrounding bytecode, so we can tell:

  - whether the driver rejection is harmless (MC sets a value we can just drop), or
  - whether MC depends on the LOD bias actually taking effect.

Correction note: 34049 is GL_TEXTURE_LOD_BIAS, NOT GL_UNPACK_ROW_LENGTH.
GL_UNPACK_ROW_LENGTH is 0x0CF2 (3314). An earlier note of mine had this wrong;
the bundled gl.xml is the authority here.

Self-locating.
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

home = os.path.expanduser("~")
cands = []
for pat in (r"%s\.gradle\caches\**\neoforge-*-merged.jar" % home,
            r"%s\.gradle\caches\neoformruntime\**\*merged*.jar" % home,
            r"%s\.gradle\caches\neoformruntime\**\recompile_*.jar" % home,
            "build/moddev/artifacts/neoforge-*-merged.jar"):
    cands.extend(glob.glob(pat, recursive=True))
cands = [c for c in sorted(set(cands)) if os.path.getsize(c) > 5_000_000]
if not cands:
    print("no merged MC jar found")
    sys.exit(1)

jar = cands[-1]
print("jar:", os.path.basename(jar), "(%.1f MB)" % (os.path.getsize(jar) / 1e6))

NEEDLE = (34049).to_bytes(4, "big")
TEX_HINTS = (b"texParameter", b"TexParameter")

tmp = tempfile.mkdtemp(prefix="e34049_")
hits = []
with zipfile.ZipFile(jar) as z:
    for n in z.namelist():
        if not n.endswith(".class"):
            continue
        try:
            data = z.read(n)
        except Exception:
            continue
        if NEEDLE not in data:
            continue
        if not any(h in data for h in TEX_HINTS):
            continue
        hits.append(n)

print("引用 34049 且涉及 texParameter 的类: %d" % len(hits))
for h in hits:
    print("   ", h)

print()
print("=" * 74)
print("反汇编上下文")
print("=" * 74)

for n in hits:
    with zipfile.ZipFile(jar) as z:
        outp = os.path.join(tmp, os.path.basename(n))
        with open(outp, "wb") as fh:
            fh.write(z.read(n))
    cls = n[:-6].replace("/", ".")
    env = dict(os.environ)
    env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"
    r = subprocess.run(
        [JAVAP, "-J-Duser.language=en", "-c", "-p", "-cp", tmp, cls],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=180)
    lines = (r.stdout or r.stderr or "").splitlines()
    print()
    print("-" * 74)
    print(cls, "   (%d lines)" % len(lines))
    print("-" * 74)
    shown = 0
    for i, ln in enumerate(lines):
        if "34049" in ln:
            lo, hi = max(0, i - 10), min(len(lines), i + 6)
            for k in range(lo, hi):
                mark = " <<<" if k == i else ""
                print("  %5d| %s%s" % (k, lines[k], mark))
            print()
            shown += 1
            if shown >= 4:
                print("  ... (more occurrences omitted)")
                break
    if shown == 0:
        print("  (no 34049 literal found in disassembly; may be in a constant pool only)")
