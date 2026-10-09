#!/usr/bin/env python3
"""
verify_exported_symbols.py -- 校验构建产物中的 GL 符号是否真的导出。

为什么需要这一步（真实教训）
------------------------------------------------------------------
`ninja: no work to do` 这句话**不能**作为「产物是最新的」的证据。
在本次改动中，build-all.ps1 的输出先后出现过两种互相矛盾的信号：

  1. 首次运行：显示 `[2/7] Building C object .../custom.c.o`（确实编译了）
  2. 随后运行：显示 `ninja: no work to do`（没编译）

而我在两次运行之间**又改过一次 custom.c**（修嵌套注释警告）。
此时无法从构建输出判断产物里到底有没有新代码 —— 文件时间戳虽然后于源码，
但那是构建系统内部行为，不是**符号层面**的证据。

因此改为直接查 .so 的动态符号表：这是唯一不依赖构建系统自述的判据。

为什么不需要命令行参数
------------------------------------------------------------------
本项目通过 VS Code 的 task runner 执行脚本，而该 shell **会剥离引号**，
导致带引号的参数被拆坏（已多次踩到）。因此本脚本：
  - 不接受任何命令行参数
  - 自行按固定相对路径定位产物
  - 校验目标（REQUIRED_CUSTOM）硬编码在文件内

如需校验其它符号，直接改 REQUIRED_CUSTOM 常量。

退出码：0 = 全部通过；1 = 有缺失或导出总数异常。

LGPL-3.0-or-later
"""

import os
import re
import subprocess
import sys

# 相对工作区根目录的产物路径（本脚本从工作区根运行）
ARTIFACTS = [
    os.path.join("build", "native", "arm64-v8a", "libgl_gles.so"),
    os.path.join("build", "native", "armeabi-v7a", "libgl_gles.so"),
]

# NDK 自带的 llvm-nm。写死路径，避免依赖 PATH。
NM_CANDIDATES = [
    r"C:\Android\Sdk\ndk\27.2.12479018\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-nm.exe",
]

# 必须存在的定制实现符号。
#
# glBufferStorage 是最新加入的一个：它原本是安全 stub（什么都不做），
# 但 Embeddium 的 MappedStagingBuffer 依赖它**真实分配存储**，
# 否则后续 glMapBufferRange 会失败并让调用方抛异常崩溃。
# 见 docs/p2-05-embeddium-assessment.md 与 docs/p2-04-degrade-routing.md。
#
# 如果这个符号在产物里**不存在**（或仍走 stub 路径而未导出实现），
# 说明构建产物是陈旧的 —— 这正是本脚本要抓的情况。
REQUIRED_CUSTOM = [
    "glGetString",
    "glGetStringi",
    "glGetIntegerv",
    "glCheckFramebufferStatus",
    "glBufferStorage",
    "glMapBufferRange",
    "glMultiDrawElements",
    "glMultiDrawArrays",
    "glMultiDrawElementsBaseVertex",
    "glTexParameterf",
    "glTexParameteri",
    "glClearDepth",
    "glGetError",
    "glGetTexImage",
    "glDrawPixels",
    "glLogicOp",
    "glPolygonMode",
    "glMapBuffer",
    "glShaderSource",
    "glTexImage2D",
    "glTexImage3D",
    "glTexStorage2D",
    "glTexStorage3D",
    "glDrawElements",
    "glGetShaderInfoLog",
    "glGetProgramInfoLog",
    "glGetShaderiv",
]

# 预期导出的函数符号总数。849 个符号减去数据符号，函数约 849。
# 这里只做**下界**校验（>=），因为编译器可能因优化调整细节。
MIN_EXPORTED_FUNCS = 840


def find_nm():
    for cand in NM_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    # 回退：从 PATH 找
    for name in ("llvm-nm.exe", "llvm-nm"):
        for p in os.environ.get("PATH", "").split(os.pathsep):
            cand = os.path.join(p, name)
            if os.path.isfile(cand):
                return cand
    return None


def read_dynamic_symbols(nm, so_path):
    """
    返回 (func_names:set, total_func_count:int)。
    llvm-nm --dynamic --defined-only 输出形如：
        0000000000012345 T glBufferStorage
    'T' = 导出的文本（代码）符号。'_' 前缀在 ELF 上不存在，无需处理。
    """
    out = subprocess.run(
        [nm, "--dynamic", "--defined-only", so_path],
        capture_output=True, text=True, errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(
            "llvm-nm failed on %s: %s" % (so_path, out.stderr.strip()[:400])
        )

    funcs = set()
    total = 0
    for line in out.stdout.splitlines():
        m = re.match(r"^[0-9a-fA-F]+\s+([TtWw])\s+(\S+)$", line.strip())
        if not m:
            continue
        kind, name = m.group(1), m.group(2)
        if kind in ("T", "W"):          # 全局导出 / 弱导出
            funcs.add(name)
            total += 1
    return funcs, total


def main():
    nm = find_nm()
    if nm is None:
        print("FAIL: 找不到 llvm-nm，无法校验导出符号")
        return 1

    print("llvm-nm : %s" % nm)
    print()

    overall_ok = True

    for so in ARTIFACTS:
        print("=" * 72)
        print("%s" % so)
        print("=" * 72)

        if not os.path.isfile(so):
            print("  FAIL: 产物不存在")
            overall_ok = False
            print()
            continue

        size_kb = os.path.getsize(so) / 1024.0
        print("  大小: %.1f KB" % size_kb)

        try:
            funcs, total = read_dynamic_symbols(nm, so)
        except RuntimeError as e:
            print("  FAIL: %s" % e)
            overall_ok = False
            print()
            continue

        print("  导出函数符号: %d" % total)

        if total < MIN_EXPORTED_FUNCS:
            print("  FAIL: 导出数量低于下界 %d —— 符号表可能被截断" % MIN_EXPORTED_FUNCS)
            overall_ok = False

        missing = [s for s in REQUIRED_CUSTOM if s not in funcs]
        if missing:
            print("  FAIL: 缺失定制实现符号 %d 个:" % len(missing))
            for s in missing:
                print("        - %s" % s)
            print()
            print("  >>> 这通常意味着构建产物是陈旧的。"
                  "请清理 native/build 后重新构建。")
            overall_ok = False
        else:
            print("  定制实现符号: 全部 %d 个已导出" % len(REQUIRED_CUSTOM))

        print()

    print("=" * 72)
    if overall_ok:
        print("结论: 通过 —— 所有定制实现符号均已导出到产物中。")
        return 0
    print("结论: 失败 —— 见上方 FAIL 行。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
