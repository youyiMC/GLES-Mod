# -*- coding: utf-8 -*-
"""Read the build log (GBK-encoded by PS 5.1) and print the gate summary."""
import io
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

PATH = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\build-rulep.txt'

with open(PATH, 'rb') as f:
    data = f.read()

text = None
for enc in ('gbk', 'utf-8', 'cp936'):
    try:
        text = data.decode(enc)
        print('decoded as %s' % enc)
        break
    except Exception:
        continue
if text is None:
    text = data.decode('utf-8', 'replace')
    print('decoded with replacement')

lines = text.split('\n')
print('lines: %d' % len(lines))

KEY = re.compile(r'artifacts|\.jar|\.so|\.apk|PASSED|FAIL|marker|'
                 r'verify|glslang|symbol|总数|合计|通过|失败|identical|CHANGED|'
                 r'\[[0-9]/[0-9]\]')
hits = [l.rstrip() for l in lines if KEY.search(l)]
print('--- %d key lines ---' % len(hits))
for l in hits:
    print('  ' + l.strip())
