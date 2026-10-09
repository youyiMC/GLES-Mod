# Convert the Flywheel diffuse.glsl shape and see exactly what we break.
# ASCII-only.
$ErrorActionPreference = 'Continue'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
Set-Location $root

$cli   = Join-Path $root 'native\tools\.cache\convert_shader_cli.exe'
$ndk   = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64'
$fx    = Join-Path $root 'native\tools\fixtures\flywheel_diffuse.frag'
$out   = Join-Path $root 'native\tools\.cache\flywheel_diffuse.out.frag'

& $cli $fx fragment $out

Write-Output '=== CONVERTED ==='
$i = 0
Get-Content $out | ForEach-Object { $i++; Write-Output ('{0,4}: {1}' -f $i, $_) }
Write-Output ''

$res = (& "$ndk\glslc.exe" --target-env=opengl -fshader-stage=fragment $out -o (Join-Path $root 'native\tools\.cache\flywheel_diffuse.spv') 2>&1 | Out-String)
$real = @(($res -split "`r?`n") | Where-Object {
    $_ -match 'error:' -and $_ -notmatch 'non-opaque' -and
    $_ -notmatch 'SPIR-V' -and $_ -notmatch 'location' -and
    $_ -notmatch 'uniform/buffer blocks require' -and $_ -notmatch 'binding=X' })
Write-Output ('=== glslc real GLSL ES errors: {0} ===' -f $real.Count)
$real | ForEach-Object { Write-Output ('  ' + $_.Trim()) }
