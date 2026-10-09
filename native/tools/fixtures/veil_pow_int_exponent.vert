#version 330 core
// Iris "Veil" compatibility shader (from device native.log, stage=vertex).
// The pack's own code is already ES-clean: it writes `pow(clamp(x,0.0,1.0), 3)`.
// The bug is ours: the bare `3` was float-converted to `3.0`, and on a
// vector-typed base `pow(vec, float)` has no overload in GLSL ES.
uniform float VeilBlockFaceBrightness[6];
vec4 minecraft_light_dir(vec3 normal) {
    return vec4(1.0);
}
float block_brightness(vec3 worldNormal) {
    float darkFromD = pow(clamp(-worldNormal.y, 0.0, 1.0), 3) * VeilBlockFaceBrightness[0];
    float darkFromU = pow(clamp(worldNormal.y, 0.0, 1.0), 3) * VeilBlockFaceBrightness[1];
    float darkFromN = pow(clamp(-worldNormal.z, 0.0, 1.0), 2) * VeilBlockFaceBrightness[2];
    return darkFromD + darkFromU + darkFromN;
}
void main() {
    gl_Position = minecraft_light_dir(vec3(0.0, 1.0, 0.0)) * block_brightness(vec3(0.0, 1.0, 0.0));
}
