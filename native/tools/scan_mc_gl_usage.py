#!/usr/bin/env python3
"""
扫描 Minecraft 客户端 jar 中实际引用的 GL 符号（精确版）。

用途（对应任务书 O-02，关键一步）：
    差集分析给出「理论上要导出多少符号」，但真正决定工作量的是
    「MC 1.21.1 实际调用哪些符号」。本脚本通过精确解析 class 常量池的
    CONSTANT_Methodref 条目得到答案。

原理：
    LWJGL 的 GL 绑定按版本分为多个类（GL11、GL12、...、GL32）。每个 GL
    函数是该类的一个静态方法。javac 编译 `GL11.glDrawElements(...)` 时
    会在常量池生成：
        Methodref -> Class("org/lwjgl/opengl/GL11")
                  -> NameAndType("glDrawElements", "(IJIJ)V")
    因此只需解析 Methodref，就能准确得到 (类, 方法名) 对。

    相比「扫描字符串」的粗糙做法，本方法不会把一个类里出现的所有 gl*
    名字错误地归属给每个被引用的 GL 类。

用法：
    py scan_mc_gl_usage.py --jar <minecraft_client.jar> \
        --gl-symbols gl_3.2_core.txt --gles-symbols gles_3.2.txt \
        --json-out mc_gl_usage.json
"""

from __future__ import annotations

import argparse
import json
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

# 常量池 tag
UTF8, INTEGER, FLOAT, LONG, DOUBLE = 1, 3, 4, 5, 6
CLASS, STRING = 7, 8
FIELDREF, METHODREF, IFACEMETHODREF, NAMEANDTYPE = 9, 10, 11, 12
METHODHANDLE, METHODTYPE = 15, 16
DYNAMIC, INVOKEDYNAMIC, MODULE, PACKAGE = 17, 18, 19, 20

# LWJGL GL 绑定类 -> 桌面 GL 版本
GL_VERSION_OF = {
    "GL11": "1.1", "GL12": "1.2", "GL13": "1.3", "GL14": "1.4", "GL15": "1.5",
    "GL20": "2.0", "GL21": "2.1", "GL30": "3.0", "GL31": "3.1", "GL32": "3.2",
    "GL33": "3.3", "GL40": "4.0", "GL41": "4.1", "GL42": "4.2", "GL43": "4.3",
    "GL44": "4.4", "GL45": "4.5", "GL46": "4.6",
}

# LWJGL 的非版本化 GL 工具类
EXTRA_CLASSES = {"GL": "utility", "GLUtil": "utility"}


class ConstantPool:
    """解析并索引 class 文件常量池。"""

    def __init__(self, data: bytes):
        self.data = data
        self.count = struct.unpack_from(">H", data, 8)[0]
        self.entries: list = [None] * self.count
        self._parse()

    def _parse(self) -> None:
        off = 10
        i = 1
        while i < self.count:
            tag = self.data[off]
            off += 1
            if tag == UTF8:
                ln = struct.unpack_from(">H", self.data, off)[0]
                off += 2
                self.entries[i] = (UTF8, self.data[off : off + ln].decode("utf-8", "replace"))
                off += ln
            elif tag == INTEGER:
                self.entries[i] = (INTEGER, struct.unpack_from(">i", self.data, off)[0])
                off += 4
            elif tag == FLOAT:
                self.entries[i] = (FLOAT, struct.unpack_from(">f", self.data, off)[0])
                off += 4
            elif tag == LONG:
                self.entries[i] = (LONG, struct.unpack_from(">q", self.data, off)[0])
                off += 8
                i += 1
            elif tag == DOUBLE:
                self.entries[i] = (DOUBLE, struct.unpack_from(">d", self.data, off)[0])
                off += 8
                i += 1
            elif tag == CLASS:
                self.entries[i] = (CLASS, struct.unpack_from(">H", self.data, off)[0])
                off += 2
            elif tag == STRING:
                self.entries[i] = (STRING, struct.unpack_from(">H", self.data, off)[0])
                off += 2
            elif tag in (FIELDREF, METHODREF, IFACEMETHODREF):
                ci, nti = struct.unpack_from(">HH", self.data, off)
                off += 4
                self.entries[i] = (tag, ci, nti)
            elif tag == NAMEANDTYPE:
                ni, di = struct.unpack_from(">HH", self.data, off)
                off += 4
                self.entries[i] = (NAMEANDTYPE, ni, di)
            elif tag == METHODHANDLE:
                off += 3
            elif tag == METHODTYPE:
                self.entries[i] = (METHODTYPE, struct.unpack_from(">H", self.data, off)[0])
                off += 2
            elif tag in (DYNAMIC, INVOKEDYNAMIC):
                off += 4
            elif tag in (MODULE, PACKAGE):
                self.entries[i] = (tag, struct.unpack_from(">H", self.data, off)[0])
                off += 2
            else:
                raise ValueError(f"unknown constant pool tag {tag}")
            i += 1

    def utf8(self, idx: int) -> str | None:
        e = self.entries[idx] if 0 < idx < self.count else None
        return e[1] if e and e[0] == UTF8 else None

    def class_name(self, idx: int) -> str | None:
        e = self.entries[idx] if 0 < idx < self.count else None
        return self.utf8(e[1]) if e and e[0] == CLASS else None

    def method_refs(self) -> list[tuple[str, str]]:
        """返回所有 Methodref 的 (类名, 方法名)。"""
        out = []
        for e in self.entries:
            if not e or e[0] != METHODREF:
                continue
            cname = self.class_name(e[1])
            nt = self.entries[e[2]] if 0 < e[2] < self.count else None
            if cname is None or not nt or nt[0] != NAMEANDTYPE:
                continue
            mname = self.utf8(nt[1])
            if mname:
                out.append((cname, mname))
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description="精确扫描 MC jar 引用的 GL 符号")
    ap.add_argument("--jar", required=True, help="Minecraft 客户端 jar 路径")
    ap.add_argument("--gl-symbols", help="GL core 符号清单（用于校验）")
    ap.add_argument("--gles-symbols", help="GLES 符号清单（用于计算需适配量）")
    ap.add_argument("--json-out", help="JSON 输出路径")
    args = ap.parse_args()

    jar_path = Path(args.jar)
    if not jar_path.is_file():
        print(f"错误: 找不到 {jar_path}")
        return 1

    def load(p):
        if not p or not Path(p).is_file():
            return set()
        return {l.strip() for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()}

    known_gl = load(args.gl_symbols)
    known_gles = load(args.gles_symbols)

    by_class: dict[str, set[str]] = defaultdict(set)
    # 符号 -> 调用它的 MC 类集合（用于判断是否在关键路径）
    callers: dict[str, set[str]] = defaultdict(set)
    scanned = failed = 0

    with zipfile.ZipFile(jar_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".class"):
                continue
            scanned += 1
            try:
                cp = ConstantPool(zf.read(name))
            except Exception:
                failed += 1
                continue
            mc_class = name[:-6].replace("/", ".")
            for cname, mname in cp.method_refs():
                if not cname.startswith("org/lwjgl/opengl/"):
                    continue
                simple = cname.rsplit("/", 1)[-1]
                if simple in GL_VERSION_OF or simple in EXTRA_CLASSES:
                    by_class[simple].add(mname)
                    if mname.startswith("gl"):
                        callers[mname].add(mc_class)

    # 只保留 gl* 函数，去掉 LWJGL 辅助方法
    for c in list(by_class):
        by_class[c] = {m for m in by_class[c] if m.startswith("gl")}
        if not by_class[c]:
            del by_class[c]

    all_symbols = set().union(*by_class.values()) if by_class else set()
    in_core = all_symbols & known_gl if known_gl else all_symbols
    beyond_core = all_symbols - known_gl if known_gl else set()
    in_gles = in_core & known_gles if known_gles else set()
    need_extra = in_core - known_gles if known_gles else set()

    result = {
        "source": str(jar_path),
        "classes_scanned": scanned,
        "classes_failed": failed,
        "gl_binding_classes_used": {
            c: GL_VERSION_OF.get(c, EXTRA_CLASSES.get(c, "?"))
            for c in sorted(by_class, key=lambda x: GL_VERSION_OF.get(x, "zz"))
        },
        "total_distinct_symbols": len(all_symbols),
        "in_gl_32_core": len(in_core),
        "beyond_gl_32_core": sorted(beyond_core),
        "in_gles_32_direct": len(in_gles),
        "need_extra_work": sorted(need_extra),
        "by_class": {c: sorted(ms) for c, ms in sorted(by_class.items())},
        "callers": {s: sorted(cs) for s, cs in sorted(callers.items())},
    }

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(f"扫描 class: {scanned}（解析失败 {failed}）")
    print()
    print("MC 使用的 LWJGL GL 绑定类：")
    for c in sorted(by_class, key=lambda x: GL_VERSION_OF.get(x, "zz")):
        ver = GL_VERSION_OF.get(c, EXTRA_CLASSES.get(c, "?"))
        print(f"  {c:7s} (GL {ver:5s}): {len(by_class[c]):3d} 个符号")
    print()
    print(f"MC 实际引用的 GL 符号总数: {len(all_symbols)}")
    if known_gl:
        print(f"  属 GL 3.2 core      : {len(in_core)}")
        if beyond_core:
            print(f"  超出 3.2 core       : {len(beyond_core)}")
    if known_gles and in_core:
        print(f"  GLES 3.2 可直接满足 : {len(in_gles)}  ({len(in_gles)/len(in_core)*100:.1f}%)")
        print(f"  需要额外适配       : {len(need_extra)}  ({len(need_extra)/len(in_core)*100:.1f}%)")
    if need_extra:
        print()
        print("需要额外适配的符号（含调用方）：")
        for s in sorted(need_extra):
            cs = callers.get(s, set())
            print(f"  {s}")
            for c in sorted(cs)[:4]:
                print(f"      <- {c}")
    if beyond_core:
        print()
        print("超出 GL 3.2 core 的符号（需核实，含调用方）：")
        for s in sorted(beyond_core):
            cs = callers.get(s, set())
            print(f"  {s}")
            for c in sorted(cs)[:4]:
                print(f"      <- {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
