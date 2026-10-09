#version 330 core
// Sodium/vanilla fullscreen-blit vertex shader (from device native.log).
// `gl_VertexID & 1` is INTEGER bitwise.  Ours converted the right operand to
// a float, producing `gl_VertexID & 1.0` -- `&` has no float overload in
// GLSL ES, so the whole program fails.
out vec2 texCoord;
void main() {
    vec2 uv = vec2((gl_VertexID & 1), (gl_VertexID & 2));
    gl_Position = vec4(((uv * vec2(3.0)) - vec2(1.0)), 0.0, 1.0);
    texCoord = (uv * vec2(1.5));
}
