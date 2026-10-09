#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Look up an OpenGL enum value in the bundled authoritative gl.xml.

Answers "what is 34049?" and "is it legal in GLES?" without guessing.
Also checks whether glPixelStorei is even in the GLES version of the spec.

Self-locating.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.path.join(HERE, ".cache", "gl.xml")

if not os.path.isfile(XML):
    print("gl.xml not found at", XML)
    sys.exit(1)

txt = open(XML, encoding="utf-8", errors="replace").read()

WANT = sys.argv[1:] or ["34049", "0x8501"]
TARGETS = {"34049", "0x8501", "8501"}

print("=" * 74)
print("gl.xml 里值为 34049 / 0x8501 的枚举")
print("=" * 74)

for m in re.finditer(r'<enum\s+value="(0x8501|34049)"\s+([^>]*?)/>', txt):
    print("  ", m.group(0)[:200])

print()
print("=" * 74)
print("glPixelStorei 在各 API 中的可用性")
print("=" * 74)
for m in re.finditer(r'<command>\s*<proto>[^<]*<name>glPixelStorei</name>.*?</command>',
                     txt, re.S):
    print("  命令定义存在（长度 %d）" % len(m.group(0)))

# Which features/require blocks mention glPixelStorei, and for which api
print()
print("提到 glPixelStorei 的 <require> 所在 feature/extension：")
for fm in re.finditer(r'<(feature|extension)\s+([^>]*?)>(.*?)</\1>', txt, re.S):
    attrs, body = fm.group(2), fm.group(3)
    if "glPixelStorei" in body:
        api = re.search(r'api="([^"]*)"', attrs)
        name = re.search(r'name="([^"]*)"', attrs)
        print("   %-12s %-28s api=%s" % (
            fm.group(1), name.group(1) if name else "?", 
            api.group(1) if api else "(all)"))

# Does GLES allow UNPACK_ROW_LENGTH?
print()
print("=" * 74)
print("UNPACK_ROW_LENGTH 是否对 gles2 可用")
print("=" * 74)
for m in re.finditer(r'<enum\s+value="0x8501"[^>]*name="GL_UNPACK_ROW_LENGTH"[^>]*>', txt):
    print("  enum 行:", m.group(0)[:220])
    if 'api="gles2"' in m.group(0):
        print("  => 标注了 api=gles2（GLES 可用）")
    else:
        print("  => 未标注 gles2（默认仅桌面可用）")
