#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_global_initializer.py -- does GLSL ES allow a global variable to be
initialized from a non-constant expression, and at which version?

Why: the device (Adreno, ES 3.2) rejects Iris's injected line
    iris_FogParameters irisInt_Fog = iris_FogParameters(iris_FogColor,
        iris_FogDensity, iris_FogStart, iris_FogEnd,
        1.0 / (iris_FogEnd - iris_FogStart));
with
    'iris_FogColor' : Only consts can be used in a global initializer

Desktop GLSL allows this. Whether ES allows it, and from which version, decides
whether the fix is "emit a higher #version" or "rewrite the construct".

This script asks glslang (the same front end the NDK ships, and the same one
already used as this project's source of truth for GLSL rules) rather than
relying on recollection. It tests every ES version with the exact construct, in
a struct form and in a plain form.

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

GLSLC = pathlib.Path(
    r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
)

# Unexpected diagnostic text that comes from the SPIR-V back end, not from GLSL
# semantics. glslc always emits SPIR-V, so these must be filtered out or every
# shader looks like it failed (a trap this project has recorded before).
SPIRV_NOISE = (
    "SPIR-V",
    "requires location",
    "layout(binding",
    "layout(location",
    "non-opaque uniform",
    "Vulkan",
    "for Vulkan",
)

CASES = {
    "struct global init from uniforms":
        """
        uniform vec4 iris_FogColor;
        uniform float iris_FogDensity;
        uniform float iris_FogStart;
        uniform float iris_FogEnd;
        struct iris_FogParameters {
            vec4 color; float density; float start; float end; float scale;
        };
        iris_FogParameters irisInt_Fog = iris_FogParameters(iris_FogColor,
            iris_FogDensity, iris_FogStart, iris_FogEnd,
            1.0 / (iris_FogEnd - iris_FogStart));
        out vec4 fragColor;
        void main() { fragColor = irisInt_Fog.color; }
        """,
    "plain float global init from uniform":
        """
        uniform float u;
        float g = u * 2.0;
        out vec4 fragColor;
        void main() { fragColor = vec4(g); }
        """,
    "non-const global, no initializer (expect OK everywhere)":
        """
        uniform float u;
        float g;
        out vec4 fragColor;
        void main() { g = u * 2.0; fragColor = vec4(g); }
        """,
}

VERSIONS = ["300 es", "310 es", "320 es"]


def compile_one(version: str, body: str) -> tuple[bool, str]:
    src = f"#version {version}\nprecision highp float;\n{body}\n"
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "t.frag"
        p.write_text(src, encoding="utf-8")
        out = pathlib.Path(td) / "t.spv"
        r = subprocess.run(
            [str(GLSLC), "--target-env=opengl", "-fshader-stage=frag",
             str(p), "-o", str(out)],
            capture_output=True, text=True,
        )
    errs = []
    for ln in (r.stdout + r.stderr).splitlines():
        if any(n in ln for n in SPIRV_NOISE):
            continue
        if "error" in ln.lower():
            errs.append(ln.strip())
    return (r.returncode == 0 and not errs), " | ".join(errs)


def main() -> int:
    if not GLSLC.exists():
        print(f"glslc not found: {GLSLC}", file=sys.stderr)
        return 2

    print("=" * 78)
    print(" global-initializer rule by GLSL ES version (adjudicated by glslang)")
    print("=" * 78)
    for name, body in CASES.items():
        print(f"\n  case: {name}")
        for v in VERSIONS:
            ok, msg = compile_one(v, body)
            tag = "ACCEPTED" if ok else "REJECTED"
            print(f"    #version {v:8s} -> {tag}" + (f"   {msg}" if msg else ""))
    print()

    print("=" * 78)
    print(" INTERPRETATION")
    print("=" * 78)
    print("  If the struct case is REJECTED at every ES version, then raising")
    print("  #version cannot fix it: the construct itself must be rewritten.")
    print("  The rewrite that preserves semantics is to keep the declaration at")
    print("  global scope (without initializer) and perform the assignment at")
    print("  the top of each function that reads the variable -- or, when the")
    print("  value is only read in main(), only there.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
