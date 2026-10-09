# Verify the built APK actually contains the freshly-built .so, and that the
# .so really carries the fix (not a stale binary). ASCII-only wrapper.
import hashlib
import os
import zipfile

ROOT = r"c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1"
APK = os.path.join(ROOT, "build", "plugin", "glesmod-renderer-plugin.apk")

def sha(b):
    return hashlib.sha256(b).hexdigest()

print("=== APK members ===")
with zipfile.ZipFile(APK) as z:
    for n in z.namelist():
        if n.endswith(".so") or n.endswith(".toml"):
            print("  %-46s %8d" % (n, z.getinfo(n).file_size))

    for abi in ("arm64-v8a", "armeabi-v7a"):
        member = "lib/%s/libgl_gles.so" % abi
        built = os.path.join(ROOT, "build", "native", abi, "libgl_gles.so")
        try:
            inside = z.read(member)
        except KeyError:
            print("MISSING in apk: %s" % member)
            continue
        outside = open(built, "rb").read()
        same = sha(inside) == sha(outside)
        print()
        print("=== %s ===" % abi)
        print("  apk     sha256 %s  (%d bytes)" % (sha(inside)[:24], len(inside)))
        print("  build   sha256 %s  (%d bytes)" % (sha(outside)[:24], len(outside)))
        print("  IDENTICAL: %s" % ("YES" if same else "NO  <-- STALE APK"))
