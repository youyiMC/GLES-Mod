#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Determine, empirically via glslang (NDK glslc), which GLSL ES 3.20 sampler
types REQUIRE an explicit default precision qualifier in vertex / fragment
shaders.  This decides what our shader converter must inject.

Method: for each sampler type, compile a minimal shader that declares it with
NO precision qualifier.  rc!=0 => our converter must inject
`precision highp <type>;`.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "prectest")
os.makedirs(TMP, exist_ok=True)

TYPES = [
    "sampler2D", "sampler3D", "samplerCube", "sampler2DArray",
    "sampler2DShadow", "samplerCubeShadow", "sampler2DArrayShadow",
    "samplerCubeArrayShadow",
    "isampler2D", "isampler3D", "isamplerCube", "isampler2DArray",
    "usampler2D", "usampler3D", "usamplerCube", "usampler2DArray",
    "samplerBuffer", "isamplerBuffer", "usamplerBuffer",
    "sampler2DMS", "isampler2DMS", "usampler2DMS",
    "sampler2DMSArray", "isampler2DMSArray", "usampler2DMSArray",
    "samplerCubeArray", "isamplerCubeArray", "usamplerCubeArray",
]

VS = """#version 320 es
uniform %s u_T;
void main() { gl_Position = vec4(0.0); }
"""

FS = """#version 320 es
precision highp float;
precision highp int;
out vec4 o_Color;
uniform %s u_T;
void main() { o_Color = vec4(0.0); }
"""

# SPIR-V-specific complaints are artifacts of glslc always emitting SPIR-V.
SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")


def compile_shader(name, stage, src):
    ext = "vert" if stage == "vert" else "frag"
    path = os.path.join(TMP, "%s_%s.%s" % (name, stage, ext))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)

    r = subprocess.run(
        [GLSlC, "--target-env=opengl", "-fshader-stage=" + stage, path, "-o",
         path + ".spv"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    msgs = []
    for ln in (r.stderr or "").splitlines():
        if not ln.strip() or "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        if ln.strip().startswith("ERROR: ") and any(
                n in ln for n in SPV_NOISE):
            continue
        # drop the pure "N errors generated" banner
        if "errors generated" in ln:
            continue
        msgs.append(ln.strip().split(": error: ")[-1])
    return r.returncode, msgs


print("legend: OK = compiles without precision qualifier (has a default)")
print("        NEED = requires explicit precision qualifier")
print()

for stage, tmpl in (("vert", VS), ("frag", FS)):
    need = []
    ok = []
    print("=" * 74)
    print("STAGE: %s" % ("VERTEX" if stage == "vert" else "FRAGMENT"))
    print("=" * 74)
    for t in TYPES:
        rc, msgs = compile_shader(t, stage, tmpl % t)
        # Distinguish "needs precision" from "type unsupported in this stage"
        looks_prec = any("precision" in m.lower() for m in msgs)
        if rc != 0 and looks_prec:
            need.append(t)
            print("  NEED  %-24s %s" % (t, msgs[0][:70]))
        elif rc != 0:
            print("  OTHER %-24s rc=%d %s" % (t, rc, (msgs[0][:60] if msgs else "")))
        else:
            ok.append(t)
    print()
    print("  needs explicit precision (%d): %s" % (len(need), ", ".join(need)))
    print("  has default           (%d)" % len(ok))

print()
print("temp dir:", TMP)
