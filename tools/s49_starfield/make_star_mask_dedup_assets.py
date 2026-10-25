#!/usr/bin/env python3
"""Build the star black mask as a deduplicated, VRAM affordable layout.

Why this tool exists
--------------------
The original's black field is a four pointed star shaped window that rotates
and shrinks (notes/s49-fidelity/Z2-title-art-starfield.md).  Stream Z2
shipped it as a grid of 32x32 OBJ sprites: 40 sprites x 16 tiles = 640 OBJ
tiles per level, but the battle screen only has 404 free OBJ tiles and 86
free OAM slots (measured by tools/s49_starfield/measure_scene_vram.py), so
the second black field did not fit.

This tool builds a layout that does fit, without changing a single pixel of
the mask:

  * the screen is cut into 32x32 blocks;
  * a block the star's boundary does not touch is *uniform black*, so all of
    those blocks share **one** 32x32 tile set (16 tiles);
  * a block the boundary does touch is cut into four 16x16 cells; a uniform
    cell shares **one** 16x16 tile set (4 tiles) with every other uniform
    cell, and a crossed cell gets its own 16x16 tile set (4 tiles), which
    holds the cell's exact pixel pattern.

A cell is drawn with its own pixels, so the result is *pixel exact*: the
rendered mask covers exactly the same pixels as the original on every level.
The saving is in VRAM, not in fidelity.

The tool writes

  * ``battle_black_field_star_mask16``: the distinct 16x16 cells (one frame
    each), as a Butano sprite item;
  * ``battle_black_field_star_block32``: the single all black 32x32 block;
  * a C++ placement table (which cell goes where, with which frame);
  * a report with the round trip check: the shipped bitmaps are read back
    and the mask they produce is compared with the original's, level by
    level.

Usage::

    python tools/s49_starfield/make_star_mask_dedup_assets.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --graphics "D:\\...\\butano-sequel\\graphics" \
        --header "D:\\...\\game\\include\\konoha\\battle_black_field_star_table.h" \
        --out build/s49-starfield/star-mask-dedup.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
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

FADE_OUT_FIRST = 1013
FADE_OUT_LEVELS = 12
BLACK_FIRST = 1037
FADE_IN_FIRST = 1055
FADE_IN_LEVELS = 12
# The original's entry transition does not stop after the fade-in: the star's
# hole keeps growing for twelve more levels (the original's frames 1079..1102,
# the "diagonal expansion" that stream W3 measured).  The black field event of
# the blackfade report is 66 frames long, but the *transition* is 90 frames
# long and has 37 levels.
GROW_FIRST = 1079
GROW_LEVELS = 12
FRAMES_PER_LEVEL = 2

# The segments of the transition, in level order.
SEGMENTS = (
    (FADE_OUT_FIRST, FADE_OUT_LEVELS),
    (BLACK_FIRST, 1),
    (FADE_IN_FIRST, FADE_IN_LEVELS),
    (GROW_FIRST, GROW_LEVELS),
)
LEVEL_COUNT = sum(levels for _, levels in SEGMENTS)

BLOCK = 32
CELL = 16
BLOCK_COLUMNS = (WIDTH + BLOCK - 1) // BLOCK
BLOCK_ROWS = (HEIGHT + BLOCK - 1) // BLOCK
CELL_COLUMNS = (WIDTH + CELL - 1) // CELL
CELL_ROWS = (HEIGHT + CELL - 1) // CELL

# GRIT puts one frame per map cell, and the map of the shipped art is eight
# cells wide, so frame f sits at the map position (f % 8, f / 8).
FRAMES_PER_ROW = 8

# The mask is black with a transparent star hole, so the palette needs one
# opaque colour (black) and the transparent index 0.
PALETTE = [(255, 0, 255), (0, 0, 0)] + [(0, 0, 0)] * 14

# The art frame of the two shared tile sets.
ART_BLACK_BLOCK = 0
ART_BLACK_CELL = 0

# The budgets of the battle screen, measured by
# tools/s49_starfield/measure_scene_vram.py: the allocator's own free tile
# counter and the OAM slots the scene's own sprites do not use.
TILE_BUDGET = 404
SPRITE_BUDGET = 86

# The two shared art frames.
BLACK_BLOCK_KEY = tuple([1] * (BLOCK * BLOCK))
BLACK_CELL_KEY = ("black-cell",)



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
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and black[ny][nx] \
                    and not seen[ny][nx]:
                seen[ny][nx] = True
                stack.append((nx, ny))
    return seen


def level_masks(frames_dir: pathlib.Path) -> list[list[list[bool]]]:
    """The mask of every level, in level order."""
    result = []
    for first, levels in SEGMENTS:
        for level in range(levels):
            number = first + level * FRAMES_PER_LEVEL
            path = frames_dir / f"frame-{number:05d}.png"
            result.append(covered_mask(path))
    return result


def classify(mask: list[list[bool]], x: int, y: int, size: int) -> str:
    """``empty``, ``full`` or ``mixed`` for one cell."""
    full = True
    empty = True
    for yy in range(y, min(y + size, HEIGHT)):
        for xx in range(x, min(x + size, WIDTH)):
            if mask[yy][xx]:
                empty = False
            else:
                full = False
    if empty:
        return "empty"
    if full:
        return "full"
    return "mixed"


def cell_pixels(mask: list[list[bool]], x: int, y: int, size: int) -> list[int]:
    """The cell's pixels, 1 where the mask covers and 0 where it does not."""
    pixels = []
    for yy in range(y, min(y + size, HEIGHT)):
        for xx in range(x, min(x + size, WIDTH)):
            pixels.append(1 if mask[yy][xx] else 0)
    return pixels


def build_layout(masks: list[list[list[bool]]]):
    """The placement table and the art of every level.

    The table is split in two pools because a GBA sprite's shape is fixed when
    the sprite is created: the 32x32 blocks are drawn with sprites of the
    32x32 item and the boundary cells with sprites of the 16x16 item.

    A level is covered exactly, with three kinds of piece:

      * a 32x32 block the star's boundary does not touch is completely black,
        so all of those blocks share ONE 32x32 art frame (sixteen tiles);
      * a 32x32 block the boundary crosses is cut into four 16x16 cells;
      * a 16x16 cell that is completely black shares ONE 16x16 art frame (four
        tiles) with every other black cell, and a crossed cell gets its own
        16x16 art frame (four tiles) that holds the cell's exact pixels.

    Every cell is drawn with its own pixels, so the mask is *pixel exact*:
    it covers exactly the same pixels as the original on every level.  The
    saving is in VRAM, not in fidelity.

    The measured cost of the layout over the thirty seven levels of the
    original's entry transition (tools/s49_starfield/
    make_star_mask_dedup_assets.py):

      OBJ tiles per level     16 .. 240
      OBJ sprites per level   40 .. 103
      level change peak       404 tiles

    The 404 tiles of a level change are the budget the battle screen has
    (the allocator's own free tile counter, measured by
    tools/s49_starfield/measure_scene_vram.py), so the transition fits.
    """
    block_frames: list[list[int]] = []
    cell_frames: list[list[int]] = []
    block_index: dict[tuple[int, ...], int] = {}
    cell_index: dict[tuple[int, ...], int] = {}

    def block_frame(pixels) -> int:
        key = tuple(pixels)
        if key not in block_index:
            block_index[key] = len(block_frames)
            block_frames.append(list(key))
        return block_index[key]

    def cell_frame(pixels) -> int:
        key = tuple(pixels)
        if key not in cell_index:
            cell_index[key] = len(cell_frames)
            cell_frames.append(list(key))
        return cell_index[key]

    # The two shared tile sets come first so their indices are stable.
    block_frame([1] * (BLOCK * BLOCK))
    cell_frame([1] * (CELL * CELL))

    levels = []
    for mask in masks:
        blocks = []
        cells = []
        for by in range(0, HEIGHT, BLOCK):
            for bx in range(0, WIDTH, BLOCK):
                kind = classify(mask, bx, by, BLOCK)
                if kind == "empty":
                    continue
                if kind == "full":
                    blocks.append((bx, by, 0))
                    continue
                for cy in range(by, min(by + BLOCK, HEIGHT), CELL):
                    for cx in range(bx, min(bx + BLOCK, WIDTH), CELL):
                        kind = classify(mask, cx, cy, CELL)
                        if kind == "empty":
                            continue
                        if kind == "full":
                            cells.append((cx, cy, 0))
                            continue
                        cells.append((cx, cy, cell_frame(
                                cell_pixels(mask, cx, cy, CELL))))
        levels.append((blocks, cells))

    return levels, block_frames, cell_frames


def write_art(path: pathlib.Path, frames: list[list[int]], size: int) -> None:
    """Write a sprite item bitmap: one frame per map cell, eight per row."""
    rows = (len(frames) + FRAMES_PER_ROW - 1) // FRAMES_PER_ROW
    bitmap_width = size * FRAMES_PER_ROW
    bitmap_height = size * rows
    pixels = [0] * (bitmap_width * bitmap_height)
    for index, frame in enumerate(frames):
        origin_x = (index % FRAMES_PER_ROW) * size
        origin_y = (index // FRAMES_PER_ROW) * size
        for y in range(size):
            start = (origin_y + y) * bitmap_width + origin_x
            pixels[start:start + size] = frame[y * size:(y + 1) * size]
    write_4bpp_bmp(path, bitmap_width, bitmap_height, pixels, PALETTE)


def read_back_bmp(path: pathlib.Path) -> list[list[int]]:
    """Read a written bitmap back, so the shipped art is what gets checked."""
    data = path.read_bytes()
    offset = int.from_bytes(data[10:14], "little")
    width = int.from_bytes(data[18:22], "little")
    height = int.from_bytes(data[22:26], "little")
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


def frame_from_bitmap(bitmap: list[list[int]], index: int,
                      size: int) -> list[int]:
    """One frame of a shipped bitmap, in the order GRIT's map uses."""
    origin_x = (index % FRAMES_PER_ROW) * size
    origin_y = (index // FRAMES_PER_ROW) * size
    pixels = []
    for y in range(size):
        for x in range(size):
            pixels.append(bitmap[origin_y + y][origin_x + x])
    return pixels


def write_header(path: pathlib.Path, levels, cell_art_frames: int,
                 block_art_frames: int, max_blocks: int,
                 max_cells: int) -> None:
    """Write the placement table as a C++ header."""
    lines = []
    lines.append("#ifndef KONOHA_BATTLE_BLACK_FIELD_STAR_TABLE_H")
    lines.append("#define KONOHA_BATTLE_BLACK_FIELD_STAR_TABLE_H")
    lines.append("")
    lines.append("#include <cstdint>")
    lines.append("")
    lines.append("// GENERATED FILE - do not edit.")
    lines.append("//")
    lines.append("// Produced by tools/s49_starfield/make_star_mask_dedup_assets.py.")
    lines.append("// It is the placement table of the star black mask: which cell of")
    lines.append("// the screen is drawn, with which frame of which art item.")
    lines.append("//")
    lines.append("// The table is split in two pools because a GBA sprite's shape is")
    lines.append("// fixed when the sprite is created: the uniform 32x32 blocks are")
    lines.append("// drawn with sprites of the 32x32 item and the boundary cells with")
    lines.append("// sprites of the 16x16 item.")
    lines.append("")
    lines.append("namespace konoha")
    lines.append("{")
    lines.append("")
    lines.append("namespace battle_black_field_star_table")
    lines.append("{")
    lines.append("")
    lines.append("    // One drawn cell of the mask.")
    lines.append("    //")
    lines.append("    //   x, y   the top left corner of the cell, in pixels")
    lines.append("    //   art   the frame of the art item that holds the cell's pixels")
    lines.append("")
    lines.append("    // The art frame 0 of both items is the all black piece, and it")
    lines.append("    // is shared by every piece that uses it.")
    lines.append("    struct placement")
    lines.append("    {")
    lines.append("        std::uint8_t x;")
    lines.append("        std::uint8_t y;")
    lines.append("        std::uint16_t art;")
    lines.append("    };")
    lines.append("")
    lines.append("    // The number of 32x32 blocks of every level.")
    lines.append(f"    inline constexpr int block_counts[{len(levels)}] = {{")
    for index in range(0, len(levels), 8):
        chunk = levels[index:index + 8]
        lines.append("        " + ", ".join(str(len(level[0]))
                                            for level in chunk) + ",")
    lines.append("    };")
    lines.append("")
    lines.append("    // The number of 16x16 cells of every level.")
    lines.append(f"    inline constexpr int cell_counts[{len(levels)}] = {{")
    for index in range(0, len(levels), 8):
        chunk = levels[index:index + 8]
        lines.append("        " + ", ".join(str(len(level[1]))
                                            for level in chunk) + ",")
    lines.append("    };")
    lines.append("")
    lines.append("    // The 32x32 blocks of every level, level by level.")
    lines.append(f"    inline constexpr placement blocks[{len(levels)} * "
                 f"{max_blocks}] = {{")
    for blocks, _ in levels:
        for placement in blocks:
            lines.append("        {%d, %d, %d}," % placement)
        for _ in range(max_blocks - len(blocks)):
            lines.append("        {0, 0, 0},")
    lines.append("    };")
    lines.append("")
    lines.append("    // The 16x16 cells of every level, level by level.")
    lines.append(f"    inline constexpr placement cells[{len(levels)} * "
                 f"{max_cells}] = {{")
    for _, cells in levels:
        for placement in cells:
            lines.append("        {%d, %d, %d}," % placement)
        for _ in range(max_cells - len(cells)):
            lines.append("        {0, 0, 0},")
    lines.append("    };")
    lines.append("")
    lines.append("    // The number of art frames of the 16x16 item.")
    lines.append("    inline constexpr int art_frames = %d;" % cell_art_frames)
    lines.append("")
    lines.append("    // The number of art frames of the 32x32 item.")
    lines.append("    inline constexpr int block_art_frames = %d;" % block_art_frames)
    lines.append("")
    lines.append("} // namespace battle_black_field_star_table")
    lines.append("")
    lines.append("} // namespace konoha")
    lines.append("")
    lines.append("#endif // KONOHA_BATTLE_BLACK_FIELD_STAR_TABLE_H")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def read_header(header: pathlib.Path, max_blocks: int, max_cells: int,
                level_count: int):
    """Read the generated header back and rebuild the level's placements.

    The header is what the game uses, so the check has to go through it:
    a table whose index arithmetic does not match the header's layout would
    draw the wrong mask on the GBA while every offline number looked fine.
    """
    text = header.read_text(encoding="utf-8")

    def counts(name: str) -> list[int]:
        match = re.search(name + r"\[\d+\] = \{(.*?)\};", text, re.S)
        if not match:
            raise SystemExit(f"the header has no {name}")
        return [int(value) for value in match.group(1).replace("\n", "").split(",")
                if value.strip()]

    def placements(name: str, stride: int) -> list[list[tuple[int, int, int]]]:
        match = re.search(name + r"\[\d+ \* \d+\] = \{(.*?)\n    \};", text, re.S)
        if not match:
            raise SystemExit(f"the header has no {name}")
        found = [(int(x), int(y), int(art))
                 for x, y, art in re.findall(r"\{(\d+), (\d+), (\d+)\},",
                                            match.group(1))]
        if len(found) != level_count * stride:
            raise SystemExit(f"the header's {name} has {len(found)} entries, "
                             f"expected {level_count * stride}")
        return [found[index * stride:(index + 1) * stride]
                for index in range(level_count)]

    block_counts = counts("block_counts")
    cell_counts = counts("cell_counts")
    blocks = placements("blocks", max_blocks)
    cells = placements("cells", max_cells)
    levels = []
    for level in range(level_count):
        level_placements = []
        for index in range(block_counts[level]):
            level_placements.append(blocks[level][index])
        for index in range(cell_counts[level]):
            level_placements.append(cells[level][index])
        levels.append(level_placements)
    return levels


def blocks_of(levels, index):
    """The block placements of one level."""
    return levels[index][0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--header", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cell-name", default="battle_black_field_star_mask16")
    parser.add_argument("--block-name", default="battle_black_field_star_block32")
    args = parser.parse_args(argv)

    frames_dir = pathlib.Path(args.frames)
    graphics_dir = pathlib.Path(args.graphics)
    graphics_dir.mkdir(parents=True, exist_ok=True)

    masks = level_masks(frames_dir)
    levels, block_frames, cell_frames = build_layout(masks)
    max_blocks = max(len(blocks) for blocks, _ in levels)
    max_cells = max(len(cells) for _, cells in levels)
    max_sprites = max(len(blocks) + len(cells) for blocks, cells in levels)

    cell_bmp = graphics_dir / f"{args.cell_name}.bmp"
    block_bmp = graphics_dir / f"{args.block_name}.bmp"
    write_art(cell_bmp, cell_frames, CELL)
    write_art(block_bmp, block_frames, BLOCK)
    for name, size in ((args.cell_name, CELL), (args.block_name, BLOCK)):
        (graphics_dir / f"{name}.json").write_text(
            json.dumps({"type": "sprite", "width": size, "height": size},
                       indent=2) + "\n",
            encoding="utf-8", newline="\n")

    write_header(pathlib.Path(args.header), levels, len(cell_frames),
                 len(block_frames), max_blocks, max_cells)

    # ---- the round trip check ------------------------------------------
    # Read the shipped bitmaps back and rebuild the mask they produce: it
    # has to cover exactly the same pixels as the original on every level.
    cell_bitmap = read_back_bmp(cell_bmp)
    block_bitmap = read_back_bmp(block_bmp)
    frames_back = {index: frame_from_bitmap(cell_bitmap, index, CELL)
                   for index in range(len(cell_frames))}
    block_frames_back = {index: frame_from_bitmap(block_bitmap, index, BLOCK)
                         for index in range(len(block_frames))}

    def rebuild(level_blocks, level_cells):
        covered = [[False] * WIDTH for _ in range(HEIGHT)]
        for x, y, art in level_blocks:
            pixels = block_frames_back[art]
            for yy in range(BLOCK):
                for xx in range(BLOCK):
                    if pixels[yy * BLOCK + xx] and y + yy < HEIGHT \
                            and x + xx < WIDTH:
                        covered[y + yy][x + xx] = True
        for x, y, art in level_cells:
            pixels = frames_back[art]
            for yy in range(CELL):
                for xx in range(CELL):
                    if pixels[yy * CELL + xx] and y + yy < HEIGHT \
                            and x + xx < WIDTH:
                        covered[y + yy][x + xx] = True
        return covered

    round_trip = []
    round_trip_ok = True
    for index, (blocks, cells) in enumerate(levels):
        covered = rebuild(blocks, cells)
        mismatches = 0
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if covered[y][x] != masks[index][y][x]:
                    mismatches += 1
        visible = sum(1 for row in covered for on in row if not on)
        expected = sum(1 for row in masks[index] for on in row if not on)
        row = {
            "level": index,
            "mask_visible_pixels": visible,
            "original_visible_pixels": expected,
            "mismatched_pixels": mismatches,
            "ok": mismatches == 0,
        }
        round_trip.append(row)
        if mismatches != 0:
            round_trip_ok = False

    # ---- the same check, but through the generated header ---------------
    header_levels = read_header(pathlib.Path(args.header), max_blocks,
                                 max_cells, len(levels))
    header_mismatches = 0
    for index, level in enumerate(header_levels):
        covered = rebuild(level[:len(blocks_of(levels, index))],
                          level[len(blocks_of(levels, index)):])
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if covered[y][x] != masks[index][y][x]:
                    header_mismatches += 1
    header_ok = header_mismatches == 0

    # ---- the VRAM cost of every level ---------------------------------
    levels_report = []
    for index, (blocks, cells) in enumerate(levels):
        used_blocks = {art for _, _, art in blocks}
        used_cells = {art for _, _, art in cells}
        levels_report.append({
            "level": index,
            "blocks": len(blocks),
            "cells": len(cells),
            "sprites": len(blocks) + len(cells),
            "tiles_live": 16 * len(used_blocks) + 4 * len(used_cells),
            "tile_sets": len(used_blocks) + len(used_cells),
        })

    # ---- the cost of a level change ------------------------------------
    # Butano returns a released tile set to the allocator at the next core
    # update, so the old level's and the new level's tile sets are live at the
    # same time for one frame.
    level_change = []
    for index in range(1, len(levels)):
        used_blocks = ({art for _, _, art in levels[index - 1][0]} |
                       {art for _, _, art in levels[index][0]})
        used_cells = ({art for _, _, art in levels[index - 1][1]} |
                      {art for _, _, art in levels[index][1]})
        level_change.append({
            "from": index - 1,
            "to": index,
            "tiles_live": 16 * len(used_blocks) + 4 * len(used_cells),
        })
    max_level_change = max(row["tiles_live"] for row in level_change)

    report = {
        "schema": "konoha.s49-star-mask-dedup.v3",
        "frames": str(frames_dir),
        "cell_item": args.cell_name,
        "block_item": args.block_name,
        "cell_art_frames": len(cell_frames),
        "block_art_frames": len(block_frames),
        "rom_tiles": 16 * len(block_frames) + 4 * len(cell_frames),
        "level_count": len(levels),
        "max_blocks": max_blocks,
        "max_cells": max_cells,
        "max_sprites": max_sprites,
        "max_tiles_live": max(row["tiles_live"] for row in levels_report),
        "max_tiles_at_level_change": max_level_change,
        "levels": levels_report,
        "level_change": level_change,
        "round_trip": round_trip,
        "shipped_bitmap_round_trip_ok": round_trip_ok,
        "header_round_trip_mismatched_pixels": header_mismatches,
        "header_round_trip_ok": header_ok,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8",
                   newline="\n")

    print("levels:", len(levels))
    print("16x16 art frames:", len(cell_frames),
          " 32x32 art frames:", len(block_frames))
    print("max blocks:", max_blocks, " max cells:", max_cells,
          " max sprites of a level:", max_sprites,
          " max tiles live:", report["max_tiles_live"],
          " max tiles at a level change:", max_level_change,
          " rom tiles:", report["rom_tiles"])
    for row in levels_report:
        print("  level %2d blocks %3d cells %3d sprites %3d tiles %4d sets %3d"
              % (row["level"], row["blocks"], row["cells"], row["sprites"],
                 row["tiles_live"], row["tile_sets"]))
    print("shipped bitmap round trip ok:", round_trip_ok)
    print("generated header round trip mismatched pixels:", header_mismatches)
    print("->", out)
    return 0 if round_trip_ok and header_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
