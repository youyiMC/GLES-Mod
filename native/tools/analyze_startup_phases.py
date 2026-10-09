#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_startup_phases.py -- 把启动耗时按阶段拆开，用数据回答
「做着色器缓存值不值」。

为什么必须先做这个
==================
「进存档慢」是个笼统的体感。若不着色器编译只占其中的百分之几，
那为它上一个会改变 GL 语义的缓存层（no-op glCompileShader + glProgramBinary）
就是**风险远大于收益**。这里先把每一段耗时量出来，再决定要不要做。

只报数据，不做因果推断。

用法： py -X utf8 native/tools/analyze_startup_phases.py [日志...]
不带参数时自动扫描仓库根目录下的 latest*.log
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# 时间戳形如 [0910月2026 21:34:02.634]（日期在前 + 中文「月」）
TS = re.compile(r"^\[\d+月\d+\s+(\d\d):(\d\d):(\d\d)\.(\d+)\]")

# 阶段锚点：(标签, 匹配子串)。按出现顺序取**第一个**匹配。
ANCHORS = [
    ("0 启动",              "ModLauncher running"),
    ("1 GL 上下文就绪",     "GL info:"),
    ("2 模组加载完成",      "Launching target 'forgeclient'"),
    ("3 资源重载开始",      "Reloading ResourceManager"),
    ("4 着色器阶段开始",    "Loaded 0 shader redirects"),
    ("5 Veil 着色器载入完", "Loaded 27 shaders from"),
    ("6 纹理图集完成",      "Created: 1024x512x0 minecraft:textures/atlas/gui.png-atlas"),
    ("7 原生着色器编译完",  "Compiled 58 vanilla shaders in"),
    ("8 着色器上传完",      "Finished uploading vanilla shaders"),
    ("9 配方注入完",        "Created 157 recipes"),
    ("10 配方加载完",       "Loaded 2941 recipes"),
    ("11 进度加载完",       "Loaded 2644 advancements"),
    ("12 启动内置服务器",   "Starting integrated minecraft server"),
    ("13 玩家进入世界",     "加入游戏"),
    ("14 世界就绪",         "Multi-Bind unsupported"),
]

# 这些阶段之间的耗时才是「着色器相关」
SHADER_SPAN = {"4 着色器阶段开始", "5 Veil 着色器载入完", "6 纹理图集完成",
               "7 原生着色器编译完", "8 着色器上传完"}


def secs(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def extract(path):
    found = {}
    nfail = 0
    nerr = 0
    compile_ms = 0
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        m = TS.match(ln)
        if m:
            t = secs(*m.groups())
            for label, needle in ANCHORS:
                if label not in found and needle in ln:
                    found[label] = t
        if "Failed to create shader" in ln:
            nfail += 1
        if re.search(r"^\s*ERROR: \d+:\d+:", ln):
            nerr += 1
        m2 = re.search(r"Compiled \d+ vanilla shaders in ([\d.]+) ms", ln)
        if m2:
            compile_ms = float(m2.group(1))
    return found, nfail, nerr, compile_ms


def main():
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        paths = sorted(f for f in os.listdir(ROOT)
                       if f.startswith("latest") and f.endswith(".log"))
        paths = [os.path.join(ROOT, p) for p in paths]

    for p in paths:
        if not os.path.isfile(p):
            print("跳过（不存在）: %s" % p)
            continue
        name = os.path.basename(p)
        found, nfail, nerr, compile_ms = extract(p)

        print("=" * 84)
        print("%s    着色器编译失败=%d  驱动错误行=%d" % (name, nfail, nerr))
        print("=" * 84)
        if len(found) < 3:
            print("  锚点太少(%d)，无法拆解" % len(found))
            print()
            continue

        keys = [k for k, _ in ANCHORS if k in found]
        base = found[keys[0]]
        prev = None
        total_shader = 0.0
        for k in keys:
            t = found[k]
            seg = "" if prev is None else "%7.2f s" % (t - prev)
            mark = " *" if k in SHADER_SPAN else ""
            print("  %-22s %8.2f s   %s%s" % (k, t - base, seg, mark))
            if k in SHADER_SPAN and prev is not None:
                total_shader += t - prev
            prev = t

        total = found[keys[-1]] - base
        print()
        print("  启动总时长          : %7.2f s" % total)
        print("  其中着色器相关段合计: %7.2f s  (%.1f%%)"
              % (total_shader, 100.0 * total_shader / total if total else 0))
        print("  驱动自报的编译耗时  : %7.0f ms" % compile_ms)
        print()
        print("  ⇒ 一个**理想**的程序二进制缓存，最多只能省掉着色器段的一部分；")
        print("    驱动自报的编译耗时是它的上界参考值。")
        print()


if __name__ == "__main__":
    sys.exit(main())
