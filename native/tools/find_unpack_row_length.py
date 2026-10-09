#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find which Minecraft classes call glPixelStorei with GL_UNPACK_ROW_LENGTH
(0x8501 = 34049), because the Adreno driver rejects that pname on GLES and
MC logs it 70 times per run.

The question that matters is not "is the log noisy" but
"does MC RELY on the row length being applied?"

  - If MC only ever sets it to 0 (the default), the setter is a no-op and the
    driver message is harmless.
  - If MC sets a non-zero value and then uploads a texture whose rows are
    padded, GLES would read the pixels with the wrong stride and silently
    corrupt the texture. That would be a real correctness bug.

This tool disassembles candidates and prints the surrounding bytecode so the
constant can be judged in context.

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
print("jar:", jar, "(%.1f MB)" % (os.path.getsize(jar) / 1e6))

# 34049 (0x8501) as a big-endian constant in the class constant pool
NEEDLE = (34049).to_bytes(4, "big")

tmp = tempfile.mkdtemp(prefix="rowlen_")
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
        # only classes that also touch pixel store / texture upload
        if b"pixelStore" not in data and b"glPixelStorei" not in data:
            continue
        hits.append(n)

print("candidates referencing 34049 + pixelStore: %d" % len(hits))
for h in hits:
    print("   ", h)

# Extract and disassemble the interesting ones
print()
print("=" * 74)
print("反汇编上下文（判断它把 UNPACK_ROW_LENGTH 设成什么）")
print("=" * 74)
for n in hits[:6]:
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
    lines = (r.stdout or "").splitlines()
    print()
    print("-" * 74)
    print(cls)
    print("-" * 74)
    shown = 0
    for i, ln in enumerate(lines):
        if "34049" in ln or "8501" in ln:
            lo, hi = max(0, i - 8), min(len(lines), i + 9)
            for k in range(lo, hi):
                mark = " <<<" if k == i else ""
                print("  %5d| %s%s" % (k, lines[k], mark))
            print()
            shown += 1
            if shown >= 3:
                break
    if shown == 0:
        print("  (no 34049 literal in disassembly)")
