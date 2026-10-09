#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search the Copilot chat transcript (JSONL) for a literal string and print
surrounding context.  Self-locating: scans the newest transcript file.
"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

needle = os.environ.get("NEEDLE", "only supports")
limit = int(os.environ.get("LIMIT", "40"))

base = os.path.expanduser(
    r"~\AppData\Roaming\Code\User\workspaceStorage"
)
files = glob.glob(os.path.join(base, "*", "GitHub.copilot-chat",
                              "transcripts", "*.jsonl"))
if not files:
    print("no transcripts found")
    sys.exit(1)
files.sort(key=os.path.getmtime, reverse=True)
print("transcripts:", len(files))
for f in files[:3]:
    print("  ", os.path.getmtime(f), f)
target = files[0]
print("using:", target)
print()

n = 0
for ln, line in enumerate(open(target, encoding="utf-8", errors="replace"), 1):
    if needle not in line:
        continue
    n += 1
    # find all occurrences within the raw line
    start = 0
    while True:
        i = line.find(needle, start)
        if i < 0 or n > limit:
            break
        lo = max(0, i - 400)
        hi = min(len(line), i + len(needle) + 500)
        print("-" * 72)
        print("line %d  (occ at %d)" % (ln, i))
        print(line[lo:hi].replace("\\n", "\n"))
        start = i + 1
    if n > limit:
        print("(truncated)")
        break
print()
print("total matching lines:", n)
