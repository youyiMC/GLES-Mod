"""Rebuild the converter CLI and re-verify the Flywheel assembly shaders.

Runs as a standalone script so it never depends on the (fragile) interactive
PowerShell session.

Usage: py native/tools/rebuild_and_verify_flywheel.py
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
GCC = r"C:\msys64\ucrt64\bin\gcc.exe"
CLI = os.path.join(HERE, ".cache", "convert_shader_cli.exe")
DUMPS = os.path.join(HERE, ".cache", "fw_dumps")

r = subprocess.run(
    [GCC, "-O2", "-std=c11", "-Wall", "-I", os.path.join(ROOT, "native", "src"),
     "-I", os.path.join(ROOT, "native", "include"),
     "-o", CLI, os.path.join(HERE, "convert_shader_cli.c"),
     os.path.join(ROOT, "native", "src", "shader.c"), "-lm"],
    capture_output=True, text=True, errors="replace")
if r.returncode != 0:
    print("BUILD FAILED")
    print(r.stdout, r.stderr)
    sys.exit(1)
warn = [l for l in (r.stderr or "").splitlines() if "warning:" in l]
print("build OK  (warnings: %d)" % len(warn))
for w in warn[:5]:
    print("   ", w.strip())

for name, stage, ext in (("04_raw", "vertex", "vert"),
                         ("06_raw", "fragment", "frag")):
    src = os.path.join(DUMPS, name + "." + ext)
    out = os.path.join(DUMPS, name + ".fixed." + ext)
    subprocess.run([CLI, src, stage, out], capture_output=True)
    n = subprocess.run([sys.executable, os.path.join(HERE, "glslang_report.py"),
                        out, stage],
                       capture_output=True).stdout.decode("utf-8", "replace")
    print("=" * 70)
    print(name, stage)
    for line in n.splitlines():
        if "REAL" in line or "verdict" in line:
            print("  " + line.strip())
    for line in n.splitlines():
        if "error:" in line:
            print("     " + line.strip()[:140])
