#!/usr/bin/env python3
"""
从 LWJGL 的 org.lwjgl.opengl 类中提取所有 native 方法名。

用途：
    确定「必须导出」的 GL 符号的权威清单。

为什么需要它（一次真实的翻车经历）：
    最初只导出 Minecraft 直接调用的 89 个符号 -> 真机崩溃：
        NullPointerException: A required function is missing: glGetStringi
            at org.lwjgl.opengl.GL.createCapabilities(GL.java:514)
    改用「GL core profile 全集」后仍然要反复试错，因为：

      * LWJGL 需要的是它在 Java 层声明的所有 native 方法，
        这个集合与「某个 GL 版本的全集」并不严格相等；
      * Minecraft、NeoForge、第三方模组各自还会调用额外的符号。

    本脚本直接从 LWJGL 的 class 文件读取 native 方法声明，
    这才是「LWJGL 会去 dlsym 的名字」的权威来源。

原理：
    LWJGL 的 GL 绑定类中，每个 GL 函数都是形如
        public static native void glDrawElements(int mode, ...);
    的方法。javac 会在 class 文件的 method_info 里设置
    ACC_NATIVE (0x0100) 标志位，且不含 Code 属性。
    因此只需解析方法表，筛出带 ACC_NATIVE 的方法即可。

用法：
    py extract_lwjgl_natives.py --jar <lwjgl-opengl.jar> --out-dir .
    py extract_lwjgl_natives.py --jar <lwjgl.jar> --out-dir . --show-gaps
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

UTF8, INTEGER, FLOAT, LONG, DOUBLE = 1, 3, 4, 5, 6
CLASS, STRING = 7, 8
FIELDREF, METHODREF, IFACEMETHODREF, NAMEANDTYPE = 9, 10, 11, 12
METHODHANDLE, METHODTYPE = 15, 16
DYNAMIC, INVOKEDYNAMIC, MODULE, PACKAGE = 17, 18, 19, 20

ACC_NATIVE = 0x0100
ACC_STATIC = 0x0008

# 只关心这些类：LWJGL 的 GL 绑定按版本分文件。
# 注意 GL11C/GL20C 等带 C 后缀的是 core profile 变体，同样在 createCapabilities
# 时被解析，必须一并收集。
GL_CLASS_RE = None  # 在 main 中编译


class ClassFile:
    """最小可用的 class 解析器：只需方法表与常量池。"""

    def __init__(self, data: bytes):
        self.data = data
        self.cp: list = []
        self.native_methods: list[str] = []
        self._parse_cp()
        self._parse_methods()

    def _parse_cp(self) -> None:
        data = self.data
        count = struct.unpack_from(">H", data, 8)[0]
        self.cp = [None] * count
        off = 10
        i = 1
        while i < count:
            tag = data[off]
            off += 1
            if tag == UTF8:
                ln = struct.unpack_from(">H", data, off)[0]
                off += 2
                self.cp[i] = (UTF8, data[off : off + ln].decode("utf-8", "replace"))
                off += ln
            elif tag == INTEGER:
                self.cp[i] = (INTEGER, struct.unpack_from(">i", data, off)[0])
                off += 4
            elif tag == FLOAT:
                self.cp[i] = (FLOAT, struct.unpack_from(">f", data, off)[0])
                off += 4
            elif tag == LONG:
                self.cp[i] = (LONG, struct.unpack_from(">q", data, off)[0])
                off += 8
                i += 1
            elif tag == DOUBLE:
                self.cp[i] = (DOUBLE, struct.unpack_from(">d", data, off)[0])
                off += 8
                i += 1
            elif tag == CLASS:
                self.cp[i] = (CLASS, struct.unpack_from(">H", data, off)[0])
                off += 2
            elif tag == STRING:
                self.cp[i] = (STRING, struct.unpack_from(">H", data, off)[0])
                off += 2
            elif tag in (FIELDREF, METHODREF, IFACEMETHODREF):
                ci, nti = struct.unpack_from(">HH", data, off)
                off += 4
                self.cp[i] = (tag, ci, nti)
            elif tag == NAMEANDTYPE:
                ni, di = struct.unpack_from(">HH", data, off)
                off += 4
                self.cp[i] = (NAMEANDTYPE, ni, di)
            elif tag == METHODHANDLE:
                off += 3
            elif tag == METHODTYPE:
                self.cp[i] = (METHODTYPE, struct.unpack_from(">H", data, off)[0])
                off += 2
            elif tag in (DYNAMIC, INVOKEDYNAMIC):
                off += 4
            elif tag in (MODULE, PACKAGE):
                self.cp[i] = (tag, struct.unpack_from(">H", data, off)[0])
                off += 2
            else:
                raise ValueError(f"cp tag {tag}")
            i += 1
        self.off_after_cp = off

    def utf8(self, idx: int) -> str | None:
        e = self.cp[idx] if 0 < idx < len(self.cp) else None
        return e[1] if e and e[0] == UTF8 else None

    def _skip_attributes(self, off: int) -> int:
        n = struct.unpack_from(">H", self.data, off)[0]
        off += 2
        for _ in range(n):
            ln = struct.unpack_from(">I", self.data, off + 2)[0]
            off += 6 + ln
        return off

    def _parse_methods(self) -> None:
        off = self.off_after_cp
        off += 6  # access_flags, this_class, super_class
        ifc = struct.unpack_from(">H", self.data, off)[0]
        off += 2 + ifc * 2

        # 字段
        fields = struct.unpack_from(">H", self.data, off)[0]
        off += 2
        for _ in range(fields):
            off += 6
            off = self._skip_attributes(off)

        # 方法
        methods = struct.unpack_from(">H", self.data, off)[0]
        off += 2
        for _ in range(methods):
            access = struct.unpack_from(">H", self.data, off)[0]
            name_idx = struct.unpack_from(">H", self.data, off + 2)[0]
            off += 6
            off = self._skip_attributes(off)
            if access & ACC_NATIVE:
                nm = self.utf8(name_idx)
                if nm:
                    self.native_methods.append(nm)


def main() -> int:
    import re

    ap = argparse.ArgumentParser(description="提取 LWJGL 声明的 GL native 方法")
    ap.add_argument("--jar", required=True, help="lwjgl-opengl.jar 或 lwjgl.jar")
    ap.add_argument("--out", help="输出符号清单（每行一个，供比对）")
    ap.add_argument("--dedup-report", action="store_true",
                    help="按 GL 类分组打印，便于人工核对")
    args = ap.parse_args()

    jar = Path(args.jar)
    if not jar.is_file():
        print(f"错误: 找不到 {jar}", file=sys.stderr)
        return 1

    # LWJGL 的 GL 绑定类名：GL11、GL12、...、GL46，以及 core 变体 GL11C、GL20C 等，
    # 另有 GL 与 GLUtil 工具类。这里只取以 gl 开头的静态 native 方法。
    cls_re = re.compile(r"^org/lwjgl/opengl/(GL\d+C?|GL|GLUtil)\.class$")

    by_class: dict[str, set[str]] = {}
    with zipfile.ZipFile(jar) as zf:
        names = zf.namelist()
        if not names:
            print("错误: jar 为空", file=sys.stderr)
            return 1
        for name in names:
            m = cls_re.match(name)
            if not m:
                continue
            cls = m.group(1)
            try:
                cf = ClassFile(zf.read(name))
            except Exception as e:
                print(f"警告: 解析 {name} 失败: {e}", file=sys.stderr)
                continue
            gl_syms = {n for n in cf.native_methods if n.startswith("gl")}
            # 顺带收集 egl*（部分绑定在同一 jar 内）
            gl_syms |= {n for n in cf.native_methods if n.startswith("egl")}
            if gl_syms:
                by_class.setdefault(cls, set()).update(gl_syms)

    if not by_class:
        print("错误: 未在 jar 中找到任何 GL native 方法。"
              "请确认传入的是 lwjgl-opengl（或含其内容的 lwjgl）jar。",
              file=sys.stderr)
        return 1

    all_syms: set[str] = set()
    for s in by_class.values():
        all_syms |= s

    if args.dedup_report:
        print("按绑定类分组：")
        for cls in sorted(by_class):
            print(f"  {cls:8s} {len(by_class[cls]):4d} 个 native 方法")
        print()

    print(f"LWJGL 声明的 GL native 方法总数: {len(all_syms)}")

    if args.out:
        out = Path(args.out)
        out.write_text("\n".join(sorted(all_syms)) + "\n", encoding="utf-8")
        print(f"已写入: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
