# -*- coding: utf-8 -*-
"""
Extract the 984-line Flywheel instancing vertex shader (shader 220) from the
LATEST native log, and also its converted form, so we can diff them.

Unlike the older dumps, this log's source lines carry the pattern
    [HH:MM:SS.mmm]  <space-padded srcline>| <text>
and the block markers are:
    ===== BEGIN 该 shader 收到 glShaderSource 的原始源码 =====
    ===== BEGIN 该 shader 实际被送入驱动的源码（转换后） =====

We pick the RAW block whose line count is largest (that is shader 220).
"""
import io
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1'
LOG = ROOT + r'\native(1).log'
OUT_RAW = ROOT + r'\fw220b-raw.txt'
OUT_CNV = ROOT + r'\fw220b-conv.txt'

ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
# "[14:24:32.044]    285| void flw_instanceVertex(in FlwInstance i) {"
SRC = re.compile(r'\]\s+(\d+)\|\s?(.*)$')


def load():
    with io.open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    return [ANSI.sub('', l) for l in raw.split('\n')]


def main():
    lines = load()
    print('log lines: %d' % len(lines))

    # Collect (start_index, kind) for every BEGIN marker.
    marks = []
    for i, l in enumerate(lines):
        if 'BEGIN' not in l:
            continue
        if '原始源码' in l:
            marks.append((i, 'RAW'))
        elif '转换后' in l:
            marks.append((i, 'CNV'))

    print('block markers: %d' % len(marks))

    blocks = []
    for n, (i, kind) in enumerate(marks):
        stop = len(lines)
        for j in range(i + 1, len(lines)):
            if '===== END' in lines[j] or '===== BEGIN' in lines[j]:
                stop = j
                break
        sec = {}
        for k in range(i + 1, stop):
            m = SRC.search(lines[k])
            if m:
                ln = int(m.group(1))
                if ln not in sec:
                    sec[ln] = m.group(2)
        blocks.append((kind, i, sec, stop))
        print('  [%d] %s  at line %d  src_lines=%d' % (n, kind, i, len(sec)))

    raws = [(i, s) for (k, i, s, _) in blocks if k == 'RAW']
    cnvs = [(i, s) for (k, i, s, _) in blocks if k == 'CNV']
    if not raws:
        print('FAIL: no RAW blocks')
        return 1

    # largest RAW block = the failing 984-line shader
    ri, rs = max(raws, key=lambda t: len(t[1]))
    print('\ntarget RAW block at log line %d, %d source lines' % (ri, len(rs)))

    # find the CNV block that immediately follows it
    ci, cs = None, None
    for (i, s) in cnvs:
        if i > ri:
            ci, cs = i, s
            break
    print('paired CNV block at log line %s, %s source lines'
          % (ci, len(cs) if cs else 0))

    with io.open(OUT_RAW, 'w', encoding='utf-8', newline='\n') as f:
        for k in sorted(rs):
            f.write(rs[k] + '\n')
    print('wrote %s (%d lines)' % (OUT_RAW, len(rs)))

    if cs:
        with io.open(OUT_CNV, 'w', encoding='utf-8', newline='\n') as f:
            for k in sorted(cs):
                f.write(cs[k] + '\n')
        print('wrote %s (%d lines)' % (OUT_CNV, len(cs)))

    # report the line we care about
    print('\n=== the failing line in RAW ===')
    for k in sorted(rs):
        if 'gl_VertexID' in rs[k]:
            print('  RAW %d| %s' % (k, rs[k].strip()))
    if cs:
        print('=== same region in the previously-converted output ===')
        for k in sorted(cs):
            if 'gl_VertexID' in cs[k]:
                print('  CNV %d| %s' % (k, cs[k].strip()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
