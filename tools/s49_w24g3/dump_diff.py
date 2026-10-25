#!/usr/bin/env python3
"""W24-G3: dump every differing pixel of the settlement screen, grouped by
colour pair, plus the per-digit shading bitmaps of the 合計 row.

Usage:
  python tools/s49_w24g3/dump_diff.py [--out build/w24-g3]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]

TRUTH = REPO / "build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png"
REMAKE = REPO / "build/w23-f4/run/shots/page-001-result.png"

LIGHT = (231, 99, 66)
DARK = (231, 24, 0)
OUTLINE = (231, 173, 140)
CREAM = (231, 247, 214)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "build/w24-g3"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    truth = Image.open(TRUTH).convert("RGB")
    remake = Image.open(REMAKE).convert("RGB")

    groups: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
    rows = defaultdict(list)
    for y in range(160):
        for x in range(240):
            pt = truth.getpixel((x, y))
            pr = remake.getpixel((x, y))
            if pt != pr:
                groups[(pt, pr)].append((x, y))
                rows[y].append((x, pt, pr))

    report = {
        "groups": [
            {
                "truth": list(k[0]),
                "remake": list(k[1]),
                "px": len(v),
                "rows": sorted({y for _, y in v}),
                "cols": sorted({x for x, _ in v}),
            }
            for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))
        ]
    }

    # The frame line columns, per row.
    line_rows = {}
    for y in range(109, 154):
        cols = sorted({x for x, _, _ in rows.get(y, [])})
        if cols:
            line_rows[y] = cols
    report["frame_line_columns"] = line_rows

    # Per-digit shading bitmap of the 合計 row (the truth's own pixels).
    digits = []
    for cx0, cx1 in [[97, 102], [105, 110], [113, 118],
                      [153, 158], [162, 167], [169, 174],
                      [210, 214], [217, 222], [225, 230]]:
        art = []
        for y in range(139, 150):
            row = ""
            for x in range(cx0, cx1):
                p = truth.getpixel((x, y))
                row += {LIGHT: "L", DARK: "D", OUTLINE: "o", CREAM: "."}.get(p, "?")
            art.append(row)
        digits.append({"x0": cx0, "x1": cx1, "art": art})
    report["digits_truth_art"] = digits

    # Same for the remake (all D) so the footprints can be compared.
    rem_digits = []
    for cx0, cx1 in [[97, 102], [105, 110], [113, 118],
                      [153, 158], [162, 167], [169, 174],
                      [210, 214], [217, 222], [225, 230]]:
        art = []
        for y in range(139, 150):
            row = ""
            for x in range(cx0, cx1):
                p = remake.getpixel((x, y))
                row += {LIGHT: "L", DARK: "D", OUTLINE: "o", CREAM: "."}.get(p, "?")
            art.append(row)
        rem_digits.append({"x0": cx0, "x1": cx1, "art": art})
    report["digits_remake_art"] = rem_digits

    with open(out_dir / "settlement-diff-groups.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("=== diff groups (truth -> remake) ===")
    for g in report["groups"]:
        print(f"  {g['px']:4d} px  {g['truth']} -> {g['remake']}"
              f"  rows {g['rows'][0]}..{g['rows'][-1]}"
              f"  ncols {len(g['cols'])}")
    print()
    print("=== frame line columns per row ===")
    for y in sorted(line_rows):
        print(f"  y={y}: {line_rows[y]}")
    print()
    for i, d in enumerate(digits):
        print(f"--- digit {i} (x {d['x0']}..{d['x1']}) TRUTH | REMAKE")
        for a, b in zip(d["art"], rem_digits[i]["art"]):
            print(f"   {a}   |   {b}")


if __name__ == "__main__":
    main()
