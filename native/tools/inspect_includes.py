#!/usr/bin/env python3
"""
检查 MC 着色器 include 文件的真实内容，并查看 MC 如何处理 #moj_import。

【为什么要查】
   我先前推断「fog.glsl 以 #version 150 开头，被 #moj_import 内联后会在
   文件中部产生第二条 #version，导致编译失败」。
   但这个推断有个致命疑点：**桌面上同样不允许文件中部出现 #version**。
   若 fog.glsl 真的以 #version 开头且 MC 原样内联，
   那 Minecraft 在桌面 GL 上也会坏 —— 显然不是事实。

   所以要么 (a) fog.glsl 其实不含 #version，要么
       (b) MC 在内联时会处理/剥离 #version。

   两种情况对转换器的要求完全不同，必须先确定是哪一种。

用法:
    py inspect_includes.py [--jar <jar>]
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


def find_jar() -> Path | None:
    base = Path.home() / ".gradle/caches/neoformruntime/artifacts"
    if not base.is_dir():
        return None
    cands = sorted(base.glob("minecraft_*_client.jar"),
                   key=lambda p: p.stat().st_size, reverse=True)
    return cands[0] if cands else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar")
    args = ap.parse_args()

    jar = Path(args.jar) if args.jar else find_jar()
    if jar is None or not jar.is_file():
        print("错误: 找不到 MC 客户端 jar", file=sys.stderr)
        return 1
    print(f"jar: {jar.name}\n")

    z = zipfile.ZipFile(jar)
    with z:
        # ---- 1. include 文件内容 ----
        print("=" * 70)
        print("1. shaders/include/ 下的文件内容")
        print("=" * 70)
        for n in sorted(z.namelist()):
            if "/shaders/include/" not in n:
                continue
            body = z.read(n).decode("utf-8", "replace")
            lines = body.split("\n")
            has_ver = any(l.strip().startswith("#version") for l in lines)
            print(f"\n--- {n}  ({len(lines)} 行, 含 #version: {has_ver}) ---")
            # 打印全部行（不去掉尾部）：需要看到确切的函数签名，
            # 以便在转换器里提供等价实现时签名完全一致。
            for i, l in enumerate(lines):
                print(f"  {i:3}| {l}")

        # ---- 2. MC 是如何处理 #moj_import 的 ----
        print()
        print("=" * 70)
        print("2. 相关 class 里出现 'moj_import' 的位置")
        print("=" * 70)
        pat = re.compile(rb"moj_import|\.glsl|#version")
        for n in z.namelist():
            if not n.endswith(".class"):
                continue
            if "shaders" not in n.lower() and "Shader" not in n:
                continue
            data = z.read(n)
            if b"moj_import" in data:
                print(f"\n  {n}")
                # 打印该 class 常量池里所有含关键字的字符串
                for m in re.finditer(rb"[\x20-\x7e]{6,200}", data):
                    s = m.group(0).decode("ascii", "replace")
                    if "moj_import" in s or "#version" in s:
                        print(f"     const: {s!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
