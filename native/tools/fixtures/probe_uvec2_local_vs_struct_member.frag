#version 330 core
out vec4 fragColor;

// REGRESSION probe: `uvec2 x = someFn();` must NOT be wrapped in vec2().
//
// Device evidence (latest.log, Flywheel instancing failed to compile):
//   RAW  : uvec2 light = _flw_lightAt(sectionOffset, uvec3(...));
//   CONV : uvec2 light = vec2(_flw_lightAt(sectionOffset, uvec3(...)));
//   -> 'uvec2' vs 'vec2' type mismatch -> Flywheel fell back to 'flywheel:off'
//
// The older baseline (fw220-conv.txt) kept this line untouched, so this is a
// regression introduced while fixing the cross-scope aliasing defects.
//
// Shape that matters:
//   * a STRUCT has a member named `light` of type vec2   -> puts `light` in fvecs
//   * elsewhere a LOCAL `uvec2 light` is declared        -> NOT collected into
//     ivecs, because collect_ivec_vars only collects at brace depth 0
//   => `light` looks like "a float vector" to 情形 B, but the local declaration
//      right here says uvec2.

struct FlwLightAo {
    vec2 light;          // <- struct MEMBER named light, type vec2
    float ao;
};

vec2 flw_lightAt() {     // returns vec2 (like Flywheel's _flw_lightAt)
    return vec2(0.5, 0.5);
}

void main() {
    // (1) int vector local from a vec2-returning call: must stay uvec2(...)
    uvec2 light = uvec2(flw_lightAt());

    // (2) control: a real float vector local SHOULD be wrapped when the rhs is
    //     an int vector. Use an obviously-int source so the intent is clear.
    ivec2 iv = ivec2(1, 2);
    vec2  fv = vec2(iv);

    // (3) control: struct member usage must keep working
    FlwLightAo s;
    s.light = vec2(0.25);

    fragColor = vec4(vec2(light).xy + fv + s.light, 0.0, 1.0);
}
