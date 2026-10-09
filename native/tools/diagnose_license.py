#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diagnose_license.py -- 诊断 GitHub 为何未识别 LICENSE 为 LGPL-3.0。

GitHub 的许可证识别（licensee）判定依据是**文件内容**与已知模板的匹配，
不是文件名。因此要逐字节看清这个文件到底长什么样。

已知 FSF 官方文本的参照尺寸
===========================
  lgpl-3.0.txt（仅 LGPL 正文，短版）    ~7654 B
  gpl-3.0.txt （GPL-3.0 全文）          ~35149 B
  两者合并（很多项目采用的形态）        ~42803 B

检查项
======
1. 尺寸与行数，是否与"合并形态"吻合
2. 首/尾若干行的实际内容（含行首空格转义显示）
3. 控制字符分布 —— GPL 正文里**本来就有**换页符 0x0C（分页），
   但其它控制字符属于异常
4. 行尾风格（LF / CRLF）以及是否存在孤立 CR
5. 是否含 BOM
6. 关键模板短语是否存在（licensee 依赖这些短语做匹配）
7. 仓库里是否有**其它**可能干扰识别的许可类文件
"""

import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LIC = os.path.join(ROOT, "LICENSE")

RULE = "=" * 84

# licensee 匹配 LGPL-3.0 时会依赖的关键短语
KEY_PHRASES = [
    "GNU LESSER GENERAL PUBLIC LICENSE",
    "Version 3, 29 June 2007",
    "This version of the GNU Lesser General Public License incorporates",
    "the terms and conditions of version 3 of the GNU General Public",
    "0. Additional Definitions.",
    "GNU LESSER GENERAL PUBLIC LICENSE",
    "TERMS AND CONDITIONS",
    "Free Software Foundation",
]


def esc(s, n=100):
    """把行首空格可视化，便于确认居中格式是否正确。"""
    lead = len(s) - len(s.lstrip(" "))
    out = s[:n]
    return "lead=%2d | %s" % (lead, out.replace("\t", "\\t"))


def main():
    print(RULE)
    print("LICENSE 诊断")
    print(RULE)

    if not os.path.isfile(LIC):
        print("FAIL: 找不到 %s" % LIC)
        return 1

    raw = open(LIC, "rb").read()
    print("路径        : %s" % LIC)
    print("字节数      : %d" % len(raw))
    print("LF 数       : %d" % raw.count(b"\n"))
    print("CRLF 数     : %d" % raw.count(b"\r\n"))
    print("孤立 CR 数  : %d" % (raw.count(b"\r") - raw.count(b"\r\n")))
    print("BOM         : %s" % ("有" if raw[:3] == b"\xef\xbb\xbf" else "无"))

    # ---- 控制字符 ----
    print()
    print("--- 控制字符分布（GPL 正文本含 0x0C 换页符，属正常）---")
    ctrl = {}
    for b in raw:
        if b < 0x09 or (0x0B <= b <= 0x0C) or (0x0E <= b <= 0x1F):
            ctrl[b] = ctrl.get(b, 0) + 1
    if not ctrl:
        print("  无任何控制字符（注意：官方 GPL 正文含 0x0C，缺失说明被处理过）")
    for b in sorted(ctrl):
        name = {0x0C: "换页 FF（官方分页符）", 0x0B: "垂直制表",
                0x08: "退格", 0x1B: "ESC"}.get(b, "控制字符")
        flag = "" if b == 0x0C else "  <-- 异常"
        print("  0x%02X %-22s x%d%s" % (b, name, ctrl[b], flag))

    # ---- 首尾内容 ----
    text = raw.decode("utf-8", "replace")
    lines = text.split("\n")
    print()
    print("--- 前 8 行（lead=行首空格数）---")
    for i, l in enumerate(lines[:8], 1):
        print("  %3d: %s" % (i, esc(l)))
    print()
    print("--- 后 6 行 ---")
    tail = [l for l in lines[-8:]]
    for i, l in enumerate(tail, len(lines) - len(tail) + 1):
        print("  %3d: %s" % (i, esc(l)))

    # ---- 关键短语 ----
    print()
    print("--- 关键短语（licensee 匹配依据）---")
    for p in KEY_PHRASES:
        print("  %-62s %s" % (p[:62], "存在" if p in text else "**缺失**"))

    # ---- 其它可能干扰的文件 ----
    print()
    print("--- 仓库根目录下的许可类文件 ---")
    for f in sorted(os.listdir(ROOT)):
        if re.match(r"^(LICEN[CS]E|COPYING|COPYRIGHT)", f, re.I):
            print("  %s" % f)
    # 非标准名但也含 license 字样的
    for f in sorted(os.listdir(ROOT)):
        if "LICENSE" in f.upper() and not re.match(r"^(LICEN[CS]E|COPYING)", f, re.I):
            print("  %s   <-- 非标准命名（通常不会被 licensee 当作许可证文件）" % f)

    # ---- 提交内容 vs 工作区 ----
    print()
    print("--- 已提交内容是否与工作区一致 ---")
    r = subprocess.run(["git", "diff", "--stat", "HEAD", "--", "LICENSE"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("  %s" % (r.stdout.strip() or "(一致)"))

    # ---- 已提交 blob 的行尾（这才是 GitHub 看到的）----
    print()
    print("--- 已提交 blob 的实际情况（GitHub 读的是这个）---")
    r = subprocess.run(["git", "show", "HEAD:LICENSE"], cwd=ROOT,
                       capture_output=True)
    if r.returncode == 0:
        blob = r.stdout
        print("  字节数   : %d" % len(blob))
        print("  LF 数    : %d" % blob.count(b"\n"))
        print("  CRLF 数  : %d" % blob.count(b"\r\n"))
        print("  前 3 行  :")
        for l in blob.decode("utf-8", "replace").split("\n")[:3]:
            print("      %s" % esc(l))
    else:
        print("  读取失败")

    print()
    print(RULE)
    print("提示：若关键短语齐全、控制字符正常、已提交内容与工作区一致，")
    print("      则文件本身没有问题，识别失败可能与 GitHub 的识别时机有关，")
    print("      重新推送一次该文件即可触发重新识别。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
