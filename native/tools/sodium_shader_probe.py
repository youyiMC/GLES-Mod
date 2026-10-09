#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce Sodium's chunk-shader compile failure locally with glslc/glslang.

Sodium 0.8.13's block_layer_opaque.vsh is a DESKTOP shader:
    #version 330
    #extension GL_ARB_separate_shader_objects : require
    ...
    layout(location = 0) out vec4 v_Color;

Our converter turns #version into `320 es` but does NOT touch #extension.
Test whether each element is legal in GLSL ES 3.20.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "sodtest")
os.makedirs(TMP, exist_ok=True)

CASES = {}

# A: exactly what we currently produce for Sodium's vsh
CASES["A_arb_ext_require"] = """
#version 320 es
#extension GL_ARB_separate_shader_objects : require
void main() { gl_Position = vec4(0.0); }
"""

# B: #extension removed, but keep layout(location) on an inter-stage output
CASES["B_noloc_ext"] = """
#version 320 es
layout(location = 0) out vec4 v_Color;
void main() { v_Color = vec4(1.0); gl_Position = vec4(0.0); }
"""

# C: same but without explicit location (baseline: must pass)
CASES["C_plain"] = """
#version 320 es
out vec4 v_Color;
void main() { v_Color = vec4(1.0); gl_Position = vec4(0.0); }
"""

# D: ES name with require -> should also be an error
CASES["D_es_ext_require"] = """
#version 320 es
#extension GL_EXT_foobar_not_real : require
void main() { gl_Position = vec4(0.0); }
"""

# E: unknown ext with enable -> warning only, should compile
CASES["E_es_ext_enable"] = """
#version 320 es
#extension GL_EXT_foobar_not_real : enable
void main() { gl_Position = vec4(0.0); }
"""

# F: Sodium-ish features: std140 block w/ bool, isamplerBuffer, uvec bit ops
CASES["F_sodium_features"] = """
#version 320 es
layout(std140) uniform u_Globals {
    mat4 u_ProjectionMatrix;
    vec4 u_FogColor;
    vec2 u_TexelSize;
    float u_FadePeriodInv;
    bool u_UseRGSS;
};
uniform isamplerBuffer u_SectionTimeInfo;
uniform sampler2D u_LightTex;
uvec3 _get_relative_chunk_coord(uint pos) {
    return uvec3(pos) >> uvec3(5u, 0u, 2u) & uvec3(7u, 3u, 7u);
}
void main() {
    uint _draw_id = 3u;
    vec3 t = vec3(_get_relative_chunk_coord(_draw_id)) * vec3(16.0);
    int chunkFade = texelFetch(u_SectionTimeInfo, int(_draw_id)).r;
    gl_Position = u_ProjectionMatrix * vec4(t, 1.0);
}
"""

ok = 0
fail = 0
for name, src in CASES.items():
    path = os.path.join(TMP, name + ".vsh")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src.lstrip("\n"))

    r = subprocess.run(
        [GLSlC, "--target-env=opengl", "-fshader-stage=vert", path, "-o",
         os.path.join(TMP, name + ".spv")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    err = (r.stderr or "").strip()
    # filter SPIR-V-only noise
    lines = []
    for ln in err.splitlines():
        low = ln.lower()
        if "spir-v" in low or "requires location" in low or "layout(binding" in low:
            continue
        if ln.strip().startswith("ERROR: ") or "error:" in low:
            lines.append(ln)
    real = [ln for ln in lines if "error" in ln.lower()]

    status = "FAIL" if r.returncode != 0 else "pass"
    print("=" * 70)
    print("%-24s rc=%d  %s" % (name, r.returncode, status))
    print("=" * 70)
    for ln in real:
        print("   ", ln)
    if r.returncode == 0 and not real:
        print("    (compiled clean)")
        ok += 1
    elif r.returncode != 0:
        fail += 1

print()
print("compiled-ok (rc==0): %d   failed: %d" % (ok, fail))
print("temp dir:", TMP)
