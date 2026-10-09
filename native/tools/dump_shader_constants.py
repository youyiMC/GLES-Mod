#!/usr/bin/env python3
"""
从 class 文件的常量池中取出真实的着色器源码字符串，并推算报错行号。

【为什么必须这么做，而不是照抄源码 jar】

判断「着色器转换器有没有生效」完全依赖一个数字：驱动报的错误行号。
而该行号是相对于【真正送入编译器的源码】的：

    转换器未生效 -> 送入的是原始源码 -> 行号 = 原始源码中的行号
    转换器生效   -> 送入的是转换后源码（前面多了 #version 等行）-> 行号后移

所以只要知道「原始源码里 gl_Position 在第几行」，就能反推结论。

但 java 源码里写入的文本块，经 javac 编译后成为常量池里的字符串常量。
文本块会保留缩进与换行，且 `\"\"\"` 之后立即换行会让字符串以 '\n' 开头
—— 这个细节直接决定行号是 11 还是 12。
照抄 .java 文件存在抄错一行的风险，而 class 文件里的常量是编译产物，
是唯一权威来源。

【实现说明】

直接解析 class 文件的常量池（不依赖 javap），因为：
  - javap 的输出会转义/换行折断长字符串，容易误读
  - 常量池解析只需要处理十几种 tag，几十行代码即可

用法：
    py native/tools/dump_shader_constants.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path
import zipfile

# earlydisplay jar（FML 早期显示窗口），版本需与真机一致
JAR_CANDIDATES = [
    Path.home() / ".gradle/caches/modules-2/files-2.1/net.neoforged.fancymodloader"
    / "earlydisplay/4.0.43",
]

CLASS_ENTRY = "net/neoforged/fml/earlydisplay/ElementShader.class"

# 定位 gl_Position 所在行，用于行号推算
MARKER = "gl_Position"


def find_class_file() -> Path | None:
    """在 Gradle 缓存里找到 earlydisplay jar 及其中的 class。"""
    for base in JAR_CANDIDATES:
        if not base.is_dir():
            continue
        for jar in base.rglob("*.jar"):
            if "sources" in jar.name:
                continue
            try:
                with zipfile.ZipFile(jar) as z:
                    if CLASS_ENTRY in z.namelist():
                        return jar
            except zipfile.BadZipFile:
                continue
    return None


def parse_utf8_constants(data: bytes) -> list[str]:
    """
    解析 class 文件的常量池，返回所有 Utf8 常量。

    只实现必要部分：按顺序读完整个常量池，跳过其它 tag 的数据长度。
    Long(5) 与 Double(6) 占两个常量池槽位，这是最容易出错的地方。
    """
    pos = 0

    def u1():
        nonlocal pos
        v = data[pos]
        pos += 1
        return v

    def u2():
        nonlocal pos
        v = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        return v

    def u4():
        nonlocal pos
        v = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        return v

    def skip(n):
        nonlocal pos
        pos += n

    magic = u4()
    if magic != 0xCAFEBABE:
        raise ValueError("不是有效的 class 文件")
    u2()  # minor
    u2()  # major

    count = u2()
    out: list[str] = []
    i = 1
    while i < count:
        tag = u1()
        if tag == 1:            # Utf8
            n = u2()
            raw = data[pos:pos + n]
            skip(n)
            # 常量池用 modified UTF-8；着色器源码是纯 ASCII，直接解码即可
            out.append(raw.decode("utf-8", errors="replace"))
        elif tag in (7, 8, 16, 19, 20):   # Class, String, MethodType, Module, Package
            skip(2)
        elif tag in (15,):      # MethodHandle
            skip(3)
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):  # 4 字节
            skip(4)
        elif tag in (5, 6):     # Long, Double：占两个槽位
            skip(8)
            i += 1
        else:
            raise ValueError(f"未知的常量池 tag {tag}（位置 {pos}）")
        i += 1

    return out


def main() -> int:
    jar = find_class_file()
    if jar is None:
        print("错误: 未在 Gradle 缓存中找到 earlydisplay jar", file=sys.stderr)
        return 1

    print(f"jar: {jar.name}")
    with zipfile.ZipFile(jar) as z:
        data = z.read(CLASS_ENTRY)

    consts = parse_utf8_constants(data)

    shaders = [c for c in consts if "#version" in c and "void main" in c]
    if not shaders:
        print("错误: 常量池中未找到着色器源码", file=sys.stderr)
        return 1

    print(f"找到 {len(shaders)} 段着色器源码\n")

    for idx, src in enumerate(shaders):
        lines = src.split("\n")
        stage = "顶点" if "gl_Position" in src else "片元"
        print(f"--- 着色器 #{idx}（{stage}）---")
        print(f"  总行数        : {len(lines)}")
        print(f"  首行内容      : {lines[0]!r}")
        print(f"  第二行内容    : {lines[1]!r}" if len(lines) > 1 else "")

        # 打印前 3 行并带行号，让 #version 的绝对位置一目了然
        for n in range(min(3, len(lines))):
            print(f"    [{n}] {lines[n]!r}")

        if MARKER in src:
            marker_line = next(n for n, l in enumerate(lines) if MARKER in l)
            print(f"  '{MARKER}' 所在行: {marker_line}  (驱动报错若为 {marker_line} 则未转换)")
        print()

    print("=== 判定 ===")
    print("真机驱动报的错误行: 0:12")
    print("若上面 marker 行号为 11 -> 源码未经转换（转换器未生效）")
    print("若为 12 或更大         -> 源码已经过转换（转换器生效）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
