#!/usr/bin/env python3
"""
扫描 Minecraft / NeoForge 的 class 文件，找出它们**实际调用**了哪些
被本库当作「安全 stub」导出的 GL 函数。

【为什么必须做这件事】

symbols.def 把 517 个 GL 函数导出为空实现（stub），理由见 O-02：
    不导出 -> LWJGL 解析失败 -> NullPointerException（不可捕获，早期初始化即崩）
    导出 stub -> 有有效指针，游戏能继续跑

副作用是：**被 stub 的函数会静默失效**。调用方不会收到任何错误，
只是那次 GL 操作什么也没做。而 LWJGL 的 GLxx 类是逐个方法调用原生的，
所以「MC 调用了某个 stub」这件事完全可以静态判定 ——
只要在 class 常量池里找到对应的方法名即可。

当前症状「方块与实体的面渲染错位，但材质正常」正属于这一类：
几何相关的某个调用被静默吞掉，纹理路径不受影响。

【用法】
    py find_stub_usage.py --jar <minecraft_client.jar> [--jar <neoform...>]
                          [--symbols-def native/symbols.def]
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
import zipfile
from pathlib import Path

# 从 class 文件字节流里粗取所有 glXxx 标识符。
# class 常量池里的方法名是原样的 UTF8，所以直接按字节按词法取就可以，
# 不需要真的解析 class 结构。用 latin-1 解码可保证不会因非法 UTF8 丢字节。
TOKEN_RE = re.compile(rb"gl[A-Z][A-Za-z0-9_]*")

DEFAULT_DEF = "native/symbols.def"


def load_def(def_path: Path) -> dict[str, set[str]]:
    """
    返回 {'S': {...stub...}, 'C': {...custom...}, 'F': {...forward...}}。

    行格式：类别 + 返回类型 + 函数名(参数...)，例如
        F void glActiveTexture(GLenum p0)
        C void * glMapBuffer(GLenum p0, GLenum p1)   <-- void * 占两个 token
        S const GLubyte * glGetString(GLenum p0)

    【不要假定函数名在第 3 个位置】指针/const 返回类型会多占 token，
      函数名可能落到第 4 个甚至第 5 个。写死 parts[2] 会让所有指针返回值
      的函数被静默跳过（如 glMapBuffer），而在 stub 审计里「跳过」
      等同于「假阴性」—— 明明被调用了却报告未使用。
      第一次实现就踩了这个坑，统计出「转发 F = 7」这种荒唐数字。
      **统计结果不合常理时，先怀疑解析器，不要相信结论。**
    """
    out: dict[str, set[str]] = {"S": set(), "C": set(), "F": set()}
    for line in def_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("/*"):
            continue
        parts = line.split()
        if len(parts) < 3 or parts[0] not in out:
            continue
        for tok in parts[1:]:
            if tok.startswith("gl") and "(" in tok:
                name = tok.split("(", 1)[0]
                if name.startswith("gl"):
                    out[parts[0]].add(name)
                break
    return out


def scan_jar(jar: Path, interesting: set[str]) -> dict[str, set[str]]:
    """
    返回 {符号名: {引用它的 class 名, ...}}。
    只看 class 文件；资源文件不含方法引用。
    """
    hits: dict[str, set[str]] = collections.defaultdict(set)
    try:
        z = zipfile.ZipFile(jar)
    except zipfile.BadZipFile:
        print(f"  跳过（非有效 zip）: {jar}", file=sys.stderr)
        return hits

    with z:
        for info in z.infolist():
            if not info.filename.endswith(".class"):
                continue
            try:
                blob = z.read(info.filename)
            except KeyError:
                continue
            for m in TOKEN_RE.finditer(blob):
                name = m.group(0).decode("ascii")
                if name in interesting:
                    hits[name].add(info.filename)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(
        description="找出 MC/NeoForge 实际调用但被本库 stub 掉的 GL 函数")
    ap.add_argument("--jar", action="append", required=True,
                    help="待扫描的 jar（可多次指定）")
    ap.add_argument("--symbols-def", dest="symbols_def", default=None,
                    help="symbols.def 路径")
    ap.add_argument("--quiet-f", action="store_true",
                    help="不报告 F（转发）类命中，只关注 stub/custom")
    args = ap.parse_args()

    # 定位 symbols.def：默认相对仓库根（本脚本在 native/tools/ 下）
    #
    # 注意参数名用 --symbols-def 而非 --def：
    #   argparse 会把属性存为 args.def，而 `def` 是 Python 关键字，
    #   `args.def` 是语法错误（不是运行时错误）。
    if args.symbols_def:
        def_path = Path(args.symbols_def)
    else:
        here = Path(__file__).resolve().parent
        def_path = here.parent / "symbols.def"
    if not def_path.is_file():
        print(f"错误: 找不到 symbols.def: {def_path}", file=sys.stderr)
        return 2

    kinds = load_def(def_path)
    stubs = kinds["S"]
    customs = kinds["C"]
    forwards = kinds["F"]

    print(f"symbols.def : {def_path}")
    print(f"  转发 F = {len(forwards)}   定制 C = {len(customs)}   "
          f"stub S = {len(stubs)}")
    print()

    watch = set(stubs) | set(customs) | (set() if args.quiet_f else set(forwards))

    all_hits: dict[str, set[str]] = collections.defaultdict(set)
    all_classes = 0
    for j in args.jar:
        jp = Path(j)
        if not jp.is_file():
            print(f"  跳过（不存在）: {jp}", file=sys.stderr)
            continue
        print(f"扫描: {jp.name} ({jp.stat().st_size / 1e6:.1f} MB)")
        hits = scan_jar(jp, watch)
        for k, v in hits.items():
            all_hits[k].update(v)
        with zipfile.ZipFile(jp) as z:
            all_classes += sum(1 for n in z.namelist() if n.endswith(".class"))

    print()
    print(f"共扫描 {all_classes} 个 class")

    def show(title: str, names: set[str], limit: int = 400) -> int:
        found = sorted(n for n in names if n in all_hits)
        print()
        print(f"===== {title}：{len(found)} / {len(names)} 个被引用 =====")
        for n in found[:limit]:
            cl = sorted(all_hits[n])
            example = cl[0] if cl else "?"
            print(f"  {n:<48} 例: {example}")
        if len(found) > limit:
            print(f"  ...（共 {len(found)} 个）")
        return len(found)

    n_stub = show("被 stub 掉但仍被 MC 调用的函数（危险）", stubs)
    n_custom = show("定制实现（应当被调用）", customs)
    if not args.quiet_f:
        show("直接转发（F）", forwards)

    print()
    print("=" * 70)
    if n_stub:
        print(f"!! 有 {n_stub} 个 stub 函数被 MC/NeoForge 实际调用 ——")
        print("   这些调用会静默失效，必须改为转发或真正实现。")
    else:
        print("结论: MC/NeoForge 没有调用任何 stub 函数。")
        print("      「安全 stub」这一假设在当前版本上成立。")
    return 1 if n_stub else 0


if __name__ == "__main__":
    sys.exit(main())
