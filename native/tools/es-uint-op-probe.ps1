# Probe GLSL ES 3.20: exactly which uint-scalar / int-literal operator
# combinations are illegal. Determines the minimal safe fix surface.
# ASCII only (PS 5.1 decodes as GBK on zh-CN).
$ErrorActionPreference = 'Continue'
$glslc = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe'
$dir   = Join-Path $PSScriptRoot '.cache\es_uint2'
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$decl = @'
layout(location = 0) uniform uint p;
layout(location = 1) uniform uint M;
layout(location = 2) uniform int  q;
layout(location = 0) out vec4 c;
'@

$ops = @('!=', '==', '>', '<', '>=', '<=', '&', '|', '^', '>>', '<<', '+', '-', '*', '/', '%')
$results = @()
foreach ($op in $ops) {
  foreach ($rhs in @('0', '1', '0u')) {
    $key = "op_$($op -replace '[^A-Za-z0-9]', '_')_rhs_$rhs"
    $expr = if ($op -eq '<<' -or $op -eq '>>') { "  bool b = (p $op $rhs) == 0u;" } else { "  bool b = p $op $rhs;" }
    $src  = "#version 320 es`nprecision highp float;`nprecision highp int;`n$decl`nvoid main() {`n$expr`n  c = vec4(b ? 1.0 : 0.0);`n}`n"
    $f    = Join-Path $dir "$key.frag"
    [System.IO.File]::WriteAllText($f, $src, (New-Object System.Text.UTF8Encoding($false)))

    $out = (& $glslc --target-env=opengl -fshader-stage=fragment $f -o (Join-Path $dir "$key.spv") 2>&1 | ForEach-Object { "$_" }) -join "`n"
    $real = ($out -split "`r?`n") | Where-Object {
        $_ -match 'error' -and $_ -notmatch 'non-opaque uniform' -and
        $_ -notmatch 'SPIR-V' -and $_ -notmatch 'layout\(location' -and
        $_ -notmatch 'not allowed when generating' -and $_ -notmatch 'requires layout'
    }
    $verdict = if ($real.Count -eq 0) { 'LEGAL  ' } else { 'ILLEGAL' }
    $results += [pscustomobject]@{
      op = $op; rhs = $rhs; verdict = $verdict
      note = (($real | Select-Object -First 1) -replace '^.*?error:\s*', '').Trim()
    }
  }
}

Write-Output ''
Write-Output 'op   rhs  verdict'
foreach ($r in $results) {
  Write-Output ("{0,-4} {1,-4} {2}  {3}" -f $r.op, $r.rhs, $r.verdict, ($r.note.Substring(0, [Math]::Min(90, $r.note.Length))))
}
Write-Output ''
Write-Output '=== ILLEGAL combos only ==='
foreach ($r in $results | Where-Object { $_.verdict -eq 'ILLEGAL' }) {
  Write-Output ("  p {0} {1}" -f $r.op, $r.rhs)
}
