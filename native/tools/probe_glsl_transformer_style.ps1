# Can our converter handle the kind of GLSL that glsl-transformer produces?
#
# iris-flw-compat merges Flywheel's vertex pipeline into the shaderpack's
# gbuffers program using glsl-transformer (an AST rewriter). Its output is then
# fed to Iris, which calls glShaderSource -> OUR converter.
#
# GlslTransformerVertPatcher explicitly:
#   * forces "#version <max(orig,400)> compatibility"
#   * rewrites gl_Vertex / gl_Normal / gl_MultiTexCoord0 / gl_Color /
#     gl_TextureMatrix[0] / ftransform() / gl_ModelViewMatrix ...
#   * declares 7 vertex attributes (vec3/vec4/vec2/vec2/vec2/vec4/ivec4/vec2)
#   * injects a Flywheel body into main()
#
# So the realistic question is: does our converter survive that output?
# ASCII only (PS 5.1 reads .ps1 as GBK on zh-CN).

$ErrorActionPreference = 'Continue'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$cache = Join-Path $scriptDir '.cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

# Build the converter CLI fresh (never reuse a stale binary).
$gcc = 'C:\msys64\ucrt64\bin\gcc.exe'
$cli = Join-Path $cache 'convert_shader_cli.exe'
& $gcc -O2 -std=c11 -w -I (Join-Path $root 'native\src') -I (Join-Path $root 'native\include') `
    -o $cli (Join-Path $scriptDir 'convert_shader_cli.c') (Join-Path $root 'native\src\shader.c') -lm
if ($LASTEXITCODE -ne 0) { throw 'converter CLI build failed' }

# A representative glsl-transformer-style output: compatibility version,
# desktop builtins, 7 attributes, Flywheel body injected into main().
$sample = @'
#version 400 compatibility
in vec3 _flw_aPos; // irisflw remapped
layout(location = 0) in vec3 at_tangent;
layout(location = 1) in vec3 at_midBlock;
layout(location = 2) in vec2 mc_Entity;
layout(location = 3) in vec4 vColor;
uniform mat4 gbufferModelViewInverse;
vec4 flw_vertexPos;
vec3 flw_vertexNormal;
vec4 flw_vertexColor;
vec2 flw_vertexTexCoord;
vec4 flw_fake_tangent;
void main() {
    flw_vertexPos = gl_ModelViewMatrix * gl_Vertex;
    flw_vertexNormal = gl_NormalMatrix * gl_Normal;
    flw_vertexColor = gl_Color;
    flw_vertexTexCoord = (gl_TextureMatrix[0] * gl_MultiTexCoord0).xy;
    vec3 skewedNormal = flw_vertexNormal + vec3(0.5,0.5,0.5);
    flw_fake_tangent = vec4(normalize(skewedNormal - flw_vertexNormal * dot(skewedNormal, flw_vertexNormal)).xyz, 1.0);
    gl_Position = ftransform();
}
'@

$in = Join-Path $cache 'gt_style.vert'
[System.IO.File]::WriteAllText($in, $sample, (New-Object System.Text.UTF8Encoding($false)))

$out = Join-Path $cache 'gt_style.es.vert'
& $cli $in vertex $out
Write-Host ('converter exit=' + $LASTEXITCODE)
if (Test-Path $out) {
    $len = (Get-Item $out).Length
    Write-Host ('output bytes=' + $len)
    Write-Host '--- output ---'
    Get-Content $out | ForEach-Object { Write-Host ('  ' + $_) }
}

# Now the decisive check: does the OUTPUT compile as GLSL ES 3.20?
$glslc = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe'
Write-Host ''
Write-Host '=== glslc (ES 3.20) on the CONVERTED output ==='
$res = (& $glslc --target-env=opengl -fshader-stage=vertex $out -o (Join-Path $cache 'gt_style.spv') 2>&1 | Out-String)
$real = @(($res -split "`r?`n") | Where-Object {
    $_ -match 'error:' -and
    $_ -notmatch 'non-opaque uniform' -and
    $_ -notmatch 'SPIR-V' -and
    $_ -notmatch 'location' -and
    $_ -notmatch 'uniform/buffer blocks require' -and
    $_ -notmatch 'binding=X' })
Write-Host ('real GLSL ES errors: ' + $real.Count)
$real | Select-Object -First 20 | ForEach-Object { Write-Host ('  ' + $_.Trim()) }
