#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_tex_format_combos.py -- derive legal (internalformat, format, type)
combinations for the sized formats that appear in the device log.

Why: the device rejects
    glTexImage2D(GL_TEXTURE_2D, 0, GL_R11F_G11F_B10F, 2670, 1200, 0,
                 GL_RGB, GL_UNSIGNED_BYTE, NULL)
with GL_INVALID_OPERATION. That combination IS legal on desktop GL (where a
sized internalformat makes format/type advisory when pixels is NULL), but ES is
strict: a floating-point internal format requires a matching pixel type.

This script does not guess. It reads the enum values out of the authoritative
gl.xml so the mapping table we compile into the backend is verifiable, and it
prints the ES 3.0 legal pairings for the formats seen on the device.

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
GL_XML = HERE / ".cache" / "gl.xml"

WANTED = [
    "GL_R11F_G11F_B10F",
    "GL_UNSIGNED_INT_10F_11F_11F_REV",
    "GL_HALF_FLOAT",
    "GL_FLOAT",
    "GL_UNSIGNED_INT",
    "GL_RGB",
    "GL_RGBA",
    "GL_RED",
    "GL_RG",
    "GL_RGBA16F",
    "GL_RGB16F",
    "GL_RGBA32F",
    "GL_RGB32F",
    "GL_R16F",
    "GL_R32F",
    "GL_RG16F",
    "GL_RG32F",
    "GL_DEPTH_COMPONENT",
    "GL_DEPTH_COMPONENT16",
    "GL_DEPTH_COMPONENT24",
    "GL_DEPTH_COMPONENT32F",
    "GL_DEPTH24_STENCIL8",
    "GL_DEPTH_STENCIL",
    "GL_UNSIGNED_BYTE",
    "GL_UNSIGNED_SHORT",
    "GL_UNSIGNED_INT_24_8",
    "GL_PROXY_TEXTURE_2D",
]

# ES 3.0 spec, table 3.2: for each sized internal format, the legal
# (format, type) pairs. Kept here as an explicit table so the C code can be
# checked against it mechanically.
ES_LEGAL = {
    "GL_R11F_G11F_B10F": [
        ("GL_RGB", "GL_UNSIGNED_INT_10F_11F_11F_REV"),
        ("GL_RGB", "GL_HALF_FLOAT"),
        ("GL_RGB", "GL_FLOAT"),
    ],
    "GL_RGBA16F": [("GL_RGBA", "GL_HALF_FLOAT"), ("GL_RGBA", "GL_FLOAT")],
    "GL_RGB16F": [("GL_RGB", "GL_HALF_FLOAT"), ("GL_RGB", "GL_FLOAT")],
    "GL_RGBA32F": [("GL_RGBA", "GL_FLOAT")],
    "GL_RGB32F": [("GL_RGB", "GL_FLOAT")],
    "GL_R16F": [("GL_RED", "GL_HALF_FLOAT"), ("GL_RED", "GL_FLOAT")],
    "GL_R32F": [("GL_RED", "GL_FLOAT")],
    "GL_RG16F": [("GL_RG", "GL_HALF_FLOAT"), ("GL_RG", "GL_FLOAT")],
    "GL_RG32F": [("GL_RG", "GL_FLOAT")],
    "GL_DEPTH_COMPONENT16": [("GL_DEPTH_COMPONENT", "GL_UNSIGNED_SHORT"),
                             ("GL_DEPTH_COMPONENT", "GL_UNSIGNED_INT")],
    "GL_DEPTH_COMPONENT24": [("GL_DEPTH_COMPONENT", "GL_UNSIGNED_INT")],
    "GL_DEPTH_COMPONENT32F": [("GL_DEPTH_COMPONENT", "GL_FLOAT")],
    "GL_DEPTH24_STENCIL8": [("GL_DEPTH_STENCIL", "GL_UNSIGNED_INT_24_8")],
}


def main() -> int:
    if not GL_XML.exists():
        print(f"gl.xml not found: {GL_XML}", file=sys.stderr)
        return 2
    text = GL_XML.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r'<enum\s+value="(0x[0-9A-Fa-f]+)"\s+name="([A-Za-z0-9_]+)"')

    found: dict[str, int] = {}
    for m in pat.finditer(text):
        name = m.group(2)
        if name not in found:
            found[name] = int(m.group(1), 16)

    print("=" * 78)
    print(" enum values (authoritative, from gl.xml)")
    print("=" * 78)
    for n in WANTED:
        if n in found:
            print(f"  0x{found[n]:04X}  {n}")
        else:
            print(f"  {'?':>6}  {n}   <-- NOT canonical in gl.xml")
    print()

    print("=" * 78)
    print(" the rejected call, decoded")
    print("=" * 78)
    dev = dict(internalformat=0x8C3A, fmt=0x1907, typ=0x1401, w=2670, h=1200)
    rev = {v: k for k, v in found.items()}
    print(f"  internalformat 0x{dev['internalformat']:04X} = "
          f"{rev.get(dev['internalformat'], '?')}")
    print(f"  format         0x{dev['fmt']:04X} = {rev.get(dev['fmt'], '?')}")
    print(f"  type           0x{dev['typ']:04X} = {rev.get(dev['typ'], '?')}")
    print(f"  size           {dev['w']}x{dev['h']}  (matches the viewport)")
    print()

    key = rev.get(dev["internalformat"], "")
    print("  ES 3.0 legal (format, type) pairs for that internal format:")
    for f, t in ES_LEGAL.get(key, []):
        fv = found.get(f, -1)
        tv = found.get(t, -1)
        print(f"    format={f} (0x{fv:04X})  type={t} (0x{tv:04X})")
    print()
    print("  The device sent (GL_RGB, GL_UNSIGNED_BYTE), which is NOT in that")
    print("  list, hence GL_INVALID_OPERATION -> the texture gets no storage")
    print("  -> attaching it yields INCOMPLETE_MISSING_ATTACHMENT (36055).")
    print()

    print("=" * 78)
    print(" C table to compile in (internal format -> replacement pixel type)")
    print("=" * 78)
    for k, pairs in ES_LEGAL.items():
        if k in found and pairs:
            f, t = pairs[0]
            print(f'  case 0x{found[k]:04X}: /* {k} */ '
                  f'type = 0x{found[t]:04X}; /* {t} */ break;')
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
