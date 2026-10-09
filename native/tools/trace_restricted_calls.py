#!/usr/bin/env python3
"""
追踪 MC 中受限 GL 符号的调用链，判断是否在关键渲染路径。

用途：
    O-02 发现 5 个 ES 不支持的符号由 GlStateManager 引用。需要判断它们
    是否真会在运行时被调用——若仅在调试/异常路径，可直接 stub；若在渲染
    主循环，必须认真实现。

方法：
    1. 解析目标 class 的方法表与 Code 属性，得到每个方法引用的 GL 符号
    2. 反查这些方法的调用者（全 jar 扫描 Methodref）
    3. 输出调用链，人工判断关键性

用法：
    py trace_restricted_calls.py --jar <mc.jar> \
        --class com/mojang/blaze3d/platform/GlStateManager.class \
        --symbols glDrawPixels glGetTexImage glLogicOp glPolygonMode glClearDepth glMapBuffer
"""

from __future__ import annotations

import argparse
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

UTF8, INTEGER, FLOAT, LONG, DOUBLE = 1, 3, 4, 5, 6
CLASS, STRING = 7, 8
FIELDREF, METHODREF, IFACEMETHODREF, NAMEANDTYPE = 9, 10, 11, 12
METHODHANDLE, METHODTYPE = 15, 16
DYNAMIC, INVOKEDYNAMIC, MODULE, PACKAGE = 17, 18, 19, 20


class ClassFile:
    """最小可用的 class 文件解析器。"""

    def __init__(self, data: bytes):
        self.data = data
        self.cp: list = []
        self.methods: list[dict] = []
        self._parse_cp()
        self._parse_members()

    def _parse_cp(self) -> None:
        data = self.data
        count = struct.unpack_from(">H", data, 8)[0]
        self.cp = [None] * count
        off = 10
        i = 1
        while i < count:
            tag = data[off]
            off += 1
            if tag == UTF8:
                ln = struct.unpack_from(">H", data, off)[0]
                off += 2
                self.cp[i] = (UTF8, data[off : off + ln].decode("utf-8", "replace"))
                off += ln
            elif tag == INTEGER:
                self.cp[i] = (INTEGER, struct.unpack_from(">i", data, off)[0])
                off += 4
            elif tag == FLOAT:
                self.cp[i] = (FLOAT, struct.unpack_from(">f", data, off)[0])
                off += 4
            elif tag == LONG:
                self.cp[i] = (LONG, struct.unpack_from(">q", data, off)[0])
                off += 8
                i += 1
            elif tag == DOUBLE:
                self.cp[i] = (DOUBLE, struct.unpack_from(">d", data, off)[0])
                off += 8
                i += 1
            elif tag == CLASS:
                self.cp[i] = (CLASS, struct.unpack_from(">H", data, off)[0])
                off += 2
            elif tag == STRING:
                self.cp[i] = (STRING, struct.unpack_from(">H", data, off)[0])
                off += 2
            elif tag in (FIELDREF, METHODREF, IFACEMETHODREF):
                ci, nti = struct.unpack_from(">HH", data, off)
                off += 4
                self.cp[i] = (tag, ci, nti)
            elif tag == NAMEANDTYPE:
                ni, di = struct.unpack_from(">HH", data, off)
                off += 4
                self.cp[i] = (NAMEANDTYPE, ni, di)
            elif tag == METHODHANDLE:
                off += 3
            elif tag == METHODTYPE:
                self.cp[i] = (METHODTYPE, struct.unpack_from(">H", data, off)[0])
                off += 2
            elif tag in (DYNAMIC, INVOKEDYNAMIC):
                off += 4
            elif tag in (MODULE, PACKAGE):
                self.cp[i] = (tag, struct.unpack_from(">H", data, off)[0])
                off += 2
            else:
                raise ValueError(f"cp tag {tag}")
            i += 1
        self.off_after_cp = off

    def utf8(self, idx: int) -> str | None:
        e = self.cp[idx] if 0 < idx < len(self.cp) else None
        return e[1] if e and e[0] == UTF8 else None

    def class_name(self, idx: int) -> str | None:
        e = self.cp[idx] if 0 < idx < len(self.cp) else None
        return self.utf8(e[1]) if e and e[0] == CLASS else None

    def _parse_members(self) -> None:
        """解析字段与方法表，记录每个方法体内引用的 Methodref。"""
        data = self.data
        off = self.off_after_cp
        # 跳过 access_flags, this_class, super_class
        off += 6
        ifc_count = struct.unpack_from(">H", data, off)[0]
        off += 2 + ifc_count * 2

        def skip_attributes(off: int) -> int:
            n = struct.unpack_from(">H", data, off)[0]
            off += 2
            for _ in range(n):
                ln = struct.unpack_from(">I", data, off + 2)[0]
                off += 6 + ln
            return off

        # 字段
        field_count = struct.unpack_from(">H", data, off)[0]
        off += 2
        for _ in range(field_count):
            off += 6
            off = skip_attributes(off)

        # 方法
        method_count = struct.unpack_from(">H", data, off)[0]
        off += 2
        for _ in range(method_count):
            name_idx = struct.unpack_from(">H", data, off + 2)[0]
            desc_idx = struct.unpack_from(">H", data, off + 4)[0]
            mname = self.utf8(name_idx)
            mdesc = self.utf8(desc_idx)
            off += 6
            attr_count = struct.unpack_from(">H", data, off)[0]
            off += 2
            refs: list[str] = []
            for _ in range(attr_count):
                aname = self.utf8(struct.unpack_from(">H", data, off)[0])
                alen = struct.unpack_from(">I", data, off + 2)[0]
                body = data[off + 6 : off + 6 + alen]
                if aname == "Code":
                    refs = self._scan_code_refs(body)
                off += 6 + alen
            self.methods.append({"name": mname, "desc": mdesc, "refs": refs})

    def _scan_code_refs(self, code_attr: bytes) -> list[str]:
        """
        扫描 Code 属性里的指令流，收集 Methodref 索引。

        只做基本的字节码长度解码，遇到不认识的指令则停止（保守）。
        """
        if len(code_attr) < 8:
            return []
        max_stack, max_locals = struct.unpack_from(">HH", code_attr, 0)
        code_len = struct.unpack_from(">I", code_attr, 4)[0]
        code = code_attr[8 : 8 + code_len]
        del max_stack, max_locals

        refs: list[str] = []
        pc = 0
        n = len(code)
        while pc < n:
            op = code[pc]
            # 收集方法调用相关指令
            if op in (0xB6, 0xB7, 0xB8, 0xB9):  # invokevirtual/special/static/interface
                if pc + 2 < n:
                    idx = struct.unpack_from(">H", code, pc + 1)[0]
                    e = self.cp[idx] if 0 < idx < len(self.cp) else None
                    if e and e[0] in (METHODREF, IFACEMETHODREF):
                        nt = self.cp[e[2]] if 0 < e[2] < len(self.cp) else None
                        if nt and nt[0] == NAMEANDTYPE:
                            mn = self.utf8(nt[1])
                            if mn:
                                refs.append(mn)
                pc += 3
                continue
            # 指令长度表（仅覆盖常见指令，未覆盖的保守停止）
            ln = OPCODE_LEN.get(op)
            if ln is None:
                if op == 0xAA:  # tableswitch
                    pad = (4 - ((pc + 1) % 4)) % 4
                    p = pc + 1 + pad
                    if p + 12 > n:
                        break
                    low, high = struct.unpack_from(">ii", code, p + 4)
                    pc = p + 12 + (high - low + 1) * 4
                    continue
                if op == 0xAB:  # lookupswitch
                    pad = (4 - ((pc + 1) % 4)) % 4
                    p = pc + 1 + pad
                    if p + 8 > n:
                        break
                    npairs = struct.unpack_from(">i", code, p + 4)[0]
                    pc = p + 8 + npairs * 8
                    continue
                break
            pc += ln
        return refs


# 常见指令的长度（操作码 -> 包含操作码本身的字节数）
OPCODE_LEN: dict[int, int] = {}
for _op in range(0x00, 0x10):
    OPCODE_LEN[_op] = 1
OPCODE_LEN.update(
    {
        0x10: 2, 0x11: 3, 0x12: 2, 0x13: 3, 0x14: 3,
        0x15: 2, 0x16: 2, 0x17: 2, 0x18: 2, 0x19: 2,
        0x1A: 1, 0x1B: 1, 0x1C: 1, 0x1D: 1,
        0x1E: 1, 0x1F: 1, 0x20: 1, 0x21: 1,
        0x22: 1, 0x23: 1, 0x24: 1, 0x25: 1,
        0x26: 1, 0x27: 1, 0x28: 1, 0x29: 1,
        0x2A: 1, 0x2B: 1, 0x2C: 1, 0x2D: 1,
        0x2E: 1, 0x2F: 1, 0x30: 1, 0x31: 1,
        0x32: 1, 0x33: 1, 0x34: 1, 0x35: 1,
        0x36: 2, 0x37: 2, 0x38: 2, 0x39: 2, 0x3A: 2,
        0x3B: 1, 0x3C: 1, 0x3D: 1, 0x3E: 1,
        0x3F: 1, 0x40: 1, 0x41: 1, 0x42: 1,
        0x43: 1, 0x44: 1, 0x45: 1, 0x46: 1,
        0x47: 1, 0x48: 1, 0x49: 1, 0x4A: 1,
        0x4B: 1, 0x4C: 1, 0x4D: 1, 0x4E: 1,
        0x4F: 1, 0x50: 1, 0x51: 1, 0x52: 1,
        0x53: 1, 0x54: 1, 0x55: 1, 0x56: 1,
        0x57: 1, 0x58: 1, 0x59: 1, 0x5A: 1,
        0x5B: 1, 0x5C: 1, 0x5D: 1, 0x5E: 1,
        0x5F: 1, 0x60: 1, 0x61: 1, 0x62: 1,
        0x63: 1, 0x64: 1, 0x65: 1, 0x66: 1,
        0x67: 1, 0x68: 1, 0x69: 1, 0x6A: 1,
        0x6B: 1, 0x6C: 1, 0x6D: 1, 0x6E: 1,
        0x6F: 1, 0x70: 1, 0x71: 1, 0x72: 1,
        0x73: 1, 0x74: 1, 0x75: 1, 0x76: 1,
        0x77: 1, 0x78: 1, 0x79: 1, 0x7A: 1,
        0x7B: 1, 0x7C: 1, 0x7D: 1, 0x7E: 1,
        0x7F: 1, 0x80: 1, 0x81: 1, 0x82: 1,
        0x83: 1, 0x84: 3, 0x85: 1, 0x86: 1, 0x87: 1, 0x88: 1,
        0x89: 1, 0x8A: 1, 0x8B: 1, 0x8C: 1, 0x8D: 1, 0x8E: 1,
        0x8F: 1, 0x90: 1, 0x91: 1, 0x92: 1, 0x93: 1, 0x94: 1,
        0x95: 1, 0x96: 1, 0x97: 1, 0x98: 1,
        0x99: 3, 0x9A: 3, 0x9B: 3, 0x9C: 3, 0x9D: 3, 0x9E: 3,
        0x9F: 3, 0xA0: 3, 0xA1: 3, 0xA2: 3, 0xA3: 3, 0xA4: 3,
        0xA5: 3, 0xA6: 3, 0xA7: 3, 0xA8: 3, 0xA9: 2,
        0xAC: 1, 0xAD: 1, 0xAE: 1, 0xAF: 1,
        0xB0: 1, 0xB1: 1, 0xB2: 3, 0xB3: 3, 0xB4: 3, 0xB5: 3,
        0xBA: 5, 0xBB: 3, 0xBC: 2, 0xBD: 3, 0xBE: 1, 0xBF: 1,
        0xC0: 3, 0xC1: 3, 0xC2: 3, 0xC3: 3, 0xC4: 4, 0xC5: 3,
        0xC6: 3, 0xC7: 3, 0xC8: 5, 0xC9: 5,
    }
)


def main() -> int:
    ap = argparse.ArgumentParser(description="追踪受限 GL 符号的调用链")
    ap.add_argument("--jar", required=True)
    ap.add_argument(
        "--class",
        dest="class_path",
        required=True,
        help="目标 class 路径，如 com/mojang/blaze3d/platform/GlStateManager.class",
    )
    ap.add_argument("--symbols", nargs="+", required=True)
    args = ap.parse_args()

    jar_path = Path(args.jar)
    symbols = set(args.symbols)

    with zipfile.ZipFile(jar_path) as zf:
        # 1. 目标 class 内部：哪些方法引用了目标符号
        target = ClassFile(zf.read(args.class_path))
        internal: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for m in target.methods:
            for r in m["refs"]:
                if r in symbols:
                    internal[r].append((m["name"], m["desc"]))

        print(f"=== {args.class_path} 内部引用 ===")
        for s in sorted(symbols):
            print(f"\n{s}:")
            if not internal[s]:
                print("    （无直接引用）")
            for mname, mdesc in internal[s]:
                print(f"    {mname}{mdesc}")

        # 2. 全 jar：谁调用了 GlStateManager 的这些包装方法
        wrappers: dict[str, set[str]] = {s: set() for s in symbols}
        for s, ms in internal.items():
            wrappers[s] = {m[0] for m in ms}

        all_wrappers = set().union(*wrappers.values()) if wrappers else set()
        print(f"\n=== 全 jar 中调用这些包装方法的位置 ===")
        ext_callers: dict[str, set[str]] = defaultdict(set)
        for name in zf.namelist():
            if not name.endswith(".class"):
                continue
            try:
                cf = ClassFile(zf.read(name))
            except Exception:
                continue
            owner = name[:-6].replace("/", ".")
            for m in cf.methods:
                for r in m["refs"]:
                    if r in all_wrappers:
                        ext_callers[r].add(f"{owner}.{m['name']}")

        for w in sorted(all_wrappers):
            cs = sorted(ext_callers.get(w, []))
            tag = "（无外部调用 -> 可能是调试/死代码）" if not cs else ""
            print(f"\n{w} 被 {len(cs)} 处调用 {tag}")
            for c in cs[:10]:
                print(f"    {c}")
            if len(cs) > 10:
                print(f"    ... 还有 {len(cs) - 10} 处")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
