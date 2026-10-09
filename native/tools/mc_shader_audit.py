#!/usr/bin/env python3
"""
从 Minecraft / NeoForge 的 jar 中取出全部着色器，逐个经转换器处理并审计。

【为什么必须这么做】

真机启动失败的最终表现是：

    java.lang.IllegalStateException: could not preload shader position
        at net.minecraft.client.renderer.GameRenderer.preloadShader(GameRenderer.java:428)

这行异常只说明「名为 position 的着色器编译/链接失败」，不含任何 GLSL 信息 ——
驱动给出的具体错误在 glGetShaderInfoLog 里，而 MC 把它记到了别处。
靠猜哪一行有问题效率极低。

MC 的核心着色器都是**桌面 GLSL**（写死在 jar 里，面向 GL 3.2 core）。
因此必然需要转换。本脚本把每个着色器都跑一遍转换器，
并按「GLSL ES 是否会拒绝」的可判定规则打分，把可疑的排到前面。

【审计的判定规则】

1. 是否存在 GLSL ES 不支持的关键字/类型：
     gl_FragColor / gl_FragData / gl_Vertex / gl_ModelViewMatrix ...
     attribute / varying（ES 3.x 已移除，转换器应已替换）
     texture2D / textureCube（转换器应已替换）
2. 是否存在「二元运算里整数与浮点混用」的可疑写法（ES 禁止隐式转换）：
     例如 vec2 * 2、vec4 * 0.5 之外的 count + 1.0
3. 输出里是否缺少必需的 #version / precision
4. 是否存在 ES 不支持的布局或内建：
     gl_PointSize 之外的 gl_* 兼容变量、gl_ClipDistance 等

【用法】
    py mc_shader_audit.py --jar <client.jar> [--cli <convert_cli.exe>]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

# 默认的 MC 客户端 jar 位置（FCL 的实例目录）
DEFAULT_JAR_CANDIDATES = [
    Path.home() / ".gradle/caches/modules-2/files-2.1/net.minecraft/client",
]

# GLSL ES 3.x 中不存在、必须被转换或替换的标识符
ES_UNSUPPORTED = {
    # 旧式片元输出
    "gl_FragColor": "桌面专属输出变量，ES 用 out 变量",
    "gl_FragData": "桌面专属输出数组，ES 用 out 变量",
    "gl_FragDepthEXT": "ES 用 gl_FragDepth",
    # 旧式顶点输入
    "attribute": "ES 3.x 用 in",
    "varying": "ES 3.x 用 in/out",
    # 旧式纹理函数
    "texture2D": "ES 用 texture",
    "texture2DProj": "ES 用 textureProj",
    "texture2DLod": "ES 用 textureLod",
    "textureCube": "ES 用 texture",
    "textureCubeLod": "ES 用 textureLod",
    # 固定功能管线内建（ES 完全没有）
    "gl_ModelViewMatrix": "固定功能管线，ES 无",
    "gl_ProjectionMatrix": "固定功能管线，ES 无",
    "gl_ModelViewProjectionMatrix": "固定功能管线，ES 无",
    "gl_NormalMatrix": "固定功能管线，ES 无",
    "gl_Vertex": "固定功能管线，ES 无",
    "gl_Normal": "固定功能管线，ES 无",
    "gl_Color": "固定功能管线，ES 无",
    "gl_MultiTexCoord0": "固定功能管线，ES 无",
    "gl_TexCoord": "固定功能管线，ES 无",
    "gl_FogFragCoord": "固定功能管线，ES 无",
    # 桌面专属
    "gl_ClipDistance": "桌面专属，ES 无",
    "gl_FragCoordARB": "桌面专属写法",
}

# 匹配「浮点/向量 与 整数 直接做算术」的可疑形式。
# 例如 `a * 2`、`2 * a`，其中左侧是标识符（可能是 float/vec）。
_MAYBE_INT_ARITH = re.compile(r"[A-Za-z_]\w*\s*[*+\-/]\s*\d+(?![\d.])(?![.\w])")


def find_client_jars() -> list[Path]:
    """找出可用的 MC 客户端 jar。"""
    out: list[Path] = []
    for base in DEFAULT_JAR_CANDIDATES:
        if not base.is_dir():
            continue
        for jar in base.rglob("*.jar"):
            if "sources" in jar.name:
                continue
            out.append(jar)
    return out


def strip_comments(src: str) -> str:
    """去掉注释，避免注释里的关键字造成误报。"""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def expand_moj_imports(text: str, includes: dict[str, str],
                       depth: int = 0) -> str:
    """
    展开 Minecraft 的 #moj_import 指令。

    【为什么必须展开 —— 这是审计中最大的一个盲区】
       MC 的核心着色器几乎都写着：
           #moj_import <fog.glsl>
       这是 Minecraft 自己的预处理指令。**MC 在调用 glShaderSource 之前
       就会把它展开成 include 文件的内容**，因此 native 端的转换器
       实际看到的是展开后的完整源码。

       若审计脚本只看 .vsh 原文（含未展开的 #moj_import），
       就会漏掉 include 文件里的全部内容 —— 而那些内容完全可能含有
       ES 不接受的写法。真机上 position 着色器编译失败，
       而 position.vsh 本身看起来毫无问题，正是这个盲区造成的。

    @param text     待展开的源码
    @param includes 已加载的 include 文件（名 -> 内容）
    @param depth    递归深度，防止循环 include 导致死循环
    @return 展开后的源码
    """
    if depth > 8:
        return text

    out_lines = []
    for line in text.split("\n"):
        m = re.match(r"\s*#moj_import\s*<([^>]+)>\s*$", line)
        if not m:
            out_lines.append(line)
            continue
        inc_name = m.group(1)
        body = includes.get(inc_name)
        if body is None:
            # 找不到 include：保留原样，并在审计时作为问题上报
            out_lines.append(line)
            continue
        out_lines.append(expand_moj_imports(body, includes, depth + 1))
    return "\n".join(out_lines)


def load_includes(z: zipfile.ZipFile) -> dict[str, str]:
    """
    加载 jar 内所有可作为 #moj_import 目标的内容。

    MC 的 include 位于 assets/minecraft/shaders/include/ 下，
    但引用时只写文件名（如 fog.glsl），因此以 basename 为键。
    """
    inc: dict[str, str] = {}
    for n in z.namelist():
        if "/shaders/include/" not in n:
            continue
        try:
            inc[Path(n).name] = z.read(n).decode("utf-8")
        except (UnicodeDecodeError, KeyError):
            continue
    return inc


def moj_import_targets(text: str) -> list[str]:
    """列出一个着色器里引用的所有 #moj_import 目标。"""
    return re.findall(r"#moj_import\s*<([^>]+)>", text)


def audit_one(cli: Path, name: str, text: str, stage: str) -> dict:
    """
    调用转换器处理单个着色器，返回审计结果。

    用子进程而非直接链接：这样某个着色器导致崩溃/超时不会拖垮整个审计，
    且能拿到退出码判断转换是否返回 NULL。

    输出通过**输出文件**回传，不用 stdout：PowerShell 的文本管道会把换行
    重复，导致输出看起来多一倍空行，容易被误读成转换器有 bug。
    """
    import tempfile
    import os

    with tempfile.NamedTemporaryFile("w", suffix=".glsl", delete=False,
                                     encoding="utf-8") as tf:
        tf.write(text)
        tmp_in = tf.name
    tmp_out = tmp_in + ".out"
    try:
        proc = subprocess.run(
            [str(cli), tmp_in, stage, tmp_out],
            capture_output=True, text=True, timeout=20,
        )
        converted = ""
        if proc.returncode == 0 and os.path.exists(tmp_out):
            with open(tmp_out, "rb") as f:
                converted = f.read().decode("utf-8", errors="replace")
    finally:
        for p in (tmp_in, tmp_out):
            try:
                os.unlink(p)
            except OSError:
                pass

    return {
        "name": name,
        "stage": stage,
        "converted_ok": proc.returncode == 0,
        "converted": converted,
        "stderr": proc.stderr.strip(),
        "raw": text,
    }


def problems_in(result: dict) -> list[str]:
    """对一个转换结果给出问题清单。"""
    out: list[str] = []

    if not result["converted_ok"]:
        out.append(f"转换器返回失败: {result['stderr']}")
        return out

    body = strip_comments(result["converted"])

    # 1. #version 指令
    #
    # 【必须恰好一条，且位于最前 —— 这一条是真实故障的产物】
    #   Minecraft 在编译前展开 #moj_import，把 include 文件内容原样内联，
    #   而 MC 的 include 文件（fog.glsl）自己也以 #version 150 开头。
    #   若转换器只移除第一处 #version，输出里就会残留一条位于文件中部，
    #   而 GLSL 规定 #version 只能出现在第一个非注释位置 —— 残留即编译失败。
    #   真机的 "could not preload shader position" 正是如此。
    nver = len(re.findall(r"(?m)^\s*#version", body))
    if nver == 0:
        out.append("输出缺少 #version 指令")
    elif nver > 1:
        out.append(f"输出含 {nver} 条 #version（必须恰好 1 条；"
                   f"内联 include 带来的多余 #version 会导致编译失败）")
    else:
        if not re.search(r"(?m)^\s*#version\s+3\d\d\s+es", body):
            m = re.search(r"(?m)^\s*#version[^\n]*", body)
            out.append(f"#version 非 3xx es 形式: {m.group(0).strip() if m else '?'}")
        # 位置检查：#version 之前只允许空白与注释
        first_ver = re.search(r"(?m)^\s*#version", body)
        prefix = body[:first_ver.start()]
        for ln in prefix.split("\n"):
            s = ln.strip()
            if s:
                out.append(f"#version 之前出现非空内容: {s[:60]!r}")
                break

    if result["stage"] == "fragment" and "precision" not in body:
        out.append("片元着色器缺少 precision 声明（ES 强制要求）")

    # 2. 不能残留任何 Minecraft 私有指令
    #
    # 【真实故障】驱动曾报：
    #     ERROR: 0:4: '' : GLSL compile error: malformed preprocessor directive
    #   原因就是 #moj_import 被原样送进了驱动 —— GLSL 从未支持这个指令。
    #   转换器必须自己展开它，输出里不允许再出现。
    if "moj_import" in body:
        n = len(re.findall(r"moj_import", body))
        out.append(f"残留 {n} 处 #moj_import（GLSL 不支持该指令，"
                   f"驱动会报 malformed preprocessor directive）")

    # 其它 Minecraft 私有预处理指令（若有，同样必须由转换器处理掉）
    for kw in ("#moj_",):
        for m in re.finditer(rf"(?m)^\s*{re.escape(kw)}\w*", body):
            if "moj_import" in m.group(0):
                continue
            out.append(f"残留 Minecraft 私有指令: {m.group(0).strip()}")

    # 3. 预处理器指令里的字面量必须保持整数形式
    #
    # 【真实故障】驱动曾报：
    #     ERROR: 0:4: '' : GLSL compile error: malformed preprocessor directive
    #   根因是 `#line 0 1` 里的行号 `1` 被当作浮点上下文中的整数，
    #   改写成了 `#line 0 1.0` —— 非法指令。
    #
    #   两个缺陷叠加：预处理器行保护只在指针恰好停在 '#' 上时生效
    #   （#line 前面常有换行，保护被跳过）；且判断运算符时把下一行
    #   块注释的斜杠误认为除法。
    #
    #   这里检查 #line / #define 等指令里是否出现了小数形式的参数。
    for m in re.finditer(r"(?m)^\s*#line\s+([^\n]*)$", body):
        args = m.group(1)
        if "." in args:
            out.append(f"#line 参数被浮点化（非法）: '#line {args.strip()}'")

    # 4. 整数向量与浮点的混合运算
    #
    # 【真实故障】驱动曾报：
    #     ERROR: 1:14: '/' : wrong operand types  no operation '/' exists that
    #     takes a left-hand operand of type 'in 2-component vector of int'
    #     and a right operand of type 'const float'
    #   源头是 MC 的 light.glsl：`clamp(uv / 256.0, ...)`（uv 为 ivec2）。
    #   桌面 GLSL 允许 ivec2 / float，**GLSL ES 不允许**。
    #
    #   因为核心着色器几乎都引用 light.glsl，它们会全部编译失败，
    #   reloadShaders 抛异常，渲染管线失效 —— 表现为
    #   「逻辑正常（音乐响、按钮可点）但画面静止不动」。
    #
    #   转换器应把这类运算改写为 vecN(变量) / 浮点。
    for m in re.finditer(
            r"\b(i|u)vec([234])\s+(\w+)[^;\n]*;", body):
        var = m.group(3)
        # 该变量作为 / 或 * 的左操作数，右侧接浮点字面量。
        #
        # 注意分组：必须把两个小数形式用 (?:...) 包起来，
        # 否则 `A|B` 会作用于整个模式，导致「任意浮点字面量」都算命中
        # （那样会给出一堆假报警，反而掩盖真实问题）。
        pat = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(var)}\s*[*/]\s*"
            rf"(?:\d+\.\d*|\d*\.\d+)")
        if pat.search(body):
            out.append(
                f"残留「整数向量 {var} 与浮点」混合运算"
                f"（GLSL ES 不允许，应为 vecN({var})）")

    # 2. ES 不支持的关键字
    for token, why in ES_UNSUPPORTED.items():
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", body):
            out.append(f"残留 ES 不支持的标识符 {token}（{why}）")

    # 5. 整数向量以「值」的形式进入浮点上下文
    #
    # 【真实故障】驱动曾报：
    #     ERROR: 0:34: 'assign' : cannot convert from
    #     'attribute 2-component vector of int' to
    #     'varying 2-component vector of float'
    #   出自 rendertype_* 顶点着色器：`texCoord2 = UV2;`
    #   （texCoord2 为 out vec2，UV2 为 in ivec2）。
    #   桌面 GLSL 允许隐式 ivec->vec 转换，GLSL ES 不允许，
    #   连赋值语境也拒绝。
    #
    #   转换器现已改写为 vecN(变量)。此规则用于确认改写已彻底 ——
    #   覆盖赋值、声明初始化、return 三种「以值传递」的语境。
    ivec_decls: dict[str, str] = {}
    for m in re.finditer(r"\b(i|u)vec([234])\s+(\w+)\s*(?=[,;=\[)])", body):
        ivec_decls[m.group(3)] = m.group(2)

    fvec_decls: set[str] = set()
    for m in re.finditer(r"\bvec([234])\s+(\w+)\s*(?=[,;=\[)])", body):
        fvec_decls.add(m.group(2))

    if ivec_decls:
        names = "|".join(re.escape(n) for n in sorted(ivec_decls, key=len,
                                                     reverse=True))
        # 5a. 赋值 / 声明初始化：浮点向量 = 整数向量
        #     用 (?!\s*[*/]\s*(?:\d+\.\d*|\d*\.\d+)) 排除已由规则 4 覆盖的算术情形
        for m in re.finditer(
                rf"(?<![A-Za-z0-9_])(?P<lhs>\w+)\s*=\s*(?P<rhs>{names})\s*[;,)]",
                body):
            lhs, rhs = m.group("lhs"), m.group("rhs")
            if lhs in fvec_decls:
                out.append(
                    f"残留「浮点向量 {lhs} = 整数向量 {rhs}」赋值"
                    f"（GLSL ES 不允许隐式转换，应为 vecN({rhs})）")

        # 5b. return 整数向量（函数返回类型为浮点向量时非法）
        for m in re.finditer(rf"\breturn\s+(?P<rhs>{names})\s*;", body):
            out.append(
                f"残留「return 整数向量 {m.group('rhs')}」"
                f"（返回浮点向量的函数中 GLSL ES 不允许隐式转换）")

    # 3. 可疑的整数/浮点混用（仅提示，不一定是错）
    #
    # 【为什么单独标记而不计入失败】
    #   MC 自己就大量使用整数字面量，其中多数是合法的：
    #       texelFetch(Sampler2, UV2 / 16, 0)   // 整数坐标，正确
    #       color *= 1 - something              // 由上下文的 float 决定
    #   早期版本把它计入失败计数，于是「19 个着色器有问题」的汇总
    #   掩盖了真正的错误（实际一个都没有）。
    #   现在这类只作提示，不参与退出码 —— 真正的判定交给 glslang 校验。
    hints: list[str] = []
    for m in _MAYBE_INT_ARITH.finditer(body):
        hints.append(f"疑似整浮混用（提示）: {m.group(0).strip()}")

    return out, hints


def main() -> int:
    ap = argparse.ArgumentParser(description="审计 MC 着色器经转换后的结果")
    ap.add_argument("--jar", help="MC 客户端 jar 路径；省略则自动搜索")
    ap.add_argument("--cli", help="convert_shader_cli 可执行文件路径")
    ap.add_argument("--dump", metavar="SUBSTR",
                    help="只展示名字含 SUBSTR 的着色器（含展开后的源码与转换结果），"
                         "用于全量审计看不出问题时的逐行排查")
    ap.add_argument("--verbose", action="store_true",
                    help="同时打印转换后的源码")
    ap.add_argument("--export", metavar="DIR",
                    help="把全部着色器的转换结果写出到 DIR（每个着色器一个文件），"
                         "用于离线 grep 排查审计规则未覆盖的写法")
    args = ap.parse_args()

    # 定位 CLI
    cli = None
    if args.cli:
        cli = Path(args.cli)
    else:
        here = Path(__file__).resolve().parent
        for cand in (here / ".cache" / "convert_shader_cli.exe",
                     here / ".cache" / "convert_shader_cli"):
            if cand.is_file():
                cli = cand
                break
    if cli is None or not cli.is_file():
        print("错误: 找不到 convert_shader_cli，请先用 run_shader_tests.ps1 "
              "或 gcc 编译，并用 --cli 指定路径", file=sys.stderr)
        return 1

    # 定位 jar
    jars = [Path(args.jar)] if args.jar else find_client_jars()
    jars = [j for j in jars if j.is_file()]
    if not jars:
        print("错误: 未找到 MC 客户端 jar", file=sys.stderr)
        return 1

    print(f"转换器: {cli}")
    total_files = 0
    total_bad = 0

    for jar in jars:
        print(f"\njar: {jar.name}")
        try:
            z = zipfile.ZipFile(jar)
        except zipfile.BadZipFile:
            print("  跳过（非有效 zip）")
            continue

        with z:
            includes = load_includes(z)

            # ---- dump mode: 只展示指定着色器，不做全量审计 ----
            #
            # 当全量审计「看不出问题」但真机确实编译失败时，唯一可靠的办法
            # 就是逐行比对「Minecraft 实际交给 GL 的源码」与「我们送回驱动的源码」。
            # 展开展开 #moj_import 是关键 —— 否则看不到 include 文件的内容。
            if args.dump:
                want = args.dump.lower()
                hits = [n for n in z.namelist()
                        if want in n.lower()
                        and n.endswith((".vsh", ".fsh", ".glsl"))]
                if not hits:
                    print(f"  未找到含 '{args.dump}' 的着色器")
                    continue
                for n in sorted(hits):
                    body = z.read(n).decode("utf-8", "replace")
                    stage = ("unknown" if n.endswith(".glsl")
                             else ("vertex" if n.endswith(".vsh") else "fragment"))

                    # 按真机实际情况喂入：源码里仍带着未展开的 #moj_import，
                    # 由转换器负责展开（真机证据表明驱动收到的是未展开的版本）。
                    res = audit_one(cli, n, body, stage)

                    print("\n" + "=" * 70)
                    print(f"### {n}   (stage={stage})")
                    print("=" * 70)
                    print("----- 输入（MC 交给 glShaderSource 的源码，"
                          "#moj_import 尚未展开）-----")
                    for i, line in enumerate(body.split("\n")):
                        print(f"{i:4}| {line}")
                    print()
                    print("----- 转换后（本库实际送入驱动的源码）-----")
                    if res["converted_ok"]:
                        for i, line in enumerate(res["converted"].split("\n")):
                            print(f"{i:4}| {line}")
                    else:
                        print(f"  !! 转换失败: {res['stderr']}")
                    probs, hints = problems_in(res)
                    if probs or hints:
                        print()
                        print("----- 审计发现 -----")
                        for p in probs:
                            print(f"  - {p}")
                        for h in hints:
                            print(f"  - {h}")
                continue

            print(f"  include 文件: {len(includes)} 个"
                  + (f" -> {', '.join(sorted(includes))}" if includes else ""))

            # 单独审计每个 include 文件本身（它们会被内联进着色器，
            # 自身也必须是合法 GLSL ES）
            for inc_name, inc_body in sorted(includes.items()):
                total_files += 1
                res = audit_one(cli, f"include/{inc_name}", inc_body, "unknown")
                probs, hints = problems_in(res)
                if probs:
                    total_bad += 1
                    print(f"\n  [问题] include/{inc_name}")
                    for p in probs:
                        print(f"        - {p}")
                    if args.verbose:
                        print("        --- 内容 ---")
                        for line in inc_body.split("\n")[:60]:
                            print(f"          {line}")

            names = [n for n in z.namelist()
                     if n.endswith(".vsh") or n.endswith(".fsh")]
            if not names:
                print("  未发现 .vsh/.fsh 着色器")
                continue

            print(f"  发现 {len(names)} 个着色器")
            for n in sorted(names):
                raw = z.read(n)
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("latin-1")

                stage = "vertex" if n.endswith(".vsh") else "fragment"

                # 刻意【不】在这里展开 #moj_import。
                #
                # 早期版本在审计里先展开再喂给转换器，结果掩盖了真实故障：
                # 真机上 #moj_import 是【原样】送到驱动的（驱动报的错误行号
                # 与它在输出中的行号完全吻合），转换器必须自己展开它。
                # 因此审计也要按真实情况喂入未展开的源码，
                # 并把「输出里是否残留 #moj_import」作为检查项。
                total_files += 1
                res = audit_one(cli, n, text, stage)
                probs, hints = problems_in(res)

                if args.export and res["converted_ok"]:
                    out_dir = Path(args.export)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    # 用下划线扁平化路径，避免子目录
                    flat = n.replace("/", "__")
                    (out_dir / flat).write_text(res["converted"],
                                                encoding="utf-8")

                # include 目标必须都在内嵌清单里（转换器靠名字查表内联）
                for tgt in moj_import_targets(text):
                    if tgt not in includes:
                        probs.append(f"#moj_import 目标在 jar 中不存在: {tgt}")

                if probs:
                    total_bad += 1
                    print(f"\n  [问题] {n}")
                    for p in probs:
                        print(f"        - {p}")
                    if args.verbose:
                        print("        --- 输入（未展开 #moj_import）---")
                        for line in text.split("\n")[:60]:
                            print(f"          {line}")
                        print("        --- 转换结果 ---")
                        for line in res["converted"].split("\n")[:60]:
                            print(f"          {line}")
                elif hints and args.verbose:
                    print(f"\n  [提示] {n}")
                    for h in hints:
                        print(f"        - {h}")

    print()
    print("=" * 60)
    print(f"共处理 {total_files} 个着色器，其中 {total_bad} 个存在问题")
    return 1 if total_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
