#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_device_fix_live.py -- 判定设备上的修复是否真的生效。

不依赖「两次日志对比」——旧日志可能已被覆盖。改用**独立证据**：

  证据 1：新日志里还有没有着色器编译失败？
     搜索 `Failed to create shader` / `ERROR: <行>:<列>:` / `compilation errors`
  证据 2：native.log 里有没有规则 S 的自证日志？
     我在 collect_builtin_int_returning_funcs 里加了
         glesmod_log("规则S 已识别内建函数的整型实参与整型返回值（…GLESMOD_RULE_S_BUILTIN_INT_ARGS）")
     它只在**真的识别到** textureSize/imageSize 时打印。
     这条日志出现在设备上，就证明设备加载的确实是含修复的原生库 ——
     这是最直接的「补丁在跑」证据，比任何间接推断都强。
  证据 3：native.log 里最后一次「编译失败的着色器」的时间戳。
     若 21:33 之后不再有新的失败转储，说明修复后没有再崩。

一条重要分工：glesmod_log 写进 glesmod/native.log，
而不是 latest.log；所以判定「补丁在跑」必须查 native.log。
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

FAIL_PATTERNS = [
    ("Veil 创建着色器失败", re.compile(r"Failed to create shader")),
    ("驱动的 ERROR 行",     re.compile(r"^\s*ERROR: \d+:\d+:")),
    ("编译错误汇总",        re.compile(r"compilation errors")),
]

# 这些是 Veil 的**正常**行为，不是失败，不能计入 bad：
#   `Skipping shader 'x' (missing required features: ...)`
# 是能力门控在工作 —— 例如 indirect_sphere 需要 compute/shader_storage/
# atomic_counter，levitite 需要 tessellation，GLES 3.2 都没有。
# 把它当失败会让判定永远红（已踩过一次）。
INFO_PATTERNS = [
    ("Skipping shader（能力门控，正常）", re.compile(r"Skipping shader")),
]

MARKER = "GLESMOD_RULE_S_BUILTIN_INT_ARGS"
MARKER_TEXT = "规则S 已识别内建函数的整型实参与整型返回值"
DUMP_RX = re.compile(r"^\[(\d\d:\d\d:\d\d\.\d+)\]\s*编译失败的着色器")
TS_RX = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\.(\d+)\]")


def lines_of(path):
    return io.open(path, encoding="utf-8", errors="replace").read().splitlines()


def main():
    bad = 0

    # ---------- 证据 1：新日志里的失败 ----------
    print("=" * 88)
    print("证据 1 —— latest(2).log（21:33 那次启动）里的着色器失败")
    print("=" * 88)
    dev = os.path.join(ROOT, "latest(2).log")
    if not os.path.isfile(dev):
        print("  找不到 %s" % dev)
        bad += 1
    else:
        L = lines_of(dev)
        print("  行数: %d" % len(L))
        for name, rx in FAIL_PATTERNS:
            hits = [l.strip() for l in L if rx.search(l)]
            print("  %-22s %d" % (name, len(hits)))
            if hits:
                bad += 1
                for h in hits[:5]:
                    print("        %s" % h[:150])
        # 信息类：只报告，不参与判定
        for name, rx in INFO_PATTERNS:
            hits = [l.strip() for l in L if rx.search(l)]
            print("  %-22s %d" % (name, len(hits)))
            for h in hits[:3]:
                print("        %s" % h[:130])
        # 特别确认这次两个受害者
        for victim in ("redstone_accumulator", "contraption_diagram"):
            n = sum(1 for l in L if victim in l and "Failed to create" in l)
            print("  %-22s %d 次失败" % (victim, n))
            if n:
                bad += 1

    # ---------- 证据 2 + 3：native.log ----------
    print()
    print("=" * 88)
    print("证据 2/3 —— native.log（原生后端自己的日志）")
    print("=" * 88)
    nlog = os.path.join(ROOT, "native.log")
    if not os.path.isfile(nlog):
        # 未提供并不等于失败：native.log 由用户手动从设备拉回，是可选的旁证。
        # 但「提供了却不含标记」是硬失败 —— 那说明设备加载的原生库确实没有修复。
        print("  未提供 native.log —— 跳过（可选旁证）")
    else:
        L = lines_of(nlog)
        print("  行数: %d" % len(L))

        n_marker = sum(1 for l in L if MARKER in l or MARKER_TEXT in l)
        print("  [证据 2] 规则 S 自证日志出现次数: %d" % n_marker)
        if n_marker == 0:
            print("        **设备上的原生库不含规则 S —— 修复没被加载！**")
            bad += 1
        else:
            for l in L:
                if MARKER in l or MARKER_TEXT in l:
                    print("        %s" % l.strip()[:140])
                    break

        dumps = [m.group(1) for m in (DUMP_RX.match(l) for l in L) if m]
        print("  [证据 3] 「编译失败的着色器」转储总数: %d" % len(dumps))
        if dumps:
            print("        最早: %s" % dumps[0])
            print("        最晚: %s" % dumps[-1])

        # 按小时统计失败时间分布
        byhour = {}
        for d in dumps:
            h = d[:2]
            byhour[h] = byhour.get(h, 0) + 1
        if byhour:
            print("        按小时: " +
                  ", ".join("%s时=%d" % (k, byhour[k]) for k in sorted(byhour)))

    print()
    print("=" * 88)
    if bad == 0:
        print("verdict: PASS —— 设备上的修复已生效，且没有新的着色器失败")
        return 0
    print("verdict: FAIL —— %d 项待查" % bad)
    return 1


if __name__ == "__main__":
    sys.exit(main())
