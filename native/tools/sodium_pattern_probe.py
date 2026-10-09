#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe GLSL ES 3.20 rules for the *exact* patterns Sodium's chunk shaders use.

These come from Sodium 0.8.13's chunk_vertex.glsl / block_layer_opaque.vsh:
    uvec3 _get_relative_chunk_coord(uint pos) {
        return uvec3(pos) >> uvec3(5u, 0u, 2u) & uvec3(7u, 3u, 7u);
    }
    vec3 _get_draw_translation(uint pos) {
        return _get_relative_chunk_coord(pos) * vec3(16.0);
    }
    vec3 position = _vert_position + translation;
    gl_Position = u_ProjectionMatrix * u_ModelViewMatrix * vec4(position, 1.0);

Key question: is `uvec3 * vec3` legal in ES 3.20? And does our converter
need to rewrite function-call results / constructors (not just variables)?

Empirical answer via glslang (NDK glslc).
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   ".cache", "sodpattern")
os.makedirs(TMP, exist_ok=True)

PRELUDE = """#version 320 es
precision highp float;
precision highp int;
"""

CASES = {
    # 1. uvec3 (function result) * vec3  -- Sodium's _get_draw_translation shape
    "01_uvec3_fn_times_vec3": PRELUDE + """
uvec3 _get_relative_chunk_coord(uint pos) {
    return uvec3(pos) >> uvec3(5u, 0u, 2u) & uvec3(7u, 3u, 7u);
}
void main() {
    uint d = 3u;
    vec3 t = _get_relative_chunk_coord(d) * vec3(16.0);
    gl_Position = vec4(t, 1.0);
}
""",

    # 2. same but explicitly converted -- expected to be the fix
    "02_fixed_vec3_cast": PRELUDE + """
uvec3 _get_relative_chunk_coord(uint pos) {
    return uvec3(pos) >> uvec3(5u, 0u, 2u) & uvec3(7u, 3u, 7u);
}
void main() {
    uint d = 3u;
    vec3 t = vec3(_get_relative_chunk_coord(d)) * vec3(16.0);
    gl_Position = vec4(t, 1.0);
}
""",

    # 3. uvecN constructor * float vector
    "03_uvec_ctor_times_vec3": PRELUDE + """
void main() {
    uint d = 3u;
    vec3 t = uvec3(d) * vec3(16.0);
    gl_Position = vec4(t, 1.0);
}
""",

    # 4. uint scalar * vec3
    "04_uint_scalar_times_vec3": PRELUDE + """
uniform uint u_RegionID;
void main() {
    vec3 t = u_RegionID * vec3(16.0);
    gl_Position = vec4(t, 1.0);
}
""",

    # 5. shift + and on uvec (must stay untouched -- valid in ES)
    "05_uvec_shift_and": PRELUDE + """
void main() {
    uint pos = 1234u;
    uvec3 r = uvec3(pos) >> uvec3(5u, 0u, 2u) & uvec3(7u, 3u, 7u);
    gl_Position = vec4(vec3(r), 1.0);
}
""",

    # 6. texelFetch on isamplerBuffer (Sodium's u_SectionTimeInfo)
    "06_isamplerbuffer": PRELUDE + """
precision highp isamplerBuffer;
uniform isamplerBuffer u_SectionTimeInfo;
uniform uint u_RegionID;
void main() {
    int chunkFade = texelFetch(u_SectionTimeInfo, int(u_RegionID)).r;
    gl_Position = vec4(float(chunkFade));
}
""",

    # 7. #line directives preserved verbatim (Sodium inserts them when
    #    expanding includes; rewriting the line number broke things before)
    "07_line_directive": PRELUDE + """
#line 0 1
in vec3 a_Position;
#line 3 0
void main() { gl_Position = vec4(a_Position, 1.0); }
""",

    # 8. std140 block containing bool (Sodium's u_Globals.u_UseRGSS)
    "08_std140_bool": PRELUDE + """
layout(std140) uniform u_Globals {
    mat4 u_ProjectionMatrix;
    vec4 u_FogColor;
    bool u_UseRGSS;
};
void main() { gl_Position = u_ProjectionMatrix * vec4(0.0); }
""",

    # 9. integer literal suffixes must not be rewritten (20u, 1u<<BITS)
    "09_uint_literals": PRELUDE + """
const uint POSITION_BITS      = 20u;
const uint POSITION_MAX_COORD = 1u << POSITION_BITS;
const float VERTEX_SCALE = 32.0 / float(POSITION_MAX_COORD);
void main() { gl_Position = vec4(VERTEX_SCALE); }
""",
}

SPV_NOISE = ("requires location for user input/output", "requires layout(binding",
             "non-opaque uniform", "for Vulkan",
             "non-opaque uniforms outside a block")


def run(name, src, verbose=False):
    path = os.path.join(TMP, name + ".vert")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)
    r = subprocess.run(
        [GLSlC, "--target-env=opengl", "-fshader-stage=vert", path, "-o",
         path + ".spv"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if verbose:
        return r.returncode, (r.stderr or "")
    msgs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        if ln.strip().startswith("ERROR: ") and any(n in ln for n in SPV_NOISE):
            continue
        # drop the pure "N errors generated" banner
        if ln.strip().split()[0].isdigit() and "generated" in ln:
            continue
        msgs.append(ln.split(": error: ")[-1].strip())
    return r.returncode, msgs


print("GLSL ES 3.20 rules for Sodium chunk-shader patterns")
print("=" * 72)
for name, src in CASES.items():
    rc, msgs = run(name, src)
    verdict = "PASS" if rc == 0 else "FAIL"
    print("%-28s %s" % (name, verdict))
    if rc != 0:
        # show the raw stderr so nothing is hidden by the noise filter
        _, raw = run(name, src, verbose=True)
        for ln in raw.splitlines():
            if ln.strip():
                print("      %s" % ln.strip()[:170])
    for m in msgs:
        print("      %s" % m)
print()
print("temp:", TMP)
