# build-native.ps1 -- cross-compile the native GLES backend (Windows)
#
# Usage:
#   .\native\build-native.ps1                     # build arm64-v8a (default)
#   .\native\build-native.ps1 -Abi armeabi-v7a    # build 32-bit ARM
#   .\native\build-native.ps1 -CheckSymbols       # also verify symbol coverage
#   .\native\build-native.ps1 -Clean              # wipe build dir first
#
# Note: this script is intentionally ASCII-only. Windows PowerShell 5.1 reads
# .ps1 files using the system ANSI codepage (GBK on zh-CN systems), so non-ASCII
# characters in this file would be mis-decoded and break parsing.
#
# The native layer builds independently of Gradle on purpose: editing C code
# should not trigger NeoForge's Minecraft decompile pipeline (tens of seconds).
#
# LGPL-3.0-or-later

param(
    [string]$Abi = "arm64-v8a",
    [string]$Platform = "android-26",
    [switch]$CheckSymbols,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

# ---- Locate NDK -------------------------------------------------------
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME }
           elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT }
           else { "C:\Android\Sdk" }

$ndkDir = Join-Path $sdkRoot "ndk"
if (-not (Test-Path $ndkDir)) {
    throw "NDK not found. Install with: sdkmanager 'ndk;27.2.12479018'"
}
$ndkVer = (Get-ChildItem $ndkDir -Directory | Select-Object -First 1).Name
$ndk = Join-Path $ndkDir $ndkVer
$toolchain = Join-Path $ndk "build\cmake\android.toolchain.cmake"
if (-not (Test-Path $toolchain)) {
    throw "Toolchain file not found: $toolchain"
}

$cmakeBinDir = Join-Path $sdkRoot "cmake\3.22.1\bin"
$cmake = Join-Path $cmakeBinDir "cmake.exe"
if (-not (Test-Path $cmake)) { $cmake = "cmake" }
$ninja = Join-Path $cmakeBinDir "ninja.exe"

Write-Host "NDK      : $ndkVer"
Write-Host "ABI      : $Abi"
Write-Host "Platform : $Platform"
Write-Host ""

# ---- Paths ------------------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $scriptDir "build\$Abi"
$outDir = Join-Path (Split-Path -Parent $scriptDir) "build\native\$Abi"

if ($Clean -and (Test-Path $buildDir)) {
    Remove-Item $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# ---- Configure --------------------------------------------------------
$cfgArgs = @(
    "-S", $scriptDir,
    "-B", $buildDir,
    "-G", "Ninja",
    "-DCMAKE_TOOLCHAIN_FILE=$toolchain",
    "-DANDROID_ABI=$Abi",
    "-DANDROID_PLATFORM=$Platform",
    "-DCMAKE_BUILD_TYPE=Release"
)
if (Test-Path $ninja) { $cfgArgs += "-DCMAKE_MAKE_PROGRAM=$ninja" }

Write-Host "=== configure ==="
& $cmake @cfgArgs
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed (exit $LASTEXITCODE)" }

# ---- Build ------------------------------------------------------------
Write-Host ""
Write-Host "=== build ==="
& $cmake --build $buildDir --parallel
if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE)" }

# ---- Collect artifact -------------------------------------------------
$so = Join-Path $buildDir "libgl_gles.so"
if (-not (Test-Path $so)) { throw "libgl_gles.so was not produced" }

Copy-Item $so (Join-Path $outDir "libgl_gles.so") -Force
$sizeKb = [math]::Round((Get-Item $so).Length / 1KB, 1)
Write-Host ""
Write-Host "artifact: $outDir\libgl_gles.so ($sizeKb KB)"

# ---- Symbol coverage --------------------------------------------------
if ($CheckSymbols) {
    Write-Host ""
    Write-Host "=== symbol coverage ==="
    $checker = Join-Path $scriptDir "tools\check_symbols.py"
    $def = Join-Path $scriptDir "symbols.def"
    if (Test-Path $checker) {
        py $checker --lib $so --def $def
    } else {
        Write-Host "(check_symbols.py not found, skipped)"
    }
}

Write-Host ""
Write-Host "Done. Copy libgl_gles.so into the FCL plugin APK jniLibs directory."
