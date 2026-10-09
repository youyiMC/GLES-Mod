#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Search the project's OWN sources and build outputs (incl. jars) for literals.

Usage:  py native\\tools\\grep_own.py "only supports"
"""
import argparse
import glob
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")


def walk_files(roots):
    for r in roots:
        if os.path.isfile(r):
            yield r
            continue
        for root, _d, files in os.walk(r):
            if any(s in root for s in (".git", ".gradle", "node_modules", ".venv")):
                continue
            for f in files:
                yield os.path.join(root, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("needles", nargs="+")
    ap.add_argument("--roots", nargs="*", default=["src", "build", "fcl-plugin", "native"])
    args = ap.parse_args()

    needles = [n.encode("utf-8") for n in args.needles]
    print("roots:", args.roots)
    print("needles:", args.needles)

    for p in walk_files(args.roots):
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        if size > 40 * 1024 * 1024:
            continue
        if p.lower().endswith((".jar", ".zip", ".apk")):
            try:
                with zipfile.ZipFile(p) as z:
                    for n in z.namelist():
                        try:
                            data = z.read(n)
                        except Exception:
                            continue
                        for nd in needles:
                            if nd in data:
                                print("  HIT  %s :: %s   (%s)" % (p, n, nd.decode()))
            except Exception:
                pass
            continue

        try:
            data = open(p, "rb").read()
        except OSError:
            continue
        for nd in needles:
            if nd in data:
                print("  HIT  %s   (%s)" % (p, nd.decode()))


if __name__ == "__main__":
    main()
