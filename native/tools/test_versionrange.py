#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Empirically test NeoForge's version-range parsing for "" vs "[0,)".

Uses the real Maven VersionRange + NeoForge MavenVersionAdapter from the
Gradle cache.  Writes a tiny Java file, compiles it with javac, runs it, and
prints the results.  Self-locating.
"""
import glob
import os
import re
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

def find(pat):
    return sorted(set(p for p in glob.glob(os.path.join(g, pat), recursive=True)
                      if "sources" not in p and "javadoc" not in p))

maven = find(r"**/maven-artifact-*.jar")
loader = find(r"**/loader-*.jar")
print("maven-artifact:", [os.path.basename(p) for p in maven])
print("loader:", [os.path.basename(p) for p in loader])

cp = maven[:1] + loader[:1]
if not cp:
    print("missing jars")
    sys.exit(1)
classpath = ";".join(cp)

src = r'''
import org.apache.maven.artifact.versioning.VersionRange;
import org.apache.maven.artifact.versioning.ArtifactVersion;
import org.apache.maven.artifact.versioning.DefaultArtifactVersion;

public class VrTest {
    static void probe(String spec, String ver) {
        String shown;
        boolean contains = false;
        String note = "";
        try {
            VersionRange r = VersionRange.createFromVersionSpec(spec);
            shown = String.valueOf(r);
            ArtifactVersion av = new DefaultArtifactVersion(ver);
            contains = r.containsVersion(av);
        } catch (Throwable t) {
            shown = "<EXCEPTION> " + t.getClass().getSimpleName() + ": " + t.getMessage();
            note = " (threw)";
        }
        System.out.printf("spec=%-10s version=%-18s contains=%-5s range=%s%s%n",
                "\"" + spec + "\"", ver, contains, shown, note);
    }

    public static void main(String[] a) {
        System.out.println("--- empty spec ---");
        probe("", "0.8.13+mc1.21.1");
        probe("", "1.0");
        System.out.println("--- [0,) ---");
        probe("[0,)", "0.8.13+mc1.21.1");
        probe("[0,)", "1.0");
        probe("[0,)", "0");
        System.out.println("--- [1.0,) ---");
        probe("[1.0,)", "0.8.13+mc1.21.1");
        System.out.println("--- * / other candidates ---");
        probe("*", "0.8.13+mc1.21.1");
        probe("[0.0.0,)", "0.8.13+mc1.21.1");
        probe("(,)", "0.8.13+mc1.21.1");
    }
}
'''

tmp = tempfile.mkdtemp(prefix="vrtest_")
srcp = os.path.join(tmp, "VrTest.java")
with open(srcp, "w", encoding="utf-8") as fh:
    fh.write(src)

env = dict(os.environ)
env["JAVA_TOOL_OPTIONS"] = "-Duser.language=en -Duser.country=US"

print("classpath:", classpath)
r = subprocess.run([JAVAC, "-encoding", "UTF-8", "-d", tmp, srcp],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env)
print("--- javac ---")
print(r.stdout or "", r.stderr or "")
if r.returncode != 0:
    sys.exit(1)

r = subprocess.run([JAVA, "-cp", tmp + ";" + classpath, "VrTest"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=180)
print("--- run ---")
print(r.stdout or "")
print(r.stderr or "")
