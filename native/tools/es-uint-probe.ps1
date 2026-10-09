# Probe GLSL ES 3.20 semantics for uint-vs-int-literal comparisons.
# ASCII only on purpose (PS 5.1 decodes as GBK on zh-CN).
#
# NOTE: glslc always emits SPIR-V, so non-opaque uniforms MUST carry
# layout(location=N) or glslc errors out before doing semantic checks.
# We add those locations so the real ES type checking runs.

$ErrorActionPreference = 'Continue'
$glslc = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe'
$dir   = Join-Path $PSScriptRoot '.cache\es_uint'
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$decl = @'
layout(location = 0) uniform uint p;
layout(location = 1) uniform uint M;
layout(location = 2) uniform int  q;
layout(location = 3) uniform uvec2 v;
layout(location = 0) out vec4 c;
'@

# name => body of main()
$cases = [ordered]@{
  't01_uint_ne_int0'     = '  bool b = (p & M) != 0;'
  't02_uint_ne_uint0'    = '  bool b = (p & M) != 0u;'
  't03_uint_eq_int0'     = '  bool b = (p & M) == 0;'
  't04_uint_eq_uint0'    = '  bool b = (p & M) == 0u;'
  't05_uint_gt_int0'     = '  bool b = p > 0;'
  't06_uint_gt_uint0'    = '  bool b = p > 0u;'
  't07_uint_lt_int1'     = '  bool b = p < 1;'
  't08_uint_lt_uint1'    = '  bool b = p < 1u;'
  't09_uint_eq_int1'     = '  bool b = p == 1;'
  't10_uint_eq_uint1'    = '  bool b = p == 1u;'
  't11_uint_ne_int1'     = '  bool b = p != 1;'
  't12_uint_ne_uint1'    = '  bool b = p != 1u;'
  't13_uint_eq_int2'     = '  bool b = p == 2;'
  't14_uint_and_int0'    = '  uint  b = p & 0;'
  't15_uint_and_uint0'   = '  uint  b = p & 0u;'
  't16_int_ge_int0'      = '  bool  b = q >= 0;'
  't17_uint_ge_uint0'    = '  bool  b = p >= 0u;'
  't18_uvec2_ne_ivec2_0' = '  bool b = (v != ivec2(0, 0)).x;'
  't19_uvec2_ne_uvec2_0' = '  bool b = (v != uvec2(0u, 0u)).x;'
  't20_uint_eq_neg1'     = '  bool b = p == -1;'
  't21_uint_eq_uintcast' = '  bool b = p == uint(-1);'
  't22_uint_eq_intvar'   = '  bool b = p == q;'
  't23_uint_eq_uintvar'  = '  bool b = p == M;'
  't24_uint_add_int0'    = '  uint  b = p + 0;'
  't25_uint_add_uint0'   = '  uint  b = p + 0u;'
  't26_fw_pattern_as_is' = '  bool b = (p & M) != 0; bool d = (p & M) == 0;'
  't27_fw_pattern_fixed' = '  bool b = (p & M) != 0u; bool d = (p & M) == 0u;'
}

$results = @()
foreach ($k in $cases.Keys) {
  $src = "#version 320 es`nprecision highp float;`nprecision highp int;`n$decl`nvoid main() {`n$($cases[$k])`n  c = vec4(b ? 1.0 : 0.0);`n}`n"
  $f   = Join-Path $dir "$k.frag"
  [System.IO.File]::WriteAllText($f, $src, (New-Object System.Text.UTF8Encoding($false)))

  $out = (& $glslc --target-env=opengl -fshader-stage=fragment $f -o (Join-Path $dir "$k.spv") 2>&1 | ForEach-Object { "$_" }) -join "`n"
  $code = $LASTEXITCODE
  [System.IO.File]::WriteAllText((Join-Path $dir "$k.log"), $out, (New-Object System.Text.UTF8Encoding($false)))

  # Drop SPIR-V-harness noise only; keep genuine ES type errors.
  $real = ($out -split "`r?`n") | Where-Object {
      $_ -match 'error' -and
      $_ -notmatch 'non-opaque uniform' -and
      $_ -notmatch 'SPIR-V' -and
      $_ -notmatch 'layout\(location' -and
      $_ -notmatch 'not allowed when generating' -and
      $_ -notmatch 'requires layout'
  }
  $firstErr = ($real | Select-Object -First 1)
  if (-not $firstErr) { $firstErr = '' }

  # Verdict is based on real errors, not glslc exit code (exit is polluted
  # by the SPIR-V harness requirements).
  $verdict = if ($real.Count -eq 0) { 'OK  (legal)' } else { 'ERR (illegal)' }

  $results += [pscustomobject]@{
    case        = $k
    verdict     = $verdict
    first_error = ($firstErr -replace '^.*?error:\s*', '').Trim()
  }
}

Write-Output ''
foreach ($r in $results) {
  Write-Output ("{0,-22} {1,-14} {2}" -f $r.case, $r.verdict, $r.first_error)
}
Write-Output ''
Write-Output '=== illegal cases ==='
($results | Where-Object { $_.verdict -like 'ERR*' } | ForEach-Object { '  ' + $_.case }) -join "`n"
