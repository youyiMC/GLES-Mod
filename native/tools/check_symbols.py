#!/usr/bin/env python3
"""
检查 libgl_gles.so 的 GL 符号导出覆盖率。

用途（对应任务书验收标准第 8 条）：
    确认 native 库确实导出了 symbols.def 中声明的全部符号。
    LWJGL 通过 dlsym 查找这些符号，任何一个缺失都可能导致启动失败或
    某个渲染功能静默失效，因此这是发布前必须通过的检查。

实现：
    纯 Python 解析 ELF 的 .dynsym 节，不依赖 readelf/nm（Windows 上不易获得）。

用法：
    py check_symbols.py --lib <libgl_gles.so> --def <symbols.def>
    py check_symbols.py --lib <libgl_gles.so> --def <symbols.def> --json-out report.json

退出码：
    0  全部符号已导出
    1  存在缺失符号（或文件/解析错误）
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

# symbols.def 行格式：`F void glBindTexture(GLenum p0, GLuint p1)`
# 三类前缀都要识别：F=转发，C=定制实现，S=安全 stub。
# 漏掉 S 会导致 74 个 stub 被误判为「未声明」，覆盖率报告失真。
DEF_LINE_RE = re.compile(r"^[FCS]\s+.+?\s+(?P<name>gl[A-Za-z0-9_]+)\s*\(")


# ---------------------------------------------------------------------
# 极简 ELF 解析（仅取 .dynsym 中的导出符号名）
# ---------------------------------------------------------------------

ELF_MAGIC = b"\x7fELF"
SHT_DYNSYM = 11
SHT_SYMTAB = 2


def _read_cstr(data: bytes, offset: int) -> str:
    end = data.find(b"\x00", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", "replace")


def parse_elf_symbols(path: Path, dynamic_only: bool = True) -> set[str]:
    """
    解析 ELF，返回符号名集合。

    同时读取 .dynsym（动态导出）与 .symtab（若存在，用于诊断未导出的符号）。
    dynamic_only=True 时只返回 .dynsym 中的符号，这才是 dlsym 能看到的集合。
    """
    data = path.read_bytes()
    if data[:4] != ELF_MAGIC:
        raise ValueError("不是 ELF 文件")

    is64 = data[4] == 2
    is_le = data[5] == 1
    endian = "<" if is_le else ">"

    if is64:
        # ELF64 header: e_shoff 位于 0x28, e_shentsize 0x3A, e_shnum 0x3C, e_shstrndx 0x3E
        e_shoff = struct.unpack_from(endian + "Q", data, 0x28)[0]
        e_shentsize = struct.unpack_from(endian + "H", data, 0x3A)[0]
        e_shnum = struct.unpack_from(endian + "H", data, 0x3C)[0]
        e_shstrndx = struct.unpack_from(endian + "H", data, 0x3E)[0]
    else:
        e_shoff = struct.unpack_from(endian + "I", data, 0x20)[0]
        e_shentsize = struct.unpack_from(endian + "H", data, 0x2E)[0]
        e_shnum = struct.unpack_from(endian + "H", data, 0x30)[0]
        e_shstrndx = struct.unpack_from(endian + "H", data, 0x32)[0]

    if e_shoff == 0 or e_shnum == 0:
        raise ValueError("ELF 无节头表")

    def section_header(idx: int) -> dict:
        off = e_shoff + idx * e_shentsize
        if is64:
            name, stype = struct.unpack_from(endian + "II", data, off)
            offset = struct.unpack_from(endian + "Q", data, off + 0x18)[0]
            size = struct.unpack_from(endian + "Q", data, off + 0x20)[0]
            link = struct.unpack_from(endian + "I", data, off + 0x28)[0]
            entsize = struct.unpack_from(endian + "Q", data, off + 0x38)[0]
        else:
            name, stype = struct.unpack_from(endian + "II", data, off)
            offset = struct.unpack_from(endian + "I", data, off + 0x10)[0]
            size = struct.unpack_from(endian + "I", data, off + 0x14)[0]
            link = struct.unpack_from(endian + "I", data, off + 0x18)[0]
            entsize = struct.unpack_from(endian + "I", data, off + 0x24)[0]
        return {
            "name": name, "type": stype, "offset": offset,
            "size": size, "link": link, "entsize": entsize,
        }

    sections = [section_header(i) for i in range(e_shnum)]
    shstr = sections[e_shstrndx]
    shstr_data = data[shstr["offset"] : shstr["offset"] + shstr["size"]]

    names: set[str] = set()

    for sec in sections:
        if sec["type"] not in (SHT_DYNSYM, SHT_SYMTAB):
            continue
        if dynamic_only and sec["type"] != SHT_DYNSYM:
            continue
        if sec["type"] == SHT_SYMTAB and dynamic_only:
            continue

        strtab = sections[sec["link"]]
        strtab_data = data[strtab["offset"] : strtab["offset"] + strtab["size"]]

        entsize = sec["entsize"] or (24 if is64 else 16)
        count = sec["size"] // entsize

        for i in range(count):
            off = sec["offset"] + i * entsize
            if off + entsize > len(data):
                break
            if is64:
                st_name = struct.unpack_from(endian + "I", data, off)[0]
                st_info = data[off + 4]
                st_shndx = struct.unpack_from(endian + "H", data, off + 6)[0]
            else:
                st_name = struct.unpack_from(endian + "I", data, off)[0]
                st_info = data[off + 12]
                st_shndx = struct.unpack_from(endian + "H", data, off + 14)[0]

            if st_name == 0:
                continue
            # 只看已定义（非 UND）的符号
            if st_shndx == 0:
                continue
            # 只要函数或对象类型
            sym_type = st_info & 0xF
            if sym_type not in (1, 2):  # STT_OBJECT=1, STT_FUNC=2
                continue

            nm = _read_cstr(strtab_data, st_name)
            if nm:
                names.add(nm)

    return names


# ---------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------

def load_def_symbols(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("/*") or s.startswith("*") or s.startswith("//"):
            continue
        if s.endswith("*/"):
            continue
        m = DEF_LINE_RE.match(s)
        if m:
            out.append(m.group("name"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="检查 GL 符号导出覆盖率")
    ap.add_argument("--lib", required=True, help="libgl_gles.so 路径")
    ap.add_argument("--def", dest="def_path", required=True, help="symbols.def 路径")
    ap.add_argument("--json-out", help="可选的 JSON 报告路径")
    ap.add_argument("--list-missing-limit", type=int, default=50)
    args = ap.parse_args()

    lib = Path(args.lib)
    if not lib.is_file():
        print(f"错误: 找不到 {lib}", file=sys.stderr)
        return 1

    try:
        exported = parse_elf_symbols(lib, dynamic_only=True)
    except Exception as e:
        print(f"错误: 解析 ELF 失败: {e}", file=sys.stderr)
        return 1

    expected = load_def_symbols(Path(args.def_path))
    if not expected:
        print("错误: symbols.def 中未解析出任何符号", file=sys.stderr)
        return 1

    expected_set = set(expected)
    missing = sorted(expected_set - exported)
    present = expected_set & exported
    extra = sorted(
        n for n in exported
        if n.startswith("gl") and n not in expected_set
    )

    coverage = len(present) / len(expected_set) * 100

    print(f"库文件            : {lib}")
    print(f"应导出（symbols.def）: {len(expected_set)}")
    print(f"实际导出          : {len(present)}")
    print(f"覆盖率            : {coverage:.1f}%")

    if missing:
        print()
        print(f"缺失符号 ({len(missing)}):")
        for n in missing[: args.list_missing_limit]:
            print(f"  {n}")
        if len(missing) > args.list_missing_limit:
            print(f"  ... 还有 {len(missing) - args.list_missing_limit} 个")

    if extra:
        print()
        print(f"额外导出（未在 def 中声明，共 {len(extra)}）:")
        for n in extra[:20]:
            print(f"  {n}")
        if len(extra) > 20:
            print(f"  ... 还有 {len(extra) - 20} 个")

    if args.json_out:
        report = {
            "lib": str(lib),
            "expected": len(expected_set),
            "exported_matching": len(present),
            "coverage_percent": round(coverage, 2),
            "missing": missing,
            "extra_gl_symbols": extra,
            "backend_symbols": sorted(n for n in exported if n.startswith("glesmod_")),
        }
        Path(args.json_out).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print()
        print(f"报告已写入: {args.json_out}")

    if missing:
        print()
        print("结果: 存在缺失符号，检查失败")
        return 1

    print()
    print("结果: 全部符号已导出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
