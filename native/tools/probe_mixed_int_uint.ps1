# Probe mixed int/uint scalar binary operations.
#
# Two questions:
#   Q1 (semantics): what does DESKTOP GLSL actually do for `int OP uint`?
#       Answered by compiling desktop GLSL to SPIR-V and disassembling --
#       the inserted conversion instruction is visible in the SPIR-V.
#   Q2 (legality): which spellings are legal in GLSL ES 3.20, so the
#       converter can pick a form that compiles AND matches desktop.
#
# ASCII only on purpose (PS 5.1 decodes .ps1 as GBK on zh-CN).

$ErrorActionPreference = 'Continue'
$glslc = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\glslc.exe'
$dis   = 'C:\Android\Sdk\ndk\27.2.12479018\shader-tools\windows-x86_64\spirv-dis.exe'
$dir   = Join-Path $PSScriptRoot '.cache\mixed_iu'
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# ---------------------------------------------------------------- Q1
Write-Output '=== Q1: desktop GLSL semantics for `int OP uint` (from SPIR-V) ==='
Write-Output ''

$deskSrc = @'
#version 460
layout(location = 0) in vec3 aPos;
layout(location = 0) out vec4 c;
layout(location = 1) uniform int  i0;
layout(location = 2) uniform uint u0;
void main() {
    uint arith = i0 + u0;
    uint shift = i0 << u0;
    bool cmp   = i0 < u0;
    c = vec4(float(arith) + float(shift) + (cmp ? 1.0 : 0.0));
    gl_Position = vec4(aPos, 1.0);
}
'@
$f = Join-Path $dir 'desk.vert'
$spv = Join-Path $dir 'desk.spv'
[System.IO.File]::WriteAllText($f, $deskSrc, (New-Object System.Text.UTF8Encoding($false)))

$o = (& $glslc --target-env=opengl -fshader-stage=vertex $f -o $spv 2>&1 | Out-String)
if ($LASTEXITCODE -eq 0) {
    $asmd = (& $dis $spv 2>&1 | Out-String)
    Write-Output '--- instructions mentioning IAdd / UConvert / Bitcast / ULessThan ---'
    ($asmd -split "`r?`n") |
        Where-Object { $_ -match 'OpI(Add|Sub|Mul|ShiftLeft|Bitwise)' -or
                       $_ -match 'UConvert|Bitcast|SConvert' -or
                       $_ -match 'OpULessThan|OpSLessThan' } |
        ForEach-Object { Write-Output ('  ' + $_.Trim()) }
    Write-Output ''
    Write-Output '--- the three result assignments ---'
    ($asmd -split "`r?`n") |
        Where-Object { $_ -match '%arith =' -or $_ -match '%shift =' -or $_ -match '%cmp =' } |
        ForEach-Object { Write-Output ('  ' + $_.Trim()) }
} else {
    Write-Output ("  desktop compile failed: " + $o)
}

# ---------------------------------------------------------------- Q2
Write-Output ''
Write-Output '=== Q2: GLSL ES 3.20 legality matrix ==='
Write-Output ''

$decl = "layout(location=0) in vec3 aPos;`n" +
        "layout(location=0) out vec4 c;`n" +
        "layout(location=1) uniform int  i0;`n" +
        "layout(location=2) uniform uint u0;`n"

function Test-Es([string]$body) {
    $src = "#version 320 es`nprecision highp float;`nprecision highp int;`n" +
           $decl + "void main() {`n  " + $body + "`n  c = vec4(1.0);`n  gl_Position = vec4(aPos,1.0);`n}`n"
    $tf = Join-Path $dir 't.vert'
    [System.IO.File]::WriteAllText($tf, $src, (New-Object System.Text.UTF8Encoding($false)))
    $res = (& $glslc --target-env=opengl -fshader-stage=vertex $tf -o (Join-Path $dir 't.spv') 2>&1 | Out-String)
    $real = @(($res -split "`r?`n") | Where-Object {
        $_ -match 'error:' -and $_ -notmatch 'non-opaque' -and
        $_ -notmatch 'SPIR-V' -and $_ -notmatch 'location\(L\)' })
    if ($real.Count -eq 0) { return 'LEGAL  ' }
    return 'ILLEGAL'
}

$ops      = @('+','-','*','/','%','&','|','^','<<','>>')
$cmpOps   = @('<','>','<=','>=','==','!=')

Write-Output '--- mixed arithmetic / bitwise / shift (result uint) ---'
Write-Output ('{0,-5} {1,-16} {2,-16} {3,-16} {4}' -f 'op','int OP uint','uint OP int','uint(int) OP uint','uint OP uint(int)')
foreach ($op in $ops) {
    $a = Test-Es ("uint r = i0 $op u0;")
    $b = Test-Es ("uint r = u0 $op i0;")
    $c = Test-Es ("uint r = uint(i0) $op u0;")
    $d = Test-Es ("uint r = u0 $op uint(i0);")
    Write-Output ('{0,-5} {1,-16} {2,-16} {3,-16} {4}' -f $op, $a, $b, $c, $d)
}

Write-Output ''
Write-Output '--- mixed comparisons (result bool) ---'
Write-Output ('{0,-5} {1,-16} {2,-16} {3,-16} {4}' -f 'op','int OP uint','uint OP int','uint(int) OP uint','uint OP uint(int)')
foreach ($op in $cmpOps) {
    $a = Test-Es ("bool r = i0 $op u0;")
    $b = Test-Es ("bool r = u0 $op i0;")
    $c = Test-Es ("bool r = uint(i0) $op u0;")
    $d = Test-Es ("bool r = u0 $op uint(i0);")
    Write-Output ('{0,-5} {1,-16} {2,-16} {3,-16} {4}' -f $op, $a, $b, $c, $d)
}

Write-Output ''
Write-Output '--- the alt form: convert BOTH to int ---'
foreach ($op in @('+','-','<','==')) {
    $a = Test-Es ("uint r = uint(int(i0) $op int(u0));")
    $b = Test-Es ("bool r = int(i0) $op int(u0);")
    Write-Output ('{0,-5} both-int->uint: {1}    both-int cmp: {2}' -f $op, $a, $b)
}
