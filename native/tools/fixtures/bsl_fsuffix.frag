#version 120

// 复现 BSL deferred1.fsh 在真机上的 3 个错误
//   167:  'assign' : cannot convert from '4-component vector of float'
//                        to 'in 3-component vector of float'
//   1212: '+' : left 'float', right 'const int'
//   1492: '*' : left 'const float', right 'uniform int'
//
// 三个都涉及**带 f 后缀的浮点字面量**（BSL 全篇都这么写）。
uniform int isEyeInWater;
uniform int maxSamples;
uniform vec3 weatherCold;
uniform vec3 weatherRain;
uniform float weatherWeight;
uniform float visibility;
uniform vec3 lightCol;
uniform float timeAngle;
in vec3 colorIn;
in float planeDifference;
in float sampleLength;

// 167 的形态：全局变量与函数形参【同名】。
// 转换器会把全局初始化器搬进函数体，若不做「形参遮蔽」检查，
// 就会在 CalcLightColor 里给 vec3 形参赋 vec4 值，真机报：
//   'assign' : cannot convert from '4-component vector of float'
//              to 'in 3-component vector of float'
vec4 weatherCol = mix(vec4(weatherRain, 1.0f), vec4(weatherCold, 1.0f) / max(weatherWeight, 1.0E-4f), weatherWeight);

vec3 CalcLightColor(vec3 sun, vec3 night, vec3 weatherCol) {
    // 形参 weatherCol 遮蔽了全局 weatherCol，这里绝不能被注入全局赋值
    return mix(night, sun, weatherCol.x) * weatherCol;
}

void main() {
    vec3 color = colorIn;

    // 1212 的形态：int(...) 里 float + int
    int samples = int(min(planeDifference / sampleLength, float(maxSamples)) + 1);

    // 1492 的形态：const float * uniform int
    color += 0.25f * lightCol * visibility * (1.0f + 0.25f * isEyeInWater);

    // 167 的调用点
    color += CalcLightColor(vec3(1.0f), vec3(0.1f), weatherCol.rgb) * (timeAngle * 0.0f + 1.0f);

    gl_FragColor = vec4(color, float(samples));
}
