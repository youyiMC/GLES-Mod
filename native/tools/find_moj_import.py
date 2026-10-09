#!/usr/bin/env python3
"""
在 MC 客户端 jar 中定位处理 #moj_import 的类，并输出其常量池里的相关字符串。

【目的】
   已确认 fog.glsl 以 `#version 150` 开头，且被 #moj_import 内联。
   若 MC 原样内联，文件中部就会出现第二条 #version —— 这在**桌面 GL 上同样
   是编译错误**。Minecraft 显然在桌面上能正常运行，因此 MC 必然在内联时
   对 include 里的 #version 做了处理（剥离或重写）。

   搞清 MC 的实际做法，才能确定：
     - 我们的转换器「移除全部 #version 再补一条」是否正确
     - 我们看到的输入究竟长什么样（是否含 #line 指令、是否已剥离）

用法:
    py find_moj_import.py [--jar <jar>]
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

KEYWORDS = [b"moj_import", b"#version", b"#line", b".glsl"]


def find_jar() -> Path | None:
    base = Path.home() / ".gradle/caches/neoformruntime/artifacts"
    if not base.is_dir():
        return None
    cands = sorted(base.glob("minecraft_*_client.jar"),
                   key=lambda p: p.stat().st_size, reverse=True)
    return cands[0] if cands else None


# class 文件常量池中的字符串是 modified UTF-8，长度前缀为 u2。
# 为了省事，这里直接在字节流里搜索可打印 ASCII 串，
# 对定位「哪个类含关键字」已经足够。
PRINTABLE = re.compile(rb"[\x20-\x7e]{5,400}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar")
    args = ap.parse_args()

    jar = Path(args.jar) if args.jar else find_jar()
    if jar is None or not jar.is_file():
        print("错误: 找不到 MC 客户端 jar", file=sys.stderr)
        return 1
    print(f"jar: {jar.name}")

    z = zipfile.ZipFile(jar)
    hits: list[tuple[str, list[str]]] = []
    with z:
        for n in z.namelist():
            if not n.endswith(".class"):
                continue
            data = z.read(n)
            if b"moj_import" not in data:
                continue
            strs = []
            for m in PRINTABLE.finditer(data):
                s = m.group(0).decode("ascii", "replace")
                if any(k.decode() in s for k in KEYWORDS):
                    strs.append(s)
            hits.append((n, strs))

    print(f"\n含 'moj_import' 的类共 {len(hits)} 个")
    for n, strs in hits:
        print("\n" + "=" * 70)
        print(f"### {n}")
        print("=" * 70)
        seen = set()
        for s in strs:
            if s in seen:
                continue
            seen.add(s)
            # 只显示与预处理相关的行，避免刷屏
            if any(k.decode() in s for k in KEYWORDS):
                print(f"  {s!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
