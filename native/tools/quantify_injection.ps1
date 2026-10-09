# Quantify the global-initializer injection: how many sites, how many bytes.
# ASCII only (PS 5.1 reads .ps1 as GBK on zh-CN).

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cache = Join-Path $scriptDir '.cache'

$raw = $args[0]
$conv = $args[1]

$rawLines  = Get-Content $raw
$convLines = Get-Content $conv

# The injected assignment has the shape "<indent>NAME = <expr>;" where NAME
# is a global that was declared WITHOUT an initializer in the raw source.
# Find globals declared without initializer = "TYPE NAME;" at column 0.
$noInit = @()
foreach ($l in $rawLines) {
    if ($l -match '^[A-Za-z_][A-Za-z0-9_]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*;\s*$') {
        $noInit += $matches[1]
    }
}
Write-Host ('globals declared without initializer in RAW: ' + $noInit.Count)
foreach ($n in $noInit) { Write-Host ('   ' + $n) }
Write-Host ''

# Count injection occurrences in the converted source.
Write-Host '=== injection sites per rewritten global ==='
$totalInjectedBytes = 0
foreach ($n in $noInit) {
    # match "<whitespace><name> = ..." as a full statement line
    $hits = @($convLines | Where-Object { $_ -match ('^\s+' + [regex]::Escape($n) + '\s*=') })
    if ($hits.Count -gt 0) {
        $bytes = ($hits | Measure-Object -Property Length -Sum).Sum
        $totalInjectedBytes += $bytes
        $ex = $hits[0].Trim()
        if ($ex.Length -gt 72) { $ex = $ex.Substring(0, 72) + '...' }
        Write-Host ('  x{0,-4} {1,-28} {2,7} bytes   e.g. {3}' -f `
                    $hits.Count, $n, $bytes, $ex)
    }
}

$inBytes  = (Get-Item $raw).Length
$outBytes = (Get-Item $conv).Length

Write-Host ''
Write-Host '=== totals ==='
Write-Host ('  input bytes                : ' + $inBytes)
Write-Host ('  output bytes               : ' + $outBytes)
Write-Host ('  growth                     : ' + [Math]::Round($outBytes / $inBytes, 2) + 'x')
Write-Host ('  bytes attributable to      : ' + $totalInjectedBytes)
Write-Host ('    global-init injection      ' + [Math]::Round(100.0 * $totalInjectedBytes / $outBytes, 1) + '% of output')
Write-Host ''
Write-Host ('  output WITHOUT that        : ~' + [Math]::Round(100.0 * ($outBytes - $totalInjectedBytes) / $inBytes, 2) + 'x input')
