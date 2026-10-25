#!/usr/bin/env python3
"""Measure every candidate layout of the star black mask against VRAM.

Problem
-------
One frame of the original's four pointed star black mask covers the whole
240x160 screen.  Stream Z2 shipped it as a grid of 32x32 OBJ sprites, which
costs 40 sprites x 16 tiles = 640 OBJ tiles per level.  The battle screen has
only 336 free OBJ tiles (Butano's own allocator counter, not a high water
mark), so the second black field does not fit.

What this tool does
-------------------
It rebuilds the mask of every level from the original's own frames (the same
measurement as tools/s49_starfield/make_star_mask_assets.py) and then measures
the VRAM cost of every layout that could work.

The accounting rules are the GBA's and Butano's:

  * a sprite of W x H pixels needs (W / 8) * (H / 8) 4bpp tiles, and those
    tiles have to be *contiguous* in VRAM, so only whole sprites can share a
    tile set;
  * Butano's sprite tile manager keys its allocations on the address of the
    tile data (bn_sprite_tiles_manager.cpp, ``items_map.find(tiles_data)``), so
    two sprites that point at the same art share one allocation;
  * a level change needs the old level's and the new level's tile sets to be
    live at the same time, because the old set is only returned to the
    allocator at the next core update.  The *union* of the two sets is
    therefore the real budget.

Layouts
-------
  grid32          40 blocks of 32x32, one metatile each              (Z2's layout)
  grid16          15 x 10 blocks of 16x16
  grid8           30 x 20 blocks of 8x8
  hybrid8         32x32 uniform blocks share one tile set, a block the star
                  boundary crosses is cut into 8x8 cells
  hybrid16        the same, but the boundary is cut at 16x16
  hierarchy       32x32 -> 16x16 -> 8x8, the smallest cell that fits
  bg_mask         a BG layer with a transparent hole (no sprite limit at all)

Usage::

    python tools/s49_starfield/analyze_vram_options.py \
        --frames build/s49-blackfade/original-entry-v2/frames \
        --out build/s49-starfield/vram-options.json \
        --markdown build/s49-starfield/vram-options.md
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

WIDTH = 240
HEIGHT = 160

FADE_OUT_FIRST = 1013
FADE_OUT_LEVELS = 12
BLACK_FIRST = 1037
FADE_IN_FIRST = 1055
FADE_IN_LEVELS = 12
FRAMES_PER_LEVEL = 2

# The GBA's hard limits.
OBJ_TILES_TOTAL = 1024
OBJ_SPRITES_TOTAL = 128
BG_TILES_TOTAL = 2048

# What the battle screen has left, measured on hardware with
# tools/s49_starfield/measure_scene_vram.py (the allocator's own counter,
# sampled on every frame of the remake's opening):
#
#   free OBJ tiles   404 (the tightest moment of the whole run)
#   free OAM slots   86  (the scene uses 42 sprites at its worst)
#
# Z2's 336 came from an older build and a coarser sample; the current build
# leaves more room.
BATTLE_FREE_OBJ_TILES = 404
BATTLE_FREE_SPRITES = 86
DEPLOY_FREE_OBJ_TILES = 662


def covered_mask(path: pathlib.Path) -> list[list[bool]]:
    """True where the original's black mask covers the screen.

    The mask is the pure black area that is connected to the screen border;
    what is left is the star's hole.
    """
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
    for first, levels in ((FADE_OUT_FIRST, FADE_OUT_LEVELS),
                          (BLACK_FIRST, 1),
                          (FADE_IN_FIRST, FADE_IN_LEVELS)):
        for level in range(levels):
            number = first + level * FRAMES_PER_LEVEL
            path = frames_dir / f"frame-{number:05d}.png"
            result.append(covered_mask(path))
    return result


def cell_pattern(mask: list[list[bool]], x: int, y: int, size: int) -> str:
    """The exact black/transparent pattern of one cell, as a key."""
    bits = []
    for yy in range(y, min(y + size, HEIGHT)):
        for xx in range(x, min(x + size, WIDTH)):
            bits.append("1" if mask[yy][xx] else "0")
    return "".join(bits)


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


def tiles_of(size: int) -> int:
    """The tiles one size x size 4bpp sprite needs."""
    return (size // 8) * (size // 8)


def layout_grid(mask: list[list[bool]], size: int) -> tuple[int, dict]:
    """A plain grid of size x size sprites, identical blocks sharing a tile set."""
    sprites = 0
    sets: dict = {}
    for y in range(0, HEIGHT, size):
        for x in range(0, WIDTH, size):
            kind = classify(mask, x, y, size)
            if kind == "empty":
                continue
            sprites += 1
            sets[("block", size, cell_pattern(mask, x, y, size))] = tiles_of(size)
    return sprites, sets


def layout_hybrid(mask: list[list[bool]], boundary: int) -> tuple[int, dict]:
    """32x32 blocks; a uniform block shares one tile set, a crossed block is
    cut into ``boundary`` sized cells."""
    sprites = 0
    sets: dict = {}
    for by in range(0, HEIGHT, 32):
        for bx in range(0, WIDTH, 32):
            kind = classify(mask, bx, by, 32)
            if kind == "empty":
                continue
            if kind == "full":
                sprites += 1
                sets[("uniform", 32)] = tiles_of(32)
                continue
            for cy in range(by, min(by + 32, HEIGHT), boundary):
                for cx in range(bx, min(bx + 32, WIDTH), boundary):
                    kind = classify(mask, cx, cy, boundary)
                    if kind == "empty":
                        continue
                    sprites += 1
                    if kind == "full":
                        sets[("uniform", boundary)] = tiles_of(boundary)
                    else:
                        sets[("unique", boundary,
                              cell_pattern(mask, cx, cy, boundary))] = \
                            tiles_of(boundary)
    return sprites, sets


def layout_hybrid_split(mask: list[list[bool]], boundary: int,
                        fallback: int, threshold: int) -> tuple[int, dict]:
    """Like ``layout_hybrid``, but a crossed 32x32 block whose split would
    need more than ``threshold`` cells is drawn as one ``fallback`` sized
    sprite.

    The tile cost is the same (a 32x32 block needs 16 tiles either way), but
    the sprite count is much lower.
    """
    sprites = 0
    sets: dict = {}
    for by in range(0, HEIGHT, 32):
        for bx in range(0, WIDTH, 32):
            kind = classify(mask, bx, by, 32)
            if kind == "empty":
                continue
            if kind == "full":
                sprites += 1
                sets[("uniform", 32)] = tiles_of(32)
                continue
            cells = []
            for cy in range(by, min(by + 32, HEIGHT), boundary):
                for cx in range(bx, min(bx + 32, WIDTH), boundary):
                    cells.append((cx, cy, classify(mask, cx, cy, boundary)))
            used = [cell for cell in cells if cell[2] != "empty"]
            if len(used) > threshold:
                sprites += 1
                sets[("unique", fallback,
                      cell_pattern(mask, bx, by, fallback))] = tiles_of(fallback)
                continue
            for cx, cy, cell_kind in used:
                sprites += 1
                if cell_kind == "full":
                    sets[("uniform", boundary)] = tiles_of(boundary)
                else:
                    sets[("unique", boundary,
                          cell_pattern(mask, cx, cy, boundary))] = \
                        tiles_of(boundary)
    return sprites, sets


def layout_hierarchy(mask: list[list[bool]]) -> tuple[int, dict]:
    """32x32 -> 16x16 -> 8x8: the biggest uniform cell that fits."""
    sprites = 0
    sets: dict = {}

    def place(x: int, y: int, size: int) -> None:
        nonlocal sprites
        kind = classify(mask, x, y, size)
        if kind == "empty":
            return
        sprites += 1
        if kind == "full":
            sets[("uniform", size)] = tiles_of(size)
            return
        if size == 8:
            sets[("unique", 8, cell_pattern(mask, x, y, 8))] = tiles_of(8)
            return
        step = size // 2
        for cy in range(y, min(y + size, HEIGHT), step):
            for cx in range(x, min(x + size, WIDTH), step):
                place(cx, cy, step)

    for by in range(0, HEIGHT, 32):
        for bx in range(0, WIDTH, 32):
            place(bx, by, 32)
    return sprites, sets


def layout_bg(mask: list[list[bool]]) -> tuple[int, dict]:
    """A BG layer with a transparent hole: no sprite limit, 8x8 tiles only."""
    sprites = 0
    sets: dict = {}
    for y in range(0, HEIGHT, 8):
        for x in range(0, WIDTH, 8):
            kind = classify(mask, x, y, 8)
            if kind == "empty":
                continue
            sprites += 1
            sets[("bg", 8, cell_pattern(mask, x, y, 8))] = tiles_of(8)
    return sprites, sets


LAYOUTS = {
    "grid32": lambda mask: layout_grid(mask, 32),
    "grid16": lambda mask: layout_grid(mask, 16),
    "grid8": lambda mask: layout_grid(mask, 8),
    "hybrid8": lambda mask: layout_hybrid(mask, 8),
    "hybrid16": lambda mask: layout_hybrid(mask, 16),
    "hybrid16fb2": lambda mask: layout_hybrid_split(mask, 16, 32, 2),
    "hybrid16fb3": lambda mask: layout_hybrid_split(mask, 16, 32, 3),
    "hierarchy": layout_hierarchy,
    "bg_mask": layout_bg,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown")
    args = parser.parse_args(argv)

    frames_dir = pathlib.Path(args.frames)
    masks = level_masks(frames_dir)

    levels = []
    per_level_sets = {}
    for index, mask in enumerate(masks):
        visible = sum(1 for row in mask for on in row if not on)
        row = {"level": index, "visible_pixels": visible}
        for key, builder in LAYOUTS.items():
            sprites, sets = builder(mask)
            per_level_sets[(key, index)] = sets
            row[key] = {
                "sprites": sprites,
                "tiles_live": sum(sets.values()),
                "tile_sets": len(sets),
            }
        levels.append(row)

    summary = {}
    for key in LAYOUTS:
        tiles = max(level[key]["tiles_live"] for level in levels)
        sprites = max(level[key]["sprites"] for level in levels)
        # The level change needs the union of the two levels' tile sets.
        peaks = []
        for index in range(1, len(levels)):
            old = per_level_sets[(key, index - 1)]
            new = per_level_sets[(key, index)]
            union = dict(old)
            union.update(new)
            peaks.append({
                "level": index,
                "union_tiles": sum(union.values()),
                "fresh_tiles": sum(new[key_] for key_ in new if key_ not in old),
            })
        summary[key] = {
            "worst_tiles_live": tiles,
            "worst_sprites": sprites,
            "worst_level": max(levels, key=lambda level: level[key]["tiles_live"])["level"],
            "transition_peak_tiles": max(row["union_tiles"] for row in peaks),
            "transition_peak_level": max(peaks, key=lambda row: row["union_tiles"])["level"],
            "transition_rows": peaks,
            "fits_battle_obj": tiles <= BATTLE_FREE_OBJ_TILES,
            "fits_transition": max(row["union_tiles"] for row in peaks)
            <= BATTLE_FREE_OBJ_TILES,
            "fits_sprite_limit": sprites <= BATTLE_FREE_SPRITES,
        }

    # The art the ROM needs: the distinct tile sets of every level together.
    for key in LAYOUTS:
        all_sets = {}
        for index in range(len(levels)):
            all_sets.update(per_level_sets[(key, index)])
        summary[key]["rom_tile_sets_all_levels"] = len(all_sets)
        summary[key]["rom_tiles_all_levels"] = sum(all_sets.values())

    report = {
        "schema": "konoha.s49-star-vram-options.v2",
        "frames": str(frames_dir),
        "limits": {
            "obj_tiles_total": OBJ_TILES_TOTAL,
            "obj_sprites_total": OBJ_SPRITES_TOTAL,
            "bg_tiles_total": BG_TILES_TOTAL,
            "battle_free_obj_tiles": BATTLE_FREE_OBJ_TILES,
            "deploy_free_obj_tiles": DEPLOY_FREE_OBJ_TILES,
        },
        "summary": summary,
        "levels": levels,
    }

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8",
                   newline="\n")

    header = ("%-10s %-10s %-9s %-10s %-8s %-8s %-8s" %
              ("layout", "tiles", "sprites", "transPeak", "tilesOK", "peakOK",
               "sprOK"))
    print(header)
    for key, data in summary.items():
        print("%-10s %-10d %-9d %-10d %-8s %-8s %-8s" %
              (key, data["worst_tiles_live"], data["worst_sprites"],
               data["transition_peak_tiles"],
               "yes" if data["fits_battle_obj"] else "NO",
               "yes" if data["fits_transition"] else "NO",
               "yes" if data["fits_sprite_limit"] else "NO"))
    print()
    print("%-6s %-8s %-8s %-8s %-8s %-8s %-8s %-8s" %
          ("level", "visible", "grid32", "grid16", "grid8", "hybrid8",
           "hybrid16", "hierarch"))
    for level in levels:
        print("%-6d %-8d %-8d %-8d %-8d %-8d %-8d %-8d" %
              (level["level"], level["visible_pixels"],
               level["grid32"]["tiles_live"], level["grid16"]["tiles_live"],
               level["grid8"]["tiles_live"], level["hybrid8"]["tiles_live"],
               level["hybrid16"]["tiles_live"],
               level["hierarchy"]["tiles_live"]))
    print()
    print("%-10s %-10s %-10s %-12s" % ("layout", "romTiles", "romBytes",
                                       "peakLevel"))
    for key, data in summary.items():
        print("%-10s %-10d %-10d %-12d" %
              (key, data["rom_tiles_all_levels"],
               data["rom_tiles_all_levels"] * 32,
               data["transition_peak_level"]))
    print("->", out)

    if args.markdown:
        markdown = pathlib.Path(args.markdown)
        rows = []
        for key, data in summary.items():
            rows.append("| %s | %d | %d | %d | %s | %s | %s |" %
                        (key, data["worst_tiles_live"], data["worst_sprites"],
                         data["transition_peak_tiles"],
                         "yes" if data["fits_battle_obj"] else "**NO**",
                         "yes" if data["fits_transition"] else "**NO**",
                         "yes" if data["fits_sprite_limit"] else "**NO**"))
        table = ("| layout | worst tiles | worst sprites | transition peak | "
                 "fits 336 tiles | fits transition | fits 128 sprites |\n"
                 "|---|---:|---:|---:|---|---|---|\n" + "\n".join(rows) + "\n")
        markdown.write_text(table, encoding="utf-8", newline="\n")
        print("->", markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
