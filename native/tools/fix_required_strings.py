# -*- coding: utf-8 -*-
"""Replace the rule-P marker with an ASCII-only one.

Why: required_strings.txt is read by verify_required_strings.py as UTF-8
(`path.read_text(encoding="utf-8")`), but the earlier append wrote the marker
through PowerShell 5.1 which encoded the file as GBK/cp936. The new marker
therefore never matched, and the gate fired a false "stale artifact".

Rather than fight encodings, pick a marker that is pure ASCII yet still proves
the rule-P code is compiled in. The diagnostic message begins with
"mixed int/uint" in the C source as an ASCII prefix? It does not -- the message
is Chinese. So instead use the ASCII token that appears ONLY in rule P's code:
the function is `fix_mixed_int_uint`, and the message contains the ASCII
substring "int/uint" plus the ASCII "uint()". Use "int/uint" as the marker --
it is ASCII, and it occurs in both the rule-P diagnostic string and nowhere
else in the artifact.

Also rewrite the whole file as UTF-8 to keep it self-consistent going forward.
"""
import io

PATH = r'c:\Users\youyi\Documents\Mods_development\glesmod-template-1.21.1\native\tools\required_strings.txt'

# read as whatever works
raw = open(PATH, 'rb').read()
text = None
for enc in ('utf-8', 'gbk', 'cp936'):
    try:
        text = raw.decode(enc)
        print('decoded as %s' % enc)
        break
    except Exception:
        continue
if text is None:
    text = raw.decode('utf-8', 'replace')

lines = text.split('\n')

# drop the bad rule-P block
out = []
skip = False
for l in lines:
    if l.startswith('# Rule P (mixed int/uint'):
        skip = True
        continue
    if skip:
        if l.strip() == 'Mixed int/uint binary operations':
            skip = False
        continue
    out.append(l)

# append a clean ASCII marker block
out.append('')
out.append('# Rule P (mixed int/uint binary operations): proof the rewrite is')
out.append('# compiled in. Flywheel\'s common.vert has `gl_VertexID - baseVertex`')
out.append('# (int - uint), legal in desktop GLSL and forbidden in GLSL ES; the')
out.append('# device reported "no operation \'-\' exists that takes a left-hand')
out.append('# operand of type \'gl_VertexID int\' and a right operand of type \'in')
out.append('# uint\'". This ASCII token occurs in the rule-P diagnostic string and')
out.append('# nowhere else, so it distinguishes "new code present" from "stale".')
out.append('int/uint')
out.append('')

# write back as UTF-8 WITHOUT BOM (the reader uses utf-8, not utf-8-sig)
with io.open(PATH, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(out))

print('rewritten as UTF-8; last lines:')
for l in out[-10:]:
    print('  ' + l)
