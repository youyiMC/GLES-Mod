#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump META-INF/neoforge.mods.toml from the built mod jar.

Also scans NeoForge / ModLauncher jars for the "only supports" message so we
know exactly which component rejects us.

Usage:
    py native\\tools\\dump_mod_toml.py
"""
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JARS = [
    r"build\libs\*.jar",
]


def show_toml(path):
    print("=" * 74)
    print("JAR:", path)
    print("=" * 74)
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.endswith(".toml") or n.endswith(".json")]
        for n in names:
            if "mods.toml" not in n:
                continue
            print(f"--- {n} ---")
            print(z.read(n).decode("utf-8", errors="replace"))
            print()


def scan_for_message(pattern):
    """Search known NeoForge/ModLauncher jars for the literal message."""
    roots = [
        os.path.expanduser(r"~\.gradle\caches\**\*.jar"),
        os.path.expanduser(r"~\.gradle\caches\modules-2\**\*.jar"),
    ]
    cands = set()
    for r in roots:
        for p in glob.glob(r, recursive=True):
            b = os.path.basename(p)
            if any(k in b for k in ("neoforge", "fml", "modlauncher", "fmlloader", "coremods")):
                cands.add(p)

    print("=" * 74)
    print("scanning %d candidate jars for: %s" % (len(cands), pattern))
    print("=" * 74)
    needle = pattern.encode("utf-8")
    hits = 0
    for p in sorted(cands):
        try:
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if not n.endswith(".class"):
                        continue
                    try:
                        data = z.read(n)
                    except Exception:
                        continue
                    if needle in data:
                        print("  HIT  %s  ::  %s" % (os.path.basename(p), n))
                        hits += 1
                        if hits > 25:
                            print("  ... (truncated)")
                            return
        except Exception:
            continue
    if hits == 0:
        print("  (no hits)")


def main():
    for pat in JARS:
        for p in glob.glob(pat):
            show_toml(p)
    scan_for_message("only supports")
    scan_for_message("Currently,")


if __name__ == "__main__":
    main()
