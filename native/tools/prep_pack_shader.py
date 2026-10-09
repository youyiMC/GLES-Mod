#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prep_pack_shader.py -- 复现 Iris 交给转换器（进而交给驱动）的真实文本。

为什么需要它
------------
光影包里的 world0/deferred1.fsh 只有 13 行，真正的代码在
    #include "/program/deferred1.glsl"
并且 Iris 在把着色器交给驱动前会用 jcpp 做一次**完整的 C 预处理**：

  * 展开 #include（前导 '/' 表示以 shaders/ 为根的包内路径）
  * 展开 #define，求值 #ifdef / #if / #elif
  * 把所有预处理指令行从输出中**删除**

所以我们的 glShaderSource 收到的既不是 13 行桩文件，
也不是 663 行的 deferred1.glsl，而是把 settings.glsl 与 lib/*.glsl
全部内联、宏全部展开之后的**上千行文本**。
Iris 打印的错误行号，就是这份文本再经我们转换器改写后的行号。

不重建这份文本，就只能靠猜 —— 前几轮已经因此浪费了时间。

用法:
    py native\\tools\\prep_pack_shader.py world0/deferred1.fsh
    py native\\tools\\prep_pack_shader.py world0/deferred1.fsh --show 45 75
    py native\\tools\\prep_pack_shader.py world0/deferred1.fsh --conv --grep sunVec 3
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
CACHE = HERE / ".cache" / "prep"
CACHE.mkdir(parents=True, exist_ok=True)

GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
CLI = str(HERE / ".cache" / "roundtrip" / "convert_shader_cli.exe")
CLI_SRC = str(HERE / "convert_shader_cli.c")
SHADER_C = str(ROOT / "native" / "src" / "shader.c")
INCLUDE = str(ROOT / "native" / "include")


def build_cli():
    """必须每次重编译。

    教训：曾经因为复用了旧的 convert_shader_cli.exe，改完 shader.c 后
    看到「毫无变化」的输出，白白多花一轮。绝不信任旧二进制。
    """
    os.makedirs(os.path.dirname(CLI), exist_ok=True)
    r = subprocess.run(
        [GCC, "-O1", "-std=c11", "-o", CLI, CLI_SRC, SHADER_C, "-I", INCLUDE],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("!! CLI 编译失败:")
        print(r.stdout or "", r.stderr or "")
        sys.exit(1)

INCLUDE_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]+[<"]([^">]+)[">]', re.M)
DIRECTIVE_RE = re.compile(r'^[ \t]*#[ \t]*(version|extension)\b.*$', re.M)

# Iris 会向 jcpp 传入这些宏；缺了它们，光影包的 #if 分支会和真机不同。
#
# 【这是一个真实踩过的坑】
#   起初只传 MC_VERSION / MC_GL_VERSION / MC_GLSL_VERSION，结果预处理的
#   结果与真机**不是同一份代码**：真机走的分支我根本没编到，
#   于是「本地全绿、真机报错」，而且报错行号与我的输出完全对不上
#   （真机 771/939，我这边 1591，差值还不是常数）。
#
#   BSL 的 shaders.properties 里 profile.LOW 定义了一批开关，
#   必须按真机所选的 profile 逐字复现，否则测的不是同一段代码。
#
# 取自 BSL v10.1.8 shaders/shaders.properties：
#     profile.MINIMUM=!AO !LIGHT_SHAFT !SHADOW !SHADOW_COLOR !SHADOW_FILTER \
#                     shadowMapResolution=512 shadowDistance=128.0 !TAA
#     profile.LOW    =profile.MINIMUM SHADOW shadowMapResolution=1024 \
#                     shadowDistance=128.0
# 真机日志显示 "Profile: LOW"。
#
# 另外光影包自己通过 #define 声明了 IS_IRIS / VOXY_PATCH 等；
# VOXY 与 DISTANT_HORIZONS 由 Iris 依据已装模组注入
# （用户装了 Voxy 与 Distant Horizons 时才会定义）。
CPP_DEFINES_BASE = [
    "MC_VERSION=12101",
    "MC_GL_VERSION=320",
    "MC_GLSL_VERSION=320",
    # Iris
    "IS_IRIS",
    # 【不要定义 VOXY_PATCH / DH_PATCH】
    #   它们是 BSL 为 Voxy / Distant Horizons 兼容版准备的补丁开关。
    #   一旦定义，lib/color/lightColor.glsl 里的
    #       #ifndef VOXY_PATCH
    #       uniform float isDesert, isMesa, isCold, ...;
    #       #endif
    #   会被跳过，而**使用**这些 uniform 的代码仍在 -> isCold 等全部「未声明」。
    #   真机 Mod List 里没有 Voxy / Distant Horizons，所以这两个补丁宏
    #   与 VOXY / DISTANT_HORIZONS 一样，都**不应定义**。
    # profile.LOW 展开后的实际开关（未列出的开关即为关闭）
    "SHADOW",
]

# 【不要用 #define 去覆盖这些名字】
#   BSL 把它们写在 lib/settings.glsl 里，形式是**带注释选项的 const 声明**：
#       const int shadowMapResolution = 2048; //[512 1024 ...]
#       const float shadowDistance = 256.0;   //[128.0 192.0 ...]
#   Iris 的做法是**直接改写这个初始化值**（依据用户在光影设置里的选择），
#   而不是定义同名宏。我们若用 `#define shadowMapResolution 1024`，
#   会把源码里的名字整段吃掉，产出 `const int 1024 = 2048;` 这种语法错误。
#   因此改为在预处理完成后做**文本层面的数值替换**。
#
# 真机用的是 profile.LOW：
#     profile.MINIMUM=... shadowMapResolution=512 shadowDistance=128.0 ...
#     profile.LOW    =profile.MINIMUM SHADOW shadowMapResolution=1024 shadowDistance=128.0
CONST_OVERRIDES = [
    ("shadowMapResolution", "1024"),
    ("shadowDistance", "128.0"),
]

# 兼容旧名字（其它脚本可能引用）
CPP_DEFINES = CPP_DEFINES_BASE


def find_pack():
    zips = sorted(ROOT.glob("BSL*.zip"))
    if not zips:
        raise SystemExit("!! 开发目录下没有 BSL*.zip")
    return zips[-1]


def expand_includes(text, cur_dir, zf, names, depth=0):
    if depth > 32:
        return "/* include depth exceeded */\n"

    def repl(m):
        inc = m.group(1).replace("\\", "/")
        cands = []
        if inc.startswith("/"):
            cands.append("shaders/" + inc[1:])
        else:
            cands.append(cur_dir + "/" + inc)
            cands.append("shaders/" + inc)
        for c in cands:
            c = c.replace("//", "/")
            if c in names:
                sub = zf.read(c).decode("utf-8", "replace")
                return expand_includes(sub, os.path.dirname(c), zf, names,
                                       depth + 1)
        return "/* MISSING INCLUDE: %s */\n" % inc

    return INCLUDE_RE.sub(repl, text)


def cpp(text, tag):
    """用宿主 gcc 当 C 预处理器，模拟 jcpp 的宏展开与指令删除。

    【为什么把宏写进源文件而不走 -D】
      光影包自己会 `#define shadowMapResolution 2048` 之类。若同时用
      `-D shadowMapResolution=1024`，gcc 会把包内那条 #define 的**值**替换掉，
      产出 `const int 1024 = 2048;` 这种语法错误。
      改成在文件最前面插入一批 #define，包内后续的 #define 就能正常
      覆盖它们，与 Iris 的行为一致（Iris 也是把 profile 开关写入源文本）。
    """
    header = ""
    for d in CPP_DEFINES_BASE:
        if "=" in d:
            k, v = d.split("=", 1)
            header += "#define %s %s\n" % (k, v)
        else:
            header += "#define %s 1\n" % d
    src = CACHE / (tag + ".src")
    with open(src, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + text)

    cmd = [GCC, "-E", "-P", "-undef", "-nostdinc", "-w", "-x", "c"]
    cmd.append(str(src))

    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 and not r.stdout:
        print("!! 预处理失败:")
        print(r.stderr[:2000])
        sys.exit(2)
    return r.stdout


def num_lines(text):
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def show(text, a, b, title):
    lines = text.splitlines()
    print("--- %s  第 %d..%d 行 (共 %d 行) ---" % (title, a, min(b, len(lines)),
                                                  len(lines)))
    for i in range(a - 1, min(b, len(lines))):
        print("%5d| %s" % (i + 1, lines[i]))
    print()


def grep(text, pat, ctx, title):
    lines = text.splitlines()
    hits = [i for i, l in enumerate(lines) if pat in l]
    print("--- %s  含 '%s' 的行: %d 处 ---" % (title, pat, len(hits)))
    shown = set()
    for i in hits[:12]:
        for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
            if j in shown:
                continue
            shown.add(j)
            print("%s%5d| %s" % (">>" if j == i else "  ", j + 1, lines[j]))
        if len(hits) > 12:
            print("  ... 其余 %d 处省略" % (len(hits) - 12))
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    entry_rel = sys.argv[1].lstrip("/")
    argv = sys.argv[2:]

    do_conv = "--conv" in argv
    show_range = None
    greps = []
    i = 0
    while i < len(argv):
        if argv[i] == "--show" and i + 2 < len(argv) + 1:
            show_range = (int(argv[i + 1]), int(argv[i + 2]))
            i += 3
        elif argv[i] == "--grep" and i + 1 < len(argv):
            pat = argv[i + 1]
            ctx = int(argv[i + 2]) if i + 2 < len(argv) and argv[i + 2].isdigit() else 0
            greps.append((pat, ctx))
            i += 3 if (i + 2 < len(argv) and argv[i + 2].isdigit()) else 2
        else:
            i += 1

    zp = find_pack()
    print("pack:", zp.name)
    print("=" * 74)

    with zipfile.ZipFile(zp) as zf:
        names = set(zf.namelist())
        entry = "shaders/" + entry_rel
        if entry not in names:
            print("!! zip 里没有", entry)
            return 3
        raw = zf.read(entry).decode("utf-8", "replace")
        expanded = expand_includes(raw, os.path.dirname(entry), zf, names)

    print("[1] 原始桩文件          : %d 行" % num_lines(raw))
    print("[2] 展开 #include 之后  : %d 行" % num_lines(expanded))

    stripped = DIRECTIVE_RE.sub("", expanded)
    pre = cpp(stripped, entry_rel.replace("/", "_"))

    # 依据真机 profile 改写 const 初始化值（见 CONST_OVERRIDES 说明）
    for name, val in CONST_OVERRIDES:
        pre = re.sub(r'\b(const\s+\w+\s+%s\s*=\s*)[^;]+;' % re.escape(name),
                     lambda m: m.group(1) + val + ";", pre)

    print("[3] 宏展开(模拟 jcpp)后 : %d 行   <- 这才是转换器收到的文本"
          % num_lines(pre))

    pre_path = CACHE / (entry_rel.replace("/", "_") + ".pre")
    with open(pre_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(pre)
    print("    已写出:", pre_path)
    print()

    target = pre
    title = "预处理后(转换器输入)"
    if do_conv:
        build_cli()
        stage = "vertex" if entry_rel.endswith((".vsh", ".vert")) else "fragment"
        out = CACHE / (entry_rel.replace("/", "_") + ".conv")
        r = subprocess.run([CLI, str(pre_path), stage, str(out)],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if not os.path.isfile(out):
            print("!! 转换失败 rc=%d  %s" % (r.returncode, r.stderr[:500]))
            return 5
        target = open(out, encoding="utf-8", errors="replace").read()
        title = "转换器输出"
        print("[4] 转换器输出          : %d 行" % num_lines(target))
        print("    已写出:", out)
        print()

    if show_range:
        show(target, show_range[0], show_range[1], title)
    for pat, ctx in greps:
        grep(target, pat, ctx, title)

    if "--validate" in argv:
        glslc = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
                 r"\windows-x86_64\glslc.exe")
        cf = CACHE / (entry_rel.replace("/", "_") + ".conv")
        stage = "-fshader-stage=frag" if entry_rel.endswith((".fsh", ".glsl")) \
            else "-fshader-stage=vert"
        r = subprocess.run([glslc, "--target-env=opengl", stage, str(cf),
                            "-o", str(cf) + ".spv"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        errs = [l.strip() for l in (r.stderr or "").splitlines()
                if "error" in l.lower()]
        # 过滤 SPIR-V 专属要求：它要求显式 location / binding，
        # 而 OpenGL ES 从链接时推断，故与本任务无关。
        noise = ("requires location for user input/output",
                 "requires layout(binding",
                 "uniform/buffer blocks require layout(binding",
                 "requires an explicit binding",
                 "non-opaque uniform",
                 "for Vulkan",
                 "non-opaque uniforms outside a block")
        real = [e for e in errs if not any(n in e for n in noise)]
        print("=" * 74)
        print("glslang 校验 (GLSL ES 前端): %s" % cf)
        print("  总错误行 %d，其中 SPIR-V 噪声 %d，真实 GLSL 错误 %d"
              % (len(errs), len(errs) - len(real), len(real)))
        if real:
            print("  ---- 真实错误 ----")
            for e in real[:40]:
                print("   ", e[:170])
            if len(real) > 40:
                print("   ... 其余 %d 条省略" % (len(real) - 40))
        else:
            print("  结论: 无 GLSL ES 错误，该着色器可被 GLSL ES 编译器接受")
        print("=" * 74)

    return 0


if __name__ == "__main__":
    sys.exit(main())
