#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_canonical_license.py -- 用 FSF 当前官方文本替换 LICENSE。

背景（为什么要替换）
====================
GitHub 的许可证识别返回了 `NOASSERTION` —— 意思是"找到了 LICENSE 文件，
但内容匹配不上任何已知模板"。逐字节比对查明原因是：

  本地 LICENSE 是 FSF 的**旧版**文本：
      http://fsf.org/                                  （旧）
      http://www.gnu.org/licenses/                     （旧）
      http://www.gnu.org/philosophy/why-not-lgpl.html  （旧路径）
  当前官方文本已全部改为 https，且最后一个 URL 连**路径**都变了：
      https://www.gnu.org/licenses/why-not-lgpl.html

URL 路径的差异属于实质性 token 差异，超出识别器的容错范围。

这不是"为了通过识别而改许可" —— 我们的授权从未变过（仍是 LGPL-3.0-or-later），
只是本地那份是过时排印。换成官方当前文本后，授权内容完全一致，
且能被机器正确识别。

做法：从 FSF 官方拼接 LGPL-3.0 正文 + GPL-3.0 正文（LGPL 第 3 条要求
以 GPL 条款为基础，因此标准做法是把两段正文都附上），**按字节**写入。
"""

import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CACHE = os.path.join(os.environ.get("TEMP", "/tmp"), "gl_lic")

LICENSE = os.path.join(ROOT, "LICENSE")
LGPL = os.path.join(CACHE, "lgpl-3.0.txt")
GPL = os.path.join(CACHE, "gpl-3.0.txt")
BACKUP = os.path.join(CACHE, "LICENSE.before-canonical")


def main():
    for p in (LICENSE, LGPL, GPL):
        if not os.path.isfile(p):
            print("FAIL: 缺少 %s" % p)
            return 1

    lgpl = io.open(LGPL, encoding="utf-8").read()
    gpl = io.open(GPL, encoding="utf-8").read()

    # LGPL-3.0 的标准形态：LGPL 正文在前，GPL-3.0 正文在后，两者直接相接。
    # 两段正文各自以换行结尾，拼接时不要再插空行（官方模板即如此）。
    canonical = lgpl.rstrip("\n") + "\n" + gpl

    old = io.open(LICENSE, encoding="utf-8").read()

    print("旧 LICENSE : %d 字节" % len(old.encode("utf-8")))
    print("新 LICENSE : %d 字节" % len(canonical.encode("utf-8")))
    print()

    if old == canonical:
        print("已经一致，无需替换")
        return 0

    # 备份原文件，便于回溯
    shutil.copyfile(LICENSE, BACKUP)
    print("原文件已备份到: %s" % BACKUP)

    with io.open(LICENSE, "w", encoding="utf-8", newline="") as fh:
        fh.write(canonical)

    chk = io.open(LICENSE, encoding="utf-8").read()
    print("写入完成，读回校验: %s" % ("一致" if chk == canonical else "**不一致**"))

    # 复核三处关键 URL 已更新
    print()
    print("--- 关键 URL 复核 ---")
    for u in ("https://fsf.org/",
              "https://www.gnu.org/licenses/",
              "https://www.gnu.org/licenses/why-not-lgpl.html"):
        print("  %-52s %s" % (u, "存在" if u in chk else "**缺失**"))
    for u in ("http://fsf.org/",
              "philosophy/why-not-lgpl.html"):
        print("  %-52s %s" % ("旧: " + u,
                              "**仍存在（异常）**" if u in chk else "已清除"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
