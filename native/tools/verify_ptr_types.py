#!/usr/bin/env python3
"""
校验 symbols.def 里的参数类型是否与 gl.xml 权威签名一致（重点：指针）。

【为什么需要这个脚本】

曾经出现过一次严重的真机 SIGSEGV，根因就是符号表里丢了指针 `*`：

    gl.xml   : <param><ptype>GLuint</ptype> *<name>buffers</name></param>
    symbols.def (错误): F void glGenBuffers(GLsizei p0, GLuint p1)

看起来只是「参数少了个星号」，但后果是运行时的静默数据损坏：
在 AArch64（Android arm64-v8a）上，GLuint 只占参数寄存器低 32 位，
LWJGL 传来的 64 位缓冲区地址被截断，驱动按截断后的地址写入 -> SIGSEGV。

    SIGSEGV at __memcpy_aarch64_simd+0x84
    si_addr: 0x00000000a0eaf3cc        <- 明显是被截断的地址
    GL.createCapabilities(...)          <- 内部 glGetIntegerv(..., IntBuffer)

这类 bug 编译不报错、链接不报错，只在真机上崩。因此必须有自动化卡点。

校验内容（逐符号比对）：
  1. 参数个数一致
  2. 每个参数「是否含 *」一致（类型拼写差异不追究，只要能区分指针）
  3. 返回类型「是否含 *」一致
  4. 参数类型名（去掉 * 与 const 后的标识符）一致
     —— 防止 GLint -> GLiptr 这类被截断的类型名

退出码：0 = 通过，1 = 发现不一致。

用法：
    py verify_ptr_types.py --def ../symbols.def --gl-xml .cache/gl.xml
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# 与 gen_symbols_def.py 相同的行格式
LINE_RE = re.compile(
    r"^(?P<kind>[FCS])\s+(?P<ret>.+?)\s+(?P<name>gl[A-Za-z0-9_]+)"
    r"\s*\((?P<params>.*)\)\s*$"
)


def normalize_type(raw: str) -> str:
    """规范类型写法：统一 * 前后空格、压缩空白。"""
    s = re.sub(r"(?<=[A-Za-z0-9_])\*", " *", raw)
    return re.sub(r"\s+", " ", s).strip()


def join_type(el: ET.Element) -> str:
    """
    按元素边界重建类型（与 gen_symbols_def.py 的 join_type 保持一致）。

    跳过 <name> 元素本身，保留其它文本与子元素。这样 <param> 内位于
    <ptype> 之外的 `*`、`const` 才能被保留。
    """
    pieces = []
    if el.text:
        pieces.append(el.text)
    for child in el:
        if child.tag == "name":
            if child.tail:
                pieces.append(child.tail)
            continue
        if child.text:
            pieces.append(child.text)
        if child.tail:
            pieces.append(child.tail)
    return normalize_type("".join(pieces))


def load_gl_xml(path: Path) -> dict[str, dict]:
    """从 gl.xml 读取权威签名：名称 -> {ret, params:[type,...]}。"""
    root = ET.parse(path).getroot()
    out: dict[str, dict] = {}
    for cmd in root.findall("./commands/command"):
        proto = cmd.find("proto")
        if proto is None:
            continue
        name_el = proto.find("name")
        if name_el is None or not name_el.text:
            continue
        name = name_el.text.strip()
        out[name] = {
            "ret": join_type(proto),
            "params": [join_type(p) for p in cmd.findall("param")],
        }
    return out


def split_def_params(params: str) -> list[str]:
    """
    切分 symbols.def 的参数列表，返回**纯类型**（去掉参数名）。

    本项目的 symbols.def 由 gen_symbols_def.py 生成，参数名恒为 p0/p1/p2...：

        F void glActiveShaderProgram(GLuint p0, GLuint p1)

    因此按逗号切分后，只需丢掉末尾的 `pN` 词元即可得到纯类型。
    若不做这一步，比对时会把 `GLuint p0` 与权威的 `GLuint` 视作不同，
    并因 `GLuint p0` 不含 `*` 而误报指针缺失。
    """
    params = params.strip()
    if not params or params == "void":
        return []
    out = []
    for raw in params.split(","):
        raw = raw.strip()
        if not raw:
            continue
        toks = raw.split()
        if len(toks) >= 2 and re.fullmatch(r"p\d+", toks[-1]):
            raw = " ".join(toks[:-1])
        out.append(raw.strip())
    return out


def is_ptr(t: str) -> bool:
    return "*" in t


def ident(t: str) -> str:
    """取出类型里的标识符（去掉 * const 与空白），用于比对类型名是否相同。"""
    cleaned = t.replace("*", " ").replace("const", " ")
    toks = [x for x in cleaned.split() if x]
    return toks[-1] if toks else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 symbols.def 的参数类型")
    ap.add_argument("--def", dest="def_path", required=True)
    ap.add_argument("--gl-xml", required=True)
    ap.add_argument("--required",
                    help="可选：只校验此清单内的符号（如 lwjgl_required.txt）")
    args = ap.parse_args()

    def_file = Path(args.def_path)
    gl_file = Path(args.gl_xml)
    if not def_file.is_file():
        print(f"错误: 找不到 {def_file}", file=sys.stderr)
        return 1
    if not gl_file.is_file():
        print(f"错误: 找不到 {gl_file}", file=sys.stderr)
        return 1

    gl = load_gl_xml(gl_file)

    only: set[str] | None = None
    if args.required:
        rp = Path(args.required)
        if rp.is_file():
            only = {
                ln.strip()
                for ln in rp.read_text(encoding="utf-8-sig").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            }

    # ---- 解析 symbols.def ----
    # 用 utf-8-sig：PowerShell 的 `Set-Content -Encoding UTF8` 会写入 BOM，
    # 带 BOM 时首行会变成 "\ufeffF ..." 导致整行无法解析（静默漏校验）。
    entries: list[dict] = []
    for lineno, line in enumerate(
            def_file.read_text(encoding="utf-8-sig").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("/*") or s.startswith("*") or s.startswith("//"):
            continue
        if s.endswith("*/"):
            continue
        m = LINE_RE.match(s)
        if not m:
            continue
        entries.append({
            "line": lineno,
            "kind": m.group("kind"),
            "ret": m.group("ret").strip(),
            "name": m.group("name"),
            "params": split_def_params(m.group("params")),
        })

    problems: list[str] = []
    checked = 0

    for e in entries:
        name = e["name"]
        if only is not None and name not in only:
            continue
        ref = gl.get(name)
        if ref is None:
            problems.append(f"[{e['line']}] {name}: gl.xml 中找不到该命令，无法校验")
            continue
        checked += 1

        # --- 返回类型：指针性 ---
        if is_ptr(ref["ret"]) != is_ptr(e["ret"]):
            problems.append(
                f"[{e['line']}] {name}: 返回类型指针性不一致 —— "
                f"gl.xml='{ref['ret']}' def='{e['ret']}'"
            )

        # --- 参数个数 ---
        if len(ref["params"]) != len(e["params"]):
            problems.append(
                f"[{e['line']}] {name}: 参数个数不一致 —— "
                f"gl.xml={len(ref['params'])} def={len(e['params'])} "
                f"(gl.xml={ref['params']} def={e['params']})"
            )
            continue

        # --- 逐参数比对 ---
        for i, (rt, dt) in enumerate(zip(ref["params"], e["params"])):
            if is_ptr(rt) != is_ptr(dt):
                problems.append(
                    f"[{e['line']}] {name}: 第 {i} 个参数指针性不一致 —— "
                    f"gl.xml='{rt}' def='{dt}' "
                    f"【危险：AArch64 上会把 64 位指针截断为 32 位，导致 SIGSEGV】"
                )
                continue
            if ident(rt) != ident(dt):
                problems.append(
                    f"[{e['line']}] {name}: 第 {i} 个参数类型名不一致 —— "
                    f"gl.xml='{rt}' def='{dt}'"
                )

    # ---- 覆盖性检查 ----
    if only is not None:
        have = {e["name"] for e in entries}
        missing = sorted(only - have)
        if missing:
            problems.append(f"必需清单中有 {len(missing)} 个符号未导出: {missing[:10]}...")

    print(f"符号总数      : {len(entries)}")
    print(f"已校验        : {checked}")
    if only is not None:
        print(f"必需清单      : {len(only)}")
    print()

    if problems:
        print(f"发现 {len(problems)} 处问题：", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    print("通过：所有参数类型与 gl.xml 权威签名一致（指针性、个数、类型名）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
