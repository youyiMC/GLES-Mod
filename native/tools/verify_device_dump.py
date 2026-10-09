#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ground truth: feed the DEVICE'S OWN raw dump back through the converter and
check the exact line that broke Flywheel on device.

Device evidence (latest.log 11:09:22):
    Failed to compile pipeline/instancing/.../flywheel_material_default_embedded.vert
    Flywheel backend fell back from 'flywheel:instancing' to 'flywheel:off'

Diffing the device's RAW vs CONVERTED dump showed exactly one bad rewrite:
    RAW : uvec2 light = _flw_lightAt(sectionOffset, uvec3(...)); \
    CONV: uvec2 light = vec2(_flw_lightAt(sectionOffset, uvec3(...))); \
   -> 'uvec2' cannot be initialised from 'vec2'

`native.log` writes every dumped line TWICE (adjacent), so the raw file is
de-duplicated before re-conversion -- otherwise the converter would see a
doubled source file.

LGPL-3.0-or-later
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
T = os.path.join(HERE, ".cache", "veil")
CLI = os.path.join(T, "cli.exe")
RAW = os.path.join(ROOT, "fw-raw.txt")
DEVICE_CONV = os.path.join(ROOT, "fw-converted.txt")

BAD = "vec2(_flw_lightAt"
GOOD = "uvec2 light = _flw_lightAt"

# The detector must be NARROW. Most `vec2 x = vec2(_flw_lightAt(...));` lines are
# CORRECT and were already in the known-good baseline (fw220-conv.txt line 697):
# `vec2 light000 = vec2(uvec2_expr)` is an explicit uvec2 -> vec2 conversion.
#
# The only genuinely broken shape is an INTEGER-vector left-hand side receiving a
# FLOAT-vector constructor:
#     uvec2 light = vec2(...);      // 'uvec2' cannot be initialised from 'vec2'
BAD_SHAPE = re.compile(
    r"\b(?:ivec[234]|uvec[234]|int|uint)\s+[A-Za-z_]\w*\s*=\s*"
    r"(?:vec[234]|float)\s*\(")


def dedupe_pairs(lines):
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if i + 1 < len(lines) and lines[i + 1] == lines[i]:
            i += 2
        else:
            i += 1
    return out


def main():
    raw = dedupe_pairs(io.open(RAW, encoding="utf-8", errors="replace")
                       .read().splitlines())
    src = os.path.join(T, "device_raw_dedup.vert")
    with io.open(src, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(raw) + "\n")
    print("device raw dump (deduped): %d lines -> %s" % (len(raw), src))

    out = os.path.join(T, "device_raw_reconv.vert")
    r = subprocess.run([CLI, src, "vertex", out],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("CONVERT FAILED rc=%d\n%s" % (r.returncode, r.stderr[:400]))
        return 1

    conv = io.open(out, encoding="utf-8", errors="replace").read()
    print()
    print("=== device's own CONVERTED dump (the broken build) ===")
    n_dev_bad = 0
    for i, l in enumerate(io.open(DEVICE_CONV, encoding="utf-8",
                                  errors="replace").read().splitlines(), 1):
        if BAD_SHAPE.search(l):
            print("  %5d | BROKEN  %s" % (i, l.strip()[:120]))
            n_dev_bad += 1
    print("  device build had %d integer-LHS / float-ctor lines" % n_dev_bad)

    print()
    print("=== our converter NOW, on the same raw input ===")
    hits_bad = 0
    for i, l in enumerate(conv.splitlines(), 1):
        if BAD_SHAPE.search(l):
            print("  %5d | BROKEN  %s" % (i, l.strip()[:120]))
            hits_bad += 1
        elif GOOD in l:
            print("  %5d | ok      %s" % (i, l.strip()[:120]))

    print()
    print("integer-LHS wrapped in a float ctor: before=%d  now=%d"
          % (n_dev_bad, hits_bad))
    if hits_bad == 0:
        print("=> the device regression is FIXED")
    return 1 if hits_bad else 0


if __name__ == "__main__":
    sys.exit(main())
