#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_device_fixtures.py -- 用真机失败的着色器验证缺陷 A/B 的修复。

这是本轮修复的**权威验收**：夹具不是人造探针，而是 native.log 里
Simulated 实际送进来的源码（`device_57.frag` / `device_101.frag`
对应 latest.log 里那两条 Veil 编译失败）。

归因基准仍用 raw_es（只换头、不转换），判据：
    raw_es PASS + conv FAIL -> 回归（我们改坏了）
    raw_es FAIL + conv PASS -> 我们修对了
    raw_es FAIL + conv FAIL -> 漏修 / 仍有别的错
    raw_es PASS + conv PASS -> 无问题
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
CACHE = os.path.join(HERE, ".cache", "device_fixtures")
GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
CLI = os.path.join(CACHE, "cli.exe")

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

ES_HEADER = ("#version 320 es\n"
             "precision highp float;\n"
             "precision highp int;\n"
             "precision highp sampler2D;\n")


def build_cli():
    os.makedirs(CACHE, exist_ok=True)
    r = subprocess.run(
        [GCC, "-O2", "-std=c11", "-Wall",
         "-I", os.path.join(ROOT, "native", "src"),
         "-I", os.path.join(ROOT, "native", "include"),
         "-o", CLI,
         os.path.join(HERE, "convert_shader_cli.c"),
         os.path.join(ROOT, "native", "src", "shader.c"), "-lm"],
        capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print("BUILD FAILED")
        print(r.stdout)
        print(r.stderr)
        return False
    warn = [l for l in (r.stderr or "").splitlines() if "warning:" in l]
    print("build OK  (warnings: %d)" % len(warn))
    for w in warn[:8]:
        print("   ", w.strip())
    return True


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


def make_raw_es(text):
    out = []
    for ln in text.splitlines():
        st = ln.strip()
        if st.startswith("#version") or re.match(r"^\s*precision\s+", ln):
            continue
        out.append(ln)
    return ES_HEADER + "\n".join(out).lstrip("\n") + "\n"


def short(e):
    return e.split("error:")[-1].strip()[:130] if "error:" in e else e[:130]


def main():
    if not build_cli():
        return 1

    names = sorted(f for f in os.listdir(FIXT)
                   if f.startswith("device_") and
                   (f.endswith(".frag") or f.endswith(".vert")))
    if not names:
        print("没有夹具")
        return 1

    print()
    print("=" * 96)
    print("%-22s %-9s %-9s %s" % ("夹具", "raw_es", "conv", "归因"))
    print("=" * 96)

    bad = 0
    for name in names:
        stage = "frag" if name.endswith(".frag") else "vert"
        raw = os.path.join(FIXT, name)
        es = os.path.join(CACHE, name + ".raw_es")
        conv = os.path.join(CACHE, name + ".conv")

        with io.open(es, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(make_raw_es(io.open(raw, encoding="utf-8",
                                         errors="replace").read()))

        subprocess.run([CLI, raw, "fragment" if stage == "frag" else "vertex",
                        conv], capture_output=True)

        es_errs = verdict(es, stage)
        conv_errs = verdict(conv, stage)
        es_ok, conv_ok = not es_errs, not conv_errs

        if es_ok and conv_ok:
            attr = "无问题"
        elif es_ok and not conv_ok:
            attr = "**回归：我们改坏了**"
            bad += 1
        elif not es_ok and conv_ok:
            attr = "我们修对了"
        else:
            attr = "**仍有错误**"
            bad += 1

        print("%-22s %-9s %-9s %s   (es错=%d conv错=%d)"
              % (name, "PASS" if es_ok else "FAIL", "PASS" if conv_ok else "FAIL",
                 attr, len(es_errs), len(conv_errs)))
        for e in conv_errs[:3]:
            print("      %s" % short(e))

        # 顺带打印我们相对 raw_es 做的**实质改写**，便于人工核对
        a = io.open(es, encoding="utf-8", errors="replace").read().splitlines()
        b = io.open(conv, encoding="utf-8", errors="replace").read().splitlines()
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        for x, y in diff[:6]:
            if any(k in x or k in y for k in ("textureSize", "texelFetch")):
                print("      - %s" % x.strip()[:110])
                print("      + %s" % y.strip()[:110])

    print()
    print("=" * 96)
    print("需人工确认的夹具数：%d" % bad)
    return 0


if __name__ == "__main__":
    sys.exit(main())
