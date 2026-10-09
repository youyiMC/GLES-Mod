#!/usr/bin/env python3
"""
hotpath_cost.py -- 量化热路径转发函数的实际指令开销。

为什么需要它
------------------------------------------------------------------
本项目的 native 后端在**每一次 GL 调用**上都要执行几段固定代码：

    glesmod_lazy_init();                     <- 跨编译单元函数调用
    GLESMOD_TRACE("glXxx");                  <- 全局变量读 + 条件分支
    真实 GLES 调用

原版 MC 每帧有 10^4 ~ 10^5 次 GL 调用。因此这些固定代码的开销
**乘以 10 万**就是每帧的净损失。

问题在于："开销可忽略"这句话在源码注释里出现过多次，但从没有人
**量过**。本脚本用 llvm-objdump 反汇编真实产物，数出指令条数 ——
这是唯一不依赖主观判断的判据。

判据
------------------------------------------------------------------
对每个被测函数，统计：
  - 函数体总指令数
  - 真正调用 GLES 之前的「序言」指令数（即固定开销）
  - 是否包含对 glesmod_lazy_init / glesmod_trace_call 的调用指令

只看**序言**，因为那才是我们能省的；尾部的函数指针间接调用
（`blr x8`）是转发必须付出的代价，无法避免。

无命令行参数（task runner 会剥离引号），路径与目标函数硬编码。

LGPL-3.0-or-later
"""

import os
import re
import subprocess
import sys

# 说明：默认只测 arm64-v8a。
#
# 原因：稳态路径推断基于 AArch64 的反汇编格式，对 ARM32 产物会失效
# （表现为「稳态 ≈ 总指令数」）。两个 ABI 的**源码完全相同**，
# 只是编译器后端不同，因此测 arm64 即可代表优化是否生效。
# 若确实要测 ARM32，把下面那条路径也加进来，但只应使用
# 「lazy_init 是否为『无』」这一个判据，忽略「稳态」列。
SO_PATHS = [
    os.path.join("build", "native", "arm64-v8a", "libgl_gles.so"),
]

OBJDUMP_CANDIDATES = [
    r"C:\Android\Sdk\ndk\27.2.12479018\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-objdump.exe",
]

# 被测符号：按「每帧调用频率」从高到低挑选。
# 这些是 MC 渲染循环里最常见的非绘制类调用（见 docs/o-02-symbol-inventory.md）。
TARGETS = [
    "glBindTexture",          # 每帧上千次
    "glUniform1i",            # uniform 上传，极高频
    "glUniformMatrix4fv",     # 矩阵上传，高频
    "glVertexAttribPointer",  # 顶点布局，高频
    "glDrawElements",         # 定制实现（含探针钩子），绘制调用
    "glBindBuffer",           # 缓冲切换，高频
    "glEnable",               # 状态切换，高频
    "glActiveTexture",        # 纹理单元切换，高频
]


def find_objdump():
    for cand in OBJDUMP_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return None


def disassemble(objdump, so_path, symbol):
    """返回该符号的指令行列表（不含符号头与空行）。"""
    out = subprocess.run(
        [objdump, "--disassemble-symbols=" + symbol, "--no-show-raw-insn", so_path],
        capture_output=True, text=True, errors="replace",
    )
    if out.returncode != 0:
        return None

    lines = []
    started = False
    for line in out.stdout.splitlines():
        # 符号头形如：  0000000000012345 <glBindTexture>:
        if re.match(r"^[0-9a-f]+ <" + re.escape(symbol) + r">:$", line.strip()):
            started = True
            continue
        if not started:
            continue
        # 下一条符号头（形如 0000... <name>:）表示本函数结束
        if re.match(r"^[0-9a-f]+ <.+>:$", line.strip()):
            break
        s = line.strip()
        if not s:
            continue
        # 只保留带助记符的行： "  地址:  助记符 操作数"
        if re.match(r"^[0-9a-f]+:", s):
            lines.append(s)
    return lines


def mnemonic_of(insn_line):
    m = re.match(r"^[0-9a-f]+:\s+(\S+)", insn_line)
    return m.group(1) if m else ""


def addr_of(insn_line):
    m = re.match(r"^([0-9a-f]+):", insn_line)
    return int(m.group(1), 16) if m else None


def branch_target(insn_line):
    """
    取出分支指令的目标地址。llvm-objdump 的格式形如：
        cbz  w8, 0x2f14c <glBindTexture+0x80>
        cbnz x2, 0x2f124 <glBindTexture+0x58>
        b    0x2f0f8 <glBindTexture+0x2c>
        br    x2                       <- 间接，无目标
    返回 int 或 None。
    """
    m = re.search(r",\s*(0x[0-9a-f]+)\s*<", insn_line)
    if m:
        return int(m.group(1), 16)
    m = re.search(r"^\s*[0-9a-f]+:\s+b\s+(0x[0-9a-f]+)", insn_line)
    if m:
        return int(m.group(1), 16)
    return None


COND_BRANCHES = {
    "cbz", "cbnz", "b.eq", "b.ne", "b.lt", "b.le", "b.gt", "b.ge",
    "b.hi", "b.hs", "b.lo", "b.ls", "tbz", "tbnz", "cbgt", "cble",
}
UNCOND_BRANCHES = {"b", "br"}


def steady_state_length(insns):
    """
    计算**稳态路径**的指令数 —— 也就是产品在 99.999% 时间里真正执行的条数。

    为什么需要它：优化之后，转发函数里出现了两条路径
      - 稳态：初始化已完成、函数指针已缓存 -> 只做两次判断后直接跳转
      - 慢路径：首次调用 / 需要解析函数指针 / 找不到符号
    只看「总指令数」会把慢路径也算进去，得出「优化后反而更多」的错误结论
    （glBindTexture 总指令数从 35 变成 44，但那 44 条里有 30 余条永远不会在
     稳态下执行）。

    判定规则（简单、可复核）：
      从函数入口开始顺序走，遇到条件分支时**取不会跳进慢路径的那个方向**。
      识别慢路径的方式：目标地址相对当前位置**向前很远**（超过全函数的 40%）
      的分支，说明它跳过了一大块代码，那块就是慢路径。

    这样得到的就是稳态实际执行的指令序列长度。
    """
    if not insns:
        return 0

    addrs = [addr_of(i) for i in insns]
    base = addrs[0]
    total_bytes = (addrs[-1] - base) if addrs[-1] else 0

    # 建立地址 -> 索引 的映射
    addr_to_idx = {}
    for idx, a in enumerate(addrs):
        if a is not None:
            addr_to_idx[a] = idx

    # 慢路径区块：由「向前很远」的条件分支标记出来
    slow_ranges = []
    for idx, ins in enumerate(insns):
        mn = mnemonic_of(ins)
        if mn in COND_BRANCHES:
            tgt = branch_target(ins)
            if tgt is not None and idx in addr_to_idx and tgt in addr_to_idx:
                tgt_idx = addr_to_idx[tgt]
                span = tgt_idx - idx
                # 跳过全函数 40% 以上 = 慢路径
                if total_bytes > 0 and span > len(insns) * 0.4:
                    slow_ranges.append((idx + 1, tgt_idx - 1))

    def in_slow(idx):
        return any(a <= idx <= b for a, b in slow_ranges)

    count = 0
    idx = 0
    while idx < len(insns):
        if in_slow(idx):
            # 跳到慢路径的末尾之后
            end = max(b for a, b in slow_ranges if a <= idx <= b)
            idx = end + 1
            continue
        ins = insns[idx]
        count += 1
        mn = mnemonic_of(ins)

        if mn in UNCOND_BRANCHES:
            break

        if mn in COND_BRANCHES:
            tgt = branch_target(ins)
            if tgt is not None and tgt in addr_to_idx:
                tgt_idx = addr_to_idx[tgt]
                # 若目标在慢路径之后的收尾区（向前跳、且在慢路径之后），
                # 稳态下这个分支**会**跳 —— 跟着它走
                if tgt_idx > idx and not any(a <= tgt_idx <= b
                                             for a, b in slow_ranges) \
                        and tgt_idx - idx < len(insns) * 0.3:
                    idx = tgt_idx
                    continue
        idx += 1

    return count


def analyze(objdump, so_path, symbol):
    insns = disassemble(objdump, so_path, symbol)
    if insns is None:
        return {"symbol": symbol, "error": "objdump failed"}
    if not insns:
        return {"symbol": symbol, "error": "symbol not found in this .so"}

    total = len(insns)

    lazy_pos = None
    trace_pos = None
    first_indirect = None

    for idx, ins in enumerate(insns):
        mn = mnemonic_of(ins)
        if mn in ("bl", "b") and "glesmod_lazy_init" in ins:
            if lazy_pos is None:
                lazy_pos = idx + 1
        if mn in ("bl", "b") and "glesmod_trace_call" in ins:
            if trace_pos is None:
                trace_pos = idx + 1
        if mn in ("blr", "br") and first_indirect is None:
            first_indirect = idx + 1

    # 注意：lazy_pos / trace_pos 只表示「函数体里**存在**这样的调用」，
    # 不代表它在稳态路径上。优化之后正确的形态是：这些调用出现在慢路径
    # （通常落在函数尾部，因为编译器会把 unlikely 分支甩到后面）。
    # 因此结论部分不再用「是否存在」判定，而用「是否在稳态指令范围内」。
    return {
        "symbol": symbol,
        "total": total,
        "steady": steady_state_length(insns),
        "lazy_pos": lazy_pos,
        "trace_pos": trace_pos,
        "first_indirect": first_indirect,
        "insns": insns,
    }


def print_report(results):
    """打印一个 ABI 的对照表。"""
    print("%-26s %8s %8s %18s" % ("符号", "总指令", "稳态", "lazy_init 位置"))
    print("-" * 78)
    for r in results:
        if "error" in r:
            print("%-26s  %s" % (r["symbol"], r["error"]))
            continue
        # 关键判据：lazy_init 是否落在**稳态指令范围内**。
        # 落在范围内 = 每次调用都要执行 = 未优化。
        # 落在范围外（函数尾部）= 只属于慢路径 = 已优化。
        lp = r["lazy_pos"]
        if lp is None:
            lazy_note = "无"
        elif lp <= r["steady"]:
            lazy_note = "第 %d 条 ★未优化★" % lp
        else:
            lazy_note = "第 %d 条（慢路径）" % lp
        print("%-26s %8d %8d %18s" % (
            r["symbol"], r["total"], r["steady"], lazy_note))
    print()
    print("  说明：'稳态' = 初始化完成、函数指针已缓存后实际执行的指令数，")
    print("        即产品 99.999% 时间里走的路径。标注「慢路径」表示该调用")
    print("        只在首次/异常时执行，不构成稳态开销（期望形态）。")
    print()
    print("  基线（优化前实测）：glBindTexture 稳态 29 条（含跨编译单元 PLT 调用）；")
    print("                    glDrawElements 534 条、栈帧 496B（探针内联）。")


def print_details(results):
    """打印关键函数的前若干条指令，供人工核对稳态路径。

    只打印**前 46 条**：那正是稳态路径所在的区域
    （初始化检查 + 探针开关判断 + 函数指针检查）。
    glDrawElements 现在共 65 条，其余是只在首次/异常时执行的慢路径。
    """
    for sym in ("glDrawElements", "glBindTexture"):
        detail = next((r for r in results
                       if r.get("symbol") == sym and "error" not in r), None)
        if not detail:
            continue
        head = detail["insns"][:46]
        print("=" * 78)
        print("明细：%s 的前 %d 条指令（稳态路径所在区域）" % (sym, len(head)))
        if len(detail["insns"]) > len(head):
            print("      （该函数共 %d 条，其余为探针/慢路径代码）"
                  % len(detail["insns"]))
        print("=" * 78)
        for i, ins in enumerate(head, 1):
            print("  %3d  %s" % (i, ins))
        print()

        out_path = os.path.join("native", "tools", ".cache",
                                "disasm_%s.txt" % sym)
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                for i, ins in enumerate(detail["insns"], 1):
                    f.write("%4d  %s\n" % (i, ins))
            print("  完整反汇编已写入: %s" % out_path)
            print()
        except OSError:
            pass


def main():
    objdump = find_objdump()
    if objdump is None:
        print("FAIL: 找不到 llvm-objdump")
        return 1

    found = [p for p in SO_PATHS if os.path.isfile(p)]
    if not found:
        print("FAIL: 找不到产物 .so（先构建）")
        return 1

    print("=" * 78)
    print("热路径指令开销量化")
    print("=" * 78)
    print("objdump : %s" % objdump)
    print()

    all_results = {}
    for so_path in found:
        print("-" * 78)
        print("产物    : %s" % so_path)
        print("-" * 78)
        results = [analyze(objdump, so_path, s) for s in TARGETS]
        all_results[so_path] = results
        print_report(results)
        print()

    # 明细只针对第一个 ABI（两者结构相同，避免输出翻倍）
    first_path = found[0]
    print_details(all_results[first_path])

    print("=" * 78)
    print("结论")
    print("=" * 78)
    for so_path, results in all_results.items():
        priced = [r for r in results if "error" not in r]
        if not priced:
            continue
        avg = sum(r["steady"] for r in priced) / len(priced)
        unopt = [r for r in priced
                 if r["lazy_pos"] is not None and r["lazy_pos"] <= r["steady"]]
        print("  %s" % so_path)
        print("      平均稳态指令数         : %.1f" % avg)
        print("      稳态里仍走 lazy_init 的: %d / %d"
              % (len(unopt), len(priced)))
        if unopt:
            for r in unopt:
                print("          %s（lazy_init 在第 %d 条，稳态 %d 条）"
                      % (r["symbol"], r["lazy_pos"], r["steady"]))
    print()
    print("  基线（优化前，2026-09-29 实测 arm64-v8a）：")
    print("       glBindTexture  稳态 29 条，序言含跨编译单元 PLT 调用")
    print("       glDrawElements 534 条，栈帧 496B + 栈保护金丝雀（探针内联）")
    print("  目标：稳态里不应出现 lazy_init；含大块分支的函数应保持小栈帧。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
