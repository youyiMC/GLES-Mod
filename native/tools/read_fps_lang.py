#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read Minecraft's own lang strings for the Max Framerate option.

Vanilla shows the top slider position as "Unlimited". Its description string in
en_us.json documents the exact numeric threshold, e.g.
"options.framerateLimit.max": "Unlimited (%s FPS)".

This gives the authoritative cut-off without guessing.

Self-locating; no args.
"""
import json
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JAR = os.path.join("build", "moddev", "artifacts",
                   "neoforge-21.1.241-client-extra-aka-minecraft-resources.jar")
if not os.path.isfile(JAR):
    # fall back to the merged jar
    JAR = os.path.join("build", "moddev", "artifacts",
                       "neoforge-21.1.241-merged.jar")

print("jar:", JAR)
keys = ("framerate", "vsync", "max", "unlimited")

with zipfile.ZipFile(JAR) as z:
    for name in z.namelist():
        if not name.endswith("en_us.json"):
            continue
        if "lang" not in name:
            continue
        try:
            obj = json.loads(z.read(name).decode("utf-8"))
        except Exception:
            continue
        hits = {k: v for k, v in obj.items()
                if any(t in k.lower() for t in keys)
                and ("framerate" in k.lower() or "vsync" in k.lower())}
        if not hits:
            continue
        print()
        print("=" * 74)
        print(name)
        print("=" * 74)
        for k in sorted(hits):
            print("  %-42s = %s" % (k, hits[k]))
