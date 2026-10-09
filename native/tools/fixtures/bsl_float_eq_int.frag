#version 330 core
// BSL 020_terrain_translucent.fsh 的真机 3092 行形态：
//   if (cloudBlendOpacity == 0) discard;
// cloudBlendOpacity 是 float、0 是 int -> `float == int`。
// 情形 C 显式排除了 '=' 与 '!'（为避开 == / !=），
// 于是 == / != 的「float 在左、int 在右」方向从未被覆盖。
out vec4 fragColor;
uniform float op;

void main() {
    float cloudBlendOpacity = op;
    if (cloudBlendOpacity == 0) {
        discard;
    }
    fragColor = vec4(cloudBlendOpacity);
}
