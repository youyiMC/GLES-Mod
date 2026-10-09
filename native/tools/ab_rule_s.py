#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ab_rule_s.py -- A/B 对照：证明缺陷 A/B 的修复确由新代码带来。

为什么一定要做
==============
「修完就 PASS」不能证明是我们修好的 —— 也可能是夹具本身早就没问题。
本仓库的标准做法是**对照构建**：用 -DGLESMOD_NO_RULE_S 关掉本规则，
同一批夹具再跑一遍。预期：
    关闭 -> 真机那两个 fixture 重新出现原错误（文本应与 native.log 一致）
    打开 -> PASS
两者都成立，才能把「修复」归因到这段代码。

顺带核对：错误文本要与 native.log 里驱动原话对得上，
否则说明我们复现的机制不对。
"""

import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIXT = os.path.join(HERE, "fixtures", "device")
CACHE = os.path.join(HERE, ".cache", "ab_rule_s")
GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

TARGETS = ["device_57.frag", "device_101.frag"]


def build(tag, extra):
    exe = os.path.join(CACHE, "cli_%s.exe" % tag)
    r = subprocess.run(
        [GCC, "-O2", "-std=c11"] + extra +
        ["-I", os.path.join(ROOT, "native", "src"),
         "-I", os.path.join(ROOT, "native", "include"),
         "-o", exe, os.path.join(HERE, "convert_shader_cli.c"),
         os.path.join(ROOT, "native", "src", "shader.c"), "-lm"],
        capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("BUILD FAILED (%s)" % tag)
        print(r.stderr[:2000])
        return None
    return exe


def verdict(path, stage):
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


def short(e):
    return e.split("error:")[-1].strip()[:120] if "error:" in e else e[:120]


def main():
    os.makedirs(CACHE, exist_ok=True)

    print("编译两个对照构建 ...")
    on = build("on", [])
    off = build("off", ["-DGLESMOD_NO_RULE_S"])
    if on is None or off is None:
        return 1
    print("  ok\n")

    for name in TARGETS:
        stage = "frag" if name.endswith(".frag") else "vert"
        src = os.path.join(FIXT, name)
        print("=" * 92)
        print(name)
        print("=" * 92)
        for tag, exe in (("规则S 关闭", off), ("规则S 开启", on)):
            out = os.path.join(CACHE, "%s.%s.conv" % (name, tag.replace(" ", "")))
            subprocess.run([exe, src, "fragment" if stage == "frag" else "vertex",
                            out], capture_output=True)
            errs = verdict(out, stage)
            print("  %-10s -> %s" % (tag, "PASS" if not errs else
                                     "FAIL (%d 条)" % len(errs)))
            for e in errs[:4]:
                print("        %s" % short(e))
            # 打印 textureSize 相关行的实际形态，直观对比
            for ln in io.open(out, encoding="utf-8",
                              errors="replace").read().splitlines():
                if "textureSize" in ln and "/" in ln:
                    print("        | %s" % ln.strip()[:120])
                    break
        print()


if __name__ == "__main__":
    sys.exit(main())
