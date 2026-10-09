# run_shader_tests.ps1 -- build and run the host-side GLSL conversion tests
#
# Why this exists:
#   The shader converter (native/src/shader.c) turns desktop GLSL into GLSL ES.
#   When it is wrong, Minecraft fails to start with a driver compile error that
#   looks nothing like a converter bug. Reproducing that required installing the
#   plugin on a phone and reading crash logs - a slow loop.
#
#   shader.c has no dependency on Android or on the GL backend, so it can be
#   compiled and exercised on the host in under a second. This script wires that
#   up so regressions are caught before any device test.
#
# Requires a host C compiler on PATH (gcc / clang). Skips cleanly if absent.
#
# ASCII-only on purpose: Windows PowerShell 5.1 decodes .ps1 using the system
# ANSI codepage (GBK on zh-CN), so non-ASCII source would break parsing.
#
# LGPL-3.0-or-later

$ErrorActionPreference = "Stop"

# This script lives at <repo>/native/tools/run_shader_tests.ps1, so the repo
# root is two levels above the script directory.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$tools = $scriptDir
$src = Join-Path $root "native\src"
$inc = Join-Path $root "native\include"

$cc = $null
foreach ($cand in @("gcc", "clang")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) { $cc = $cmd.Source; break }
}
if (-not $cc) {
    Write-Host "  no host C compiler (gcc/clang) found - shader tests skipped"
    exit 0
}

$outDir = Join-Path $tools ".cache"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$exe = Join-Path $outDir "test_shader.exe"

Write-Host "  compiler : $cc"
& $cc -std=c11 -O1 -Wall -I $inc -I $src `
    -o $exe (Join-Path $tools "test_shader_convert.c") (Join-Path $src "shader.c") -lm
if ($LASTEXITCODE -ne 0) { throw "shader test build failed" }

& $exe
if ($LASTEXITCODE -ne 0) { throw "shader tests failed" }
