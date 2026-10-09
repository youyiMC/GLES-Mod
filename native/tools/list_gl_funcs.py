#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""list_gl_funcs.py -- 统计光影包里出现的函数调用名，找出我们尚未映射的旧式函数。

用法:
    py native\\tools\\list_gl_funcs.py            # 全部
    py native\\tools\\list_gl_funcs.py texture    # 只看含 texture 的
"""
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent
CALL_RE = re.compile(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*\(')


def main():
    filt = sys.argv[1] if len(sys.argv) > 1 else ""
    zips = sorted(ROOT.glob("BSL*.zip"))
    if not zips:
        raise SystemExit("!! 没有 BSL*.zip")

    c = Counter()
    with zipfile.ZipFile(zips[-1]) as zf:
        for n in zf.namelist():
            if not n.lower().endswith((".fsh", ".vsh", ".glsl", ".inc")):
                continue
            txt = zf.read(n).decode("utf-8", "replace")
            for m in CALL_RE.finditer(txt):
                name = m.group(1)
                if filt and filt not in name.lower():
                    continue
                c[name] += 1

    for name, n in c.most_common():
        print("%6d  %s" % (n, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
