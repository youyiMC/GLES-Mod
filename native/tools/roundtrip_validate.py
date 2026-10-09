#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round-trip gate: convert FIRST-HAND shader fixtures with OUR converter,
then validate the output with real glslang.

Why this gate exists
--------------------
Our converter only learns about a GLSL-ES-vs-desktop difference when it bites
us on a real device. That is a slow and expensive feedback loop - entering the
world crashed several times before Sodium's chunk shader was fixed.

Two things make this gate much stronger than hand-written assertions:
  1. The fixtures are REAL shaders (extracted from device logs), not
     approximations of them. Approximations missed the bug twice: I had
     written a Sodium-like sample by hand, it passed, and the device still
     crashed because the real file had an additional pattern
     (`uvec3 * float-scalar-variable`).
  2. The verdict comes from glslang (the real GLSL ES front end in the Android
     NDK), not from our own rules. Our rules cannot catch a rule we have not
     implemented yet; glslang applies the whole ES type system.

Caveat on the verdict: glslc always emits SPIR-V, so it also reports
Vulkan-only requirements (layout(location) on non-opaque uniforms, etc.) and
exits non-zero for those. For an OpenGL/ES target those are irrelevant, so we
judge by whether any GLSL error remains AFTER filtering SPIR-V noise.

Self-locating; rebuilds the CLI from current sources every run
(lesson: never trust a stale binary - it once sent me chasing a fixed bug).
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIXTURES = os.path.join(HERE, "fixtures")
TMP = os.path.join(HERE, ".cache", "roundtrip")
os.makedirs(TMP, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

CLI_SRC = os.path.join(HERE, "convert_shader_cli.c")
CLI_EXE = os.path.join(TMP, "convert_shader_cli.exe")
SHADER_C = os.path.join(ROOT, "native", "src", "shader.c")
INCLUDE = os.path.join(ROOT, "native", "include")

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

# Fixtures that PROVOKE a converter gap we have not fixed yet.
#
# They stay in fixtures/ on purpose: they are the executable record of a
# known defect, and they must NOT be deleted just to make this gate green.
# The gate is bidirectional:
#   - still failing  -> reported as KNOWN-UNFIXED, does not fail the build
#   - now passing    -> HARD ERROR, because the defect is fixed and this
#                       entry (plus the reason to keep the fixture) is stale
#
# Entries are (name -> reason). Keep the reason SPECIFIC: it is what tells a
# future reader whether the fixture is still meaningful.
#
# Currently empty, for the second time. The last entry
# (probe_scope_alias_arith.frag) was FIXED by dropping ambiguous names from the
# float-variable table: a name that is `int` in one scope and `float` in another
# can no longer be used to wrap an integer operand, so
#     int add(int a, int b) { return a + b; }
# stays untouched instead of becoming `return float(a) + b;`.
# The gate flagged the stale entry exactly as designed.
KNOWN_UNFIXED = set()


def build_cli():
    r = subprocess.run(
        [GCC, "-O1", "-std=c11", "-o", CLI_EXE, CLI_SRC, SHADER_C,
         "-I", INCLUDE],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("CLI build FAILED:")
        print(r.stdout or "", r.stderr or "")
        sys.exit(1)


def glslang(path, stage):
    """Return (rc, glsl_errors) with SPIR-V noise removed."""
    r = subprocess.run(
        [GLSlC, "--target-env=opengl", "-fshader-stage=" + stage, path,
         "-o", path + ".spv"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        if "error" not in ln.lower():
            continue
        if any(n in ln for n in SPV_NOISE):
            continue
        if ln.strip().split() and ln.strip().split()[0].isdigit() \
                and "generated" in ln:
            continue
        errs.append(ln.strip())
    return r.returncode, errs


def wrap_as_es(src):
    """Force ES version + precision so we can show the original idiom is
    genuinely illegal under GLSL ES."""
    body = src.split("\n", 1)[1] if src.startswith("#version") else src
    pre = ("#version 320 es\n"
           "precision highp float;\nprecision highp int;\n"
           "precision highp sampler2D;\nprecision highp isamplerBuffer;\n")
    return pre + body


def main():
    print("=" * 74)
    print("[1] 用当前源码重新编译转换器 CLI（绝不复用旧二进制）")
    print("=" * 74)
    build_cli()
    print("OK ->", CLI_EXE)

    fixtures = sorted(f for f in os.listdir(FIXTURES)
                      if f.endswith((".vert", ".frag", ".vsh", ".fsh")))
    if not fixtures:
        print("no fixtures found in", FIXTURES)
        return 1

    total_ok = 0
    total_bad = 0
    known_still_broken = []
    known_now_fixed = []

    print()
    print("=" * 74)
    print("[2] 真实着色器往返验证（转换 -> glslang）")
    print("=" * 74)

    for name in fixtures:
        stage = "vert" if name.endswith((".vert", ".vsh")) else "frag"
        src_path = os.path.join(FIXTURES, name)
        src = open(src_path, encoding="utf-8", errors="replace").read()

        out_path = os.path.join(TMP, name + ".converted")
        es_path = os.path.join(TMP, name + ".as_es")

        print()
        print("-" * 74)
        print("夹具 %s   (阶段=%s)" % (name, stage))
        print("-" * 74)

        # (a) prove the original is NOT valid ES as-is
        with open(es_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(wrap_as_es(src))
        rc_in, err_in = glslang(es_path, stage)
        if rc_in != 0 and err_in:
            print("  [原码按 ES 编译]  非法（预期）—— 证明它是桌面专属写法")
            for m in err_in[:3]:
                print("      %s" % m[:150])
        else:
            print("  [原码按 ES 编译]  合法 —— 该夹具不构成 ES 差异（作回归保护）")

        # (b) run OUR converter
        r = subprocess.run(
            [CLI_EXE, src_path,
             "vertex" if stage == "vert" else "fragment", out_path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if r.returncode != 0 or not os.path.isfile(out_path):
            print("  [转换]            失败 rc=%d" % r.returncode)
            print(r.stdout or "", r.stderr or "")
            total_bad += 1
            continue
        print("  [转换]            成功")

        # (c) the output MUST be GLSL-ES clean
        rc_out, err_out = glslang(out_path, stage)
        if not err_out:
            print("  [输出按 ES 编译]  通过（无 GLSL ES 错误）")
            total_ok += 1
            if name in KNOWN_UNFIXED:
                known_now_fixed.append(name)
        elif name in KNOWN_UNFIXED:
            print("  [输出按 ES 编译]  仍失败 —— 已知未修缺陷（不计入失败）")
            print("      原因: %s" % KNOWN_UNFIXED[name])
            for m in err_out[:3]:
                print("      %s" % m[:170])
            known_still_broken.append(name)
        else:
            print("  [输出按 ES 编译]  失败 —— 仍有 GLSL ES 错误")
            for m in err_out[:8]:
                print("      %s" % m[:170])
            total_bad += 1

        # (d) show the rewritten lines so the fix is visible in build output
        conv = open(out_path, encoding="utf-8", errors="replace").read()
        interesting = [ln for ln in conv.splitlines()
                       if "vec3(_deinterleave" in ln
                       or "vec3(_get_relative_chunk_coord" in ln
                       or "float(_get_relative_chunk_coord" in ln]
        if interesting:
            print("  [改写点]")
            for ln in interesting[:6]:
                print("      %s" % ln.strip()[:150])

    print()
    print("=" * 74)
    print("结果: 通过 %d 个夹具，失败 %d 个" % (total_ok, total_bad))
    if known_still_broken:
        print()
        print("已知未修缺陷（不计入失败，但必须是刻意保留的）:")
        for n in known_still_broken:
            print("  - %s" % n)
    if known_now_fixed:
        print()
        print("!! KNOWN_UNFIXED 名单已过期 !!")
        for n in known_now_fixed:
            print("  - %s 现在已经通过 —— 缺陷已修复。" % n)
        print("  请从 roundtrip_validate.py 的 KNOWN_UNFIXED 中删除该条目，")
        print("  并让它转为正常夹具（此后它会守卫这个修复）。")
    print("=" * 74)
    return 0 if (total_bad == 0 and not known_now_fixed) else 1


if __name__ == "__main__":
    sys.exit(main())
