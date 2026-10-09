#version 330 core
// Probe: name REUSE across functions with DIFFERENT types, plus int-ctor wrapping.
//
// Found in Veil's own include chain (veil:space_helper + veil:light):
//
//   veil:space_helper : vec4 screenToWorldSpace(vec2 uv, float depth) {...}
//   veil:light        : vec2 minecraft_sample_lightmap_coords(ivec2 uv) {
//                           return clamp(uv / 256.0, vec2(...), vec2(...));
//                       }
//
// GLSL scopes parameters to their function, so this is legal on desktop.
// If our int-identity table is keyed by NAME ONLY (flat, not per-scope), the
// earlier `vec2 uv` claims the name and the later `ivec2 uv` is treated as
// float, so `uv / 256.0` is never wrapped and GLSL ES rejects it:
//     '/' : no operation '/' exists that takes a left-hand operand of type
//           'in highp 2-component vector of int' and a right operand of
//           'const float'
//
// A main() is REQUIRED: without an entry point glslang stops at
// "Missing entry point" and never type-checks the rest.

out vec4 fragColor;

// (a) float-typed uv -> must stay unwrapped
vec2 a(vec2 uv) {
    return uv / 256.0;
}

// (b) int-typed uv -> MUST become vec2(uv) / 256.0
vec2 b(ivec2 uv) {
    return uv / 256.0;
}

// (c) control: differently-named int param (known to work)
vec2 c(ivec2 coord) {
    return coord / 256.0;
}

// (d) int-typed uv in a LATER function, after (a) already claimed the name
vec2 d(ivec2 uv) {
    ivec2 q = uv + ivec2(1);
    return q / 256.0;
}

// (e) int ctor as an arithmetic operand: must NOT be wrapped
vec2 e(ivec2 uv) {
    return vec2(uv + ivec2(1));
}

void main() {
    fragColor = vec4(a(vec2(0.0)) + b(ivec2(0)) + c(ivec2(0))
                   + d(ivec2(0)) + e(ivec2(0)), 0.0, 1.0);
}
