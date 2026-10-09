#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_builtin_int_args.py -- 复现 14:19 日志里的两处着色器编译失败。

背景
====
真机日志（latest.log）里 Veil 报了两个真实失败：

  1) simulated:redstone_accumulator/diode  （片元）
     ERROR: 0:106: '/' : wrong operand types
            no operation '/' exists that takes a left-hand operand of type
            'const 2-component vector of float' and a right operand of type
            '2-component vector of int'

  2) simulated:contraption_diagram/outline_diagram （片元）
     ERROR: 0:21: 'textureSize' : no matching overloaded function found
     ERROR: 0:47: 'textureSize' : no matching overloaded function found
     ERROR: 0:109: '=' : cannot convert from '2-component vector of int'
                          to '2-component vector of float'

假设（待验证，不是结论）
========================
`textureSize(sampler, lod)` 的第二个参数**必须是 int**。如果我们的转换器
把 `0` 浮点化成 `0.0`，就会得到 "no matching overloaded function found"。
同理 `texelFetch(s, ivec2, lod)`、`textureLod(s, uv, lod)` 等内建函数的
整型实参一旦被浮点化，就会整类失败。

而且这些内建函数**没有出现在 shader.c 的整型实参名单里**（grep `textureSize`
在 native/src 下 0 命中），嫌疑很大。

本脚本：对每个探针 → 用真实转换器转换 → glslang 判定 → 打印结果。
只报事实，不下结论。

用法： py -X utf8 native/tools/probe_builtin_int_args.py
"""

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(HERE, ".cache", "probe_builtin")
GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
CLI = os.path.join(CACHE, "cli.exe")

# glslc 目标是 SPIR-V，会额外报 Vulkan 专有要求 —— 与 GLES 目标无关，过滤掉。
SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")


def build_cli():
    os.makedirs(CACHE, exist_ok=True)
    r = subprocess.run(
        [GCC, "-O2", "-std=c11", "-Wall",
         "-I", os.path.join(ROOT, "native", "src"),
         "-I", os.path.join(ROOT, "native", "include"),
         "-o", CLI,
         os.path.join(HERE, "convert_shader_cli.c"),
         os.path.join(ROOT, "native", "src", "shader.c"), "-lm"],
        capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("BUILD FAILED")
        print(r.stdout)
        print(r.stderr)
        return False
    print("build OK")
    return True


HEAD_FRAG = """#version 330 core

uniform sampler2D uTex;
uniform sampler2D uData;
uniform sampler2D uDepth;
uniform sampler2D uTint;

in vec2 vUV;
out vec4 fragColor;

"""

# 每条探针：(名字, 说明, 源码片段)
PROBES = [
    ("textureSize_literal",
     "textureSize 的 lod 实参是字面量 0（必须是 int）",
     """
void main() {
    ivec2 sz = textureSize(uTex, 0);
    vec2 uv = vUV * vec2(sz);
    fragColor = texture(uTex, uv);
}
"""),

    ("textureSize_vec2_assign",
     "textureSize 结果直接赋给 vec2（对照：原样应报 int->float）",
     """
void main() {
    vec2 sz = textureSize(uTex, 0);
    fragColor = texture(uTex, vUV * sz);
}
"""),

    ("texelFetch_literal",
     "texelFetch 的 lod 实参是字面量 0",
     """
void main() {
    ivec2 p = ivec2(vUV * 64.0);
    vec4 c = texelFetch(uTex, p, 0);
    fragColor = c;
}
"""),

    ("textureLod_literal",
     "textureLod 的 lod 实参是字面量 0",
     """
void main() {
    fragColor = textureLod(uTex, vUV, 0);
}
"""),

    ("texture_literal_lod_ctor",
     "构造 ivec2 时混入整型字面量，再参与浮点运算",
     """
void main() {
    ivec2 a = ivec2(0, 0);
    vec2 b = vec2(a);
    fragColor = texture(uTex, vUV + b);
}
"""),

    ("div_const_vec_by_ivec",
     "const vec2 除以 ivec2 —— 对照日志里的 '/' 错误",
     """
void main() {
    ivec2 i = ivec2(4, 4);
    vec2 r = vec2(1.0, 1.0) / i;
    fragColor = texture(uTex, vUV * r);
}
"""),

    ("textureSize_in_float_expr",
     "textureSize 结果参与浮点表达式（Veil 生成代码常见形态）",
     """
void main() {
    vec2 uv = vUV * 2.0 - 1.0;
    ivec2 size = textureSize(uData, 0);
    vec2 inv = 1.0 / vec2(size);
    fragColor = texture(uData, (uv * 0.5 + 0.5) / inv);
}
"""),

    ("control_plain",
     "对照组：不涉及内建整型实参，预期始终通过",
     """
void main() {
    fragColor = texture(uTex, vUV);
}
"""),

    # ---- 第二轮：浮点构造器上下文中的内建整型实参 ----
    # 机制假设：`vec2(textureSize(...))` 把浮点性渗透进 textureSize 的 lod 实参。
    ("size_in_vec2_ctor",
     "[关键] vec2(textureSize(uTex, 0)) —— lod 在浮点 ctor 上下文内",
     """
void main() {
    vec2 inv = vec2(textureSize(uTex, 0));
    fragColor = texture(uTex, vUV * inv);
}
"""),

    ("size_in_vec2_ctor_div",
     "[关键] 1.0 / vec2(textureSize(uTex, 0)) —— 日志里 '/' 错误的同型",
     """
void main() {
    vec2 texel = 1.0 / vec2(textureSize(uTex, 0));
    fragColor = texture(uTex, vUV + texel * 0.5);
}
"""),

    ("size_ivec2_then_vec2",
     "先存 ivec2 再手动转 vec2（正确写法对照）",
     """
void main() {
    ivec2 sz = textureSize(uTex, 0);
    vec2 inv = 1.0 / vec2(sz);
    fragColor = texture(uTex, vUV + inv * 0.5);
}
"""),

    ("size_in_float_ctor_macro",
     "[关键] 宏参与 + 浮点 ctor：vec2(textureSize(uTex, LOD))",
     """
#define LOD 0
void main() {
    vec2 inv = vec2(textureSize(uTex, LOD));
    fragColor = texture(uTex, vUV * inv);
}
"""),

    ("size_in_vec2_ctor_variable",
     "[关键] 局部 int 变量作 lod，外层套浮点 ctor",
     """
void main() {
    int lod = 0;
    vec2 inv = vec2(textureSize(uTex, lod));
    fragColor = texture(uTex, vUV * inv);
}
"""),

    ("texelfetch_in_float_expr",
     "[关键] texelFetch 的 lod 在浮点表达式中",
     """
void main() {
    ivec2 p = ivec2(vUV * 64.0);
    vec4 c = texelFetch(uTex, p, 0) * 0.5;
    fragColor = c;
}
"""),

    ("texelfetch_ivec_from_float",
     "[关键] ivec2(浮点运算) 作为 texelFetch 坐标",
     """
void main() {
    vec2 uv = vUV * 64.0;
    vec4 c = texelFetch(uTex, ivec2(uv), 0);
    fragColor = c;
}
"""),

    ("div_const_by_ivec_ctor",
     "[关键] const vec2 / ivec2(...) —— 复现日志的 '/' 错误",
     """
void main() {
    vec2 r = vec2(1.0, 1.0) / ivec2(4, 4);
    fragColor = texture(uTex, vUV * r);
}
"""),

    ("div_const_by_texturesize",
     "[关键] const vec2 / textureSize(...) —— '/' 错误另一形态",
     """
void main() {
    vec2 r = vec2(1.0, 1.0) / textureSize(uTex, 0);
    fragColor = texture(uTex, vUV * r);
}
"""),

    ("size_in_float_ctor_texel",
     "[关键] 变量 vec2 = 1.0 / vec2(textureSize(...))，与日志结构最接近",
     """
void main() {
    vec2 uv = vUV * 2.0 - 1.0;
    vec2 texelSize = 1.0 / vec2(textureSize(uData, 0));
    vec4 acc = vec4(0.0);
    acc += texture(uData, uv + vec2(-1.0, -1.0) * texelSize);
    acc += texture(uData, uv + vec2( 1.0,  1.0) * texelSize);
    acc += texture(uData, uv + vec2(-1.0,  1.0) * texelSize);
    acc += texture(uData, uv + vec2( 1.0, -1.0) * texelSize);
    fragColor = acc * 0.25;
}
"""),
]


def glslang_errors(path, stage="frag"):
    r = subprocess.run([GLSLC, "--target-env=opengl", "-fshader-stage=" + stage,
                        path, "-o", path + ".spv"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        s = ln.strip()
        if not s or "error" not in s.lower():
            continue
        if any(n in s for n in SPV_NOISE):
            continue
        if "errors generated" in s:
            continue
        errs.append(s)
    return errs


def main():
    if not build_cli():
        return 1

    print()
    print("=" * 78)
    bad = 0
    for name, desc, body in PROBES:
        raw = os.path.join(CACHE, name + ".raw.frag")
        conv = os.path.join(CACHE, name + ".conv.frag")
        with open(raw, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(HEAD_FRAG + body)

        subprocess.run([CLI, raw, "fragment", conv],
                       capture_output=True, text=True)

        # 转换前后的关键行，用来判断我们到底改了什么
        before = open(raw, encoding="utf-8", errors="replace").read().splitlines()
        after = open(conv, encoding="utf-8", errors="replace").read().splitlines()

        errs = glslang_errors(conv)
        verdict = "PASS" if not errs else "FAIL (%d)" % len(errs)

        print("%-26s %-52s" % (name, desc))
        print("    verdict: %s" % verdict)

        # 打印我们改动的行（原始 vs 转换后 不一致处）
        changed = []
        for i, ln in enumerate(after):
            if i < len(before):
                if before[i] != ln and ("textureSize" in ln or "texelFetch" in ln
                                        or "textureLod" in ln or "vec2" in ln
                                        or "ivec2" in ln):
                    changed.append("      ORIG %s" % before[i].strip())
                    changed.append("      CONV %s" % ln.strip())
            else:
                if "textureSize" in ln or "ico" in ln:
                    changed.append("      CONV+ %s" % ln.strip())
        for c in changed[:8]:
            print(c)

        for e in errs[:4]:
            print("      %s" % e[:150])
            bad += 1
        print()

    print("=" * 78)
    print("总判定：%s" % ("全部通过 —— 内建整型实参未被破坏"
                        if bad == 0 else "有 %d 条错误行" % bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
