#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize launcher logs side by side, to answer questions that matter for
comparing launchers:

  * which launcher produced the log (--versionType)
  * is OUR native library demonstrably in the path?
  * what GL version string was reported
  * the residual GL debug-message inventory

Why this exists: I concluded "120 FPS is the hardware ceiling" from a control
experiment that changed the RENDERER but kept the LAUNCHER fixed (FCL). That
control could only ever prove "not our backend" - it could NOT prove anything
about hardware, because the launcher was a common factor in both arms.
This tool makes the launcher/backend identity explicit so that mistake is
harder to repeat.

Self-locating; globs latest*.log.
"""
import glob
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

logs = sorted(glob.glob("latest*.log"), key=os.path.getmtime)
if not logs:
    print("no latest*.log found")
    sys.exit(1)

for p in logs:
    txt = open(p, encoding="utf-8", errors="replace").read()
    import datetime
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(p))

    print("=" * 74)
    print("%s   (mtime %s, %.1f KB)" % (p, mt, len(txt) / 1024))
    print("=" * 74)

    m = re.search(r"--versionType,\s*([^,\]]+)", txt)
    print("  launcher (--versionType) : %s" % (m.group(1).strip() if m else "?"))

    m = re.search(r"-Dminecraft\.launcher\.brand=(\S+)", txt)
    print("  launcher brand           : %s" % (m.group(1) if m else "(not in log)"))

    m = re.search(r"-Dminecraft\.launcher\.version=(\S+)", txt)
    print("  launcher version         : %s" % (m.group(1) if m else "(not in log)"))

    # Our mod jar loaded?
    m = re.search(r'Found mod file "(glesmod[^"]*)"', txt)
    print("  our mod jar              : %s" % (m.group(1) if m else "NOT FOUND"))

    # Native stderr lines like "[GLESMod] ..." (our C library)
    native = re.findall(r"^\[GLESMod\] .*$", txt, re.M)
    print("  native stderr lines      : %d" % len(native))

    # The unconditional load banner (proves the .so executed in THIS session)
    banner = [l for l in native if "本库已加载" in l]
    print("  load banner present      : %s" % ("YES -> " + banner[0][:110]
                                              if banner else "no"))

    # Native degrade events (only emitted by our library)
    deg = [l for l in native if "降级:" in l]
    print("  native degrade lines     : %d" % len(deg))

    m = re.search(r"OpenGL Version: (.+)", txt)
    print("  GL version string        : %s" % (m.group(1).strip()[:80] if m else "?"))

    # Frame-rate related settings that could cap us
    print("  minecraft fps limit hint : %s"
          % ("(not logged)" if "framerateLimit" not in txt else
             re.search(r"framerateLimit[^\n]*", txt).group(0)[:80]))

    # GL debug message inventory
    msgs = re.findall(r"message='([^']+)'", txt)
    if msgs:
        print("  GL debug messages (%d total):" % len(msgs))
        for k, v in Counter(msgs).most_common(8):
            print("      %4d  %s" % (v, k[:88]))
    else:
        print("  GL debug messages        : none")
    print()
