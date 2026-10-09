#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the proposed converter fix: injecting default precision
qualifiers for all sampler types in BOTH stages.

Checks:
  1. "declare all sampler precisions" compiles cleanly under #version 320 es
     (for types it declares but does not use).
  2. A Sodium-like vertex shader (isamplerBuffer + texelFetch) FAILS before
     the fix and PASSES after.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "fixtest")
os.makedirs(TMP, exist_ok=True)

# The full list our probe found to require explicit precision.
SAMPLER_PRECISION = [
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

PREC_BLOCK = "".join("precision highp %s;\n" % t for t in SAMPLER_PRECISION)

# Sodium 0.8.13 block_layer_opaque.vsh, reduced to the parts that matter.
SODIUM_VSH_BODY = """
layout(std140) uniform u_Globals {
    mat4 u_ProjectionMatrix;
    mat4 u_ModelViewMatrix;
    vec4 u_FogColor;
    vec2 u_EnvironmentFog;
    vec2 u_RenderFog;
    vec2 u_TexelSize;
    vec2 u_TexCoordShrink;
    float u_FadePeriodInv;
    bool u_UseRGSS;
};
uniform isamplerBuffer u_SectionTimeInfo;
uniform sampler2D u_LightTex;
uniform vec3 u_RegionOffset;
uniform int u_CurrentTime;
uniform uint u_RegionID;

layout(location = 0) out vec4 v_Color;
layout(location = 1) out vec2 v_TexCoord;
layout(location = 2) out vec2 v_FragDistance;
layout(location = 3) out float fadeFactor;

vec3 _get_relative_chunk_coord(uint pos) {
    return vec3(uvec3(pos) >> uvec3(5u, 0u, 2u) & uvec3(7u, 3u, 7u));
}
void main() {
    uint _draw_id = 3u;
    vec3 translation = u_RegionOffset + _get_relative_chunk_coord(_draw_id) * vec3(16.0);
    vec3 position = vec3(1.0, 2.0, 3.0) + translation;
    v_FragDistance = vec2(length(position));
    int chunkFade = texelFetch(u_SectionTimeInfo, int(_draw_id)).r;
    fadeFactor = (chunkFade < 0) ? 1.0 : 0.5;
    gl_Position = u_ProjectionMatrix * u_ModelViewMatrix * vec4(position, 1.0);
    v_Color = vec4(1.0) * texture(u_LightTex, vec2(0.5));
    v_TexCoord = vec2(0.5);
}
"""

CASES = {
    "before_vertex": "#version 320 es\n" + SODIUM_VSH_BODY,
    "after_vertex": "#version 320 es\n" + PREC_BLOCK + SODIUM_VSH_BODY,
    "precblock_only": "#version 320 es\n" + PREC_BLOCK +
                      "void main(){ gl_Position = vec4(0.0); }\n",
}

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")


def run(name, src, stage="vert"):
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
        low = ln.lower()
        if "error" not in low:
            continue
        if any(n in ln for n in SPV_NOISE) or "errors generated" in low:
            continue
        if ln.strip().startswith("ERROR: ") and any(n in ln for n in SPV_NOISE):
            continue
        msgs.append(ln.split(": error: ")[-1].strip())
    return r.returncode, msgs


for name, src in CASES.items():
    rc, msgs = run(name, src)
    print("=" * 72)
    print("%-20s rc=%d  %s" % (name, rc, "PASS" if rc == 0 else "FAIL"))
    print("=" * 72)
    for m in msgs:
        print("   ", m)
    if rc == 0:
        print("    (clean)")

print()
print("temp dir:", TMP)
