#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prepublish_audit.py -- 开源前的发布前审计。

为什么必须先审计「实际会被提交的文件」，而不是「我打算提交的文件」
================================================================
本仓库的开发过程产生了大量第三方素材：
  - Sable 的着色器（PolyForm Shield，非 FOSS，无再分发权）
  - BSL 光影包（无再分发权）
  - Sodium 的着色器（Polyform Shield）
  - Simulated / Create 的着色器源码
  - 从 Minecraft / NeoForge jar 提取的代码（含 Mojang 代码）
  - 设备日志（含玩家 UUID、token 占位、绝对路径）
  - 签名密钥、构建产物
.gitignore 是白名单式的（默认 `*` 全忽略），但**放行段可能过宽**
（例如 `!src/**`、`!native/**`），把不该入库的一起带进去。
历史一旦写入就永久留存，所以这里用**实证**代替肉眼读规则。

做法：在临时目录里 git init + 复制本仓库的 .gitignore + 按真实路径建骨架，
然后用 git status 看**实际会被纳入的文件**。

用法： py -X utf8 native/tools/prepublish_audit.py
退出码 0 = 未发现阻断项；1 = 有必须人工处理的问题。
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# 必须被忽略的路径特征（正则）。命中即视为泄露风险。
#
# 例外：gradle/wrapper/gradle-wrapper.jar 是 Gradle Wrapper 的引导文件，
# 按 Gradle 官方规范**应当提交**（否则首次克隆无法构建）。
# 它只是一个下载器，不含本项目的任何代码，也不含第三方受版权内容。
BLOCK_EXT = (
    ".jar", ".zip", ".so", ".dex", ".apk", ".class", ".dll", ".dylib",
    ".log", ".keystore", ".jks", ".p12", ".pfx", ".pem", ".key",
    ".spv", ".conv", ".bak", ".orig", ".rej", ".exe",
)
ALLOWLIST = (
    "gradle/wrapper/gradle-wrapper.jar",   # 官方规范要求提交
)
ALLOW_EXT = (
    ".c", ".h", ".java", ".gradle", ".properties", ".md", ".txt", ".json",
    ".glsl", ".frag", ".vert", ".vsh", ".fsh", ".comp", ".ps1", ".py",
    ".def", ".toml", ".xml", ".yml", ".yaml", ".cfg", ".gitignore",
    ".gitattributes", "",
)

BLOCK_DIR_NAMES = {
    "bslsrc", "bsl3", "bsl4", "bsl5", "bsl6", "bsl7", "bsl8", "bsl_patched",
    "shader_bsl", "patched_shaders", "shader_dump", "exported", "exported4",
    "exported5", "exported6", "exported7", "veil-src", "sable-src",
    "sable-companion-src", "fw-src", "fw-upstream", "corpus-before",
    "corpus-after", "corpus-after2", "corpus-rulesNOP", "reconv", "reconv2",
    "reconv3", "build", "run", ".cache", ".gradle", "__pycache__", "dirtest",
    "danger3", "confirm", "bisect", "bisect3", "shrink", "prep",
}

# 源码里绝不能出现的敏感串
SECRET_RX = [
    ("疑似真实 accessToken", re.compile(r"accessToken,\s*[A-Za-z0-9._-]{20,}")),
    ("疑似设备 UUID", re.compile(r"--uuid,\s*[0-9a-f]{32}")),
    ("疑似 xuid", re.compile(r"--xuid,\s*\d{15,}")),
]


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def collect_paths():
    """列出工作区里的全部文件（相对路径）。跳过 .git。"""
    names = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        if rel == ".":
            rel = ""
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            names.append(os.path.join(rel, fn) if rel else fn)
    return names


def check_with_git(paths):
    """用临时 git 仓库判定每个路径是否会被忽略。"""
    tmp = tempfile.mkdtemp(prefix="prepublish-")
    try:
        shutil.copyfile(os.path.join(ROOT, ".gitignore"),
                        os.path.join(tmp, ".gitignore"))
        r = sh(["git", "init", "-q"], tmp)
        if r.returncode != 0:
            return None, "git init 失败: %s" % r.stderr

        # 建出全部路径（只建空文件，不复制内容）
        for p in paths:
            full = os.path.join(tmp, p)
            try:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                if not os.path.exists(full):
                    with open(full, "w") as fh:
                        fh.write("")
            except OSError:
                pass

        # 一次性问 git：哪些文件会被纳入
        r = sh(["git", "add", "--dry-run", "--all", "."], tmp)
        tracked = []
        for line in (r.stdout or "").splitlines():
            m = re.match(r"^add '(.+)'$", line.strip())
            if m:
                tracked.append(m.group(1).replace("/", os.sep))
        return tracked, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 90)
    print("发布前审计 —— 工作区 %s" % ROOT)
    print("=" * 90)

    # 工作区本身是否已是 git 仓库
    is_repo = os.path.isdir(os.path.join(ROOT, ".git"))
    print("工作区是 git 仓库: %s" % is_repo)
    print()

    paths = collect_paths()
    print("扫描到文件总数: %d" % len(paths))

    tracked, err = check_with_git(paths)
    if tracked is None:
        print("FAIL: %s" % err)
        return 1

    print("git 实际会纳入: %d 个文件" % len(tracked))
    print()

    # ---- 分类统计 ----
    by_dir = {}
    for p in tracked:
        top = p.split(os.sep)[0] if os.sep in p else "(根)"
        by_dir[top] = by_dir.get(top, 0) + 1
    print("--- 按顶层目录分布 ---")
    for k in sorted(by_dir, key=lambda x: -by_dir[x])[:30]:
        print("  %-34s %d" % (k, by_dir[k]))
    print()

    # ---- 阻断项 ----
    blockers = []
    for p in tracked:
        posix = p.replace(os.sep, "/")
        if posix in ALLOWLIST:
            continue
        parts = p.split(os.sep)
        ext = os.path.splitext(p)[1].lower()
        if ext in BLOCK_EXT:
            blockers.append(("扩展名 %s 不应入库" % ext, p))
        for d in parts[:-1]:
            if d in BLOCK_DIR_NAMES:
                blockers.append(("目录 %s 是第三方/产物" % d, p))
                break

    print("=" * 90)
    print("阻断项（必须修 .gitignore）—— %d 个" % len(blockers))
    print("=" * 90)
    seen_dirs = {}
    for why, p in blockers:
        seen_dirs.setdefault(why, []).append(p)
    for why in sorted(seen_dirs):
        ex = seen_dirs[why]
        print("  [%s] 共 %d 个" % (why, len(ex)))
        for e in ex[:4]:
            print("        %s" % e)
        if len(ex) > 4:
            print("        ... 另外 %d 个" % (len(ex) - 4))
    if not blockers:
        print("  (无)")

    # ---- 敏感串扫描（只查会被纳入的文本文件）----
    print()
    print("=" * 90)
    print("敏感串扫描")
    print("=" * 90)
    leaks = []
    for p in tracked:
        ext = os.path.splitext(p)[1].lower()
        if ext not in (".java", ".md", ".txt", ".c", ".h", ".properties",
                       ".gradle", ".json", ".xml", ".ps1", ".py", ".yml",
                       ".yaml", ".toml", ".def", ".glsl", ".frag", ".vert",
                       ".vsh", ".fsh", ""):
            continue
        full = os.path.join(ROOT, p)
        if not os.path.isfile(full):
            continue
        try:
            txt = io.open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for name, rx in SECRET_RX:
            for m in rx.finditer(txt):
                leaks.append((name, p, m.group(0)[:60]))
    if leaks:
        for name, p, s in leaks[:30]:
            print("  [%s] %s" % (name, p))
            print("        %s" % s)
    else:
        print("  (未发现)")

    print()
    print("=" * 90)
    ok = not blockers and not leaks
    print("verdict: %s" % ("PASS —— 可以继续准备开源" if ok else "FAIL —— 必须先处理上述问题"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
