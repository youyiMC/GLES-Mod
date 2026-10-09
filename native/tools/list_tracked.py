#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""list_tracked.py -- 列出 git 实际会纳入的文件（按目录分组）。"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def main():
    names = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        if rel == ".":
            rel = ""
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            names.append(os.path.join(rel, fn) if rel else fn)

    tmp = tempfile.mkdtemp(prefix="tracked-")
    try:
        shutil.copyfile(os.path.join(ROOT, ".gitignore"),
                        os.path.join(tmp, ".gitignore"))
        subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True)
        for p in names:
            full = os.path.join(tmp, p)
            try:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                if not os.path.exists(full):
                    open(full, "w").close()
            except OSError:
                pass
        r = subprocess.run(["git", "add", "--dry-run", "--all", "."],
                           cwd=tmp, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        tracked = sorted(m.group(1).replace("/", os.sep)
                         for m in (re.match(r"^add '(.+)'$", l.strip())
                                   for l in r.stdout.splitlines()) if m)
        print("共 %d 个文件\n" % len(tracked))
        cur = None
        for p in tracked:
            d = os.path.dirname(p)
            if d != cur:
                print("[%s]" % (d if d else "(根)"))
                cur = d
            print("   %s" % os.path.basename(p))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
