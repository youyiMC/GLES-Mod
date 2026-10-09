#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify enum values against gl.xml and print ES 3.0 required pixel types.

Also lists the sized internal formats whose required type differs from
GL_UNSIGNED_BYTE, so the C table can be checked mechanically.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
GL_XML = HERE / ".cache" / "gl.xml"

WANT = [
    0x8059, 0x805B, 0x8058, 0x8051, 0x8229, 0x822B, 0x8C3A, 0x8814, 0x881A,
    0x8815, 0x881B, 0x822A, 0x822D, 0x822E, 0x8230, 0x822F, 0x1903, 0x8227,
    0x1401, 0x1403, 0x1405, 0x1406, 0x140B, 0x8368, 0x8C3B, 0x84FA, 0x0DE1,
]

text = GL_XML.read_text(encoding="utf-8", errors="replace")
pat = re.compile(r'<enum\s+value="(0x[0-9A-Fa-f]+)"\s+name="([A-Za-z0-9_]+)"')
found = {}
for m in pat.finditer(text):
    found.setdefault(m.group(2), int(m.group(1), 16))
rev = {}
for k, v in found.items():
    rev.setdefault(v, k)

print("=" * 70)
print(" enum values (authoritative, from gl.xml)")
print("=" * 70)
for v in WANT:
    print("  0x%04X  %s" % (v, rev.get(v, "<unknown>")))

print()
print("=" * 70)
print(" ES 3.0 table 3.2 -- required pixel TYPE for sized internal formats")
print(" (only those that differ from GL_UNSIGNED_BYTE / GL_RGBA)")
print("=" * 70)
TABLE = [
    ("GL_R8", "GL_RED", "GL_UNSIGNED_BYTE"),
    ("GL_R8_SNORM", "GL_RED", "GL_BYTE"),
    ("GL_R16F", "GL_RED", "GL_HALF_FLOAT"),
    ("GL_R32F", "GL_RED", "GL_FLOAT"),
    ("GL_RG8", "GL_RG", "GL_UNSIGNED_BYTE"),
    ("GL_RG16F", "GL_RG", "GL_HALF_FLOAT"),
    ("GL_RG32F", "GL_RG", "GL_FLOAT"),
    ("GL_RGB8", "GL_RGB", "GL_UNSIGNED_BYTE"),
    ("GL_RGB10_A2", "GL_RGBA", "GL_UNSIGNED_INT_2_10_10_10_REV"),
    ("GL_RGBA8", "GL_RGBA", "GL_UNSIGNED_BYTE"),
    ("GL_RGBA16", "GL_RGBA", "GL_UNSIGNED_SHORT"),
    ("GL_RGBA16F", "GL_RGBA", "GL_HALF_FLOAT"),
    ("GL_RGBA32F", "GL_RGBA", "GL_FLOAT"),
    ("GL_RGB16F", "GL_RGB", "GL_HALF_FLOAT"),
    ("GL_RGB32F", "GL_RGB", "GL_FLOAT"),
    ("GL_R11F_G11F_B10F", "GL_RGB", "GL_UNSIGNED_INT_10F_11F_11F_REV"),
    ("GL_SRGB8", "GL_RGB", "GL_UNSIGNED_BYTE"),
    ("GL_SRGB8_ALPHA8", "GL_RGBA", "GL_UNSIGNED_BYTE"),
]
for name, fmt, typ in TABLE:
    iv = found.get(name, -1)
    fv = found.get(fmt, -1)
    tv = found.get(typ, -1)
    flag = "  <-- MISSING from our table" if name in (
        "GL_RGB10_A2", "GL_RGBA16") else ""
    print("  {:<22} 0x{:04X}  format={:<12} 0x{:04X}  type={:<34} 0x{:04X}{}".format(
        name, iv, fmt, fv, typ, tv, flag))
