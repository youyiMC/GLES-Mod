#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare all fcl-latest*.log runs and prove which native-library build was
actually loaded.

Self-locating, no args.  For each log prints:
  - the probe banner (v9 vs v10 -> which .so was loaded)
  - whether the v9-only self-contaminating depth readback fired
  - the plugin install directory from LD_LIBRARY_PATH
    (Android changes the ~~<random>== suffix on every (re)install,
     so an identical path == the APK was NOT reinstalled)
  - the mod jar filename
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

logs = sorted(glob.glob("fcl-latest*.log"), key=os.path.getmtime)
if not logs:
    print("no fcl-latest*.log found")
    sys.exit(1)

print("found %d run log(s)" % len(logs))
print()

for p in logs:
    txt = open(p, encoding="utf-8", errors="replace").read()

    banner = "?"
    m = re.search(r"几何诊断探针 (v\d+)", txt)
    if m:
        banner = m.group(1)

    # v9-only self-contamination artifacts
    readback = "深度回读:" in txt
    contamin = "the combination of format 6402 and type 5126 is unsupported" in txt

    # plugin install dir (random suffix changes on reinstall)
    inst = "?"
    m = re.search(r"com\.youyimc\.glesmod\.plugin-([A-Za-z0-9_\-]+)==/lib/arm64", txt)
    if m:
        inst = m.group(1)

    modjar = "?"
    m = re.search(r"Found mod file \"(glesmod[^\"]*)\"", txt)
    if m:
        modjar = m.group(1)

    sod = "sodium-neoforge-" in txt
    crash = "Shader compilation failed" in txt

    import datetime
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(p))

    print("=" * 74)
    print("%s   (mtime %s)" % (p, mt))
    print("=" * 74)
    print("  探针 banner          : %s   <-- 说明加载的是哪个 .so" % banner)
    print("  v9 专用『深度回读』  : %s" % ("存在" if readback else "不存在"))
    print("  6402/5126 自污染报错 : %s" % ("存在" if contamin else "不存在"))
    print("  插件安装目录签名     : %s" % inst)
    print("  mod jar              : %s" % modjar)
    print("  装载了 Sodium        : %s" % ("是" if sod else "否"))
    print("  Sodium 着色器编译崩溃: %s" % ("是" if crash else "否"))
    print()

print("=" * 74)
print("结论判据")
print("=" * 74)
print("  v10 .so 的 banner 里不会出现『深度回读』，且不含 6402/5126 自污染报错。")
print("  插件安装目录的 ~~<随机串>== 每次重装都会变；两次相同 => 没有重装 APK。")
