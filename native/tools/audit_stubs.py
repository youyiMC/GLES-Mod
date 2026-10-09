#!/usr/bin/env python3
"""
audit_stubs.py -- 审计所有安全 stub，找出「调用方可能依赖其副作用」的危险项。

背景（为什么需要这个工具）
------------------------------------------------------------------
P2-05 的 Embeddium 评估中发现了 `glBufferStorage` 的一类缺陷：

    glBufferStorage(...)   -> 静默 stub：不分配存储，返回 void，无错误
    glMapBufferRange(...)  -> 因缓冲区无存储而失败，返回 NULL
    调用方                 -> 抛异常崩溃

失败发生在**离根因很远的地方**，且以「与存储完全无关」的形式出现。
由此确立的原则：

    静默 stub 只适用于「调用方不会依赖其返回值/副作用」的函数。
    若函数的契约包含产生某种资源（分配存储、创建对象、返回句柄），
    做成静默 stub 就等于用一个谎言替换一次失败。

`glBufferStorage` 已修复，但**其余 484 个 stub 尚未逐一审计**（记为 R-12）。
本脚本做这个审计。

分类逻辑
------------------------------------------------------------------
对每个 `S` 符号，按「名字 + 签名」判定其危险等级：

  DANGER  —— 契约是「产生一个调用方随后要使用的资源」。
             stub 会让调用方拿到无效资源，失败延迟暴露。
             例：glBufferStorage / glCreateBuffers / glTextureStorage2D

  CAUTION —— 返回值会被调用方当作有效数据使用（如查询类）。
             stub 返回 0/NULL 可能被误读为「真实值就是 0」。
             例：glGetTextureLevelParameteriv / glGetNamedBufferParameteriv

  SAFE    —— 纯状态设置、或调用方不依赖结果。
             例：glEnable / glBlendBarrier / glTextureBarrier

无命令行参数（task runner 会剥离引号），自行按固定相对路径定位输入。

LGPL-3.0-or-later
"""

import os
import re
import sys

SYMBOLS_DEF = os.path.join("native", "symbols.def")

# ----------------------------------------------------------------------
# 分类规则
# ----------------------------------------------------------------------

# DANGER：契约是「产生资源」。这些函数一旦被 stub，
# 调用方会拿到无效资源（0 / NULL / 空存储），并在后续某个无关调用处失败。
DANGER_PATTERNS = [
    # 缓冲存储分配（glBufferStorage 的同类）
    r"^glBufferStorage$",
    r"^glNamedBufferStorage",
    r"^glNamedBufferData",
    r"^glBufferData$",              # 若被 stub 则同上
    r"^glTextureBuffer",
    r"^glNamedBufferDataEXT",
    # DSA 创建函数：返回句柄，stub 返回 0 = 无效句柄
    r"^glCreateBuffers$",
    r"^glCreateTextures$",
    r"^glCreateFramebuffers$",
    r"^glCreateRenderbuffers$",
    r"^glCreateVertexArrays$",
    r"^glCreatePrograms$",
    r"^glCreateShaderProgramv",
    r"^glCreateSamplers$",
    r"^glCreateTransformFeedbacks$",
    r"^glCreateQueries$",
    # 纹理存储分配
    r"^glTextureStorage",
    r"^glTexStorage",
    r"^glTextureBufferRange",
    r"^glTextureSubImage",
    # 映射（返回指针供调用方读写）
    r"^glMapNamedBuffer",
    r"^glMapBuffer",
    # 渲染缓冲存储
    r"^glNamedRenderbufferStorage",
    r"^glRenderbufferStorageMultisample",
    # 顶点数组元素缓冲绑定（绑定失败会导致绘制读错数据）
    r"^glVertexArrayElementBuffer$",
    # 在「缓冲无存储」前提下必然连带失败的
    r"^glFlushMappedBufferRange",
    r"^glFlushMappedNamedBufferRange",
    r"^glUnmapNamedBuffer$",
]

# CAUTION：返回值的语义是「查询结果」，stub 返回 0 可能被误读。
CAUTION_PATTERNS = [
    r"^glGetNamedBuffer",
    r"^glGetTexture",
    r"^glGetVertexArray",
    r"^glGetFramebuffer",
    r"^glGetRenderbuffer",
    r"^glGetQuery",
    r"^glGetSynciv",
    r"^glGetSampler",
    r"^glGetTransformFeedback",
    r"^glGetProgramResource",
    r"^glGetActiveUniformBlock",
    r"^glGetInternalformativ",
    r"^glGetMultisamplefv",
    r"^glGetnTexImage",
]

# 说明：以下功能在 ES 3.2 上**本就不存在**，且原版 MC 不使用（见 o-02），
# 因此 stub 是合理选择 —— 但要确认「调用方不会依赖它产生资源」。
KNOWN_DESKTOP_ONLY = {
    "几何着色器": r"^glProgramParameteri$|^glFramebufferTexture$|^glFramebufferTextureLayer$",
    "细分着色器": r"^glPatchParameteri|^glPatchParameterfv",
    "变换反馈": r"^glBeginTransformFeedback|^glEndTransformFeedback|^glTransformFeedback",
    "裁剪控制": r"^glClipControl$",
    "深度钳制": r"^glDepthRange$",
    "多边形模式": r"^glPolygonMode$|^glPolygonOffsetClamp",
}


def parse_stubs(path):
    """
    从 symbols.def 解析 `S <ret> <name>(<args>)` 行。
    返回 [(name, return_type, full_signature), ...]
    """
    out = []
    if not os.path.isfile(path):
        return out

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.startswith("S "):
                continue
            sig = line[2:].strip()
            m = re.match(r"^(.*?)\s+(\w+)\s*\((.*)\)\s*$", sig)
            if not m:
                continue
            ret, name, args = m.group(1).strip(), m.group(2), m.group(3)
            out.append((name, ret, sig))
    return out


def classify(name, ret):
    for pat in DANGER_PATTERNS:
        if re.match(pat, name):
            return "DANGER"
    for pat in CAUTION_PATTERNS:
        if re.match(pat, name):
            return "CAUTION"
    return "SAFE"


def why_danger(name):
    """给 DANGER 项一句人话解释。"""
    if "BufferStorage" in name or "TextureStorage" in name or "TexStorage" in name:
        return "分配存储；stub 后存储为空，后续 map/使用会失败"
    if name.startswith("glCreate"):
        return "创建对象并返回句柄；stub 返回 0 = 无效句柄"
    if "NamedBufferData" in name or name == "glBufferData":
        return "分配/填充缓冲存储；stub 后缓冲无数据"
    if name.startswith("glMap"):
        return "返回映射指针；stub 返回 NULL，调用方按解引用处理"
    if "RenderbufferStorage" in name:
        return "分配渲染缓冲存储；stub 后附件不完整"
    if "ElementBuffer" in name:
        return "绑定索引缓冲；stub 后绘制读到错误索引"
    if name.startswith("glFlush") or name.startswith("glUnmap"):
        return "对已映射缓冲的操作；缓冲本无存储，连带失败"
    if name.startswith("glTextureSubImage") or name.startswith("glTextureBuffer"):
        return "向纹理上传数据；stub 后纹理内容为空"
    return "契约含产生资源的副作用"


def main():
    if not os.path.isfile(SYMBOLS_DEF):
        print("FAIL: 找不到 %s" % SYMBOLS_DEF)
        return 1

    stubs = parse_stubs(SYMBOLS_DEF)
    if not stubs:
        print("FAIL: 未解析到任何 stub —— symbols.def 格式可能已变")
        return 1

    buckets = {"DANGER": [], "CAUTION": [], "SAFE": []}
    for name, ret, sig in stubs:
        buckets[classify(name, ret)].append((name, ret, sig))

    print("=" * 74)
    print("Stub 危险度审计（判据：调用方是否依赖其返回值/副作用）")
    print("=" * 74)
    print("扫描文件 : %s" % SYMBOLS_DEF)
    print("Stub 总数: %d" % len(stubs))
    print()
    print("  DANGER  (产生资源，stub 会导致延迟失败) : %d" % len(buckets["DANGER"]))
    print("  CAUTION (返回值被当作数据使用)         : %d" % len(buckets["CAUTION"]))
    print("  SAFE    (纯状态设置 / 调用方不依赖)     : %d" % len(buckets["SAFE"]))
    print()

    # ---- DANGER 详情 ----
    if buckets["DANGER"]:
        print("=" * 74)
        print("DANGER 清单（这些是与 glBufferStorage 同类的隐患）")
        print("=" * 74)
        for name, ret, sig in sorted(buckets["DANGER"]):
            print("  %-42s %s" % (name, why_danger(name)))
            print("      返回类型: %s" % ret)
        print()
    else:
        print("DANGER 清单为空 —— 未发现与 glBufferStorage 同类的隐患。")
        print()

    # ---- CAUTION 详情 ----
    if buckets["CAUTION"]:
        print("=" * 74)
        print("CAUTION 清单（返回值会被当作真实数据）")
        print("=" * 74)
        for name, ret, sig in sorted(buckets["CAUTION"]):
            print("  %-42s 返回类型: %s" % (name, ret))
        print()

    # ---- 已知桌面专属功能（stub 是合理选择，仅提示） ----
    print("=" * 74)
    print("参考：ES 3.2 本就不存在、且原版 MC 不使用的功能族")
    print("=" * 74)
    for label, pat in KNOWN_DESKTOP_ONLY.items():
        matched = [n for n, _, _ in stubs if re.match(pat, n)]
        if matched:
            print("  %-10s %d 个: %s" % (label, len(matched), ", ".join(matched[:4])))
            if len(matched) > 4:
                print("  %-10s      ... 等共 %d 个" % ("", len(matched)))
    print()

    # ---- 结论 ----
    print("=" * 74)
    n_danger = len(buckets["DANGER"])
    if n_danger == 0:
        print("结论: 未发现 DANGER 项。484 个 stub 中无 glBufferStorage 同类隐患。")
    else:
        print("结论: 发现 %d 个 DANGER 项，需逐个判断「原版 MC / Sodium 是否真的会调用」。" % n_danger)
        print("      判据：若某符号在真机 status.json 的 stub_symbols 里出现过，")
        print("            说明确有调用方走到它，必须按 glBufferStorage 的方式修复。")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
