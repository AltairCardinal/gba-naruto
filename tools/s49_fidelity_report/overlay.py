"""The per-cell overlay family map -- the second dimension of the residual.

The overlay layer is a grid of cells, and every cell carries one of a small
vocabulary of *families* (the lattice, the move range, the cursor, ...).  The
original's vocabulary comes from its own tile indices (256..287) and the
remake's from its style header's tile ranges (1..76); the two are the same
seven names, so the two layers can be compared cell by cell.

The family vocabulary and the tile decoding are **re-used read-only** from the
streams that own them:

* ``tools/s49_rule_probe/overlay_ground_truth.py`` -- the original's
  ``TILE_FAMILY`` table and the logical cell geometry.
* ``tools/s49_overlay_align/compare_overlay_families.py`` -- the remake's
  ``remake_family`` decoder and the VRAM signature that locates the remake's
  overlay map.

Nothing in either directory is modified by this module; the cell *counting*
and the offset search are re-implemented here so that a comparison of 25 x 35
frame pairs does not build a per-cell difference list it never reads.
"""

from __future__ import annotations

import hashlib
import struct
import sys

from .paths import OVERLAY_ALIGN, RULE_PROBE

for _extra in (str(OVERLAY_ALIGN), str(RULE_PROBE)):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from compare_overlay_families import (  # noqa: E402
    LOGICAL_COLS, LOGICAL_ROWS, find_overlay_map, remake_family,
)
from overlay_ground_truth import TILE_FAMILY  # noqa: E402

FAMILY_NAMES = ("blank", "edge", "hatch", "line_alt", "band", "hatch_shift",
                "solid")
# How a logical cell decides its family when its four 8x8 quadrants disagree:
# the family with the most quadrants wins, ties are broken by this priority.
FAMILY_PRIORITY = {"solid": 6, "hatch": 5, "band": 4, "line_alt": 3,
                   "edge": 2, "hatch_shift": 2, "blank": 0}

# The original's BG2 tilemap lives at this VRAM offset (the ground truth
# exporter's BG2_SCREEN_BASE_OFFSET for screen base block 2).
ORIGINAL_OVERLAY_OFFSET = 0x1000
# The remake's overlay map is located by signature instead (its screen space
# layer has no fixed base).
REMAKE_TILE_MAX = 77


def blank_grid() -> list[list[str]]:
    return [["blank"] * LOGICAL_COLS for _ in range(LOGICAL_ROWS)]


def _dominant(families: list[str]) -> str:
    counts: dict[str, int] = {}
    for family in families:
        counts[family] = counts.get(family, 0) + 1
    return max(counts.items(),
               key=lambda item: (item[1], FAMILY_PRIORITY.get(item[0], 1)))[0]


def original_grid(vram: bytes, offset: int = ORIGINAL_OVERLAY_OFFSET) -> list[list[str]]:
    """The original's overlay map as a 16 x 16 grid of logical cell families.

    The map is in **map space**: one logical cell is 16x16 px, four 8x8
    tilemap entries, and the whole 256x256 px map is 16 x 16 logical cells.
    """
    entries = struct.unpack_from("<1024H", vram, offset)
    quadrants: dict[tuple[int, int], list[str]] = {}
    for index, entry in enumerate(entries):
        family = TILE_FAMILY.get(entry & 0x3FF, "other")
        map_x, map_y = index % 32, index // 32
        key = (map_x // 2, map_y // 2)
        quadrants.setdefault(key, []).append(family)
    grid = blank_grid()
    for (cell_x, cell_y), families in quadrants.items():
        if cell_x < LOGICAL_COLS and cell_y < LOGICAL_ROWS:
            grid[cell_y][cell_x] = _dominant(families)
    return grid


def remake_grid(vram: bytes) -> tuple[list[list[str]] | None, dict]:
    """The remake's overlay map as a 16 x 16 grid of logical cell families."""
    base = find_overlay_map(vram, REMAKE_TILE_MAX)
    if base < 0:
        # No overlay map in VRAM: the overlay layer is **not displayed** (the
        # action menu re-uses the very same BG map, and the overlay is off
        # while a menu is open).  That is an *empty* overlay, not a missing
        # measurement, so the grid is blank rather than absent.
        return blank_grid(), {"overlay_map": None}
    cells: dict[tuple[int, int], str] = {}
    entries = struct.unpack_from("<1024H", vram, base)
    for index, entry in enumerate(entries):
        tile = entry & 0x3FF
        if tile == 0:
            continue
        family, tile_x, tile_y = remake_family(tile)
        if family == "blank":
            continue
        entry_x, entry_y = index % 32, index // 32
        key = (entry_x - tile_x, entry_y - tile_y)
        if key in cells and cells[key] != family:
            cells[key] = "mixed"
        else:
            cells[key] = family
    if not cells:
        return blank_grid(), {"overlay_map": base}
    lefts = sorted({key[0] for key in cells})
    tops = sorted({key[1] for key in cells})
    left_origin, top_origin = lefts[0], tops[0]
    grid = blank_grid()
    for (left, top), family in cells.items():
        column = (left - left_origin) // 4
        row = (top - top_origin) // 2
        logical_column = column * 2
        logical_row = row
        if 0 <= logical_column < LOGICAL_COLS and 0 <= logical_row < LOGICAL_ROWS:
            for half in (0, 1):
                index = logical_column + half
                if index >= LOGICAL_COLS:
                    continue
                if grid[logical_row][index] not in ("blank", family):
                    grid[logical_row][index] = "mixed"
                else:
                    grid[logical_row][index] = family
    return grid, {"overlay_map": base, "cell_left_origin": left_origin,
                  "cell_top_origin": top_origin}


def grid_digest(grid: list[list[str]]) -> str:
    payload = "|".join("".join(cell for cell in row) for row in grid)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def grid_counts(grid: list[list[str]]) -> dict:
    counts: dict[str, int] = {}
    for row in grid:
        for family in row:
            counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def lit_cells(grid: list[list[str]]) -> int:
    return sum(1 for row in grid for family in row if family != "blank")


def compare_counts(left: list[list[str]], right: list[list[str]],
                   offset_x: int, offset_y: int) -> dict:
    """Count the cells that differ, with the right grid shifted."""
    original_only = remake_only = mismatch = both_lit = 0
    for y in range(LOGICAL_ROWS):
        for x in range(LOGICAL_COLS):
            other_x = x + offset_x
            other_y = y + offset_y
            a = left[y][x]
            b = "blank"
            if 0 <= other_x < LOGICAL_COLS and 0 <= other_y < LOGICAL_ROWS:
                b = right[other_y][other_x]
            a_lit = a != "blank"
            b_lit = b != "blank"
            if a_lit and b_lit:
                both_lit += 1
                if a != b:
                    mismatch += 1
            elif a_lit:
                original_only += 1
            elif b_lit:
                remake_only += 1
    return {
        "offset": [offset_x, offset_y],
        "both_lit": both_lit,
        "original_only": original_only,
        "remake_only": remake_only,
        "family_mismatches": mismatch,
        "residual": original_only + remake_only + mismatch,
    }


def best_offset(left: list[list[str]], right: list[list[str]]) -> dict:
    """The offset at which the two overlay grids agree best.

    The original's overlay lives in map space and the remake's in screen
    space, so the two are aligned by searching the 16 x 16 possible cell
    offsets -- the same correspondence the overlay alignment stream uses.
    """
    best = None
    for offset_y in range(LOGICAL_ROWS):
        for offset_x in range(LOGICAL_COLS):
            result = compare_counts(left, right, offset_x, offset_y)
            score = (result["both_lit"] - result["family_mismatches"],
                     -result["residual"])
            if best is None or score > best[0]:
                best = (score, result)
    return best[1]
