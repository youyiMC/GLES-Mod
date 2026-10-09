#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_open_source_ready.py -- 推送前的最终复检。

为什么单独写脚本而不是内联跑
============================
本终端会把内联 python 里的引号与括号吞掉（PowerShell 解析器介入），
所以凡涉及字符串比较的检查一律写成文件 —— 这是本仓库反复验证过的做法。

检查项
======
1. 仓库是否已是 git 仓库、远程是否指向预期地址
2. 待提交文件的**权威清单**来自 git 自身（git diff --cached），不是我的设想
3. 绝对不允许入库的扩展名 / 目录（第三方素材、密钥、产物）
4. 源码里不得出现设备/账号标识
5. 开源必备文件是否齐全（LICENSE / README / THIRD-PARTY-NOTICES …）
6. README 是否中英双语、英文在前、锚点可跳转
"""

import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

RULE = "=" * 88

# 绝不能入库的扩展名（gradle-wrapper.jar 是唯一例外，见下）
BAD_EXT = {".jar", ".zip", ".so", ".apk", ".dex", ".class", ".log",
           ".keystore", ".jks", ".p12", ".pfx", ".pem", ".key", ".spv",
           ".exe", ".bak", ".orig", ".rej"}
ALLOW = {"gradle/wrapper/gradle-wrapper.jar"}

BAD_DIR = {"bslsrc", "bsl3", "bsl4", "bsl5", "bsl6", "bsl7", "bsl8",
           "bsl_patched", "shader_bsl", "patched_shaders", "shader_dump",
           "veil-src", "sable-src", "sable-companion-src", "fw-src",
           "fw-upstream", ".cache", "build", "run", "__pycache__",
           "reconv", "reconv2", "reconv3", "corpus-before", "corpus-after",
           "corpus-after2", "corpus-rulesNOP"}

SECRETS = [
    ("accessToken", re.compile(r"accessToken,\s*[A-Za-z0-9._-]{20,}")),
    ("uuid",        re.compile(r"--uuid,\s*[0-9a-f]{32}")),
    ("xuid",        re.compile(r"--xuid,\s*\d{15,}")),
    ("private key", re.compile(r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY")),
]

REQUIRED = ["LICENSE", "README.md", "THIRD-PARTY-NOTICES.md",
            "TEMPLATE_LICENSE.txt", ".gitignore", ".gitattributes",
            "build.gradle", "settings.gradle", "gradle.properties",
            "开发任务书.txt"]


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def git_paths(*args):
    """返回 git 的路径列表，**不做引号转义**。

    ⚠ 踩过的坑：`git diff --cached --name-only` 默认对含非 ASCII 字节的
     路径加引号并转义（core.quotePath=true），于是 `开发任务书.txt` 会输出成
     `"\345\274\200..."`。后果有两层：
       ① 与真实文件名比对必然失败（本该“已暂存”的被判为“缺失”）；
       ② 更危险的是 **“禁止项”检查会被绕过** —— 一个带引号的路径
          匹配不上 BAD_DIR 里的任何模式。
     因此改用 `-z`（NUL 分隔）拿原始字节；NUL 分隔永远不会加引号。
    """
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True)
    raw = r.stdout or b""
    parts = raw.split(b"\0")
    out = []
    for p in parts:
        if not p:
            continue
        out.append(p.decode("utf-8", "replace"))
    return r.returncode, out, (r.stderr or b"").decode("utf-8", "replace")


def main():
    bad = 0

    # ---- 1. git 状态 ----
    print(RULE)
    print("1. 仓库状态")
    print(RULE)
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("  FAIL: 不是 git 仓库")
        return 1
    _, branch, _ = git("branch", "--show-current")
    _, remote, _ = git("remote", "get-url", "origin")
    _, name, _ = git("config", "user.name")
    _, mail, _ = git("config", "user.email")
    print("  分支   : %s" % branch.strip())
    print("  远程   : %s" % remote.strip())
    print("  提交者 : %s <%s>" % (name.strip(), mail.strip()))
    for label, v in (("branch", branch), ("remote", remote),
                     ("user.name", name), ("user.email", mail)):
        if not v.strip():
            print("  FAIL: %s 未设置" % label)
            bad += 1

    # ---- 2. 权威清单来自 git ----
    rc, files, err = git_paths("diff", "--cached", "--name-only", "-z")
    if rc != 0:
        print("  FAIL: git diff --cached 失败: %s" % err.strip())
        return 1
    print()
    print(RULE)
    print("2. 待提交文件（权威来源：git diff --cached，-z 原始路径）")
    print(RULE)
    print("  共 %d 个文件" % len(files))
    if not files:
        print("  FAIL: 暂存区为空，忘了 git add？")
        bad += 1

    # ---- 3. 禁止项 ----
    print()
    print(RULE)
    print("3. 禁止入库的内容")
    print(RULE)
    hits = []
    for f in files:
        posix = f.replace(os.sep, "/")
        if posix in ALLOW:
            continue
        if os.path.splitext(f)[1].lower() in BAD_EXT:
            hits.append(("扩展名", f))
        for part in posix.split("/")[:-1]:
            if part in BAD_DIR:
                hits.append(("目录 %s" % part, f))
                break
    if hits:
        for why, f in hits[:40]:
            print("  BAD [%s] %s" % (why, f))
        bad += len(hits)
    else:
        print("  无（gradle-wrapper.jar 为规范允许的引导文件，已显式放行）")

    # ---- 4. 敏感串 ----
    print()
    print(RULE)
    print("4. 敏感信息（直接扫描索引内容，而非工作区）")
    print(RULE)
    leaks = []
    rc, out, _ = git("grep", "--cached", "-I", "-n", "-E",
                     "accessToken, ?[A-Za-z0-9._-]{20,}|"
                     "--uuid, ?[0-9a-f]{32}|--xuid, ?[0-9]{15,}|"
                     "BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY")
    for line in out.splitlines():
        leaks.append(line.strip()[:150])
    if leaks:
        for l in leaks[:20]:
            print("  LEAK %s" % l)
        bad += len(leaks)
    else:
        print("  无")

    # ---- 5. 必备文件 ----
    print()
    print(RULE)
    print("5. 开源必备文件")
    print(RULE)
    for f in REQUIRED:
        ok = os.path.isfile(os.path.join(ROOT, f)) and \
            (f.replace(os.sep, "/") in [x.replace(os.sep, "/") for x in files])
        print("  %-26s %s" % (f, "在仓库中 ✓" if ok else "**缺失或未暂存**"))
        if not ok:
            bad += 1

    # ---- 6. README 双语 ----
    print()
    print(RULE)
    print("6. README 结构（英文在前、中文在后、锚点可跳转）")
    print(RULE)
    rp = os.path.join(ROOT, "README.md")
    if not os.path.isfile(rp):
        print("  FAIL: README.md 不存在")
        bad += 1
    else:
        t = io.open(rp, encoding="utf-8").read()
        i_en = t.find('<a name="english">')
        i_zh = t.find('<a name="中文">')
        checks = [
            ("英文锚点存在", i_en >= 0),
            ("中文锚点存在", i_zh >= 0),
            ("英文在前", 0 <= i_en < i_zh),
            ("顶部有英文标题 H1", "# GLES Mod" in t[:400]),
            ("含中文标题 H2", "## 中文" in t),
            ("含许可证段", "License" in t and "许可证" in t),
            ("含已知限制段", "Known limitations" in t and "已知限制" in t),
            ("含部署陷阱说明", "-WithPlugin" in t),
            ("UTF-8 可解码", True),
        ]
        for label, ok in checks:
            print("  %-24s %s" % (label, "✓" if ok else "**✗**"))
            if not ok:
                bad += 1

    print()
    print(RULE)
    if bad == 0:
        print("verdict: PASS —— 可以提交并推送")
        return 0
    print("verdict: FAIL —— %d 项需要处理" % bad)
    return 1


if __name__ == "__main__":
    sys.exit(main())
