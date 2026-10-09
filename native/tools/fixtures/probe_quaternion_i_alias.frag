#version 330 core
out vec4 fragColor;

// REPRO for the current device failure:
//
//   Failed to compile pipeline/instancing/create_instance_rotating/
//                      flywheel_material_default_default.vert
//   error: no matching overloaded function found
//    --> flywheel:util/quaternion.glsl
//   21 |     vec3 i = q.xyz;
//   22 |     return v + 2.0 * cross(i, cross(i, v) + q.w * v);
//      |                      ^^^^^
//
// Flywheel's report shows ITS OWN source lines, so the caret tells us the type
// of `i` is wrong in OUR OUTPUT. `i` is a `vec3` here, but the same program has
// an `int i` elsewhere, so the name-keyed integer table says "i is an int" and
// 情形 F (int argument to a float-only builtin -- `cross` is in
// kStrictFloatFns) wraps it.
//
// Expected: `cross(i, ...)` must stay untouched.

struct FlwInstance {
    vec4 rotation;
};

// a function that makes `i` look like an int
int indexOf(float coord, float start) {
    int i = int(coord - start);
    return i;
}

vec3 rotateByQuaternion(vec3 v, vec4 q) {
    vec3 i = q.xyz;                                   // i is a VEC3 here
    return v + 2.0 * cross(i, cross(i, v) + q.w * v); // must not be wrapped
}

void main() {
    FlwInstance inst;
    inst.rotation = vec4(0.0, 0.0, 0.0, 1.0);
    vec3 r = rotateByQuaternion(vec3(0.5), inst.rotation);
    fragColor = vec4(r + vec3(float(indexOf(1.0, 0.0))), 1.0);
}
