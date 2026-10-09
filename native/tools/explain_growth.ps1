# Convert one shader and report structural growth, to explain why output
# bytes are ~3x input. ASCII only (PS 5.1 reads .ps1 as GBK on zh-CN).

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$exe = Join-Path $scriptDir '.cache\bench_convert.exe'

$src = Join-Path $root $args[0]
$outFile = Join-Path $scriptDir '.cache\growth_out.txt'

# bench_convert writes nothing; reuse it only for timing. Use the CLI instead.
$cli = Join-Path $scriptDir '.cache\convert_shader_cli.exe'
if (-not (Test-Path $cli)) {
    $gcc = 'C:\msys64\ucrt64\bin\gcc.exe'
    & $gcc -O2 -std=c11 -w -I (Join-Path $root 'native\src') -I (Join-Path $root 'native\include') `
        -o $cli (Join-Path $scriptDir 'convert_shader_cli.c') (Join-Path $root 'native\src\shader.c') -lm
    if ($LASTEXITCODE -ne 0) { throw 'cli build failed' }
}

& $cli $src fragment $outFile
if ($LASTEXITCODE -ne 0) { throw 'convert failed' }

$inBytes = (Get-Item $src).Length
$outBytes = (Get-Item $outFile).Length
$inLines = @(Get-Content $src).Count
$outLines = @(Get-Content $outFile).Count

Write-Host ''
Write-Host ('input : ' + $inBytes + ' bytes, ' + $inLines + ' lines')
Write-Host ('output: ' + $outBytes + ' bytes, ' + $outLines + ' lines')
Write-Host ('growth: ' + [Math]::Round($outBytes / $inBytes, 2) + 'x bytes, ' +
            [Math]::Round($outLines / [Math]::Max(1,$inLines), 2) + 'x lines')
Write-Host ''

# Which single line appears most often in the output?
Write-Host '=== top 12 most-repeated output lines ==='
Get-Content $outFile |
    Where-Object { $_.Trim().Length -gt 0 } |
    Group-Object |
    Sort-Object Count -Descending |
    Select-Object -First 12 |
    ForEach-Object {
        $t = $_.Name.Trim()
        if ($t.Length -gt 96) { $t = $t.Substring(0, 96) + '...' }
        Write-Host ('  x{0,-5} {1}' -f $_.Count, $t)
    }
