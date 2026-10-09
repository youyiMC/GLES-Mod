#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_license_to_official.py -- 把本地 LICENSE 与 FSF 官方原文逐字节比对。

为什么必须逐字节比对
====================
GitHub 的许可证识别（licensee）是拿文件内容与内置模板做匹配的。
"看起来对"不算数 —— 只要结构上有任何偏离模板的地方（多一个空行、
少一个换行、段落顺序不同），匹配就可能失败，而且**不会给任何提示**。
所以唯一的办法是与官方原文对齐比较，把差异点定位到具体字节。
"""

import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CACHE = os.path.join(os.environ.get("TEMP", "/tmp"), "gl_lic")

OURS = os.path.join(ROOT, "LICENSE")
LGPL = os.path.join(CACHE, "lgpl-3.0.txt")
GPL = os.path.join(CACHE, "gpl-3.0.txt")

RULE = "=" * 84


def read(p):
    if not os.path.isfile(p):
        return None
    return open(p, "rb").read()


def ff_note(b):
    return "0x0C x%d" % b.count(b"\x0c")


def main():
    ours, lgpl, gpl = read(OURS), read(LGPL), read(GPL)
    if ours is None:
        print("FAIL: 找不到 LICENSE")
        return 1
    if lgpl is None or gpl is None:
        print("FAIL: 官方原文缺失，请先下载到 %s" % CACHE)
        return 1

    print(RULE)
    print("逐字节比对")
    print(RULE)
    print("  本地 LICENSE      : %6d B   %s" % (len(ours), ff_note(ours)))
    print("  官方 lgpl-3.0.txt : %6d B   %s" % (len(lgpl), ff_note(lgpl)))
    print("  官方 gpl-3.0.txt  : %6d B   %s" % (len(gpl), ff_note(gpl)))
    print("  两者直接拼接      : %6d B" % (len(lgpl) + len(gpl)))
    print()

    # 尝试几种常见的拼接方式
    cands = [
        ("lgpl+gpl（无分隔）", lgpl + gpl),
        ("lgpl+LF+gpl", lgpl + b"\n" + gpl),
        ("lgpl+CRLF+gpl", lgpl + b"\r\n" + gpl),
        ("gpl+lgpl", gpl + lgpl),
    ]
    best = None
    for name, c in cands:
        if c == ours:
            print("  ✔ 完全一致：%s" % name)
            best = (name, c)
            break
        # 计算首个不同字节
        n = min(len(c), len(ours))
        i = 0
        while i < n and c[i] == ours[i]:
            i += 1
        print("  ✗ %-20s 长度差 %+d，首个不同字节 @%d"
              % (name, len(ours) - len(c), i))
        if best is None:
            best = (name, c)
    print()

    if best is None:
        return 1

    # 详细展示首个差异点
    name, c = best
    n = min(len(c), len(ours))
    i = 0
    while i < n and c[i] == ours[i]:
        i += 1
    print(RULE)
    print("首个差异点（以最接近的候选「%s」为基准，第 %d 字节）" % (name, i))
    print(RULE)

    lo = max(0, i - 200)
    print("--- 官方（该位置前 200 字节起）---")
    print(repr(c[lo:i]))
    print("--- 本地（同位置）---")
    print(repr(ours[lo:i]))

    print()
    print("--- 官方该处后续 120 字节 ---")
    print(repr(c[i:i + 120]))
    print("--- 本地该处后续 120 字节 ---")
    print(repr(ours[i:i + 120]))

    if len(ours) != len(c):
        print()
        print("长度差 %+d 字节" % (len(ours) - len(c)))
        if len(ours) > len(c):
            print("本地多出的尾部: %r" % ours[len(c):][:200])
        else:
            print("本地缺少的尾部: %r" % c[len(ours):][:200])

    print()
    print(RULE)
    print("结论")
    print(RULE)
    print("  若差异仅在行尾/空行/分页符，则用官方拼接结果直接替换本地 LICENSE 即可，")
    print("  这是消除识别不确定性最省事也最可靠的做法。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
