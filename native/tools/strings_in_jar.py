#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract printable strings from a class inside a jar, around a keyword.

Usage:
    py native\\tools\\strings_in_jar.py --jar <jar> --class <name> --around "only supports"
"""
import argparse
import glob
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", required=True)
    ap.add_argument("--class", dest="cls", default="")
    ap.add_argument("--around", default="")
    ap.add_argument("--window", type=int, default=6)
    args = ap.parse_args()

    path = args.jar
    if not os.path.isfile(path):
        hits = glob.glob(os.path.expanduser(path), recursive=True)
        if not hits:
            print("jar not found:", path)
            return 1
        path = hits[0]

    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if n.endswith(".class") and (args.cls in n if args.cls else True)]
        for n in names:
            data = z.read(n)
            # printable ASCII runs >= 4
            strs = re.findall(rb"[\x20-\x7e]{4,}", data)
            strs = [s.decode("ascii", "replace") for s in strs]
            if args.around:
                idx = [i for i, s in enumerate(strs) if args.around in s]
                if not idx:
                    continue
                lo = max(0, min(idx) - args.window)
                hi = min(len(strs), max(idx) + args.window + 1)
                print("=" * 70)
                print("CLASS:", n)
                print("=" * 70)
                for i in range(lo, hi):
                    mark = "  <<<" if i in idx else ""
                    print("%4d| %s%s" % (i, strs[i], mark))
            else:
                print("=" * 70)
                print("CLASS:", n, "(%d strings)" % len(strs))
                print("=" * 70)
                for i, s in enumerate(strs):
                    print("%4d| %s" % (i, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
