"""Extract the shader dumps that the native backend writes to native.log.

native.log logs, for each glShaderSource call, both
    ===== BEGIN 该 shader 收到 glShaderSource 的原始源码 =====
    ...
    ===== END   该 shader 收到 glShaderSource 的原始源码 (N 行) =====
    ===== BEGIN 该 shader 实际被送入驱动的源码（转换后） =====
    ...
    ===== END   该 shader 实际被送入驱动的源码（转换后） (N 行) =====

Each content line is logged TWICE in a row (known quirk), so consecutive
identical lines must be collapsed.

Usage:
    py native/tools/extract_native_dumps.py <native.log> <outdir> [--list]
"""
import os
import re
import sys

SENTINEL = "\u8be5 shader"
BEGIN_RAW = "BEGIN " + SENTINEL
END_RAW = "END " + SENTINEL

# [16:02:02.201]      0| #version 330 core
LINE_RE = re.compile(r"^\[[\d:.]+\]\s+(\d+)\|\s?(.*)$")


def read_text(path):
    """native.log is UTF-8, EXCEPT the segments that quote the driver's own
    error log, which can contain raw invalid bytes (the driver returns binary
    garbage in some cases). Decoding strictly therefore fails mid-file, and a
    latin-1 fallback would turn the Chinese sentinels into mojibake so nothing
    would ever match. Use utf-8 + errors='replace'."""
    return open(path, "rb").read().decode("utf-8", errors="replace")


def main():
    log = sys.argv[1]
    outdir = sys.argv[2]
    list_only = "--list" in sys.argv
    os.makedirs(outdir, exist_ok=True)

    lines = read_text(log).splitlines()
    print("log %s : %d lines" % (os.path.basename(log), len(lines)))

    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kind = None
        if "BEGIN" in line and SENTINEL in line:
            kind = "converted" if "\u8f6c\u6362\u540e" in line else "raw"
        if kind is None:
            i += 1
            continue

        # Collect until the matching END.
        content = []
        i += 1
        while i < len(lines):
            if "END" in lines[i] and SENTINEL in lines[i]:
                break
            m = LINE_RE.match(lines[i])
            if m:
                content.append((int(m.group(1)), m.group(2)))
            i += 1
        i += 1

        # Collapse the "logged twice in a row" duplication.
        dedup = []
        for item in content:
            if dedup and dedup[-1] == item:
                continue
            dedup.append(item)

        # Rebuild in source order.
        text = "\n".join(t for _, t in dedup) + "\n"
        blocks.append({"kind": kind, "n": len(dedup), "text": text})

    print("found %d dump blocks" % len(blocks))
    for idx, b in enumerate(blocks):
        head = [t for _, t in []]  # placeholder
        first = next((l for l in b["text"].splitlines() if l.strip()), "")
        marks = []
        for probe in ("VERTEX_SHADER", "FRAGMENT_SHADER", "FLW_EMBEDDED",
                      "flywheel:internal/diffuse.glsl",
                      "flywheel:internal/wavelet.glsl",
                      "flywheel:internal/light_lut.glsl",
                      "sodium:include", "GLES_MOD", "MAX_TEXTURE_LOD_BIAS"):
            if probe in b["text"]:
                marks.append(probe)
        print("  [%2d] %-9s %4d lines | %-34s | %s"
              % (idx, b["kind"], b["n"], first.strip()[:34], ",".join(marks)))
        if not list_only:
            name = "%02d_%s.%s" % (idx, b["kind"],
                                   "vert" if "VERTEX_SHADER" in b["text"]
                                   or ".vert" in b["text"] else "frag")
            with open(os.path.join(outdir, name), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(b["text"])

    if not list_only:
        print("written to %s" % outdir)


if __name__ == "__main__":
    main()
