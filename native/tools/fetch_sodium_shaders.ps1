# Download Sodium 0.8.13's shader sources for local glslang reproduction.
# ASCII-only (PS 5.1 reads .ps1 as GBK on zh-CN).
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$out = Join-Path $env:TEMP 'sodiumvsh'
New-Item -ItemType Directory -Force -Path $out | Out-Null

# Try several refs: the 0.8.13 tag, and the 1.21.1 branch names.
$refs = @('0.8.13', 'mc1.21.1', '1.21.1')
$base = 'https://raw.githubusercontent.com/CaffeineMC/sodium'
$files = @(
    'common/src/main/resources/assets/sodium/shaders/blocks/block_layer_opaque.vsh',
    'common/src/main/resources/assets/sodium/shaders/blocks/block_layer_opaque.fsh',
    'common/src/main/resources/assets/sodium/shaders/include/chunk_vertex.glsl',
    'common/src/main/resources/assets/sodium/shaders/include/chunk_matrices.glsl',
    'common/src/main/resources/assets/sodium/shaders/include/globals.glsl',
    'common/src/main/resources/assets/sodium/shaders/include/fog.glsl',
    'common/src/main/resources/assets/sodium/shaders/include/chunk_material.glsl',
    'common/src/main/resources/assets/sodium/shaders/include/mc_fog.glsl'
)

$saved = 0
foreach ($ref in $refs) {
    Write-Output "===== ref: $ref ====="
    foreach ($f in $files) {
        $name = Split-Path $f -Leaf
        $dest = Join-Path $out $name
        if (Test-Path $dest) { continue }
        $url = "$base/$ref/$f"
        try {
            Invoke-WebRequest -Uri $url -OutFile $dest -TimeoutSec 20 -UseBasicParsing
            $len = (Get-Item $dest).Length
            Write-Output ("  OK   {0}  ({1} bytes)" -f $name, $len)
            $saved++
        } catch {
            Write-Output ("  fail {0}" -f $name)
        }
    }
}

Write-Output ""
Write-Output "saved: $saved"
Write-Output "dir  : $out"
Get-ChildItem $out -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output ("  {0}  {1}" -f $_.Name, $_.Length) }
