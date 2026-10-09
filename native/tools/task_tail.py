#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report the tail of a captured VS Code task output file (UTF-8).

Usage: py native\\tools\\task_tail.py <file> [n]
"""
import io
import sys

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30

with io.open(path, encoding="utf-8", errors="replace") as f:
    lines = f.read().splitlines()

for ln in lines[-n:]:
    sys.stdout.write(ln[:170] + "\n")
