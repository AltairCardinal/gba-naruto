#!/usr/bin/env python3
"""Scan every captured remake frame against the original's four moments.

For each original moment (the exported BG2 ground truth) and each remake
VRAM dump, the per-16x16-logical-cell family maps are compared over all 256
possible grid offsets.  The best (moment, frame, offset) triple is the
coordinate correspondence between the two sides.

Usage::

    python tools/s49_overlay_align/scan_remake_frames.py \
        --vram-dir build/s49-overlay-g/remake --out build/s49-overlay-g/scan.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from compare_overlay_families import (  # noqa: E402
    best_offset,
    find_overlay_map,
    original_cells,
    remake_cells,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print(f"ERR no VRAM dumps under {args.vram_dir}")
        return 2

    moments = {
        name: original_cells(name)
        for name in ("field-frame-v1", "movegrid-frame-v1",
                     "grid16-frame-v1", "banner-frame-v1")
    }

    rows = []
    for path in dumps:
        vram = path.read_bytes()
        base = find_overlay_map(vram)
        if base < 0:
            print(f"  {path.name}: no overlay map")
            continue
        right, info = remake_cells(vram, base)
        for name, left in moments.items():
            best = best_offset(left, right)
            rows.append({
                "frame": path.name,
                "moment": name,
                "offset": best["offset"],
                "original_lit": best["original_lit"],
                "remake_lit": best["remake_lit"],
                "both_lit": best["both_lit"],
                "original_only": best["original_only"],
                "remake_only": best["remake_only"],
                "family_mismatches": best["family_mismatches"],
                "exact": best["exact"],
                "differences": best["differences"],
            })
        best_row = max(
            (r for r in rows if r["frame"] == path.name),
            key=lambda r: r["both_lit"] - r["family_mismatches"])
        print(f"  {path.name:<28} best moment {best_row['moment']:<20} "
              f"offset {best_row['offset']}  both {best_row['both_lit']:>3}  "
              f"orig-only {best_row['original_only']:>3}  "
              f"remake-only {best_row['remake_only']:>3}  "
              f"mismatch {best_row['family_mismatches']:>3}")

    print("\n=== best frame per original moment ===")
    summary = {}
    for name in moments:
        candidates = [r for r in rows if r["moment"] == name]
        if not candidates:
            continue
        best = max(candidates,
                   key=lambda r: (r["both_lit"] - r["family_mismatches"],
                                  -r["original_only"] - r["remake_only"]))
        summary[name] = best
        print(f"  {name:<20} {best['frame']:<28} offset {best['offset']}  "
              f"both {best['both_lit']:>3}  original-only {best['original_only']:>3}  "
              f"remake-only {best['remake_only']:>3}  "
              f"mismatches {best['family_mismatches']:>3}  exact {best['exact']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"rows": rows, "summary": summary},
                       ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
