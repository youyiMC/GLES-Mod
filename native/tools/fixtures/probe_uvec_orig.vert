#version 320 es
precision highp float;
precision highp int;
layout(location = 0) in uvec2 a_TexCoord;
layout(location = 0) out vec2 v;
const uint M = 15u;
void main() {
    v = vec2(a_TexCoord & M) / 16.0;
    gl_Position = vec4(0.0);
}
