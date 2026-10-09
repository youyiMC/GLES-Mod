#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Is the `06_raw.frag` failure NEW, or was it only MASKED before?

Context: fixing the `vec2 vec2(light);` corruption (which had made
flywheel_material_default_embedded.vert fail with `syntax error` on device)
changed the gate output. The vertex dump now PASSES, but the fragment dump
reports 8 errors that were previously hidden behind the syntax error.

This compares:
  * the 10/5 output  (produced BEFORE today's fixes)
  * today's output
for both the vertex and the fragment dumps, and reports the verdict of each.

If the 10/5 fragment output also fails, the 8 errors are a pre-existing defect
that the syntax error used to hide -- not a regression introduced today.

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

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

# The corruption this session fixed: an integer LHS given a float constructor,
# and a struct member turned into `vec2 vec2(name);`
BAD_PATTERNS = [
    ("int-LHS + float-ctor",
     re.compile(r"\b(?:ivec[234]|uvec[234]|int|uint)\s+\w+\s*=\s*"
                r"(?:vec[234]|float)\s*\(")),
    ("struct member corrupted",
     re.compile(r"^\s*(?:vec[234]|float|int|uint)\s+(?:vec[234]|float)\s*\(")),
]

PAIRS = [
    ("VERTEX  old(10/5)", "04_raw.reconv.vert", "vert"),
    ("VERTEX  now",       "04_raw.fixed.vert",  "vert"),
    ("FRAGMENT old(10/5)", "06_raw.reconv.frag", "frag"),
    ("FRAGMENT now",       "06_raw.fixed.frag",  "frag"),
]


def glslang(path, stage):
    r = subprocess.run([GLSLC, "--target-env=opengl", "-fshader-stage=" + stage,
                        path, "-o", path + ".spv"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        if ln.strip().split() and ln.strip().split()[0].isdigit() and \
                "generated" in ln:
            continue
        errs.append(ln.strip())
    return errs


def main():
    for label, name, stage in PAIRS:
        p = os.path.join(DUMPS, name)
        if not os.path.isfile(p):
            print("%-20s MISSING %s" % (label, name))
            continue
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        bad = []
        for tag, rx in BAD_PATTERNS:
            n = len(rx.findall(txt))
            if n:
                bad.append("%s x%d" % (tag, n))
        errs = glslang(p, stage)
        print("%-20s errors=%d   corruption: %s"
              % (label, len(errs), ", ".join(bad) if bad else "none"))
        for e in errs[:3]:
            print("        %s" % e[:150])
    return 0


if __name__ == "__main__":
    sys.exit(main())
