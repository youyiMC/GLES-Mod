#!/usr/bin/env python3
"""
用 glslc（Android NDK 自带的 glslang 前端）校验转换后的 GLSL ES 源码。

【为什么需要这个 —— 这是本项目的「真相来源」】

在此之前，判断「转换后的着色器能否被 GLSL ES 接受」靠的是自己写的正则规则。
正则只能覆盖已经踩过的坑：每修好一类，才发现还有下一类。
真机一轮测试要几分钟，靠这种方式找 bug 代价极高。

glslc 内置 **glslang** —— 与 Adreno 驱动同一套 GLSL ES 类型规则的真实编译器前端。
它能直接复现驱动原话：

    ERROR: 0:34: 'assign' : cannot convert from
    'attribute 2-component vector of int' to
    'varying 2-component vector of float'      <- Adreno

    error: 'assign' :  cannot convert from ' in highp 2-component vector of int'
    to ' smooth out highp 2-component vector of float'   <- glslc（同一错误）

因此本地就能穷举出全部隐式转换错误，无需真机往返。

【为什么要过滤一批错误】

glslc 总是产出 SPIR-V，而 SPIR-V 对 GLSL 有额外约束（要求显式 location、
uniform 必须放进 block 等）。Minecraft 的着色器是给 GL 驱动用的，
不要求这些。因此下列错误属于 glslc 的产物，必须过滤掉，
否则每个着色器都会刷屏、掩盖真正的类型错误：

    'location' : SPIR-V requires location for user input/output
    'binding' : sampler/texture/image requires layout(binding=X)
    'non-opaque uniforms outside a block' : not allowed when using GLSL for Vulkan

【用法】
    py glslc_validate.py --dir <已导出的转换结果目录> [--glslc <路径>]
    py glslc_validate.py --dir <...> --verbose
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# glslc 的 SPIR-V 附加约束 —— 与 GLSL 类型规则无关，必须过滤
#
# 每一类都对应 Minecraft 着色器的正常写法，只是不满足 SPIR-V 的要求：
#   - in/out 没有 layout(location)：GL 由 glBindAttribLocation 决定，SPIR-V 要求显式
#   - sampler 没有 layout(binding)：GL 由 glUniform1i 决定，SPIR-V 要求显式
#   - 普通 uniform 在 block 之外：GLSL ES 3.x 完全允许
#   - 普通 uniform 没有 layout(location)：同上，仅是 SPIR-V 的限制
SPIRV_NOISE = (
    "SPIR-V requires location for user input/output",
    "requires layout(binding=X)",
    "non-opaque uniform variables need a layout(location=L)",
    "non-opaque uniforms outside a block",
    "not allowed when using GLSL for Vulkan",
    "SPIR-V requires explicitly",
    "requires an initializer",
    "can only be used in SPIR-V",
)

# glslc 的汇总行（"3 errors generated."）：不是错误本身，必须排除，
# 否则每个着色器都会因它被判为失败。
SUMMARY_RE = re.compile(r"^\d+\s+errors?\s+generated\.?$")

DEFAULT_GLSLC = (
    r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
)


def find_glslc(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    p = Path(DEFAULT_GLSLC)
    if p.is_file():
        return p
    # 退而求其次：在 Android SDK 下搜索最新 NDK
    sdk = Path(os.environ.get("ANDROID_HOME", r"C:\Android\Sdk"))
    ndk_root = sdk / "ndk"
    if ndk_root.is_dir():
        for d in sorted(ndk_root.iterdir(), reverse=True):
            for cand in d.glob("shader-tools/*/glslc.exe"):
                if cand.is_file():
                    return cand
    return None


def stage_of(name: str) -> str:
    if name.endswith(".vsh"):
        return "vert"
    if name.endswith(".fsh"):
        return "frag"
    # include 文件（.glsl）没有阶段，按顶点着色器校验其函数体可编译性意义不大，
    # 但它们已被内联进各着色器，所以跳过即可
    return ""


def validate(glslc: Path, path: Path, stage: str) -> list[str]:
    """返回真实（已过滤）错误行；空列表表示通过。"""
    cmd = [
        str(glslc),
        "--target-env=opengl",
        f"-fshader-stage={stage}",
        str(path),
        "-o", os.devnull,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except subprocess.TimeoutExpired:
        return [f"超时: {path.name}"]

    blob = (r.stdout or "") + (r.stderr or "")
    errs: list[str] = []
    for line in blob.splitlines():
        line = line.strip()
        if not line or "error" not in line.lower():
            continue
        if SUMMARY_RE.match(line):
            continue
        if any(n in line for n in SPIRV_NOISE):
            continue
        errs.append(line)
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="用 glslc 校验转换后的 GLSL ES")
    ap.add_argument("--dir", required=True,
                    help="转换结果目录（audit-mc-shaders.ps1 -Export 的输出）")
    ap.add_argument("--glslc", help="glslc 可执行文件路径")
    ap.add_argument("--verbose", action="store_true",
                    help="同时打印通过的着色器")
    args = ap.parse_args()

    glslc = find_glslc(args.glslc)
    if glslc is None:
        print("错误: 找不到 glslc（Android NDK 的 shader-tools）", file=sys.stderr)
        return 2

    src_dir = Path(args.dir)
    if not src_dir.is_dir():
        print(f"错误: 目录不存在: {src_dir}", file=sys.stderr)
        return 2

    print(f"glslc : {glslc}")
    print(f"目录  : {src_dir}")
    print()

    files = sorted(p for p in src_dir.iterdir()
                   if p.suffix in (".vsh", ".fsh"))
    if not files:
        print("错误: 目录中没有 .vsh/.fsh 文件", file=sys.stderr)
        return 2

    n_ok = 0
    n_bad = 0
    for p in files:
        stage = stage_of(p.name)
        if not stage:
            continue
        errs = validate(glslc, p, stage)
        if errs:
            n_bad += 1
            print(f"[失败] {p.name}")
            # 同类错误去重，只保留前若干条，避免刷屏
            seen = set()
            shown = 0
            for e in errs:
                # 去掉文件路径前缀，保留 :行: 列: 信息
                m = re.search(r":(\d+):\s*(.*)$", e)
                key = m.group(2) if m else e
                if key in seen:
                    continue
                seen.add(key)
                print(f"       {m.group(0) if m else e}")
                shown += 1
                if shown >= 8:
                    print(f"       ...（共 {len(errs)} 条错误）")
                    break
        else:
            n_ok += 1
            if args.verbose:
                print(f"[通过] {p.name}")

    print()
    print("=" * 60)
    print(f"通过 {n_ok} 个，失败 {n_bad} 个，共 {n_ok + n_bad} 个")
    if n_bad == 0:
        print("结论: 全部着色器通过 glslang 的 GLSL ES 类型检查。")
    else:
        print("结论: 仍有 GLSL ES 拒绝的写法，见上方失败列表。")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
