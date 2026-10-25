#!/usr/bin/env python3
"""Scan every walk frame of the remake and score it against the original.

For each remake VRAM dump the overlay map is located, decoded into a 16x16
logical cell grid (buffer space) and compared with the original's buffer for
each of the four moments.

Usage::

    python tools/s49_w2/scan_frames.py --vram-dir <dir>
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import find_overlay_map, remake_entry_map, remake_terrain  # noqa: E402
from overlay_ground_truth import load_moment, MOMENTS  # noqa: E402
from buffer_diff import logical_grid_from_entries  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    args = ap.parse_args()

    terrain = remake_terrain()
    originals = {name: load_moment(name).logical_grid() for name in MOMENTS}

    best = {name: None for name in MOMENTS}
    print(f"{'frame':<34} {'overlay':<8} " +
          " ".join(f"{name.split('-')[0]:>12}" for name in MOMENTS))
    for path in sorted(args.vram_dir.glob("*.vram-*.bin")):
        vram = path.read_bytes()
        base = find_overlay_map(vram, terrain=terrain)
        if base < 0:
            print(f"{path.name:<34} {'none':<8}")
            continue
        grid = logical_grid_from_entries(remake_entry_map(vram, base))
        lit = sum(1 for row in grid for f in row if f != "blank")
        cells = []
        for name in MOMENTS:
            orig = originals[name]
            both = only_o = only_r = mism = 0
            for ly in range(16):
                for lx in range(16):
                    a, b = orig[ly][lx], grid[ly][lx]
                    if a != "blank" and b != "blank":
                        both += 1
                        if a != b:
                            mism += 1
                    elif a != "blank":
                        only_o += 1
                    elif b != "blank":
                        only_r += 1
            residual = only_o + only_r + mism
            cells.append(f"{both:>3}/{only_o:>2}/{only_r:>2}/{mism:>2}")
            key = (-residual, both)
            if best[name] is None or key < best[name][0]:
                best[name] = (key, path.name, lit)
        print(f"{path.name:<34} {'0x%05X' % base:<8} " +
              " ".join(f"{c:>12}" for c in cells))

    print("\n=== best frame per moment (both/only_o/only_r/mismatch) ===")
    for name in MOMENTS:
        key, frame, lit = best[name]
        print(f"  {name:<20} residual {-key[0]:>3}  frame {frame}  "
              f"remake lit {lit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
