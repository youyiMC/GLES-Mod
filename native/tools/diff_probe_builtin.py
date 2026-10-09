#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff_probe_builtin.py -- 精确对照每条探针的 ORIG vs CONV。

用途：把「我们改动的行」和「源本身就错的探针」严格分开。
我写的探针里有几条**源本身就是非法 GLSL**（例如 `vec2 sz = textureSize(...)`），
它们在桌面也同样失败 —— 那是我的探针问题，不是转换器缺陷。
不区分就会把假阳性当成缺陷报上去。
"""
import difflib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, ".cache", "probe_builtin")

# 对照组：源本身在桌面 GLSL 就非法，失败不可归因于我们
INVALID_SOURCE = {
    "textureSize_vec2_assign": "vec2 = textureSize() 桌面也不允许 int->vec2",
    "div_const_by_ivec_ctor": "vec2 / ivec2 桌面也不允许（我探针写错了）",
    "div_const_by_texturesize": "vec2 / textureSize() 同上",
}

names = sorted(f[:-len(".raw.frag")] for f in os.listdir(D)
               if f.endswith(".raw.frag"))

for name in names:
    raw = os.path.join(D, name + ".raw.frag")
    conv = os.path.join(D, name + ".conv.frag")
    a = open(raw, encoding="utf-8", errors="replace").read().splitlines()
    b = open(conv, encoding="utf-8", errors="replace").read().splitlines()

    # 只比较语句体（跳过 #version / precision / 声明等头部的插入）
    def body(L):
        out = []
        grab = False
        for ln in L:
            if ln.strip().startswith("void main"):
                grab = True
                continue
            if grab:
                out.append(ln.rstrip())
        while out and not out[-1].strip():
            out.pop()
        return out

    ab, bb = body(a), body(b)
    changes = [l for l in difflib.unified_diff(ab, bb, lineterm="", n=0)
               if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]

    tag = " [源本身非法]" if name in INVALID_SOURCE else ""
    print("=" * 74)
    print("%s%s" % (name, tag))
    if name in INVALID_SOURCE:
        print("  注: %s" % INVALID_SOURCE[name])
    if not changes:
        print("  转换器未改动任何语句")
    else:
        for c in changes:
            print("  %s" % c.strip()[:130])
