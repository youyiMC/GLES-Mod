#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""show_device_fix_diff.py -- 打印真机夹具里 textureSize 相关行的改动。

为什么要单独做：
  verify_device_fixtures.py 里用 zip(a,b) 逐行对比，一旦我们**插入**了行
  （本修复会插入 vec2(...) 包装），行号整体错位，diff 就全是噪声、
  一条也打不出来。所以这里按“关键词定位 + 上下文打印”的方式核对，
  确保改动确实落在 textureSize 上，而不是别的地方。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache", "device_fixtures")
KEYS = ("textureSize", "texelFetch", "imageSize")

for name in ("device_57.frag", "device_101.frag"):
    es = os.path.join(CACHE, name + ".raw_es")
    conv = os.path.join(CACHE, name + ".conv")
    if not (os.path.isfile(es) and os.path.isfile(conv)):
        print("(缺文件) %s" % name)
        continue
    a = io.open(es, encoding="utf-8", errors="replace").read().splitlines()
    b = io.open(conv, encoding="utf-8", errors="replace").read().splitlines()

    print("=" * 92)
    print("%s   raw_es=%d 行   conv=%d 行" % (name, len(a), len(b)))
    print("=" * 92)

    # 收集两侧所有含关键词的行（不带行号，便于乱序对齐）
    ka = [(i + 1, l.strip()) for i, l in enumerate(a) if any(k in l for k in KEYS)]
    kb = [(i + 1, l.strip()) for i, l in enumerate(b) if any(k in l for k in KEYS)]

    print("--- raw_es（只换头，未转换）---")
    for n, l in ka:
        print("  %4d: %s" % (n, l[:150]))
    print()
    print("--- conv（我们的输出）---")
    for n, l in kb:
        print("  %4d: %s" % (n, l[:150]))
    print()

    # 逐条判断是否“实质变化”
    print("--- 判定 ---")
    for (na, la) in ka:
        # 找 conv 侧最相似的一条
        best, bd = None, 99
        for (nb, lb) in kb:
            d = sum(1 for c1, c2 in zip(la, lb) if c1 != c2) + abs(len(la) - len(lb))
            if d < bd:
                bd, best = d, (nb, lb)
        if best is None:
            print("  raw %d: 在 conv 里找不到对应行！" % na)
        elif la == best[1]:
            print("  未改动 : %s" % la[:120])
        else:
            print("  已改动 :")
            print("     raw  : %s" % la[:130])
            print("     conv : %s" % best[1][:130])
    print()
