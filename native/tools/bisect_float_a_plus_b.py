#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal reproducer for the `float(a) + b` corruption.

`int f(int a, int b) { return a + b; }` is used to survive the converter
untouched, but in a larger file it comes out as `float(a) + b` -- which is
invalid ES (float + int). The A/B build (rule R on/off) shows identical output
for that line, so rule R is NOT the cause; this script exists to pin down which
*other* ingredient triggers it, so the finding can be recorded honestly.

LGPL-3.0-or-later
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, ".cache", "veil")
CLI = os.path.join(T, "cli.exe")

BASE = """#version 330 core
out vec4 fragColor;
%s
void main() {
    fragColor = vec4(%s, 0.0, 0.0, 1.0);
}
"""

CASES = {
    "01_alone":
        ("int i1(int a, int b) { return a + b; }",
         "float(i1(4, 5))"),
    "02_plus_float_param_fn":
        ("int i1(int a, int b) { return a + b; }\n"
         "float f1(float x) { return x / 16.0; }",
         "float(i1(4, 5)) + f1(3)"),
    "03_plus_vec_fn":
        ("int i1(int a, int b) { return a + b; }\n"
         "vec2 v1(ivec2 p) { return vec2(p) / 16.0; }",
         "float(i1(4, 5)) + v1(ivec2(9)).x"),
    "04_plus_uint_fn":
        ("int i1(int a, int b) { return a + b; }\n"
         "float u1(uint n) { return float(n) / 16.0; }",
         "float(i1(4, 5)) + u1(2)"),
    "05_three_param_fn":
        ("float m2(int a, int b, float g) { return float(a) / 16.0 + float(b) + g; }\n"
         "int i1(int a, int b) { return a + b; }",
         "m2(7, 8, 0.5) + float(i1(4, 5))"),
}


def main():
    for name, (decls, expr) in CASES.items():
        src = BASE % (decls, expr)
        p = os.path.join(T, "bis_auth_%s.frag" % name)
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
        out = p + ".out"
        subprocess.run([CLI, p, "fragment", out], capture_output=True)
        txt = io.open(out, encoding="utf-8", errors="replace").read()
        bad = "float(a)" in txt or "float(b)" in txt
        print("%-24s %s" % (name, "BROKEN  ->  " + 
              [l.strip() for l in txt.splitlines() if "return" in l and "a + b" in l or
               "float(a)" in l][0][:60] if bad else "ok"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
