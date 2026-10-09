#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_pack_all.py -- 把整个光影包的每个着色器都走一遍
「展开 include -> 宏展开 -> 转换 -> glslang 校验」，汇总结果。

为什么值得做：单个 deferred1.fsh 修好不代表光影能加载。
BSL 有 179 个着色器，只要**一个**编译失败，Iris 就会
"disabling shaders!"。逐个验证是唯一能在上机前发现问题的办法。

已知的**模拟失真**（真机上不存在，需排除）：
  * `gl_FragData` —— Iris 用 glsl-transformer 的 AST 把它改写成
    `layout(location=N) out vec4 outColorN;`。我们的手工复现做不到，
    因此残留的 gl_FragData 会报 undeclared identifier。
  * 同名二次声明 —— Iris 也会改名，我们不会。

用法:
    py native\\tools\\validate_pack_all.py
    py native\\tools\\validate_pack_all.py --only deferred1
"""
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / ".cache" / "packall"
CACHE.mkdir(parents=True, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
GLSlC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")
CLI = str(CACHE / "cli.exe")
CLI_SRC = str(HERE / "convert_shader_cli.c")
SHADER_C = str(ROOT / "native" / "src" / "shader.c")
INCLUDE = str(ROOT / "native" / "include")

INCLUDE_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]+[<"]([^">]+)[">]', re.M)
DIRECTIVE_RE = re.compile(r'^[ \t]*#[ \t]*(version|extension)\b.*$', re.M)

CPP_DEFINES = ["MC_VERSION=12101", "MC_GL_VERSION=320", "MC_GLSL_VERSION=320"]

SPV_NOISE = ("requires location for user input/output",
             "requires layout(binding",
             "uniform/buffer blocks require layout(binding",
             "requires an explicit binding",
             "non-opaque uniform",
             "for Vulkan",
             "non-opaque uniforms outside a block")

# 已知的模拟失真：命中这些的行不计入失败。
#
# 【为什么必须过滤 —— 否则结果无法解读】
#   本脚本只能模拟「jcpp 预处理 + Iris 的 jcpp 阶段」，**无法**模拟
#   Iris 在 glsl-transformer 阶段用 AST 做的改写。而 BSL 的
#   gbuffers_*.vsh 大量使用固定功能变量，Iris 会把它们整体替换掉：
#       gl_MultiTexCoord0  -> vec4(UV0, 0.0, 1.0)
#       gl_TextureMatrix0  -> mat4(1.0)
#       gl_Color           -> vec4(Color, 1.0)
#       gl_FragData[N]     -> layout(location=N) out vec4 outColorN
#       gl_FragColor       -> out vec4
#   这些在真机上根本不会以原样到达驱动，因此相关错误是**我们的失真**，
#   不是转换器的缺陷。不过滤就会把大量噪声误判成真 bug。
SIM_ARTIFACTS = ("gl_FragData", "gl_MultiTexCoord", "gl_TextureMatrix",
                 "gl_Color", "gl_SecondaryColor", "gl_Normal",
                 "gl_Vertex", "gl_ModelView", "gl_ProjectionMatrix",
                 "gl_FogFragCoord", "gl_FragColor", "gl_AlphaTestRef",
                 "gl_NormalMatrix",
                 # Iris 的 VanillaTransformer 在检测到 ftransform 时会注入
                 # `vec4 ftransform() { return gl_ModelViewProjectionMatrix * gl_Vertex; }`
                 "ftransform",
                 # Iris 注入的实体/方块相关 uniform 与 attribute。
                 # 它们在真机上一定存在（由 Iris 自己声明并填充），
                 # 我们的手工复现没有，于是会连锁报出「未声明」以及
                 # 「int 赋给 float」等下游错误 —— 全是失真，不是转换器缺陷。
                 "mc_Entity", "mc_midTexCoord", "at_tangent", "at_midBlock",
                 "entityId", "blockEntityId", "iris_", "vaPosition",
                 "vaColor", "vaUV", "vaNormal",
                 # Iris 依据光影包 .properties 声明的阴影缓冲。
                 # 注意只列**全名**，绝不写 "shadow" 这样的短子串 ——
                 # 那会把 shadowCol / shadow0 等真实错误一并吞掉。
                 "shadowtex0", "shadowtex1", "shadowcolor0", "shadowcolor1",
                 )


def build_cli():
    r = subprocess.run(
        [GCC, "-O1", "-std=c11", "-o", CLI, CLI_SRC, SHADER_C,
         "-I", INCLUDE],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("!! CLI 编译失败:")
        print(r.stdout or "", r.stderr or "")
        sys.exit(1)


def expand(text, cur_dir, zf, names, depth=0):
    if depth > 32:
        return ""
    def repl(m):
        inc = m.group(1).replace("\\", "/")
        cands = (["shaders/" + inc[1:]] if inc.startswith("/")
                 else [cur_dir + "/" + inc, "shaders/" + inc])
        for c in cands:
            c = c.replace("//", "/")
            if c in names:
                return expand(zf.read(c).decode("utf-8", "replace"),
                              os.path.dirname(c), zf, names, depth + 1)
        return ""
    return INCLUDE_RE.sub(repl, text)


def cpp(text, tag):
    src = CACHE / (tag + ".src")
    src.write_text(text, encoding="utf-8", newline="\n")
    cmd = [GCC, "-E", "-P", "-undef", "-nostdinc", "-w", "-x", "c"]
    for d in CPP_DEFINES:
        cmd += ["-D", d]
    cmd.append(str(src))
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout or ""


def check(text, tag, stage):
    """返回 (real_errors, artifact_errors)。

    【必须按行号过滤，而不只是按错误文本】
    模拟失真会产生**级联错误**：`gl_MultiTexCoord0` 未声明 -> 它的类型未知
    -> 同一行上对它的 `*`、`/`、赋值全部跟着报错。这些级联错误的文本里
    并不含 `gl_`，如果只按文本过滤，它们会被误判成转换器的真实缺陷。
    因此先找出「含失真标识符的报错行」，再把该行上的所有错误一并归为失真。
    """
    src = CACHE / (tag + ".pre")
    src.write_text(text, encoding="utf-8", newline="\n")
    p = CACHE / (tag + ".conv")
    r = subprocess.run([CLI, str(src), stage, str(p)],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not p.is_file():
        return ["转换器未产出文件: %s" % (r.stderr or "")[:200]], []

    r2 = subprocess.run([GLSlC, "--target-env=opengl",
                         "-fshader-stage=" + stage, str(p),
                         "-o", str(p) + ".spv"],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace")

    lines = [ln.strip() for ln in (r2.stderr or "").splitlines()
             if "error" in ln.lower()]
    lines = [ln for ln in lines
             if not any(n in ln for n in SPV_NOISE)]
    # glslc 结尾的汇总行 `N errors generated.` 也含 "error"，但没有行号。
    # 不过滤掉它，每个着色器都会多出一条假的「真实错误」。
    lines = [ln for ln in lines if re.search(r':\d+:\s*error', ln)]

    # 第一遍：找出失真行号。
    #
    # 【★关键：必须查「转换后源码的第 N 行」，而不是只看错误文本★】
    #   原先的判据是「错误文本里是否含 gl_ 之类」，但那只对
    #       'gl_MultiTexCoord0' : undeclared identifier
    #   这种「消息里带标识符」的错误有效。
    #   而失真最常见的后果是**级联错误**：类型推不出来，于是同一行上的
    #   `*`、`/`、赋值全部跟着报错，消息长这样：
    #       world0_gbuffers_water.vsh.conv:101: error: '=' : cannot convert ...
    #   里面一个 gl_ 都没有 —— 于是被误判成转换器的真实缺陷。
    #   实测：整包 17 个「失败」文件里有 15 个都是这一类。
    #
    #   正确做法：拿行号去**读转换产物对应的那一行源码**，看它是否含
    #   失真标识符。这样级联错误会被正确归入失真。
    conv_lines = []
    try:
        conv_lines = (p.read_text(encoding="utf-8", errors="replace")
                      .splitlines())
    except OSError:
        conv_lines = []

    artifact_lines = set()
    for ln in lines:
        m = re.search(r":(\d+):\s*error", ln)
        if not m:
            continue
        n = int(m.group(1))
        # (a) 错误文本本身含失真标识符
        if any(x in ln for x in SIM_ARTIFACTS):
            artifact_lines.add(n)
            continue
        # (b) 该行**源码**含失真标识符（级联错误的主要来源）
        if 1 <= n <= len(conv_lines):
            src_line = conv_lines[n - 1]
            if any(x in src_line for x in SIM_ARTIFACTS):
                artifact_lines.add(n)

    real, art = [], []
    for ln in lines:
        m = re.search(r':(\d+):\s*error', ln)
        n = int(m.group(1)) if m else -1
        if n in artifact_lines or any(x in ln for x in SIM_ARTIFACTS):
            art.append(ln)
        else:
            real.append(ln)
    return real, art


def main():
    only = None
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        if i + 1 < len(sys.argv):
            only = sys.argv[i + 1]

    zips = sorted(ROOT.glob("BSL*.zip"))
    if not zips:
        raise SystemExit("!! 没有 BSL*.zip")
    zp = zips[-1]
    print("pack:", zp.name)
    build_cli()
    print("CLI   :", CLI)

    with zipfile.ZipFile(zp) as zf:
        names = set(zf.namelist())
        entries = sorted(n for n in names
                         if n.startswith("shaders/")
                         and n.endswith((".fsh", ".vsh")))
        if only:
            entries = [e for e in entries if only in e]

        print("待验证着色器: %d 个\n" % len(entries))

        ok = 0
        fails = []
        for e in entries:
            stage = "frag" if e.endswith(".fsh") else "vert"
            tag = e.replace("shaders/", "").replace("/", "_")
            raw = zf.read(e).decode("utf-8", "replace")
            ex = expand(raw, os.path.dirname(e), zf, names)
            pre = cpp(DIRECTIVE_RE.sub("", ex), tag)
            real, art = check(pre, tag, stage)
            if real:
                fails.append((e, real))
                print("  [FAIL] %-52s 真实错误 %d（模拟失真 %d）"
                      % (e, len(real), len(art)))
            else:
                ok += 1

    print()
    print("=" * 74)
    print("通过 %d / 共 %d" % (ok, len(entries)))
    if fails:
        print("\n失败清单:")
        for e, errs in fails:
            print("\n### %s" % e)
            for x in errs[:6]:
                print("    ", x[:165])
            if len(errs) > 6:
                print("     ... 其余 %d 条" % (len(errs) - 6))
    print("=" * 74)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
