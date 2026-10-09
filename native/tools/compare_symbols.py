#!/usr/bin/env python3
"""
比对桌面 GL core profile 与 GLES 的符号差集。

用途（对应任务书 O-02）：
    量化 native 层的真实工作量。三类符号的实现成本差异极大：

    [共通] GL 与 GLES 都有同名命令 -> 直接转发（零成本，仅需函数指针转发）
    [映射] GL 有、GLES 无，但可用其他 GLES 调用等价实现 -> 需写适配代码
           （如 glTexImage1D -> glTexImage2D，glGetString(GL_EXTENSIONS) -> glGetStringi）
    [缺失] GL 有、GLES 完全无对应能力 -> 需仿真或降级
           （如 glPolygonMode、glLogicOp）

    差集大小直接决定 MVP 工作量，是本项目最重要的量化指标。

用法：
    py compare_symbols.py --gl gl_3.2_core.txt --gles gles_3.2.txt \
        --json-out symbol_diff.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# 已知 GL 有 / GLES 无，但可用其他 GLES 调用等价实现的命令。
# 值是替代方案说明，供实现时参考。
KNOWN_MAPPABLE: dict[str, str] = {
    # 一维/三维纹理：ES 无 1D 纹理，用 2D + height=1 模拟
    "glTexImage1D": "→ glTexImage2D（height=1）",
    "glTexSubImage1D": "→ glTexSubImage2D（height=1）",
    "glCopyTexImage1D": "→ glCopyTexImage2D（height=1）",
    "glCopyTexSubImage1D": "→ glCopyTexSubImage2D（height=1）",
    # 多重采样纹理的固定采样数变体：ES 无对应入口
    "glTexImage2DMultisample": "→ glTexStorage2DMultisample 或降级为非 MSAA",
    "glTexImage3DMultisample": "→ glTexStorage3DMultisample 或降级为非 MSAA",
    # 双精度像素传输：ES 无
    "glPixelStoref": "→ glPixelStorei（浮点值取整）",
    # 整数纹理参数：ES 3.0+ 有 glTexParameterIiv，但部分组合语义不同
    "glTexParameterIiv": "→ glTexParameteri（ES 3.0+ 有对应）",
    "glTexParameterIuiv": "→ glTexParameteri（ES 3.0+ 有对应）",
    # 扩展查询：GL 3.0+ 改用 glGetStringi，ES 3.0+ 同样支持
    "glGetStringi": "→ 直通（ES 3.0+ 支持）",
    # FBO 的 1D/3D 纹理附着
    "glFramebufferTexture1D": "→ glFramebufferTexture2D（height=1）",
    "glFramebufferTexture3D": "→ glFramebufferTextureLayer 或 2D 数组",
    # 渲染缓冲多重采样：ES 3.0+ 支持 glRenderbufferStorageMultisample
    "glRenderbufferStorageMultisample": "→ 直通（ES 3.0+ 支持）",
    # glGetError：ES 有，但错误枚举值不同，需映射返回值
    "glGetError": "→ 直通 + 枚举值映射",
    # 帧缓冲位块传送：ES 3.0+ 支持
    "glBlitFramebuffer": "→ 直通（ES 3.0+ 支持）",

    # ===== 以下为已逐条核对手工填入的精确映射 =====
    # 浮点变体：ES 统一用 f 后缀
    "glClearDepth": "→ glClearDepthf（double 转 float）",
    "glDepthRange": "→ glDepthRangef（double 转 float）",
    # 浮点顶点属性：ES 只有 f 后缀版本
    "glVertexAttrib1d": "→ glVertexAttrib1f（double 转 float）",
    "glVertexAttrib1dv": "→ glVertexAttrib1fv",
    "glVertexAttrib1s": "→ glVertexAttrib1f（short 转 float）",
    "glVertexAttrib1sv": "→ glVertexAttrib1fv",
    "glVertexAttrib2d": "→ glVertexAttrib2f",
    "glVertexAttrib2dv": "→ glVertexAttrib2fv",
    "glVertexAttrib2s": "→ glVertexAttrib2f",
    "glVertexAttrib2sv": "→ glVertexAttrib2fv",
    "glVertexAttrib3d": "→ glVertexAttrib3f",
    "glVertexAttrib3dv": "→ glVertexAttrib3fv",
    "glVertexAttrib3s": "→ glVertexAttrib3f",
    "glVertexAttrib3sv": "→ glVertexAttrib3fv",
    "glVertexAttrib4d": "→ glVertexAttrib4f",
    "glVertexAttrib4dv": "→ glVertexAttrib4fv",
    "glVertexAttrib4s": "→ glVertexAttrib4f",
    "glVertexAttrib4sv": "→ glVertexAttrib4fv",
    "glVertexAttrib4bv": "→ glVertexAttribI4bv / glVertexAttrib4Nubv",
    "glVertexAttrib4iv": "→ glVertexAttribI4iv",
    "glVertexAttrib4uiv": "→ glVertexAttribI4uiv",
    "glVertexAttrib4usv": "→ glVertexAttribI4usv",
    "glVertexAttrib4Nub": "→ glVertexAttrib4f（归一化后转换）",
    "glVertexAttrib4Nubv": "→ glVertexAttrib4Nubv（ES 支持）",
    "glVertexAttrib4Niv": "→ glVertexAttrib4Niv（ES 支持）",
    "glVertexAttrib4Nsv": "→ glVertexAttrib4Nsv（ES 支持）",
    "glVertexAttrib4Nbv": "→ glVertexAttrib4Nubv",
    "glVertexAttrib4Nuiv": "→ glVertexAttribI4uiv（归一化）",
    "glVertexAttrib4Nusv": "→ glVertexAttribI4usv（归一化）",
    "glVertexAttribI1i": "→ 拆分为向量变体 glVertexAttribI4i",
    "glVertexAttribI1iv": "→ glVertexAttribI4iv",
    "glVertexAttribI1ui": "→ glVertexAttribI4ui",
    "glVertexAttribI1uiv": "→ glVertexAttribI4uiv",
    "glVertexAttribI2i": "→ glVertexAttribI4i",
    "glVertexAttribI2iv": "→ glVertexAttribI4iv",
    "glVertexAttribI2ui": "→ glVertexAttribI4ui",
    "glVertexAttribI2uiv": "→ glVertexAttribI4uiv",
    "glVertexAttribI3i": "→ glVertexAttribI4i",
    "glVertexAttribI3iv": "→ glVertexAttribI4iv",
    "glVertexAttribI3ui": "→ glVertexAttribI4ui",
    "glVertexAttribI3uiv": "→ glVertexAttribI4uiv",
    "glVertexAttribI4bv": "→ glVertexAttribI4iv（byte 转 int）",
    "glVertexAttribI4sv": "→ glVertexAttribI4iv（short 转 int）",
    "glVertexAttribI4ubv": "→ glVertexAttribI4uiv",
    "glVertexAttribI4usv": "→ glVertexAttribI4uiv",
    # 双精度查询：ES 无 double，转 float
    "glGetDoublev": "→ glGetFloatv（double 转 float）",
    "glGetVertexAttribdv": "→ glGetVertexAttribfv",
    # 缓冲区映射：ES 只有 Range 变体
    "glMapBuffer": "→ glMapBufferRange（offset=0, length=全量）",
    "glGetBufferSubData": "→ glMapBufferRange + memcpy + glUnmapBuffer",
    "glGetCompressedTexImage": "→ 无直接对应，需 FBO 回读或降级",
    "glCompressedTexImage1D": "→ glCompressedTexImage2D（height=1）",
    "glCompressedTexSubImage1D": "→ glCompressedTexSubImage2D（height=1）",
    # 查询对象：ES 只有无符号整数版本
    "glGetQueryObjectiv": "→ glGetQueryObjectuiv（ES 3.0+）",
    # 多重绘制：ES 无，必须降级（Sodium 依赖，重点）
    "glMultiDrawArrays": "→ 循环 glDrawArrays（降级，计入 DegradeReason）",
    "glMultiDrawElements": "→ 循环 glDrawElements（降级，Sodium 会受影响）",
    "glMultiDrawElementsBaseVertex": "→ 循环 glDrawElementsBaseVertex",
    # 片元数据位置：ES 用着色器 layout 限定符
    "glBindFragDataLocation": "→ 着色器转换时改写为 layout(location=N) out",
    # 其他 ES 支持但命名不同的查询
    "glGetActiveUniformName": "→ glGetActiveUniform + glGetUniformName（ES 无此入口）",
    # 点参数：ES 仅支持 gl_PointSize 走着色器
    "glPointParameterf": "→ 忽略或转 gl_PointSize 着色器写入",
    "glPointParameterfv": "→ 忽略或转 gl_PointSize 着色器写入",
    "glPointParameteri": "→ 忽略（ES 无点精灵坐标原点切换）",
    "glPointParameteriv": "→ 忽略",
    # ES 3.0 有固定索引重启值，但入口不同
    "glPrimitiveRestartIndex": "→ glPrimitiveRestartIndex（ES 3.0+ 有同名入口）",
    # 条件渲染：ES 3.0+ 有 glBeginConditionalRender 的等价能力
    "glBeginConditionalRender": "→ 需用 GL_ANY_SAMPLES_PASSED 间接实现或降级",
    "glEndConditionalRender": "→ 同上",
    "glClampColor": "→ 忽略（ES 无颜色钳制控制）",
    "glProvokingVertex": "→ 忽略或依赖 GL_LAST_VERTEX_CONVENTION 扩展",
}

# 已知 GL 有 / GLES 无，且无法用等价调用实现，必须仿真或降级。
KNOWN_UNSUPPORTED: dict[str, str] = {
    "glPolygonMode": "ES 无面模式（wireframe）。仅 GL_FILL 可忽略，其他需降级",
    "glLogicOp": "ES 无逻辑运算。需降级为混合或忽略",
    "glPointSize": "ES 无 glPointSize。可用着色器 gl_PointSize 替代",
    "glLineWidth": "ES 仅支持 1.0（部分驱动支持更多）。需降级或忽略",
    "glClipPlane": "ES 无裁剪平面。需用着色器 discard 替代",
    "glAlphaFunc": "ES 无 alpha 测试（core profile 也移除了）。需着色器替代",
    "glColorMaterial": "ES 无。固定功能管线相关，core profile 已移除",
    "glDrawBuffer": "ES 无单缓冲选择。用 glDrawBuffers 替代",
    "glReadBuffer": "ES 3.0+ 支持，但可用值受限",
    "glGetTexImage": "ES 无。需用 glReadPixels 或 FBO 回读",
    "glGetTexLevelParameteriv": "ES 无。需跟踪纹理状态",
    "glTexGend": "ES 无纹理坐标生成。固定功能相关",
    "glTexGenf": "ES 无纹理坐标生成。固定功能相关",
    "glTexGeni": "ES 无纹理坐标生成。固定功能相关",
    "glFogi": "ES 无雾效。固定功能相关",
    "glFogf": "ES 无雾效。固定功能相关",
    "glFogfv": "ES 无雾效。固定功能相关",
    "glFogiv": "ES 无雾效。固定功能相关",
    "glLightf": "ES 无光照。固定功能相关",
    "glLightfv": "ES 无光照。固定功能相关",
    "glLighti": "ES 无光照。固定功能相关",
    "glLightiv": "ES 无光照。固定功能相关",
    "glLightModelf": "ES 无光照模型。固定功能相关",
    "glLightModelfv": "ES 无光照模型。固定功能相关",
    "glMaterialf": "ES 无材质。固定功能相关",
    "glMaterialfv": "ES 无材质。固定功能相关",
    "glShadeModel": "ES 无。固定功能相关",
    "glPixelTransferf": "ES 无像素传输操作",
    "glPixelTransferi": "ES 无像素传输操作",
    "glPixelMapfv": "ES 无像素映射",
    "glPixelZoom": "ES 无像素缩放",
    "glCopyPixels": "ES 无。用 glBlitFramebuffer 替代",
    "glRasterPos2f": "ES 无光栅位置。固定功能相关",
    "glRasterPos2i": "ES 无光栅位置。固定功能相关",
    "glRasterPos3f": "ES 无光栅位置。固定功能相关",
    "glRasterPos3i": "ES 无光栅位置。固定功能相关",
    "glRasterPos4f": "ES 无光栅位置。固定功能相关",
    "glRasterPos4i": "ES 无光栅位置。固定功能相关",
    "glDrawPixels": "ES 无。固定功能相关",
    "glBitmap": "ES 无。固定功能相关",
    "glAccum": "ES 无累加缓冲",
    "glClearAccum": "ES 无累加缓冲",
    "glPushAttrib": "ES 无属性栈。需自行跟踪状态",
    "glPopAttrib": "ES 无属性栈。需自行跟踪状态",
    "glPushClientAttrib": "ES 无客户端属性栈",
    "glPopClientAttrib": "ES 无客户端属性栈",
    "glPrioritizeTextures": "ES 无纹理优先级",
    "glAreTexturesResident": "ES 无纹理驻留查询",
    "glFeedbackBuffer": "ES 无反馈缓冲",
    "glPassThrough": "ES 无",
    "glSelectBuffer": "ES 无选择缓冲",
    "glInitNames": "ES 无名称栈",
    "glLoadName": "ES 无名称栈",
    "glPushName": "ES 无名称栈",
    "glPopName": "ES 无名称栈",
    "glRenderMode": "ES 无渲染模式切换",
}


def load(path: Path) -> set[str]:
    if not path.is_file():
        print(f"错误: 找不到 {path}", file=sys.stderr)
        raise SystemExit(1)
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="比对 GL core 与 GLES 符号差集")
    ap.add_argument("--gl", required=True, help="桌面 GL 符号清单")
    ap.add_argument("--gles", required=True, help="GLES 符号清单")
    ap.add_argument("--json-out", help="JSON 输出路径")
    args = ap.parse_args()

    gl = load(Path(args.gl))
    gles = load(Path(args.gles))

    common = gl & gles
    only_gl = gl - gles
    only_gles = gles - gl

    mappable = sorted(n for n in only_gl if n in KNOWN_MAPPABLE)
    unsupported = sorted(n for n in only_gl if n in KNOWN_UNSUPPORTED)
    unknown = sorted(n for n in only_gl if n not in KNOWN_MAPPABLE and n not in KNOWN_UNSUPPORTED)

    total = len(gl)
    result = {
        "source": "Khronos OpenGL-Registry gl.xml",
        "gl_symbols": total,
        "gles_symbols": len(gles),
        "common": len(common),
        "gl_only": len(only_gl),
        "buckets": {
            "forward": {"count": len(common), "meaning": "同名同义，直接转发（零成本）"},
            "map": {"count": len(mappable), "meaning": "需映射到其他 GLES 调用"},
            "unsupported": {"count": len(unsupported), "meaning": "需仿真或降级"},
            "unknown": {"count": len(unknown), "meaning": "未分类，需人工复核"},
        },
        "forward_percent": round(len(common) / total * 100, 1) if total else 0,
        "workload_percent": round((len(mappable) + len(unsupported) + len(unknown)) / total * 100, 1)
        if total
        else 0,
        "details": {
            "mappable": [{"name": n, "plan": KNOWN_MAPPABLE[n]} for n in mappable],
            "unsupported": [{"name": n, "plan": KNOWN_UNSUPPORTED[n]} for n in unsupported],
            "unknown": unknown,
            "gles_only": sorted(only_gles),
        },
    }

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print(f"桌面 GL core 符号数 : {total}")
    print(f"GLES 符号数         : {len(gles)}")
    print(f"异名（GL 独有）     : {len(only_gl)}")
    print(f"GLES 独有（无需导出）: {len(only_gles)}")
    print()
    print("本项目 native 层分类：")
    print(f"  [共通] 直接转发   {len(common):4d}  ({len(common)/total*100:5.1f}%)")
    print(f"  [映射] 需适配     {len(mappable):4d}  ({len(mappable)/total*100:5.1f}%)")
    print(f"  [缺失] 需仿真降级 {len(unsupported):4d}  ({len(unsupported)/total*100:5.1f}%)")
    print(f"  [未知] 待复核     {len(unknown):4d}  ({len(unknown)/total*100:5.1f}%)")
    print()
    print(f"需要额外实现的符号占比: {result['workload_percent']}%")
    if unknown:
        print()
        print("待复核符号:")
        for n in unknown:
            print(f"  {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
