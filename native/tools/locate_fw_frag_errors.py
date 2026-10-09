#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate the 8 remaining GLSL ES errors in the Flywheel fragment dump.

glslc reports `12:4: error: ...` -- but the file is full of `#line 0 N // file`
directives, so "line 12" refers to a LOGICAL line inside one of Flywheel's own
source files, not to line 12 of the dump.

This resolves each reported line through the `#line` map and prints the actual
offending text, so the defect can be named precisely instead of guessed.

LGPL-3.0-or-later
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DUMPS = os.path.join(HERE, ".cache", "fw_dumps")
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
TARGET = os.path.join(DUMPS, "06_raw.fixed.frag")

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

LINE_RX = re.compile(r"^#line\s+(\d+)\s+(\d+)\s*(?://\s*(.*))?$")


def logical_map(lines):
    """physical line index (0-based) -> (logical_line, origin_file)."""
    m = {}
    cur_file = "?"
    cur_log = 0
    for i, l in enumerate(lines):
        mm = LINE_RX.match(l.strip())
        if mm:
            cur_log = int(mm.group(2))
            if mm.group(3):
                cur_file = mm.group(3).strip()
            continue
        m[i] = (cur_log, cur_file)
        cur_log += 1
    return m


def main():
    txt = io.open(TARGET, encoding="utf-8", errors="replace").read()
    lines = txt.splitlines()
    lmap = logical_map(lines)

    r = subprocess.run([GLSLC, "--target-env=opengl", "-fshader-stage=frag",
                        TARGET, "-o", TARGET + ".spv"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        errs.append(ln.strip())

    print("errors: %d" % len(errs))
    print()
    # glslc prints the physical line of the file it read; recover it from the
    # "  12:4: error: ..." prefix.
    seen = set()
    for e in errs:
        m = re.match(r"^\s*(\d+):(\d+):\s*error:\s*(.*)$", e)
        print("  %s" % e[:150])
        if not m:
            continue
        phys = int(m.group(1)) - 1
        # walk back to the nearest known physical line
        p = phys
        while p > 0 and p not in lmap:
            p -= 1
        if p in lmap:
            log, origin = lmap[p]
            key = (origin, log)
            if key in seen:
                continue
            seen.add(key)
            print("        -> %s : logical line %d" % (origin, log))
            for k in range(phys, min(len(lines), phys + 3)):
                print("           | %s" % lines[k][:140])
    return 0


if __name__ == "__main__":
    sys.exit(main())
