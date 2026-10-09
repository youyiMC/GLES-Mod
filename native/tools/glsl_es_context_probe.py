#!/usr/bin/env python3
"""
用 glslc（glslang）实测 GLSL ES 到底允许哪些隐式转换。

【为什么需要这个脚本】

转换器的每条改写规则，本质都是在回答「GLSL ES 会不会接受这种写法」。
此前这些答案来自记忆和试错 —— 结果是每轮真机测试只能发现一类新错误，
代价是一轮几分钟的真机往返。

NDK 自带了 glslc，其前端就是 glslang —— 一套真实的 GLSL ES 类型检查器。
于是可以把每个「转换语境」写成最小着色器，让编译器直接给出裁决。
这样得到的是一张【实测表】，而不是推测。

【用法】
    py glsl_es_context_probe.py [--glslc <路径>] [--version 320]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_GLSLC = (
    r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
)

# glslc 总是产出 SPIR-V，SPIR-V 的附加约束与本调查无关，必须过滤
SPIRV_NOISE = (
    "SPIR-V requires location for user input/output",
    "requires layout(binding=X)",
    "non-opaque uniform variables need a layout(location=L)",
    "non-opaque uniforms outside a block",
    "not allowed when using GLSL for Vulkan",
    "SPIR-V requires explicitly",
    "can only be used in SPIR-V",
)
SUMMARY_RE = re.compile(r"^\d+\s+errors?\s+generated\.?$")

# (编号, 说明, 期望, 着色器主体)
#
# 期望值只是【记录先验认知】，脚本不会因不符而失败 ——
# 它的职责是如实报告编译器裁决，先验正确与否由结果本身揭示。
CASES: list[tuple[str, str, str, str]] = [
    # ---- 标量 int / float ----
    ("S1", "float 变量 = int 变量（赋值）", "允许?",
     "uniform int i; void main(){ float f; f = i; gl_Position = vec4(f); }"),
    ("S2", "float 变量 = int 变量（声明初始化）", "允许?",
     "uniform int i; void main(){ float f = i; gl_Position = vec4(f); }"),
    ("S3", "int 变量 + float 字面量（二元运算）", "禁止?",
     "uniform int i; void main(){ float f = i + 1.0; gl_Position = vec4(f); }"),
    ("S4", "int 字面量 + float 字面量", "允许?",
     "void main(){ float f = 1 + 1.0; gl_Position = vec4(f); }"),
    ("S5", "float(i + 1)，i 为 int —— float() 是转换构造", "允许",
     "uniform int i; void main(){ float f = float(i + 1); gl_Position = vec4(f); }"),
    ("S6", "float(1)，整数字面量直接入 float()", "允许",
     "void main(){ float f = float(1); gl_Position = vec4(f); }"),
    ("S7", "int 变量 == float 字面量（比较）", "禁止?",
     "uniform int i; void main(){ float f = (i == 0.0) ? 1.0 : 0.0; gl_Position = vec4(f); }"),
    ("S8", "int 变量 == int 字面量（比较）", "允许",
     "uniform int i; void main(){ float f = (i == 0) ? 1.0 : 0.0; gl_Position = vec4(f); }"),

    # ---- 向量 int / float ----
    ("V1", "vec2 变量 = ivec2 变量（赋值）—— 真机报错的情形", "禁止",
     "in ivec2 UV2; out vec2 tc; void main(){ tc = UV2; gl_Position = vec4(0.0); }"),
    ("V2", "vec2 变量 = ivec2 变量（声明初始化）", "禁止?",
     "in ivec2 UV2; out vec2 tc; void main(){ vec2 v = UV2; tc = v; gl_Position = vec4(0.0); }"),
    ("V3", "ivec2 变量 / float 字面量 —— 真机报错的情形", "禁止",
     "in ivec2 UV2; out vec2 tc; void main(){ tc = UV2 / 256.0; gl_Position = vec4(0.0); }"),
    ("V4", "vec2(ivec2 变量) —— 转换构造", "允许",
     "in ivec2 UV2; out vec2 tc; void main(){ tc = vec2(UV2); gl_Position = vec4(0.0); }"),
    ("V5", "ivec2 变量 * float 字面量", "禁止?",
     "in ivec2 UV2; out vec2 tc; void main(){ tc = UV2 * 0.5; gl_Position = vec4(0.0); }"),
    ("V6", "vec2 构造实参里的整数字面量 vec2(0, 0)", "允许?",
     "out vec2 tc; void main(){ tc = vec2(0, 0); gl_Position = vec4(0.0); }"),
    ("V7", "vec4 构造实参里的整数字面量 vec4(1,1,1,1)", "允许?",
     "out vec4 c; void main(){ c = vec4(1, 1, 1, 1); gl_Position = vec4(0.0); }"),
    ("V8", "ivec2 变量 + ivec2 字面量（整数向量运算）", "允许",
     "in ivec2 UV2; out ivec2 o; void main(){ o = UV2 + ivec2(1, 1); gl_Position = vec4(0.0); }"),
    ("V9", "ivec2 变量作为 vec2 形参的实参", "禁止?",
     "in ivec2 UV2; out vec2 tc;"
     "vec2 passthru(vec2 v){ return v; }"
     "void main(){ tc = passthru(UV2); gl_Position = vec4(0.0); }"),
    ("V10", "浮点函数返回整数变量", "禁止?",
     "in ivec2 UV2; out vec2 tc;"
     "vec2 passthru2(){ return UV2; }"
     "void main(){ tc = passthru2(); gl_Position = vec4(0.0); }"),

    # ---- 函数实参的标量情形 ----
    ("F1", "float 形参 ← int 字面量实参", "禁止?",
     "out float o; void g(float x){ o = x; } void main(){ g(1); gl_Position = vec4(0.0); }"),
    ("F2", "float 形参 ← int 变量实参", "禁止?",
     "uniform int i; out float o; void g(float x){ o = x; }"
     "void main(){ g(i); gl_Position = vec4(0.0); }"),
    ("F3", "int 形参 ← float 字面量实参", "禁止",
     "out float o; void g(int x){ o = float(x); }"
     "void main(){ g(1.0); gl_Position = vec4(0.0); }"),

    # ---- 内建函数 ----
    ("B1", "texelFetch(sampler2D, ivec2, int) —— 需要整数坐标", "允许",
     "uniform sampler2D s; in ivec2 UV2; out vec4 c;"
     "void main(){ c = texelFetch(s, UV2 / 16, 0); gl_Position = vec4(0.0); }"),
    ("B2", "texture(sampler2D, vec2) 收到 ivec2", "禁止",
     "uniform sampler2D s; in ivec2 UV2; out vec4 c;"
     "void main(){ c = texture(s, UV2); gl_Position = vec4(0.0); }"),
    ("B3", "clamp(ivec2 / float, vec2, vec2)", "禁止",
     "in ivec2 UV2; out vec2 tc;"
     "void main(){ tc = clamp(UV2 / 256.0, vec2(0.5), vec2(0.9)); gl_Position = vec4(0.0); }"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="实测 GLSL ES 的隐式转换规则")
    ap.add_argument("--glslc", default=DEFAULT_GLSLC)
    ap.add_argument("--version", default="320", help="GLSL ES 版本，默认 320")
    ap.add_argument("--dir", default=None, help="临时文件目录")
    args = ap.parse_args()

    glslc = Path(args.glslc)
    if not glslc.is_file():
        print(f"错误: 找不到 glslc: {glslc}", file=sys.stderr)
        return 2

    tmp = Path(args.dir) if args.dir else Path(os.environ.get("TEMP", "."))
    tmp.mkdir(parents=True, exist_ok=True)

    print(f"glslc  : {glslc}")
    print(f"版本   : #version {args.version} es")
    print()
    print(f"{'ID':<4} {'裁决':<6} {'先验':<8} 说明")
    print("-" * 78)

    n_accept = n_reject = 0
    rows: list[tuple[str, str, str, str, list[str]]] = []

    for cid, desc, prior, body in CASES:
        if "#version" in body:
            src = body
        else:
            src = f"#version {args.version} es\n{body}\n"
        f = tmp / f"probe_{cid}.vsh"
        f.write_text(src, encoding="utf-8")

        cmd = [str(glslc), "--target-env=opengl",
               "-fshader-stage=vert", str(f), "-o", os.devnull]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30)
        except subprocess.TimeoutExpired:
            verdict, errs = "超时", []
            rows.append((cid, verdict, prior, desc, errs))
            print(f"{cid:<4} {verdict:<6} {prior:<8} {desc}")
            continue

        blob = (r.stdout or "") + (r.stderr or "")
        errs = []
        for line in blob.splitlines():
            line = line.strip()
            if not line or "error" not in line.lower():
                continue
            if SUMMARY_RE.match(line):
                continue
            if any(n in line for n in SPIRV_NOISE):
                continue
            errs.append(line)

        verdict = "禁止" if errs else "允许"
        if errs:
            n_reject += 1
        else:
            n_accept += 1
        rows.append((cid, verdict, prior, desc, errs))
        print(f"{cid:<4} {verdict:<6} {prior:<8} {desc}")

    print()
    print("=" * 78)
    print(f"允许 {n_accept} 项，禁止 {n_reject} 项，共 {len(rows)} 项")
    print()
    print("【编译器原话（仅禁止项）】")
    for cid, verdict, prior, desc, errs in rows:
        if not errs:
            continue
        msg = errs[0]
        m = re.search(r":\d+:\s*(.*)$", msg)
        print(f"  {cid}: {(m.group(1) if m else msg)[:150]}")

    # 统计先验判断与实测不符的项 —— 这些是最有价值的信息
    print()
    print("【先验与实测不一致的项】")
    any_mismatch = False
    for cid, verdict, prior, desc, _ in rows:
        p = prior.replace("?", "")
        if p in ("允许", "禁止") and p != verdict:
            any_mismatch = True
            print(f"  {cid}: 先验认为「{prior}」，实测「{verdict}」 —— {desc}")
    if not any_mismatch:
        print("  （无）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
