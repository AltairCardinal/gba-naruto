#!/usr/bin/env python3
"""Probe whether a frame pair differs by a *camera translation* or by *content*.

Why this tool exists
--------------------
`tools/s49_wave18/align_capture_steps.py` aligns the two capture walks by a
**step offset** (which remake frame belongs to which original frame) and then
reports the residual in pixels.  That answers "which moment is this", but not
"why do the pixels differ".

Two very different causes produce the same big residual:

  * **camera / scenery offset** - the remake shows the same map, but the
    visible window sits somewhere else.  Then shifting one frame by the
    camera delta collapses the residual.
  * **content difference** - the remake draws different tiles, different
    sprites, an extra overlay, ...  Then no shift helps.

This tool measures that directly: for a pair of frames it searches an integer
translation `(dx, dy)` of the remake frame and reports

  * the residual at `(0, 0)` (what the bench charges today),
  * the best `(dx, dy)` and its residual (what a camera fix could buy),
  * the residual normalised back to the full field area, so shifts with a
    smaller overlap stay comparable with the `(0, 0)` reading,
  * a row profile of the difference, so a band (e.g. a forest strip at the
    top) can be told apart from a whole-frame difference.

Everything is pure PIL; the pixel semantics are the repository's own
(`s49_fidelity_report.pixels.diff_mask`: a pixel differs when any channel
differs).

Usage
-----
    python tools/s49_w20e/shift_probe.py \
        --original build/.../capture-original \
        --remake   build/w20-e3/capture-remake \
        --offset 4 --radius 32 --out build/w20-e3/shift-probe.json

Exit code 0 always (analysis tool); the verdict is printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)
FULL_BOX = (0, 0, 240, 160)


def list_frames(directory: str) -> list[str]:
    return sorted(
        name for name in os.listdir(directory)
        if name.startswith("step-") and name.endswith(".png")
    )


def shifted_residual(original, remake, box, dx: int, dy: int):
    """(differing pixels, overlap area) for the remake frame moved by (dx, dy).

    ``dx`` is the amount the *remake* content moves to the right, ``dy`` the
    amount it moves down.  Only the region that exists in both frames is
    compared; the caller normalises it back to the full field area.
    """
    x0, y0, x1, y1 = box
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


def best_shift(original, remake, box, radius: int):
    best = None
    zero = shifted_residual(original, remake, box, 0, 0)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            count, area = shifted_residual(original, remake, box, dx, dy)
            if count is None:
                continue
            if best is None or count < best[0]:
                best = (count, dx, dy, area)
    return zero, best


def row_profile(original, remake, box, dx: int, dy: int) -> list[int]:
    """Differing pixels per row of the field area at the given shift."""
    x0, y0, x1, y1 = box
    ox0 = max(x0, x0 + dx)
    ox1 = min(x1, x1 + dx)
    oy0 = max(y0, y0 + dy)
    oy1 = min(y1, y1 + dy)
    if ox1 <= ox0 or oy1 <= oy0:
        return []
    left = original.crop((ox0, oy0, ox1, oy1))
    right = remake.crop((ox0 - dx, oy0 - dy, ox1 - dx, oy1 - dy))
    _, mask = diff_mask(left, right, (0, 0, ox1 - ox0, oy1 - oy0))
    data = mask.load()
    counts = []
    for row in range(oy1 - oy0):
        count = 0
        for column in range(ox1 - ox0):
            if data[column, row]:
                count += 1
        counts.append(count)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--offset", type=int, default=4,
                        help="step offset: original frame i pairs with remake frame i+offset")
    parser.add_argument("--radius", type=int, default=32,
                        help="search radius in pixels for the translation")
    parser.add_argument("--only", default="",
                        help="comma separated original frame names to probe")
    parser.add_argument("--scan-all-remake", action="store_true",
                        help="also search every remake frame for every original frame")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    original_names = list_frames(args.original)
    remake_names = list_frames(args.remake)
    print(f"original frames: {len(original_names)}   remake frames: {len(remake_names)}")
    print(f"offset {args.offset:+d}   shift radius +/-{args.radius} px")

    originals = {name: load_rgb(os.path.join(args.original, name))
                 for name in original_names}
    remakes = {name: load_rgb(os.path.join(args.remake, name))
               for name in remake_names}

    only = [name for name in args.only.split(",") if name] if args.only else []

    report = []
    header = f"{'original':<16}{'remake':<16}{'px@0,0':>9}{'best dx':>8}{'best dy':>8}{'best px':>9}{'norm px':>9}{'overlap%':>9}"
    print("\n=== per frame: residual vs best camera translation ===")
    print(header)
    for index, oname in enumerate(original_names):
        if only and oname not in only:
            continue
        rindex = index + args.offset
        if rindex >= len(remake_names):
            continue
        rname = remake_names[rindex]
        zero, best = best_shift(originals[oname], remakes[rname], FIELD_AREA, args.radius)
        zero_count = zero[0] if zero else 0
        if best is None:
            continue
        count, dx, dy, area = best
        overlap_pct = 100.0 * area / (FIELD_AREA[2] - FIELD_AREA[0]) / (
            FIELD_AREA[3] - FIELD_AREA[1])
        norm = int(round(count * (FIELD_AREA[2] - FIELD_AREA[0]) *
                         (FIELD_AREA[3] - FIELD_AREA[1]) / area)) if area else 0
        print(f"{oname:<16}{rname:<16}{zero_count:>9}{dx:>8}{dy:>8}{count:>9}"
              f"{norm:>9}{overlap_pct:>8.1f}%")
        report.append({
            "original": oname,
            "remake": rname,
            "px_at_zero_shift": zero_count,
            "best_dx": dx,
            "best_dy": dy,
            "best_px": count,
            "best_px_normalised": norm,
            "overlap_area": area,
        })

    if args.scan_all_remake:
        print("\n=== best (remake frame, shift) for every original frame ===")
        print(f"{'original':<16}{'best remake':<16}{'best dx':>8}{'best dy':>8}{'best px':>9}")
        for oname in original_names:
            if only and oname not in only:
                continue
            best = None
            for rname in remake_names:
                zero, candidate = best_shift(originals[oname], remakes[rname],
                                             FIELD_AREA, args.radius)
                if candidate is None:
                    continue
                count, dx, dy, area = candidate
                if best is None or count < best[0]:
                    best = (count, rname, dx, dy)
            if best is None:
                continue
            count, rname, dx, dy = best
            print(f"{oname:<16}{rname:<16}{dx:>8}{dy:>8}{count:>9}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({
                "original_dir": args.original,
                "remake_dir": args.remake,
                "offset": args.offset,
                "radius": args.radius,
                "field_area": list(FIELD_AREA),
                "per_frame": report,
            }, handle, ensure_ascii=False, indent=1)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
