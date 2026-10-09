#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Why did guard (5) not fire for `cross(float(i), ...)`?

The guard reads the token immediately BEFORE `expr_start` and clears do_wrap
when it is a float type name (`vec3` in `vec3 i = q.xyz;`).

Two candidate explanations, and they need different fixes:
  (a) the guard code never runs because 情形 F was not reached for this token
      (some earlier 情形 already wrapped it), or
  (b) it runs but the token scan looks at the wrong position.

Rather than reason, this prints, for the fixture, every place where `float(`
or `vec2(`/`vec3(` got inserted around a single-token identifier, together with
the preceding text on that line -- so the actual decision point is visible.

LGPL-3.0-or-later
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, ".cache", "veil")
OUT = os.path.join(T, "probe_quaternion_i_alias.frag.out")


def main():
    if not os.path.isfile(OUT):
        print("missing:", OUT)
        return 1
    for i, l in enumerate(io.open(OUT, encoding="utf-8", errors="replace")
                         .read().splitlines(), 1):
        if "(" in l and ("cross" in l or "vec3 i" in l or "vec4 q" in l):
            print("%4d | %s" % (i, l.rstrip()[:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
