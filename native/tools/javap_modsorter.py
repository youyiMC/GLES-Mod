#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decompile (javap -c -p) a class from a jar and print the part around a
method of interest.  Self-locating: finds loader-*.jar in the gradle cache.
"""
import glob
import os
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JAVAP = r"C:\Program Files\Java\jdk-21.0.12\bin\javap.exe"
if not os.path.isfile(JAVAP):
    JAVAP = "javap"

home = os.path.expanduser("~")
pats = [
    r"%s\.gradle\caches\modules-2\files-2.1\net.neoforged\fml_loader\**\loader-*.jar" % home,
    r"%s\.gradle\caches\**\loader-*.jar" % home,
    r"%s\.gradle\caches\**\fmlloader-*.jar" % home,
]
jars = []
for p in pats:
    jars.extend(glob.glob(p, recursive=True))
jars = sorted(set(j for j in jars if "sources" not in j))
print("loader jars:", [os.path.basename(j) for j in jars])
if not jars:
    sys.exit(1)

CLASSES = [
    "net.neoforged.fml.loading.ModSorter",
    "net.neoforged.fml.loading.ModSorter$DependencyResolutionResult",
]

tmp = tempfile.mkdtemp(prefix="javap_")
for cls in CLASSES:
    for j in jars:
        inner = cls.replace(".", "/") + ".class"
        try:
            with zipfile.ZipFile(j) as z:
                if inner not in z.namelist():
                    continue
        except Exception:
            continue

        # extract the whole package tree so inner classes resolve
        pkgdir = os.path.join(tmp, os.path.dirname(inner))
        os.makedirs(pkgdir, exist_ok=True)
        try:
            with zipfile.ZipFile(j) as z:
                for n in z.namelist():
                    base = os.path.basename(inner)
                    if n.startswith(os.path.dirname(inner) + "/") and n.endswith(".class"):
                        outp = os.path.join(tmp, n)
                        os.makedirs(os.path.dirname(outp), exist_ok=True)
                        with open(outp, "wb") as fh:
                            fh.write(z.read(n))
        except Exception:
            continue

        print()
        print("#" * 72)
        print("# %s   (from %s)" % (cls, os.path.basename(j)))
        print("#" * 72)
        env = dict(os.environ)
        env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"
        try:
            r = subprocess.run(
                [JAVAP, "-J-Duser.language=en", "-J-Duser.country=US",
                 "-J-Dfile.encoding=UTF-8", "-c", "-p", "-cp", tmp, cls],
                capture_output=True, text=True, timeout=180,
                encoding="utf-8", errors="replace", env=env)
        except Exception as e:
            print("javap failed:", e)
            continue
        txt = r.stdout or r.stderr
        lines = txt.splitlines()
        # if too long, print only regions mentioning dependency/optional
        if len(lines) > 400:
            keep = []
            for i, ln in enumerate(lines):
                if any(k in ln.lower() for k in
                       ("missingdependency", "optional", "versionrange",
                        "modloadingissue", "checkDependency", "version")):
                    keep.append(i)
            show = set()
            for i in keep:
                show.update(range(max(0, i - 6), min(len(lines), i + 7)))
            prev = -2
            for i in sorted(show):
                if i != prev + 1:
                    print("   ....")
                print("%5d| %s" % (i, lines[i]))
                prev = i
        else:
            for i, ln in enumerate(lines):
                print("%5d| %s" % (i, ln))
        break
