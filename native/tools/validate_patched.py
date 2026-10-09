#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_patched.py -- 拿 Iris 导出的**真机原文**做基准，验证我们的转换器。

这是目前最可靠的验证方式：
  1. `patched_shaders/` 里的文件是 Iris 交给我们库之前（或之后）的真实文本，
     错误行号与它**精确对齐**，不必再猜分支或行号。
  2. 用它跑一次转换 + glslang，能立刻看出还剩哪些真实缺陷。

【重要】Iris 会在切换光影包时**清空并覆盖** patched_shaders 目录。
所以一个包里只放**最后使用的那个光影包**的输出。
若要保留某个包的原文，请在切换前先把目录复制出来。

用法:
    py native\\tools\\validate_patched.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / ".cache" / "patched"
CACHE.mkdir(parents=True, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
CLI = str(CACHE / "cli.exe")
CLI_SRC = str(HERE / "convert_shader_cli.c")
SHADER_C = str(ROOT / "native" / "src" / "shader.c")
INCLUDE = str(ROOT / "native" / "include")
SRC_DIR = ROOT / "patched_shaders"

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")


def build_cli():
    r = subprocess.run(
        [GCC, "-O1", "-std=c11", "-o", CLI, CLI_SRC, SHADER_C,
         "-I", INCLUDE],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("!! CLI 编译失败:")
        print(r.stdout or "", r.stderr or "")
        sys.exit(1)


def check(path: Path, stage: str):
    """转换 -> glslang。返回 (真实错误, 输出路径)"""
    out = CACHE / (path.name + ".conv")
    r = subprocess.run([CLI, str(path), stage, str(out)],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not out.is_file():
        return ["转换器未产出文件: %s" % (r.stderr or "")[:200]], None

    r2 = subprocess.run([GLSlC, "--target-env=opengl",
                         "-fshader-stage=" + stage, str(out),
                         "-o", str(out) + ".spv"],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    real = []
    for ln in (r2.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        real.append(ln.strip())
    return real, out


def main():
    if not SRC_DIR.is_dir():
        print("!! 找不到 patched_shaders 目录:", SRC_DIR)
        return 2
    files = sorted(p for p in SRC_DIR.glob("*")
                   if p.suffix in (".fsh", ".vsh"))
    if not files:
        print("!! patched_shaders 里没有着色器")
        return 2

    build_cli()
    print("patched_shaders 基准:", SRC_DIR)
    print("着色器:", len(files))
    print()

    total_bad = 0
    for p in files:
        stage = "frag" if p.suffix == ".fsh" else "vert"
        real, out = check(p, stage)
        src_lines = p.read_text(encoding="utf-8",
                                errors="replace").splitlines()
        # 【注意】glslang 报的行号是**转换输出**的行号，不是原文行号。
        # 我们的转换器会在最前面加 #version + precision 若干行，
        # 因此两者有固定偏移。同时打印两边，避免再看错。
        conv_lines = (out.read_text(encoding="utf-8", errors="replace")
                      .splitlines() if out else [])
        print("-" * 74)
        print("%s  (原文 %d 行, 输出 %d 行, 阶段=%s)"
              % (p.name, len(src_lines), len(conv_lines), stage))
        print("-" * 74)
        if not real:
            print("  通过：转换后无 GLSL ES 错误")
        else:
            total_bad += len(real)
            print("  剩余 %d 条错误" % len(real))
            for e in real[:24]:
                m = re.search(r':(\d+):\s*error:\s*(.*)$', e)
                if m:
                    ln = int(m.group(1))
                    txt = conv_lines[ln - 1].strip() if ln <= len(conv_lines) else ""
                    print("    输出 L%-5d %s" % (ln, txt[:92]))
                    print("                    %s" % m.group(2)[:104])
                else:
                    print("   ", e[:150])
            if len(real) > 24:
                print("    ... 其余 %d 条" % (len(real) - 24))
        print()

    print("=" * 74)
    print("总剩余真实错误:", total_bad)
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
