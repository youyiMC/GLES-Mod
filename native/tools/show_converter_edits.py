"""Show every semantic change the converter makes to a shader.

Compares the RAW source (what the driver was handed before us, i.e. what
Flywheel/Iris produced) against the RE-CONVERTED output from the current
converter, ignoring pure formatting additions.

Usage: py native/tools/show_converter_edits.py <raw> <converted>
"""
import difflib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")


def norm(lines):
    """Drop lines we add purely for the ES target so they don't drown the diff."""
    out = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("#version"):
            continue
        if s.startswith("precision "):
            continue
        if s.startswith("// glesmod:"):
            continue
        out.append(ln)
    return out


a = norm(open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines())
b = norm(open(sys.argv[2], encoding="utf-8", errors="replace").read().splitlines())

n = 0
for line in difflib.unified_diff(a, b, "RAW", "CONVERTED", lineterm="", n=0):
    if line.startswith(("---", "+++", "@@")):
        continue
    if line.startswith(("+", "-")):
        n += 1
        print(line)
print()
print("=== %d changed lines ===" % n)
