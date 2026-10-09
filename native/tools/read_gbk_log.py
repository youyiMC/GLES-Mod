# Read a GBK-encoded log safely and print the tail. ASCII-only wrapper.
# Usage: py native/tools/read_gbk_log.py <log> [lines]
import sys

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 60

raw = open(path, "rb").read()
text = raw.decode("gbk", errors="replace")
lines = text.splitlines()
print("total lines: %d" % len(lines))
print("=" * 70)
for ln in lines[-n:]:
    print(ln.rstrip())
