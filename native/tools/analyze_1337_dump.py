# -*- coding: utf-8 -*-
"""
Extract the failing 13:37 session's RAW and CONVERTED shader dumps from
native.log, then compare the FlwInstance struct and flw_instanceVertex
function between them.

This is forensic work: the device reported
    'pose' : field selection requires structure, vector, or matrix
for `i.pose`, yet the RAW source contains `mat4x4 pose;`.
Either the converter mangled the struct, or something else is going on.

ASCII-only output on purpose (Windows console codepage is GBK).
"""
import re
import sys

# The console codepage here is GBK; native.log contains replacement chars.
# Force UTF-8 with replacement so printing never raises.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

LOG = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\native.log'

# native.log carries ANSI colour escapes, so strip them before parsing.
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

# Non-anchored: the line may be prefixed by escape sequences / other text.
DUMP = re.compile(r'\[(\d\d):(\d\d):(\d\d)\.(\d+)\]\s+(\d+)\|\s?(.*)$')


def load():
    with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    return [ANSI.sub('', l) for l in raw.split('\n')]


def main():
    lines = load()
    print('total lines: %d' % len(lines))

    # Collect dump lines belonging to the 13:3x session.
    # NOTE: the minute field is '37', not '3' -- comparing == '3' silently
    # matched nothing. Use startswith.
    idx = []
    for i, l in enumerate(lines):
        m = DUMP.match(l)
        if m and m.group(1) == '13' and m.group(2).startswith('3'):
            idx.append(i)
    print('13:3x dump lines: %d' % len(idx))
    if not idx:
        return 1
    lo, hi = idx[0], idx[-1]
    print('window: %d .. %d' % (lo, hi))

    # Show every non-dump line inside the window: these are the labels.
    print('\n=== non-dump lines in window (labels) ===')
    labels = []
    for i in range(lo, hi + 1):
        if not DUMP.match(lines[i]):
            s = lines[i].rstrip()
            if s.strip():
                labels.append(i)
                print('%7d  %s' % (i, s.strip()[:150]))
    print('label count: %d' % len(labels))

    # Split the window into sections at label lines.
    bounds = [lo] + labels + [hi + 1]
    print('\n=== sections ===')
    sections = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        sec = {}
        order = []
        for i in range(a, b):
            m = DUMP.match(lines[i])
            if not m:
                continue
            ln = int(m.group(5))
            txt = m.group(6)
            if ln not in sec:
                order.append(ln)
            sec[ln] = txt
        if sec:
            sections.append((a, b, sec))
            print('  section %d: lines %d..%d  srclines=%d  max=%d'
                  % (k, a, b, len(sec), max(sec)))

    # Analyse each section for the struct and the function.
    for (a, b, sec) in sections:
        joined = '\n'.join(sec[k] for k in sorted(sec))
        has_pose_decl = 'pose;' in joined
        has_ipose = 'i.pose' in joined
        has_rot = 'rotation;' in joined
        print('\n--- section %d..%d ---' % (a, b))
        print('  has "pose;" decl : %s' % has_pose_decl)
        print('  has "i.pose"     : %s' % has_ipose)
        print('  has "rotation;"  : %s' % has_rot)
        print('  lines: %d' % len(sec))

        # Print the FlwInstance struct definition
        for k in sorted(sec):
            if 'struct FlwInstance' in sec[k]:
                print('  struct FlwInstance at line %d:' % k)
                for j in range(k, min(k + 14, max(sec) + 1)):
                    if j in sec:
                        print('    %4d| %s' % (j, sec[j]))
                break

    # Finally: does any section contain a *mangled* mat4x4 / pose token?
    print('\n=== search for suspicious tokens across ALL 13:3x dump lines ===')
    for token in ['mat4x4', 'mat4 pose', 'pose', 'flw_instanceVertex',
                  'FlwInstance']:
        cnt = 0
        for i in idx:
            if token in lines[i]:
                cnt += 1
        print('  %-20s %d' % (token, cnt))

    return 0


if __name__ == '__main__':
    sys.exit(main())
