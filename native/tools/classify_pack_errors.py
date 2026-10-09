#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classify every glslang error in a validate_pack_all report by PATTERN.

Purpose: stop fixing one shader at a time.  Group errors by their message so
the distinct GLES-vs-desktop rule violations become visible at once, with a
count and a representative example for each.

Usage: py native\\tools\\classify_pack_errors.py <report.txt> [out.txt]
"""
import collections
import io
import re
import sys

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "pack-errors-by-pattern.txt"

with io.open(src, encoding="utf-8", errors="replace") as f:
    lines = f.read().splitlines()

# glslang error line shape:
#   C:\...\name.fsh.conv:123: error: '==' :  wrong operand types ...
RX = re.compile(r"^(.*?)[:](\d+): error: (.*)$")

# Normalise the message so structurally identical errors collapse.
def norm(msg: str) -> str:
    """Collapse to (category, key token).

    glslang messages are often truncated by the caller's line width, so
    comparing raw text produces many near-duplicates.  We instead extract the
    *category* (what kind of rule was broken) plus the leading quoted token
    (operator or function name), which is what actually identifies the fix.
    """
    m = re.sub(r"\s+", " ", msg.strip())
    m = m.replace("\u200b", "")

    # quoted leading token, e.g.  'scalar swizzle' : ...   or  '==' : ...
    tok = re.match(r"'([^']*)'\s*:", m)
    key = tok.group(1) if tok else "?"

    if "scalar swizzle" in m:
        cat = "IL: scalar swizzle on non-vector"
    elif "vector swizzle selection out of" in m:
        cat = "IL: swizzle out of range (type mismatch upstream)"
    elif "can't redefine/overload" in m:
        cat = "IL: redefines builtin"
    elif "no matching overloaded function" in m:
        cat = "IL: no matching overload"
    elif "wrong operand types" in m:
        cat = "IL: mixed int/float or vector op"
    elif "cannot convert from" in m or "cannot convert return" in m:
        cat = "IL: assignment/return type mismatch"
    elif "Only consts can be used in a global initializer" in m:
        cat = "IL: non-const global initializer"
    elif "type requires declaration of default precision" in m:
        cat = "IL: missing precision"
    elif "not supported for this version" in m or "Reserved" in m:
        cat = "IL: reserved/unsupported keyword"
    elif "l-value required" in m:
        cat = "IL: l-value required"
    elif "syntax error" in m:
        cat = "IL: syntax error"
    elif "undeclared" in m:
        cat = "IL: undeclared identifier"
    else:
        cat = "IL: other"

    return "%s   [%s]" % (cat, key)

by_pattern = collections.defaultdict(list)
for ln in lines:
    mm = RX.match(ln.strip())
    if not mm:
        continue
    f, line_no, msg = mm.group(1), mm.group(2), mm.group(3)
    by_pattern[norm(msg)].append((f.split("\\")[-1], line_no, msg.strip()))

# also count which shaders fail at all
failed_shaders = collections.Counter()
for pat, items in by_pattern.items():
    for f, _ln, _msg in items:
        failed_shaders[f] += 1

with io.open(out, "w", encoding="utf-8") as o:
    o.write("source: %s\n" % src)
    o.write("distinct error patterns: %d\n" % len(by_pattern))
    o.write("distinct failing files : %d\n\n" % len(failed_shaders))

    o.write("=" * 78 + "\n")
    o.write(" PATTERNS (most frequent first)\n")
    o.write("=" * 78 + "\n")
    for pat, items in sorted(by_pattern.items(), key=lambda kv: -len(kv[1])):
        o.write("\n[%3d]  %s\n" % (len(items), pat[:150]))
        seen = set()
        for f, ln, msg in items:
            if f in seen:
                continue
            seen.add(f)
            o.write("        %s:%s\n" % (f, ln))
            o.write("          %s\n" % msg[:150])
            if len(seen) >= 4:
                break

    o.write("\n\n" + "=" * 78 + "\n")
    o.write(" FILES BY ERROR COUNT\n")
    o.write("=" * 78 + "\n")
    for f, n in failed_shaders.most_common():
        o.write("  %3d  %s\n" % (n, f))

sys.stdout.write("wrote %s (%d patterns, %d files)\n"
                 % (out, len(by_pattern), len(failed_shaders)))
