#!/usr/bin/env python3
"""
统计 Minecraft / NeoForge 实际使用了哪些 GL 调用（按分组）。

【为什么需要】

「方块与实体面渲染错位」这类几何问题，取决于 MC 走的是哪条绘制路径：
    glDrawElements               普通索引绘制
    glDrawElementsBaseVertex     带基准顶点偏移（多个网格共用同一 VBO）
    glDrawElementsInstanced      实例化
    glMultiDrawElements*         多重绘制
这些路径在 ES 上的可用性各不相同，降级方式也不同。
必须先用**证据**确定 MC 走哪条路，而不是凭版本号猜。

做法：GL 方法的调用在 class 常量池里留下原样的方法名字符串，
因此在 class 字节流里做词法扫描即可精确判定「引用了哪些 glXxx」。
这比猜测或逐个真机试错快得多，也不需要反编译。

【用法】
    py scan_gl_calls.py --jar <minecraft_client.jar>
    py scan_gl_calls.py --jar <a.jar> --jar <b.jar> --group draws
    py scan_gl_calls.py --jar <a.jar> --tokens glFoo glBar
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
import zipfile
from pathlib import Path

TOKEN_RE = re.compile(rb"gl[A-Z][A-Za-z0-9_]*")

# 按主题分组，便于一次看清某条路径的全貌
GROUPS: dict[str, list[str]] = {
    "绘制路径（核心）": [
        "glDrawArrays", "glDrawElements",
        "glDrawElementsBaseVertex", "glDrawArraysBaseVertex",
        "glDrawElementsInstanced", "glDrawArraysInstanced",
        "glDrawElementsInstancedBaseVertex",
        "glMultiDrawArrays", "glMultiDrawElements",
        "glMultiDrawElementsBaseVertex",
        "glMultiDrawArraysIndirect", "glMultiDrawElementsIndirect",
        "glDrawRangeElements", "glDrawRangeElementsBaseVertex",
        "glDrawElementsIndirect",
    ],
    "实例化配置": [
        "glVertexAttribDivisor", "glVertexAttribDivisorARB",
        "glDrawArraysInstancedBaseInstance",
        "glVertexAttribBinding", "glBindVertexBuffer",
    ],
    "顶点属性": [
        "glVertexAttribPointer", "glVertexAttribIPointer",
        "glVertexAttribPointerARB", "glVertexAttribIPointerEXT",
        "glEnableVertexAttribArray", "glVertexAttribFormat",
        "glVertexAttribIFormat",
    ],
    "缓冲上传 / 映射": [
        "glBufferData", "glBufferSubData", "glBufferStorage",
        "glMapBuffer", "glMapBufferRange", "glUnmapBuffer",
        "glFlushMappedBufferRange", "glCopyBufferSubData",
        "glGetBufferSubData", "glInvalidateBufferData",
    ],
    "同步对象": [
        "glFenceSync", "glClientWaitSync", "glWaitSync",
        "glDeleteSync", "glIsSync", "glGetSynciv",
    ],
    "深度 / 裁剪 / 面模式": [
        "glDepthRange", "glDepthRangef", "glClipControl",
        "glPolygonMode", "glPolygonOffset", "glPolygonOffsetClamp",
        "glClearDepth", "glClearDepthf", "glDepthFunc", "glDepthMask",
    ],
    "混合 / 逻辑": [
        "glLogicOp", "glBlendFuncSeparate", "glBlendEquationSeparate",
        "glBlendColor", "glBlendFuncSeparatei",
    ],
    "纹理": [
        "glTexImage2D", "glTexSubImage2D", "glTexStorage2D",
        "glTexParameterIiv", "glPixelStorei", "glGetTexImage",
        "glTexBuffer", "glGenerateMipmap",
    ],
    "状态查询": [
        "glGetString", "glGetStringi", "glGetIntegerv", "glGetError",
        "glGetTexLevelParameteriv", "glGetBufferParameteriv",
    ],
}


def scan(jar: Path, tokens: set[str]) -> tuple[dict[str, set[str]], int]:
    hits: dict[str, set[str]] = collections.defaultdict(set)
    n_classes = 0
    with zipfile.ZipFile(jar) as z:
        for info in z.infolist():
            if not info.filename.endswith(".class"):
                continue
            n_classes += 1
            blob = z.read(info.filename)
            for m in TOKEN_RE.finditer(blob):
                name = m.group(0).decode("ascii")
                if name in tokens:
                    hits[name].add(info.filename)
    return hits, n_classes


def scan_all_gl(jar: Path) -> tuple[dict[str, set[str]], int]:
    """取出 jar 里出现的**全部** gl* token（不做白名单过滤）。"""
    hits: dict[str, set[str]] = collections.defaultdict(set)
    n_classes = 0
    with zipfile.ZipFile(jar) as z:
        for info in z.infolist():
            if not info.filename.endswith(".class"):
                continue
            n_classes += 1
            blob = z.read(info.filename)
            for m in TOKEN_RE.finditer(blob):
                hits[m.group(0).decode("ascii")].add(info.filename)
    return hits, n_classes


def parse_def_line(line: str) -> tuple[str, str] | None:
    """
    解析 symbols.def 的一行，返回 (类别, 函数名)；不是符号行则返回 None。

    行格式：类别 + 返回类型 + 函数名(参数...)，例如
        F void glActiveTexture(GLenum p0)
        C void * glMapBuffer(GLenum p0, GLenum p1)   <-- 注意 void * 占两个 token
        S const GLubyte * glGetString(GLenum p0)

    【不要假定函数名在第 3 个位置】
      指针/const 返回类型会多占 token，函数名可能落到第 4 个甚至第 5 个。
      早期版本写死 parts[2]，于是所有指针返回值的函数被静默跳过
      （例如 glMapBuffer）—— 而「跳过」在 stub 审计里等同于
      「假阴性：明明被调用了却报告未使用」，非常危险。
      因此改为：找到第一个以 gl 开头且带 '(' 的 token。
    """
    parts = line.split()
    if len(parts) < 3 or parts[0] not in ("F", "C", "S"):
        return None
    for tok in parts[1:]:
        if tok.startswith("gl") and "(" in tok:
            name = tok.split("(", 1)[0]
            if name.startswith("gl"):
                return parts[0], name
    return None


def load_def(def_path: Path) -> dict[str, str]:
    """返回 {名称: 'F'/'C'/'S'}。"""
    out: dict[str, str] = {}
    for line in def_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("/*"):
            continue
        parsed = parse_def_line(line)
        if parsed is not None:
            out[parsed[1]] = parsed[0]
    return out


def coverage_report(jars: list[Path], def_path: Path) -> int:
    """
    完整性审计：把 MC 实际用到的全部 gl* 符号与 symbols.def 对照。

    【为什么这一步很关键】
      本库只导出 symbols.def 里的符号。若 MC 调用了清单外的 gl 函数，
      LWJGL 解析失败 -> 该调用不可用 -> 静默的功能缺失。
      这是「stub 静默失效」之外的第二种静默缺口，必须排除。

    【注意反向噪声】
      class 常量池里也会出现非函数的 gl* 前缀串
      （JNI 描述符 "glGetString(Ljava/lang/String;)J" 之类、
        以及 org.lwjgl.opengl.GLxx 的类名 GL11/GL30 等），
      以及 LWJGL 自己的 Java 包装方法名（glGenTextures 等）。
      因此「清单外」的条目需要人工过一眼，不能直接当成 bug。
    """
    print(f"symbols.def: {def_path}")
    kinds = load_def(def_path)
    n_f = sum(1 for v in kinds.values() if v == "F")
    n_c = sum(1 for v in kinds.values() if v == "C")
    n_s = sum(1 for v in kinds.values() if v == "S")
    print(f"  转发 F={n_f}  定制 C={n_c}  stub S={n_s}  合计={len(kinds)}")
    print()

    used: dict[str, set[str]] = collections.defaultdict(set)
    total_classes = 0
    for j in jars:
        if not j.is_file():
            print(f"跳过（不存在）: {j}", file=sys.stderr)
            continue
        print(f"扫描: {j.name} ({j.stat().st_size / 1e6:.1f} MB)")
        h, n = scan_all_gl(j)
        total_classes += n
        for k, v in h.items():
            used[k].update(v)

    # 过滤明显不是 GL 函数的 token
    def looks_like_gl_func(name: str) -> bool:
        if not name.startswith("gl"):
            return False
        body = name[2:]
        # 形如 GL11 / GL30 —— 长度 2-3 且全大写数字
        if len(body) <= 3 and body.isupper() or (body.isdigit()):
            return False
        return True

    funcs = {k: v for k, v in used.items() if looks_like_gl_func(k)}

    in_def = {k: v for k, v in funcs.items() if k in kinds}
    not_in_def = {k: v for k, v in funcs.items() if k not in kinds}

    print()
    print("=" * 72)
    print(f"MC/NeoForge 引用的 gl* 标识符：{len(funcs)} 个（共 {total_classes} class）")
    print("=" * 72)

    by_kind: dict[str, list[str]] = collections.defaultdict(list)
    for name in in_def:
        by_kind[kinds[name]].append(name)

    print()
    print(f"【清单内 · 直接转发 F：{len(by_kind['F'])} 个】")
    print("  " + ", ".join(sorted(by_kind["F"])))

    print()
    print(f"【清单内 · 定制实现 C：{len(by_kind['C'])} 个】")
    for n in sorted(by_kind["C"]):
        print(f"  {n:<40} ({len(in_def[n])} 处引用)")

    print()
    print(f"【清单内 · 安全 stub S：{len(by_kind['S'])} 个】  <-- 若非空即为静默失效点")
    for n in sorted(by_kind["S"]):
        print(f"  {n:<40} ({len(in_def[n])} 处引用)")

    print()
    print(f"【不在清单内：{len(not_in_def)} 个】  <-- 需人工确认是否为真实 GL 函数")
    for n in sorted(not_in_def):
        print(f"  {n:<40} ({len(not_in_def[n])} 处引用)")

    print()
    print("=" * 72)
    danger = len(by_kind["S"])
    if danger:
        print(f"!! {danger} 个被 MC 调用的函数仍是 stub —— 这些调用会静默失效。")
    else:
        print("OK: MC 调用的函数没有一个落在 stub 集合里。")
    return 1 if danger else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="统计 MC 实际使用的 GL 调用")
    ap.add_argument("--jar", action="append", required=True)
    ap.add_argument("--group", action="append", default=None,
                    choices=sorted(GROUPS), help="只看某个分组（可多次）")
    ap.add_argument("--tokens", nargs="*", default=None, help="自定义符号列表")
    ap.add_argument("--show-classes", type=int, default=0,
                    help="对每个命中的符号额外列出前 N 个调用类")
    ap.add_argument("--coverage", action="store_true",
                    help="完整性审计：全部 gl* 符号对照 symbols.def")
    ap.add_argument("--symbols-def", dest="symbols_def", default=None,
                    help="symbols.def 路径（配合 --coverage）")
    args = ap.parse_args()

    if args.coverage:
        if args.symbols_def:
            def_path = Path(args.symbols_def)
        else:
            here = Path(__file__).resolve().parent
            def_path = here.parent / "symbols.def"
        if not def_path.is_file():
            print(f"错误: 找不到 symbols.def: {def_path}", file=sys.stderr)
            return 2
        return coverage_report([Path(j) for j in args.jar], def_path)

    if args.tokens:
        wanted_groups = {"自定义": list(args.tokens)}
    else:
        names = args.group if args.group else sorted(GROUPS)
        wanted_groups = {k: GROUPS[k] for k in names}

    all_tokens: set[str] = set()
    for v in wanted_groups.values():
        all_tokens.update(v)

    all_hits: dict[str, set[str]] = collections.defaultdict(set)
    total_classes = 0
    for j in args.jar:
        jp = Path(j)
        if not jp.is_file():
            print(f"跳过（不存在）: {jp}", file=sys.stderr)
            continue
        print(f"扫描: {jp.name} ({jp.stat().st_size / 1e6:.1f} MB)")
        hits, n = scan(jp, all_tokens)
        total_classes += n
        for k, v in hits.items():
            all_hits[k].update(v)

    print(f"共 {total_classes} 个 class")
    print()

    n_used_total = 0
    for gname, toks in wanted_groups.items():
        print("=" * 72)
        print(f"  {gname}")
        print("=" * 72)
        used = [t for t in toks if t in all_hits]
        unused = [t for t in toks if t not in all_hits]
        n_used_total += len(used)
        if used:
            print("  【实际使用】")
            for t in used:
                cl = sorted(all_hits[t])
                print(f"    {t:<44} 引用 {len(cl)} 处")
                if args.show_classes:
                    for c in cl[:args.show_classes]:
                        print(f"        {c}")
        if unused:
            print("  【未使用】")
            print("    " + ", ".join(unused))
        print()

    print("=" * 72)
    print(f"合计：{n_used_total} 个 GL 符号被实际调用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
