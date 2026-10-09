#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_ncgi_extension.py -- can the driver's own extension list satisfy the
non-constant global initializer rule?

Context: Iris injects
    iris_FogParameters irisInt_Fog = iris_FogParameters(iris_FogColor, ...);
which needs GL_EXT_shader_non_constant_global_initializers. glslang confirms
that is the ONLY missing piece (it names the extension explicitly at every ES
version).

So the decision is:
  (a) if the driver already exposes that extension, nothing needs fixing here
      and the shader failure must have another cause;
  (b) if it does not, the backend can TRUTHFULLY append it only if the driver
      actually accepts such shaders -- which is the claim we must not make
      without evidence.

This script answers (a) from the captured device log, and settles what glslang
does when the extension is enabled, so (b) can be decided on facts.

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LOG = ROOT / "native.log"
GLSLC = pathlib.Path(
    r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
)

EXT = "GL_EXT_shader_non_constant_global_initializers"

SPIRV_NOISE = (
    "SPIR-V", "requires location", "layout(binding", "layout(location",
    "non-opaque uniform", "Vulkan", "for Vulkan",
)


def device_says() -> tuple[bool, str]:
    """Search the captured native.log for the extension name."""
    if not LOG.exists():
        return False, "native.log not found"
    txt = LOG.read_text(encoding="utf-8", errors="replace")
    n = txt.count(EXT)
    return n > 0, f"occurrences in native.log: {n}"


def glslang_with_ext() -> tuple[bool, str]:
    """Compile the exact construct with the extension required."""
    src = (
        "#version 320 es\n"
        f"#extension {EXT} : require\n"
        "precision highp float;\n"
        "uniform vec4 iris_FogColor;\n"
        "uniform float iris_FogDensity;\n"
        "uniform float iris_FogStart;\n"
        "uniform float iris_FogEnd;\n"
        "struct iris_FogParameters {\n"
        "    vec4 color; float density; float start; float end; float scale;\n"
        "};\n"
        "iris_FogParameters irisInt_Fog = iris_FogParameters(iris_FogColor,\n"
        "    iris_FogDensity, iris_FogStart, iris_FogEnd,\n"
        "    1.0 / (iris_FogEnd - iris_FogStart));\n"
        "out vec4 fragColor;\n"
        "void main() { fragColor = irisInt_Fog.color; }\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "t.frag"
        p.write_text(src, encoding="utf-8")
        out = pathlib.Path(td) / "t.spv"
        r = subprocess.run(
            [str(GLSLC), "--target-env=opengl", "-fshader-stage=frag",
             str(p), "-o", str(out)],
            capture_output=True, text=True,
        )
    errs = [ln.strip() for ln in (r.stdout + r.stderr).splitlines()
            if "error" in ln.lower() and not any(x in ln for x in SPIRV_NOISE)]
    return (not errs), " | ".join(errs)


def main() -> int:
    print("=" * 78)
    print(" 1) does the DEVICE advertise the required extension?")
    print("=" * 78)
    found, detail = device_says()
    print(f"  {EXT}")
    print(f"  -> {'PRESENT' if found else 'ABSENT'}   ({detail})")
    print()

    print("=" * 78)
    print(" 2) does glslang accept the construct once the extension is enabled?")
    print("=" * 78)
    ok, msg = glslang_with_ext()
    print(f"  -> {'ACCEPTED' if ok else 'REJECTED'}" + (f"   {msg}" if msg else ""))
    print()

    print("=" * 78)
    print(" 3) what the two answers together imply")
    print("=" * 78)
    if not found and ok:
        print("  The extension is ABSENT from the device's list, and the")
        print("  construct compiles once it is enabled. That means the backend")
        print("  CAN truthfully add the extension name -- but ONLY if the")
        print("  driver genuinely implements it. Adreno's own parser is what")
        print("  produced the original error message, so the driver is")
        print("  enforcing the rule; whether it honours the extension must be")
        print("  settled by the driver, not by us.")
        print()
        print("  SAFER FIX: rewrite the construct instead. Move the")
        print("  initialisation into the first statement of main() (or of each")
        print("  function that reads it). That is version- and driver-agnostic")
        print("  and needs no capability claim at all.")
    elif found and ok:
        print("  The extension IS present, so this shader should have")
        print("  compiled; the failure must have another cause.")
    else:
        print("  glslang rejects the construct even with the extension, so")
        print("  do NOT add the extension name; rewrite the construct.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
