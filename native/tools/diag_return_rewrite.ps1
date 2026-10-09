# Diagnostic: why is `return 0;` still rejected on device?
#
# Answers two independent questions with hard evidence:
#   [1] Is the new rule actually COMPILED INTO the shipped .so?
#       (baked-in marker strings are the proof, not timestamps)
#   [2] Does the converter actually rewrite `return 0;` -> `return 0.0;`
#       in the REAL device dump?
#       (prints every `return` line of the converted output)
#
# ASCII-only on purpose (PS 5.1 decodes .ps1 as GBK on zh-CN).
# LGPL-3.0-or-later

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path   # <root>\native\tools
$root = Split-Path -Parent (Split-Path -Parent $here)     # <root>
Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
Write-Host ("root = " + $root)

Write-Host '=============================================================='
Write-Host ' [1] is the new rule compiled into the shipped .so?'
Write-Host '=============================================================='
# The note strings passed to glesmod_degrade are string literals, so they end
# up in .rodata. Finding them proves the code path exists in the binary.
$markers = @(
    'return <int>',                 # (ascii marker if present)
    'wavelet'                       # sanity: unrelated
)
$soFiles = @(
    'build\native\arm64-v8a\libgl_gles.so',
    'build\native\armeabi-v7a\libgl_gles.so'
)
foreach ($so in $soFiles) {
    if (-not (Test-Path $so)) { Write-Host ("  MISSING: " + $so); continue }
    $bytes = [System.IO.File]::ReadAllBytes($so)
    # UTF-8 bytes of the Chinese note used by fix_return_int_in_float_fn
    $needle = [System.Text.Encoding]::UTF8.GetBytes(([char]0x6D6E + [char]0x70B9 + [char]0x8FD4 + [char]0x56DE))
    $found = $false
    for ($i = 0; $i -le $bytes.Length - $needle.Length; $i++) {
        if ($bytes[$i] -eq $needle[0]) {
            $ok = $true
            for ($j = 1; $j -lt $needle.Length; $j++) {
                if ($bytes[$i + $j] -ne $needle[$j]) { $ok = $false; break }
            }
            if ($ok) { $found = $true; break }
        }
    }
    $st = Get-Item $so
    Write-Host ("  {0}" -f $so)
    Write-Host ("      size={0}  mtime={1}" -f $st.Length, $st.LastWriteTime.ToString('MM-dd HH:mm:ss'))
    Write-Host ("      contains 'return int in float fn' note : {0}" -f $found)
}

Write-Host ''
Write-Host '=============================================================='
Write-Host ' [2] what does the converter do to the REAL device dump?'
Write-Host '=============================================================='
$cli = 'native\tools\.cache\convert_shader_cli.exe'
$dump = 'native\tools\.cache\fw_dumps\06_raw.frag'
if (-not (Test-Path $cli)) {
    # build it (shader.c needs the glesmod_degrade stub; the CLI provides it)
    & 'C:\msys64\ucrt64\bin\gcc.exe' -O2 -std=c11 -w `
        -I native\src -I native\include `
        -o $cli native\tools\convert_shader_cli.c native\src\shader.c -lm
}
if (-not (Test-Path $dump)) {
    Write-Host ("  dump not found: " + $dump)
    Write-Host '  (extract it first with native/tools/extract_native_dumps.py)'
} else {
    $out = 'native\tools\.cache\fw_dumps\06_check.frag'
    & $cli $dump 'fragment' $out
    Write-Host ("  converted -> " + $out)
    Write-Host ''
    Write-Host '  --- every `return` line in the CONVERTED output ---'
    $i = 0
    $n = 0
    foreach ($l in (Get-Content $out)) {
        $i++
        if ($l -match '\breturn\b') {
            $n++
            Write-Host ("    {0,5}| {1}" -f $i, $l.Trim())
        }
    }
    Write-Host ("    (total {0} return lines)" -f $n)
    Write-Host ''
    $txt = Get-Content $out -Raw
    Write-Host ("  contains 'return 0.0;'   : {0}" -f ($txt -match 'return 0\.0;'))
    Write-Host ("  contains bare 'return 0;' : {0}" -f ($txt -match 'return 0;'))
}

Write-Host ''
Write-Host '=============================================================='
