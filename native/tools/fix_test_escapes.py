# -*- coding: utf-8 -*-
"""Fix the doubled backslash escapes in the rule-P test template.

The M_TEMPLATE block was written with `\\n` (two backslashes) which produces a
literal backslash + 'n' in the C string, so the whole shader became ONE line
starting with '#version' -- and every statement line was then treated as part
of the preprocessor directive and copied verbatim, so rule P never ran.

Correct form is a single backslash: `\n`.
"""
import io

PATH = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\native\tools\test_shader_convert.c'

with io.open(PATH, 'r', encoding='utf-8', newline='') as f:
    text = f.read()

lines = text.split('\n')

start = None
for i, l in enumerate(lines):
    if 'static const char *const M_TEMPLATE' in l:
        start = i
        break
if start is None:
    raise SystemExit('M_TEMPLATE not found')

# the block ends at the line that closes it with '";'
end = start + 1
while end < len(lines) and not lines[end].rstrip().endswith('";'):
    end += 1

print('block: lines %d..%d' % (start + 1, end + 1))

fixed = 0
for j in range(start, end + 1):
    if '\\\\n' in lines[j]:
        lines[j] = lines[j].replace('\\\\n', '\\n')
        fixed += 1

print('lines fixed: %d' % fixed)
for j in range(start, end + 1):
    print('  %d| %s' % (j + 1, lines[j]))

with io.open(PATH, 'w', encoding='utf-8', newline='') as f:
    f.write('\n'.join(lines))
print('written')
