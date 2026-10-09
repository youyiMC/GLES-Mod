/* Focused debug: what does the converter actually produce for rule P cases? */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *glesmod_convert_shader_source(const char *src, int *out_len, int stage);
int glesmod_trace_enabled = 0;
void glesmod_degrade(int code, const char *detail) { (void)code; (void)detail; }

int main(void) {
    const char *src =
        "#version 330 core\n"
        "uniform uint baseVertex;\n"
        "out float v;\n"
        "void main() {\n"
        "    uint vid = gl_VertexID - baseVertex;\n"
        "    v = float(vid);\n"
        "    gl_Position = vec4(v);\n"
        "}\n";

    printf("=== INPUT ===\n%s\n", src);
    int len = 0;
    char *out = glesmod_convert_shader_source(src, &len, 0x8B31);
    printf("=== OUTPUT (%d bytes) ===\n%s\n", len, out ? out : "(null)");
    if (out) free(out);
    return 0;
}
