#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decisive test of versionRange semantics.

Builds a classpath with maven-artifact + commons-lang3 + loader(neoforgespi)
and probes BOTH:
   org.apache.maven.artifact.versioning.VersionRange
   net.neoforged.neoforgespi.language.MavenVersionAdapter
for spec "" and "[0,)".
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

WANTED = [
    ("org/apache/maven/artifact/versioning/VersionRange.class", "maven-artifact"),
    ("org/apache/commons/lang3/math/NumberUtils.class", "commons-lang3"),
    ("net/neoforged/neoforgespi/language/MavenVersionAdapter.class", "loader-"),
]

cp = []
for wanted, hint in WANTED:
    found = None
    for p in sorted(glob.glob(os.path.join(g, "**", "*.jar"), recursive=True)):
        base = os.path.basename(p)
        if hint not in base or "sources" in base or "javadoc" in base:
            continue
        try:
            with zipfile.ZipFile(p) as z:
                if wanted in z.namelist():
                    found = p
                    break
        except Exception:
            pass
    print("%-22s -> %s" % (hint, os.path.basename(found) if found else "NOT FOUND"))
    if found:
        cp.append(found)

if len(cp) < 3:
    print("missing deps")
    sys.exit(1)

classpath = os.pathsep.join(cp)

src = r'''
import org.apache.maven.artifact.versioning.VersionRange;
import org.apache.maven.artifact.versioning.ArtifactVersion;
import org.apache.maven.artifact.versioning.DefaultArtifactVersion;

public class VrTest {
    static void probe(String label, String spec, String ver) {
        String shown;
        boolean contains = false;
        try {
            VersionRange r = VersionRange.createFromVersionSpec(spec);
            shown = r.toString();
            contains = r.containsVersion(new DefaultArtifactVersion(ver));
        } catch (Throwable t) {
            shown = "<" + t.getClass().getSimpleName() + ": " + t.getMessage() + ">";
        }
        System.out.printf("%-16s spec=%-12s ver=%-18s contains=%-5s range=%s%n",
                label, "[" + spec + "]", ver, contains, shown);
    }

    static void probeNV(String label, String spec, String ver) {
        String shown;
        boolean contains = false;
        try {
            Class<?> c = Class.forName(
                "net.neoforged.neoforgespi.language.MavenVersionAdapter");
            java.lang.reflect.Method m =
                c.getMethod("createFromVersionSpec", String.class);
            Object r = m.invoke(null, spec);
            shown = r.toString();
            java.lang.reflect.Method cm =
                c.getMethod("containsVersion",
                    org.apache.maven.artifact.versioning.ArtifactVersion.class);
            contains = (Boolean) cm.invoke(r, new DefaultArtifactVersion(ver));
        } catch (Throwable t) {
            Throwable cause = t.getCause() != null ? t.getCause() : t;
            shown = "<" + cause.getClass().getSimpleName() + ": "
                    + cause.getMessage() + ">";
        }
        System.out.printf("%-16s spec=%-12s ver=%-18s contains=%-5s range=%s%n",
                label, "[" + spec + "]", ver, contains, shown);
    }

    public static void main(String[] a) {
        System.out.println("=== plain Maven VersionRange ===");
        probe("maven", "", "0.8.13+mc1.21.1");
        probe("maven", "[0,)", "0.8.13+mc1.21.1");
        probe("maven", "[0,)", "1.0");
        probe("maven", "[0.0.0,)", "0.8.13+mc1.21.1");
        probe("maven", "*", "0.8.13+mc1.21.1");
        System.out.println();
        System.out.println("=== NeoForge MavenVersionAdapter ===");
        probeNV("neoforge", "", "0.8.13+mc1.21.1");
        probeNV("neoforge", "[0,)", "0.8.13+mc1.21.1");
        probeNV("neoforge", "[0,)", "1.0");
        probeNV("neoforge", "[0.0.0,)", "0.8.13+mc1.21.1");
        probeNV("neoforge", "*", "0.8.13+mc1.21.1");
        probeNV("neoforge", "[1.2,)", "0.8.13+mc1.21.1");
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
