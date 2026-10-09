#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-validate every shader that native.log marked as 编译失败, using glslang.

Now with correct de-duplication (position pairing -- see shader_from_log.py).

SPIR-V-only diagnostics are filtered: glslc targets SPIR-V, while the device
runs plain GLES, which does NOT require layout(location=...) on uniforms or
user in/out.  Treating those as failures would produce false "real error"
counts, which is exactly the trap this script exists to avoid.

Usage: py native\\tools\\revalidate_failed.py <log> [outdir]
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shader_from_log import (find_block, find_failing_shaders,  # noqa: E402
                             load_lines, write_src)

GLSLC = r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
"""
glslc emits diagnostics that only apply to SPIR-V generation.  The device runs
plain GLES, where none of these are required, so counting them as failures
would manufacture a large phantom bug list.  Each entry below was confirmed to
be SPIR-V-specific:

  layout(location=L) / non-opaque uniform variables
      SPIR-V requires an explicit location on every uniform and user in/out.
      GLES assigns them automatically.
  SPIR-V requires location for user input/output
      same rule, worded for in/out.
  not allowed when generating SPIR-V
      e.g. `shared` layout qualifier -- a compute-only qualifier.
  uniform/buffer blocks require layout(binding=X)
      SPIR-V requires explicit bindings; GLES does not.
"""
IGNORE = re.compile(
    r"layout\(location=L\)"
    r"|SPIR-V requires"
    r"|non-opaque uniform variables"
    r"|not allowed when generating SPIR-V"
    r"|uniform/buffer blocks require layout"
)

OUT = sys.argv[2] if len(sys.argv) > 2 else "shader_dump"
os.makedirs(OUT, exist_ok=True)

lines = load_lines(sys.argv[1])
fails = find_failing_shaders(lines)

seen = set()
uniq = []
for idx, sid, st in fails:
    if sid in seen:
        continue
    seen.add(sid)
    uniq.append((idx, sid, st))

real = []
ok = []
missing = []

for idx, sid, stage in uniq:
    data = find_block(lines, idx, "实际被送入驱动的源码（转换后）")
    if data is None:
        missing.append(sid)
        continue
    p = os.path.join(OUT, "r%d.%s" % (sid, stage))
    write_src(p, data)
    r = subprocess.run(
        [GLSLC, "--target-env=opengl", "-fshader-stage=" + stage, p,
         "-o", p + ".spv"],
        capture_output=True, text=True, errors="replace")
    errs = [ln for ln in (r.stdout + r.stderr).splitlines()
            if ": error:" in ln and not IGNORE.search(ln)]
    if errs:
        real.append((sid, stage, p, errs))
    else:
        ok.append((sid, stage))

print("=" * 74)
print(" distinct 'compile failure' entries : %d" % len(uniq))
print("   converted source compiles fine   : %d" % len(ok))
print("   REAL compile failures            : %d" % len(real))
print("   no converted block recorded      : %d %s" % (len(missing), missing))
print("=" * 74)
for sid, stage, p, errs in real:
    print("\n shader %d (%s)  <- %s" % (sid, stage, p))
    for e in errs[:8]:
        print("     " + e.strip())
