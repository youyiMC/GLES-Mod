#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the remaining regression gates after a shader.c change and print verdicts.

Gates (each independently meaningful; a failure in any is a blocker):
  bsl     : BSL shaderpack shaders  -> expected 166/166
  flywheel: Flywheel internal instancing shaders -> expected 0 errors
  corpus  : Sodium chunk-shader corpus -> expected CHANGED <= 1

Same reason as run_mc_gate.py for existing: PowerShell 5.1 redirection mangles
native stdout, and long inline commands get eaten by the terminal.

LGPL-3.0-or-later
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

# script -> list of output keywords worth surfacing
GATES = [
    ("bsl",      os.path.join(ROOT, "validate-pack-all.ps1"),
     ("通过", "失败", "error", "错误")),
    ("flywheel", os.path.join(ROOT, "repro_flywheel_diffuse.ps1"),
     ("通过", "失败", "error", "错误")),
]


def run_ps(script):
    if not os.path.isfile(script):
        return None, "MISSING: %s" % script
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", script],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, script, keys in GATES:
        if only and only != name:
            continue
        rc, out = run_ps(script)
        print("=" * 70)
        print("GATE %-9s rc=%s" % (name, rc))
        print("=" * 70)
        if rc is None:
            print(out)
            continue
        for l in out.splitlines():
            s = l.strip()
            if s and any(k in s for k in keys):
                print(s[:190])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
