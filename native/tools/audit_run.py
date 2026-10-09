#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit the GLESmod logs for remaining compatibility gaps.

No CLI arguments on purpose: the VS Code task-runner shell mangles quotes,
pipes and parentheses in filenames, so we just glob the cwd ourselves.

Reports, per log file:
  * how many times each known driver complaint appears
  * whether our depth-format translation actually fired
  * the depth-attachment / readback probe results
  * the GL debug message inventory (grouped)

Usage:
    py native\\tools\\audit_run.py
"""
import glob
import os
import re
import sys
from collections import Counter

PATS = [
    ("depth_format_err", r"the combination of format 6402"),
    ("depth_translated", r"深层格式已翻译"),
    ("swizzle_g_err", r"pname 34049"),
    ("pixel_format_err", r"pixel buffer format is not compatible"),
    ("tri_lt_3_err", r"unable to generate a triangle primitive"),
    ("attachemnt_err", r"cannot have attachemnts"),
    ("ns_collision", r"Namespace collision"),
    ("depth_readback", r"深度回读"),
    ("attach_depth", r"附件 DEPTH\b"),
    ("attach_selfcheck", r"深度附件自证"),
    ("depth_texture", r"深度纹理:"),
    ("probe_banner", r"几何诊断探针 v\d"),
    ("degrade", r"降级: "),
]

CONTEXT = [
    "深度回读",
    "深度附件自证",
    "附件 DEPTH ",
    "深度纹理:",
    "深层格式已翻译",
]

GLMSG = re.compile(r"OpenGL debug message:.*message='([^']*)'")
GLMSG_INT = re.compile(r"^\[probe\]|^\[GLESMod\]")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    files = sorted(glob.glob("*.log"))
    if not files:
        print("no .log files found in", os.getcwd())
        return 1

    for fn in files:
        counts = Counter()
        glmsgs = Counter()
        ctx_lines = []
        try:
            with open(fn, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    for name, pat in PATS:
                        if re.search(pat, line):
                            counts[name] += 1
                    m = GLMSG.search(line)
                    if m:
                        glmsgs[m.group(1)[:90]] += 1
                    if any(c in line for c in CONTEXT):
                        ctx_lines.append(line.rstrip()[:200])
        except OSError as e:
            print(fn, "!! cannot read:", e)
            continue

        print("=" * 78)
        print("FILE:", fn, " (%.1f MB)" % (os.path.getsize(fn) / 1048576.0))
        print("=" * 78)
        for name, _ in PATS:
            if counts[name]:
                print("  %-18s %6d" % (name, counts[name]))
        if glmsgs:
            print("  --- GL debug messages (top) ---")
            for msg, n in glmsgs.most_common(8):
                print("      %6d  %s" % (n, msg))

        if ctx_lines:
            print("  --- probe / depth context (last 14) ---")
            for l in ctx_lines[-14:]:
                print("      " + l)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
