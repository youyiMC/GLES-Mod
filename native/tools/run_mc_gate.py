#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the MC core shader gate and print a compact verdict.

Why a wrapper: PowerShell 5.1 redirection mangles native stdout (UTF-16 vs OEM
codepage), and the integrated terminal corrupts long inline heredocs. A tiny
script that captures subprocess output itself is the reliable path.

LGPL-3.0-or-later
"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

KEYS = ("通过", "失败", "PASS", "FAIL", "glslang", "总计", "total",
        "ok:", "OK:", "error", "错误")


def run(args):
    r = subprocess.run(args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    rc, out = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", "audit-mc-shaders.ps1"])
    print("=" * 70)
    print("audit-mc-shaders.ps1  rc=%d" % rc)
    print("=" * 70)
    for l in out.splitlines():
        s = l.strip()
        if not s:
            continue
        if any(k in s for k in KEYS):
            print(s[:190])
    return rc


if __name__ == "__main__":
    sys.exit(main())
