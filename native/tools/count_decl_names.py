#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""count_decl_names.py -- 统计某个已预处理着色器里各类变量声明的数量。

用途：给转换器里几张固定容量表的**容量**定值提供依据。
凭感觉定容量会两头出错：太小会静默截断（真机 BSL 就吃过这个亏），
太大会把栈吃掉（转换器里这些表都是栈上数组）。

用法:
    py native\\tools\\count_decl_names.py native\\tools\\.cache\\prep\\<文件>.pre
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FLOAT_VEC = ("vec2", "vec3", "vec4")
FLOAT_SCA = ("float", "double")
INT_VEC = ("ivec2", "ivec3", "ivec4", "uvec2", "uvec3", "uvec4",
           "bvec2", "bvec3", "bvec4")
INT_SCA = ("int", "uint", "bool")

QUAL = {"uniform", "const", "in", "out", "inout", "attribute", "varying",
        "flat", "smooth", "noperspective", "centroid", "invariant", "precise",
        "lowp", "mediump", "highp", "patch", "sample", "readonly",
        "writeonly", "coherent", "volatile", "restrict", "shared", "buffer",
        "struct"}


def scan(text):
    counts = {}
    members = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split("//")[0].strip()
        if not line:
            continue
        toks = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|.", line)
        # 去掉限定符
        i = 0
        while i < len(toks) and toks[i] in QUAL:
            i += 1
        if i >= len(toks):
            continue
        ty = toks[i]
        if ty not in FLOAT_VEC + FLOAT_SCA + INT_VEC + INT_SCA:
            continue
        # 只统计全局作用域（行首无缩进）——粗略判据：原始行未缩进
        if raw[:1] in (" ", "\t"):
            continue
        n = 0
        for t in toks[i + 1:]:
            if t == ";":
                break
            if t == ",":
                n += 1
                continue
            n = n if n else 0
        names = re.findall(r"[A-Za-z_][A-Za-z_0-9]*", line[line.index(ty) + len(ty):])
        # 第一个名字是变量名，逗号后的也是
        cnt = max(1, line.count(",") + 1) if "(" not in line.split(ty, 1)[1] else 1
        if ty in FLOAT_VEC:
            counts["float_vec"] = counts.get("float_vec", 0) + cnt
        elif ty in FLOAT_SCA:
            counts["float_scalar"] = counts.get("float_scalar", 0) + cnt
        elif ty in INT_VEC:
            counts["int_vec"] = counts.get("int_vec", 0) + cnt
            members += cnt * int(ty[-1])
        elif ty in INT_SCA:
            counts["int_scalar"] = counts.get("int_scalar", 0) + cnt
    counts["int_vec_members"] = members
    return counts


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1])
    text = p.read_text(encoding="utf-8", errors="replace")
    print("文件:", p)
    print("行数:", text.count("\n") + 1)
    c = scan(text)
    print()
    print("统计（仅为容量定值提供量级参考）:")
    for k in ("float_vec", "float_scalar", "int_vec", "int_scalar",
              "int_vec_members"):
        print("  %-18s %d" % (k, c.get(k, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
