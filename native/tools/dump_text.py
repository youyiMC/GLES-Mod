#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump a (possibly UTF-16) file as UTF-8 text, with optional head/tail.

Usage:
    py native\\tools\\dump_text.py --file build-v7-native.txt --head 120
"""
import argparse
import sys


def read_any(path):
    with open(path, "rb") as f:
        d = f.read()
    if d[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return d.decode("utf-16", errors="replace")
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return d.decode(enc)
        except UnicodeDecodeError:
            continue
    return d.decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--head", type=int, default=0)
    ap.add_argument("--tail", type=int, default=0)
    ap.add_argument("--grep", default="")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    text = read_any(args.file)
    lines = text.splitlines()
    if args.grep:
        lines = [l for l in lines if args.grep.lower() in l.lower()]
    if args.head:
        lines = lines[:args.head]
    if args.tail:
        lines = lines[-args.tail:]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
