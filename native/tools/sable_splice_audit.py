#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble a "Sable-flavoured" Flywheel shader OFFLINE, then convert it.

Why this exists
---------------
`sable_audit.py` fed Sable's override files to glslang standalone and got 11/11
"failures" -- all harness artifacts: they are Veil/Flywheel `#include`
fragments, referencing uniforms, functions and macros provided by whatever
includes them. Standalone type-checking them is meaningless. (Same mistake I
made on the Veil investigation; recorded so it stops recurring.)

The right target is the ASSEMBLED shader the driver actually receives.

How we get that offline
-----------------------
`fw-raw.txt` is a real device dump of Flywheel's assembled instancing shader.
It is already fully inlined and carries section markers:

    #line 0 7 // flywheel:internal/api_impl.glsl
    <the contents of that file>

Sable's action is precisely to REPLACE some of those files. So we can splice
Sable's versions into the dump at the matching markers and get a faithful
approximation of what the driver would see with Sable installed -- without a
device.

Then run our converter + judgement on the spliced result, comparing against the
unspliced baseline, so any difference is attributable.

Only the .so/.shader text is handled; nothing is written back to the repo.

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
SABLE = os.path.join(ROOT, "sable-src")
FWDUMPS = os.path.join(HERE, ".cache", "fw_dumps")
TMP = os.path.join(HERE, ".cache", "sable_splice")
os.makedirs(TMP, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
CLI = os.path.join(TMP, "cli.exe")
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

# glslc always emits SPIR-V, so it also reports Vulkan-only requirements that are
# irrelevant for an OpenGL/ES target. Same filter list as the other gates.
SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")


def glslang(path, stage):
    r = subprocess.run([GLSLC, "--target-env=opengl",
                        "-fshader-stage=" + stage, path, "-o", path + ".spv"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    errs = []
    for ln in (r.stderr or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if "error" not in s.lower():
            continue
        if any(n in s for n in SPV_NOISE):
            continue
        # glslc's summary lines look like "23 errors generated." -- they are not
        # diagnostics, and counting them produced a phantom "1 error" on the
        # baseline run. Drop anything that does not carry a file:line prefix.
        if not re.match(r"^\S.*?:\d+:\d+:\s*error", s):
            continue
        errs.append(s)
    return errs

MARK = re.compile(r"^#line\s+\d+\s+\d+\s*//\s*(flywheel:.*?)\s*$")

# Sable file (flattened name) -> flywheel include path it overrides
OVERRIDES = {
    "flywheel_flywheel_internal_api_impl.glsl":
        "flywheel:internal/api_impl.glsl",
    "flywheel_flywheel_internal_api_impl.frag":
        "flywheel:internal/api_impl.frag",
    "flywheel_flywheel_internal_common.vert":
        "flywheel:internal/common.vert",
    "flywheel_flywheel_internal_light_lut.glsl":
        "flywheel:internal/light_lut.glsl",
    "flywheel_flywheel_internal_indirect_matrices.glsl":
        "flywheel:internal/indirect/matrices.glsl",
    "flywheel_flywheel_internal_indirect_main.vert":
        "flywheel:internal/indirect/main.vert",
    "flywheel_flywheel_internal_instancing_main.vert":
        "flywheel:internal/instancing/main.vert",
    "flywheel_flywheel_light_flat.glsl":
        "flywheel:light/flat.glsl",
    "flywheel_flywheel_light_smooth.glsl":
        "flywheel:light/smooth.glsl",
    "flywheel_flywheel_light_smooth_when_embedded.glsl":
        "flywheel:light/smooth_when_embedded.glsl",
}

CORRUPTION = [
    ("int-LHS + float-ctor",
     re.compile(r"\b(?:ivec[234]|uvec[234]|int|uint)\s+\w+\s*=\s*"
                r"(?:vec[234]|float)\s*\(")),
    ("struct member wrapped",
     re.compile(r"^\s*(?:vec[234]|float|int|uint)\s+(?:vec[234]|float)\s*\(")),
    ("float() around uvec",
     re.compile(r"\bfloat\s*\(\s*u?vec[234]\s*\(")),
]


def dedupe_pairs(lines):
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        if i + 1 < len(lines) and lines[i + 1] == lines[i]:
            i += 2
        else:
            i += 1
    return out


def splice(dump_lines, stage):
    """Replace each section whose marker matches an override."""
    out = []
    i = 0
    spliced = []
    while i < len(dump_lines):
        line = dump_lines[i]
        out.append(line)
        m = MARK.match(line)
        if not m:
            i += 1
            continue
        path = m.group(1).strip()
        # find the sable file overriding this path
        sable_file = None
        for f, p in OVERRIDES.items():
            if p == path and (f.endswith((".vert", ".frag")) == stage.endswith((".vert", ".frag"))):
                sable_file = f
                break
        if sable_file is None:
            for f, p in OVERRIDES.items():
                if p == path:
                    sable_file = f
                    break
        i += 1
        if sable_file is None:
            continue
        src = os.path.join(SABLE, sable_file)
        if not os.path.isfile(src):
            continue
        body = io.open(src, encoding="utf-8", errors="replace").read().rstrip("\n")
        # consume the original section: up to the next marker
        while i < len(dump_lines) and not MARK.match(dump_lines[i]):
            i += 1
        out.append(body)
        spliced.append(path)
    return out, spliced


def build_cli():
    r = subprocess.run([GCC, "-O1", "-std=c11", "-o", CLI,
                        os.path.join(HERE, "convert_shader_cli.c"),
                        os.path.join(ROOT, "native", "src", "shader.c"),
                        "-I", os.path.join(ROOT, "native", "include")],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("CLI BUILD FAILED\n" + (r.stderr or ""))
        sys.exit(1)


def convert(src_path, stage, tag):
    conv = os.path.join(TMP, "%s.conv" % tag)
    subprocess.run([CLI, src_path, stage, conv], capture_output=True)
    if not os.path.isfile(conv):
        return None
    return io.open(conv, encoding="utf-8", errors="replace").read()


def expand_flywheel_includes(text, depth=0):
    """Recursively inline `#include "flywheel:..."` from the sable-src tree.

    WHY: after splicing Sable's overrides into the dump, the spliced bodies still
    carry Flywheel's own `#include` directives. Leaving them made glslang report
    five "Cannot find or open include file" errors -- a harness artifact, not a
    converter problem. Recorded so this is not misread as a real failure again.

    Only Sable's own copies are used as the include source: whatever Sable ships
    is what the driver would see once Sable overrides Flywheel.
    """
    if depth > 6:
        return text
    out = []
    for ln in text.splitlines():
        m = re.match(r'^\s*#include\s+"flywheel:([^"]+)"\s*$', ln)
        if not m:
            out.append(ln)
            continue
        rel = m.group(1)
        cand = os.path.join(SABLE, "flywheel_flywheel_" + rel.replace("/", "_").replace(".", "."))
        # sable-src flattens 'internal/light_lut.glsl' -> 'flywheel_flywheel_internal_light_lut.glsl'
        cand2 = os.path.join(SABLE,
                             "flywheel_flywheel_" + rel.replace("/", "_"))
        pick = cand if os.path.isfile(cand) else cand2
        if not os.path.isfile(pick):
            out.append(ln)          # leave it; glslang will say so explicitly
            continue
        body = io.open(pick, encoding="utf-8", errors="replace").read()
        out.append("// ==== inlined %s ====" % rel)
        out.append(expand_flywheel_includes(body, depth + 1))
        out.append("// ==== end %s ====" % rel)
    return "\n".join(out)


def main():
    build_cli()
    base = os.path.join(FWDUMPS, "04_raw.vert")
    if not os.path.isfile(base):
        print("missing device dump:", base)
        return 1
    lines = dedupe_pairs(io.open(base, encoding="utf-8", errors="replace")
                         .read().splitlines())
    print("baseline dump lines: %d" % len(lines))

    out_lines, spliced = splice(lines, ".vert")
    print("spliced %d section(s):" % len(spliced))
    for s in spliced:
        print("   %s" % s)
    print()

    # the spliced bodies still contain Flywheel includes -> inline them, else
    # glslang reports 'Cannot find or open include file' (harness artifact)
    joined = expand_flywheel_includes("\n".join(out_lines))
    print("after include expansion: %d lines" % (len(joined.splitlines())))
    print()

    plain = os.path.join(TMP, "baseline.vert")
    sab = os.path.join(TMP, "sable.vert")
    with io.open(plain, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    with io.open(sab, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(joined + "\n")

    for tag, path in (("baseline", plain), ("sable", sab)):
        c = convert(path, "vertex", tag)
        if c is None:
            print("%-10s CONVERT FAILED" % tag)
            continue
        conv_path = os.path.join(TMP, "%s.conv" % tag)
        hits = [t for t, rx in CORRUPTION if rx.search(c)]
        errs = glslang(conv_path, "vert")
        verdict = "PASS" if not errs else "%d GLSL-ES error(s)" % len(errs)
        print("%-10s converted %6d bytes   corruption: %-8s   glslang: %s"
              % (tag, len(c), ", ".join(hits) if hits else "none", verdict))
        for e in errs[:4]:
            print("        %s" % e[:150])
    return 0


if __name__ == "__main__":
    sys.exit(main())
