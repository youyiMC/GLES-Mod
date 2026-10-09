#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump MC's RenderTarget/MainTarget bytecode around depth-texture creation.

Goal: determine what internalformat Minecraft passes to glTexImage2D for the
main framebuffer's DEPTH attachment.

Background (why this matters):
  Our library forwards glTexImage2D verbatim.  Desktop GL accepts
  internalformat = GL_DEPTH_COMPONENT (0x1902 = 6402), but **GLES does not**
  -- ES only accepts GL_DEPTH_COMPONENT16/24/32F or DEPTH24_STENCIL8.
  If MC passes 6402/GL_DEPTH_COMPONENT, the depth texture is never allocated
  and depth testing silently does nothing.  Symptom matches exactly:
  un-culled faces + front & back of entities rendering on top of each other.

The driver confirmed this in latest.log:
  'the combination of format 6402 and type 5126 is unsupported'

Usage:
    py native\\tools\\mc_depth_format.py [--jar PATH]
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
import zipfile

CANDIDATES = [
    r"~\.gradle\caches\neoformruntime\intermediate_results\recompile_*_output.jar",
    r"~\.gradle\caches\neoformruntime\intermediate_results\inject_*_output.jar",
    r"~\.gradle\caches\neoformruntime\artifacts\minecraft_*_client.jar",
]

NAMES = re.compile(r"(RenderTarget|MainTarget|TextureTarget|GlStateManager)$")

# decimal constants we care about
CONST = {
    6402: "GL_DEPTH_COMPONENT(0x1902) !! desktop-only internalformat",
    5126: "GL_FLOAT(0x1406) !! invalid depth type in ES",
    33189: "GL_DEPTH_COMPONENT16(0x81A5)",
    33190: "GL_DEPTH_COMPONENT24(0x81A6)",
    33191: "GL_DEPTH_COMPONENT32F(0x81A7)",
    34041: "GL_DEPTH_STENCIL(0x84F9) !! desktop-only internalformat",
    35056: "GL_DEPTH24_STENCIL8(0x88F0)",
    33190: "(24)",
    6408: "GL_RGBA(0x1908)",
    32856: "GL_RGBA8(0x8058)",
    6407: "GL_RGB",
    6403: "GL_STENCIL_INDEX",
}

CALLS = ("texImage2D", "texStorage2D", "framebufferTexture2D",
         "renderbufferStorage", "texImage3D")


def find_jars(explicit):
    if explicit:
        return [explicit]
    out = []
    for pat in CANDIDATES:
        out += sorted(glob.glob(os.path.expanduser(pat)))
    return out


def javap():
    p = r"C:\Program Files\Java\jdk-21.0.12\bin\javap.exe"
    return p if os.path.isfile(p) else "javap"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar")
    ap.add_argument("--max", type=int, default=3, help="max jars to scan")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    jars = find_jars(args.jar)[: args.max]
    if not jars:
        print("!! no jar found")
        return 1
    jp = javap()
    tmp = tempfile.mkdtemp(prefix="mcdep_")
    found_any = False

    for jar in jars:
        print("=" * 72)
        print("JAR:", os.path.basename(jar))
        print("=" * 72)
        try:
            z = zipfile.ZipFile(jar)
        except Exception as e:
            print("  !! cannot open:", e)
            continue

        targets = []
        for n in z.namelist():
            if not n.endswith(".class"):
                continue
            base = os.path.basename(n)[:-6]
            if NAMES.search(base) or "blaze3d/pipeline" in n:
                targets.append(n)

        print("  candidates: %d" % len(targets))
        for n in targets:
            p = os.path.join(tmp, os.path.basename(n))
            with open(p, "wb") as f:
                f.write(z.read(n))
            try:
                r = subprocess.run([jp, "-c", "-p", p],
                                   capture_output=True, text=True, timeout=180)
            except Exception:
                continue
            lines = r.stdout.splitlines()

            idxs = []
            for i, l in enumerate(lines):
                if any(c in l for c in CALLS):
                    idxs.append(i)
                else:
                    m = re.search(r"// (?:int|short|byte) (\d+)", l)
                    if m and int(m.group(1)) in CONST:
                        idxs.append(i)
            if not idxs:
                continue

            found_any = True
            print("\n----- %s (%d lines) -----" % (n, len(lines)))
            shown = set()
            for i in idxs:
                lo, hi = max(0, i - 8), min(len(lines), i + 9)
                if any(x in shown for x in range(lo, hi)):
                    continue
                for j in range(lo, hi):
                    shown.add(j)
                    tag = "   <<<<" if j == i else ""
                    txt = lines[j]
                    m = re.search(r"// (?:int|short|byte) (\d+)", txt)
                    if m and int(m.group(1)) in CONST:
                        txt += "     [" + CONST[int(m.group(1))] + "]"
                    print(txt + tag)
                print("  ...")

    if not found_any:
        print("\n(no relevant classes found in scanned jars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
