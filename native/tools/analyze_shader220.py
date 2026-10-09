# -*- coding: utf-8 -*-
"""
Extract shader 220 (the one that failed with the 'pose' error) from native.log
and compare RAW vs CONVERTED.

Device errors for it were:
    ERROR: 10:2: 'constructor' : can't convert
    ERROR: 10:2: 'pose' : field selection requires structure, vector, or matrix
    ERROR: 15:79: '-' : no operation '-' takes 'gl_VertexID int' and 'uint'
    ERROR: 15:79: 'assign' : cannot convert from 'gl_VertexID int' to 'uint'
    ERROR: 16:53: '!=' : no operation '!=' takes 'uint' and 'const int'

`10:2` etc. are Flywheel's own #line coordinates, not our file's lines.
The point of this script: decide whether OUR converter mangled the shader,
or whether the input already contained the offending constructs.
"""
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

LOG = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\native.log'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
DUMP = re.compile(r'\[(\d\d):(\d\d):(\d\d)\.(\d+)\]\s+(\d+)\|\s?(.*)$')


def load():
    with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    return [ANSI.sub('', l) for l in raw.split('\n')]


def collect(lines, lo, hi):
    """Return {srcline: text} for dump lines in [lo, hi)."""
    sec = {}
    for i in range(lo, hi):
        m = DUMP.match(lines[i])
        if not m:
            continue
        ln = int(m.group(5))
        if ln not in sec:
            sec[ln] = m.group(6)
    return sec


def show_region(sec, needles, label, ctx=6):
    print('  --- %s ---' % label)
    lo, hi = min(sec), max(sec)
    shown = set()
    for k in sorted(sec):
        if any(n in sec[k] for n in needles):
            for j in range(max(lo, k - ctx), min(hi, k + ctx) + 1):
                if j in sec and j not in shown:
                    print('    %4d| %s' % (j, sec[j].rstrip()))
                    shown.add(j)
            print('    ...')
    if not shown:
        print('    (no match for %s)' % (needles,))


def main():
    lines = load()
    idx = [i for i, l in enumerate(lines)
           if (m := DUMP.match(l)) and m.group(1) == '13'
           and m.group(2).startswith('3')]
    lo, hi = idx[0], idx[-1]

    # Section boundaries: label lines that say BEGIN/END.
    bounds = []
    for i in range(lo, hi + 1):
        s = lines[i]
        if not DUMP.match(s) and ('BEGIN' in s or 'END' in s
                                  or 'GL 名称' in s):
            kind = ('BEGIN_RAW' if ('BEGIN' in s and '原始源码' in s) else
                    'END_RAW' if ('END' in s and '原始源码' in s) else
                    'BEGIN_CONV' if ('BEGIN' in s and '转换后' in s) else
                    'END_CONV' if ('END' in s and '转换后' in s) else 'OTHER')
            bounds.append((i, kind))

    # Build (raw_range, conv_range) pairs, take the LAST one (shader 220).
    pairs = []
    cur = {}
    for (i, kind) in bounds:
        if kind == 'BEGIN_RAW':
            cur = {'raw': [i, None]}
        elif kind == 'END_RAW' and 'raw' in cur:
            cur['raw'][1] = i
        elif kind == 'BEGIN_CONV':
            cur['conv'] = [i, None]
        elif kind == 'END_CONV' and 'conv' in cur:
            cur['conv'][1] = i
            if 'raw' in cur and cur['raw'][1] is not None:
                pairs.append((cur['raw'], cur['conv']))
            cur = {}

    print('shader sections found: %d' % len(pairs))
    for n, (r, c) in enumerate(pairs):
        rc = collect(lines, r[0] + 1, r[1])
        cc = collect(lines, c[0] + 1, c[1])
        print('  [%d] RAW %d lines (log %d..%d)  CONV %d lines (log %d..%d)'
              % (n, len(rc), r[0], r[1], len(cc), c[0], c[1]))

    if not pairs:
        return 1

    # The failing shader 220 is the LARGEST section (RAW 984 -> CONV 988).
    # Log order: shader 217 (minor), then 218, then 220 (the big one),
    # then 221. Picking pairs[-1] selects the wrong (216-line) shader, so
    # select by size instead.
    raw_rng, conv_rng = max(pairs, key=lambda pr:
                            pr[0][1] - pr[0][0])
    rc = collect(lines, raw_rng[0] + 1, raw_rng[1])
    cc = collect(lines, conv_rng[0] + 1, conv_rng[1])
    print('\n=== target = largest section (shader 220) ===')
    print('RAW srclines: %d   CONVERTED srclines: %d' % (len(rc), len(cc)))

    for name, sec in (('RAW', rc), ('CONVERTED', cc)):
        print('\n########## %s ##########' % name)
        for tok in ['mat4x4 pose', 'mat4 pose', 'pose;', 'i.pose',
                    'rotation;', 'vec3 pos;', 'flw_instanceVertex',
                    'struct FlwInstance']:
            hits = [k for k in sec if tok in sec[k]]
            print('  %-22s %d %s' % (tok, len(hits),
                                     ('-> lines ' + str(hits[:6]))
                                     if hits else ''))
        show_region(sec, ['struct FlwInstance'], 'struct FlwInstance')
        show_region(sec, ['flw_instanceVertex'], 'flw_instanceVertex')

    # Line-by-line diff of the two regions (dedup by srcline).
    lo_l, hi_l = min(rc), max(rc)
    print('\n=== structural diff (RAW vs CONVERTED, by source line) ===')
    diffs = 0
    for k in range(lo_l, hi_l + 1):
        a = rc.get(k)
        b = cc.get(k)
        if a is None and b is None:
            continue
        if a != b:
            diffs += 1
            if diffs <= 40:
                print('  %4d  RAW: %s' % (k, (a or '').rstrip()[:110]))
                print('        CNV: %s' % ((b or '').rstrip()[:110]))
    print('  total differing lines: %d' % diffs)

    return 0


if __name__ == '__main__':
    sys.exit(main())
