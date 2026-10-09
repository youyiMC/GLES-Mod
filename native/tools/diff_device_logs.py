#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff_device_logs.py -- 严格对比两次设备日志，判定修复是否真的生效。

为什么要机器对比而不是肉眼
==========================
「这次没看到那个错误」可能是没报，也可能是日志被截断、或者根本没走到那一步。
所以按固定类别逐项比对，并把「上一次有、这一次没有」的行单独列出来。

用法：
    py -X utf8 native/tools/diff_device_logs.py latest(1).log latest(2).log
"""

import io
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# 关心的事件类别：(名称, 正则)
CATS = [
    ("Veil 编译失败",      re.compile(r"Failed to create shader")),
    ("着色器编译错误行",   re.compile(r"^\s*ERROR: \d+:\d+:")),
    ("驱动错误汇总行",     re.compile(r"compilation errors")),
    ("Veil 跳过着色器",    re.compile(r"Skipping shader")),
    ("Veil 加载着色器",    re.compile(r"Loaded \d+ shaders from")),
    ("Veil 编译原生着色器", re.compile(r"Compiled \d+ vanilla shaders")),
    ("Flywheel 后端回退",  re.compile(r"backend fell back")),
    ("多幔绑失败",         re.compile(r"Multi-Bind unsupported")),
    ("Sable 原生加载",     re.compile(r"Rapier native loaded")),
    ("Sable 子级别报文",   re.compile(r"sub-level movement packet")),
    ("光影包相关",         re.compile(r"shaderpack|shader pack|iris", re.I)),
    ("glesmod 降级",       re.compile(r"降级事件|缺失符号|被调用的空实现")),
]

# 这些是「多一行就可能是真实回归」的类别
NEGATIVE = {"Veil 编译失败", "着色器编译错误行", "驱动错误汇总行"}


def load(path):
    lines = []
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^\[[^\]]*\]\s?(.*)$", ln.rstrip("\n"))
        lines.append(m.group(1) if m else ln.rstrip("\n"))
    return lines


def bucket(lines, rx):
    out = []
    for l in lines:
        if rx.search(l):
            out.append(l.strip())
    return out


def main():
    if len(sys.argv) < 3:
        print("用法: diff_device_logs.py <旧日志> <新日志>")
        return 1

    old_p, new_p = sys.argv[1], sys.argv[2]
    for p in (old_p, new_p):
        if not os.path.isfile(p):
            print("找不到 %s" % p)
            return 1

    old = load(old_p)
    new = load(new_p)
    print("旧日志 %-16s %d 行" % (old_p, len(old)))
    print("新日志 %-16s %d 行" % (new_p, len(new)))
    print()

    print("=" * 96)
    print("%-22s %8s %8s   %s" % ("类别", "旧", "新", "判定"))
    print("=" * 96)

    regress = []
    fixed = []
    for name, rx in CATS:
        a = bucket(old, rx)
        b = bucket(new, rx)
        ca, cb = Counter(a), Counter(b)

        if ca == cb:
            judge = "相同"
        elif name in NEGATIVE:
            if len(b) < len(a):
                judge = "★ 减少 %d -> %d（修复生效）" % (len(a), len(b))
                fixed.append((name, a, b))
            else:
                judge = "**增加 %d -> %d（疑似回归）**" % (len(a), len(b))
                regress.append((name, a, b))
        else:
            judge = "变化 %d -> %d" % (len(a), len(b))

        print("%-22s %8d %8d   %s" % (name, len(a), len(b), judge))

    print()
    print("=" * 96)
    print("逐条列出：上次有、这次没有的行（即被修掉的）")
    print("=" * 96)
    for name, a, b in fixed:
        ca, cb = Counter(a), Counter(b)
        gone = list((ca - cb).elements())
        if not gone:
            continue
        print()
        print("[%s]" % name)
        for g in gone:
            print("    - %s" % g[:150])

    if not fixed:
        print("(无)")

    print()
    print("=" * 96)
    print("逐条列出：这次新增的行（需人工确认是否新问题）")
    print("=" * 96)
    anynew = False
    for name, rx in CATS:
        a = bucket(old, rx)
        b = bucket(new, rx)
        ca, cb = Counter(a), Counter(b)
        added = list((cb - ca).elements())
        if not added:
            continue
        anynew = True
        print()
        print("[%s]" % name)
        for x in added:
            print("    + %s" % x[:150])
    if not anynew:
        print("(无新增)")

    print()
    if regress:
        print("verdict: 有疑似回归 %d 类" % len(regress))
        return 1
    print("verdict: 无回归，且失败项已消失")
    return 0


if __name__ == "__main__":
    sys.exit(main())
