#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_converter_output.py -- show exactly what the shader converter emits.

Why: the host-side test suite reports errors like
    'fogValue' : undeclared identifier
    'leng' : undeclared identifier
inside text that comes from the EMBEDDED fog.glsl. Guessing at the cause is
wasteful; this prints the real output so the defect is visible.

It runs the same source through the same converter the build uses, so what is
printed here is what the driver would receive.

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "native" / "src"
TOOLS = ROOT / "native" / "tools"
GCC = r"C:\msys64\ucrt64\bin\gcc.exe"

# A minimal desktop-GLSL shader that exercises the embedded fog include path.
CASES = {
    "fog-include only (via #moj_import <fog.glsl>)": (
        "#version 150\n"
        "\n"
        "#moj_import <fog.glsl>\n"
        "\n"
        "in vec3 Position;\n"
        "out float vertexDistance;\n"
        "uniform int FogShape;\n"
        "void main() {\n"
        "    vertexDistance = fog_distance(Position, FogShape);\n"
        "    gl_Position = vec4(1.0);\n"
        "}\n"
    ),
    "plain global init from uniform": (
        "#version 150\n"
        "\n"
        "uniform vec4 fogColor;\n"
        "uniform float fogStart;\n"
        "uniform float fogEnd;\n"
        "struct Fog { vec4 c; float s; float e; };\n"
        "Fog theFog = Fog(fogColor, fogStart, fogEnd);\n"
        "out vec4 fragColor;\n"
        "void main() { fragColor = theFog.c; }\n"
    ),
    "two functions, global before both": (
        "#version 150\n"
        "\n"
        "uniform float u;\n"
        "float g = u * 2.0;\n"
        "float helper() { return g; }\n"
        "out vec4 fragColor;\n"
        "void main() { fragColor = vec4(helper()); }\n"
    ),
}


def build_cli() -> pathlib.Path:
    exe = pathlib.Path(tempfile.gettempdir()) / "glesmod_convert_cli.exe"
    r = subprocess.run(
        [GCC, "-O0", "-g",
         "-I", str(SRC),
         "-I", str(ROOT / "native" / "include"),
         "-o", str(exe),
         str(TOOLS / "convert_shader_cli.c"), str(SRC / "shader.c"), "-lm"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("build failed:\n" + r.stdout + r.stderr, file=sys.stderr)
        raise SystemExit(1)
    return exe


def main() -> int:
    exe = build_cli()
    print(f"converter built: {exe}")
    print()

    for name, body in CASES.items():
        with tempfile.TemporaryDirectory() as td:
            inp = pathlib.Path(td) / "in.vert"
            inp.write_text(body, encoding="utf-8")
            out = pathlib.Path(td) / "out.vert"
            r = subprocess.run([str(exe), str(inp), "vertex", str(out)],
                               capture_output=True, text=True)
        print("=" * 78)
        print(f" CASE: {name}")
        print("=" * 78)
        print("--- input ---")
        for i, ln in enumerate(body.splitlines(), 1):
            print(f"  {i:3d}| {ln}")
        print("--- output ---")
        if out.exists():
            txt = out.read_text(encoding="utf-8", errors="replace")
            for i, ln in enumerate(txt.splitlines(), 1):
                print(f"  {i:3d}| {ln}")
        else:
            print("  (no output file; rc=%d)" % r.returncode)
            if r.stderr.strip():
                print("  stderr: " + r.stderr.strip())
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
