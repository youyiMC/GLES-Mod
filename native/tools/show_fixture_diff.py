# Exact unified diff between a fixture and its converted output.
# Usage: py native/tools/show_fixture_diff.py <fixture> <converted>
import sys
import difflib

a = open(sys.argv[1], encoding="utf-8").read().splitlines()
b = open(sys.argv[2], encoding="utf-8").read().splitlines()

n = 0
for line in difflib.unified_diff(a, b, "INPUT", "CONVERTED", lineterm="", n=1):
    if line.startswith(("---", "+++")):
        continue
    if line.startswith(("+", "-")):
        n += 1
    print(line)

print()
print("=== changed lines: %d ===" % n)
