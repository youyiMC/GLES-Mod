#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_gitignore.py -- 实证第三方素材确实会被 .gitignore 挡住。

背景（重要，踩过的坑）
====================
开发工作区**本身不是 Git 仓库**（没有 .git 目录），所以直接在原地跑
`git check-ignore` 只会得到 `fatal: not a git repository`（rc=128）。
把 rc!=0 当成"未被忽略"会让整个检查全量误报 —— 这个坑踩过一次。

正确做法：在一个**临时目录**里 `git init`，把本仓库的 .gitignore 原样复制
进去，再按真实路径建出目录/文件骨架，然后用 `git check-ignore` 实证。
这样验证的是**规则语义本身**（合规问题正在于此），且不触碰工作区。

白名单式 .gitignore 的风险
==========================
本仓库默认 `*` 忽略一切，再逐条 `!xxx` 放行。新素材默认安全；但任何人往
"显式放行"段里加一条过宽的规则（例如 `!native/**` 却忘了补排除），就可能
把第三方内容带进历史。历史一旦写入就永久保留，所以必须机器校验。

用法
====
    py -X utf8 native/tools/check_gitignore.py
退出码 0 = PASS，1 = 违规。
"""

import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (相对路径, "d"/"f", 为什么必须被忽略)
MUST_IGNORE = [
    ("sable-src", "d", "Sable 着色器副本 (PolyForm Shield, 无再分发权)"),
    ("sable-src/sable_pinwheel_shaders_include_fancy_sublevel_vertex.glsl", "f",
     "Sable 自有着色器 (PolyForm Shield)"),
    ("sable-companion-src", "d", "Sable Companion 源码副本"),
    ("veil-src", "d", "Veil 源码副本"),
    ("sablebridge-2.2.jar", "f", "第三方模组 jar (MIT, 但不由我们分发)"),
    ("native/tools/.cache/fw_dumps/04_raw.vert", "f",
     "真机着色器 dump (含 Mojang / 第三方 GLSL)"),
    ("shader_dump/foo.vert", "f", "从 MC jar 提取的着色器"),
    ("bsl6", "d", "BSL 光影包副本"),
    ("native/tools/fixtures/sodium_chunk_0.8.13.vert", "f",
     "Sodium 着色器逐字副本 (Polyform Shield)"),
    ("greenscreen.log", "f", "运行日志"),
    ("native/build/arm64-v8a/libgl_gles.so", "f", "构建产物"),
    ("build/libs/glesmod-1.0.0.jar", "f", "构建产物"),
]

# 必须能入库，否则源码/文档会静默丢失
MUST_TRACK = [
    ("native/src/shader.c", "f"),
    ("native/tools/run_all_gates.py", "f"),
    ("native/symbols.def", "f"),
    ("src/main/java/com/youyimc/glesmod/GLESMod.java", "f"),
    ("src/main/resources/assets/glesmod/lang/en_us.json", "f"),
    ("build.gradle", "f"),
    (".gitignore", "f"),
    ("THIRD-PARTY-NOTICES.md", "f"),
    ("开发任务书.txt", "f"),
]


def build_skeleton(root, entries):
    """按真实路径建出目录/文件骨架。

    ⚠ 己经踩过的坑：MUST_TRACK 里包含 `.gitignore`，早期版本先复制规则
      再建骨架，于是骨架把 `.gitignore` 写成了 `x`，临时仓库里一条规则都
      没有 ⇒ 所有路径都报“未忽略”，全量误报。
      现在两层防护：① 不覆盖已存在文件 ② 调用方最后才写入规则。
    """
    for entry in entries:
        path, kind = entry[0], entry[1]
        full = os.path.join(root, path.replace("/", os.sep))
        if kind == "d":
            os.makedirs(full, exist_ok=True)
            continue
        if os.path.exists(full):
            continue          # 不覆盖（.gitignore 等已就位）
        d = os.path.dirname(full)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write("x\n")


def check(root, path):
    """返回 (是否被忽略, 命中的规则)。

    ⚠ 不能用返回码判断（踩过的坑）：
      这个 git 版本的 `check-ignore -v` 只要路径命中**任何**规则就返回 0，
      连否定规则（`!native/**`）也算命中。于是“未被忽略”的源码也会 rc=0，
      靠 rc 判断会让检查全量误报。

    正确做法：解析 `-v` 打印出来的规则。格式为
        <源文件>:<行号>:<模式>\t<路径>
    模式以 `!` 开头 ⇒ 否定规则 ⇒ **未被忽略**。
    无输出 ⇒ 无规则命中 ⇒ 未被忽略（因为默认规则 `*` 总在，实际不会发生）。
    """
    r = subprocess.run(["git", "check-ignore", "-v", "--", path],
                       cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode == 128:
        raise RuntimeError("git check-ignore 无法运行: %s" % r.stderr.strip())
    out = (r.stdout or "").strip()
    if not out:
        return False, "(无规则命中)"
    first = out.splitlines()[0]
    # <file>:<line>:<pattern>\t<path>
    head = first.partition("\t")[0]
    parts = head.split(":", 2)
    where, pattern = (parts[0], parts[2]) if len(parts) >= 3 else ("?", head)
    if len(parts) >= 2:
        where = "%s:%s" % (parts[0], parts[1])
    return (not pattern.startswith("!")), "%s  %s" % (where, pattern)


def main():
    src_ignore = os.path.join(REPO, ".gitignore")
    if not os.path.isfile(src_ignore):
        print("FAIL: 找不到 %s" % src_ignore)
        return 1

    tmp = tempfile.mkdtemp(prefix="gitignore-probe-")
    try:
        print("工作区是 Git 仓库吗 : %s" % os.path.isdir(os.path.join(REPO, ".git")))
        print("规则来源            : %s" % src_ignore)
        print("临时实证仓库        : %s" % tmp)
        print()

        init = subprocess.run(["git", "init", "-q"], cwd=tmp,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if init.returncode != 0:
            print("FAIL: git init 失败: %s" % init.stderr.strip())
            return 1

        # 先建骨架，再写规则 —— 顺序不能反（见 build_skeleton 注释）
        build_skeleton(tmp, MUST_IGNORE)
        build_skeleton(tmp, MUST_TRACK)
        shutil.copyfile(src_ignore, os.path.join(tmp, ".gitignore"))

        bad = []

        # ---- 对照组：验证解析逻辑本身 ----
        # 期望行为：没有显式放行的新文件被默认规则 `*` 拦住。
        # 如果这里判成“未被忽略”，说明默认拒绝失效（白名单被破坏）。
        ctl = "control_unlisted_file.xyz"
        with open(os.path.join(tmp, ctl), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        ctl_ign, ctl_rule = check(tmp, ctl)
        print("--- 对照组（新文件应被默认规则 `*` 拦住）---")
        print("  %s %s   [%s]" % ("ok  " if ctl_ign else "BAD!", ctl, ctl_rule))
        if not ctl_ign:
            print("  解析逻辑异常：未列出的新文件竟然未被忽略，默认拒绝已失效")
            return 1
        # 反向对照：显式放行的源码必须不被判为已忽略（验证 `!` 前缀解析）
        ctl2 = "native/src/shader.c"
        ctl2_ign, ctl2_rule = check(tmp, ctl2)
        print("  %s %s   [%s]" % ("ok  " if not ctl2_ign else "BAD!", ctl2,
                                  ctl2_rule))
        if ctl2_ign:
            print("  解析逻辑异常：命中否定规则 `!` 的路径被判为已忽略")
            return 1
        print()

        print("--- 必须被 IGNORE ---")
        for path, _kind, why in MUST_IGNORE:
            ign, rule = check(tmp, path)
            if ign:
                print("  IGNORED  %s" % path)
                print("           规则: %s" % rule)
            else:
                print("  TRACKED! %s" % path)
                print("           风险: %s" % why)
                bad.append(path)

        print()
        print("--- 必须 TRACKED（不能被误挡）---")
        for path, _kind in MUST_TRACK:
            ign, rule = check(tmp, path)
            if ign:
                print("  IGNORED! %s   <-- 被排除了！规则: %s" % (path, rule))
                bad.append(path)
            else:
                print("  ok       %s" % path)

        print()
        if not bad:
            print("verdict: PASS -- 所有合规红线成立")
            return 0
        print("verdict: FAIL -- %d 处违规" % len(bad))
        for p in bad:
            print("   %s" % p)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
