#!/usr/bin/env python3
"""X2: where are the original's map walls in map 14's canvas?

The original's battle-14 map canvas is 480 x 304 px (60 x 38 tiles), i.e.
15 battle columns of 32 px by 19 battle rows of 16 px.  This script prints,
for every tile row, the *tile* column pattern of the left edge and of the
right edge of the canvas, so the wall's pixel extent can be read off
directly.

Read-only: the reverse line is never modified.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image

DEFAULT_CANVAS = pathlib.Path(
    "D:/Shell/Github/gba-naruto-reverse/artifacts/map-canvases-v1/canvases"
    "/map-14-primary.png")


def main() -> int:
    canvas = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CANVAS
    image = Image.open(canvas).convert("RGB")
    width, height = image.size
    pixels = image.load()
    print(f"canvas {width} x {height} px = {width // 8} x {height // 8} tiles")

    def signature(tile_x: int, tile_y: int) -> tuple:
        colours = []
        for y in range(tile_y * 8, tile_y * 8 + 8):
            for x in range(tile_x * 8, tile_x * 8 + 8):
                colour = pixels[x, y]
                if colour not in colours:
                    colours.append(colour)
        return tuple(sorted(colours))

    print("\nleft edge: tile columns 0..7 (map px 0..63)")
    for tile_y in range(0, 6):
        row = [signature(tile_x, tile_y) for tile_x in range(8)]
        ids = {sig: index for index, sig in enumerate(
            dict.fromkeys(row))}
        print(f"  tile row {tile_y:2d} (map px {tile_y * 8:3d}): "
              + " ".join(f"{ids[sig]:2d}" for sig in row))

    print("\nright edge: tile columns 52..59 (map px 416..479)")
    for tile_y in range(0, 6):
        row = [signature(tile_x, tile_y) for tile_x in range(52, 60)]
        ids = {sig: index for index, sig in enumerate(
            dict.fromkeys(row))}
        print(f"  tile row {tile_y:2d} (map px {tile_y * 8:3d}): "
              + " ".join(f"{ids[sig]:2d}" for sig in row))

    print("\nlegend (colour sets seen, most common first):")
    seen: dict[tuple, list] = {}
    for tile_y in range(0, height // 8):
        for tile_x in range(0, width // 8):
            sig = signature(tile_x, tile_y)
            seen.setdefault(sig, []).append((tile_x, tile_y))
    for index, (sig, cells) in enumerate(
            sorted(seen.items(), key=lambda kv: -len(kv[1]))[:12]):
        print(f"  [{index:2d}] {len(cells):4d} tiles  colours={sig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
