# Re-convert the extracted Flywheel assembly shaders with the CURRENT
# converter and check the output with real glslang.
# ASCII-only.
$ErrorActionPreference = 'Continue'
$root = 'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1'
Set-Location $root
$cli = 'native\tools\.cache\convert_shader_cli.exe'
$dir = 'native\tools\.cache\fw_dumps'

foreach ($case in @(
    @{ n = '04_raw';  stage = 'vertex'   },
    @{ n = '06_raw';  stage = 'fragment' }
)) {
    $src = Join-Path $dir ($case.n + '.vert')
    if ($case.stage -eq 'fragment') { $src = Join-Path $dir ($case.n + '.frag') }
    $out = Join-Path $dir ($case.n + '.reconv.' + $(if ($case.stage -eq 'vertex') { 'vert' } else { 'frag' }))
    Write-Host ('=' * 74)
    Write-Host ('  ' + $case.n + '  (' + $case.stage + ')')
    Write-Host ('=' * 74)
    & $cli $src $case.stage $out
    if (-not (Test-Path $out)) { Write-Host '  converter produced no output'; continue }
    Write-Host ('  converted -> ' + $out)
    Write-Host ''
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'native\tools\glslang_report.py') $out $case.stage
}
