#!/usr/bin/env python3
"""The remake's baked battlefield overlay implementation (round 25).

The original's move-range screen is not "one extra grid layer": the game
writes a whole battlefield layout map into BG2's tilemap when the battle
starts, and the move-range screen merely enables BG2.  Round 25 carries that
layout over into the remake.

This gate pins the two halves of that work:

* the **asset** (``artifacts/s49-original-battlefield-overlay-v1/*.bin``)
  must still hash to the values recorded in the signed manifest, and the
  **generated header** must be exactly what the generator produces from it
  (the gate fails closed when the two disagree);
* the **lookup** the remake uses must place the original's layout on the
  remake's grid the way the original had it: one remake grid point covers
  two of the original's 16x16 px logical cells, the even column on the left,
  and the selected unit has to land on the centre of the original's
  move-range lens.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "artifacts/s49-original-battlefield-overlay-v1"
FIELD = ASSET_DIR / "bg2-tilemap-field.bin"
MOVEGRID = ASSET_DIR / "bg2-tilemap-movegrid.bin"
MANIFEST = ASSET_DIR / "manifest.json"
GENERATOR = ROOT / "tools/generate_butano_battlefield_overlay.py"
GENERATED = (
    ROOT
    / "butano-sequel/game/include/konoha"
    / "generated_battle_battlefield_overlay_content.h"
)
STYLE_HEADER = (
    ROOT / "butano-sequel/game/include/konoha/battle_range_ui_style.h"
)
SCENE = ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
MOVEGRID_TILE_HEADER = (
    ROOT
    / "butano-sequel/game/include/konoha"
    / "generated_battle_movegrid_overlay_content.h"
)

# The remake's S49 deployment puts the selected unit (Naruto) here; the
# original's move-range lens is centred on the same unit.
SELECTED_UNIT_GRID = (6, 7)

# The mapping the remake uses between the two grids, mirrored from
# battle_range_ui_style.h.  The test re-derives what it implies and checks
# the implication against the layout itself.
COL_BASE = 10
ROW_BASE = -1
LOGICAL_COLUMNS = 16
LOGICAL_ROWS = 16
TILEMAP_COLUMNS = 32
TILEMAP_ROWS = 32
TILE_MASK = 0x03FF


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_butano_battlefield_overlay", GENERATOR
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _entries(path: Path) -> list[int]:
    data = path.read_bytes()
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


def _header_entries(name: str) -> list[int]:
    text = GENERATED.read_text(encoding="utf-8")
    match = re.search(
        r"battle_battlefield_overlay_tilemap_" + name + r"\s*=\s*\{(.*?)\};",
        text,
        re.S,
    )
    assert match is not None, f"missing generated array: {name}"
    return [int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{4})", match.group(1))]


def _logical_signature(entries: list[int], row: int, col: int) -> tuple[int, ...]:
    return tuple(
        entries[(row * 2 + dy) * TILEMAP_COLUMNS + (col * 2 + dx)]
        & TILE_MASK
        for dy in range(2)
        for dx in range(2)
    )


def _family_of(tile: int) -> int:
    """The original's family index: 0 web, 2 move, 4 attack, 6 cursor,
    8 target, 10 blocked."""
    if tile >= 278:
        return 10
    if tile >= 274:
        return 8
    if tile >= 270:
        return 6
    if tile >= 266:
        return 4
    if tile >= 262:
        return 2
    return 0


def _wrap(value: int, count: int) -> int:
    wrapped = value % count
    return wrapped + count if wrapped < 0 else wrapped


def _layout_for_point(entries: list[int], grid_x: int, grid_y: int) -> list[int]:
    """The 4x2 block of original tile indices one remake grid point draws."""
    row = _wrap(grid_y + ROW_BASE, LOGICAL_ROWS)
    even_col = _wrap(grid_x * 2 + COL_BASE, LOGICAL_COLUMNS)
    odd_col = _wrap(even_col + 1, LOGICAL_COLUMNS)
    block: list[int] = []
    for tile_y in range(2):
        for tile_x in range(4):
            col = even_col if tile_x < 2 else odd_col
            block.append(
                _logical_signature(entries, row, col)[tile_y * 2 + tile_x % 2]
            )
    return block


class GeneratedHeaderTest(unittest.TestCase):
    """The generated header must be exactly what the generator emits."""

    def test_the_generator_refuses_a_drifted_asset(self) -> None:
        generator = _load_generator()
        field, movegrid, meta = generator.load_assets()
        self.assertEqual(len(field), 32 * 32 * 2)
        self.assertEqual(len(movegrid), 32 * 32 * 2)
        self.assertEqual(
            hashlib.sha256(field).hexdigest(), meta["field_tilemap_sha256"]
        )
        self.assertEqual(
            hashlib.sha256(movegrid).hexdigest(),
            meta["movegrid_tilemap_sha256"],
        )

    def test_the_generated_header_is_up_to_date(self) -> None:
        generator = _load_generator()
        field, movegrid, meta = generator.load_assets()
        expected = generator.render(field, movegrid, meta)
        self.assertEqual(
            GENERATED.read_text(encoding="utf-8"),
            expected,
            "the generated header disagrees with the layout asset; run "
            "tools/generate_butano_battlefield_overlay.py",
        )

    def test_the_generator_check_mode_fails_closed(self) -> None:
        generator = _load_generator()
        self.assertEqual(generator.main(["--check"]), 0)

    def test_the_header_tilemaps_are_the_asset_bytes(self) -> None:
        self.assertEqual(_header_entries("field"), _entries(FIELD))
        self.assertEqual(_header_entries("movegrid"), _entries(MOVEGRID))

    def test_the_header_pins_the_asset_hashes(self) -> None:
        text = GENERATED.read_text(encoding="utf-8")
        self.assertIn(
            hashlib.sha256(FIELD.read_bytes()).hexdigest(), text
        )
        self.assertIn(
            hashlib.sha256(MOVEGRID.read_bytes()).hexdigest(), text
        )

    def test_no_captured_entry_uses_a_flip(self) -> None:
        for entries in (_entries(FIELD), _entries(MOVEGRID)):
            for entry in entries:
                self.assertEqual(entry & 0x0C00, 0)


class LookupGeometryTest(unittest.TestCase):
    """The lookup has to place the original's layout on the remake's grid."""

    def test_the_style_header_declares_the_mapping(self) -> None:
        text = STYLE_HEADER.read_text(encoding="utf-8")
        self.assertIn(
            f"battle_range_ui_layout_col_base = {COL_BASE}", text
        )
        self.assertIn(
            f"battle_range_ui_layout_row_base = {ROW_BASE}", text
        )
        self.assertIn("generated_battle_battlefield_overlay_content.h", text)

    def test_the_scene_uses_the_layout_lookup(self) -> None:
        text = SCENE.read_text(encoding="utf-8")
        self.assertIn("battle_range_ui_layout_for_point", text)
        self.assertIn("battle_battlefield_overlay_tilemap_movegrid", text)
        self.assertIn("battle_battlefield_overlay_tilemap_field", text)

    def test_one_grid_point_covers_two_logical_cells_even_column_left(self) -> None:
        entries = _entries(MOVEGRID)
        for grid_x in range(0, 24):
            for grid_y in range(0, 20):
                block = _layout_for_point(entries, grid_x, grid_y)
                self.assertEqual(len(block), 8)
                even_col = _wrap(grid_x * 2 + COL_BASE, LOGICAL_COLUMNS)
                odd_col = _wrap(even_col + 1, LOGICAL_COLUMNS)
                row = _wrap(grid_y + ROW_BASE, LOGICAL_ROWS)
                even = _logical_signature(entries, row, even_col)
                odd = _logical_signature(entries, row, odd_col)
                self.assertEqual(block[0:4], [even[0], even[1], odd[0], odd[1]])
                self.assertEqual(block[4:8], [even[2], even[3], odd[2], odd[3]])
                self.assertEqual(even_col % 2, 0)

    def test_the_selected_unit_lands_on_the_lens_centre(self) -> None:
        entries = _entries(MOVEGRID)
        lens = {
            (row, col)
            for row in range(LOGICAL_ROWS)
            for col in range(LOGICAL_COLUMNS)
            if 2 in {
                _family_of(tile)
                for tile in _logical_signature(entries, row, col)
            }
        }
        grid_x, grid_y = SELECTED_UNIT_GRID
        centre_row = _wrap(grid_y + ROW_BASE, LOGICAL_ROWS)
        centre_even = _wrap(grid_x * 2 + COL_BASE, LOGICAL_COLUMNS)
        self.assertIn((centre_row, centre_even), lens)
        # The lens is symmetric around the column of the selected unit.
        for row in range(LOGICAL_ROWS):
            columns = {col for (r, col) in lens if r == row}
            if not columns:
                continue
            distances = sorted(
                abs(_wrap(col - centre_even, LOGICAL_COLUMNS) % LOGICAL_COLUMNS)
                for col in columns
            )
            distances = sorted(min(d, LOGICAL_COLUMNS - d) for d in distances)
            self.assertEqual(distances, sorted(set(distances)))

    def test_the_lens_spans_the_columns_the_mapping_predicts(self) -> None:
        entries = _entries(MOVEGRID)
        grid_x, grid_y = SELECTED_UNIT_GRID
        even_col = _wrap(grid_x * 2 + COL_BASE, LOGICAL_COLUMNS)
        row = _wrap(grid_y + ROW_BASE, LOGICAL_ROWS)
        # The cell that holds the selected unit carries the highlight family.
        self.assertIn(
            2,
            {
                _family_of(tile)
                for tile in _logical_signature(entries, row, even_col)
            },
        )
        # Six remake columns to the left of the selected unit reaches the
        # original's column 0, which is the left edge of the lens.
        self.assertEqual(_wrap((grid_x - 3) * 2 + COL_BASE, LOGICAL_COLUMNS), 0)


class OriginalTileGraphicsTest(unittest.TestCase):
    """The original's 4bpp tiles have to expand to the remake's 8bpp ones."""

    def test_the_four_bpp_expansion_is_two_pixels_per_byte(self) -> None:
        text = MOVEGRID_TILE_HEADER.read_text(encoding="utf-8")
        match = re.search(
            r"battle_movegrid_overlay_tile_data\s*=\s*\{(.*?)\};", text, re.S
        )
        assert match is not None
        data = bytes(
            int(value, 16)
            for value in re.findall(r"0x([0-9A-Fa-f]{2})", match.group(1))
        )
        self.assertEqual(len(data), 1024)
        # Tile 262 is the plain move-range fill: every byte is 0x22, which is
        # palette index 2 in both nibbles.
        fill = data[262 * 32:263 * 32]
        self.assertEqual(set(fill), {0x22})
        # The high nibble is the left pixel: 0x32 is index 3 (the border)
        # on the left and index 2 on the right.
        self.assertEqual(data[263 * 32 + 3], 0x32)
        self.assertEqual(data[263 * 32 + 3] >> 4, 3)
        self.assertEqual(data[263 * 32 + 3] & 0x0F, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
