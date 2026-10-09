#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare the 10/5 vs today output for the exact corruption patterns.

`py -X utf8 -c "..."` keeps getting mangled by PowerShell's parser (parentheses
and quotes), so this lives in a file. Lesson recorded: use script files, never
inline python with parentheses, in this terminal.

LGPL-3.0-or-later
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, ".cache", "fw_dumps")

PAIRS = [("OLD 10/5", "06_raw.reconv.frag"), ("NEW today", "06_raw.fixed.frag")]
NEEDLES = ["vec2(light)", "flw_fragLight", "vec2 vec2(", "uvec2 light"]


def main():
    for label, name in PAIRS:
        p = os.path.join(D, name)
        print("=" * 70)
        print("%s  (%s)" % (label, name))
        print("=" * 70)
        if not os.path.isfile(p):
            print("  MISSING")
            continue
        lines = io.open(p, encoding="utf-8",
                        errors="replace").read().splitlines()
        found = False
        for i, l in enumerate(lines, 1):
            if any(n in l for n in NEEDLES):
                print("  %5d | %s" % (i, l.strip()[:130]))
                found = True
        if not found:
            print("  (no match)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
