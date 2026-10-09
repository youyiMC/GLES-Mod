#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan every converted shader for wrap-inside-subscript, which is ALWAYS a bug.

Why this specific check
-----------------------
The predicate used by 情形 C/E/B is "this name is an int operand". When a name
is *also* used as an array subscript (BSL's `moonDiffuse[moonPhase]`, where the
same identifier is a float in one scope and an index in another), a wrong
verdict produces

    moonDiffuse[float(moonPhase)]      // GLSL ES: array subscript must be int

which glslang only rejects once the code path is compiled -- and it is illegal
in descriptor GLSL too, so it is unambiguously our bug, not a target difference.

This scans the whole converted corpus for `[` immediately followed by a
float/vec constructor. Those are hard failures wherever they appear.

LGPL-3.0-or-later
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

ROOTS = ["corpus-rulesNOP", "corpus-before"]

# `[float(` / `[ vec3(` / `[vec3(` -- subscript wrapped in a FLOAT or FLOAT-VECTOR
# constructor. Those are hard failures: a GLSL ES array subscript must be int.
#
# Deliberately NOT matched: `[int(...)]` and `[uint(...)]`. Those are the
# CORRECT output (the converter promoting an integer index), and BSL's
#     u_chunkFades[int(_draw_id) >> 2][int(_draw_id) & 3]
# is exactly that case. An earlier, over-broad version flagged them and made
# the gate cry wolf -- worth remembering: a gate that fires on correct output
# is worse than no gate, because it trains you to ignore it.
BAD = re.compile(r"\[\s*(float|vec[234])\s*\(")


def main():
    total = 0
    for root in ROOTS:
        d = os.path.join(ROOT, root)
        if not os.path.isdir(d):
            print("[skip] %s" % d)
            continue
        print("=" * 74)
        print(root)
        print("=" * 74)
        hits = 0
        for dirpath, _, files in os.walk(d):
            for f in files:
                if not f.endswith(".conv"):
                    continue
                p = os.path.join(dirpath, f)
                for i, line in enumerate(
                        io.open(p, encoding="utf-8", errors="replace")
                        .read().splitlines(), 1):
                    if BAD.search(line):
                        rel = os.path.relpath(p, d)
                        print("  %s:%d  %s" % (rel, i, line.strip()[:130]))
                        hits += 1
        print("  命中: %d" % hits)
        if root == "corpus-rulesNOP":
            total = hits
        print()
    print("结论:", "无下标内包裹（正确）" if total == 0
          else "!! 发现 %d 处下标内包裹 —— 会让 ES 数组下标非法" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
