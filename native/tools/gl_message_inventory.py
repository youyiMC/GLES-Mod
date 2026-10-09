#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gl_message_inventory.py

统计 latest.log 里所有 GL 调试消息（GlDebug 打印的 message='...'），
按出现次数倒序排列，并标出哪些是「本库自己引起的」。

为什么要做这件事：
    驱动通过 KHR_debug 回调报告的错误是**一手证据** —— 它就是 GL 实现
    对「你调用错了」的原话。把这些消息归类计数，能立刻分辨：
      · 哪些是长期存在、与我们无关的噪声（如 pixel buffer format）
      · 哪些是本项目在某些调用上真的用错了 API（如对默认帧缓冲做附件查询）
      · 哪些是渲染本身真的坏了（如 framebuffer incomplete）

用法：
    py native/tools/gl_message_inventory.py --log latest.log
"""

import argparse
import re
import sys
from collections import Counter

MSG_RE = re.compile(r"message='([^']*)'")
# 本库自己会触发的查询/调用，用于标注「疑似与本库有关」
SELF_MARKERS = (
    "attachemnt", "attachment", "pname",
    "framebuffer", "renderbuffer",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    with open(args.log, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    msgs = []
    for ln in lines:
        m = MSG_RE.search(ln)
        if m:
            msgs.append(m.group(1))

    if not msgs:
        print("未找到任何 GL 调试消息（GlDebug message='...'）。")
        return 0

    cnt = Counter(msgs)
    total = len(msgs)

    print(f"GL 调试消息总数: {total}，去重后 {len(cnt)} 种")
    print()
    print(f"{'次数':>7}  {'与本库相关':<10} 消息")
    print("-" * 100)
    for msg, c in cnt.most_common(args.top):
        low = msg.lower()
        self_rel = "★ 是" if any(k in low for k in SELF_MARKERS) else "-"
        print(f"{c:>7}  {self_rel:<10} {msg}")

    print()
    print("=" * 100)
    print("按「与本库相关」汇总：")
    self_hits = sum(c for m, c in cnt.items()
                    if any(k in m.lower() for k in SELF_MARKERS))
    print(f"  疑似与本库查询/调用有关: {self_hits}")
    print(f"  其余（历史噪声等）      : {total - self_hits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
