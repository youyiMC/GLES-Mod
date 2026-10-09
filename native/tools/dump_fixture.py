#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_fixture.py -- 把 fixtures/ 下某个夹具经我们的转换器跑一遍并打印输出。

用法:
    py native\\tools\\dump_fixture.py iris_layout_out.frag
    py native\\tools\\dump_fixture.py            # 列出所有夹具

为什么需要它: 上一轮的错误行号 (0:20) 是**我们输出**的行号，所以必须能看到
自己产出的文本，而不是去猜驱动看到了什么。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIXTURES = os.path.join(HERE, "fixtures")
TMP = os.path.join(HERE, ".cache", "roundtrip")
os.makedirs(TMP, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
CLI_SRC = os.path.join(HERE, "convert_shader_cli.c")
CLI_EXE = os.path.join(TMP, "convert_shader_cli_dump.exe")
SHADER_C = os.path.join(ROOT, "native", "src", "shader.c")
INCLUDE = os.path.join(ROOT, "native", "include")


def build_cli():
    r = subprocess.run(
        [GCC, "-O1", "-std=c11", "-o", CLI_EXE, CLI_SRC, SHADER_C,
         "-I", INCLUDE],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("CLI 编译失败:")
        print(r.stdout or "", r.stderr or "")
        sys.exit(1)


def main():
    files = sorted(f for f in os.listdir(FIXTURES)
                   if f.endswith((".vert", ".frag", ".vsh", ".fsh")))

    if len(sys.argv) < 2:
        print("fixtures/ 下的夹具:")
        for f in files:
            print("   ", f)
        print("\n用法: py native\\tools\\dump_fixture.py <夹具名>")
        return 0

    name = sys.argv[1]
    if name not in files:
        print("!! 没有这个夹具:", name)
        return 2

    build_cli()

    stage = "vertex" if name.endswith((".vert", ".vsh")) else "fragment"
    src = os.path.join(FIXTURES, name)
    out = os.path.join(TMP, name + ".dump")

    orig = open(src, encoding="utf-8", errors="replace").read().splitlines()
    print("=" * 74)
    print("输入:", src)
    print("=" * 74)
    for i, ln in enumerate(orig):
        print("%4d| %s" % (i + 1, ln))

    r = subprocess.run([CLI_EXE, src, stage, out],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print()
    print("=" * 74)
    print("转换输出 (rc=%d):" % r.returncode)
    print("=" * 74)
    if r.stderr.strip():
        print("[stderr]", r.stderr.strip())
    if not os.path.isfile(out):
        print("!! 没有产出文件")
        return 3
    for i, ln in enumerate(open(out, encoding="utf-8",
                                errors="replace").read().splitlines()):
        print("%4d| %s" % (i + 1, ln))

    return 0


if __name__ == "__main__":
    sys.exit(main())
