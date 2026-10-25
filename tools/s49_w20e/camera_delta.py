#!/usr/bin/env python3
"""Measure the camera translation between two frames, with an overlap floor.

Why this tool exists
--------------------
`tools/s49_w20e/shift_probe.py` searches a translation without constraining
the overlap, so a big shift can "win" by comparing a sliver of the frame.
This tool keeps only shifts whose overlap covers at least `--min-overlap` of
the field area, and reports three numbers per candidate:

  * the residual over the overlap,
  * the residual normalised back to the full field area,
  * the repository's `structure_match` score (survives a palette shift).

Two modes:

  ``--mode consecutive``  same side, frame *i* against frame *i+1*.  Both
                          frames show nearly the same content, so the best
                          translation is the *camera velocity* of that step.

  ``--mode cross``        original frame *i* against remake frame *i+offset*,
                          searched over a wide translation range.  This is the
                          camera *offset* between the two sides.

Usage
-----
    python tools/s49_w20e/camera_delta.py --mode consecutive \
        --original build/.../capture-original --remake build/w20-e3/capture-remake
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
FIELD_W = FIELD_AREA[2] - FIELD_AREA[0]
FIELD_H = FIELD_AREA[3] - FIELD_AREA[1]
FIELD_PIXELS = FIELD_W * FIELD_H


def overlap_residual(original, remake, dx: int, dy: int):
    """(differing pixels, overlap area) for the remake frame moved by (dx, dy)."""
    x0, y0, x1, y1 = FIELD_AREA
    ox0 = max(x0, x0 + dx)
    ox1 = min(x1, x1 + dx)
    oy0 = max(y0, y0 + dy)
    oy1 = min(y1, y1 + dy)
    if ox1 <= ox0 or oy1 <= oy0:
        return None, 0
    width = ox1 - ox0
    height = oy1 - oy0
    left = original.crop((ox0, oy0, ox1, oy1))
    right = remake.crop((ox0 - dx, oy0 - dy, ox1 - dx, oy1 - dy))
    count, _ = diff_mask(left, right, (0, 0, width, height))
    return count, width * height


def search(original, remake, radius_x: int, radius_y: int, min_overlap: int):
    best = None
    zero, zero_area = overlap_residual(original, remake, 0, 0)
    for dy in range(-radius_y, radius_y + 1):
        for dx in range(-radius_x, radius_x + 1):
            count, area = overlap_residual(original, remake, dx, dy)
            if count is None or area < min_overlap:
                continue
            if best is None or count < best[0]:
                best = (count, dx, dy, area)
    return (zero, zero_area), best


def structure_at(original, remake, dx: int, dy: int, tolerance: int) -> float:
    x0, y0, x1, y1 = FIELD_AREA
    ox0 = max(x0, x0 + dx)
    ox1 = min(x1, x1 + dx)
    oy0 = max(y0, y0 + dy)
    oy1 = min(y1, y1 + dy)
    if ox1 <= ox0 or oy1 <= oy0:
        return 0.0
    left = original.crop((ox0, oy0, ox1, oy1))
    right = remake.crop((ox0 - dx, oy0 - dy, ox1 - dx, oy1 - dy))
    return structure_match(block_means(left, (0, 0, ox1 - ox0, oy1 - oy0)),
                            block_means(right, (0, 0, ox1 - ox0, oy1 - oy0)),
                            tolerance)


def list_frames(directory: str) -> list[str]:
    return sorted(
        name for name in os.listdir(directory)
        if name.startswith("step-") and name.endswith(".png")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--mode", choices=("consecutive", "cross"), required=True)
    parser.add_argument("--offset", type=int, default=4)
    parser.add_argument("--radius-x", type=int, default=48)
    parser.add_argument("--radius-y", type=int, default=32)
    parser.add_argument("--min-overlap", type=float, default=0.35,
                        help="minimum share of the field area that must overlap")
    parser.add_argument("--tolerance", type=int, default=8)
    parser.add_argument("--only", default="")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    min_overlap_px = int(args.min_overlap * FIELD_PIXELS)
    original_names = list_frames(args.original)
    remake_names = list_frames(args.remake)
    originals = {name: load_rgb(os.path.join(args.original, name))
                 for name in original_names}
    remakes = {name: load_rgb(os.path.join(args.remake, name))
               for name in remake_names}
    only = [name for name in args.only.split(",") if name] if args.only else []

    print(f"mode {args.mode}   radius x +/-{args.radius_x} y +/-{args.radius_y}"
          f"   min overlap {args.min_overlap:.0%} ({min_overlap_px} px)")
    report = []
    if args.mode == "consecutive":
        for label, names, images in (("original", original_names, originals),
                                     ("remake", remake_names, remakes)):
            print(f"\n=== {label}: frame i vs frame i+1 (camera velocity) ===")
            print(f"{'pair':<28}{'px@0,0':>9}{'best dx':>8}{'best dy':>8}"
                  f"{'best px':>9}{'overlap%':>9}{'struct@0':>9}{'struct@best':>12}")
            for index in range(len(names) - 1):
                left = names[index]
                right = names[index + 1]
                if only and left not in only:
                    continue
                zero, best = search(images[left], images[right],
                                    args.radius_x, args.radius_y, min_overlap_px)
                if best is None:
                    continue
                count, dx, dy, area = best
                struct_zero = structure_at(images[left], images[right], 0, 0,
                                           args.tolerance)
                struct_best = structure_at(images[left], images[right], dx, dy,
                                           args.tolerance)
                print(f"{left + ' -> ' + right:<28}{zero[0]:>9}{dx:>8}{dy:>8}"
                      f"{count:>9}{100.0 * area / FIELD_PIXELS:>8.1f}%"
                      f"{struct_zero:>9.3f}{struct_best:>12.3f}")
                report.append({
                    "side": label, "from": left, "to": right,
                    "px_at_zero": zero[0], "best_dx": dx, "best_dy": dy,
                    "best_px": count, "overlap_area": area,
                    "structure_at_zero": round(struct_zero, 4),
                    "structure_at_best": round(struct_best, 4),
                })
    else:
        print(f"\n=== cross side: original i vs remake i+{args.offset} ===")
        print(f"{'original':<16}{'remake':<16}{'px@0,0':>9}{'best dx':>8}"
              f"{'best dy':>8}{'best px':>9}{'overlap%':>9}{'norm px':>9}"
              f"{'struct@best':>12}")
        for index, oname in enumerate(original_names):
            if only and oname not in only:
                continue
            rindex = index + args.offset
            if rindex >= len(remake_names):
                continue
            rname = remake_names[rindex]
            zero, best = search(originals[oname], remakes[rname],
                                args.radius_x, args.radius_y, min_overlap_px)
            if best is None:
                continue
            count, dx, dy, area = best
            struct_best = structure_at(originals[oname], remakes[rname], dx, dy,
                                       args.tolerance)
            norm = int(round(count * FIELD_PIXELS / area))
            print(f"{oname:<16}{rname:<16}{zero[0]:>9}{dx:>8}{dy:>8}{count:>9}"
                  f"{100.0 * area / FIELD_PIXELS:>8.1f}%{norm:>9}"
                  f"{struct_best:>12.3f}")
            report.append({
                "original": oname, "remake": rname,
                "px_at_zero": zero[0], "best_dx": dx, "best_dy": dy,
                "best_px": count, "overlap_area": area,
                "best_px_normalised": norm,
                "structure_at_best": round(struct_best, 4),
            })

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({
                "mode": args.mode,
                "original_dir": args.original,
                "remake_dir": args.remake,
                "offset": args.offset,
                "radius_x": args.radius_x,
                "radius_y": args.radius_y,
                "min_overlap": args.min_overlap,
                "pairs": report,
            }, handle, ensure_ascii=False, indent=1)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
