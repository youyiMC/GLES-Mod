# Reproduce the Flywheel integer-macro defect locally.
# ASCII-only (PS 5.1 reads .ps1 as GBK on zh-CN).
$ErrorActionPreference = 'Continue'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$cache = Join-Path $scriptDir '.cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

# Always rebuild the CLI: never trust a stale binary (see repo lesson 2s).
$gcc = 'C:\msys64\ucrt64\bin\gcc.exe'
$cli = Join-Path $cache 'convert_shader_cli.exe'
& $gcc -O2 -std=c11 -w -I (Join-Path $root 'native\src') -I (Join-Path $root 'native\include') `
    -o $cli (Join-Path $scriptDir 'convert_shader_cli.c') (Join-Path $root 'native\src\shader.c') -lm
if ($LASTEXITCODE -ne 0) { throw 'CLI build failed' }

$fx  = Join-Path $scriptDir 'fixtures\flywheel_int_macro.frag'
$out = Join-Path $cache 'int_macro.out.frag'
& $cli $fx fragment $out

Write-Host ''
Write-Host '=== INPUT (authoritative Flywheel shape) ==='
Get-Content $fx | ForEach-Object { Write-Host ('  ' + $_) }
Write-Host ''
Write-Host '=== CONVERTED ==='
Get-Content $out | ForEach-Object { Write-Host ('  ' + $_) }
Write-Host ''

$conv = Get-Content $out -Raw
Write-Host '=== verdict ==='
$bad1 = $conv -match 'COUNT-1\.0|COUNT - 1\.0'
$bad2 = $conv -match '-1\.0\) / TRANSPARENCY'
Write-Host ('  integer literal floated inside macro arithmetic : ' + $(if ($bad1) { 'YES  <-- DEFECT' } else { 'no' }))
Write-Host ('  produced `-1.0) / COUNT`                        : ' + $(if ($bad2) { 'YES  <-- DEFECT' } else { 'no' }))

# And the decisive check: does the OUTPUT compile as GLSL ES 3.20?
$glslc = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe'
$res = (& $glslc --target-env=opengl -fshader-stage=fragment $out -o (Join-Path $cache 'int_macro.spv') 2>&1 | Out-String)
$real = @(($res -split "`r?`n") | Where-Object {
    $_ -match 'error:' -and $_ -notmatch 'non-opaque' -and
    $_ -notmatch 'SPIR-V' -and $_ -notmatch 'location' -and
    $_ -notmatch 'uniform/buffer blocks require' -and $_ -notmatch 'binding=X' })
Write-Host ('  glslc real GLSL ES errors                       : ' + $real.Count)
$real | Select-Object -First 8 | ForEach-Object { Write-Host ('     ' + $_.Trim()) }
