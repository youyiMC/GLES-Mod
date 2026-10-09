#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_required_strings.py -- fail the build if the artifact lacks new code.

Why this exists
---------------
`verify_exported_symbols.py` proves a symbol is EXPORTED. It cannot prove that
the code behind it is the NEW code. Both a stub forwarder and a custom
implementation export the same name, so replacing one with the other leaves the
symbol table identical.

That gap cost this project real time. After adding the `glGetStringi`
implementation, the rebuilt library passed the symbol gate and had a size
byte-identical to the previous build (1078352). The reason was not subtle: at
that moment the source did not compile, the build failed, and the previous
artifact remained in place. The symbol gate said "OK" the whole time.

The reliable judge is content, not names. A string literal that exists ONLY in
the new code path cannot be present in an old artifact. Checking for it
converts a silent stale binary into a failed build.

Design notes
------------
- Reads markers from `required_strings.txt` (one per line, '#' comments).
- Searches the RAW BYTES of each artifact, not a decoded string, so this is
  immune to encoding assumptions on any platform.
- Checks EVERY artifact passed on the command line, so a per-ABI staleness
  (one ABI rebuilt, the other not) is caught as well.
- Exit code is non-zero if any marker is missing from any artifact.

Usage
-----
    py native/tools/verify_required_strings.py build/native/arm64-v8a/libgl_gles.so ...
    py native/tools/verify_required_strings.py              # use default paths

LGPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_LIST = HERE / "required_strings.txt"
DEFAULT_ARTIFACTS = [
    ROOT / "build" / "native" / "arm64-v8a" / "libgl_gles.so",
    ROOT / "build" / "native" / "armeabi-v7a" / "libgl_gles.so",
]


def load_markers(path: pathlib.Path) -> list[str]:
    """Return the marker list, ignoring blank lines and '#' comments."""
    markers: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        markers.append(line)
    return markers


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("artifacts", nargs="*", type=pathlib.Path,
                    help="artifacts to check (default: build/native/*/libgl_gles.so)")
    ap.add_argument("--list", type=pathlib.Path, default=DEFAULT_LIST,
                    dest="marker_list",
                    help=f"marker list file (default: {DEFAULT_LIST.name})")
    args = ap.parse_args()

    if not args.marker_list.exists():
        print(f"ERROR: marker list not found: {args.marker_list}", file=sys.stderr)
        return 2

    markers = load_markers(args.marker_list)
    if not markers:
        print(f"ERROR: marker list is empty: {args.marker_list}", file=sys.stderr)
        return 2

    artifacts = args.artifacts or DEFAULT_ARTIFACTS
    artifacts = [p for p in artifacts]

    print("=" * 70)
    print(" artifact content check (string markers)")
    print("=" * 70)
    print(f"markers  : {len(markers)} from {args.marker_list.name}")
    print()

    failures = 0

    for art in artifacts:
        if not art.exists():
            print(f"[SKIP] {art} (not built)")
            continue

        data = art.read_bytes()
        size = len(data)
        print(f"{art}  ({size} bytes)")

        missing_here: list[str] = []
        for m in markers:
            needle = m.encode("utf-8")
            idx = data.find(needle)
            if idx >= 0:
                print(f"  [OK]      {m!r} @ 0x{idx:X}")
            else:
                print(f"  [MISSING] {m!r}")
                missing_here.append(m)

        if missing_here:
            print(f"  -> {len(missing_here)} marker(s) absent: "
                  f"the artifact does NOT contain the current code.")
            print(f"  -> If the size looks byte-identical to a previous build, "
                  f"the build most likely FAILED and left the old file behind.")
            failures += 1
        else:
            print("  -> all markers present")
        print()

    print("=" * 70)
    if failures:
        print(f"FAILED: {failures} artifact(s) missing required strings")
        print("A missing marker is not a formatting issue: it means the artifact")
        print("predates the source change. Check the build log for a compile error")
        print("rather than assuming the build system did its job.")
        print("=" * 70)
        return 1

    print("PASSED: every artifact contains every required string marker")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
