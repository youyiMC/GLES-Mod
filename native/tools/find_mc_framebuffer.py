#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find how Minecraft creates its main framebuffer's DEPTH attachment.

Looks at com/mojang/blaze3d/pipeline/{RenderTarget,MainTarget}.class and
disassembles them with javap, printing the context around any
glTexImage2D / glTexStorage2D call plus the depth-related constants.

Why: our library forwards glTexImage2D verbatim.  Desktop GL accepts
internalformat = GL_DEPTH_COMPONENT (0x1902), but GLES does NOT -- ES only
accepts GL_DEPTH_COMPONENT16/24/32F.  If MC passes 0x1902 the depth texture
is never allocated and depth testing silently does nothing (exactly the
symptom: un-culled faces + front/back overlapping).

Usage:
    py native\\tools\\find_mc_framebuffer.py [--jar PATH] [--all]
"""
import argparse
import glob
import os
import subprocess
import sys
import tempfile
import zipfile

DEFAULT_JAR_GLOBS = [
    r"C:\Users\youyi\.gradle\caches\neoformruntime\artifacts\minecraft_1.21.1_client.jar",
    r"C:\Users\youyi\.gradle\caches\**\minecraft_*_client.jar",
]

TARGETS = [
    "com/mojang/blaze3d/pipeline/RenderTarget.class",
    "com/mojang/blaze3d/pipeline/MainTarget.class",
    "com/mojang/blaze3d/platform/GlStateManager.class",
]

# Interesting GL constants (decimal as javap prints them)
INTERESTING = {
    "6402": "GL_DEPTH_COMPONENT(0x1902)  <-- INVALID as ES internalformat!",
    "5126": "GL_FLOAT(0x1406)  <-- invalid as depth texture *type* in ES",
    "33189": "GL_DEPTH_COMPONENT16(0x81A5)",
    "33190": "GL_DEPTH_COMPONENT24(0x81A6)",
    "33191": "GL_DEPTH_COMPONENT32F(0x81A7)",
    "34041": "GL_DEPTH_STENCIL(0x84F9) <-- also desktop-only internalformat",
    "35056": "GL_DEPTH24_STENCIL8(0x88F0)",
    "33190 ": "(dep24)",
    "6403": "GL_STENCIL_INDEX(0x1901)",
    "6408": "GL_RGBA(0x1908)",
    "32856": "GL_RGBA8(0x8058)",
}

CALLS = ["texImage2D", "texStorage2D", "framebufferTexture2D", "renderbufferStorage"]


def find_jar(explicit):
    if explicit:
        return explicit
    for pat in DEFAULT_JAR_GLOBS:
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    return None


def javap_path():
    for cand in [
        r"C:\Program Files\Java\jdk-21.0.12\bin\javap.exe",
        "javap",
    ]:
        if os.path.sep in cand:
            if os.path.isfile(cand):
                return cand
        else:
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", help="MC client jar")
    ap.add_argument("--all", action="store_true",
                    help="scan ALL classes in the jar (slow) instead of the known targets")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    jar = find_jar(args.jar)
    if not jar or not os.path.isfile(jar):
        print("!! MC client jar not found")
        return 1
    print("jar:", jar)

    jp = javap_path()
    if jp is None:
        print("!! javap not found")
        return 1

    tmp = tempfile.mkdtemp(prefix="mcjar_")
    with zipfile.ZipFile(jar) as z:
        names = z.namelist()
        if args.all:
            targets = [n for n in names if n.endswith(".class")]
        else:
            targets = [t for t in TARGETS if t in names]
            print("(targets found: %d of %d)" % (len(targets), len(TARGETS)))

        for n in targets:
            try:
                data = z.read(n)
            except KeyError:
                continue
            p = os.path.join(tmp, os.path.basename(n))
            with open(p, "wb") as f:
                f.write(data)
            try:
                out = subprocess.run([jp, "-c", "-p", p],
                                     capture_output=True, text=True, timeout=120)
            except Exception as e:
                print("!! javap failed on", n, e)
                continue
            lines = out.stdout.splitlines()

            hits = []
            for i, l in enumerate(lines):
                if any(c in l for c in CALLS):
                    hits.append(i)
                else:
                    for k in INTERESTING:
                        if ("// int " + k) in l or ("// int " + k.rstrip()) in l:
                            hits.append(i)
                            break
            if not hits:
                continue

            print("\n" + "=" * 70)
            print("CLASS:", n, " (%d bytecode lines)" % len(lines))
            print("=" * 70)
            shown = set()
            for i in hits:
                lo, hi = max(0, i - 6), min(len(lines), i + 7)
                if any(x in shown for x in range(lo, hi)):
                    continue
                for j in range(lo, hi):
                    shown.add(j)
                    mark = " <<<" if j == i else ""
                    print(lines[j] + mark)
                print("  ---")

    return 0


if __name__ == "__main__":
    sys.exit(main())
