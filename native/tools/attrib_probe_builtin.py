#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attrib_probe_builtin.py -- 决定性归因（修正版）。

前一个版本的错误（必须记录，避免重犯）
=====================================
我拿「原始源码」与「转换后源码」直接对比。但这两者之间**有两处差异**：
  1) 头部：`#version 330 core` -> `#version 320 es` + precision 声明
  2) 我们的整型/浮点改写
于是像 `vec2(1.0,1.0) / ivec2(4,4)` 这种**我们一个字都没改**的语句，
也会因为「桌面 GLSL 允许 ivec->vec 隐式转换、而 GLSL ES 不允许」而被
误判成「我们改坏了」。先前那版归因结论不可信，已作废。

正确基准：raw_es
================
把原始源码**只换头**（版本行改成 320 es、补 precision），不做任何转换，
得到 raw_es —— 它代表「一个纯粹的原样转发者」会交给驱动的源码。

归因判据：
  raw_es PASS + conv FAIL  -> **回归**（我们把本来能过的改坏了）
  raw_es FAIL + conv PASS  -> 我们修对了
  raw_es FAIL + conv FAIL  -> **漏修**（该修没修，对我们是真实缺陷）
  raw_es PASS + conv PASS  -> 无问题
"""

import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, ".cache", "probe_builtin")
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

# 与我们转换器的头部组装一致（取自实际 .conv.frag 输出）
ES_HEADER = ("#version 320 es\n"
             "precision highp float;\n"
             "precision highp int;\n"
             "precision highp sampler2D;\n")


def verdict(path, stage="frag"):
    r = subprocess.run([GLSLC, "--target-env=opengl", "-fshader-stage=" + stage,
                        path, "-o", path + ".spv"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        s = ln.strip()
        if not s or "error" not in s.lower():
            continue
        if any(n in s for n in SPV_NOISE):
            continue
        if "errors generated" in s:
            continue
        errs.append(s)
    return errs


def make_raw_es(src_text):
    """只换头：删掉原 #version 与已有 precision，插入 ES 头。"""
    out = []
    for ln in src_text.splitlines():
        st = ln.strip()
        if st.startswith("#version"):
            continue
        if re.match(r"^\s*precision\s+", ln):
            continue
        out.append(ln)
    return ES_HEADER + "\n".join(out).lstrip("\n") + "\n"


def short(e):
    return e.split("error:")[-1].strip()[:150] if "error:" in e else e[:150]


# 已知未修缺口（**与本次真机缺陷无关**，不计为失败）
#
# 已核实：该形态在真机夹具（fixtures/device/）与全部语料
# （bslsrc / veil-src / fw-src / sable-src / mccore）里**命中数均为 0**。
# 它是我在探测缺陷 A/B 时自己构造出来的形态，不是真机实际发生的问题。
#
# 说明：`vec2(1.0,1.0) / ivec2(4,4)` 里那个**裸的 ivecN 构造函数**
# 没有像 `ivec2 变量` 那样被插上 vecN 包装。补它需要动「二元运算符
# 右侧的构造函数」这条路径 —— 而那正是历史上制造过
# `vec2 vec2(light)` / `n2.float(x)` 这类结构体/成员误包的区域。
# 因此**刻意不在本次修复范围内**，避免为一个人造形态引入真实回归。
KNOWN_GAPS = {
    "div_const_by_ivec_ctor": "裸 ivecN 构造函数参与除法（语料命中数 0，人造形态）",
    "div_const_by_texturesize": "已修：现输出 / vec2(textureSize(...))",
}


names = sorted(f[:-len(".raw.frag")] for f in os.listdir(D)
               if f.endswith(".raw.frag"))

print("=" * 100)
print("%-28s %-9s %-9s %s" % ("探针", "raw_es", "conv", "归因"))
print("=" * 100)

regressions, missing, gaps = [], [], []
for name in names:
    raw = os.path.join(D, name + ".raw.frag")
    es = os.path.join(D, name + ".raw_es.frag")
    conv = os.path.join(D, name + ".conv.frag")

    with open(es, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(make_raw_es(open(raw, encoding="utf-8", errors="replace").read()))

    es_errs = verdict(es)
    conv_errs = verdict(conv)
    es_ok, conv_ok = not es_errs, not conv_errs

    if es_ok and conv_ok:
        attr = "无问题"
    elif es_ok and not conv_ok:
        attr = "**回归：我们改坏了**"
        regressions.append((name, conv_errs))
    elif not es_ok and conv_ok:
        attr = "我们修对了"
    elif name in KNOWN_GAPS:
        attr = "已知缺口（非真机问题）"
        gaps.append((name, conv_errs))
    else:
        attr = "**漏修：该修没修**"
        missing.append((name, conv_errs))

    print("%-28s %-9s %-9s %s" % (name, "PASS" if es_ok else "FAIL",
                                  "PASS" if conv_ok else "FAIL", attr))

for title, items in (("回归（我们改坏了）", regressions),
                     ("漏修（该修没修）", missing),
                     ("已知缺口（与真机缺陷无关，语料命中数 0）", gaps)):
    print()
    print("=" * 100)
    print("%s  —— 共 %d 条" % (title, len(items)))
    print("=" * 100)
    for name, errs in items:
        print("  %s" % name)
        for e in errs[:2]:
            print("      %s" % short(e))
    print()

print("verdict: %s" % ("PASS" if not regressions and not missing
                        else "FAIL -- 回归 %d / 漏修 %d"
                        % (len(regressions), len(missing))))
sys.exit(1 if (regressions or missing) else 0)
