# -*- coding: utf-8 -*-
"""Dump specific converted source-line ranges from the 13:37 session."""
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
        return [ANSI.sub('', l) for l in f.read().split('\n')]


def collect(lines, lo, hi):
    sec = {}
    for i in range(lo, hi):
        m = DUMP.match(lines[i])
        if m:
            ln = int(m.group(5))
            if ln not in sec:
                sec[ln] = m.group(6)
    return sec


lines = load()
idx = [i for i, l in enumerate(lines)
       if (m := DUMP.match(l)) and m.group(1) == '13' and m.group(2).startswith('3')]

# section [1]: RAW 419845..421815, CONV 421817..423794  (shader 220)
raw = collect(lines, 419846, 421815)
cnv = collect(lines, 421818, 423794)

print('=== RAW lines 275..295 ===')
for k in range(275, 296):
    if k in raw:
        print('%4d| %s' % (k, raw[k].rstrip()))

print('\n=== CONVERTED lines 279..299 ===')
for k in range(279, 300):
    if k in cnv:
        print('%4d| %s' % (k, cnv[k].rstrip()))

# Find every difference in the 270..300 band
print('\n=== band 270..300: RAW vs CONVERTED ===')
for k in range(270, 301):
    a, b = raw.get(k), cnv.get(k)
    if a != b:
        print('%4d RAW: %s' % (k, (a or '<absent>').rstrip()))
        print('     CNV: %s' % ((b or '<absent>').rstrip()))

# Locate the gl_VertexID line in both
print('\n=== gl_VertexID / baseVertex lines ===')
for k in sorted(raw):
    if 'gl_VertexID' in raw[k]:
        print('RAW %4d| %s' % (k, raw[k].rstrip()))
for k in sorted(cnv):
    if 'gl_VertexID' in cnv[k]:
        print('CNV %4d| %s' % (k, cnv[k].rstrip()))
