# Build a tiny harness that runs the real device shader (fw220-raw.txt)
# through the converter and prints the lines around i.pose / gl_VertexID /
# the uint comparison, so we can see exactly what the device will receive.
# ASCII-only (PS 5.1 decodes as GBK on zh-CN).

$ErrorActionPreference = 'Stop'
# This script lives at <repo>/native/tools/, so the repo root is TWO levels up
# from the script directory (not one -- that mistake pointed at native\native).
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$src  = Join-Path $root 'native\src'
$inc  = Join-Path $root 'native\include'
$cache = Join-Path $scriptDir '.cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

$cc = $null
foreach ($cand in @('gcc', 'clang')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) { $cc = $cmd.Source; break }
}
if (-not $cc) { throw 'no host C compiler' }

$harness = Join-Path $cache 'fw220_main.c'
$exe     = Join-Path $cache 'fw220.exe'
$raw     = Join-Path $root 'fw220-raw.txt'

# The harness: read file, convert as vertex shader, write result, then
# report the interesting lines.
@"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *glesmod_convert_shader_source(const char *src, int *out_len, int stage);
int glesmod_trace_enabled = 0;
void glesmod_degrade(int code, const char *detail) { (void)code; (void)detail; }

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: fw220 <raw>\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "open failed\n"); return 2; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = malloc((size_t)n + 1);
    size_t got = fread(buf, 1, (size_t)n, f);
    buf[got] = 0; fclose(f);

    int len = 0;
    char *out = glesmod_convert_shader_source(buf, &len, 0x8B31);
    if (!out) { fprintf(stderr, "convert failed\n"); return 1; }

    FILE *o = fopen("fw220-converted-now.txt", "wb");
    fwrite(out, 1, (size_t)len, o);
    fclose(o);

    /* report */
    printf("=== converted length: %d ===\n", len);
    const char *pats[] = { "i.pose", "float(i)", "gl_VertexID", "!= 0", "pose;", NULL };
    const char *s = out;
    int lineno = 1;
    while (s && *s) {
        const char *e = strchr(s, '\n');
        size_t ll = e ? (size_t)(e - s) : strlen(s);
        for (int i = 0; pats[i]; i++) {
            if (strstr(s, pats[i]) && ll < 200) {
                /* only print if the match is within this line */
                char tmp[256];
                size_t cp = ll < sizeof(tmp) - 1 ? ll : sizeof(tmp) - 1;
                memcpy(tmp, s, cp); tmp[cp] = 0;
                if (strstr(tmp, pats[i])) {
                    printf("L%-4d | %s\n", lineno, tmp);
                }
                break;
            }
        }
        if (!e) break;
        s = e + 1; lineno++;
    }
    free(out); free(buf);
    return 0;
}
"@ | Set-Content -Path $harness -Encoding ASCII

& $cc -std=c11 -O1 -w -I (Join-Path $root 'native\include') -I $src `
    -o $exe $harness (Join-Path $src 'shader.c') -lm
if ($LASTEXITCODE -ne 0) { throw 'harness build failed' }

Push-Location $root
& $exe $raw
Pop-Location
