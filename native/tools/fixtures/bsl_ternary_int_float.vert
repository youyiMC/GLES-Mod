#version 330 core
// BSL hand_cutout.vsh（真机导出 031_hand_cutout.vsh）第 81/94 行的真实形态。
//
// 【重要：源文件里两侧都是整数，本来就是合法的！】
//     isMainHand = float(gl_Position.x * (isRightHanded ? 1 : -1) > 0.0f);
//
// 但转换器逐字面量处理时：
//   * 右操作数 `-1` 左侧是一元负号 `-`，命中规则 B（算术操作数）被浮点化；
//   * `1` 两侧是 `?` 和 `:`，不是算术也不是 vecN 实参，没有任何规则碰它。
// 输出因此变成 `isRightHanded ? 1 : -1.0` —— **转换器自己制造了**
// 三元两侧类型不一致。GLSL ES 规范 5.9 要求条件表达式两分支类型一致
// （桌面 GLSL 会自动把 int 提升为 float，ES 不提升），驱动于是报：
//   ':' : no operation ':' exists that takes a left-hand operand of
//         type 'const int' and a right operand of type 'const float'
//
// 因此规则 L 必须是**后置**的：等所有逐字面量规则跑完、看到最终文本，
// 再把整数一侧补成浮点，使两侧一致。
//
// 说明：gl_Position 是内建变量，不能当局部变量重新声明，否则 fixture
// 自己就不合法（那会掩盖转换器的效果），这里用普通变量模拟。
uniform mat4 gbufferModelView;
in vec3 Position;
uniform bool isRightHanded;
out float outMainHand;

void main() {
    vec4 glpos = gbufferModelView * vec4(Position, 1.0f);
    float isMainHand;
    isMainHand = float(glpos.x * (isRightHanded ? 1 : -1) > 0.0f);
    outMainHand = isMainHand;
}
