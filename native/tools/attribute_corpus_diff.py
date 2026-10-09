#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attribute the corpus diff: show WHAT changed, so we can tell which edits are
ours and which predate this session.

`corpus-before` is an OLD baseline (pre-RuleP), so a nonzero CHANGED count does
not by itself implicate the current change. The only honest test is to read the
diffs and judge each one.

LGPL-3.0-or-later
"""
import difflib
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BASE = os.path.join(ROOT, "corpus-before")
NOW = os.path.join(ROOT, "corpus-rulesNOP")

# Only the .conv files that survived the diff, plus their source names.
TARGETS = [
    "bsl7/001_deferred1.fsh.conv",
    "bsl7/012_sky_basic.fsh.conv",
    "bsl7/013_sky_basic_color.fsh.conv",
    "mccore/assets__minecraft__shaders__program__transparency.fsh.conv",
]


def main():
    for t in TARGETS:
        a = os.path.join(BASE, t)
        b = os.path.join(NOW, t)
        print("=" * 78)
        print(t)
        print("=" * 78)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            print("  missing: %s" % ("base" if not os.path.isfile(a) else "now"))
            continue
        A = io.open(a, encoding="utf-8", errors="replace").read().splitlines()
        B = io.open(b, encoding="utf-8", errors="replace").read().splitlines()
        n = 0
        for line in difflib.unified_diff(A, B, "before", "now",
                                         lineterm="", n=1):
            if line.startswith(("---", "+++")):
                continue
            print("  " + line[:170])
            n += 1
        if n == 0:
            print("  (identical)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
