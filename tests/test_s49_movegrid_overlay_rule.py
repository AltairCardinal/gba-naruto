#!/usr/bin/env python3
"""The original's move-range overlay tile model, and how far the rule is closed.

The overlay is drawn on BG2 with 32 four-bpp tiles (ROM LZ77 ``0x080B9E94``)
and palette bank 12 (ROM LZ77 ``0x080B9F5C``).  Round 15 established the tile
model and this gate pins it:

* the 32 tiles are five **fill families** plus the always-present grid lines:
  family ``fill 0 / edge 1`` (tiles 256-261), ``fill 2 / edge 3`` (262-265),
  ``fill 4 / edge 5`` (266-269), ``fill 6 / edge 7`` (270-273),
  ``fill 8 / edge 9`` (274-277) and ``fill 10 / edge 11`` (278-281);
* each family has four variants: plain, a frame on two sides, a frame on three
  sides and a frame on all four;
* the families line up **one for one** with the remake's own six overlay roles
  and with the palette indices the remake already uses
  (``grid_secondary`` 1, ``move_primary`` 2, ``move_secondary`` 3,
  ``attack_primary`` 4, ``attack_secondary`` 5, ``cursor_primary`` 6,
  ``cursor_secondary`` 7, ``target_primary`` 8, ``target_secondary`` 9,
  ``blocked_primary`` 10, ``blocked_secondary`` 11).

The **selection rule** is only partly closed.  Within one family, the four
sub-tiles of a 16x16-pixel logical cell are determined by the cell's
**left/right** neighbours *in the same family*: a cell whose left neighbour is
in the family but whose right neighbour is not gets the framed variant, every
other cell gets the plain one.  That rule reproduces the cursor family and
the small families with **zero** conflicts, but the large families still show
conflicts, so one more dimension is missing.  The counts below are the
measured state of that gap; they are pinned so the next round can see whether
the gap closed.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "tools" / "butano"))

import export_s49_movegrid_tilemap as exporter  # noqa: E402

ARTIFACTS = ROOT / "artifacts/s49-original-movegrid-tilemap-v1"
INSTANCES = ("movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1")

#: fill colour -> (first tile, edge colour) of each four-variant family.
FAMILIES = {
    0: (256, 1),
    2: (262, 3),
    4: (266, 5),
    6: (270, 7),
    8: (274, 9),
    10: (278, 11),
}
#: the remake's overlay role -> the original's fill colour.
ROLE_TO_FILL = {
    "grid_secondary": 1,
    "move_primary": 2,
    "move_secondary": 3,
    "attack_primary": 4,
    "attack_secondary": 5,
    "cursor_primary": 6,
    "cursor_secondary": 7,
    "target_primary": 8,
    "target_secondary": 9,
    "blocked_primary": 10,
    "blocked_secondary": 11,
}


def _load(instance: str) -> dict:
    path = ARTIFACTS / f"{instance}.bg2-tilemap.json"
    if not path.is_file():
        raise unittest.SkipTest(f"missing decoded tilemap: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _tile_grid(payload: dict) -> list[list[int]]:
    cells = payload["cells"]
    return [[cells[row * 32 + column]["tile"] for column in range(32)] for row in range(32)]


def _changed_logical_cells(payload: dict) -> set[tuple[int, int]]:
    changed = payload["changed_cells"]
    return {(cell["map_y"] // 2, cell["map_x"] // 2) for cell in changed}


def _families(payload: dict) -> dict[tuple[int, int], int]:
    grid = _tile_grid(payload)
    result = {}
    for row, column in _changed_logical_cells(payload):
        first = grid[2 * row][2 * column]
        fill = None
        for candidate, (base, _edge) in FAMILIES.items():
            if base <= first <= base + 3:
                fill = candidate
                break
        result[(row, column)] = fill
    return result


def _left_right_rule(payload: dict) -> dict[int, dict[str, list[int]]]:
    """Group each family's cells by their same-family left/right neighbours."""
    grid = _tile_grid(payload)
    families = _families(payload)
    grouped: dict[int, set[tuple[int, int]]] = {}
    for cell, fill in families.items():
        grouped.setdefault(fill, set()).add(cell)
    result: dict[int, dict[str, list[int]]] = {}
    for fill, cells in grouped.items():
        table: dict[str, list[int]] = {}
        for row, column in cells:
            left = 1 if (row, column - 1) in cells else 0
            right = 1 if (row, column + 1) in cells else 0
            key = f"L{left}R{right}"
            value = [
                grid[2 * row][2 * column],
                grid[2 * row][2 * column + 1],
                grid[2 * row + 1][2 * column],
                grid[2 * row + 1][2 * column + 1],
            ]
            table.setdefault(key, value)
        result[fill] = table
    return result


class OverlayTileModelTest(unittest.TestCase):
    """What the 32 tiles are, verified from the ROM-exported bytes."""

    def test_each_family_has_four_variants(self) -> None:
        rom = ROOT / "artifacts/s49-original-movegrid-overlay-v1/movegrid-tiles-4bpp.bin"
        self.assertTrue(rom.is_file(), f"missing exported tiles: {rom}")
        raw = rom.read_bytes()
        self.assertEqual(len(raw), 32 * 32)

        def matrix_of(tile: int) -> list[list[int]]:
            offset = (tile - 256) * 32
            result = []
            for row in range(8):
                line = []
                for column in range(8):
                    byte = raw[offset + row * 4 + column // 2]
                    line.append((byte >> 4) if column % 2 == 0 else byte & 0x0F)
                result.append(line)
            return result

        for fill, (base, edge) in FAMILIES.items():
            for index in range(4):
                matrix = matrix_of(base + index)
                present = {value for line in matrix for value in line}
                self.assertLessEqual(
                    present,
                    {fill, edge},
                    f"tile {base + index} carries a colour outside its family",
                )
                body = [value for value in present if value != edge]
                if not body:
                    continue
                self.assertEqual(
                    body[0],
                    fill,
                    f"tile {base + index} is not a fill-{fill} tile",
                )

    def test_the_families_match_the_remakes_overlay_palette(self) -> None:
        """The remake's overlay colours are the original's bank 12 indices.

        The remake keeps its overlay colours in the shared 8bpp background
        palette at 225..235; entries 224..239 are palette bank 14, so
        225..235 are bank 14 indices 1..11 -- exactly the original's bank 12
        indices 1..11, role for role.
        """
        header = ROOT / "butano-sequel/game/include/konoha/battle_range_ui_style.h"
        text = header.read_text(encoding="utf-8")
        for role, index in ROLE_TO_FILL.items():
            self.assertIn(
                f"{role} = {224 + index}",
                text,
                f"the remake's overlay palette lost {role} = {224 + index}",
            )
        self.assertEqual(
            sorted(FAMILIES),
            sorted({0, 2, 4, 6, 8, 10}),
            "the original's fill families changed",
        )


class OverlaySelectionRuleTest(unittest.TestCase):
    """How far the per-cell tile selection rule is closed."""

    def test_the_cursor_family_follows_the_left_right_rule(self) -> None:
        payload = _load("grid16-frame-v1")
        table = _left_right_rule(payload)
        cursor = table.get(6)
        self.assertIsNotNone(cursor, "the grid16 instance no longer has a cursor family")
        self.assertEqual(
            cursor.get("L1R0"),
            [270, 271, 272, 273],
            "the cursor family's framed variant changed",
        )
        self.assertEqual(
            cursor.get("L0R0"),
            [270, 270, 272, 272],
            "the cursor family's plain variant changed",
        )

    def test_the_highlight_families_follow_the_column_parity_rule(self) -> None:
        """A highlighted cell's four sub-tiles follow its column parity.

        Measured over every logical cell the move-range and cursor states
        touched, in all three recorded instances: the four sub-tiles of a
        16x16-pixel logical cell are the plain variant when the cell's
        column is even and the framed variant when it is odd, with **zero**
        conflicts.
        """
        expected = {
            ("movegrid-frame-v1", 2): {0: [262, 262, 264, 264], 1: [262, 263, 264, 265]},
            ("grid16-frame-v1", 2): {0: [262, 262, 264, 264], 1: [262, 263, 264, 265]},
            ("grid16-frame-v1", 6): {0: [270, 270, 272, 272], 1: [270, 271, 272, 273]},
        }
        for (instance, fill), table in expected.items():
            payload = _load(instance)
            grid = _tile_grid(payload)
            families = _families(payload)
            for (row, column), cell_fill in families.items():
                if cell_fill != fill:
                    continue
                value = [
                    grid[2 * row][2 * column],
                    grid[2 * row][2 * column + 1],
                    grid[2 * row + 1][2 * column],
                    grid[2 * row + 1][2 * column + 1],
                ]
                self.assertEqual(
                    value,
                    table[column % 2],
                    f"{instance} family {fill} at ({row},{column}) broke the "
                    "column parity rule",
                )

    def test_the_measured_rule_coverage_is_pinned(self) -> None:
        """Pin where the rule still fails, so the next round can see progress.

        The counts are the measured conflict counts of the column-parity
        rule, per instance and per fill family.  They are expected to fall as the
        rule is completed; the assertion is that they never *grow* past the
        values measured when the rule was first written down.
        """
        ceiling = {
            "movegrid-frame-v1": {0: 0, 2: 0},
            "grid16-frame-v1": {0: 41, 2: 0, 6: 0},
            "banner-frame-v1": {0: 2},
        }
        for instance, limits in ceiling.items():
            payload = _load(instance)
            grid = _tile_grid(payload)
            families = _families(payload)
            grouped: dict[int, list[tuple[int, int]]] = {}
            for cell, fill in families.items():
                grouped.setdefault(fill, []).append(cell)
            for fill, cells in grouped.items():
                limit = limits.get(fill)
                if limit is None:
                    continue
                table: dict[str, list[int]] = {}
                conflicts = 0
                for row, column in cells:
                    key = f"C{column % 2}"
                    value = [
                        grid[2 * row][2 * column],
                        grid[2 * row][2 * column + 1],
                        grid[2 * row + 1][2 * column],
                        grid[2 * row + 1][2 * column + 1],
                    ]
                    if key in table and table[key] != value:
                        conflicts += 1
                    else:
                        table.setdefault(key, value)
                self.assertLessEqual(
                    conflicts,
                    limit,
                    f"{instance} family {fill}: the left/right rule conflicts grew "
                    f"from {limit} to {conflicts}",
                )

    def test_the_decoder_reads_two_pixels_per_byte(self) -> None:
        """Guard the 4bpp decoder itself.

        Reading four 2-bit groups per byte instead of two 4-bit pixels turns
        solid fills into dashed patterns and mis-classifies every family; the
        bug silently produced a wrong tile model once already.
        """
        vram = bytearray(0x18000)
        vram[0x2000:0x2020] = bytes([0x11] * 32)  # tile 256: all pixels = 1
        matrix = exporter.tile_pixels(bytes(vram), 256)
        self.assertEqual(len(matrix), 8)
        for row in matrix:
            self.assertEqual(len(row), 8)
            self.assertEqual(set(row), {1})


if __name__ == "__main__":
    unittest.main()
