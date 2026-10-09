#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_license_final.py -- 确认新 LICENSE 与 GitHub 模板完全一致。

结论回顾（这轮排查的完整逻辑链）
================================
1. GitHub API 返回 spdx_id=NOASSERTION  -> 识别器找到了 LICENSE 但没匹配上
2. 本地是 FSF 旧版排印（http:// 且 why-not-lgpl 路径已变）-> 先换成官方当前文本
3. 仍为 NOASSERTION                      -> 说明问题不止于 URL
4. 查 GET /licenses/lgpl-3.0             -> GitHub 模板 = **7652 字节，只有 LGPL 正文**
   而本地是 LGPL+GPL 拼接 = 42801 字节   -> **文件比模板大 5.6 倍，必然不匹配**

教训：**"法律上用哪份文本"与"识别器认哪份模板"是两件事。**
      LGPL-3.0 正文第 3 条以"并入 GPL-3.0 条款"的方式引用 GPL，
      因此只附 LGPL 正文在法律上成立（这也是 GitHub 模板的做法）；
      附上完整 GPL 正文虽然更周全，却会让识别器匹配不上。
      取舍：LICENSE 用 GitHub 模板（保证识别），GPL 全文以引用方式说明。
"""

import io
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CACHE = os.path.join(os.environ.get("TEMP", "/tmp"), "gl_lic")
LICENSE = os.path.join(ROOT, "LICENSE")

HDRS = {"User-Agent": "glesmod-verify", "Accept": "application/vnd.github+json"}


def main():
    cur = io.open(LICENSE, encoding="utf-8").read()
    print("本地 LICENSE : %d 字节, %d 行"
          % (len(cur.encode("utf-8")), cur.count("\n")))

    req = urllib.request.Request("https://api.github.com/licenses/lgpl-3.0",
                                 headers=HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        t = json.loads(r.read().decode("utf-8"))
    body = t["body"]
    print("GitHub 模板  : %d 字节, %d 行   spdx=%s"
          % (len(body.encode("utf-8")), body.count("\n"), t.get("spdx_id")))
    print()
    print("与 GitHub 模板逐字节相同 : %s" % ("是 ✓" if cur == body else "否 ✗"))

    gnu = os.path.join(CACHE, "lgpl-3.0.txt")
    if os.path.isfile(gnu):
        g = io.open(gnu, encoding="utf-8").read()
        print("与 gnu.org 文本相同      : %s" % ("是 ✓" if cur == g else "否"))

    # 关键短语复核
    print()
    print("--- 关键短语 ---")
    for p in ("GNU LESSER GENERAL PUBLIC LICENSE",
              "Version 3, 29 June 2007",
              "This version of the GNU Lesser General Public License incorporates",
              "https://www.gnu.org/licenses/why-not-lgpl.html"):
        print("  %-62s %s" % (p[:62], "存在" if p in cur else "缺失"))

    # 确认旧的旧版残留已清除
    print()
    print("--- 旧版残留检查（应全部为「已清除」）---")
    for p in ("http://fsf.org/", "http://www.gnu.org/licenses/",
              "philosophy/why-not-lgpl.html"):
        print("  %-40s %s" % (p, "**仍在**" if p in cur else "已清除"))

    print()
    ok = cur == body
    print("verdict: %s" % ("PASS —— LICENSE 与 GitHub 模板完全一致，识别器应当匹配"
                          if ok else "FAIL —— 仍有差异"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
