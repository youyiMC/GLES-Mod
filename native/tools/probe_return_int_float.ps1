# Probe: is `return <int literal>;` inside a float-returning function legal in
# DESKTOP GLSL (and illegal in GLSL ES)?
#
# Why this decides something important:
#   Flywheel's flywheel:internal/wavelet.glsl has
#       float total_absorbance(...) {
#           if (scale_coefficient == 0) { return 0; }   // int literal
#           ...
#       }
#   If desktop GLSL ACCEPTS this, it is a desktop-only idiom -- exactly the
#   class of thing our converter exists to adapt (like `float f = 0;`,
#   `vec2 * 2`, `float < int`, ...). If desktop REJECTS it, it is genuinely
#   an upstream Flywheel bug.
#
# ASCII-only on purpose (PS 5.1 decodes .ps1 as GBK on zh-CN).
# LGPL-3.0-or-later

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $here)
Set-Location $root

$ndk = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64'
$cache = Join-Path $root 'native\tools\.cache\probe_return'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

$desktop = @'
#version 460
out vec4 color;
float f() {
    return 0;
}
void main() {
    gl_Position = vec4(0.0);
    color = vec4(f());
}
'@

$es = @'
#version 320 es
precision highp float;
out vec4 color;
float f() {
    return 0;
}
void main() {
    gl_Position = vec4(0.0);
    color = vec4(f());
}
'@

function Probe([string]$name, [string]$src) {
    $f   = Join-Path $cache ($name + '.vert')
    $spv = Join-Path $cache ($name + '.spv')
    [System.IO.File]::WriteAllText($f, $src, (New-Object System.Text.ASCIIEncoding))

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName  = "$ndk\glslc.exe"
    $psi.Arguments = "--target-env=opengl -fshader-stage=vertex `"$f`" -o `"$spv`""
    $psi.RedirectStandardError  = $true
    $psi.RedirectStandardOutput = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow  = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $err = $p.StandardError.ReadToEnd()
    $null = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()

    $lines = @(($err -split "`r?`n") | Where-Object { $_ -match '\S' })
    $real  = @($lines | Where-Object {
        $_ -match 'error:' -and
        $_ -notmatch 'non-opaque' -and
        $_ -notmatch 'SPIR-V' -and
        $_ -notmatch 'requires location' -and
        $_ -notmatch 'uniform/buffer blocks require' -and
        $_ -notmatch 'binding=X' -and
        $_ -notmatch 'errors? generated' })
    $verdict = if ($real.Count -eq 0) { 'ACCEPTED' } else { 'REJECTED' }
    Write-Host ("  {0,-14} {1}   (real errors = {2})" -f $name, $verdict, $real.Count)
    foreach ($l in $real) { Write-Host ("        " + $l.Trim()) }
    return $real.Count
}

Write-Host '=============================================================='
Write-Host ' `float f() { return 0; }`  --  desktop vs GLSL ES'
Write-Host '=============================================================='
$d = Probe 'desktop460' $desktop
Write-Host ''
$e = Probe 'es320' $es
Write-Host ''
Write-Host '=============================================================='
if ($d -eq 0 -and $e -gt 0) {
    Write-Host 'CONCLUSION: desktop ACCEPTS, ES REJECTS.'
    Write-Host '  => this is a desktop-only idiom, i.e. the same class of gap'
    Write-Host '     our converter already handles for assignments / args /'
    Write-Host '     comparisons. Adapting it is OUR job, not an upstream bug.'
} elseif ($d -gt 0) {
    Write-Host 'CONCLUSION: desktop also REJECTS it.'
    Write-Host '  => genuinely an upstream Flywheel bug; desktop never allowed it.'
} else {
    Write-Host 'CONCLUSION: inconclusive (both accepted?) -- inspect above.'
}
Write-Host '=============================================================='
