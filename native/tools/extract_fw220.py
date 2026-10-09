# -*- coding: utf-8 -*-
"""Extract the 984-line shader 220 RAW source to fw220-raw.txt and grep for
the declarations of `i` that could have polluted a name table."""
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

LOG = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\native.log'
OUT = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\fw220-raw.txt'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
DUMP = re.compile(r'\[(\d\d):(\d\d):(\d\d)\.(\d+)\]\s+(\d+)\|\s?(.*)$')


def load():
    with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        return [ANSI.sub('', l) for l in f.read().split('\n')]


def collect(lines, lo, hi):
    sec, order = {}, []
    for i in range(lo, hi):
        m = DUMP.match(lines[i])
        if m:
            ln = int(m.group(5))
            if ln not in sec:
                order.append(ln)
            sec[ln] = m.group(6)
    return sec, sorted(set(order))


lines = load()
raw, _ = collect(lines, 419846, 421815)      # shader 220 RAW
cnv, _ = collect(lines, 421818, 423794)      # shader 220 CONVERTED

with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    for k in sorted(raw):
        f.write(raw[k] + '\n')
print('wrote %s  (%d lines)' % (OUT, len(raw)))

with open(OUT.replace('raw', 'conv'), 'w', encoding='utf-8', newline='\n') as f:
    for k in sorted(cnv):
        f.write(cnv[k] + '\n')
print('wrote conv (%d lines)' % len(cnv))

print('\n=== every declaration of the identifier `i` in RAW ===')
pat = re.compile(r'^\s*(?:flat\s+|const\s+|in\s+|out\s+|uniform\s+|'
                 r'highp\s+|mediump\s+|lowp\s+|varying\s+|attribute\s+)*'
                 r'([A-Za-z_][A-Za-z0-9_]*)\s+i\s*(?:[,;)=]|\[)')
for k in sorted(raw):
    m = pat.match(raw[k])
    if m:
        print('  L%4d  type=%-10s | %s' % (k, m.group(1), raw[k].strip()))

print("\n=== 'i' used as a for-loop counter ===")
for k in sorted(raw):
    if re.search(r'\bfor\s*\(\s*(?:int|uint)\s+i\b', raw[k]):
        print('  L%4d | %s' % (k, raw[k].strip()))

print('\n=== all lines containing `i.` (member access on i) in RAW ===')
n = 0
for k in sorted(raw):
    if re.search(r'\bi\.', raw[k]):
        n += 1
        if n <= 12:
            print('  L%4d | %s' % (k, raw[k].strip()))
print('  total: %d' % n)

print('\n=== which of those got rewritten in CONVERTED? ===')
for k in sorted(raw):
    if re.search(r'\bi\.', raw[k]):
        a, b = raw[k], cnv.get(k)
        if a != b:
            print('  RAW  L%4d | %s' % (k, a.strip()))
            print('  CONV L%4d | %s' % (k, (b or '<absent>').strip()))
