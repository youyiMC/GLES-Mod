# probe_converter.ps1 -- generic: run a fixture through the converter and glslang.
#   usage: probe_converter.ps1 <fixture> <vertex|fragment>
# ASCII-only (PowerShell 5.1 decodes .ps1 as GBK on zh-CN).
#
# LGPL-3.0-or-later

param(
    [Parameter(Mandatory = $true)][string]$Fixture,
    [Parameter(Mandatory = $true)][string]$Stage
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))

$T   = "native\tools\.cache\veil"
$CLI = Join-Path $T "cli.exe"
$GLS = "C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe"
$out = Join-Path $T ((Split-Path -Leaf $Fixture) + ".out")

if (-not (Test-Path $CLI)) { Write-Output "cli missing; run probe_userfn.ps1 first"; exit 1 }

& $CLI $Fixture $Stage $out
Write-Output "=== converted ==="
Get-Content $out
Write-Output ""
Write-Output "=== glsl ES verdict (SPIR-V noise filtered) ==="
& $GLS --target-env=opengl -fshader-stage=frag $out -o ($out + ".spv") 2>&1 |
    Select-String -SimpleMatch "error:" |
    Where-Object { $_.Line -notmatch "requires location" } |
    ForEach-Object { $_.Line.Trim() }
Write-Output "(nothing above == PASS)"
