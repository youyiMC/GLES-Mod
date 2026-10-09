#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_device_evidence.py -- pull the decisive lines out of native.log.

Why Python instead of PowerShell: native.log is UTF-8, and Windows PowerShell
5.1's Get-Content decodes with the ANSI codepage (GBK on zh-CN) unless told
otherwise. That silently breaks every Chinese needle, which is exactly the
kind of "looks like absent, actually present" trap this project keeps hitting.

What this extracts, in order of importance:
  1. Every DISTINCT texture-allocation rejection, with its full parameters.
     The probe prints these from the custom glTexImage2D/glTexStorage2D, after
     draining the error queue, so they are correctly attributed.
  2. Every line our glCheckFramebufferStatus diagnostic emitted.
  3. The GL_EXTENSIONS / GL_NUM_EXTENSIONS proof lines.
  4. Whether eglGetProcAddress was obtained (vs the dlsym fallback).

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import re
import sys
from collections import OrderedDict

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LOG = ROOT / "native.log"


def main() -> int:
    if not LOG.exists():
        print(f"missing: {LOG}", file=sys.stderr)
        return 2

    text = LOG.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    print(f"native.log : {LOG.stat().st_size} bytes, {len(lines)} lines")
    print()

    # 1. distinct texture rejection fingerprints -------------------------
    print("=" * 78)
    print(" 1) DISTINCT texture-allocation rejections (probe, queue drained)")
    print("=" * 78)
    seen: "OrderedDict[str, int]" = OrderedDict()
    for i, ln in enumerate(lines, 1):
        if "★" in ln and "拒绝" in ln:
            # keep the part from the star onward; strip the trailing hint text
            star = ln.index("★")
            body = ln[star:]
            body = body.split("——")[0].strip()
            if body not in seen:
                seen[body] = i
    if not seen:
        print("  (none)")
    for body, ln in seen.items():
        print(f"  L{ln}: {body}")
    print()

    # 2. our FBO diagnostic ----------------------------------------------
    print("=" * 78)
    print(" 2) glCheckFramebufferStatus diagnostic output")
    print("=" * 78)
    n = 0
    for i, ln in enumerate(lines, 1):
        if "FBO" in ln:
            print(f"  L{i}: {ln.strip()[:300]}")
            n += 1
            if n >= 15:
                print("  ... (truncated)")
                break
    if n == 0:
        print("  (none)")
    print()

    # 3. extension-list proof --------------------------------------------
    print("=" * 78)
    print(" 3) extension-list handling (proves the glGetString / count fix ran)")
    print("=" * 78)
    n = 0
    for i, ln in enumerate(lines, 1):
        if "GL_NUM_EXTENSIONS" in ln or "扩展列表含" in ln:
            print(f"  L{i}: {ln.strip()[:260]}")
            n += 1
            if n >= 6:
                break
    if n == 0:
        print("  (none)")
    print()

    # 4. eglGetProcAddress -------------------------------------------------
    print("=" * 78)
    print(" 4) eglGetProcAddress acquisition")
    print("=" * 78)
    n = 0
    for i, ln in enumerate(lines, 1):
        if "eglGetProcAddress" in ln:
            print(f"  L{i}: {ln.strip()[:260]}")
            n += 1
            if n >= 6:
                break
    if n == 0:
        print("  (none)")
    print()

    # 5. depth-format translation ----------------------------------------
    print("=" * 78)
    print(" 5) depth-format translation events (glTexImage2D / glTexStorage2D)")
    print("=" * 78)
    n = 0
    for i, ln in enumerate(lines, 1):
        if "深层格式已翻译" in ln or "DEPTH_COMPONENT" in ln:
            print(f"  L{i}: {ln.strip()[:260]}")
            n += 1
            if n >= 8:
                break
    if n == 0:
        print("  (none)")
    print()

    # 6. how many times each storage function was actually invoked --------
    print("=" * 78)
    print(" 6) storage-function invocation counts (from trace lines)")
    print("=" * 78)
    for fn in ("glTexImage2D", "glTexImage3D", "glTexStorage2D", "glTexStorage3D",
               "glFramebufferTexture2D", "glCheckFramebufferStatus", "glDrawBuffers"):
        c = text.count(fn)
        print(f"  {fn:28s} {c}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
