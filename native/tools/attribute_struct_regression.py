#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attribute the struct-member wrapping regression.

Device evidence (latest.log): Flywheel instancing failed to compile and the
backend fell back to 'flywheel:off'.  A minimal probe reproduces the shape:

    struct FlwLightAo { vec2 light; float ao; };
    ...
    uvec2 light = uvec2(...);

converts to

    struct FlwLightAo { vec2 vec2(light); ... };   // syntax error

The older baseline (fw220-conv.txt) did NOT have this, so it is a regression.

This script runs the SAME input through every build we have and prints the
struct line, so the culprit build is identified by evidence rather than by
reasoning:

    cli_ambig.exe    current shipping build          (ambiguity drop ON)
    cli_noambig.exe  ambiguity drop compiled out     (-DGLESMOD_NO_AMBIG_DROP)
    cli_norule.exe   rule R compiled out             (-DGLESMOD_NO_RULE_R)

LGPL-3.0-or-later
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
T = os.path.join(HERE, ".cache", "veil")
CC = r"C:\msys64\ucrt64\bin\gcc.exe"

CLI_SRC = os.path.join(HERE, "convert_shader_cli.c")
SHADER_C = os.path.join(ROOT, "native", "src", "shader.c")
INCLUDE = os.path.join(ROOT, "native", "include")

FIXTURE = os.path.join(ROOT, "native", "tools", "fixtures",
                       "probe_uvec2_local_vs_struct_member.frag")

BUILDS = [
    ("ambig_on",    []),
    ("ambig_off",   ["-DGLESMOD_NO_AMBIG_DROP"]),
    ("ruleR_off",   ["-DGLESMOD_NO_RULE_R"]),
]


def build(name, defs):
    exe = os.path.join(T, "attr_%s.exe" % name)
    cmd = [CC, "-O1", "-std=c11"] + defs + ["-o", exe, CLI_SRC, SHADER_C,
                                             "-I", INCLUDE]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("BUILD FAILED for %s:\n%s" % (name, r.stderr[:400]))
        return None
    return exe


def run(exe):
    out = exe + ".out"
    subprocess.run([exe, FIXTURE, "fragment", out], capture_output=True)
    txt = io.open(out, encoding="utf-8", errors="replace").read()
    lines = []
    for l in txt.splitlines():
        if "FlwLightAo" in l and "struct" not in l or "vec2 light" in l \
                or "vec2 vec2" in l:
            lines.append(l.strip())
        if "uvec2 light" in l and "=" in l:
            lines.append(l.strip())
    return lines


def main():
    print("fixture:", os.path.basename(FIXTURE))
    print()
    for name, defs in BUILDS:
        exe = build(name, defs)
        if exe is None:
            continue
        got = run(exe)
        broken = any("vec2(light)" in g for g in got)
        print("%-12s %s" % (name, "BROKEN" if broken else "ok"))
        for g in got:
            print("      %s" % g[:120])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
