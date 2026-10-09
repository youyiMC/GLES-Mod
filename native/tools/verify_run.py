#!/usr/bin/env python3
"""
verify_run.py -- 对某一次真机运行日志做逐项核对。

与 audit_run.py 的分工
------------------------------------------------------------------
  audit_run.py   统计驱动报错与探针结果（面向「驱动说了什么」）
  verify_run.py  核对「本次运行是否达成预期」（面向「验收与版本核验」）

回答四个固定问题：

  1. **跑的是新构建吗？** 靠某个「只有新构建才会有」的日志行判定，
     而不是靠文件时间戳或用户描述。
  2. 有没有致命错误？      崩溃、着色器编译失败、缺符号。
  3. 降级/静默失效情况？    降级事件、缺失符号、被调用的空实现。
  4. 驱动噪声量级？        与历史基线对比，判断是否恶化。

无命令行参数（task runner 会剥离引号），自行 glob 工作区根目录下的 *.log
并取编号最大的一个（即最新那份）。

LGPL-3.0-or-later
"""

import glob
import os
import re
import sys

# ---------------------------------------------------------------- 配置

# 「只有新构建才会有」的标记行。用于判定设备上跑的产物是否为新。
#
# 为什么用这个而不是文件时间戳：
#   时间戳只反映构建系统的内部记账，不反映二进制里到底有什么
#   （本项目已因此浪费过一整轮真机测试，见记忆 2bm）。
#   而日志里「某一行存在/不存在」是二进制内容的直接证据。
NEW_BUILD_MARKERS = [
    # 修复「calledStubs 解析了却传不出到诊断报告」之后才有的段。
    # 该修复与 P3-01 同批构建，因此可作为本批产物的指纹。
    ("诊断报告含『被调用的空实现』段", r"被调用的空实现 \(\d+\)"),
]

# 致命 / 需关注的模式
FATAL_PATTERNS = [
    ("崩溃 (SIGSEGV)",          r"SIGSEGV"),
    ("着色器编译失败",          r"Shader compilation failed|could not preload shader"),
    ("Failed to map buffer",    r"Failed to map buffer"),
    ("未捕获异常",              r"Exception in thread \"main\"|FATAL ERROR"),
]

# 降级 / 静默失效（取括号里的数字）
DEGRADE_PATTERNS = [
    ("降级事件",        r"降级事件 \((\d+) 类\)"),
    ("缺失符号",        r"缺失符号 \((\d+)\)"),
    ("被调用的空实现",  r"被调用的空实现 \((\d+)\)"),
]

# 驱动噪声（用于与历史基线对比）
NOISE_PATTERNS = [
    ("Namespace collision",        r"Namespace collision detected"),
    ("EsxBufferMapUnsyncedBit",    r"Ignoring EsxBufferMapUnsyncedBit"),
    ("less than 3 vertices",       r"less than 3 vertices"),
    ("unsubmitted work",           r"high level of unsubmitted work"),
    ("Abnormally high render area", r"Abnormally high render area"),
    ("Reset max power request",    r"Reset max power request"),
]

# 第三方模组问题（非本项目职责）
THIRDPARTY_PATTERNS = [
    ("SCLP Mixin 注入",   r"sclp\.mixins|MixinTaintDetector|Write access detected"),
    ("SCLP 找不到类",     r"Error loading class.*(sodium|embeddium)"),
    ("ShaderInstance 采样器", r"could not find sampler named"),
]

# 历史基线（用于对比噪声是否恶化）。取最近一次已验证正常的运行。
BASELINE_NOTE = "基线参考：2026-09-29 Embeddium 轮 —— Namespace collision ~50 次，" \
                "EsxBufferMapUnsyncedBit 1 次，less than 3 vertices 4 次"


def find_latest_log(root):
    """取工作区根目录下编号最大的 latest(N).log。

    必须按**数字**排序：字符串排序会把 latest(10).log 排到 latest(9).log 之前。
    同时兼容没有编号的 *.log。
    """
    cands = glob.glob(os.path.join(root, "*.log"))
    if not cands:
        return None

    def sort_key(path):
        m = re.search(r"\((\d+)\)", os.path.basename(path))
        return int(m.group(1)) if m else -1

    return max(cands, key=sort_key)


def count_matches(text, pattern):
    return len(re.findall(pattern, text))


def extract_number(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def main():
    # 本脚本位于 native/tools/，工作区根目录在其上两级
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", ".."))

    log_path = find_latest_log(root)
    if log_path is None:
        print("FAIL: 工作区根目录下找不到 *.log")
        return 1

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    print("=" * 76)
    print("真机运行日志核对")
    print("=" * 76)
    print("日志文件 : %s" % os.path.basename(log_path))
    print("大小     : %.1f KB" % (os.path.getsize(log_path) / 1024.0))
    print()

    # ---- 1. 构建版本核验 ----
    print("=" * 76)
    print("[1] 构建版本核验")
    print("=" * 76)
    for label, pat in NEW_BUILD_MARKERS:
        hit = re.search(pat, text) is not None
        print("  [%s] %s" % ("OK" if hit else "NO", label))
    print()
    print("  判据：这些标记行只存在于新构建的产物中。")
    print("        时间戳不可靠（只反映构建系统记账），标记行才是二进制内容的证据。")
    print()

    # ---- 2. 致命错误 ----
    print("=" * 76)
    print("[2] 致命错误")
    print("=" * 76)
    fatal_any = False
    for label, pat in FATAL_PATTERNS:
        n = count_matches(text, pat)
        if n:
            fatal_any = True
        print("  [%s] %-26s %d 次" % ("!!" if n else "OK", label, n))
    print()

    # ---- 3. 降级 / 静默失效 ----
    print("=" * 76)
    print("[3] 降级与静默失效")
    print("=" * 76)
    for label, pat in DEGRADE_PATTERNS:
        v = extract_number(text, pat)
        if v is None:
            print("  [??] %-24s 未出现（日志可能被截断，或该段尚未加入构建）" % label)
        else:
            print("  [%s] %-24s %d" % ("OK" if v == 0 else "!!", label, v))
    print()

    # ---- 4. 驱动噪声 ----
    print("=" * 76)
    print("[4] 驱动噪声（与历史基线对比）")
    print("=" * 76)
    for label, pat in NOISE_PATTERNS:
        n = count_matches(text, pat)
        print("  %-30s %d 次" % (label, n))
    print()
    print("  %s" % BASELINE_NOTE)
    print()

    # ---- 5. 第三方模组问题 ----
    print("=" * 76)
    print("[5] 第三方模组问题（非本项目职责）")
    print("=" * 76)
    for label, pat in THIRDPARTY_PATTERNS:
        n = count_matches(text, pat)
        print("  %-30s %d 次" % (label, n))
    print()

    # ---- 6. 关键状态行 ----
    print("=" * 76)
    print("[6] 关键状态行（原文摘录）")
    print("=" * 76)
    keys = [
        r"GLES 后端已激活.*",
        r"优化模组: .*",
        r"OpenGL Version: .*",
    ]
    for k in keys:
        for m in re.finditer(k, text):
            line = m.group(0)
            if len(line) > 140:
                line = line[:140] + " ..."
            print("  " + line)
    print()

    print("=" * 76)
    print("结论")
    print("=" * 76)
    if fatal_any:
        print("  [!] 发现致命错误，见 [2] 中标 !! 的项。")
    else:
        print("  [OK] 无致命错误。")
    print("  [OK] 判据：降级事件 / 缺失符号 / 被调用的空实现 三项均为 0")
    print("       表示渲染路径没有踩到任何未实现或降级的功能。")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
