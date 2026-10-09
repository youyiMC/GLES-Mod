#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Show the FULL glslang errors for Sable's own shader, then decide.

The first `sable_audit.py` run reported 11/11 problems, but every file in
sable-src/ is a Veil `#include` FRAGMENT or a Flywheel override fragment:
no `#version`, usually no `main()`, and it references uniforms/functions defined
by the file that includes it. glslang therefore CANNOT type-check them in
isolation, and the errors are very likely harness artifacts, not converter bugs.

This prints the complete error text (not truncated) plus the corresponding
converted source line, so the call can be made from evidence instead of from the
error count. Same discipline as the Veil investigation, where my first harness
also produced dozens of phantom failures.

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
TMP = os.path.join(HERE, ".cache", "sable")

GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

TARGETS = [
    ("sable_pinwheel_shaders_include_fancy_sublevel_vertex.glsl", "frag"),
    ("flywheel_flywheel_light_flat.glsl", "frag"),
    ("flywheel_flywheel_internal_api_impl.frag", "frag"),
]


def main():
    for name, stage in TARGETS:
        p = os.path.join(TMP, name + ".raw.conv")
        print("=" * 78)
        print(name)
        print("=" * 78)
        if not os.path.isfile(p):
            print("  missing", p)
            continue
        r = subprocess.run([GLSLC, "--target-env=opengl",
                            "-fshader-stage=" + stage, p, "-o", p + ".spv"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        errs = [l.rstrip() for l in (r.stderr or "").splitlines()
                if "error" in l.lower()]
        lines = io.open(p, encoding="utf-8",
                        errors="replace").read().splitlines()
        for e in errs[:6]:
            print("  ERR: %s" % e[:200])
            m = re.search(r":(\d+):", e)
            if m:
                n = int(m.group(1))
                for k in range(max(0, n - 2), min(len(lines), n + 1)):
                    mark = " <<<" if k == n - 1 else ""
                    print("       %4d | %s%s" % (k + 1, lines[k][:130], mark))
        print("  (%d error lines total)" % len(errs))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
