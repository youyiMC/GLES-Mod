#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect the SableBridge mod jar the user placed in the workspace.

Three things matter, in this order:

1. LICENSE IN THE ARTIFACT. The upstream repo's LICENSE file actually contains
   `neoforge.mods.toml` text, so the MIT claim could not be verified there. The
   user confirms CurseForge lists MIT; the jar's own `mods.toml` `license` field
   is the strongest locally verifiable evidence.

2. WHAT NATIVES IT SHIPS. Last round the binary provenance was unknown because
   the repo showed no Rust sources or build for the .so files. If the jar
   contains them, we can at least see exactly which ABIs and how big they are.

3. WHAT IT TOUCHES AT RUNTIME. The README says it redirects System.load() and
   adds tick throttling. Both are worth confirming from the classes, because a
   tick-throttle changes block-entity update rates and could affect what we
   observe on device.

This only reads the jar. It never extracts binaries into the repo.

LGPL-3.0-or-later
"""
import io
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.path.join(HERE, ".cache", "sablebridge")


def find_jar():
    hits = []
    for dirpath, _, files in os.walk(ROOT):
        # skip build outputs and our scratch dirs to keep this fast
        low = dirpath.lower()
        if any(s in low for s in ("\\.git", "\\.gradle", "\\build\\",
                                  "\\.cache", "node_modules")):
            continue
        for f in files:
            if f.lower().endswith(".jar") and "sable" in f.lower():
                hits.append(os.path.join(dirpath, f))
    return hits


def main():
    jars = find_jar()
    if not jars:
        print("no sable*.jar found under", ROOT)
        return 1

    for jar in jars:
        print("=" * 78)
        print(jar)
        print("  size %d bytes" % os.path.getsize(jar))
        print("=" * 78)
        with zipfile.ZipFile(jar) as z:
            names = z.namelist()

            # --- 1. license / mods.toml -------------------------------------
            print("\n-- metadata --")
            for n in names:
                if n.endswith("mods.toml") or n.upper().endswith("LICENSE") \
                        or n.upper().endswith("LICENSE.MD") \
                        or n.upper().endswith("LICENSE.TXT"):
                    txt = z.read(n).decode("utf-8", "replace")
                    print("  [%s]" % n)
                    for l in txt.splitlines()[:40]:
                        print("    " + l[:120])
                    print()

            # --- 2. natives -------------------------------------------------
            print("-- natives --")
            nat = [n for n in names if ".so" in n.lower()
                   or ".dll" in n.lower() or ".dylib" in n.lower()]
            if not nat:
                print("  (none in this jar)")
            for n in nat:
                print("  %-70s %9d" % (n, z.getinfo(n).file_size))

            # --- 3. classes -------------------------------------------------
            print("\n-- classes --")
            cls = sorted(n for n in names if n.endswith(".class"))
            for n in cls[:60]:
                print("  " + n)
            if len(cls) > 60:
                print("  ... +%d more" % (len(cls) - 60))

            # --- 4. mixin configs -------------------------------------------
            print("\n-- config/json/xml --")
            for n in sorted(names):
                if n.endswith((".json", ".xml")) and "META-INF" in n.upper():
                    print("  " + n)
        print()

    os.makedirs(SCRATCH, exist_ok=True)
    print("note: jar contents were only READ; nothing extracted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
