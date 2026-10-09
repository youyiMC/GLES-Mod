#!/usr/bin/env python3
"""
从 Khronos 官方 gl.xml 提取指定 GL 版本与 profile 的命令集合。

用途（对应任务书 O-02）：
    生成本项目 native 层必须导出的 GL 符号清单，量化 MVP 工作量。

用法：
    py extract_gl_symbols.py --gl-xml .cache/gl.xml --version 3.2 --profile core
    py extract_gl_symbols.py --gl-xml .cache/gl.xml --version 3.2 --profile core \
        --json-out gl_3.2_core.json --txt-out gl_3.2_core.txt

设计说明：
    - gl.xml 中 <feature> 按版本累积，<remove profile="core"> 表示该版本起从
      core profile 中移除的命令（如固定功能管线的 glBegin/glEnd）。
    - 因此必须按版本顺序处理 require 与 remove，不能只取单个 feature。
    - 输出的符号是 C API 名称（如 glDrawElements），即本项目 native 库需要
      导出的名字。注意桌面 GL 与 GLES 的 C API 名称绝大多数相同，这也是我们
      能以符号替换方式工作的基础。
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_version(number: str) -> tuple[int, ...]:
    """把 '3.2' 解析为 (3, 2)，容错处理非数字段。"""
    parts = []
    for seg in number.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            # 形如 4.6.0 或带后缀的版本，截断即可
            break
    return tuple(parts)


def load_commands(root: ET.Element) -> dict[str, dict]:
    """建立 command 名称 -> 元信息（返回类型、参数）的索引。"""
    commands: dict[str, dict] = {}
    for cmd in root.findall("./commands/command"):
        proto = cmd.find("proto")
        if proto is None:
            continue
        name_el = proto.find("name")
        if name_el is None or not name_el.text:
            continue
        name = name_el.text.strip()

        # proto 的文本在被 name 拆开后是返回类型
        ret = "".join(proto.itertext())
        ret = ret.replace(name, "").strip()

        params = []
        for p in cmd.findall("param"):
            p_name = p.find("name")
            p_type = "".join(p.itertext())
            if p_name is not None and p_name.text:
                p_type = p_type.replace(p_name.text, "").strip()
                params.append({"name": p_name.text.strip(), "type": p_type})

        commands[name] = {"return": ret, "params": params}
    return commands


def collect_core_commands(
    root: ET.Element, max_version: tuple[int, ...], profile: str, api: str = "gl"
) -> dict[str, list[str]]:
    """
    按版本顺序累积 require / remove，返回 command -> [贡献它的 feature 名]。

    关键点：remove 只对匹配的 profile 生效。core profile 下 GL_VERSION_3_2
    会移除自 GL_VERSION_1_0 起累积的固定功能命令。

    GLES 的 feature 没有 profile 属性，此时传入 profile=None 处理。
    GLES 的 feature 名为 GL_ES_VERSION_x_y，桌面 GL 为 GL_VERSION_x_y。
    """
    prefixes = ("GL_VERSION_", "GL_ES_VERSION_")
    features = []
    for feature in root.findall("./feature"):
        if feature.get("api") != api:
            continue
        name = feature.get("name", "")
        number = feature.get("number")
        if not name.startswith(prefixes) or not number:
            continue
        ver = parse_version(number)
        if not ver or ver > max_version:
            continue
        features.append((ver, name, feature))

    features.sort(key=lambda x: x[0])

    active: dict[str, list[str]] = {}
    removed: set[str] = set()

    for _, fname, feature in features:
        for req in feature.findall("require"):
            prof = req.get("profile")
            if prof is not None and prof != profile:
                continue
            for c in req.findall("command"):
                cname = c.get("name")
                if cname:
                    active.setdefault(cname, []).append(fname)
                    removed.discard(cname)

        for rem in feature.findall("remove"):
            prof = rem.get("profile")
            if prof is not None and prof != profile:
                continue
            for c in rem.findall("command"):
                cname = c.get("name")
                if cname:
                    active.pop(cname, None)
                    removed.add(cname)

    return active


def classify(name: str) -> str:
    """
    初步分类，供人工复核。分类决定实现难度，直接影响工作量估算。

    forward   直接转发即可（GL 与 GLES 语义一致）
    map       需要枚举/格式/参数映射
    emulate   需要仿真（GLES 无对应能力）
    shader    依赖着色器转换
    """
    direct = (
        "glGen", "glDelete", "glBind", "glBufferData", "glBufferSubData",
        "glDraw", "glEnableVertexAttribArray", "glDisableVertexAttribArray",
        "glVertexAttribPointer", "glDepthFunc", "glDepthMask", "glBlendFunc",
        "glCullFace", "glFrontFace", "glViewport", "glScissor", "glClear",
        "glUseProgram", "glAttachShader", "glLinkProgram", "glCreateProgram",
        "glCreateShader", "glGetProgramiv", "glGetShaderiv", "glUniform",
    )
    mapping = (
        "glTexImage", "glTexStorage", "glGetIntegerv", "glGetString",
        "glGetFloatv", "glGetBooleanv", "glTexParameter", "glFramebuffer",
        "glRenderbuffer", "glPixelStore", "glReadPixels", "glBlitFramebuffer",
        "glDrawBuffers", "glGetError",
    )
    emulate = (
        "glPolygonMode", "glPointSize", "glLineWidth", "glLogicOp",
        "glClipPlane", "glAlphaFunc", "glColorMaterial",
    )
    shader = ("glShaderSource", "glCompileShader", "glGetShaderInfoLog", "glGetProgramInfoLog")

    if name.startswith(shader):
        return "shader"
    if name.startswith(emulate):
        return "emulate"
    if name.startswith(mapping):
        return "map"
    if name.startswith(direct):
        return "forward"
    return "forward"


def main() -> int:
    ap = argparse.ArgumentParser(description="提取 GL 版本 core profile 符号集")
    ap.add_argument("--gl-xml", required=True, help="gl.xml 路径")
    ap.add_argument("--version", default="3.2", help="目标 GL 版本，如 3.2")
    ap.add_argument("--profile", default="core", help="profile，如 core / compatibility")
    ap.add_argument("--api", default="gl", help="api，gl 或 gles2")
    ap.add_argument("--json-out", help="JSON 输出路径")
    ap.add_argument("--txt-out", help="纯符号列表输出路径（每行一个，便于 shell 比对）")
    args = ap.parse_args()

    xml_path = Path(args.gl_xml)
    if not xml_path.is_file():
        print(f"错误: 找不到 {xml_path}", file=sys.stderr)
        return 1

    root = ET.parse(xml_path).getroot()
    max_version = parse_version(args.version)

    all_commands = load_commands(root)
    profile = None if args.profile in ("", "none", "None") else args.profile
    active = collect_core_commands(root, max_version, profile, args.api)

    missing = sorted(set(active) - set(all_commands))
    if missing:
        print(f"警告: {len(missing)} 个命令在 <commands> 中无定义", file=sys.stderr)

    rows = []
    for name in sorted(active):
        meta = all_commands.get(name, {})
        rows.append(
            {
                "name": name,
                "class": classify(name),
                "ret": meta.get("return", ""),
                "param_count": len(meta.get("params", [])),
                "features": active[name],
            }
        )

    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1

    payload = {
        "source": "Khronos OpenGL-Registry gl.xml",
        "api": args.api,
        "gl_version": args.version,
        "profile": args.profile,
        "total": len(rows),
        "by_class": by_class,
        "commands": rows,
    }

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if args.txt_out:
        Path(args.txt_out).write_text(
            "\n".join(r["name"] for r in rows) + "\n", encoding="utf-8"
        )

    print(f"api={args.api}  GL {args.version} / {args.profile} profile")
    print(f"命令总数: {len(rows)}")
    for k in sorted(by_class):
        pct = by_class[k] / len(rows) * 100 if rows else 0
        print(f"  {k:9s} {by_class[k]:4d}  ({pct:5.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
