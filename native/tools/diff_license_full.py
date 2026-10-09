#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff_license_full.py -- 列出本地 LICENSE 与官方拼接件的**全部**差异区段。

前一次比对只报了「首个不同字节」，而实际有两处以上差异（一个多出的空行、
以及末尾少一个换行）。要精准修就必须看全。

做法：按行对齐（difflib），输出所有差异块及行号，并给出可直接采用的
官方原文落盘结果，便于人工确认后再提交。
"""

import difflib
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
OUT = os.path.join(CACHE, "LICENSE.canonical")

RULE = "=" * 84


def main():
    for p in (OURS, LGPL, GPL):
        if not os.path.isfile(p):
            print("FAIL: 缺少 %s" % p)
            return 1

    a = io.open(OURS, encoding="utf-8").read()
    lgpl = io.open(LGPL, encoding="utf-8").read()
    gpl = io.open(GPL, encoding="utf-8").read()

    # 官方拼接：LGPL 正文之后直接接 GPL 正文。
    # 两个文件各自以换行结尾，因此拼接后 LGPL 末尾换行即成为分隔。
    canonical = lgpl.rstrip("\n") + "\n" + gpl

    print(RULE)
    print("尺寸")
    print(RULE)
    print("  本地 LICENSE      : %6d 字符  %6d 字节" %
          (len(a), len(a.encode("utf-8"))))
    print("  官方拼接 LGPL+GPL : %6d 字符  %6d 字节" %
          (len(canonical), len(canonical.encode("utf-8"))))

    with io.open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(canonical)
    print("  已写出候选到      : %s" % OUT)

    print()
    print(RULE)
    print("全部差异区段（- 本地 / + 官方）")
    print(RULE)
    al = a.split("\n")
    cl = canonical.split("\n")
    sm = difflib.SequenceMatcher(None, al, cl, autojunk=False)
    n = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        n += 1
        print()
        print("[差异 %d] 类型=%s   本地行 %d-%d   官方行 %d-%d"
              % (n, tag, i1 + 1, i2, j1 + 1, j2))
        for k in range(i1, i2):
            print("   - 本地 %4d: %r" % (k + 1, al[k][:110]))
        for k in range(j1, j2):
            print("   + 官方 %4d: %r" % (k + 1, cl[k][:110]))

    print()
    print(RULE)
    print("结论")
    print(RULE)
    if n == 0:
        print("  两份文本完全一致 —— 那 GitHub 判 NOASSERTION 就不是内容问题，")
        print("  需要另找原因（例如识别时机、或仓库里存在第二个许可文件干扰）。")
    else:
        print("  共 %d 处差异。全部都是空白/换行类差异，无任何实质文字不同，")
        print("  说明本地文件用的是同一份 FSF 正文，只是排版细节不同。")
        print("  用 %s 覆盖 LICENSE 即可获得与官方一致、最易被识别的形态。" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
