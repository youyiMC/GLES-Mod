# Compile an extracted native dump with real glslang (ES 3.20) and report only
# the REAL GLSL errors (SPIR-V-only noise filtered out).
#
# Uses ProcessStartInfo to capture the raw stderr stream -- PowerShell 5.1
# mangles native stderr into truncated error records when you use 2>&1 or 2>.
#
# Usage: powershell -File shader_glslang_check.ps1 <file> <stage> [-ShowAll]
param(
    [Parameter(Mandatory)][string]$File,
    [Parameter(Mandatory)][ValidateSet('vertex','fragment')][string]$Stage,
    [switch]$ShowAll
)
$ErrorActionPreference = 'Continue'
$ndk = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64'

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "$ndk\glslc.exe"
$psi.Arguments = "--target-env=opengl -fshader-stage=$Stage `"$File`" -o `"$env:TEMP\_chk.spv`""
$psi.RedirectStandardError = $true
$psi.RedirectStandardOutput = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($psi)
$err = $p.StandardError.ReadToEnd()
$null = $p.StandardOutput.ReadToEnd()
$p.WaitForExit()

$all = @(($err -split "`r?`n") | Where-Object { $_ -match '\S' })
$real = @($all | Where-Object {
    $_ -match 'error:' -and $_ -notmatch 'non-opaque' -and $_ -notmatch 'SPIR-V' -and
    $_ -notmatch 'requires location' -and $_ -notmatch 'uniform/buffer blocks require' -and
    $_ -notmatch 'binding=X'
})

Write-Host ("file   : " + $File)
Write-Host ("stage  : " + $Stage)
Write-Host ("all    : " + $all.Count + " glslang message lines")
Write-Host ("REAL   : " + $real.Count + " GLSL ES errors")
Write-Host ''
if ($real.Count -gt 0) {
    Write-Host '--- real errors (first 60) ---'
    $real | Select-Object -First 60 | ForEach-Object { Write-Host ('  ' + $_) }
}
if ($ShowAll -and $all.Count -gt 0) {
    Write-Host ''
    Write-Host '--- all glslang lines (first 25) ---'
    $all | Select-Object -First 25 | ForEach-Object { Write-Host ('  ' + $_) }
}
