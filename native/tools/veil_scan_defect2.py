#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does defect 2 (int literal in a user-function call gets float-ized) actually
fire on Veil's real sources?

Defect 2 (minimal repro):
    float c(int n) { return float(n)/16.0; }
    void main() { o = vec4(c(1), 1.0); }   // c(1) becomes c(1.0) -> ES error

It needs a USER-DEFINED function with an int parameter, called with a bare int
literal, from inside a constructor or arithmetic expression.

This script lists those call sites so we can decide whether the defect is
theoretical or real for Veil.

LGPL-3.0-or-later
"""
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

SRC = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "veil-src")

SIG = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"\s*\(([^)]*)\)\s*\{", re.M)
INT_PARAM = re.compile(r"^(int|ivec[234]|uint|uvec[234]|bool)\b")


def main():
    files = [f for f in glob.glob(os.path.join(SRC, "*")) if os.path.isfile(f)]
    files += glob.glob(os.path.join(SRC, "include", "*.glsl"))

    intfn = {}
    for f in files:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        for m in SIG.finditer(t):
            name, params = m.group(1), m.group(2)
            plist = [p.strip() for p in params.split(",") if p.strip()]
            if any(INT_PARAM.match(p) for p in plist):
                # the function must be USER-DEFINED, i.e. not a GLSL builtin
                intfn.setdefault(name, set()).update(plist)

    print("用户自定函数（含 int 族形参）: %d 个" % len(intfn))
    for k in sorted(intfn):
        print("    %-34s (%s)" % (k, ", ".join(sorted(intfn[k]))))

    print()
    print("以【裸 int 字面量】调用这些函数的点:")
    callsite = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([^()]*)\)")
    bare = re.compile(r"(?<![\w.])[0-9]+(?![.\w])")

    hits = []
    for f in files:
        for i, line in enumerate(
                io.open(f, encoding="utf-8", errors="replace").read()
                .splitlines(), 1):
            for m in callsite.finditer(line):
                if m.group(1) not in intfn:
                    continue
                if bare.search(m.group(2)):
                    hits.append((os.path.basename(f), i, line.strip()))

    for h in hits:
        print("    %s:%d  %s" % (h[0], h[1], h[2][:120]))
    print("    合计 %d 处" % len(hits))

    print()
    print("判定:", "Veil 真实触发缺陷 2" if hits else
          "Veil 未触发缺陷 2（仅理论风险）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
