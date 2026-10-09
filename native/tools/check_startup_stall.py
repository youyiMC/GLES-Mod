#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_startup_stall.py -- 量化「着色器编译失败」是否拖慢了启动。

观察：三次日志里，`Finished uploading vanilla shaders` 与
`Created 157 recipes` 之间存在一段空档，长度随失败数变化。

  14:20 那次（2 个失败）：14:20:08 -> 14:20:11
  21:23 那次（2 个失败）：21:23:46 -> 21:24:25   <-- 明显异常
  21:33 那次（0 个失败）：21:34:02 -> 21:34:05

若确实相关，修复就同时消除了一个启动期卡顿。
这里**只报数据，不推测因果** —— 空档也可能由首次资源加载、JIT 等引起。
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
# 实际时间戳形如 [0910月2026 21:34:02.634]（日期在前、带中文「月」），
# 而不是 [21:34:02.634]。最初按后者写，导致一条都对不上、两个锚点全 None。
TS = re.compile(r"^\[\d+月\d+\s+(\d\d):(\d\d):(\d\d)\.(\d+)\]")


def secs(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def scan(path):
    if not os.path.isfile(path):
        return None
    a = b = None
    nfail = 0
    nerr = 0
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        m = TS.match(ln)
        t = secs(*m.groups()) if m else None
        if "Finished uploading vanilla shaders" in ln and a is None:
            a = t
        if "Created 157 recipes" in ln and b is None and a is not None:
            b = t
        if "Failed to create shader" in ln:
            nfail += 1
        if re.search(r"^\s*ERROR: \d+:\d+:", ln):
            nerr += 1
    return a, b, nfail, nerr


for name in ("latest.log", "latest(1).log", "latest(2).log"):
    p = os.path.join(ROOT, name)
    r = scan(p)
    print("=" * 76)
    print(name)
    if r is None:
        print("  (文件不存在)")
        continue
    a, b, nfail, nerr = r
    print("  着色器编译失败数 : %d   驱动错误行: %d" % (nfail, nerr))
    if a is None or b is None:
        print("  找不到时间锚点（a=%s b=%s）" % (a, b))
    else:
        print("  空档: %.1f s  (%.1f -> %.1f)" % (b - a, a, b))
