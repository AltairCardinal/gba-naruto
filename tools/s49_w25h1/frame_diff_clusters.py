#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Per-frame diff clustering for the S49 intro (判定台 #0-#11).

For each (original, remake) frame pair it computes the field-area residual
(field = screen top 128 rows, FIELD_AREA = (0,0,240,128)), clusters the
differing pixels into 8-connected components and reports each component with
its bounding box, area and the dominant colours on both sides.

That turns a single number ("2514 px") into an addressable list of causes:
label strips, unit sprites, marker arrows, palette/black-field tints.

Usage:
    python tools/s49_w25h1/frame_diff_clusters.py --original <dir> --remake <dir> \
        --pairs step-00-base:step-04-A ... [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from pathlib import Path

from PIL import Image

FIELD_AREA = (0, 0, 240, 128)


def load(directory: Path, stem: str) -> Image.Image:
    path = directory / f"{stem}.png"
    if not path.exists():
        raise SystemExit(f"missing frame: {path}")
    return Image.open(path).convert("RGB")


def diff_pixels(a: Image.Image, b: Image.Image, area=FIELD_AREA):
    x0, y0, x1, y1 = area
    pa, pb = a.load(), b.load()
    out = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pa[x, y] != pb[x, y]:
                out.append((x, y))
    return out


def cluster(pixels, gap: int = 1):
    """8-connected components; `gap` = max Chebyshev distance between pixels
    still considered part of the same blob (gap=1 => plain 8-connectivity)."""
    s = set(pixels)
    seen = set()
    comps = []
    for p in s:
        if p in seen:
            continue
        q = deque([p])
        seen.add(p)
        comp = []
        while q:
            cx, cy = q.popleft()
            comp.append((cx, cy))
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    n = (cx + dx, cy + dy)
                    if n in s and n not in seen:
                        seen.add(n)
                        q.append(n)
        comps.append(comp)
    return comps


def classify(box):
    """Coarse region classifier based on the bounding box in field coords."""
    x0, y0, x1, y1 = box
    w = x1 - x0 + 1
    h = y1 - y0 + 1
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    if h <= 10 and w >= 24:
        return "label_strip"
    if y0 < 14 and w >= 20:
        return "top_label"
    if cy < 40:
        return "upper_unit"
    if cy < 96:
        return "mid_unit"
    return "lower_unit"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--pairs", nargs="+", required=True)
    ap.add_argument("--json")
    ap.add_argument("--gap", type=int, default=1)
    ap.add_argument("--min-area", type=int, default=3)
    args = ap.parse_args()

    original = Path(args.original)
    remake = Path(args.remake)
    report = []
    grand = 0
    for pair in args.pairs:
        o_stem, r_stem = pair.split(":")
        a = load(original, o_stem)
        b = load(remake, r_stem)
        px = diff_pixels(a, b)
        grand += len(px)
        comps = cluster(px, args.gap)
        pa, pb = a.load(), b.load()
        entries = []
        for comp in comps:
            if len(comp) < args.min_area:
                continue
            xs = [p[0] for p in comp]
            ys = [p[1] for p in comp]
            box = (min(xs), min(ys), max(xs), max(ys))
            co = Counter(pa[x, y] for x, y in comp).most_common(3)
            cr = Counter(pb[x, y] for x, y in comp).most_common(3)
            entries.append(
                {
                    "area": len(comp),
                    "box": box,
                    "cls": classify(box),
                    "orig_colors": co,
                    "remake_colors": cr,
                }
            )
        entries.sort(key=lambda e: -e["area"])
        by_cls = Counter()
        for e in entries:
            by_cls[e["cls"]] += e["area"]
        print(f"== {o_stem} vs {r_stem}: field diff = {len(px)} px, "
              f"{len(comps)} components (>= {args.min_area} px: {len(entries)})")
        for cls, n in by_cls.most_common():
            print(f"   class {cls:<12} {n:6d} px")
        for e in entries[:14]:
            print(
                f"   area={e['area']:5d} box={e['box']} {e['cls']:<12} "
                f"orig={e['orig_colors'][:2]} remake={e['remake_colors'][:2]}"
            )
        if len(entries) > 14:
            print(f"   ... {len(entries) - 14} more components")
        report.append(
            {
                "original": o_stem,
                "remake": r_stem,
                "field_px": len(px),
                "by_class": dict(by_cls),
                "components": entries,
            }
        )

    print(f"# total field diff across pairs = {grand} px")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print(f"# wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
