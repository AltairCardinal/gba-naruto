#!/usr/bin/env python3
"""Match a dense capture window against walk screenshots.

Why this tool exists
--------------------
E3's dense capture proved that the original's camera pans *while the walk
screenshot is being taken*, but the exact frame index of the walk screenshot
inside the dense window was only reported as prose ("f043").  The C1 stream
needs that index as a machine readable number, and it needs the same number
for the remake side.

This tool answers one question per (dense frame, target) pair:

    how many pixels differ, and which integer translation best explains the
    difference?

Usage
-----
    python tools/s49_w21c1/match_dense.py \
        --dense build/w20-e3/dense/step-20-to-21 \
        --target build/s49-package-w18/work/s49-report/capture-original/step-21-A.png \
        --out build/w20-e1/dense-match-original.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)


def shift_residual(left, right, dx: int, dy: int):
    x0, y0, x1, y1 = FIELD_AREA
    ox0 = max(x0, x0 + dx)
    ox1 = min(x1, x1 + dx)
    oy0 = max(y0, y0 + dy)
    oy1 = min(y1, y1 + dy)
    if ox1 <= ox0 or oy1 <= oy0:
        return None, 0
    width = ox1 - ox0
    height = oy1 - oy0
    a = left.crop((ox0, oy0, ox1, oy1))
    b = right.crop((ox0 - dx, oy0 - dy, ox1 - dx, oy1 - dy))
    count, _ = diff_mask(a, b, (0, 0, width, height))
    return count, width * height


def best_shift(left, right, radius: int):
    best = None
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            count, area = shift_residual(left, right, dx, dy)
            if count is None:
                continue
            if best is None or count < best[0]:
                best = (count, dx, dy, area)
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dense", required=True, help="directory with fNNN.png")
    parser.add_argument("--target", required=True, help="walk screenshot png")
    parser.add_argument("--radius", type=int, default=12)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    names = sorted(n for n in os.listdir(args.dense)
                   if n.startswith("f") and n.endswith(".png"))
    target = load_rgb(args.target)
    rows = []
    for name in names:
        frame = load_rgb(os.path.join(args.dense, name))
        count, _ = diff_mask(frame, target, (0, 0, frame.width, frame.height))
        field, _ = diff_mask(frame, target, FIELD_AREA)
        best = best_shift(frame, target, args.radius)
        rows.append({
            "frame": name,
            "full_px": count,
            "field_px": field,
            "best_dx": best[1] if best else None,
            "best_dy": best[2] if best else None,
            "best_field_px": best[0] if best else None,
            "best_overlap_px": best[3] if best else None,
        })
    rows.sort(key=lambda r: (r["full_px"], r["field_px"]))
    exact = [r for r in rows if r["full_px"] == 0]
    print(f"target={os.path.basename(args.target)} frames={len(rows)}")
    print(f"exact (0 px) matches: {[r['frame'] for r in exact]}")
    print("top matches:")
    for row in rows[:args.top]:
        print(f"  {row['frame']}  full={row['full_px']:6d}  field={row['field_px']:6d}  "
              f"best=({row['best_dx']:+d},{row['best_dy']:+d}) -> {row['best_field_px']}")

    document = {
        "schema": "konoha.s49-w21c1-dense-match.v1",
        "dense": os.path.abspath(args.dense),
        "target": os.path.abspath(args.target),
        "radius": args.radius,
        "exact_frames": [r["frame"] for r in exact],
        "rows": rows,
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
