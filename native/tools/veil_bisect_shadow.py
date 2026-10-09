#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bisect WHY `ivec2 uv` is not treated as an int identifier.

`scan_int_idents` is supposed to add any name following `int` / `ivec2` / ...
regardless of scope, so `ivec2 uv` should be in the table. Yet the small
shadowing probe shows `uv / 256.0` is left unwrapped while `coord / 256.0` (a
uniquely-named ivec2) IS wrapped.

This tries a few variants to find the trigger.

LGPL-3.0-or-later
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, ".cache", "veil")
os.makedirs(T, exist_ok=True)
CLI = os.path.join(T, "cli.exe")

HEAD = """#version 330 core
out vec4 fragColor;
"""

VARIANTS = {
    # baseline: unique int name -> expect vec2(coord)
    "01_unique_ivec2":
        "vec2 b(ivec2 coord) { return coord / 256.0; }\n"
        "void main() { fragColor = vec4(b(ivec2(0)), 0.0, 0.0, 1.0); }\n",

    # same name, but ONLY ever declared as ivec2
    "02_ivec2_only":
        "vec2 b(ivec2 uv) { return uv / 256.0; }\n"
        "void main() { fragColor = vec4(b(ivec2(0)), 0.0, 0.0, 1.0); }\n",

    # vec2 declared FIRST (in another function), then ivec2
    "03_vec2_then_ivec2":
        "vec2 a(vec2 uv) { return uv / 256.0; }\n"
        "vec2 b(ivec2 uv) { return uv / 256.0; }\n"
        "void main() { fragColor = vec4(a(vec2(0.0)) + b(ivec2(0)), 0.0, 0.0, 1.0); }\n",

    # ivec2 declared FIRST, then vec2
    "04_ivec2_then_vec2":
        "vec2 b(ivec2 uv) { return uv / 256.0; }\n"
        "vec2 a(vec2 uv) { return uv / 256.0; }\n"
        "void main() { fragColor = vec4(a(vec2(0.0)) + b(ivec2(0)), 0.0, 0.0, 1.0); }\n",

    # float local named uv, then ivec2 param named uv
    "05_local_float_then_ivec2":
        "float g() { float uv = 1.0; return uv / 256.0; }\n"
        "vec2 b(ivec2 uv) { return uv / 256.0; }\n"
        "void main() { fragColor = vec4(b(ivec2(0)) + g(), 0.0, 0.0, 1.0); }\n",
}


def main():
    for name, body in VARIANTS.items():
        src = HEAD + body
        p = os.path.join(T, "bisect_%s.frag" % name)
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
        out = p + ".out"
        subprocess.run([CLI, p, "fragment", out], capture_output=True)
        txt = io.open(out, encoding="utf-8", errors="replace").read()
        body_out = [l for l in txt.splitlines()
                    if "/ 256.0" in l or "vec2(b" in l or "return" in l and "uv" in l]
        print("%-26s %s" % (name, " | ".join(s.strip() for s in body_out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
