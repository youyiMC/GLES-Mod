#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple multi-file regex log grepper (avoids PowerShell quoting hell).

Usage:
    py native\\tools\\grep_log.py --pattern "MultiDraw|BaseVertex" --log "native(12).log" --log latest.log [--tail 30]
"""
import argparse
import glob
import os
import re
import sys


def collect_logs(patterns):
    """Expand glob patterns (handles names with parentheses that a shell
    would otherwise mangle)."""
    out = []
    for p in patterns:
        matched = sorted(glob.glob(p))
        if matched:
            out.extend(matched)
        elif os.path.isfile(p):
            out.append(p)
        else:
            out.append(p)  # keep so the caller can report "not found"
    # de-dup, preserve order
    seen = set()
    uniq = []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", required=True, help="regex to search for")
    ap.add_argument("--log", action="append", default=[],
                    help="log file or glob (repeatable)")
    ap.add_argument("--logglob", default="*.log",
                    help="glob used when --log is not given (default: *.log)")
    ap.add_argument("--tail", type=int, default=0, help="only show last N matches (0 = all)")
    ap.add_argument("--encoding", default="utf-8")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    pat = re.compile(args.pattern)
    files = collect_logs(args.log if args.log else [args.logglob])
    hits = []
    for fn in files:
        try:
            with open(fn, "r", encoding=args.encoding, errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if pat.search(line):
                        hits.append(f"{fn}:{i}: {line.rstrip()}")
        except FileNotFoundError:
            hits.append(f"!! {fn}: not found")

    if args.tail and len(hits) > args.tail:
        hits = hits[-args.tail:]
    for h in hits:
        print(h)
    print(f"--- {len(hits)} match(es) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
