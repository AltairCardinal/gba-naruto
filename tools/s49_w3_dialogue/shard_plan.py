"""W3: the shard plan of the original's entry transition.

The overlay (the black window) of the entry transition is drawn with OBJ
sprites.  A sprite may not exceed 64x64 px, so the screen is covered by a
grid of shards.  Not every shard needs its own tiles: a shard that is
completely black is the same shape as every other completely black shard
and can share one run of tiles.

This probe measures, for every level of the transition and for two shard
sizes, how many shards are

    empty    - nothing to draw (the picture is already visible there)
    solid    - completely black (one shared run of tiles can draw it)
    partial  - cut by the star's edge (needs its own tiles)

and how many *distinct* partial patterns the level has.  The result is the
placement table of the transition and the number of OBJ tiles it needs.
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


def overlay(path: pathlib.Path):
    """One bit per pixel: 1 where the overlay paints black."""
    hole = star_mask(path)
    return [[0 if hole[y][x] else 1 for x in range(WIDTH)]
            for y in range(HEIGHT)]


def shard_plan(overlay_bits, shard):
    empty = solid = partial = 0
    patterns = {}
    for y in range(0, HEIGHT, shard):
        for x in range(0, WIDTH, shard):
            block = []
            for dy in range(shard):
                for dx in range(shard):
                    py = min(y + dy, HEIGHT - 1)
                    px = min(x + dx, WIDTH - 1)
                    block.append(overlay_bits[py][px])
            total = sum(block)
            if total == 0:
                empty += 1
            elif total == len(block):
                solid += 1
            else:
                partial += 1
                patterns[tuple(block)] = patterns.get(tuple(block), 0) + 1
    return {
        "shards": empty + solid + partial,
        "empty": empty,
        "solid": solid,
        "partial": partial,
        "distinct_partial": len(patterns),
        "tiles_per_shard": (shard // 8) * (shard // 8),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", required=True)
    parser.add_argument("--levels", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    directory = pathlib.Path(args.frames)
    levels = json.loads(
        pathlib.Path(args.levels).read_text(encoding="utf-8"))["levels"]

    report = []
    print(f"{'lvl':>3} {'frame':>5} {'area':>6} | "
          f"16px: solid partial distinct tiles sprites | "
          f"32px: solid partial distinct tiles sprites")
    for level in levels:
        if level["frames"] <= 0:
            continue
        frame = level["first_frame"]
        path = directory / f"frame-{frame:05d}.png"
        if not path.exists():
            continue
        bits = overlay(path)
        entry = {"level": level["level"], "frame": frame,
                 "frames": level["frames"], "area": level["area"], "shards": {}}
        text = []
        for shard in (16, 32):
            plan = shard_plan(bits, shard)
            # A solid shard shares one run of tiles with every other solid
            # shard; a partial shard needs its own run.
            tiles = plan["tiles_per_shard"] * (plan["distinct_partial"] + 1)
            plan["obj_tiles"] = tiles
            # The solid bulk is drawn with 64x64 sprites, so sixteen solid
            # 16 px shards fit into one of them; the partial shards each need
            # a sprite of their own.
            plan["sprites"] = plan["partial"] + (
                (plan["solid"] + 15) // 16 if shard == 16 else plan["solid"])
            entry["shards"][str(shard)] = plan
            text.append(f"{plan['solid']:3d} {plan['partial']:3d} "
                        f"{plan['distinct_partial']:4d} "
                        f"{tiles:5d} {plan['sprites']:4d}")
        report.append(entry)
        print(f"{level['level']:3d} {frame:5d} {level['area']:6d} | "
              + " | ".join(text))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
