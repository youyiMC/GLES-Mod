/* What does the converter actually produce for `baseVertex + 0`? */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *glesmod_convert_shader_source(const char *src, int *out_len, int stage);
int glesmod_trace_enabled = 0;
void glesmod_degrade(int code, const char *detail) { (void)code; (void)detail; }

static void run(const char *stmt) {
    char buf[512];
    snprintf(buf, sizeof buf,
             "#version 330 core\n"
             "uniform uint baseVertex;\n"
             "out float v;\n"
             "void main() {\n"
             "    uint acc = baseVertex;\n"
             "    %s\n"
             "    gl_Position = vec4(float(acc));\n"
             "}\n", stmt);
    int len = 0;
    char *out = glesmod_convert_shader_source(buf, &len, 0x8B31);
    printf("--- stmt: %s\n", stmt);
    if (out) {
        /* print only the body lines containing acc/uint */
        char *save = NULL;
        for (char *l = strtok_r(out, "\n", &save); l; l = strtok_r(NULL, "\n", &save)) {
            if (strstr(l, "acc") || strstr(l, "uint") || strstr(l, "baseVertex"))
                printf("      %s\n", l);
        }
        free(out);
    }
    printf("\n");
}

int main(void) {
    run("uint r = baseVertex + 0; acc = r; v = float(acc);");
    run("uint r = baseVertex + 1; acc = r; v = float(acc);");
    run("acc += 1; v = float(acc);");
    run("uint r = baseVertex - 2; acc = r; v = float(acc);");
    return 0;
}
