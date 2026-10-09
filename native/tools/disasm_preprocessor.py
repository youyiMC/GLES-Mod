#!/usr/bin/env python3
"""
反汇编 Minecraft 中处理 #moj_import 的类，搞清它究竟如何变换着色器源码。

【要回答的问题 —— 这决定了转换器该怎么做】

  已确认两件事：
    1. fog.glsl 以 `#version 150` 开头（见 inspect_includes.py 输出）
    2. Minecraft 会把它内联进使用 `#moj_import <fog.glsl>` 的着色器

  若 MC 原样内联，文件中部就会出现第二条 `#version` —— 而 GLSL 规定
  `#version` 只能出现在程序最前，这在**桌面 GL 上同样是编译错误**。
  Minecraft 在桌面上能正常运行，因此 MC 必然对 include 里的 #version
  做了某种处理（剥离、或整体重写）。

  这一点直接决定我们的转换器策略：
    - 若 MC 已剥离 include 的 #version -> 我们收到的输入没有多余 #version，
      "移除全部 #version" 只是防御性措施，不是故障根因
    - 若 MC 未剥离                 -> 我们的修复方向正确，需继续排查别处

  已从常量池看到 fap.class 含：
      '#line %d %d'
      '/*#moj_import "%s"*/'
      '/*#moj_import <%s>*/'
  即 MC 会插入 #line 指令，并把原指令改写成注释形式。但具体组合方式、
  以及 include 里的 #version 是否被丢弃，只有读字节码才能确定。

用法:
    py disasm_preprocessor.py [--jar <jar>] [--method <子串>]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def find_jar() -> Path | None:
    base = Path.home() / ".gradle/caches/neoformruntime/artifacts"
    if not base.is_dir():
        return None
    cands = sorted(base.glob("minecraft_*_client.jar"),
                   key=lambda p: p.stat().st_size, reverse=True)
    return cands[0] if cands else None


def find_javap() -> str | None:
    """定位 javap。优先 JAVA_HOME，其次常见安装位置，最后 PATH。"""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        cand = Path(java_home) / "bin" / "javap.exe"
        if cand.is_file():
            return str(cand)
        cand = Path(java_home) / "bin" / "javap"
        if cand.is_file():
            return str(cand)

    for base in (r"C:\Program Files\Java", r"C:\Program Files\Eclipse Adoptium"):
        p = Path(base)
        if not p.is_dir():
            continue
        for d in sorted(p.glob("jdk*"), reverse=True):
            for exe in ("javap.exe", "javap"):
                cand = d / "bin" / exe
                if cand.is_file():
                    return str(cand)

    return shutil.which("javap")


def javap_disassemble(javap: str, class_file: Path) -> str:
    proc = subprocess.run(
        [javap, "-p", "-c", "-constants", str(class_file)],
        capture_output=True, text=True, errors="replace",
    )
    return proc.stdout


def method_excerpts(disasm: str, needles: list[str],
                    max_lines: int = 60) -> list[tuple[str, list[str]]]:
    """
    从 javap 输出中抽出「引用了指定字符串的方法」及其字节码片段。

    javap 的格式：
        方法签名以两个空格缩进
        字节码以四个及以上空格缩进
    据此切分方法块。
    """
    blocks: list[tuple[str, list[str]]] = []
    cur_sig: str | None = None
    cur_lines: list[str] = []

    def flush():
        if cur_sig is None:
            return
        joined = "\n".join(cur_lines)
        if any(n in joined for n in needles):
            blocks.append((cur_sig, cur_lines[:]))

    for line in disasm.split("\n"):
        if re.match(r"^  \S", line) and not line.startswith("    "):
            flush()
            cur_sig = line.strip()
            cur_lines = [line]
        elif cur_sig is not None:
            cur_lines.append(line)
    flush()

    # 只保留与关键字相关的行，外加少量上下文
    out: list[tuple[str, list[str]]] = []
    for sig, lines in blocks:
        keep = [ln for ln in lines if any(n in ln for n in needles)]
        if not keep:
            continue
        # 截断，避免报错刷屏
        if len(keep) > max_lines:
            keep = keep[:max_lines] + [f"        ... (共 {len(keep)} 行匹配)"]
        out.append((sig, keep))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar")
    ap.add_argument("--method", help="只看名字含该子串的方法")
    args = ap.parse_args()

    jar = Path(args.jar) if args.jar else find_jar()
    if jar is None or not jar.is_file():
        print("错误: 找不到 MC 客户端 jar", file=sys.stderr)
        return 1
    print(f"jar: {jar.name}")

    javap = find_javap()
    if javap is None:
        print("错误: 找不到 javap（请设置 JAVA_HOME）", file=sys.stderr)
        return 1
    print(f"javap: {javap}\n")

    needles = ["#version", "moj_import", "#line", "version"]

    z = zipfile.ZipFile(jar)
    targets: list[str] = []
    with z:
        for n in z.namelist():
            if not n.endswith(".class"):
                continue
            data = z.read(n)
            if b"moj_import" in data or b"#version" in data:
                targets.append(n)

        print(f"含 '#version' 或 'moj_import' 的类: {len(targets)}")
        for t in targets:
            print(f"  {t}")
        print()

        tmpdir = Path(tempfile.mkdtemp(prefix="mcdis_"))
        try:
            for t in targets:
                cls = tmpdir / Path(t).name
                cls.write_bytes(z.read(t))
                disasm = javap_disassemble(javap, cls)

                excerpts = method_excerpts(disasm, needles)
                if args.method:
                    excerpts = [(s, l) for s, l in excerpts
                                if args.method.lower() in s.lower()]
                if not excerpts:
                    continue

                print("=" * 70)
                print(f"### {t}")
                print("=" * 70)
                for sig, lines in excerpts:
                    print(f"\n  {sig}")
                    for ln in lines:
                        print(f"  {ln.rstrip()}")
                print()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
