#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sable audit: run Sable's OWN GLSL through our converter and judge with glslang.

Why Sable is a fourth shader family
-----------------------------------
Already validated: MC core (125/125), BSL (174/182 baseline), Flywheel dumps
(PASS x2), Veil pinwheel (48/48).

Sable ships exactly ONE glsl of its own and OVERRIDES Flywheel's for the rest
(see sable-src/flywheel_explanation.md). Its reason is a "scene ID" added to
Flywheel's lighting storage/LUT/shaders.

What is different about Sable's own shader, and why that matters to us
--------------------------------------------------------------------
`fancy_sublevel_vertex.glsl` is bit-manipulation heavy:

    layout(location = 2) in uvec2 SableData;
    uint vertexIndex = uint(gl_VertexID) & 0x3u;
    uint xOffset = (SableData.y) & 0xFFu;
    uint ao = (SableData.y >> (24u + (vertexIndex << 1u))) & 0x3u;
    ivec2 UV2 = ivec2(packedLight & 0xF0u, (packedLight << 4) & 0xF0u);
    vec3 Position;                     // non-const GLOBAL, written in a function

Those are exactly the areas where our converter has historically been wrong
(int/uint mixing, uvec components, non-const globals, mixed-width shifts).

Method
------
These files are Veil `#include` fragments, not standalone units, and Sable has
no `#version` of its own. So for each file:
  * prepend `#version 330 core` (what Veil's ShaderVersionProcessor produces on
    our reported 3.2 caps)
  * run OUR converter
  * diff raw vs converted and flag the corruption shapes we have actually hit
    before (int-LHS + float ctor, struct member wrapped, uvec given vecN)
  * additionally run glslang on the converted text; when a file is a fragment
    (no main) glslang reports "Missing entry point" which we treat as N/A, not
    as a pass.

Reference-only: sable-src/ must never be committed (PolyForm Shield).

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
SRC = os.path.join(ROOT, "sable-src")
TMP = os.path.join(HERE, ".cache", "sable")
os.makedirs(TMP, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
CLI_SRC = os.path.join(HERE, "convert_shader_cli.c")
CLI_EXE = os.path.join(TMP, "cli.exe")
SHADER_C = os.path.join(ROOT, "native", "src", "shader.c")
INCLUDE = os.path.join(ROOT, "native", "include")

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

# Shapes that have actually broken on device for us. Reused verbatim so the
# judge stays consistent across Veil / Flywheel / Sable.
CORRUPTION = [
    ("int-LHS + float-ctor",
     re.compile(r"\b(?:ivec[234]|uvec[234]|int|uint)\s+\w+\s*=\s*"
                r"(?:vec[234]|float)\s*\(")),
    ("struct member wrapped",
     re.compile(r"^\s*(?:vec[234]|float|int|uint)\s+(?:vec[234]|float)\s*\(")),
    ("float() around a vector/uint expr",
     re.compile(r"\bfloat\s*\(\s*u?vec[234]\s*\(")),
]

# Fragments: no main() -> glslang "missing entry point" is expected, not a fail.
NO_MAIN_OK = True


def build_cli():
    r = subprocess.run([GCC, "-O1", "-std=c11", "-o", CLI_EXE, CLI_SRC,
                        SHADER_C, "-I", INCLUDE],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("CLI build FAILED:\n" + (r.stderr or ""))
        sys.exit(1)


def glslang(path, stage):
    r = subprocess.run([GLSLC, "--target-env=opengl",
                        "-fshader-stage=" + stage, path, "-o", path + ".spv"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        errs.append(ln.strip())
    return errs


def stage_of(name):
    if ".vert" in name or ".vsh" in name:
        return "vert", "vertex"
    if ".frag" in name or ".fsh" in name:
        return "frag", "fragment"
    # .glsl / .md -> includes, treat as fragment for type-checking purposes
    return "frag", "fragment"


def main():
    build_cli()
    files = sorted(f for f in os.listdir(SRC) if not f.endswith(".md"))
    print("sable-src files: %d" % len(files))
    print()

    ok = bad = na = 0
    for name in files:
        glslc_stage, cli_stage = stage_of(name)
        raw = os.path.join(TMP, name + ".raw")
        conv = raw + ".conv"
        text = io.open(os.path.join(SRC, name), encoding="utf-8",
                       errors="replace").read()
        if not text.lstrip().startswith("#version"):
            text = "#version 330 core\n" + text
        with io.open(raw, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

        subprocess.run([CLI_EXE, raw, cli_stage, conv], capture_output=True)
        if not os.path.isfile(conv):
            print("[CONVERTER CRASH] %s" % name)
            bad += 1
            continue
        ctext = io.open(conv, encoding="utf-8", errors="replace").read()

        found = []
        for tag, rx in CORRUPTION:
            if rx.search(ctext):
                found.append(tag)

        errs = glslang(conv, glslc_stage)
        missing_main = any("Missing entry point" in e or
                           "no main()" in e.lower() or
                           "Missing main" in e for e in errs)
        real = [e for e in errs
                if "Missing entry point" not in e and "no main()" not in e.lower()
                and "Missing main" not in e]

        if found:
            status = "CORRUPTED: " + ", ".join(found)
            bad += 1
        elif real:
            status = "%d GLSL ES error(s)" % len(real)
            bad += 1
        elif missing_main and NO_MAIN_OK:
            status = "fragment (no main) - converter clean"
            na += 1
        else:
            status = "PASS"
            ok += 1

        print("%-58s %s" % (name, status))
        for e in real[:3]:
            print("      %s" % e[:150])

    print()
    print("=" * 74)
    print("PASS=%d   fragment(no main)=%d   PROBLEM=%d" % (ok, na, bad))
    print("=" * 74)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
