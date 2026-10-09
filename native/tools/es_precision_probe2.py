#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extended ES precision probe: which types need an explicit default precision
qualifier in GLSL ES 3.20, for BOTH stages — including scalars (float/int/uint)
so we know whether the fragment stage needs more than float+int.

Also verifies our current converter output shape compiles for a
Sodium-0.8.13-like vertex + fragment pair.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "prec2")
os.makedirs(TMP, exist_ok=True)

SCALARS = ["float", "int", "uint"]

SAMPLERS = [
    "sampler2D", "sampler3D", "samplerCube", "sampler2DArray",
    "samplerCubeArray",
    "sampler2DShadow", "samplerCubeShadow", "sampler2DArrayShadow",
    "samplerCubeArrayShadow",
    "samplerBuffer", "sampler2DMS", "sampler2DMSArray",
    "isampler2D", "isampler3D", "isamplerCube", "isampler2DArray",
    "isamplerCubeArray", "isamplerBuffer", "isampler2DMS", "isampler2DMSArray",
    "usampler2D", "usampler3D", "usamplerCube", "usampler2DArray",
    "usamplerCubeArray", "usamplerBuffer", "usampler2DMS", "usampler2DMSArray",
]

# Declare the type as a uniform (scalars and samplers alike).
VS = "#version 320 es\nuniform %s u_T;\nvoid main(){ gl_Position = vec4(0.0); }\n"
FS = ("#version 320 es\nout vec4 o_Color;\nuniform %s u_T;\n"
      "void main(){ o_Color = vec4(0.0); }\n")

SPV_NOISE = ("requires location for user input/output", "requires layout(binding",
             "non-opaque uniform", "for Vulkan",
             "non-opaque uniforms outside a block")


def run(name, src, stage):
    ext = "vert" if stage == "vert" else "frag"
    path = os.path.join(TMP, "%s.%s" % (name, ext))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)
    r = subprocess.run(
        [GLSlC, "--target-env=opengl", "-fshader-stage=" + stage, path, "-o",
         path + ".spv"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    msgs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE) or "errors generated" in ln.lower():
            continue
        msgs.append(ln.split(": error: ")[-1].strip())
    return r.returncode, msgs


print("### 标量类型：是否需要显式默认精度 ###")
for stage, tmpl in (("vert", VS), ("frag", FS)):
    label = "顶点" if stage == "vert" else "片元"
    for t in SCALARS:
        rc, msgs = run("s_%s_%s" % (t, stage), tmpl % t, stage)
        needs = rc != 0 and any("precision" in m.lower() for m in msgs)
        verdict = "需要显式精度" if needs else ("有默认精度" if rc == 0 else
                                              "其他错误")
        print("  %-3s %-6s -> %s" % (label, t, verdict))
        if rc != 0 and not needs:
            print("        %s" % (msgs[0][:70] if msgs else ""))

print()
print("### 采样器类型：需要显式精度的清单 ###")
for stage, tmpl in (("vert", VS), ("frag", FS)):
    label = "顶点" if stage == "vert" else "片元"
    need = []
    for t in SAMPLERS:
        rc, msgs = run("t_%s_%s" % (t, stage), tmpl % t, stage)
        if rc != 0 and any("precision" in m.lower() for m in msgs):
            need.append(t)
    print("  %s: %d 个" % (label, len(need)))
    print("     %s" % ", ".join(need))
