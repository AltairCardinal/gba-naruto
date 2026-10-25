#!/usr/bin/env python3
"""Classify *why* a frame pair differs: camera shift, palette shade, or content.

Why this tool exists
--------------------
`tools/s49_w20e/shift_probe.py` answers "does a translation collapse the
residual".  That is only one of three possible causes, and it cannot tell the
other two apart:

  * **camera / scenery offset** - the same map, seen from another window.
  * **palette / shade difference** - the same map and the same window, but the
    colours are shifted (GBA palettes are per-BG, so a palette swap turns every
    grass pixel into a "difference" while the geometry is identical).
  * **content difference** - different tiles, different sprites, a different
    overlay.

The bench metric (`s49_fidelity_report.pixels.diff_mask`) only counts
*whether* a pixel differs, never *how much*.  This tool adds the missing
magnitudes:

  * a histogram of the per-pixel maximum channel difference
    (1-3 / 4-7 / 8-15 / 16-31 / 32-63 / 64+),
  * the repository's own `structure_match` score (block means within a
    tolerance), which survives a palette shift,
  * a row profile of the differences.

Reading the three together gives a decidable verdict per frame pair.

Usage
-----
    python tools/s49_w20e/residual_cause.py \
        --original build/.../capture-original \
        --remake   build/w20-e3/capture-remake \
        --offset 4 --out build/w20-e3/residual-cause.json

Exit code 0 always (analysis tool).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import (  # noqa: E402
    block_means,
    diff_mask,
    load_rgb,
    structure_match,
)

FIELD_AREA = (0, 0, 240, 128)
FULL_BOX = (0, 0, 240, 160)

BUCKETS = ((1, 3), (4, 7), (8, 15), (16, 31), (32, 63), (64, 255))


def magnitude_histogram(original, remake, box) -> dict:
    """How much do the differing pixels differ by?"""
    x0, y0, x1, y1 = box
    left = original.crop(box)
    right = remake.crop(box)
    _, mask = diff_mask(left, right, (0, 0, x1 - x0, y1 - y0))
    histogram = mask.histogram()
    out = {}
    total = 0
    for low, high in BUCKETS:
        count = sum(histogram[low:high + 1])
        out[f"{low}-{high}"] = count
        total += count
    out["differing_total"] = total
    out["pixels_total"] = (x1 - x0) * (y1 - y0)
    return out


def row_profile(original, remake, box) -> list[int]:
    x0, y0, x1, y1 = box
    _, mask = diff_mask(original.crop(box), remake.crop(box),
                        (0, 0, x1 - x0, y1 - y0))
    data = mask.load()
    width = x1 - x0
    height = y1 - y0
    return [sum(1 for column in range(width) if data[column, row])
            for row in range(height)]


def list_frames(directory: str) -> list[str]:
    return sorted(
        name for name in os.listdir(directory)
        if name.startswith("step-") and name.endswith(".png")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--offset", type=int, default=4)
    parser.add_argument("--only", default="")
    parser.add_argument("--tolerance", type=int, default=8)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    original_names = list_frames(args.original)
    remake_names = list_frames(args.remake)
    originals = {name: load_rgb(os.path.join(args.original, name))
                 for name in original_names}
    remakes = {name: load_rgb(os.path.join(args.remake, name))
               for name in remake_names}

    only = [name for name in args.only.split(",") if name] if args.only else []

    print(f"offset {args.offset:+d}   field area {FIELD_AREA}   "
          f"structure tolerance {args.tolerance}")
    print(f"{'original':<16}{'remake':<16}{'diff px':>9}{'1-3':>8}{'4-7':>7}"
          f"{'8-15':>7}{'16-31':>7}{'32-63':>7}{'64+':>7}{'struct':>8}")
    report = []
    for index, oname in enumerate(original_names):
        if only and oname not in only:
            continue
        rindex = index + args.offset
        if rindex >= len(remake_names):
            continue
        rname = remake_names[rindex]
        left = originals[oname]
        right = remakes[rname]
        hist = magnitude_histogram(left, right, FIELD_AREA)
        blocks_left = block_means(left, FIELD_AREA)
        blocks_right = block_means(right, FIELD_AREA)
        structure = structure_match(blocks_left, blocks_right, args.tolerance)
        rows = row_profile(left, right, FIELD_AREA)
        print(f"{oname:<16}{rname:<16}{hist['differing_total']:>9}"
              f"{hist['1-3']:>8}{hist['4-7']:>7}{hist['8-15']:>7}"
              f"{hist['16-31']:>7}{hist['32-63']:>7}{hist['64-255']:>7}"
              f"{structure:>8.3f}")
        report.append({
            "original": oname,
            "remake": rname,
            "magnitudes": hist,
            "structure_match": round(structure, 4),
            "row_profile": rows,
        })

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({
                "original_dir": args.original,
                "remake_dir": args.remake,
                "offset": args.offset,
                "field_area": list(FIELD_AREA),
                "tolerance": args.tolerance,
                "per_frame": report,
            }, handle, ensure_ascii=False, indent=1)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
