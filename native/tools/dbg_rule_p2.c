/* Replicate the exact rule-P test template to find why it fails. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *glesmod_convert_shader_source(const char *src, int *out_len, int stage);
int glesmod_trace_enabled = 0;
void glesmod_degrade(int code, const char *detail) { (void)code; (void)detail; }

static const char *const M_TEMPLATE =
    "#version 330 core\n"
    "layout(std140) uniform B { uint baseVertex; };\n"
    "out float v;\n"
    "void main() {\n"
    "    uint acc = baseVertex;\n"
    "    %s\n"
    "    gl_Position = vec4(float(acc));\n"
    "}\n";

int main(void) {
    char buf[512];
    snprintf(buf, sizeof buf, M_TEMPLATE, "uint vid = gl_VertexID - baseVertex;");

    printf("=== INPUT ===\n%s\n", buf);
    int len = 0;
    char *out = glesmod_convert_shader_source(buf, &len, 0x8B31);
    printf("=== OUTPUT (%d bytes) ===\n%s\n", len, out ? out : "(null)");
    if (out) free(out);

    printf("=== does std140 survive? ===\n");
    out = glesmod_convert_shader_source(buf, &len, 0x8B31);
    printf("  strstr(std140)      : %s\n", strstr(out, "std140") ? "YES" : "NO");
    printf("  strstr(std140.0)    : %s\n", strstr(out, "std140.0") ? "YES <-- BUG" : "no");
    printf("  strstr(uint(gl_Ver) : %s\n", strstr(out, "uint(gl_VertexID)") ? "YES" : "NO");
    free(out);
    return 0;
}
