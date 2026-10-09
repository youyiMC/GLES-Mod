#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Veil audit: feed Veil's OWN pinwheel shaders through OUR converter and
validate the result with real glslang (the GLSL ES front end from the NDK).

Why this gate exists
--------------------
Veil is a FOURTH shader family, after:
  (a) Minecraft core shaders       -> 125/125
  (b) BSL shaderpack shaders       -> 166/166
  (c) Flywheel internal instancing -> 49 errors -> 0

We must not assume it behaves like the previous three. Veil has its own
preprocessor (`#include veil:...`, `#veil:buffer ...`) implemented in Java with
the `glslprocessor` library, and it INJECTS into vanilla shaders too.

What Veil actually hands the driver
-----------------------------------
`ShaderVersionProcessor` picks the version from LWJGL's GLCapabilities:

    if (version == 110 && core) {
        if (caps.OpenGL41) version = 410;
        else               version = 330;   // <- us: we report "3.2"
    }

So on our backend Veil's programs are compiled as desktop **#version 330 core**.
That is exactly the same translation our converter already does for Flywheel
and the MC core shaders -- but we must PROVE it on Veil's real sources.

Faithfulness notes (what this script does and does not reproduce)
----------------------------------------------------------------
* `#include veil:NAME`       -> expanded from veil-src/include/NAME.glsl
* `#veil:buffer veil:x T`    -> replaced by a synthetic `layout(std140) uniform T`
                                block. The real member list lives in Veil's Java
                                registry; we only need the STRUCTURE (a std140
                                UBO) to be faithful, and we say so in the output.
* `#veil:...` directive lines -> dropped (they are markers for Veil's injector)
* `#ifdef VEIL_*`            -> left for glslc, but we also run a pass with all
                                VEIL_* macros DEFINED so the optional branches
                                (normal/light code) are compiled too.
* compute shaders            -> reported separately; Veil gates them in json via
                                `required_features`, and ES 3.2/Adreno 750 does
                                support compute, so they are in scope.

LGPL-3.0-or-later
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Write our own UTF-8 report.
#
# Why not just `py veil_audit.py > out.txt` in PowerShell?
# PowerShell 5.1 redirection writes UTF-16LE, and it decodes native stdout with
# the OEM code page, so the captured file is a mojibake-duplexed mess that
# neither Get-Content nor Select-String handles usefully. Writing the report
# ourselves is the only reliably readable path.
REPORT = None
_report_buf = []


def log(*parts):
    line = " ".join(str(p) for p in parts)
    _report_buf.append(line)
    print(line)


def flush_report(path):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(_report_buf) + "\n")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "veil-src")
TMP = os.path.join(HERE, ".cache", "veil")
os.makedirs(TMP, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

CLI_SRC = os.path.join(HERE, "convert_shader_cli.c")
CLI_EXE = os.path.join(TMP, "convert_shader_cli.exe")
SHADER_C = os.path.join(ROOT, "native", "src", "shader.c")
INCLUDE = os.path.join(ROOT, "native", "include")

# glslc always emits SPIR-V, so it also reports Vulkan-only requirements.
# For an OpenGL/ES target those are irrelevant (same list as roundtrip_validate.py).
SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

# Synthetic std140 block standing in for Veil's `#veil:buffer veil:camera VeilCamera`.
#
# IMPORTANT -- instance name and member set are both deliberate:
#  * The block carries an INSTANCE NAME (`VeilCamera`) and is accessed as
#    `VeilCamera.ProjMat`. A block WITHOUT an instance name is legal in desktop
#    GLSL but NOT in GLSL ES, and worse, its members get injected into global
#    scope -- which collides with the standalone `uniform mat4 ProjMat;` that
#    several Veil programs declare. Getting this wrong produced a whole batch of
#    phantom 'redefinition' / 'cannot be used as an instance name' errors that
#    had nothing to do with our converter. Cost: one debug cycle.
#  * Only the members Veil actually dereferences are listed (verified by
#    grepping veil-src for `VeilCamera.<member>`): ProjMat, ViewMat, IViewMat,
#    CameraPosition, CameraBobOffset. The real member list lives in Veil's Java
#    registry; we only need the STRUCTURE to be faithful.
SYNTH_CAMERA = """layout(std140) uniform VeilCameraBlock {
    mat4 ProjMat;
    mat4 IProjMat;
    mat4 ViewMat;
    mat4 IViewMat;
    vec3 CameraPosition;
    vec3 CameraBobOffset;
    float NearPlane;
    float FarPlane;
} VeilCamera;
"""

# Veil injects this from its own config; the value is a bone-buffer capacity.
BONE_BUFFER_SIZE = 128


def build_cli():
    r = subprocess.run(
        [GCC, "-O1", "-std=c11", "-o", CLI_EXE, CLI_SRC, SHADER_C,
         "-I", INCLUDE],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("CLI build FAILED:")
        print(r.stdout or "", r.stderr or "")
        sys.exit(1)


def load_includes():
    inc = {}
    d = os.path.join(SRC, "include")
    for f in os.listdir(d):
        if f.endswith(".glsl"):
            inc[f[:-5]] = open(os.path.join(d, f), encoding="utf-8",
                               errors="replace").read()
    return inc


def expand_includes(text, inc, depth=0):
    """Expand `#include veil:NAME` using the fetched include library."""
    out = []
    for ln in text.split("\n"):
        m = re.match(r"^\s*#include\s+veil:([A-Za-z0-9_/]+)\s*$", ln)
        if m and depth < 6:
            name = m.group(1)
            body = inc.get(name)
            if body is not None:
                out.append("/* --- include veil:%s --- */" % name)
                out.append(expand_includes(body, inc, depth + 1))
                out.append("/* --- end include veil:%s --- */" % name)
                continue
            out.append("/* MISSING include %s */" % name)
            continue
        out.append(ln)
    return "\n".join(out)


def preprocess_veil(path, inc, define_optional):
    """Reproduce, as faithfully as we can, what Veil hands the driver."""
    text = open(path, encoding="utf-8", errors="replace").read()
    text = expand_includes(text, inc)

    out = []
    emitted_blocks = set()
    for ln in text.split("\n"):
        s = ln.strip()
        # `#veil:buffer veil:x STRUCT` -> synthetic std140 UBO (structure only).
        # Emit each block at most ONCE: includes also carry these directives
        # (veil:light, veil:camera, veil:gui ...), so naively substituting every
        # occurrence produces a duplicated block name and a cascade of phantom
        # errors ('Cannot reuse block name', '-' wrong operand types).
        m = re.match(r"^#veil:buffer\s+\S+\s+([A-Za-z_][A-Za-z0-9_]*)", s)
        if m:
            name = m.group(1)
            if name not in emitted_blocks:
                emitted_blocks.add(name)
                if name == "VeilCamera":
                    out.append(SYNTH_CAMERA)
                else:
                    # Any other Veil block we do not model. Declaring an empty
                    # block keeps the structure honest without inventing members.
                    out.append("layout(std140) uniform %sBlock { vec4 _pad; } %s;"
                               % (name, name))
            continue
        # every other `#veil:...` is an injector marker -> drop
        if s.startswith("#veil:"):
            continue
        out.append(ln)

    body = "\n".join(out)

    # Veil adds the version via ShaderVersionProcessor; on our caps it is 330 core.
    # Our own preprocessor's `#define NAME <int literal>` expansion and the
    # `#ifdef` handling both need the macros present BEFORE the body.
    pre = "#version 330 core\n"

    # Macros Veil's Java layer always injects for these programs.
    pre += "#define NECROMANCER_BONE_BUFFER_SIZE %d\n" % BONE_BUFFER_SIZE

    if define_optional:
        # Exercise the optional branches Veil turns on with features enabled.
        pre += ("#define VEIL_NORMAL\n"
                "#define VEIL_LIGHT_UV\n"
                "#define VEIL_LIGHT_COLOR\n"
                "#define INSCATTERING\n")

    return pre + body


def glslang(path, stage, extra=None):
    cmd = [GLSLC, "--target-env=opengl", "-fshader-stage=" + stage, path,
           "-o", path + ".spv"]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
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


# glslc stage names vs OUR CLI stage names differ on purpose:
#   glslc      : vert / frag / comp
#   our CLI    : vertex / fragment / (anything else = UNKNOWN)
# Getting this wrong silently disables the precision injection and produces
# dozens of bogus 'float : type requires declaration of default precision'
# errors. It cost us one full debug cycle; hence the explicit mapping.
#
# `.comp` deliberately maps to "compute" (UNKNOWN in the CLI): at runtime the
# converter receives GL_COMPUTE_SHADER (0x91B9), which is neither vertex nor
# fragment, so it injects no precision. Reproducing that is the faithful thing
# to do -- if ES compute then fails on precision, that is a REAL finding.
STAGE = {".vsh": ("vert", "vertex"),
         ".vert": ("vert", "vertex"),
         ".fsh": ("frag", "fragment"),
         ".frag": ("frag", "fragment"),
         ".comp": ("comp", "compute")}


def main():
    log("=" * 78)
    log("[1] 用当前源码编译转换器 CLI（绝不复用旧二进制）")
    log("=" * 78)
    build_cli()
    log("OK ->", CLI_EXE)

    inc = load_includes()
    log("include 库: %d 个 (%s)" % (len(inc), ", ".join(sorted(inc))))

    progs = sorted(f for f in os.listdir(SRC)
                   if os.path.splitext(f)[1] in STAGE
                   and f.startswith("program_"))
    if not progs:
        log("no veil programs found in", SRC)
        return 1

    log("")
    log("=" * 78)
    log("[2] Veil 真实的 pinwheel 着色器：转换 -> glslang")
    log("=" * 78)

    tot_ok = tot_bad = 0
    fails = []

    for name in progs:
        ext = os.path.splitext(name)[1]
        glslc_stage, cli_stage = STAGE[ext]
        src_path = os.path.join(SRC, name)

        log("")
        log("-" * 78)
        log("节目 %s   (阶段=%s)" % (name, glslc_stage))
        log("-" * 78)

        for opt in (False, True):
            tag = "含可选特性" if opt else "最小"
            raw = os.path.join(TMP, "%s.%s.330" % (name, "opt" if opt else "min"))
            conv = raw + ".converted"
            with open(raw, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(preprocess_veil(src_path, inc, opt))

            rc, errs = glslang(raw, glslc_stage)
            if errs:
                log("  [%s] 原码按 330 core 编译: %d 条错误（桌面专属，预期）"
                    % (tag, len(errs)))
            else:
                log("  [%s] 原码按 330 core 编译: 干净" % tag)

            r = subprocess.run([CLI_EXE, raw, cli_stage, conv],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0 or not os.path.isfile(conv):
                log("  [%s] 我们的转换: 失败 rc=%d" % (tag, r.returncode))
                log((r.stdout or "")[:500], (r.stderr or "")[:500])
                tot_bad += 1
                fails.append((name, tag, "converter-crash", []))
                continue

            rc2, errs2 = glslang(conv, glslc_stage)
            if not errs2:
                log("  [%s] 转换后按 ES 编译: 通过" % tag)
                tot_ok += 1
            else:
                log("  [%s] 转换后按 ES 编译: %d 条仍然错误" % (tag, len(errs2)))
                for m in errs2[:6]:
                    log("       %s" % m[:165])
                tot_bad += 1
                fails.append((name, tag, "es-error", errs2))

    log("")
    log("=" * 78)
    log("结果: 通过 %d，失败 %d" % (tot_ok, tot_bad))
    log("=" * 78)
    if fails:
        log("")
        log("失败明细:")
        for n, tag, kind, errs in fails:
            log("  - %s [%s] %s" % (n, tag, kind))
            for e in errs[:3]:
                log("      %s" % e[:165])

    out = os.path.join(ROOT, "veil-audit-report.txt")
    flush_report(out)
    print("report ->", out)
    return 1 if tot_bad else 0


if __name__ == "__main__":
    sys.exit(main())
