#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate maven-artifact jars that actually contain
org/apache/maven/artifact/versioning/VersionRange.class and run a Java probe
against them to decide which versionRange spec is safe.
"""
import glob
import os
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

JDK = r"C:\Program Files\Java\jdk-21.0.12"
JAVAC = os.path.join(JDK, "bin", "javac.exe")
JAVA = os.path.join(JDK, "bin", "java.exe")

home = os.path.expanduser("~")
g = os.path.join(home, ".gradle", "caches")

WANT = "org/apache/maven/artifact/versioning/VersionRange.class"

good = []
for p in glob.glob(os.path.join(g, "**", "*.jar"), recursive=True):
    if not os.path.basename(p).startswith("maven-artifact"):
        continue
    if "sources" in p or "javadoc" in p:
        continue
    try:
        with zipfile.ZipFile(p) as z:
            if WANT in z.namelist():
                good.append(p)
    except Exception:
        pass

print("jars containing VersionRange.class: %d" % len(good))
for p in good:
    print("  ", p)
if not good:
    # broaden: any jar at all
    print("broadening search to ALL jars ...")
    for p in glob.glob(os.path.join(g, "**", "*.jar"), recursive=True):
        if "sources" in p or "javadoc" in p:
            continue
        try:
            with zipfile.ZipFile(p) as z:
                if WANT in z.namelist():
                    good.append(p)
                    print("  ", p)
        except Exception:
            pass
    print("total:", len(good))

if not good:
    sys.exit(1)

classpath = good[0]

src = r'''
import org.apache.maven.artifact.versioning.VersionRange;
import org.apache.maven.artifact.versioning.ArtifactVersion;
import org.apache.maven.artifact.versioning.DefaultArtifactVersion;

public class VrTest {
    static void probe(String spec, String ver) {
        String shown;
        boolean contains = false;
        try {
            VersionRange r = VersionRange.createFromVersionSpec(spec);
            shown = r.toString();
            contains = r.containsVersion(new DefaultArtifactVersion(ver));
        } catch (Throwable t) {
            shown = "<" + t.getClass().getSimpleName() + ": " + t.getMessage() + ">";
        }
        System.out.printf("spec=%-12s ver=%-18s contains=%-5s range=%s%n",
                "[" + spec + "]", ver, contains, shown);
    }
    public static void main(String[] a) {
        System.out.println("### empty spec (current bug) ###");
        probe("", "0.8.13+mc1.21.1");
        System.out.println("### [0,) candidate ###");
        probe("[0,)", "0.8.13+mc1.21.1");
        probe("[0,)", "1.0");
        System.out.println("### [0.0.0,) ###");
        probe("[0.0.0,)", "0.8.13+mc1.21.1");
        System.out.println("### * ###");
        probe("*", "0.8.13+mc1.21.1");
    }
}
'''

tmp = tempfile.mkdtemp(prefix="vrtest_")
srcp = os.path.join(tmp, "VrTest.java")
open(srcp, "w", encoding="utf-8").write(src)

env = dict(os.environ)
env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"

r = subprocess.run([JAVAC, "-encoding", "UTF-8", "-cp", classpath,
                    "-d", tmp, srcp],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env)
if r.returncode != 0:
    print("--- javac FAILED ---")
    print(r.stdout or "", r.stderr or "")
    sys.exit(1)

r = subprocess.run([JAVA, "-cp", tmp + os.pathsep + classpath, "VrTest"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=180)
print("--- results ---")
print(r.stdout or "")
if r.stderr:
    print(r.stderr)
