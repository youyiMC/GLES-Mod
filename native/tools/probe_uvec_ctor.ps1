# Is `uint(uvec2)` legal in GLSL ES 3.20?  Error or silent truncation?
# This decides the SYMPTOM SHAPE:
#   error      -> shader fails to compile, chunk rendering dies outright
#   truncation -> shader links, texcoords collapse to .x  -> wrong textures
$glslc = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe'

function Probe([string]$name, [string]$body) {
    $f = Join-Path $env:TEMP ("uvecprobe_" + $name + ".vert")
    $o = Join-Path $env:TEMP ("uvecprobe_" + $name + ".spv")
    @"
#version 320 es
precision highp float;
precision highp int;
in uvec2 a_TexCoord;
out vec2 v;
void main() {
$body
    gl_Position = vec4(0.0);
}
"@ | Set-Content -Path $f -Encoding UTF8
    $res = (& $glslc --target-env=opengl -fshader-stage=vertex $f -o $o 2>&1 | Out-String)
    $real = @(($res -split "`r?`n") | Where-Object {
        $_ -match 'error:' -and $_ -notmatch 'non-opaque' -and
        $_ -notmatch 'SPIR-V' -and $_ -notmatch 'location' -and
        $_ -notmatch 'uniform/buffer blocks require' -and $_ -notmatch 'binding=X' })
    $verdict = if ($real.Count -eq 0) { 'ACCEPTED (silent)' } else { 'REJECTED' }
    Write-Host ("  {0,-46} {1}" -f $name, $verdict)
    if ($real.Count -gt 0) { $real | Select-Object -First 3 | ForEach-Object { Write-Host ('        ' + $_.Trim()) } }
}

Write-Host '=== constructing a scalar from a uvec2 ==='
Probe 'uint(uvec2)  -> uint'      '    uint r = uint(a_TexCoord); v = vec2(float(r));'
Probe 'int(uvec2)   -> uint'      '    int  r = int(a_TexCoord);  v = vec2(float(r));'
Probe 'float(uvec2) -> uint'      '    float r = float(a_TexCoord); v = vec2(r);'
Probe 'vec2(uvec2)  -> uint'      '    vec2 r = vec2(a_TexCoord); v = r;'
Write-Host ''
Write-Host '=== exact failing expression ==='
Probe 'vec2(uint(uvec2) & uint)'  '    const uint M = 15u; v = vec2(uint(a_TexCoord) & M) / 16.0;'
Probe 'vec2(uvec2 & uint) [orig]' '    const uint M = 15u; v = vec2(a_TexCoord & M) / 16.0;'
