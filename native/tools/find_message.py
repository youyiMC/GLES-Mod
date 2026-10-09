#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find which jar/class contains a given literal message.

Usage:  py native\\tools\\find_message.py "only supports"
        py native\\tools\\find_message.py "only supports" --scan-neoforge
"""
import argparse
import glob
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")


def jars_in_search_path(with_neoforge):
    pats = [r"build\libs\*.jar", r"build\classes\**\*"]
    if with_neoforge:
        pats += [
            os.path.expanduser(r"~\.gradle\caches\modules-2\files-2.1\net.neoforged\**\*.jar"),
            os.path.expanduser(r"~\.gradle\caches\modules-2\files-2.1\net.minecraftforge\**\*.jar"),
            os.path.expanduser(r"~\.gradle\caches\**\neoforge*.jar"),
        ]
    out = []
    for p in pats:
        out += glob.glob(p, recursive=True)
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("needle")
    ap.add_argument("--scan-neoforge", action="store_true")
    args = ap.parse_args()

    needle = args.needle.encode("utf-8")
    jars = jars_in_search_path(args.scan_neoforge)
    print("searching %d jars/dirs for %r" % (len(jars), args.needle))

    for p in jars:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if not f.endswith(".class"):
                        continue
                    fp = os.path.join(root, f)
                    try:
                        data = open(fp, "rb").read()
                    except OSError:
                        continue
                    if needle in data:
                        print("  HIT  %s" % fp)
            continue
        try:
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if not n.endswith(".class"):
                        continue
                    try:
                        data = z.read(n)
                    except Exception:
                        continue
                    if needle in data:
                        print("  HIT  %s :: %s" % (os.path.basename(p), n))
        except Exception:
            continue


if __name__ == "__main__":
    main()
