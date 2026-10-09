#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diff the device's RAW vs CONVERTED shader dump for the Flywheel program that
failed on device:

    11:09:22 [Render thread/ERROR] [flywheel/backend/]: Falling back
    Failed to compile pipeline/instancing/flywheel_instance_transformed/
                       flywheel_material_default_embedded.vert
    error: Syntax error: syntax error
    --> flywheel:internal/api_impl.glsl
    1 | struct FlwLightAo {
    2 |     vec2 light;
      |     ^^^^

`native.log` writes each dumped source line TWICE (a known artefact), so the
files are de-duplicated in adjacent pairs before diffing.

This answers the only question that matters: did OUR converter change the text
around `struct FlwLightAo`, or is the failure somewhere else entirely?

LGPL-3.0-or-later
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(ROOT, "fw-raw.txt")
CONV = os.path.join(ROOT, "fw-converted.txt")


def dedupe_pairs(lines):
    """native.log writes each line twice, adjacent. Collapse those."""
    out = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if i + 1 < len(lines) and lines[i + 1] == lines[i]:
            i += 2
        else:
            i += 1
    return out


def main():
    a = dedupe_pairs(io.open(RAW, encoding="utf-8", errors="replace")
                     .read().splitlines())
    b = dedupe_pairs(io.open(CONV, encoding="utf-8", errors="replace")
                     .read().splitlines())
    print("raw  lines: %d -> %d (deduped)" %
          (len(io.open(RAW, encoding="utf-8", errors="replace").read()
               .splitlines()), len(a)))
    print("conv lines: %d -> %d (deduped)" %
          (len(io.open(CONV, encoding="utf-8", errors="replace").read()
               .splitlines()), len(b)))

    # locate the struct that the driver complained about
    for tag, arr in (("RAW", a), ("CONV", b)):
        idx = [i for i, l in enumerate(arr) if "struct FlwLightAo" in l]
        print("%s: 'struct FlwLightAo' at %s" % (tag, idx))

    print()
    print("=" * 74)
    print("FULL diff: every line that differs between RAW and CONVERTED")
    print("=" * 74)
    import difflib
    ndiff = 0
    for line in difflib.unified_diff(a, b, "RAW", "CONVERTED",
                                     lineterm="", n=0):
        if line.startswith(("---", "+++")):
            continue
        print("  " + line[:170])
        ndiff += 1
    print()
    print("differing diff lines: %d" % ndiff)
    if ndiff == 0:
        print("=> converter produced IDENTICAL text: the failure is NOT ours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
