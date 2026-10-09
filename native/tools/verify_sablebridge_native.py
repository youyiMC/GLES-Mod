#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify SableBridge's bundled ARM64 native really is a loadable Android ELF.

Why this matters: last round the provenance was unknown (no Rust sources in the
repo). Now the jar turns out to CONTAIN its own natives, so the decisive
question is no longer "where did they come from" but "will they actually load
on Android at all". That is checkable:

  * ELF machine/class/OS-ABI  -> must be AArch64, ELF64, and ideally SYSV/Android
  * DT_NEEDED                 -> shared libs it needs (libc++_shared, liblog,
                                 libm, libdl, libc ...). A missing dependency
                                 means dlopen fails on device.
  * SONAME / exported symbols -> sanity, plus whether it looks like Rapier

Only the arm64-v8a slice is needed: that is the test device (SM8650).

The .so is extracted to native/tools/.cache (scratch) and never committed.

LGPL-3.0-or-later
"""
import os
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(HERE, ".cache", "sablebridge")

READELF = (r"C:\Android\Sdk\ndk\27.2.12479018\toolchains\llvm\prebuilt"
           r"\windows-x86_64\bin\llvm-readelf.exe")
# the shader-tools dir has llvm-readelf too on some installs; fall back if needed
READELF_ALT = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
               r"\windows-x86_64\llvm-readelf.exe")

ABI = "natives/sablebridge/SableRapier_Android_arm64-v8a.so"


def find_jar():
    for dirpath, _, files in os.walk(ROOT):
        low = dirpath.lower()
        if any(s in low for s in ("\\.git", "\\.gradle", "\\build\\", "\\.cache")):
            continue
        for f in files:
            if f.lower().endswith(".jar") and "sable" in f.lower():
                return os.path.join(dirpath, f)
    return None


def tool():
    for t in (READELF, READELF_ALT):
        if os.path.isfile(t):
            return t
    return None


def main():
    jar = find_jar()
    if not jar:
        print("no sable*.jar found")
        return 1
    os.makedirs(CACHE, exist_ok=True)

    with zipfile.ZipFile(jar) as z:
        if ABI not in z.namelist():
            print("ABI not present:", ABI)
            return 1
        dest = os.path.join(CACHE, "SableRapier_Android_arm64-v8a.so")
        with z.open(ABI) as src, open(dest, "wb") as out:
            out.write(src.read())
        print("extracted %s -> %s (%d bytes)"
              % (ABI, dest, os.path.getsize(dest)))

        # -- mixins config -------------------------------------------------
        print()
        print("=" * 74)
        print("sablebridge.mixins.json")
        print("=" * 74)
        for n in z.namelist():
            if n.endswith("sablebridge.mixins.json"):
                print(z.read(n).decode("utf-8", "replace"))

    rd = tool()
    if not rd:
        print("llvm-readelf.exe not found; skipping ELF checks")
        return 0

    for args, title in (
            (["-h"], "ELF header"),
            (["-d"], "dynamic section (DT_NEEDED / SONAME)"),
            (["--dyn-syms"], "dynamic symbols (first 40)"),
    ):
        print("=" * 74)
        print(title)
        print("=" * 74)
        r = subprocess.run([rd] + args + [dest], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        lines = (r.stdout or "").splitlines()
        if args == ["--dyn-syms"]:
            lines = lines[:44]
        for l in lines:
            print("  " + l[:150])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
