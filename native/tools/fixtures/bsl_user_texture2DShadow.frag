#version 330 core
// BSL 007_basic.fsh 的真实形态：光影包自定义了一个叫 texture2DShadow 的辅助函数。
// 桌面 GLSL 上这没问题，但我们的替换表会把这个【函数名】也改成 texture，
// 于是产出同名于内建函数的定义，并让函数体内的裸调用变成自递归。
// 驱动报：can't redefine/overload built-in functions + Has recursive call chain
uniform sampler2DShadow shadowtex0;
uniform float gradNoise;
out vec4 fragColor;

float texture2DShadow(sampler2DShadow shadowtex, vec3 shadowPos) {
    return vec4(texture(shadowtex, shadowPos)).x;
}

float sampleShadow(vec3 shadowPos) {
    return texture2DShadow(shadowtex0, vec3(shadowPos.st, shadowPos.z));
}

void main() {
    float acc = 0.0;
    for (int i = 0; i < 4; i++) {
        float dist = (i + gradNoise) / 12.0f;
        acc += dist + sampleShadow(vec3(0.0, 0.0, dist));
    }
    fragColor = vec4(acc);
}
