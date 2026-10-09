#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Show the text behind the 8 remaining Flywheel fragment errors.

glslc reports logical line 12 of some included file; `#line` directives make the
physical position hard to read. This prints, for each raw error, the nearest
enclosing `#line` marker plus the next few physical lines, and separately lists
every `light` token that looks like a swizzle (the error names mention `light`).

LGPL-3.0-or-later
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DUMPS = os.path.join(HERE, ".cache", "fw_dumps")
TARGET = os.path.join(DUMPS, "06_raw.fixed.frag")
RAWF = os.path.join(DUMPS, "06_raw.frag")

LINE_RX = re.compile(r"^#line\s+(\d+)\s+(\d+)\s*(?://\s*(.*))?$")


def main():
    lines = io.open(TARGET, encoding="utf-8",
                    errors="replace").read().splitlines()
    print("total physical lines: %d" % len(lines))

    # Build a map: logical line -> list of (physical index, origin)
    fwd = {}
    origin = "?"
    log = 0
    for i, l in enumerate(lines):
        m = LINE_RX.match(l.strip())
        if m:
            log = int(m.group(2))
            if m.group(3):
                origin = m.group(3).strip()
            continue
        fwd.setdefault((origin, log), []).append(i)
        log += 1

    print()
    print("=== every line where a 'light' identifier appears ===")
    for i, l in enumerate(lines, 1):
        if re.search(r"\blight\b", l):
            print("%5d | %s" % (i, l.strip()[:150]))

    print()
    print("=== raw file: same search ===")
    rlines = io.open(RAWF, encoding="utf-8",
                     errors="replace").read().splitlines()
    for i, l in enumerate(rlines, 1):
        if re.search(r"\blight\b", l):
            print("%5d | %s" % (i, l.strip()[:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
