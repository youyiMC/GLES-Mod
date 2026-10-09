/*
 * enum.c —— 桌面 GL 枚举值到 GLES 的映射
 *
 * 背景：
 *   桌面 GL 与 GLES 的枚举值大多数值相同（如 GL_TEXTURE_2D = 0x0DE1），
 *   但存在若干差异。若直接把桌面 GL 的枚举传给 GLES，轻则行为错误，
 *   重则产生 GL_INVALID_ENUM 并被上层误判为渲染故障。
 *
 * 本文件只处理「确定有差异」的枚举。不确定的一律原样透传，
 * 因为这比错误映射更安全（错误映射会静默产生错误渲染）。
 *
 * 许可证：LGPL-3.0-or-later
 */

#include "gl_internal.h"

#include <stdio.h>

/* ------------------------------------------------------------------ */
/* 已知差异表                                                          */
/* ------------------------------------------------------------------ */

typedef struct {
    GLenum from;   /* 桌面 GL 值 */
    GLenum to;     /* GLES 值 */
    const char *note;
} enum_map_entry;

/*
 * 差异来源说明：
 *
 * 1. 纹理目标
 *    GL_TEXTURE_1D (0x0DE0) 在 ES 中不存在。若上层请求 1D 纹理，
 *    只能降级为 2D（由调用方处理），此处不映射以免掩盖问题。
 *
 * 2. 内部格式
 *    GL_RGBA8 在桌面为 0x8058，ES 3.0 起同样为 0x8058，无需映射。
 *    但 GL_SRGB8_ALPHA8 等格式在 ES 中要求扩展支持。
 *    ES 提供了兼容格式别名（如 GL_RGBA8 可用 GL_RGBA + GL_UNSIGNED_BYTE），
 *    本项目优先依赖数值一致性，仅对确认不一致的做映射。
 *
 * 3. 像素格式
 *    GL_BGRA (0x80E1) 在 ES 中需要扩展 (GL_EXT_texture_format_BGRA8888)。
 *    MC 在部分路径使用 BGRA（如字体纹理），此处映射为 GL_RGBA 并记录。
 *    注意：这是有损转换（通道顺序改变），因此仅在明确需要时启用。
 *
 * 4. 着色器阶段
 *    GL_GEOMETRY_SHADER (0x8DD9) / GL_TESS_* 在 ES 3.2 无对应。
 *    由调用方检测并降级，此处不映射。
 */
static const enum_map_entry KNOWN_MAPS[] = {
    /* 目前没有「可以安全自动映射」的条目。
     *
     * 这是刻意的保守选择：纹理格式与像素格式的转换会改变数据布局，
     * 盲目自动映射会静默产生错误图像。正确做法是在具体的调用点
     * （如 glTexImage2D）判断并处理，而不是在这里做全局映射。
     *
     * 保留此表以便后续加入确认安全的映射。 */
    { 0, 0, NULL }
};

/* ------------------------------------------------------------------ */
/* 映射实现                                                            */
/* ------------------------------------------------------------------ */

GLenum glesmod_map_enum(GLenum value) {
    for (size_t i = 0; KNOWN_MAPS[i].note != NULL; i++) {
        if (KNOWN_MAPS[i].from == value) {
            return KNOWN_MAPS[i].to;
        }
    }
    /* 无已知差异 -> 原样透传 */
    return value;
}

/*
 * 映射统计。用一个小的去重表记录发生过的映射，供状态文件输出。
 */
#define MAX_ENUM_MAPS 32

typedef struct {
    GLenum original;
    GLenum mapped;
    unsigned long count;
} enum_map_stat;

static enum_map_stat g_enum_stats[MAX_ENUM_MAPS];
static int g_enum_stats_len = 0;

void glesmod_log_enum_map(GLenum original, GLenum mapped) {
    if (original == mapped) return;

    for (int i = 0; i < g_enum_stats_len; i++) {
        if (g_enum_stats[i].original == original &&
            g_enum_stats[i].mapped == mapped) {
            g_enum_stats[i].count++;
            return;
        }
    }

    if (g_enum_stats_len < MAX_ENUM_MAPS) {
        g_enum_stats[g_enum_stats_len].original = original;
        g_enum_stats[g_enum_stats_len].mapped = mapped;
        g_enum_stats[g_enum_stats_len].count = 1;
        g_enum_stats_len++;

        char detail[128];
        snprintf(detail, sizeof(detail),
                 "枚举映射 0x%04X -> 0x%04X", original, mapped);
        glesmod_degrade(GLESMOD_DEGRADE_ENUM_MAPPED, detail);
    }
}

int glesmod_enum_map_count(void) {
    return g_enum_stats_len;
}
