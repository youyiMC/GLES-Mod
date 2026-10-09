#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize the two test logs (with Veil / with shaderpack).

Answers two questions with evidence pulled straight from the logs:
  1. Does Flywheel degrade as EXPECTED when a shaderpack is on?
  2. What is Veil's state in each case?

Why this is a script rather than inline python: PowerShell in this terminal
eats parentheses/quotes in `py -c "..."`, and PS 5.1 redirection writes UTF-16.

LGPL-3.0-or-later
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

LOGS = [
    ("latest(3).log", "Veil on, no shaderpack"),
    ("latest(4).log", "Veil on, WITH shaderpack"),
]

KEYS = [
    ("flywheel", r"Flywheel backend fell back"),
    ("iris",     r"Using shaderpack|Shaders are disabled|Profile:"),
    ("veil",     r"\[Veil/\].*"),
]

# things that would indicate WE broke something
BAD = [
    r"Failed to compile",
    r"ShaderException",
    r"flywheel:off",
]


def main():
    for name, label in LOGS:
        p = os.path.join(ROOT, name)
        print("=" * 78)
        print("%s   (%s)" % (name, label))
        print("=" * 78)
        if not os.path.isfile(p):
            print("  MISSING")
            continue
        lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()

        for tag, rx in KEYS:
            hits = [l.strip() for l in lines if re.search(rx, l)]
            if not hits:
                continue
            print("  [%s]" % tag)
            for h in hits[:12]:
                # keep the timestamp, drop the noisy prefixes
                m = re.match(r"^\[([^\]]*)\]\s*\[[^\]]*\]\s*\[[^\]]*\]\s*(.*)$", h)
                stamp = m.group(1) if m else ""
                body = m.group(2) if m else h
                print("      %-14s %s" % (stamp, body[:120]))
            if len(hits) > 12:
                print("      ... +%d more" % (len(hits) - 12))

        print()
        print("  --- indicators that we broke something ---")
        for rx in BAD:
            hits = [l.strip() for l in lines if re.search(rx, l)]
            print("      %-22s %d" % (rx, len(hits)))
            for h in hits[:4]:
                m = re.match(r"^\[([^\]]*)\]\s*\[[^\]]*\]\s*(.*)$", h)
                print("           %s" % (m.group(2) if m else h)[:130])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
