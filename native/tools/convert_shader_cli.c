/*
 * convert_shader_cli.c -- 主机端命令行工具：转换一个着色器文件并输出结果
 *
 * 用途：
 *   把 Minecraft / FML / 模组的真实着色器文件喂给转换器，
 *   在主机上直接看输出，无需真机。配合 mc_shader_audit.py 批量审计。
 *
 * 用法：
 *   convert_shader_cli <输入文件> <vertex|fragment|unknown> [输出文件]
 *
 * 【为什么建议始终给出第三个参数（输出文件）】
 *   PowerShell 的文本管道会把换行重复，导致输出看起来多出一倍空行，
 *   从而把正确结果误判成有 bug。直接写文件则按字节保留原样。
 *
 * LGPL-3.0-or-later
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 转换器入口（定义在 shader.c）；本文件刻意不包含 gl_internal.h，
 * 只前向声明所需符号，避免把整个后端头文件拖进来。 */
char *glesmod_convert_shader_source(const char *src, int *out_len, int stage);

/*
 * shader.c 引用的外部符号，此处给出最小实现以便独立链接。
 *
 * glesmod_degrade 在真实后端里会累计降级事件并写日志；
 * 主机端测试只关心转换结果，因此实现为空。
 */
int glesmod_trace_enabled = 0;

void glesmod_degrade(int code, const char *detail) {
    (void)code;
    (void)detail;
}

void glesmod_log(const char *message) {
    (void)message;
}

void glesmod_trace_dump(const char *label, const char *text) {
    (void)label;
    (void)text;
}

#define STAGE_UNKNOWN   0
#define STAGE_VERTEX    0x8B31  /* GL_VERTEX_SHADER */
#define STAGE_FRAGMENT  0x8B30  /* GL_FRAGMENT_SHADER */

/* 读取整个文件到堆内存（NUL 结尾）。失败返回 NULL。 */
static char *read_whole_file(const char *path, size_t *out_size) {
    FILE *f = fopen(path, "rb");
    if (f == NULL) return NULL;

    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long n = ftell(f);
    if (n < 0) { fclose(f); return NULL; }
    rewind(f);

    char *buf = (char *)malloc((size_t)n + 1);
    if (buf == NULL) { fclose(f); return NULL; }

    size_t got = fread(buf, 1, (size_t)n, f);
    fclose(f);
    buf[got] = '\0';
    if (out_size) *out_size = got;
    return buf;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr,
                "用法: %s <输入文件> <vertex|fragment|unknown> [输出文件]\n"
                "  省略输出文件时写到 stdout。\n"
                "  建议始终指定输出文件：PowerShell 的文本管道会把换行重复，\n"
                "  导致输出看起来多出一倍空行，从而误判转换结果。\n",
                argv[0]);
        return 2;
    }

    const char *stage_arg = argv[2];
    int stage = STAGE_UNKNOWN;
    if (strcmp(stage_arg, "vertex") == 0)        stage = STAGE_VERTEX;
    else if (strcmp(stage_arg, "fragment") == 0) stage = STAGE_FRAGMENT;

    size_t size = 0;
    char *src = read_whole_file(argv[1], &size);
    if (src == NULL) {
        fprintf(stderr, "错误: 无法读取 %s\n", argv[1]);
        return 1;
    }

    int out_len = 0;
    char *out = glesmod_convert_shader_source(src, &out_len, stage);
    free(src);

    if (out == NULL) {
        fprintf(stderr, "错误: 转换失败（返回 NULL）\n");
        return 1;
    }

    if (argc >= 4) {
        /* 按字节写入文件，绕开任何 shell / PowerShell 的文本处理 */
        FILE *f = fopen(argv[3], "wb");
        if (f == NULL) {
            fprintf(stderr, "错误: 无法写入 %s\n", argv[3]);
            free(out);
            return 1;
        }
        fwrite(out, 1, (size_t)out_len, f);
        fclose(f);
    } else {
        fwrite(out, 1, (size_t)out_len, stdout);
    }
    free(out);
    return 0;
}
