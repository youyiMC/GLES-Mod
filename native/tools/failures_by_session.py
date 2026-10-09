#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Group every shader 'compile failure' entry in native.log by session.

Why: native.log accumulates across many game runs and many converter builds.
A failure recorded at 17:05 may already be fixed; only the entries from the run
being debugged matter.  Lumping them together inflates the bug list and sends
you chasing ghosts.

Usage: py native\\tools\\failures_by_session.py <log>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shader_from_log import content, find_failing_shaders, load_lines  # noqa: E402

lines = load_lines(sys.argv[1])
fails = find_failing_shaders(lines)

TS = re.compile(r"^\[(\d\d:\d\d:\d\d)")

row = []
for idx, sid, stage in fails:
    # NOTE: take the timestamp from the RAW line -- content() strips it.
    m = TS.match(lines[idx])
    row.append((m.group(1) if m else "??:??:??", sid, stage, idx))

# A new session begins when the clock jumps backwards (or forward by a lot).
sessions = []
for t, sid, stage, idx in row:
    if not sessions:
        sessions.append([t, [(sid, stage)]])
        continue
    prev = sessions[-1][0]
    if t < prev:
        sessions.append([t, [(sid, stage)]])
    else:
        sessions[-1][1].append((sid, stage))

print("total failure entries: %d" % len(row))
print("sessions detected    : %d" % len(sessions))
print()
for t, items in sessions:
    ids = [s for s, _ in items]
    print("  start %s   %3d entries   shaders %s" % (t, len(items), ids[:22]))
