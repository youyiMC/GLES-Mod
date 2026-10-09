#version 120

// Fixture modelled on the failure signatures reported by the device for BSL's
// deferred1.fsh. Each construct below corresponds to a distinct diagnostic:
//
//   Only consts can be used in a global initializer   -> sunVec / upVec / timeAngle ...
//   int / const float                                  -> f0 / c
//   assign: cannot convert from 'const int' to 'float'  -> f2
//   float - uniform int                                -> f1 / a
//   const float + const int                            -> f3
//   int / const float (const int left)                  -> f4
//
// The point is to measure how far our converter gets, not to reproduce BSL
// exactly: the constructs are what matter.

uniform vec3 sunPosition;
uniform vec3 upPosition;
uniform int moonPhase;
uniform int worldTime;
uniform sampler2D colortex0;

vec3 sunVec = normalize(sunPosition);
vec3 upVec = normalize(upPosition);
float timeAngle = worldTime / 24000.0;
float nightMult = 1.0 - moonPhase;
float lightMorning = 1.0 - timeAngle;
float lightDay = 1.0 - lightMorning;

const int SHADOW_RES = 2048;

float f0 = 1 / 2.0;
float f1 = 3.0 - moonPhase;
float f2 = SHADOW_RES;
float f3 = min(1.0, timeAngle + 1);
float f4 = SHADOW_RES / 2.0;

float helper() {
    return 3.0 - worldTime;
}

void main() {
    float a = 3.0 - worldTime;
    float b = SHADOW_RES * 2.0;
    float c = 1 / 2.0;
    // 比较的【操作数】类型不一致：float < const int。
    // 真机报 '0:453: '<' : no operation '<' exists that takes a left-hand
    // operand of type 'float' and a right operand of type 'const int''。
    // 注意不能写成 `float d = a < SHADOW_RES;` —— 那是 bool 赋给 float，
    // 桌面 GLSL 同样不允许，会让本夹具失去“桌面合法”的前提。
    float d = 0.0;
    if (a < SHADOW_RES) {
        d = 1.0;
    }
    gl_FragColor = vec4(a + b + c + d + helper(), f2, f3, texture2D(colortex0, vec2(0.5)).r);
}
