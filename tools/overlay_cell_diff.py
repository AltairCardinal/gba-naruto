#!/usr/bin/env python3
"""Cell-level diff between the remake's overlay layer and the original's.

The original's BG2 overlay is exported as a cell-level ground truth: 1,024
cells, each with a family (blank / solid / edge / hatch / line_alt / band), a
palette bank and a tile index, for four moments of the S49 battle.

The remake paints the same layer, but with a different cell size (32x16 px
instead of 16x16), a different family vocabulary and a shared palette.  So
the comparison is done on the *populated pattern* -- which cells carry an
overlay tile -- and the result is reported per moment:

    overlap       cells lit by both sides
    remake-only   cells the remake lights and the original does not
    original-only cells the original lights and the remake does not

The "original-only" cells are grouped by the original's family, which is the
actionable output: it says *which kind* of cell the remake is missing.

Usage::

    python tools/overlay_cell_diff.py --dump-dir build/ovl2 --prefix v \
        --out build/ovl2/cell-diff.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
from collections import Counter

GT = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)
MOMENTS = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1")


def load_moment(moment: str) -> list[dict]:
    path = GT / f"{moment}.bg2-tilemap.json"
    return json.loads(path.read_text(encoding="utf-8")).get("cells", [])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump-dir", type=pathlib.Path, required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--base", type=lambda v: int(v, 0), default=0,
                    help="VRAM offset of the overlay tilemap inside a full-VRAM dump")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    dumps = sorted(args.dump_dir.glob(f"{args.prefix}-*.bin"))
    if not dumps:
        print(f"ERR no dumps matching {args.prefix}-*.bin under {args.dump_dir}")
        return 2

    # Pick the dump with the most populated cells in the overlay map: that is
    # the moment the remake's overlay is fully drawn.
    best = None
    for path in dumps:
        raw = path.read_bytes()
        if args.base + 2048 > len(raw):
            continue
        cells = struct.unpack_from("<1024H", raw, args.base)
        populated = sum(1 for c in cells if c)
        if best is None or populated > best[0]:
            best = (populated, path, cells)
    populated, path, got = best
    print(f"remake overlay: {path.name}  {populated} populated cells  "
          f"({len(set(got))} distinct entries)")
    print()

    results = {}
    for moment in MOMENTS:
        cells = load_moment(moment)
        blank = {int(c["raw_hex"], 16) for c in cells if c.get("family") == "blank"}
        want = [0 if int(c["raw_hex"], 16) in blank else 1 for c in cells]
        have = [1 if c else 0 for c in got]
        n = min(len(want), len(have))
        overlap = sum(1 for i in range(n) if want[i] and have[i])
        remake_only = [i for i in range(n) if have[i] and not want[i]]
        original_only = [i for i in range(n) if want[i] and not have[i]]
        families = Counter(cells[i].get("family") for i in original_only)
        results[moment] = {
            "remake_populated": populated,
            "original_populated": sum(want),
            "overlap": overlap,
            "remake_only": len(remake_only),
            "original_only": len(original_only),
            "original_only_by_family": dict(families),
            "original_only_cell_indices": original_only[:512],
            "remake_only_cell_indices": remake_only[:512],
        }
        print(f"=== {moment} ===")
        print(f"  original lit {sum(want):>4}   remake lit {populated:>4}")
        print(f"  overlap {overlap:>4}   remake-only {len(remake_only):>4}"
              f"   original-only {len(original_only):>4}")
        if families:
            print("  original-only by family: "
                  + ", ".join(f"{k}={v}" for k, v in families.most_common()))
        print()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"dump": path.name, "results": results},
                       ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
