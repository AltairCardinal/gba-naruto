#!/usr/bin/env python3
"""Full per-cell family transition histogram for the overlay comparison.

``tools/s49_overlay_align/compare_overlay_families.py`` only keeps the first
64 difference records, so the transition histogram it prints is truncated.
This script recomputes the comparison with the same functions and reports the
**complete** transition table, which is what the "original cyan / remake
green" question (G-H15) needs.

Usage::

    python tools/s49_w1/overlay_transitions.py \
        --vram-dir build/s49-w1/vram-after \
        --moment movegrid-frame-v1 --frame step-20-A.vram-0000.bin
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from compare_overlay_families import (  # noqa: E402
    find_overlay_map,
    original_cells,
    remake_cells,
)


def full_transitions(left, right, offset_x, offset_y, cols, rows):
    out = Counter()
    for y in range(rows):
        for x in range(cols):
            other_x = x + offset_x
            other_y = y + offset_y
            a = left[y][x]
            b = "blank"
            if 0 <= other_x < cols and 0 <= other_y < rows:
                b = right[other_y][other_x]
            out[(a, b)] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    ap.add_argument("--frame", default=None,
                    help="the VRAM dump to use (default: the first one)")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if args.frame:
        dumps = [path for path in dumps if path.name == args.frame]
    if not dumps:
        print("ERR no VRAM dumps")
        return 2

    left = original_cells(args.moment)
    rows = len(left)
    cols = len(left[0])
    report = {}
    for path in dumps:
        vram = path.read_bytes()
        base = find_overlay_map(vram)
        if base < 0:
            print(f"  {path.name}: no overlay map")
            continue
        right, _info = remake_cells(vram, base)
        # The offset search: pick the offset with the most agreeing cells.
        best = None
        for offset_y in range(rows):
            for offset_x in range(cols):
                counts = full_transitions(left, right, offset_x, offset_y,
                                          cols, rows)
                agree = sum(count for (a, b), count in counts.items()
                            if a == b and a != "blank")
                mism = sum(count for (a, b), count in counts.items()
                           if a != b and a != "blank" and b != "blank")
                score = agree - mism
                if best is None or score > best[0]:
                    best = (score, offset_x, offset_y, counts)
        score, offset_x, offset_y, counts = best
        report[path.name] = {
            "offset": [offset_x, offset_y],
            "transitions": {f"{a} -> {b}": n
                            for (a, b), n in sorted(counts.items())},
        }
        print(f"=== {path.name}  offset [{offset_x}, {offset_y}] ===")
        for (a, b), n in sorted(counts.items()):
            if a != b and (a != "blank" or b != "blank"):
                print(f"  {a:>10} -> {b:<10} x{n}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        import json
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1)
                            + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
