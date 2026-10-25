#!/usr/bin/env python3
"""Per-palette-bank colour census for a GBA regular-BG image.

A **4bpp** background draws every 8x8 tile from exactly **one** 16-entry
palette bank, and the bank is selected per tile by the tilemap entry's bits
12-15.  A 4bpp background therefore owns **up to 16 banks** (the whole of
palette RAM), and a tile can be moved to any bank as long as the map cell's
palette-bank bits are updated with it.

The question this tool answers is: *how many banks does this image need, and
can the banks be chosen so that no pixel changes colour?*

Three groupings are reported:

1. ``fixed:<n>``  - consecutive tiles in file order (row-major over the image)
   grouped ``n`` tiles at a time.  This is the "bank per n tiles" shape that a
   fixed-stride exporter produces.  ``n = 1`` is the finest case.
2. ``greedy``     - minimum number of 16-colour banks that cover every tile
   (a tile's colours must all lie inside its bank).  This is an **upper
   bound** on the true minimum (greedy is not optimal).
3. ``optimistic`` - a lower bound on the number of banks: the number of
   distinct colours divided by 16, rounded up (each bank holds at most 16).

Usage:
    python probe_palette_banks.py --images <bmp> [<bmp> ...] [--out <json>]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

from PIL import Image


def load_tiles(path: pathlib.Path) -> list[set[int]]:
    image = Image.open(path)
    if image.mode != "P":
        image = image.convert("P", palette=Image.ADAPTIVE, colors=256)
    pixels = list(image.getdata())
    width, height = image.size
    tiles: list[set[int]] = []
    for by in range(0, height - 7, 8):
        for bx in range(0, width - 7, 8):
            distinct: set[int] = set()
            for y in range(by, by + 8):
                row = y * width
                for x in range(bx, bx + 8):
                    distinct.add(pixels[row + x])
            tiles.append(distinct)
    return tiles


def fixed_groups(tiles: list[set[int]], size: int) -> dict[str, object]:
    groups = []
    for start in range(0, len(tiles), size):
        chunk = tiles[start : start + size]
        distinct: set[int] = set()
        for t in chunk:
            distinct |= t
        groups.append(distinct)
    sizes = [len(g) for g in groups]
    over = [i for i, s in enumerate(sizes) if s > 16]
    hist = Counter(sizes)
    return {
        "group_size": size,
        "groups": len(groups),
        "max_distinct_colors_in_group": max(sizes) if sizes else 0,
        "groups_over_16_colors": len(over),
        "groups_over_16_indices_sample": over[:20],
        "distinct_color_histogram": dict(sorted(hist.items())),
        "lossless": len(over) == 0,
    }


def greedy_banks(tiles: list[set[int]], limit: int = 40) -> dict[str, object]:
    """Greedy bank cover; an UPPER bound on the minimum number of banks."""
    remaining = list(tiles)
    banks = 0
    while remaining and banks < limit:
        freq = Counter(c for t in remaining for c in t)
        top = {c for c, _ in freq.most_common(16)}
        # pick the tile that is most coverable, then grow the bank to cover it
        best = min(remaining, key=lambda t: (len(t - top), -len(t)))
        bank = set(best)
        still = [t for t in remaining if t <= bank]
        if not still:
            bank = top
            still = [t for t in remaining if t <= bank]
        banks += 1
        remaining = [t for t in remaining if t not in still]
    distinct_colors = len({c for t in tiles for c in t})
    return {
        "greedy_banks_upper_bound": banks,
        "greedy_exhausted": not remaining,
        "distinct_colors": distinct_colors,
        "lower_bound_banks": -(-distinct_colors // 16),
        "fits_16_banks": banks <= 16,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--group-sizes", nargs="+", type=int, default=[1, 4, 8, 16, 32])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    result: dict[str, object] = {}
    for raw in args.images:
        path = pathlib.Path(raw)
        tiles = load_tiles(path)
        entry: dict[str, object] = {
            "path": str(path),
            "tile_count": len(tiles),
            "max_colors_in_one_tile": max((len(t) for t in tiles), default=0),
            "tiles_over_16_colors": sum(1 for t in tiles if len(t) > 16),
            "fixed_groupings": {
                str(size): fixed_groups(tiles, size) for size in args.group_sizes
            },
            "bank_cover": greedy_banks(tiles),
        }
        result[path.name] = entry

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
