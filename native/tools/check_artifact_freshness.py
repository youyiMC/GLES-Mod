#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_artifact_freshness.py -- 防止「改了代码但没重建 APK」再次发生。

血泪教训（2026-10-09，21:23 那次设备测试）
=========================================
我在 16:10 重建了 native 库、真机夹具 5/5 通过、9 个门禁全绿 ——
就以为完事了。但设备上 Simulated 的两个着色器**报出与 14:19 完全相同的错误**，
仿佛修复不存在。

真相：我调用 `build-all.ps1` 时**没加 `-WithPlugin`**，所以 FCL 渲染器插件 APK
一直是昨天 10/8 13:03 的旧版。设备装的是 APK，APK 里的原生库没有今天的修复。

判定办法（本脚本的核心）：**不比对时间戳，而是直接比对标记字符串**。
时间戳只能说明「文件被写过」；只有标记能证明「补丁真的在那个二进制里」。
本仓库的 `native/tools/required_strings.txt` 就是为此维护的。

为什么单查本机 .so 不够
========================
本机 `build/native/*/libgl_gles.so` 和 APK 内的副本是**两条独立路径**，
可以一个新一个旧。必须分别检查。

用法： py -X utf8 native/tools/check_artifact_freshness.py
退出码 0 = 全部新鲜且含全部标记；1 = 有陈旧或缺标记的产物。
"""

import io
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

APK = os.path.join(ROOT, "build", "plugin", "glesmod-renderer-plugin.apk")
SOS = [os.path.join(ROOT, "build", "native", "arm64-v8a", "libgl_gles.so"),
       os.path.join(ROOT, "build", "native", "armeabi-v7a", "libgl_gles.so")]
REQ = os.path.join(HERE, "required_strings.txt")


def load_markers():
    """读取 required_strings.txt 里的**全部**标记。

    清单里既有 `GLESMOD_XXX` 这种 ASCII 标记，也有中文标记
    （例如 `存储`）。两者在 .so 里都是原文字节，所以不能只按 ASCII 判。
    依然跳过以 '#' 开头的注释行，以及纯说明性的英文句子
    （编译时常量字符串不会出现在产物里）。
    """
    marks = []
    if not os.path.isfile(REQ):
        return marks
    for line in io.open(REQ, encoding="utf-8", errors="replace"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # 注释里那些整句英文说明不会是产物里的常量；只取「标记」形态：
        #   - GLESMOD_XXX
        #   - 纯中文/中英混排的短串（常量字符串）
        if RX_MARK.match(s):
            marks.append(s)
        elif LEN(s) <= 24 and not s.endswith(".") and " " not in s:
            marks.append(s)
        elif any("\u4e00" <= ch <= "\u9fff" for ch in s) and len(s) <= 24:
            marks.append(s)
    return marks


# 只看这一类标记：形如 GLESMOD_XXX 的大写标识符
RX_MARK = re.compile(r"^GLESMOD_[A-Z0-9_]+$")
LEN = len


def check_blob(name, data, marks):
    """在二进制里按 UTF-8 与 ASCII 两种方式找标记。

    GLSLC/NDK 的工具链把源文件里的字符串字面量按 UTF-8 原样存进 .rodata，
    因此中文标记也能直接搜到；但为免某些构建选项把它转成别的编码，
    这里两种解码都试，命中任一即算存在。
    """
    hay = data.decode("utf-8", "ignore")
    hay_a = data.decode("ascii", "ignore")
    missing = [m for m in marks if m not in hay and m not in hay_a]
    print("  %-38s %s" % (name, "OK" if not missing
                          else "缺标记 %d 个" % len(missing)))
    for m in missing:
        print("        MISSING: %s" % m)
    return not missing


def main():
    marks = load_markers()
    print("required_strings.txt 里的标记数: %d" % len(marks))
    if not marks:
        print("FAIL: 读不到标记清单，无法判定")
        return 1

    bad = 0

    print()
    print("--- 本机 native 库 ---")
    for so in SOS:
        if not os.path.isfile(so):
            print("  %-38s 不存在" % os.path.relpath(so, ROOT))
            bad += 1
            continue
        with open(so, "rb") as fh:
            data = fh.read()
        if not check_blob(os.path.relpath(so, ROOT), data, marks):
            bad += 1

    print()
    print("--- FCL 渲染器插件 APK（设备实际加载的就是这份）---")
    if not os.path.isfile(APK):
        print("  APK 不存在: %s" % os.path.relpath(APK, ROOT))
        bad += 1
    else:
        with zipfile.ZipFile(APK) as z:
            sos = [e for e in z.namelist() if e.endswith(".so")]
            if not sos:
                print("  APK 里没有任何 .so —— 插件不含原生后端？")
                bad += 1
            for nm in sorted(sos):
                if not check_blob(nm, z.read(nm), marks):
                    bad += 1

    print()
    if bad == 0:
        print("verdict: PASS -- 所有产物都是新鲜的，且包含全部标记")
        return 0
    print("verdict: FAIL -- %d 处问题。" % bad)
    print("        若 APK 报陈旧，通常是忘了 `build-all.ps1 -WithPlugin`：")
    print("        不带 -WithPlugin 时脚本只重建 mod jar 与 native 库，")
    print("        APK 会保持旧版本，设备跑的仍是旧原生库。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
