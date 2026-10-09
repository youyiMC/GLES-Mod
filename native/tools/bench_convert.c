/*
 * bench_convert.c -- measure GLSL->GLSL ES conversion throughput.
 *
 * Why: the converter runs inside glShaderSource. Whether that matters for
 * performance depends entirely on how often shaders are compiled and how
 * long one conversion takes. Both are measurable, neither should be guessed.
 *
 * Prints per-file and aggregate timings using real corpus shaders.
 *
 * LGPL-3.0-or-later
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

char *glesmod_convert_shader_source(const char *src, int *out_len, int stage);
int glesmod_trace_enabled = 0;
void glesmod_degrade(int code, const char *detail) { (void)code; (void)detail; }

#define STAGE_VERTEX   0x8B31
#define STAGE_FRAGMENT 0x8B30

static char *slurp(const char *path, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz <= 0) { fclose(f); return NULL; }
    char *b = (char *)malloc((size_t)sz + 1);
    size_t got = fread(b, 1, (size_t)sz, f);
    b[got] = 0;
    fclose(f);
    *n = got;
    return b;
}

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: bench <file> [file...]\n");
        return 2;
    }

    double total_in = 0, total_out = 0;
    double worst = 0;
    const char *worst_name = "";
    int n = 0;

    printf("%-46s %8s %8s %10s\n", "file", "in_B", "out_B", "ms");
    printf("--------------------------------------------------------"
           "-------------------\n");

    for (int i = 1; i < argc; i++) {
        size_t sz = 0;
        char *src = slurp(argv[i], &sz);
        if (!src) continue;

        /* pick stage by extension so precision injection is exercised */
        int stage = STAGE_FRAGMENT;
        size_t L = strlen(argv[i]);
        if (L > 5 && (strcmp(argv[i] + L - 5, ".vert") == 0 ||
                      strcmp(argv[i] + L - 4, ".vsh") == 0)) {
            stage = STAGE_VERTEX;
        }

        double t0 = now_ms();
        int out_len = 0;
        char *out = glesmod_convert_shader_source(src, &out_len, stage);
        double dt = now_ms() - t0;

        if (out) {
            printf("%-46s %8zu %8d %10.3f\n",
                   argv[i] + (strlen(argv[i]) > 44 ? strlen(argv[i]) - 44 : 0),
                   sz, out_len, dt);
            total_in += (double)sz;
            total_out += (double)out_len;
            if (dt > worst) { worst = dt; worst_name = argv[i]; }
            n++;
            free(out);
        }
        free(src);
    }

    printf("\n=== summary ===\n");
    printf("files converted      : %d\n", n);
    printf("input  bytes total   : %.0f\n", total_in);
    printf("output bytes total   : %.0f\n", total_out);
    printf("worst single file    : %.3f ms  (%s)\n", worst, worst_name);
    printf("\n");
    printf("NOTE: this measures ONE conversion pass over each file.\n");
    printf("      Device compiled ~150 shaders in one session.\n");
    return 0;
}
