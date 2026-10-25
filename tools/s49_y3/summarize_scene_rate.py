#!/usr/bin/env python3
"""Summarise the per-iteration rate measured by measure_scene_rate.py."""
from __future__ import annotations

import collections
import pathlib
import sys

path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else "build/s49-y3/scene-rate/scene-frame.txt")
rows = [tuple(int(x) for x in line.split())
        for line in path.read_text().splitlines() if line.strip()]
print(f"rows {len(rows)} first={rows[0]} last={rows[-1]}")

runs = []
start = 0
for i in range(1, len(rows) + 1):
    if i == len(rows) or rows[i][1] != rows[start][1]:
        runs.append((rows[start][0], rows[i - 1][0], i - start, rows[start][1]))
        start = i

histogram = collections.Counter(run[2] for run in runs)
print("run length (emulated frames per scene iteration) histogram:")
for length, count in sorted(histogram.items()):
    print(f"  {length}: {count}")

print()
print("runs of length >= 2 (first 60):")
shown = 0
for run in runs:
    if run[2] >= 2:
        print(f"  frames {run[0]}..{run[1]} len={run[2]} scene_frame={run[3]}")
        shown += 1
        if shown >= 60:
            break
