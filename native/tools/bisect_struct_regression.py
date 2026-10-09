#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bisect the `uvec2 light = ... -> vec2(...)` regression seen on device.

Device facts (latest.log + fw-raw.txt/fw-converted.txt):
  RAW : uvec2 light = _flw_lightAt(sectionOffset, uvec3(...)); \\
  CONV: uvec2 light = vec2(_flw_lightAt(sectionOffset, uvec3(...))); \\
  -> type mismatch, Flywheel fell back to 'flywheel:off'
The whole statement sits inside a `#define` MACRO BODY, and `light` is ALSO a
struct member (`vec2 light;`) in the same translation unit.

Baseline fw220-conv.txt did NOT have the wrap, so it is a regression relative
to that snapshot.

Each case below adds one ingredient at a time so the trigger is identified by
evidence. Output line is the `uvec2 light = ...` text.

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

HEADER = "#version 330 core\nout vec4 fragColor;\n"

STRUCT = ("struct FlwLightAo {\n"
          "    vec2 light;\n"
          "    float ao;\n"
          "};\n")

DECL = "uvec2 _flw_lightAt(uint off, uvec3 p);\n"

CASES = {
    "01_plain": (
        DECL + """
void f() {
    uvec2 light = _flw_lightAt(0u, uvec3(1));
    fragColor = vec4(vec2(light).xy, 0.0, 1.0);
}
"""),
    "02_with_struct_member": (
        STRUCT + DECL + """
void f() {
    uvec2 light = _flw_lightAt(0u, uvec3(1));
    fragColor = vec4(vec2(light).xy, 0.0, 1.0);
}
"""),
    "03_in_macro": (
        DECL + """
void f() {
    uint lights[27];
    #define FETCH(i) { \\
        uvec2 light = _flw_lightAt(0u, uvec3(1)); \\
        lights[i] = light.x; \\
    }
    FETCH(0)
    fragColor = vec4(0.0);
}
"""),
    "04_macro_and_struct": (
        STRUCT + DECL + """
void f() {
    uint lights[27];
    #define FETCH(i) { \\
        uvec2 light = _flw_lightAt(0u, uvec3(1)); \\
        lights[i] = light.x; \\
    }
    FETCH(0)
    fragColor = vec4(0.0);
}
"""),
    "05_struct_member_vec2_only": (
        STRUCT + """
void f() {
    vec2 light = vec2(0.5);
    fragColor = vec4(light, 0.0, 1.0);
}
"""),
}


def main():
    for name, body in CASES.items():
        src = HEADER + body
        p = os.path.join(T, "bis_struct_%s.frag" % name)
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src)
        out = p + ".out"
        subprocess.run([CLI, p, "fragment", out], capture_output=True)
        txt = io.open(out, encoding="utf-8", errors="replace").read()
        hits = [l.strip() for l in txt.splitlines()
                if "uvec2 light" in l or "vec2 light" in l
                or "vec2 vec2" in l or "vec2(_flw_lightAt" in l]
        broken = any("vec2(_flw_lightAt" in h or "vec2 vec2" in h for h in hits)
        print("%-26s %s" % (name, "BROKEN" if broken else "ok"))
        for h in hits:
            print("        %s" % h[:110])
    return 0


if __name__ == "__main__":
    sys.exit(main())
