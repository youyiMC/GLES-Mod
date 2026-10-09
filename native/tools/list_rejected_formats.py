#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List every DISTINCT glTexImage* rejection recorded in the native log.

Purpose: the previous rounds failed because the ES format table was grown
one entry at a time, each round discovering the next missing format from a new
device log.  This script enumerates the complete set at once so the table can
be closed in a single pass.

Usage: py native\\tools\\list_rejected_formats.py <log>
"""
import collections
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from shader_from_log import content, load_lines  # noqa: E402

NAMES = {
    0x1903: "GL_RED", 0x1907: "GL_RGB", 0x1908: "GL_RGBA", 0x8227: "GL_RG",
    0x8051: "GL_RGB8", 0x8056: "GL_RGBA4", 0x8057: "GL_RGB5_A1",
    0x8058: "GL_RGBA8", 0x8059: "GL_RGB10_A2", 0x805B: "GL_RGBA16",
    0x8229: "GL_R8", 0x822B: "GL_RG8", 0x822A: "GL_R16",
    0x822D: "GL_R32F", 0x822E: "GL_R16F", 0x8814: "GL_RGBA32F",
    0x8815: "GL_RGB32F", 0x881A: "GL_RGBA16F", 0x881B: "GL_RGB16F",
    0x8C3A: "GL_R11F_G11F_B10F", 0x8C41: "GL_SRGB8", 0x8C43: "GL_SRGB8_ALPHA8",
    0x81A5: "GL_DEPTH_COMPONENT16", 0x81A6: "GL_DEPTH_COMPONENT24",
    0x81A7: "GL_DEPTH_COMPONENT32F", 0x88F0: "GL_DEPTH24_STENCIL8",
    0x1902: "GL_DEPTH_COMPONENT", 0x84F9: "GL_DEPTH_STENCIL",
    0x1401: "GL_UNSIGNED_BYTE", 0x1403: "GL_UNSIGNED_SHORT",
    0x1405: "GL_UNSIGNED_INT", 0x1406: "GL_FLOAT", 0x140B: "GL_HALF_FLOAT",
    0x8368: "GL_UNSIGNED_INT_2_10_10_10_REV",
    0x8C3B: "GL_UNSIGNED_INT_10F_11F_11F_REV",
    0x84FA: "GL_UNSIGNED_INT_24_8",
    0x0DE1: "GL_TEXTURE_2D", 0x8064: "GL_PROXY_TEXTURE_2D",
}
ERR = {0x0500: "INVALID_ENUM", 0x0501: "INVALID_VALUE", 0x0502: "INVALID_OPERATION"}

HX = r"(0x[0-9A-Fa-f]+)(?:\([^)]*\))?"
RX = re.compile(
    r"(glTexImage\w*|glTexStorage\w*) 被驱动拒绝: err=" + HX +
    r" target=" + HX + r"(?: level=\d+)? internalformat=" + HX +
    r" (\d+)x(\d+) format=" + HX + r" type=" + HX + r" pixels=(\S+)")

lines = load_lines(sys.argv[1])
table = collections.Counter()
example = {}

for raw in lines:
    s = content(raw)
    m = RX.search(s)
    if not m:
        continue
    who, err, tgt, ifmt, w, h, fmt, typ, px = m.groups()
    key = (int(ifmt, 16), int(fmt, 16), int(typ, 16), px)
    table[(who, err, tgt) + key] += 1
    example.setdefault((who, err, tgt) + key, (int(w), int(h)))


def nm(v):
    return NAMES.get(v, "0x%04X?" % v)


print("=" * 96)
print(" DISTINCT glTexImage*/glTexStorage* REJECTIONS IN THE LOG")
print("=" * 96)
for key in sorted(table, key=lambda k: (-table[k], k)):
    who, err, tgt, ifmt, fmt, typ, px = key
    w, h = example[key]
    print("\n  x%-4d %s  %dx%d  pixels=%s" % (table[key], who, w, h, px))
    print("        err=%s(%s)  target=%s" % (err, ERR.get(int(err, 16), "?"), nm(int(tgt, 16))))
    print("        internalformat=%s   format=%s   type=%s"
          % (nm(ifmt), nm(fmt), nm(typ)))

print()
print("=" * 96)
print(" DISTINCT SIZED internal formats whose TYPE does not match (deduped)")
print("=" * 96)
bad = sorted({k[3] for k in table})
for v in bad:
    print("   0x%04X  %s" % (v, nm(v)))
