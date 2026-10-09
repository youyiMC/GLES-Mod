#version 330 core

// ===========================================================================
// 本文件是 Engine-Room/Flywheel 的**逐字副本**（verbatim copy）。
//
//   上游: https://github.com/Engine-Room/Flywheel
//   路径: assets/flywheel/flywheel/internal/diffuse.glsl
//   许可: MIT License
//   版权: Copyright (c) 2021-2024 Jozufozu
//
// MIT 允许再分发，条件是**保留版权声明与许可全文**。以下为完整许可文本：
//
//   Copyright (c) 2021-2024 Jozufozu
//
//   Permission is hereby granted, free of charge, to any person obtaining
//   a copy of this software and associated documentation files (the
//   "Software"), to deal in the Software without restriction, including
//   without limitation the rights to use, copy, modify, merge, publish,
//   distribute, sublicense, and/or sell copies of the Software, and to
//   permit persons to whom the Software is furnished to do so, subject to
//   the following conditions:
//
//   The above copyright notice and this permission notice shall be
//   included in all copies or substantial portions of the Software.
//
//   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
//   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
//   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
//   NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
//   LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
//   OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
//   WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//
// 【为何放在本仓库】作为回归夹具，用于验证转换器对
//   `min(n2.x + n2.y * (3. + normal.y) + n2.z, 1.)` 这类
//   「整数字面量 3. 的简写 + 向量成员运算」的处理。它曾经触发过真机缺陷。
// ===========================================================================
float diffuse(vec3 normal) {
    vec3 n2 = normal * normal * vec3(.6, .25, .8);
    return min(n2.x + n2.y * (3. + normal.y) + n2.z, 1.);
}

float diffuseNether(vec3 normal) {
    vec3 n2 = normal * normal * vec3(.6, .9, .8);
    return min(n2.x + n2.y + n2.z, 1.);
}

in vec3 v_Normal;

out vec4 fragColor;

void main() {
    fragColor = vec4(vec3(diffuse(v_Normal) + diffuseNether(v_Normal)), 1.0);
}
