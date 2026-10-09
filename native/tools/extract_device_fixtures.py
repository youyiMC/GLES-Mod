#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_device_fixtures.py -- 从 native.log 抽出真机失败的着色器做回归夹具。

为什么值得单独抽
================
真机源码比人造探针更有价值：它就是 Simulated 实际送进来的东西，
包含 `vec2(textureSize(X, 0))`、`ivec2 x = textureSize(X, 0)`、
`vec2(16.0,0.0) / textureSize(X, 0)`、`vec2 size = textureSize(X, 0)`
等真实组合。修完必须用它回归。

日志格式
========
    ===== BEGIN 该 shader 收到 glShaderSource 的原始源码 =====
         0| #version 330 core
         ...
    ===== END 该 shader 收到 glShaderSource 的原始源码 (112 行) =====
    ===== BEGIN 该 shader 实际被送入驱动的源码（转换后） =====
         ...
    ===== END 该 shader 实际被送入驱动的源码（转换后） (N 行) =====
    编译失败的着色器 —— 阶段=片元，GL 名称=101

注意：每条内容行在日志里**连续出现两次**（两条转储路径都写了），
抽取时必须去重，否则错误行号会整体翻倍。
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOG = os.path.join(ROOT, "native.log")
OUT = os.path.join(HERE, "fixtures", "device")

RX_RAW_BEGIN = re.compile(r"BEGIN 该 shader 收到 glShaderSource 的原始源码")
RX_CONV_BEGIN = re.compile(r"BEGIN 该 shader 实际被送入驱动的源码")
RX_END = re.compile(r"END 该 shader .*源码.*?\((\d+) 行\)")
RX_FAIL = re.compile(r"编译失败的着色器 .* 阶段=(\S+)，GL 名称=(\d+)")
RX_LINE = re.compile(r"^\s*(\d+)\|\s?(.*)$")


def strip_ts(line):
    """去掉 `[hh:mm:ss.mmm] ` 前缀。"""
    m = re.match(r"^\[[^\]]*\]\s?(.*)$", line)
    return m.group(1) if m else line


def dedupe(lines):
    """相邻两行内容相同 -> 只留一行（日志双写）。"""
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if i + 1 < len(lines) and lines[i] == lines[i + 1]:
            i += 2
        else:
            i += 1
    return out


def parse_block(lines, i, begin_rx, end_rx):
    """从 lines[i:] 里解析一个源码块，返回 (文本, 下一索引, 行数)。"""
    # 跳过重复的 BEGIN 行
    j = i
    while j < len(lines) and begin_rx.search(strip_ts(lines[j])):
        j += 1
    body = []
    while j < len(lines):
        s = strip_ts(lines[j])
        m = end_rx.search(s)
        if m:
            n = int(m.group(1))
            # 跳过重复的 END 行
            j += 1
            while j < len(lines) and end_rx.search(strip_ts(lines[j])):
                j += 1
            return body, j, n
        m2 = RX_LINE.match(s)
        if m2:
            body.append(m2.group(2))
        j += 1
    return body, j, -1


def main():
    if not os.path.isfile(LOG):
        print("FAIL: 找不到 %s" % LOG)
        return 1
    os.makedirs(OUT, exist_ok=True)

    with io.open(LOG, encoding="utf-8", errors="replace") as fh:
        raw_lines = fh.read().splitlines()
    lines = dedupe([strip_ts(l) for l in raw_lines])
    print("native.log 行数（去时间戳+去重后）: %d" % len(lines))

    found = []
    i = 0
    while i < len(lines):
        if RX_RAW_BEGIN.search(lines[i]):
            raw_body, i, raw_n = parse_block(lines, i, RX_RAW_BEGIN, RX_END)
            # 其后应紧跟 conv 块
            while i < len(lines) and not RX_CONV_BEGIN.search(lines[i]):
                if RX_RAW_BEGIN.search(lines[i]):
                    break
                i += 1
            conv_body, i, conv_n = parse_block(lines, i, RX_CONV_BEGIN, RX_END)
            # 往后找失败标记 / 错误文本
            stage, sid = "?", "?"
            errs = []
            j = i
            while j < len(lines) and j < i + 400:
                m = RX_FAIL.search(lines[j])
                if m:
                    stage, sid = m.group(1), m.group(2)
                    break
                j += 1
            k = j
            while k < len(lines) and k < j + 60:
                if "ERROR:" in lines[k] and "compilation errors" not in lines[k]:
                    errs.append(lines[k].strip())
                if RX_RAW_BEGIN.search(lines[k]):
                    break
                k += 1
            if raw_body and conv_body:
                found.append((sid, stage, raw_n, conv_n, raw_body, conv_body, errs))
            continue
        i += 1

    print("解析到 %d 个成对的失败转储\n" % len(found))
    written = 0
    for sid, stage, raw_n, conv_n, raw_body, conv_body, errs in found:
        if not errs:
            continue          # 只落有明确错误的，避免噪声
        ext = ".frag" if "片元" in stage else ".vert"
        base = os.path.join(OUT, "device_%s%s" % (sid, ext))
        if os.path.exists(base):
            continue          # 同名只写一次（日志里同一 shader 会反复出现）
        with io.open(base, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(raw_body) + "\n")
        with io.open(base[:-len(ext)] + ".expected_errors.txt", "w",
                     encoding="utf-8", newline="\n") as fh:
            fh.write("阶段=%s\n" % stage)
            for e in errs:
                fh.write(e + "\n")
        written += 1
        print("  写出 %s  (%d 行, %d 条错误)" % (os.path.basename(base),
                                                 raw_n, len(errs)))
    print("\n共写出 %d 个夹具 -> %s" % (written, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
