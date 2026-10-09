#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diff the real-device raw vs converted shader, then validate the converted
one with real glslang to get the exact remaining GLSL ES error.

This uses the actual failing shader extracted from the device log
(native/tools/extract_shader_from_log.py), so it is ground truth, not a guess.
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(HERE, ".cache", "fromlog")
RAW = os.path.join(CACHE, "shader_raw.vert")
CONV = os.path.join(CACHE, "shader_reconverted.vert")   # 用当前代码重新转换

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

CLI_SRC = os.path.join(HERE, "convert_shader_cli.c")
CLI_EXE = os.path.join(CACHE, "convert_shader_cli.exe")
SHADER_C = os.path.join(ROOT, "native", "src", "shader.c")

if not os.path.isfile(RAW):
    print("missing extracted shader; run extract_shader_from_log.py first")
    sys.exit(1)

# --- Rebuild the converter from CURRENT sources (never trust a stale exe) ---
print("=" * 74)
print("[0] 用当前源码重新编译转换器 CLI")
print("=" * 74)
r = subprocess.run(
    [GCC, "-O1", "-std=c11", "-o", CLI_EXE, CLI_SRC, SHADER_C,
     "-I", os.path.join(ROOT, "native", "include")],
    capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode != 0:
    print("CLI build FAILED:\n", r.stdout or "", r.stderr or "")
    sys.exit(1)
print("OK ->", CLI_EXE)

# --- Re-convert the REAL device shader with the CURRENT converter ---
print()
print("[1] 用当前转换器重新转换【设备上的真实源码】")
r = subprocess.run([CLI_EXE, RAW, "vertex", CONV],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace")
if r.returncode != 0 or not os.path.isfile(CONV):
    print("convert FAILED rc=%d" % r.returncode)
    print(r.stdout or "", r.stderr or "")
    sys.exit(1)
print("OK ->", CONV)

raw = open(RAW, encoding="utf-8", errors="replace").read().splitlines()
conv = open(CONV, encoding="utf-8", errors="replace").read().splitlines()

print("=" * 74)
print("行数: raw=%d  converted=%d" % (len(raw), len(conv)))
print("=" * 74)

# Show only the lines that differ in *content* (ignoring the 2 added header
# lines our converter prepends).
import difflib
sm = difflib.SequenceMatcher(None, raw, conv, autojunk=False)
print("转换器实际改动的地方：")
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    print("-" * 74)
    print("  [%s] raw[%d:%d] -> conv[%d:%d]" % (tag, i1, i2, j1, j2))
    for k in range(i1, i2):
        print("   raw %4d| %s" % (k, raw[k]))
    for k in range(j1, j2):
        print("   cvt %4d| %s" % (k, conv[k]))

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")


def check(path, stage="vert"):
    r = subprocess.run(
        [GLSlC, "--target-env=opengl", "-fshader-stage=" + stage, path,
         "-o", path + ".spv"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    msgs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        if ln.strip().split() and ln.strip().split()[0].isdigit() \
                and "generated" in ln:
            continue
        msgs.append(ln.strip())
    return r.returncode, msgs, (r.stderr or "")


print()
print("=" * 74)
print("用真实 glslang 编译【设备上送进驱动的源码】")
print("=" * 74)
rc, msgs, raw_err = check(CONV)
if not msgs and rc == 0:
    print("  无 GLSL ES 错误 —— 与真机不符，需检查提取是否完整")
else:
    for m in msgs:
        print("  %s" % m[:170])
    if not msgs:
        print("  (只剩 SPIR-V 噪声；真实错误可能在下面)")
        for ln in raw_err.splitlines():
            if ln.strip():
                print("   RAW %s" % ln.strip()[:170])

# Also try the raw one for contrast
print()
print("=" * 74)
print("对照：直接编译【设备收到的原始源码】（桌面写法，预期失败）")
print("=" * 74)
rc2, msgs2, _ = check(RAW)
for m in msgs2[:6]:
    print("  %s" % m[:170])
