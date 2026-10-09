#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trace_conv_lines.py -- 把真机 patched_shaders 原文跑一遍我们的转换器，
并显示**转换输出**里多个指定行。

【为什么必须看输出的行号】
日志里的 ERROR: 0:167 是**驱动看到的那份文本**的行号，也就是
    Iris 输出 -> 我们的库 glShaderSource
之后由我们产出的文本。所以要用转换器跑一遍 Iris 的输出，
再按那个行号去我们的输出里定位。

用法:
    py native\\tools\\trace_conv_lines.py <Iris输出文件> <阶段> 167 1212 1492
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / ".cache" / "trace"
CACHE.mkdir(parents=True, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
CLI = str(CACHE / "cli.exe")
CLI_SRC = str(HERE / "convert_shader_cli.c")
SHADER_C = str(ROOT / "native" / "src" / "shader.c")
INCLUDE = str(ROOT / "native" / "include")

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


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    stage = sys.argv[2]
    if not src.is_file():
        print("!! 找不到", src)
        return 1

    build_cli()
    out = CACHE / (src.name + ".conv")
    r = subprocess.run([CLI, str(src), stage, str(out)],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not out.is_file():
        print("!! 转换失败:", (r.stderr or "")[:300])
        return 3

    src_lines = src.read_text(encoding="utf-8",
                              errors="replace").splitlines()
    out_lines = out.read_text(encoding="utf-8",
                              errors="replace").splitlines()
    print("输入: %s  (%d 行)" % (src, len(src_lines)))
    print("输出: %s  (%d 行)" % (out, len(out_lines)))

    for a in sys.argv[3:]:
        try:
            n = int(a)
        except ValueError:
            continue
        print()
        print("################ 输出第 %d 行 ################" % n)
        for i in range(max(1, n - 5), min(len(out_lines), n + 4) + 1):
            mark = ">>" if i == n else "  "
            print("%s%5d| %s" % (mark, i, out_lines[i - 1]))

    # 顺带跑一次 glslang，看我们自己能不能复现
    r2 = subprocess.run([GLSlC, "--target-env=opengl",
                         "-fshader-stage=" + stage, str(out),
                         "-o", str(out) + ".spv"],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    real = [l.strip() for l in (r2.stderr or "").splitlines()
            if "error" in l.lower()
            and not any(x in l for x in SPV_NOISE)]
    print()
    print("=" * 74)
    print("我方 glslang 校验: 真实错误 %d 条" % len(real))
    for e in real[:20]:
        print("   ", e[:150])
    return 0


if __name__ == "__main__":
    sys.exit(main())
