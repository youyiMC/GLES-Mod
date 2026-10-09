#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List the method signatures of Sable Companion's API, javadoc stripped.

Purpose: decide which parts of Companion are RELEVANT TO A RENDERER BACKEND.
Our mod does GL passthrough + GLSL conversion; it does no spatial logic, so most
of Companion (positions, distances, velocities) is for content mods, not us.

If any method turns out to be rendering-relevant (skylight, brightness, bounds
for culling), that changes the plan -- so this is checked against the source
rather than assumed.

LGPL-3.0-or-later
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "sable-companion-src")

FILES = ["SableCompanion.java", "SubLevelAccess.java", "ClientSubLevelAccess.java"]

# NOTE: any of these words in a signature would make the method renderer-relevant
RENDER_HINTS = ("light", "bright", "color", "colour", "render", "fog",
                "camera", "pass", "layer")

SIG = re.compile(
    r"^\s{0,8}(?:@\w+(?:\([^)]*\))?\s+)*"          # annotations
    r"(?:public\s+|default\s+|static\s+|abstract\s+)*"
    r"(?!return\b|if\b|for\b|while\b|new\b|class\b|import\b|package\b)"
    r"([\w<>,.\[\]\s?@]+?)\s+(\w+)\(([^)]*)\)\s*[;{]")


def main():
    for f in FILES:
        p = os.path.join(SRC, f)
        if not os.path.isfile(p):
            print("missing %s" % f)
            continue
        print("=" * 78)
        print(f)
        print("=" * 78)
        in_block = False
        n = 0
        for line in io.open(p, encoding="utf-8", errors="replace").read().splitlines():
            s = line.strip()
            if s.startswith("/*"):
                in_block = True
            if in_block:
                if "*/" in s:
                    in_block = False
                continue
            if s.startswith("*") or s.startswith("//") or not s:
                continue
            m = SIG.match(line)
            if not m:
                continue
            ret, name, args = m.group(1).strip(), m.group(2), m.group(3)
            if name in ("if", "for", "while", "return", "new", "load"):
                continue
            hint = ""
            low = (ret + " " + name + " " + args).lower()
            if any(h in low for h in RENDER_HINTS):
                hint = "   <== RENDER-RELEVANT?"
            print("  %-24s %s(%s)%s" % (ret[:24], name, args[:60], hint))
            n += 1
        print("  -- %d methods --" % n)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
