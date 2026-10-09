#version 330 core
// BSL shadow.glsl:238 的真实形态：
//   varying float mat;
//   ...
//   int blockID = int(mc_Entity.x / 100);
//   mat = 0;
//   if (blockID == 201 || blockID == 202) mat = 1;
// 桌面 GLSL 允许 `float = int` 隐式转换，GLSL ES 不允许：
//   'assign' : cannot convert from 'const int' to 'float'
// 注意这条**不在** `float x = <int>;` 的位置，而是普通的赋值语句，
// 规则 D（要求字面量是整个右值且左侧是浮点声明）覆盖不到。
in vec2 mc_Entity;
uniform mat4 shadowModelViewInverse;
out float vmat;

void main() {
    int blockID = int(mc_Entity.x / 100);
    float mat = 0.0f;
    mat = 0;
    if (blockID == 201 || blockID == 202) mat = 1;
    if (blockID == 200 || blockID == 205) mat = 2;
    vmat = mat * (shadowModelViewInverse[0].x);
    gl_Position = vec4(mat);
}
