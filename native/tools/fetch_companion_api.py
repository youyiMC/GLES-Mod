#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Sable Companion's public API sources via the GitHub contents API.

raw.githubusercontent.com returns 502 here, but api.github.com works, so pull
the files through the API and print them.

These four files ARE the entire compatibility contract, so reading them is the
only way to know what "Sable compatibility" concretely means for us.

LGPL-3.0-or-later
"""
import base64
import io
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
# Scratch copy for REFERENCE only -- never vendored into the repo.
OUT = os.path.join(ROOT, "sable-companion-src")

API = ("https://api.github.com/repos/ryanhcode/sable-companion/contents/")

FILES = [
    "common/src/main/java/dev/ryanhcode/sable/companion/SableCompanion.java",
    "common/src/main/java/dev/ryanhcode/sable/companion/SubLevelAccess.java",
    "common/src/main/java/dev/ryanhcode/sable/companion/ClientSubLevelAccess.java",
    "common/src/main/java/dev/ryanhcode/sable/companion/impl/DefaultSableCompanion.java",
    "common/src/main/java/dev/ryanhcode/sable/companion/impl/SableCompanionUtil.java",
    "common/src/main/resources/META-INF/services/dev.ryanhcode.sable.companion.SableCompanion",
    "common/src/main/resources/META-INF/neoforge.mods.toml",
]


def get(path):
    req = urllib.request.Request(API + path,
                                 headers={"User-Agent": "glesmod",
                                          "Accept": "application/vnd.github+json"})
    d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    return base64.b64decode(d["content"]).decode("utf-8", "replace")


def main():
    os.makedirs(OUT, exist_ok=True)
    got = 0
    for p in FILES:
        leaf = p.split("/")[-1]
        try:
            txt = get(p)
        except Exception as e:
            print("  FETCH ERROR %-40s %s" % (leaf, e))
            continue
        dest = os.path.join(OUT, leaf)
        with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        n = len(txt.splitlines())
        print("  ok  %-42s %5d lines" % (leaf, n))
        got += 1
    print()
    print("written to %s  (%d/%d)" % (OUT, got, len(FILES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
