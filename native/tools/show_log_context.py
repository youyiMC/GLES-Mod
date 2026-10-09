#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""show_log_context.py -- print raw context around given line numbers.

Used to verify that the texture-rejection probe is attributing errors
correctly (i.e. that the pre-call drain is working and the reported parameters
really do belong to the failing call).

Usage:  py native/tools/show_log_context.py 94940 94962
        py native/tools/show_log_context.py --tail 40

LGPL-3.0-or-later
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LOG = ROOT / "native.log"


def main() -> int:
    if not LOG.exists():
        print(f"missing: {LOG}", file=sys.stderr)
        return 2
    lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()

    args = sys.argv[1:]
    if not args:
        print("usage: show_log_context.py <start> <end> | --tail N", file=sys.stderr)
        return 2

    if args[0] == "--tail":
        n = int(args[1]) if len(args) > 1 else 40
        start, end = max(1, len(lines) - n + 1), len(lines)
    else:
        start = int(args[0])
        end = int(args[1]) if len(args) > 1 else start

    print(f"native.log total lines: {len(lines)}")
    print(f"showing {start}..{end}")
    print("-" * 78)
    for i in range(start, min(end, len(lines)) + 1):
        print(f"{i}: {lines[i-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
