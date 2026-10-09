#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install_github_license_template.py -- 安装 GitHub **自己**的许可证模板。

为什么这才是正解
================
此前的做法是「从 gnu.org 拉 LGPL + GPL 正文拼接」，那是**法律文本**，
但不一定是**识别模板**。GitHub 的许可证检测用的是
    GET https://api.github.com/licenses/<key>
返回的那份 `body`（同一份模板也用于网页上「Choose a license template」）。
两者排版不同，识别器对模板之外的形式并不保证匹配。

实测差异（这就是 NOASSERTION 的原因）：
    本地拼接件 (gnu.org LGPL+GPL) : 42801 字节
    SPDX LGPL-3.0-or-later 文本    : 42098 字节
    GitHub 自己的模板              : 见下方实测
三者互不相同 —— 只有最后一份才与检测器对齐。

关于占位符
==========
GitHub 的 `body` 里含有 `[year]` / `[fullname]` 之类占位符。
本项目不打算填写版权行到 LICENSE 正文（LGPL 正文本身不含项目版权行），
因此只做必要替换，其余保持模板原样。
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

HDRS = {
    "User-Agent": "glesmod-license-install",
    "Accept": "application/vnd.github+json",
}


def fetch_template(key):
    url = "https://api.github.com/licenses/%s" % key
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    os.makedirs(CACHE, exist_ok=True)

    # 先看看有哪些 LGPL 相关的 key
    print("=== 查询 GitHub 模板 ===")
    tmpl = None
    for key in ("lgpl-3.0", "lgpl-3.0-only", "lgpl-3.0-or-later"):
        try:
            t = fetch_template(key)
            body = t.get("body", "")
            print("  %-22s spdx=%-18s %d 字节  占位符=%s"
                  % (key, t.get("spdx_id"), len(body.encode("utf-8")),
                     t.get("conditions") is not None))
            if tmpl is None:
                tmpl = (key, t)
        except Exception as e:  # noqa: BLE001
            print("  %-22s 不可用: %s" % (key, e))

    if tmpl is None:
        print("FAIL: 拿不到任何模板")
        return 1

    key, t = tmpl
    body = t["body"]
    print()
    print("=== 选用模板: %s (spdx=%s) ===" % (key, t.get("spdx_id")))
    print("  名称    : %s" % t.get("name"))
    print("  字节数  : %d" % len(body.encode("utf-8")))
    print("  行数    : %d" % body.count("\n"))

    # 占位符检查
    import re
    ph = sorted(set(re.findall(r"\[[a-z ]+\]", body)))
    print("  占位符  : %s" % (ph if ph else "无"))
    print()
    print("--- 前 6 行 ---")
    for i, l in enumerate(body.split("\n")[:6], 1):
        print("  %2d: %r" % (i, l[:100]))

    # 保存模板原文备查
    tp = os.path.join(CACHE, "github_template_%s.txt" % key)
    with io.open(tp, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    print()
    print("模板已存: %s" % tp)

    # 与当前 LICENSE 比对
    cur = io.open(LICENSE, encoding="utf-8").read()
    print()
    print("=== 与当前 LICENSE 比对 ===")
    print("  当前 LICENSE 字节数 : %d" % len(cur.encode("utf-8")))
    print("  模板字节数          : %d" % len(body.encode("utf-8")))
    print("  完全相同            : %s" % (cur == body))

    if cur == body:
        print()
        print("当前 LICENSE 已与 GitHub 模板一致，无需替换。")
        print("若 GitHub 仍报 NOASSERTION，则是异步扫描延迟，只需等待。")
        return 0

    # 替换
    backup = os.path.join(CACHE, "LICENSE.before-github-template")
    with io.open(backup, "w", encoding="utf-8", newline="") as fh:
        fh.write(cur)
    print("  原文件已备份        : %s" % backup)

    with io.open(LICENSE, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    chk = io.open(LICENSE, encoding="utf-8").read()
    print()
    print("已用 GitHub 模板覆盖 LICENSE，读回校验: %s"
          % ("一致" if chk == body else "**不一致**"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
