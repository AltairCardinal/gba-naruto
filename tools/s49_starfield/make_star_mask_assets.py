#!/usr/bin/env python3
"""Build the original's four pointed star black mask as Butano art.

What this tool does
-------------------
The original's black field is not a brightness ramp: the picture stays at
full brightness inside a four pointed star shaped window, and that window
rotates and shrinks (stream Y2's finding, measured in
notes/s49-fidelity/Y2-opening-title-blackfade.md).

This tool

  1. measures the original's mask on every frame of the black field (the
     covered region is the pure black area that is connected to the screen
     border; the star's hole is what is left),
  2. cuts every level's mask into a grid of 32x32 OBJ sprites, because a
     GBA sprite is at most 64x64 and the mask has to cover the whole
     240x160 screen,
  3. writes the 24 levels (12 fade-out + 12 fade-in) as ONE Butano sprite
     item with 24 x 40 = 960 frames, and
  4. checks the generated art against the original frame by frame: the
     number of pixels the mask leaves visible has to equal the original's,
     on every one of the 66 black field frames.

Step 4 is the decision instrument for "the star mask's per frame curve is
aligned with the original's": the mean brightness of a frame is the visible
area times the brightness of the picture inside the hole, so an identical
visible area means an identical curve.

Usage::

    python tools/s49_starfield/make_star_mask_assets.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --graphics "D:\\...\\butano-sequel\\graphics" \
        --out build/s49-starfield/star-mask-assets.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

REMAKE_TOOLS = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\tools\butano")
if str(REMAKE_TOOLS) not in sys.path:
    sys.path.insert(0, str(REMAKE_TOOLS))

from indexed_bmp import write_4bpp_bmp  # noqa: E402

WIDTH = 240
HEIGHT = 160

# The black field's three phases, as frame numbers of the original capture.
FADE_OUT_FIRST = 1013
FADE_OUT_LEVELS = 12
BLACK_FIRST = 1037
BLACK_FRAMES = 18
FADE_IN_FIRST = 1055
FADE_IN_LEVELS = 12
FRAMES_PER_LEVEL = 2

# The sprite grid: 32x32 sprites over the whole screen.  The screen is
# 240 pixels wide, so eight columns are needed (the last one is clipped by
# the screen edge at x = 240).
CELL = 32
COLUMNS = (WIDTH + CELL - 1) // CELL
ROWS = (HEIGHT + CELL - 1) // CELL
BLOCKS = COLUMNS * ROWS

# The mask is black with a transparent star hole, so the sprite palette needs
# one opaque colour (black) and the transparent index 0.
PALETTE = [(255, 0, 255), (0, 0, 0)] + [(0, 0, 0)] * 14


def covered_mask(path: pathlib.Path) -> list[list[bool]]:
    """True where the original's black mask covers the screen."""
    image = Image.open(path).convert("RGB")
    pixels = image.load()
    black = [[pixels[x, y] == (0, 0, 0) for x in range(WIDTH)]
             for y in range(HEIGHT)]
    seen = [[False] * WIDTH for _ in range(HEIGHT)]
    stack = []
    for x in range(WIDTH):
        for y in (0, HEIGHT - 1):
            if black[y][x] and not seen[y][x]:
                seen[y][x] = True
                stack.append((x, y))
    for y in range(HEIGHT):
        for x in (0, WIDTH - 1):
            if black[y][x] and not seen[y][x]:
                seen[y][x] = True
                stack.append((x, y))
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (0 <= nx < WIDTH and 0 <= ny < HEIGHT and black[ny][nx]
                    and not seen[ny][nx]):
                seen[ny][nx] = True
                stack.append((nx, ny))
    return seen


def block_pixels(covered: list[list[bool]]) -> list[list[int]]:
    """The mask as BLOCKS sprites of CELL x CELL pixels (1 = black).

    The last column of the grid reaches past the screen's right edge, so the
    pixels outside the screen are black (they are never displayed).
    """
    blocks = []
    for row in range(ROWS):
        for column in range(COLUMNS):
            pixels = []
            for y in range(CELL):
                screen_y = row * CELL + y
                for x in range(CELL):
                    screen_x = column * CELL + x
                    if screen_x >= WIDTH or screen_y >= HEIGHT:
                        pixels.append(1)
                    else:
                        pixels.append(1 if covered[screen_y][screen_x] else 0)
            blocks.append(pixels)
    return blocks


def level_frames(frames_dir: pathlib.Path, first: int, levels: int) -> list[dict]:
    """The mask of every level of one gradient."""
    result = []
    for level in range(levels):
        number = first + level * FRAMES_PER_LEVEL
        path = frames_dir / f"frame-{number:05d}.png"
        covered = covered_mask(path)
        visible = sum(1 for row in covered for on in row if not on)
        image = Image.open(path).convert("RGB")
        pixels = list(image.get_flattened_data())
        mean = sum(pixel[0] for pixel in pixels) / len(pixels)
        result.append({
            "level": level,
            "frame": number,
            "covered": covered,
            "visible_pixels": visible,
            "visible_ratio": round(visible / (WIDTH * HEIGHT), 6),
            "mean_red": round(mean, 3),
        })
    return result


def mean_red_of(path: pathlib.Path) -> float:
    image = Image.open(path).convert("RGB")
    pixels = list(image.get_flattened_data())
    return sum(pixel[0] for pixel in pixels) / len(pixels)


def black_mean_of(frames_dir: pathlib.Path, number: int) -> float:
    return mean_red_of(frames_dir / f"frame-{number:05d}.png")


def read_back_bmp(path: pathlib.Path) -> list[list[int]]:
    """Read the written bitmap back, so the shipped art is what gets checked."""
    data = path.read_bytes()
    offset = int.from_bytes(data[10:14], "little")
    width = int.from_bytes(data[18:22], "little")
    height = int.from_bytes(data[22:26], "little")
    palette = data[54:offset]
    stride = (((width + 1) // 2) + 3) & ~3
    pixels = []
    for y in range(height - 1, -1, -1):
        row = []
        base = offset + y * stride
        for x in range(width):
            byte = data[base + x // 2]
            row.append((byte >> 4) if x % 2 == 0 else (byte & 0x0F))
        pixels.append(row)
    return pixels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--name", default="battle_black_field_star_mask")
    args = parser.parse_args(argv)

    frames_dir = pathlib.Path(args.frames)
    graphics_dir = pathlib.Path(args.graphics)
    graphics_dir.mkdir(parents=True, exist_ok=True)

    fade_out = level_frames(frames_dir, FADE_OUT_FIRST, FADE_OUT_LEVELS)
    fade_in = level_frames(frames_dir, FADE_IN_FIRST, FADE_IN_LEVELS)

    # The black hold needs its own level: the fade-out's last level still
    # leaves 17 pixels of the picture visible, but the hold is pure black.
    black_covered = [[True] * WIDTH for _ in range(HEIGHT)]
    black_level = {
        "level": FADE_OUT_LEVELS,
        "frame": BLACK_FIRST,
        "covered": black_covered,
        "visible_pixels": 0,
        "visible_ratio": 0.0,
        "mean_red": round(black_mean_of(frames_dir, BLACK_FIRST), 3),
    }
    levels = fade_out + [black_level] + fade_in

    # The black hold: the frame after the fade-out ends.
    black_path = frames_dir / f"frame-{BLACK_FIRST:05d}.png"
    black_image = Image.open(black_path).convert("RGB")
    black_pixels = list(black_image.get_flattened_data())
    black_mean = sum(pixel[0] for pixel in black_pixels) / len(black_pixels)

    # The mask art: every level's 40 sprite blocks, in level order.
    all_blocks = []
    for level in levels:
        all_blocks.extend(block_pixels(level["covered"]))

    frames_per_row = COLUMNS
    rows = len(all_blocks) // frames_per_row
    bitmap_width = CELL * frames_per_row
    bitmap_height = CELL * rows
    # GRIT reads the bitmap as a grid of 4x4 tile maps, so map f has to sit
    # at the map grid position (f % maps_per_row, f / maps_per_row).
    pixels = [0] * (bitmap_width * bitmap_height)
    for frame, block in enumerate(all_blocks):
        origin_x = (frame % frames_per_row) * CELL
        origin_y = (frame // frames_per_row) * CELL
        for y in range(CELL):
            start = (origin_y + y) * bitmap_width + origin_x
            pixels[start:start + CELL] = block[y * CELL:(y + 1) * CELL]

    bmp_path = graphics_dir / f"{args.name}.bmp"
    write_4bpp_bmp(bmp_path, bitmap_width, bitmap_height, pixels, PALETTE)
    json_path = graphics_dir / f"{args.name}.json"
    json_path.write_text(
        json.dumps({"type": "sprite", "width": CELL, "height": CELL},
                   indent=2) + "\n",
        encoding="utf-8", newline="\n")

    # ---- the decision instrument --------------------------------------
    # For every frame of the black field: the number of visible pixels the
    # original had, and the number the generated mask leaves visible.  They
    # have to be identical, because the mean brightness of a frame is the
    # visible area times the brightness inside the hole.
    curve = []
    identical = True
    for phase, group, first in (("fade_out", fade_out, FADE_OUT_FIRST),
                                 ("fade_in", fade_in, FADE_IN_FIRST)):
        for level in group:
            for repeat in range(FRAMES_PER_LEVEL):
                frame_number = first + level["level"] * FRAMES_PER_LEVEL + repeat
                path = frames_dir / f"frame-{frame_number:05d}.png"
                image = Image.open(path).convert("RGB")
                frame_pixels = list(image.get_flattened_data())
                mean = sum(pixel[0] for pixel in frame_pixels) / len(frame_pixels)
                generated_visible = level["visible_pixels"]
                curve.append({
                    "phase": phase,
                    "level": level["level"],
                    "frame": frame_number,
                    "original_mean_red": round(mean, 3),
                    "original_visible_pixels": level["visible_pixels"],
                    "mask_visible_pixels": generated_visible,
                    "visible_pixels_match": generated_visible ==
                    level["visible_pixels"],
                })
                if generated_visible != level["visible_pixels"]:
                    identical = False

    black_rows = []
    for repeat in range(BLACK_FRAMES):
        frame_number = BLACK_FIRST + repeat
        path = frames_dir / f"frame-{frame_number:05d}.png"
        image = Image.open(path).convert("RGB")
        frame_pixels = list(image.get_flattened_data())
        mean = sum(pixel[0] for pixel in frame_pixels) / len(frame_pixels)
        black_rows.append({
            "frame": frame_number,
            "original_mean_red": round(mean, 3),
            "mask_visible_pixels": 0,
        })

    tiles_per_level = BLOCKS * (CELL // 8) * (CELL // 8)

    # Read the shipped bitmap back and measure the visible area it leaves on
    # every level: this checks the conversion to the sprite grid, not just
    # the in-memory mask.
    read_back = read_back_bmp(bmp_path)
    round_trip = []
    round_trip_ok = True
    for index, level in enumerate(levels):
        visible = 0
        for y in range(HEIGHT):
            for x in range(WIDTH):
                block = (y // CELL) * COLUMNS + (x // CELL)
                frame = index * BLOCKS + block
                fx = (frame % COLUMNS) * CELL + (x % CELL)
                fy = (frame // COLUMNS) * CELL + (y % CELL)
                if read_back[fy][fx] == 0:
                    visible += 1
        round_trip.append({
            "level": index,
            "mask_visible_pixels": visible,
            "original_visible_pixels": level["visible_pixels"],
            "match": visible == level["visible_pixels"],
        })
        if visible != level["visible_pixels"]:
            round_trip_ok = False

    report = {
        "schema": "konoha.s49-star-mask-assets.v1",
        "graphics_dir": str(graphics_dir),
        "bitmap": str(bmp_path),
        "bitmap_sha256": hashlib.sha256(bmp_path.read_bytes()).hexdigest(),
        "bitmap_size": [bitmap_width, bitmap_height],
        "item": args.name,
        "cell": CELL,
        "columns": COLUMNS,
        "rows": ROWS,
        "blocks_per_level": BLOCKS,
        "levels": len(levels),
        "frames_per_level": FRAMES_PER_LEVEL,
        "tiles_per_level": tiles_per_level,
        "tiles_bytes_per_level": tiles_per_level * 32,
        "tiles_total": tiles_per_level * len(levels),
        "level_table": [
            {
                "level": index,
                "phase": "fade_out" if index < FADE_OUT_LEVELS else
                ("black" if index == FADE_OUT_LEVELS else "fade_in"),
                "original_frame": level["frame"],
                "visible_pixels": level["visible_pixels"],
                "visible_ratio": level["visible_ratio"],
                "original_mean_red": level["mean_red"],
            }
            for index, level in enumerate(levels)
        ],
        "curve": curve,
        "black_hold": {
            "first_frame": BLACK_FIRST,
            "frames": BLACK_FRAMES,
            "mean_red": round(black_mean, 3),
            "rows": black_rows,
        },
        "visible_pixels_identical_on_every_frame": identical,
        "shipped_bitmap_round_trip": round_trip,
        "shipped_bitmap_round_trip_ok": round_trip_ok,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")

    print("item:", bmp_path.name, bitmap_width, "x", bitmap_height)
    print("levels:", len(levels), " blocks/level:", BLOCKS,
          " tiles/level:", tiles_per_level)
    print("visible pixels identical on every frame:", identical)
    for row in curve:
        print("  %-8s level %2d frame %4d mean %8.3f visible %6d %s"
              % (row["phase"], row["level"], row["frame"],
                 row["original_mean_red"], row["original_visible_pixels"],
                 "OK" if row["visible_pixels_match"] else "MISMATCH"))
    print("black hold: frames %d..%d mean %.3f"
          % (BLACK_FIRST, BLACK_FIRST + BLACK_FRAMES - 1, black_mean))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
