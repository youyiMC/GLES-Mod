#!/usr/bin/env python3
"""
从 FML 早期显示窗口的着色器源码推算报错行号，用于判断转换器是否生效。

【背景】

真机启动失败时，日志里只有驱动给出的编译错误：

    VertexShader linkage failure.
    ERROR: 0:12: '*' : wrong operand types  no operation '*' exists that takes
                   a left-hand operand of type '2-component vector of float' and
                   a right operand of type 'const int'
    ERROR: 0:12: '-' : wrong operand types ...
    ERROR: 2 compilation errors.  No code generated.

单看这段文本无法判断问题出在哪，因为 GLSL ES 1.00 与 ES 3.00+ 都「能」
编译 vec2 * int —— 区别在于前者非法、后者合法。于是有两种可能：

  a) 转换器没生效，源码原样给了驱动，驱动按默认版本（ES 1.00）解析
  b) 转换器生效了，但产出的 #version 指令被忽略/无效，仍按 ES 1.00 解析

两者修法完全不同，必须区分。

【本脚本的判定方法】

行号是可计算的指纹。GLSL 编译器报的行号以「送入驱动的源码」为准：

  转换器未生效 -> 源码原样 -> 报错行号 = 原始源码里的行号
  转换器生效   -> 输出多了 #version 与 precision 行，行号必然后移

因此：

  报错行号 == 原始源码行号  => 源码未经转换（情形 a）
  报错行号 != 原始源码行号  => 经过了转换（情形 b）

本脚本把两种情况的行号都算出来，与真机报的 0:12 对照即可定论。

用法：
    py native/tools/analyze_shader_line.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------
# FML 顶点着色器原文
#
# 逐字节抄自 net.neoforged.fancymodloader:earlydisplay:4.0.43 的
# net/neoforged/fml/earlydisplay/ElementShader.java（glShaderSource 的文本块）。
#
# Java 文本块会保留源码里的换行与缩进，并在 """ 之后立即开始内容，
# 因此第一个字符就是换行 —— 这一行为对行号计算至关重要，不能省略。
# ---------------------------------------------------------------------
FML_VERTEX_SOURCE = (
    "\n"
    "                         #version 150 core\n"
    "                         in vec2 position;\n"
    "                         in vec2 tex;\n"
    "                         in vec4 colour;\n"
    "                         uniform vec2 screenSize;\n"
    "                         out vec2 fTex;\n"
    "                         out vec4 fColour;\n"
    "                         void main() {\n"
    "                             fTex = tex;\n"
    "                             fColour = colour;\n"
    "                             gl_Position = vec4((position/screenSize) * 2 - 1, 0.0, 1.0);\n"
    "                         }\n"
)

# 真机上驱动报告的错误行号（1-based，来自 latest(1).log）
DEVICE_ERROR_LINE = 12

# 报错表达式所在的源码片段。用它定位「原始源码里是哪一行」，
# 避免手工数行出错。
MARKER = "gl_Position = vec4((position/screenSize) * 2 - 1, 0.0, 1.0);"


def find_marker_line(text: str) -> int:
    """返回 MARKER 在 text 中的 1-based 行号；找不到返回 -1。

    行号按「送入编译器的源码」计算。GLSL 编译器把第一个字符视为 0 行，
    因此源码第一行对应报错里的 0；这里的返回值同样按 0 起算，
    以便与驱动输出直接比较。
    """
    for idx, line in enumerate(text.split("\n")):
        if MARKER in line:
            return idx
    return -1


def main() -> int:
    raw_line = find_marker_line(FML_VERTEX_SOURCE)

    # 模拟转换器的输出：它会在最前面加入 #version 与 precision 行。
    # 这里只关心行数变化，因此用等量的占位行表示。
    converted_prefix_lines = 1      # "#version 320 es"
    converted = "\n".join(["#version 320 es"] * converted_prefix_lines
                          + FML_VERTEX_SOURCE.split("\n"))
    conv_line = find_marker_line(converted)

    print("=== 报错行号推算 ===")
    print(f"驱动报告的错误行  : 0:{DEVICE_ERROR_LINE}")
    print()
    print(f"情形 a) 转换器未生效，源码原样送入驱动")
    print(f"        表达式位于   : 0:{raw_line}")
    print()
    print(f"情形 b) 转换器生效，输出前面多了 #version 行")
    print(f"        表达式位于   : 0:{conv_line}")
    print()

    if raw_line == DEVICE_ERROR_LINE and conv_line != DEVICE_ERROR_LINE:
        verdict = ("结论: 属于情形 a —— 源码未经转换就送到了驱动。\n"
                   "      转换器（glShaderSource 钩子）没有被调用，"
                   "应排查本库是否在调用路径上。")
        rc = 0
    elif conv_line == DEVICE_ERROR_LINE and raw_line != DEVICE_ERROR_LINE:
        verdict = ("结论: 属于情形 b —— 源码经过了转换，但产出的 #version 无效。\n"
                   "      应检查转换器输出的 #version 拼写与位置。")
        rc = 0
    else:
        verdict = ("结论: 无法判定（两种情形的行号相同或都不匹配）。\n"
                   "      需要开启 GLESMOD_SHADER_PROBE=1 直接比对源码。")
        rc = 1

    print(verdict)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
