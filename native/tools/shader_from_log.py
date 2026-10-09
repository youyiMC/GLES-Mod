#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers to pull a shader dump out of a glesmod native.log.

CRITICAL (this bit us once, hard):
  The native logger writes every dumped source line TWICE IN A ROW -- two
  identical content lines carrying different timestamps:

      [20:32:52.209]     59|     iris_FragData0 = vec4(color, 1.0f);
      [20:32:52.211]     59|     iris_FragData0 = vec4(color, 1.0f);

  Deduplicating by CONTENT silently drops genuinely repeated source lines
  (adjacent `}` / `}`, blank lines), which corrupts the program, shifts every
  line number, and manufactures phantom compile errors.

  Always deduplicate by POSITION PAIRING:
      if content(lines[i+1]) == content(lines[i]) -> i+1 is the copy, skip it
      else                                        -> line i is a real repeat

LGPL-3.0-or-later
"""
import io
import re

TS = re.compile(r"^\[\d\d:\d\d:\d\d\.\d+\]\s?")
PFX = re.compile(r"^\s*\d+\|\s?")

END_PREFIX = "===== END 该 shader"


def load_lines(path):
    with io.open(path, "rb") as f:
        return [l.decode("utf-8", errors="replace").rstrip("\r\n") for l in f]


def content(line):
    """Strip the log timestamp and the '   N| ' dump prefix."""
    return PFX.sub("", TS.sub("", line))


def find_block(lines, idx, kind):
    """Source lines of the dump block whose name contains `kind`, ending at or
    just before index `idx`.  Returns None when the block is absent."""
    end_label = "END 该 shader " + kind
    end = None
    for i in range(idx, max(0, idx - 1200), -1):
        if end_label in lines[i]:
            end = i
            break
    if end is None:
        return None

    beg_label = "BEGIN 该 shader " + kind
    begin = None
    for i in range(end, max(0, end - 1200), -1):
        if beg_label in lines[i]:
            begin = i
            break
    if begin is None:
        return None

    out = []
    i = begin + 1
    while i < end:
        t = content(lines[i])
        if t.startswith(END_PREFIX):
            break
        out.append(t)
        nxt = content(lines[i + 1]) if i + 1 < end else None
        i += 2 if nxt == t else 1
    return out


def find_failing_shaders(lines):
    """Return [(line_index, shader_id, stage)] for every failure entry."""
    res = []
    rx = re.compile(r"编译失败的着色器 .* 阶段=(\S+)，GL 名称=(\d+)")
    for i, s in enumerate(lines):
        m = rx.search(s)
        if m:
            stage = "vert" if "顶点" in m.group(1) else "frag"
            res.append((i, int(m.group(2)), stage))
    return res


def write_src(path, data):
    with io.open(path, "w", encoding="utf-8") as o:
        o.write("\n".join(data) + "\n")
