#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_fbo_enums.py -- print the authoritative FramebufferStatus enum table.

Why this exists
---------------
`fbo_status_name()` in custom.c was written from memory, and the values from
0x8CD9 upward were WRONG. The consequence was not cosmetic: a real device
reported 36055, and the recorder would have printed a confident, wrong name.

36055 = 0x8CD7 = GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT
               (NOT GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER = 0x8CDB)

The lesson this project has now recorded three times (0x1801, 34049, and this):
never write an enum from memory. Read gl.xml.

This script derives the table from gl.xml so the C code can be checked against
it mechanically rather than by recollection.

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
GL_XML = HERE / ".cache" / "gl.xml"

WANTED = [
    "GL_FRAMEBUFFER_COMPLETE",
    "GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT",
    "GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT",
    "GL_FRAMEBUFFER_INCOMPLETE_DIMENSIONS",
    "GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER",
    "GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER",
    "GL_FRAMEBUFFER_UNSUPPORTED",
    "GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE",
    "GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS",
    "GL_NUM_EXTENSIONS",
    "GL_EXTENSIONS",
    "GL_VERSION",
]


def main() -> int:
    if not GL_XML.exists():
        print(f"gl.xml not found: {GL_XML}", file=sys.stderr)
        return 2

    text = GL_XML.read_text(encoding="utf-8", errors="replace")

    # <enum value="0x8CD7" name="GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT" group="..."/>
    pattern = re.compile(r'<enum\s+value="(0x[0-9A-Fa-f]+)"\s+name="([A-Za-z0-9_]+)"')

    found: dict[str, int] = {}
    for m in pattern.finditer(text):
        value = int(m.group(1), 16)
        name = m.group(2)
        # keep the first (canonical) occurrence for each exact name
        if name not in found:
            found[name] = value

    print("=" * 78)
    print(" authoritatively derived from native/tools/.cache/gl.xml")
    print("=" * 78)
    print(f"{'value':>10}  {'decimal':>7}  name")
    print("-" * 78)
    for name in WANTED:
        if name in found:
            v = found[name]
            print(f"  0x{v:04X}  {v:>7}  {name}")
        else:
            print(f"  {'?':>10}  {'?':>7}  {name}   <-- NOT IN gl.xml")
    print()

    # Decode the value that actually appeared on the device.
    DEVICE_STATUS = 36055
    hit = None
    for m in pattern.finditer(text):
        if int(m.group(1), 16) == DEVICE_STATUS:
            hit = m.group(2)
            break

    print("=" * 78)
    print(f" decode of the real-device value {DEVICE_STATUS} (0x{DEVICE_STATUS:04X})")
    print("=" * 78)
    if hit:
        print(f"  {DEVICE_STATUS} = {hit}")
    else:
        print(f"  {DEVICE_STATUS}: no canonical name found")
    print()

    # Report every name that shares the device value, to expose EXT aliases.
    aliases = []
    for m in pattern.finditer(text):
        if int(m.group(1), 16) == DEVICE_STATUS:
            aliases.append(m.group(2))
    if aliases:
        print("  all names carrying that value:")
        for a in aliases:
            print(f"    {a}")
    print()

    print("=" * 78)
    print(" C table that MUST match the above (for fbo_status_name)")
    print("=" * 78)
    core = [
        "GL_FRAMEBUFFER_COMPLETE",
        "GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT",
        "GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT",
        "GL_FRAMEBUFFER_INCOMPLETE_DIMENSIONS",
        "GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER",
        "GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER",
        "GL_FRAMEBUFFER_UNSUPPORTED",
        "GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE",
        "GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS",
    ]
    for name in core:
        if name in found:
            v = found[name]
            short = name.replace("GL_FRAMEBUFFER_", "")
            print(f'    case 0x{v:04X}: return "{short}";')
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
