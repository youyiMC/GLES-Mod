"""Run glslc (glslang, the real GLSL ES front end from the Android NDK) on a
shader and report verbatim diagnostics.

Why Python and not the PowerShell wrapper: glslc always targets SPIR-V, so it
also emits Vulkan-only complaints we must filter out, AND PowerShell 5.1
mangles a native command's stderr into truncated error records. Python gives
us the raw bytes.

Usage:
    py native/tools/glslang_report.py <shader> <vertex|fragment> [--all]

LGPL-3.0-or-later
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

GLSLC = (r"C:\Android\Sdk\ndk\27.2.12479018\shader-tools"
         r"\windows-x86_64\glslc.exe")

# glslc emits these because it must produce SPIR-V; they are meaningless for
# an OpenGL/ES target and must not be counted as GLSL errors.
NOISE = (
    "requires location for user input/output",
    "requires location for user output",
    "non-opaque uniform",
    "non-opaque uniforms outside a block",
    "uniform/buffer blocks require layout(binding",
    "requires an explicit binding",
    "requires layout(binding",
    "for Vulkan",
)


def run(path, stage):
    spv = os.path.join(os.environ.get("TEMP", "."), "_glslang_report.spv")
    r = subprocess.run(
        [GLSLC, "--target-env=opengl", "-fshader-stage=" + stage, path,
         "-o", spv],
        capture_output=True)
    err = r.stderr.decode("utf-8", errors="replace")
    return r.returncode, err


def main():
    path = sys.argv[1]
    stage = sys.argv[2]
    show_all = "--all" in sys.argv

    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    print("file   : %s" % path)
    print("stage  : %s" % stage)
    print("lines  : %d" % len(lines))
    print()

    rc, err = run(path, stage)
    raw = [ln for ln in err.splitlines() if ln.strip()]

    real = []
    for ln in raw:
        low = ln.lower()
        if "error" not in low and "warning" not in low:
            continue
        # "N errors generated." is a summary, not a diagnostic
        if re.match(r"^\s*\d+\s+errors? generated\.?\s*$", ln):
            continue
        if any(n in ln for n in NOISE):
            continue
        real.append(ln)

    print("glslang emitted %d message lines, %d after SPIR-V-noise filtering"
          % (len(raw), len(real)))
    print("=" * 74)

    if show_all:
        print("--- verbatim ---")
        for ln in raw:
            print("  " + ln)
        print("=" * 74)
        return

    for ln in real:
        # Show the offending source line when the diagnostic carries a
        # file:line:col prefix.  Careful: a `#line 0 1` directive renumbers
        # the file, so map by scanning the #line markers ourselves.
        print("  " + ln)
        m = re.search(r"(?:^|\s)(\d+):(\d+):", ln)
        if m:
            n = int(m.group(1))
            shown = False
            seq = 0
            logical = 0
            for i, src in enumerate(lines):
                mm = re.match(r"#line\s+(\d+)\s+(\d+)", src)
                if mm:
                    logical = int(mm.group(1)) - 1
                    seq = i
                    continue
                seq += 1
                logical += 1
                if logical == n:
                    print("      seq L%d | %s" % (i + 1, src))
                    shown = True
                    break
            if not shown and 0 < n <= len(lines):
                print("      seq L%d | %s" % (n, lines[n - 1]))

    print("=" * 74)
    print("verdict: %s" % ("PASS (no real GLSL ES errors)"
                           if not real else "FAIL (%d)" % len(real)))


if __name__ == "__main__":
    main()
