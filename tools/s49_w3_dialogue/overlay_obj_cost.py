"""W3: the OBJ cost of the original's entry transition, per level.

The transition's black overlay is drawn with OBJ sprites.  A sprite may not
exceed 64x64 px, so the screen is covered by a grid of shards.  The number
of *distinct* tile patterns the overlay needs in one level is the number of
OBJ tiles that level occupies in VRAM, and the number of sprites is the
number of OAM entries it needs.

This probe measures both, for three shard sizes, on every measured level of
the transition.  It answers one question:

    how many OBJ tiles does the original's entry transition really need,
    and how does that number change with the shard size?
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "s49_starfield"))

from star_geometry import star_mask  # noqa: E402  (shared, read only)

WIDTH = 240
HEIGHT = 160
SHARD_SIZES = (8, 16, 32)


def overlay_cells(path: pathlib.Path, shard: int):
    """The cells of the black overlay, as one bit per pixel."""
    hole = star_mask(path)
    cells = []
    for y in range(0, HEIGHT, shard):
        for x in range(0, WIDTH, shard):
            block = []
            for dy in range(shard):
                for dx in range(shard):
                    py = min(y + dy, HEIGHT - 1)
                    px = min(x + dx, WIDTH - 1)
                    block.append(0 if hole[py][px] else 1)
            cells.append((x, y, tuple(block)))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", required=True)
    parser.add_argument("--levels", required=True,
                        help="the JSON written by entry_levels.py")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    directory = pathlib.Path(args.frames)
    levels = json.loads(pathlib.Path(args.levels).read_text(encoding="utf-8"))["levels"]

    report = []
    print(f"{'lvl':>3} {'frame':>5} {'area':>6} | "
          + " | ".join(f"{s}px: tiles/sprites/distinct"
                       for s in SHARD_SIZES))
    for level in levels:
        if level["frames"] <= 0:
            continue
        frame = level["first_frame"]
        path = directory / f"frame-{frame:05d}.png"
        if not path.exists():
            continue
        entry = {
            "level": level["level"],
            "frame": frame,
            "frames": level["frames"],
            "area": level["area"],
            "shards": {},
        }
        cells_text = []
        for shard in SHARD_SIZES:
            cells = overlay_cells(path, shard)
            distinct = {cell[2] for cell in cells}
            tiles = len(distinct) * (shard // 8) * (shard // 8)
            sprites = len(cells)
            entry["shards"][str(shard)] = {
                "sprites": sprites,
                "distinct_patterns": len(distinct),
                "obj_tiles": tiles,
            }
            cells_text.append(f"{sprites:4d}/{len(distinct):3d}/{tiles:4d}")
        report.append(entry)
        print(f"{level['level']:3d} {frame:5d} {level['area']:6d} | "
              + " | ".join(cells_text))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
