#version 120

// 真机 BSL v10.1.8 deferred1.fsh 的第 2 个错误：
//     ERROR: 0:939: '*' :  wrong operand types  no operation '*' exists that
//           takes a left-hand operand of type 'const float' and a right operand
//           of type 'uniform int'
// 来源：shaders/lib/atmospherics/sunmoon.glsl 第 126 行
//     color += 0.25 * lightCol * visibility * (1.0 + 0.25 * isEyeInWater);
// `isEyeInWater` 是 uniform int，`0.25 * isEyeInWater` 是 float * int。
//
// 注意：变量必须写成**函数内局部变量**。早先版本把 color/lightCol 写成
// `varying`，在片元着色器里 varying 是只读输入，赋值会报
// `l-value required`，与要测的问题无关。
uniform int isEyeInWater;
uniform int worldTime;
uniform int moonPhase;
uniform float rainStrength;

void main() {
    vec3 color = vec3(0.0);
    vec3 lightCol = vec3(1.0);
    float visibility = 1.0;

    // 主目标：const float * uniform int
    color += 0.25 * lightCol * visibility * (1.0 + 0.25 * isEyeInWater);
    // 同一族的其它方向
    color *= 1.0 - float(worldTime) * 0.001;
    color += vec3(rainStrength * float(worldTime));
    color += vec3(1.0 - moonPhase);
    color = vec3(isEyeInWater) * 0.5;

    gl_FragColor = vec4(color, 1.0);
}
