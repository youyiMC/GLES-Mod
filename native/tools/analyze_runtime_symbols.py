#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_runtime_symbols.py

目的：把「真机日志里 MC 实际调用过的 GL 符号」与 symbols.def 的分类对账。

为什么这个对账是关键：
    日志里每条 "注意: 符号 glXxx 来自 ..." 都是本库**第一次**解析该符号时打的，
    也就是说，这份名单 = MC 在这次运行里真正用到的 GL 函数的完整集合。
    比静态扫描 class 字节可靠得多（静态扫描会被同名前缀和常量池误伤）。

    然后按 symbols.def 的分类：
        F = 纯转发（安全）
        C = 定制实现（本项目自己的代码，需要人工确认）
        S = 存根（**静默忽略调用**）
    如果某个 S 类符号出现在运行期名单里，说明 MC 调了它、我们却什么都没做。
    这就是「静默丢调用」的确证，优先排查。

用法：
    py native/tools/analyze_runtime_symbols.py \
        --log "native(8).log" --def native/symbols.def
"""

import argparse
import re
import sys
from collections import OrderedDict

# 一次运行的分界：后端激活行
RUN_START_RE = re.compile(r"GLES 后端已激活")
# 符号解析行：  注意: 符号 glXxx 来自 ...
SYM_RE = re.compile(r"符号\s+(gl[A-Za-z0-9_]+)")
# symbols.def 行： F void glXxx(...)   或  S GLenum glXxx(...)
DEF_RE = re.compile(r"^([FCS])\s+.*?\b(gl[A-Za-z0-9_]+)\s*\(")


def load_def(path):
    cls = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = DEF_RE.match(line)
            if m:
                cls[m.group(2)] = m.group(1)
    return cls


def split_runs(lines):
    """按 'GLES 后端已激活' 切分运行；返回 [(start_idx, [lines])]"""
    starts = [i for i, l in enumerate(lines) if RUN_START_RE.search(l)]
    runs = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        runs.append((s, lines[s:e]))
    if not starts:
        runs.append((0, lines))
    return runs


def used_symbols(run_lines):
    """按首次出现顺序收集该运行里解析过的符号"""
    out = OrderedDict()
    for l in run_lines:
        m = SYM_RE.search(l)
        if not m:
            continue
        name = m.group(1)
        if name not in out:
            out[name] = l.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--def", dest="symbols_def", required=True)
    ap.add_argument("--run", type=int, default=-1,
                    help="分析第几次运行（1 起）。默认最后一次。")
    args = ap.parse_args()

    with open(args.log, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    cls = load_def(args.symbols_def)
    runs = split_runs(lines)

    idx = args.run
    if idx < 0:
        idx = len(runs)
    if not (1 <= idx <= len(runs)):
        print(f"运行序号超出范围：共 {len(runs)} 次运行")
        return 2

    start, run_lines = runs[idx - 1]
    used = used_symbols(run_lines)

    print(f"日志：{args.log}")
    print(f"共 {len(runs)} 次运行；本次分析第 {idx} 次"
          f"（文件第 {start + 1} 行起，{len(run_lines)} 行）")
    print(f"symbols.def：{len(cls)} 个符号"
          f"（F={sum(1 for v in cls.values() if v == 'F')} "
          f"C={sum(1 for v in cls.values() if v == 'C')} "
          f"S={sum(1 for v in cls.values() if v == 'S')}）")
    print()

    buckets = {"F": [], "C": [], "S": [], "?": []}
    for name in used:
        buckets[cls.get(name, "?")].append(name)

    print(f"运行期实际解析过的符号：{len(used)} 个")
    print(f"  F 纯转发 : {len(buckets['F'])}")
    print(f"  C 定制   : {len(buckets['C'])}")
    print(f"  S 存根   : {len(buckets['S'])}   <== 非零即为「静默丢调用」")
    print(f"  ? 未登记 : {len(buckets['?'])}   <== 非零说明 symbols.def 有漏项")
    print()

    if buckets["S"]:
        print("=" * 68)
        print("!! 危险：以下存根（S）函数在运行期被 MC 真正调用过")
        print("   调用被静默忽略 —— 很可能就是几何错位的元凶")
        print("=" * 68)
        for n in buckets["S"]:
            print(f"  [S] {n}")
        print()

    if buckets["?"]:
        print("=" * 68)
        print("!! 未登记符号（symbols.def 里查不到，需补全）")
        print("=" * 68)
        for n in buckets["?"]:
            print(f"  [?] {n:44s}  {used[n]}")
        print()

    if buckets["C"]:
        print("定制实现（C）被调用清单 —— 这些是本项目自己的代码：")
        for n in buckets["C"]:
            print(f"  [C] {n}")
        print()

    print("完整运行期符号清单（按首次使用顺序）：")
    for i, n in enumerate(used, 1):
        k = cls.get(n, "?")
        print(f"  {i:3d}. [{k}] {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
