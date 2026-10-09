#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_doc_claims.py -- 交叉校对：文档里写的数字必须与代码一致。

为什么需要
==========
文档里最容易出错、也最容易误导人的，就是**具体数字**：
符号数量、文件行数、着色器数量、阈值。一旦代码改了而文档没改，
读者就拿到了错误信息，而且不会有人发现。

本脚本把文档中的关键断言与真实源码/产物逐条核对。
不检查"文风"，只检查"事实"。

用法： py -X utf8 native/tools/verify_doc_claims.py
"""

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

RULE = "=" * 86


def read(p):
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8", errors="replace").read()


def count_symbols():
    t = read(os.path.join(ROOT, "native", "symbols.def"))
    if t is None:
        return None
    counts = {"F": 0, "S": 0, "C": 0}
    for line in t.splitlines():
        m = re.match(r"^([FSC])\s", line)
        if m:
            counts[m.group(1)] += 1
    counts["total"] = sum(counts.values())
    return counts


def file_lines(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8", errors="replace").read().count("\n")


def main():
    bad = 0
    docs = [
        os.path.join(ROOT, "docs", "DEVELOPER-GUIDE.en.md"),
        os.path.join(ROOT, "docs", "DEVELOPER-GUIDE.md"),
        os.path.join(ROOT, "docs", "PLAYER-GUIDE.md"),
        os.path.join(ROOT, "README.md"),
    ]

    print(RULE)
    print("文档事实校对")
    print(RULE)

    for d in docs:
        if not os.path.isfile(d):
            print("FAIL: 缺少 %s" % os.path.relpath(d, ROOT))
            bad += 1
    if bad:
        return 1

    sy = count_symbols()
    print()
    print("--- symbols.def 实际统计 ---")
    if sy is None:
        print("  FAIL: 读不到 symbols.def")
        return 1
    for k in ("total", "F", "C", "S"):
        print("  %-6s %d" % (k, sy[k]))

    shader_lines = file_lines(os.path.join("native", "src", "shader.c"))
    print("  shader.c 行数: %s" % shader_lines)

    # ---- 断言表：(描述, 在文档中查找的断言, 校验函数) ----
    checks = []

    def has(doc, needle):
        return needle in doc

    # 符号数量：**精确匹配申明式措辞**，不能用裸数字。
    #
    # ⚠ 踩过的坑：最初用 `"20" in doc` 判定，会把 `2024`、`2007`、
    #   章节号 `20`、以及任何含 20 的数字全部命中，于是文档改对了
    #   检查器仍然报错。检查「事实」必须匹配「表达事实的那句话」，
    #   而不是匹配一个数字 —— 后者既不精确也容易反向误导。
    CLAIMS = {
        "forwarded": (r"(\d+)\s*(?:exported\s+)?forward", sy["F"]),
        "custom":    (r"(\d+)\s*custom\s+implementation", sy["C"]),
        "stub":      (r"(\d+)\s*safe\s+stub", sy["S"]),
        "total":     (r"(\d+)\s*exported\s+GL\s+symbols", sy["total"]),
        # 中文表述
        "forwarded_zh": (r"(\d+)\s*个转发", sy["F"]),
        "custom_zh":    (r"(\d+)\s*个定制", sy["C"]),
        "stub_zh":      (r"(\d+)\s*个安全桩", sy["S"]),
        "total_zh":     (r"导出\s*(\d+)\s*个", sy["total"]),
    }
    for d in docs:
        t = read(d)
        name = os.path.basename(d)
        for key, (rx, expected) in CLAIMS.items():
            for m in re.finditer(rx, t, re.I):
                got = int(m.group(1))
                if got == expected:
                    continue
                # 只在「像符号数量」的量级上报错，避免把普通数字当声明
                if got < 10 or got > 2000:
                    continue
                checks.append(("%s: %s 声称 %d" % (name, key, got), False,
                               "实际 %d" % expected))

    # shader.c 行数：文档写 "~9 000 lines" / "约 9 000 行"
    if shader_lines:
        for d in docs[:2]:
            t = read(d)
            name = os.path.basename(d)
            m = re.search(r"~?9\s?000", t)
            if m:
                ok = abs(shader_lines - 9000) <= 1500
                checks.append(("%s 中 shader.c 约 9000 行" % name, ok,
                               "实际 %d 行" % shader_lines))

    # 顶层目录名不应出现已废弃的文件名
    STALE = ["entry_gl11.c", "entry_gl20.c", "entry_gl30.c", "caps.c",
             "state.c", "shader_conv.c", "check_symbols.sh"]
    for d in docs[:2]:
        t = read(d)
        name = os.path.basename(d)
        for s in STALE:
            # 允许出现在"已知过时"章节里 —— 那是在说明它过时
            idx = t.find(s)
            if idx < 0:
                continue
            # 检查它是否位于 14 节 / Known divergences 之后
            tail = t.find("Known divergences")
            if tail < 0:
                tail = t.find("已知的文档与代码不一致")
            if tail >= 0 and idx > tail:
                continue          # 出现在"过时说明"里，正确
            checks.append(("%s 误用废弃文件名 %s" % (name, s), False,
                           "该文件不存在"))

    # 真实存在的源文件被正确提及
    REAL = ["core.c", "custom.c", "enum.c", "generated_forwarders.c",
            "probe.c", "shader.c"]
    for r in REAL:
        if not os.path.isfile(os.path.join(ROOT, "native", "src", r)):
            checks.append(("%s 实际存在" % r, False, "但文件不存在"))
            continue
        for d in docs[:2]:
            t = read(d)
            if r not in t:
                checks.append(("%s 提及 %s" % (os.path.basename(d), r), False,
                               "文档未提及真实源文件"))

    # FCL 插件应为 v1，不能声称 v2 为当前实现
    manifest = read(os.path.join(ROOT, "fcl-plugin", "AndroidManifest.xml"))
    if manifest:
        if 'android:name="fclPlugin"' not in manifest:
            checks.append(("清单含 v1 fclPlugin 标记", False, "未找到"))
        else:
            checks.append(("清单含 v1 fclPlugin 标记", True, ""))
        for field in ("renderer", "des", "boatEnv", "pojavEnv", "minMCVer",
                      "maxMCVer"):
            ok = ('android:name="%s"' % field) in manifest
            checks.append(("清单含必需字段 %s" % field, ok, ""))
        ok = "LIBGL_ES=3" in manifest
        checks.append(("清单注入 LIBGL_ES=3", ok, ""))
        ok = "POJAV_RENDERER=opengles3" in manifest
        checks.append(("清单注入 POJAV_RENDERER=opengles3", ok, ""))

    # ABI 版本一致性：头文件 与 Java 侧
    hdr = read(os.path.join(ROOT, "native", "include", "gles_backend.h"))
    jstat = read(os.path.join(ROOT, "src", "main", "java", "com",
                              "youyimc", "glesmod", "backend",
                              "GlesBackendStatus.java"))
    if hdr and jstat:
        mh = re.search(r"#define\s+GLESMOD_ABI_VERSION\s+(\d+)", hdr)
        mj = re.search(r"EXPECTED_ABI_VERSION\s*=\s*(\d+)", jstat)
        if mh and mj:
            ok = mh.group(1) == mj.group(1)
            checks.append(("ABI 版本一致（native=%s java=%s）"
                           % (mh.group(1), mj.group(1)), ok, ""))

    # 状态文件路径一致性
    if hdr and jstat:
        ok = ('"glesmod/status.json"' in jstat) and \
             ('"glesmod/status.json"' in hdr)
        checks.append(("status.json 路径两侧一致", ok, ""))

    # 降级原因码：native 与 Java 应一一对应
    jdr = read(os.path.join(ROOT, "src", "main", "java", "com", "youyimc",
                            "glesmod", "degrade", "DegradeReason.java"))
    if hdr and jdr:
        nc = set(re.findall(r"GLESMOD_DEGRADE_[A-Z_]+\s*=\s*(0x[0-9A-Fa-f]+)",
                            hdr))
        jc = set(re.findall(r"\(0x([0-9A-Fa-f]{4})", jdr))
        nc_norm = {int(x, 16) for x in nc}
        jc_norm = {int(x, 16) for x in jc}
        only_n = sorted(nc_norm - jc_norm)
        only_j = sorted(jc_norm - nc_norm)
        ok = not only_n and not only_j
        checks.append(("降级原因码两侧一一对应", ok,
                       ("仅 native: %s 仅 java: %s"
                        % ([hex(x) for x in only_n], [hex(x) for x in only_j]))
                       if not ok else "共 %d 个" % len(nc_norm)))

    # 玩家文档：不该出现代码术语
    pg = read(os.path.join(ROOT, "docs", "PLAYER-GUIDE.md"))
    if pg:
        jargon = ["glShaderSource", "GLSL", "JNI", "ABI", "mixin",
                  "compiler", "struct"]
        found = [j for j in jargon if j.lower() in pg.lower()]
        checks.append(("玩家文档未使用代码术语", not found,
                       ("出现: %s" % found) if found else ""))

    print()
    print(RULE)
    print("断言核对")
    print(RULE)
    for name, ok, detail in checks:
        print("  %-52s %s%s" % (name, "OK" if ok else "**不一致**",
                                ("   " + detail) if detail else ""))
        if not ok:
            bad += 1

    print()
    print(RULE)
    if bad == 0:
        print("verdict: PASS —— 文档中的关键事实与代码一致")
        return 0
    print("verdict: FAIL —— %d 处不一致" % bad)
    return 1


if __name__ == "__main__":
    sys.exit(main())
