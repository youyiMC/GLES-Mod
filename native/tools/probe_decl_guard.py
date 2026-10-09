#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal probe: does declares_ident_as_var fire for a function DEFINITION?

We need to know whether the guard sees `float texture2DShadow(...)`.
Since declares_ident_as_var is static, we test through the CLI product using a
file that ONLY contains the function definition (no calls, no other texture uses).
"""
import subprocess
import sys

CLI = r"native\tools\.cache\convert_shader_cli.exe"

cases = {
    "def_only": """#version 330 core
float texture2DShadow(sampler2DShadow s, vec3 p) {
    return 1.0;
}
void main() { gl_FragData[0] = vec4(texture2DShadow(shadowtex0, vec3(0.0))); }
""",
    "var_decl": """#version 330 core
uniform sampler2D texture;
void main() { gl_FragData[0] = texture(texture, vec2(0.0)); }
""",
    "call_only": """#version 330 core
uniform sampler2D tex;
void main() { gl_FragData[0] = texture(tex, vec2(0.0)); }
""",
}

for name, src in cases.items():
    p = "shader_dump/probe_%s.frag" % name
    open(p, "w", encoding="utf-8").write(src)
    out = "shader_dump/probe_%s.out" % name
    subprocess.run([CLI, p, "fragment", out], capture_output=True)
    txt = open(out, encoding="utf-8", errors="replace").read()
    hits = [l.strip() for l in txt.splitlines()
            if "texture" in l and not l.strip().startswith("//")]
    print("=== %s ===" % name)
    for h in hits:
        print("   ", h[:140])
    print()
