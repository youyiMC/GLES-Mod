# probe_userfn.ps1 -- rebuild the converter CLI and run the user-function
# signature probe. ASCII-only (PowerShell 5.1 decodes .ps1 as GBK on zh-CN).
#
# LGPL-3.0-or-later

$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))

$T   = "native\tools\.cache\veil"
$CLI = Join-Path $T "cli.exe"
$GLS = "C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"

& "C:\msys64\ucrt64\bin\gcc.exe" -O1 -std=c11 -o $CLI `
    "native\tools\convert_shader_cli.c" "native\src\shader.c" -I "native\include"
Write-Output ("gcc rc=" + $LASTEXITCODE)
if ($LASTEXITCODE -ne 0) { Write-Output "BUILD FAILED - stopping"; exit 1 }

$fx  = "native\tools\fixtures\probe_userfn_int_args.frag"
$out = Join-Path $T "userfn.out"
& $CLI $fx fragment $out

Write-Output ""
Write-Output "=== converted call sites ==="
Get-Content $out | Select-String -Pattern "c1\(|u1\(|v1\(|m1\(|m2\(|f1\(|b1\(" |
    ForEach-Object { $_.Line.Trim() }

Write-Output ""
Write-Output "=== glsl ES verdict (real errors only) ==="
& $GLS --target-env=opengl -fshader-stage=frag $out -o (Join-Path $T "userfn.spv") 2>&1 |
    Select-String -Pattern "error:" |
    Where-Object { $_ -notmatch "requires location" } |
    ForEach-Object { $_.Line.Trim() }

Write-Output "(nothing above == PASS)"
