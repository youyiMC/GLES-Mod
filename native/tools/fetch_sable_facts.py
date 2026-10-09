#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch the two upstream files that decide our constraints on Sable.

The web fetcher keeps failing on raw.githubusercontent.com, so use Python's
urllib and print only the lines that matter.

  1. sable_rapier/build.gradle   -> WHICH desktop platforms ship prebuilt natives
                                    (an Android target absent here is what makes
                                     Sable unrunnable on Android by itself)
  2. neoforge .../neoforge.mods.toml -> whether veil / sodium are REQUIRED deps

LGPL-3.0-or-later
"""
import base64
import json
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API = "https://api.github.com/repos/ryanhcode/sable/contents/"

FILES = [
    ("sable_rapier/build.gradle", "sable_rapier/build.gradle",
     [r"supportedTargets", r"triple:", r"^\s*(mac|linux|freebsd|windows)\(",
      r"android|aarch64"]),
    ("mods.toml",
     "neoforge/src/main/resources/META-INF/neoforge.mods.toml",
     [r"modId", r"type\s*=", r"versionRange", r"veil|sodium|flywheel"]),
]


def get(path):
    req = urllib.request.Request(API + path,
                                 headers={"User-Agent": "glesmod",
                                          "Accept": "application/vnd.github+json"})
    d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    return base64.b64decode(d["content"]).decode("utf-8", "replace")


def main():
    for label, path, pats in FILES:
        print("=" * 76)
        print(label)
        print("=" * 76)
        try:
            txt = get(path)
        except Exception as e:
            print("  FETCH ERROR: %s" % e)
            print()
            continue
        rx = [re.compile(p, re.I) for p in pats]
        for i, line in enumerate(txt.splitlines(), 1):
            if any(p.search(line) for p in rx):
                print("  %4d | %s" % (i, line.rstrip()[:130]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
