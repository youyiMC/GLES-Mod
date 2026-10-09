#!/usr/bin/env python3
"""
从 symbols.def 生成 GL 转发层源码。

用途：
    本项目需要导出约 200 个 GL 符号，其中绝大多数是「解析同名 GLES 函数
    指针后直接调用」。手写这些转发函数既繁琐又易错，因此采用生成方式。

设计要点：
    1. 每个 F 类型符号生成一个同名导出函数，函数体内调用 glesym_resolve()
       取得的函数指针。指针首次使用时解析并缓存（避免每帧重复 dlsym）。
    2. 解析失败时不崩溃：记录降级事件并直接返回。返回值类型为 void 之外
       时返回零值（这是保守且安全的选择——GL 调用失败时游戏通常仍可运行）。
    3. C 类型（定制实现）只生成声明，实现写在 src/custom.c。
    4. 生成 __attribute__((visibility("default"))) 标记，确保符号被导出，
       这是 LWJGL 能通过 dlsym 找到它们的前提。

用法：
    py gen_gl_forwarders.py --def symbols.def --out src/generated_forwarders.c
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 解析 symbols.def 中的一行
# F = 转发，C = 定制实现（在 custom.c），S = 安全 stub
LINE_RE = re.compile(
    r"^(?P<kind>[FCS])\s+(?P<ret>.+?)\s+(?P<name>gl[A-Za-z0-9_]+)\s*\((?P<params>.*)\)\s*$"
)

# 参数类型到「传给函数的变量名」的映射由生成器按位置处理，不需要静态表。
# 但 void 参数需要特殊处理。
VOID_PARAM = "void"

# 返回值零值表
ZERO_VALUES = {
    "void": None,
    "GLenum": "0",
    "GLboolean": "GL_FALSE",
    "GLuint": "0",
    "GLint": "0",
    "GLfloat": "0.0f",
    "GLsizei": "0",
    "GLuint64": "0",
    "GLint64": "0",
    "GLintptr": "0",
    "GLsizeiptr": "0",
    "GLdouble": "0.0",
    "void *": "NULL",
    "const void *": "NULL",
    "const GLubyte *": "NULL",
    "const GLchar *": "NULL",
    # 同步对象句柄。GL 3.2 core 的 glFenceSync/glIsSync 用它；
    # ES 3.0+ 有对应能力，故多为转发；万一缺失时返回 0 表示无效句柄。
    "GLsync": "NULL",
}


def split_params(params: str) -> list[tuple[str, str]]:
    """
    切分参数列表，返回 [(类型, 变量名)]。

    需要处理：
      - 函数指针参数（本项目暂不支持，遇到即报错）
      - 数组/指针参数如 `const GLuint *`
      - 只有类型、没有变量名的参数（如 `void`、`GLenum`）
      - 类型名本身含大写字母与数字（GLdouble、GLsizeiptr、GLuint64）

    注意：`GLdouble` 这类类型名不能按「以大写字母为界」切分，否则会被错误
    拆成 `G` + `Ldouble`。判定规则是「最后一个词是否为合法变量名」，而变量名
    的约定是「全小写开头」。因此仅当最后一个词以小写字母开头时，才认为它是
    变量名。
    """
    params = params.strip()
    if not params or params == VOID_PARAM:
        return []
    if "(*" in params:
        # 形如 void (*cb)(...) 的复杂参数，暂不支持
        raise ValueError(f"不支持的参数形式（函数指针）: {params}")

    out = []
    for i, raw in enumerate(params.split(",")):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split()
        if len(parts) >= 2 and re.match(r"^[a-z_][A-Za-z0-9_]*$", parts[-1]):
            # 最后一个词是合法变量名（小写开头）
            var = parts[-1]
            ptype = " ".join(parts[:-1])
        else:
            # 只有类型，没有变量名 -> 合成一个
            var = f"arg{i}"
            ptype = raw
        out.append((ptype.strip(), var))
    return out


def parse_def(path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """解析 symbols.def，返回 (转发, 定制, stub) 三个列表。"""
    forward, custom, stub = [], [], []
    seen = set()
    # utf-8-sig：容忍 BOM（PowerShell Set-Content 会写入），否则首行会被静默跳过
    for lineno, line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("/*") or s.startswith("*") or s.startswith("//"):
            continue
        if s.endswith("*/"):
            continue
        m = LINE_RE.match(s)
        if not m:
            print(f"警告: 第 {lineno} 行无法解析，已跳过: {s}", file=sys.stderr)
            continue
        name = m.group("name")
        if name in seen:
            print(f"警告: 第 {lineno} 行符号重复 {name}，已跳过", file=sys.stderr)
            continue
        seen.add(name)
        try:
            params = split_params(m.group("params"))
        except ValueError as e:
            print(f"警告: 第 {lineno} 行 {e}", file=sys.stderr)
            continue
        entry = {
            "kind": m.group("kind"),
            "ret": m.group("ret").strip(),
            "name": name,
            "params": sanitize_params(params),
        }
        kind = m.group("kind")
        if kind == "C":
            custom.append(entry)
        elif kind == "S":
            stub.append(entry)
        else:
            forward.append(entry)
    return forward, custom, stub


# C 语言保留字与非标识符安全的参数名。gl.xml 里的参数名偶尔会撞上，
# 例如 `near`/`far`（Windows 头文件宏）、`type`（部分 SDK 定义为宏）。
# 统一加前缀是最省事且不会出错的做法。
UNSAFE_PARAM_NAMES = {
    "near", "far", "small", "type", "new", "class", "template", "this",
    "operator", "delete", "and", "or", "not", "xor", "index", "string",
    "params", "base", "n", "i", "j",
}


def sanitize_params(params: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """把可能冲突的参数名统一加重前缀，并处理重复名。"""
    out = []
    seen: dict[str, int] = {}
    for ptype, name in params:
        new = name
        if name in UNSAFE_PARAM_NAMES:
            new = "p_" + name
        # 处理重复参数名（极少见，但 gl.xml 里出现过）
        if new in seen:
            seen[new] += 1
            new = f"{new}{seen[new]}"
        else:
            seen[new] = 0
        out.append((ptype, new))
    return out


def render_signature(ret: str, name: str, params: list[tuple[str, str]], extern: bool = False) -> str:
    """渲染函数签名（带参数名，用于定义）。"""
    plist = ", ".join(f"{t} {v}" for t, v in params) if params else "void"
    prefix = "extern " if extern else ""
    return f"{prefix}{ret} {name}({plist})"


def render_cast(ret: str, params: list[tuple[str, str]]) -> str:
    """
    渲染函数指针转换类型（匿名，用于把 void* 转为可调用的函数指针）。

    必须是匿名的：C 语法中 `(void (*)(GLenum))ptr` 是合法转换，
    而 `(void (*fp)(GLenum))ptr` 会被解析为声明而非转换。
    """
    plist = ", ".join(t for t, _ in params) if params else "void"
    return f"{ret} (*)({plist})"


def gen_stub(e: dict) -> str:
    """
    生成安全 stub：GLES 不提供该函数时使用。

    【为什么必须有 stub，而不是干脆不导出】
        LWJGL 在 GL.createCapabilities() 时需要一批函数。对必需函数，
        缺失会让 LWJGL 抛 NullPointerException 硬崩溃，且该异常在早期
        初始化阶段无法被上层捕获——游戏直接退出。
        导出为 stub 则 LWJGL 能拿到有效指针，调用时返回零值并记一次降级，
        游戏继续运行（该功能失效，但不崩）。

    这是用真机验证得出的结论：参见 docs/test-log-analysis.md 测试 #3。
    """
    ret, name, params = e["ret"], e["name"], e["params"]
    sig = render_signature(ret, name, params)
    zero = ZERO_VALUES.get(ret)

    lines = []
    lines.append(f"/* {name} —— GLES 不提供，安全 stub */")
    lines.append(f"GLESMOD_EXPORT {sig}")
    lines.append("{")
    lines.append("    glesmod_lazy_init();")
    lines.append(f'    GLESMOD_TRACE("{name}");')

    # 参数可能全未使用；显式 (void) 掉，避免 -Wunused-parameter
    if params:
        for _, v in params:
            lines.append(f"    (void){v};")

    lines.append(f'    glesmod_report_stub("{name}");')

    if zero is not None:
        lines.append(f"    return {zero};")
    lines.append("}")
    return "\n".join(lines)


def gen_forwarder(e: dict) -> str:
    """生成单个转发函数。"""
    ret, name, params = e["ret"], e["name"], e["params"]
    sig = render_signature(ret, name, params)
    zero = ZERO_VALUES.get(ret)

    lines = []
    lines.append(f"/* {name} —— 转发至同名 GLES 函数 */")
    lines.append(f"GLESMOD_EXPORT {sig}")
    lines.append("{")

    # 触发惰性初始化。
    #
    # 【为什么原来每个转发函数都要调用 glesmod_lazy_init()】
    #   1. 诊断能力。任何一次 GL 调用都会触发一次初始化尝试，成功后写出
    #      status.json 并输出一行日志。否则若 Minecraft 恰好没走到那些定制
    #      函数（glShaderSource/glGetError 等），我们在真机上就拿不到任何
    #      来自本库的证据，无法判断库是否真的在调用链上。
    #   2. 首次调用后 pthread_once 只剩一次原子读，开销可忽略。
    #
    # 不会造成递归：maybe_probe 内部用原子状态位防止重入（见 core.c）。
    #
    # 【★ 改为 GLESMOD_HOTPATH —— 依据是反汇编实测，不是猜测 ★】
    #   上述第 2 条「开销可忽略」是**没有量过**的假设。用
    #   native/tools/hotpath_cost.py 反汇编 optimized 产物后发现：
    #     到达真正的 GLES 调用需要 29 条指令，其中真正必要的只有尾部 5 条。
    #     第 7 条是跨编译单元的 PLT 调用，它迫使编译器先把两个参数存进
    #     callee-saved 寄存器（第 5、6 条）并在返回后恢复 —— 仅为了保持这次
    #     调用的 ABI 正确性。
    #   按每帧 5e4 次 GL 调用估算，这 24 条序言约合 0.2 ms/帧；
    #   在 300 FPS（3.3 ms/帧）下占 6%。
    #
    #   GLESMOD_HOTPATH 把「快速路径检查」内联进函数体：
    #     稳态 -> adrp/ldr/cbnz，4 条指令，无跨单元调用、无栈帧
    #     首次 -> 跳 glesmod_on_first_call 完成全部初始化
    lines.append("    GLESMOD_HOTPATH(" + '"%s"' % name + ");")

    # 解析函数指针
    lines.append("    static glesmod_proc_t fn = NULL;")
    lines.append("    if (!fn) {")
    lines.append(f'        fn = glesym_resolve("{name}");')
    lines.append("        if (!fn) {")
    lines.append(f'            glesmod_report_missing("{name}");')
    if zero is not None:
        lines.append(f"            return {zero};")
    else:
        lines.append("            return;")
    lines.append("        }")
    lines.append("    }")

    # 调用
    arglist = ", ".join(v for _, v in params)
    cast = render_cast(ret, params)
    if zero is not None:
        lines.append(f"    return (({cast})fn)({arglist});")
    else:
        lines.append(f"    (({cast})fn)({arglist});")

    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 GL 转发层")
    ap.add_argument("--def", dest="def_path", required=True, help="symbols.def 路径")
    ap.add_argument("--out", required=True, help="输出 .c 文件路径")
    ap.add_argument("--manifest", help="可选：输出 JSON 清单（供测试比对）")
    args = ap.parse_args()

    # 重新生成转发层
    fwd, cus, stubs = parse_def(Path(args.def_path))

    # 检查是否有返回值类型未在 ZERO_VALUES 中登记。
    # 漏登记会导致 stub 生成出 `return ;` 之类的非法代码（非 void 函数），
    # 或者转发路径的失败分支缺少 return。提前报错比编译期发现更省事。
    unknown_rets = set()
    for e in fwd + stubs:
        r = e["ret"]
        if r not in ZERO_VALUES:
            unknown_rets.add(r)
    if unknown_rets:
        print("错误: 以下返回类型未登记到 ZERO_VALUES，无法生成安全默认值:", file=sys.stderr)
        for r in sorted(unknown_rets):
            print(f"    {r}", file=sys.stderr)
        print("请在 gen_gl_forwarders.py 的 ZERO_VALUES 中补充。", file=sys.stderr)
        return 1

    out = []
    out.append("/*")
    out.append(" * generated_forwarders.c —— 由 native/tools/gen_gl_forwarders.py 自动生成")
    out.append(" *")
    out.append(" * 请勿手工编辑本文件。修改 native/symbols.def 后重新生成：")
    out.append(" *   py native/tools/gen_gl_forwarders.py --def native/symbols.def \\")
    out.append(" *       --out native/src/generated_forwarders.c")
    out.append(" *")
    out.append(" * 本文件包含三类实现：")
    out.append(f" *   - {len(fwd)} 个转发函数（GLES 有同名函数）")
    out.append(f" *   - {len(stubs)} 个安全 stub（GLES 不提供，返回零值并记降级）")
    out.append(f" *   - {len(cus)} 个定制实现在 custom.c（本文件不包含）")
    out.append(" *")
    out.append(" * 为什么需要 stub：LWJGL 在 GL.createCapabilities() 时需要一批函数，")
    out.append(" * 缺失会让它抛 NullPointerException 直接崩溃。导出为 stub 可让它拿到")
    out.append(" * 有效指针，调用时返回零值，游戏继续运行。详见 symbols.def 头部说明。")
    out.append(" *")
    out.append(" * LGPL-3.0-or-later")
    out.append(" */")
    out.append("")
    out.append('#include "gl_internal.h"')
    out.append("")
    out.append("/* ==================== 直接转发 ==================== */")
    out.append("")

    for e in fwd:
        out.append(gen_forwarder(e))
        out.append("")

    out.append("/* ==================== 安全 stub ==================== */")
    out.append("")
    out.append("/*")
    out.append(" * 这些符号在 GL 3.2 core 中存在，但 GLES 3.2 不提供。")
    out.append(" * 统一导出为安全 stub 而不是留空，原因见文件头说明。")
    out.append(" *")
    out.append(" * 每个 stub 都调用 glesmod_report_stub()，它会：")
    out.append(" *   - 首次调用时记一条降级事件（避免刷屏）")
    out.append(" *   - 把符号名加入状态文件的 stub_symbols 列表，便于诊断")
    out.append(" *   - 不做任何可能影响渲染的副作用")
    out.append(" */")
    out.append("")

    for e in stubs:
        out.append(gen_stub(e))
        out.append("")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(out), encoding="utf-8")

    if args.manifest:
        manifest = {
            "forward": [e["name"] for e in fwd],
            "custom": [e["name"] for e in cus],
            "stub": [e["name"] for e in stubs],
            "total": len(fwd) + len(cus) + len(stubs),
        }
        Path(args.manifest).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(f"转发函数 : {len(fwd)}")
    print(f"安全 stub: {len(stubs)}")
    print(f"定制实现 : {len(cus)}")
    print(f"合计     : {len(fwd) + len(stubs) + len(cus)}")
    print(f"输出     : {args.out}")
    if cus:
        print()
        print("定制实现清单（需在 custom.c 中提供）:")
        for e in cus:
            print(f"  {render_signature(e['ret'], e['name'], e['params'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
