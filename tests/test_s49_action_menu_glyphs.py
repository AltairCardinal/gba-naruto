#!/usr/bin/env python3
"""The S49 action menu's glyph cells must match the original frame.

What this gate holds
--------------------
Every glyph cell the original S49 action menu draws is cut out of the
original frame and compared with the shipped ``battle_action_menu_font``
atlas, cell by cell.  The character-to-position map is taken from the identity
generator's own ``ACTION_MENU_ORIGINAL_GLYPH_SOURCES`` table, so it is owned by
the generator and cannot drift from it.  All 46 cells match exactly, and the
gate keeps them that way.

The guard against a measurement that looked like a defect
----------------------------------------------------------
The S49 ledger receipt ``artifacts/s49-ledger-evidence-v1/action-menu-glyphs.json``
reported two differing cells -- 隐 and 年, 105/128 and 69/128 -- and called them
bold-stroke defects in the remake's atlas.  They are not defects.  The ledger
tool transcribed the S49 menu as ``隐身术``/``十年手里剑`` and compared the frame
cells at (8,40) and (16,88) with the atlas cells of 隐 and 年, but the original
draws 瞬 and 字 there.  Both of those cells already match the original exactly.

``test_the_frame_cells_resolve_to_the_right_characters`` pins that resolution:
the frame cell at (8,40) is 瞬 and the one at (16,88) is 字, and 隐 and 年 are
not characters of the S49 action menu at all.  Without that guard the phantom
defect can be "repaired" again, which would put the wrong glyph into the 隐
and 年 cells of the atlas.

``test_the_atlas_outside_the_action_menu_cells_is_untouched`` pins a SHA-256
over the atlas with the 46 action-menu cells removed, so the 39 hand-fixed
cells of the atlas, and everything else in it, cannot drift.

The gate fails closed.  A missing original frame, an unresolvable
character-to-cell mapping, or a splice that would touch a byte outside the
repatched cells is an error, never a skip.
"""

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = ROOT / "butano-sequel/graphics/battle_action_menu_font.bmp"
ORIGINAL_FRAME = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-21-A.png"
)
FONT_HEADER = (
    ROOT
    / "butano-sequel/game/include/konoha/battle_action_menu_sprite_font.h"
)

GLYPH_WIDTH = 8
GLYPH_HEIGHT = 16
ASCII_GLYPH_COUNT = 94
ACTION_MENU_LEFT = 8

#: The two frame cells the ledger receipt called 隐 and 年, and what the
#: original actually draws there.
LEDGER_MISLABELLED_CELLS = (
    ("隐", 8, 40, "瞬"),
    ("年", 16, 88, "字"),
)

#: The four rows the original S49 action menu draws, and the text each row
#: holds.  The rows start at screen x=8 and the cells are 8 pixels apart.
ACTION_MENU_ROWS = (
    (40, "瞬身术"),
    (56, "影分身术"),
    (72, "忍者组合拳"),
    (88, "十字手里剑"),
)

#: SHA-256 over every byte of the atlas except the 46 action-menu cells.
#: Any change to any other byte of the atlas breaks this value.
ATLAS_OUTSIDE_ACTION_MENU_CELLS_SHA256 = (
    "2c99c625b4f2bac96f91dd552dd2991171fd07739c235694b41d7cd9362ce221"
)

#: The colour mapping the identity generator uses when it cuts a glyph out of
#: an original screenshot.  The same mapping is applied here so the cut can be
#: compared with the shipped atlas cell by cell.
GLYPH_BACKGROUND = (231, 247, 214)
GLYPH_SHADOW_COLORS = frozenset(
    {
        (173, 181, 156),
        (189, 173, 222),
        (231, 173, 140),
    }
)
GLYPH_MIDTONE_COLORS = frozenset(
    {
        (115, 123, 107),
        (148, 99, 239),
    }
)
GLYPH_FOREGROUND_INDEX = 2
GLYPH_SHADOW_INDEX = 5
GLYPH_MIDTONE_INDEX = 15


def _generator():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools import generate_butano_battle_identity_content as generator

    return generator


def _header_characters() -> list[str]:
    """The character order the shipped font header declares."""

    if not FONT_HEADER.is_file():
        raise AssertionError(f"missing font header: {FONT_HEADER}")
    text = FONT_HEADER.read_text(encoding="utf-8")
    match = re.search(
        r"battle_action_menu_font_utf8_characters\[\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(
            f"battle_action_menu_font_utf8_characters not found in {FONT_HEADER}"
        )
    return [
        value.encode().decode("unicode_escape") if "\\u" in value else value
        for value in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    ]


def _cell_index(character: str) -> int:
    """The atlas cell the character is stored in."""

    characters = _header_characters()
    if character not in characters:
        raise AssertionError(
            f"{character!r} is not in the action menu font character list"
        )
    return ASCII_GLYPH_COUNT + characters.index(character)


def _action_menu_cells() -> list[dict[str, object]]:
    """The action menu's glyph cells, taken from the generator's own table."""

    generator = _generator()
    characters = _header_characters()
    cells: list[dict[str, object]] = []
    for character, (
        source,
        left,
        top,
    ) in generator.ACTION_MENU_ORIGINAL_GLYPH_SOURCES.items():
        if source != generator.SCENARIO_49_ACTION_MENU_SOURCE:
            continue
        if character not in characters:
            raise AssertionError(
                f"{character!r} is cut from the S49 action menu but is not in "
                f"the action menu font character list"
            )
        cells.append(
            {
                "character": character,
                "cell": ASCII_GLYPH_COUNT + characters.index(character),
                "left": left,
                "top": top,
            }
        )
    cells.sort(key=lambda cell: (int(cell["top"]), int(cell["left"])))
    return cells


def _cut_glyph_indices(pixels, left: int, top: int) -> list[int]:
    """Cut one glyph cell out of the original frame as palette indices."""

    indices: list[int] = []
    for dy in range(GLYPH_HEIGHT):
        for dx in range(GLYPH_WIDTH):
            color = pixels[left + dx, top + dy]
            if color == GLYPH_BACKGROUND:
                indices.append(0)
            elif color in GLYPH_SHADOW_COLORS:
                indices.append(GLYPH_SHADOW_INDEX)
            elif color in GLYPH_MIDTONE_COLORS:
                indices.append(GLYPH_MIDTONE_INDEX)
            else:
                indices.append(GLYPH_FOREGROUND_INDEX)
    return indices


def _bmp_layout(data: bytes) -> dict[str, int]:
    """Read the atlas' BMP layout, independently of the repatch tool."""

    if len(data) < 54 or data[0:2] != b"BM":
        raise AssertionError("the action menu font is not a BMP file")
    pixel_offset = int.from_bytes(data[10:14], "little")
    width = int.from_bytes(data[18:22], "little")
    height = int.from_bytes(data[22:26], "little", signed=True)
    bits = int.from_bytes(data[28:30], "little")
    if bits != 8:
        raise AssertionError(f"the action menu font must be 8 bit, got {bits}")
    if width != GLYPH_WIDTH:
        raise AssertionError(f"unexpected action menu font width {width}")
    if height <= 0 or height % GLYPH_HEIGHT:
        raise AssertionError(f"unexpected action menu font height {height}")
    stride = ((width * bits + 31) // 32) * 4
    if stride != GLYPH_WIDTH:
        raise AssertionError(f"unexpected action menu font row stride {stride}")
    tiles = height // GLYPH_HEIGHT
    if pixel_offset + stride * height != len(data):
        raise AssertionError(
            "the action menu font's pixel data does not fill the file"
        )
    return {
        "pixel_offset": pixel_offset,
        "height": height,
        "stride": stride,
        "tiles": tiles,
    }


def _tile_byte_range(layout: dict[str, int], tile: int) -> tuple[int, int]:
    """The byte range a tile occupies in the file (BMP rows run bottom up)."""

    block = layout["stride"] * GLYPH_HEIGHT
    start = layout["pixel_offset"] + (layout["tiles"] - 1 - tile) * block
    return start, start + block


def _atlas_tile_indices(
    data: bytes, layout: dict[str, int], tile: int
) -> list[int]:
    """The palette indices a tile holds, read straight out of the file."""

    start, end = _tile_byte_range(layout, tile)
    block = data[start:end]
    indices: list[int] = []
    for row in range(GLYPH_HEIGHT - 1, -1, -1):
        base = row * layout["stride"]
        indices.extend(block[base:base + GLYPH_WIDTH])
    return indices


def _bytes_outside_action_menu_cells(
    data: bytes, layout: dict[str, int]
) -> bytes:
    """Every byte of the atlas except the action-menu cells."""

    ranges = sorted(
        _tile_byte_range(layout, int(cell["cell"]))
        for cell in _action_menu_cells()
    )
    kept = bytearray()
    position = 0
    for start, end in ranges:
        kept += data[position:start]
        position = end
    kept += data[position:]
    return bytes(kept)


def _original_pixels():
    from PIL import Image

    if not ORIGINAL_FRAME.is_file():
        raise AssertionError(f"missing original frame: {ORIGINAL_FRAME}")
    return Image.open(ORIGINAL_FRAME).convert("RGB").load()


class ActionMenuGlyphMapping(unittest.TestCase):
    """The character-to-cell mapping must be closed before anything else."""

    def setUp(self):
        self.cells = _action_menu_cells()

    def test_header_and_generator_agree_on_the_character_order(self):
        generator = _generator()
        self.assertEqual(
            _header_characters(),
            [
                str(item)
                for item in generator.load_identity_content(ROOT)[
                    "utf8_characters"
                ]
            ],
            "the shipped font header and the identity generator disagree "
            "about the character order; the cell mapping is not closed",
        )

    def test_the_action_menu_names_46_cells(self):
        self.assertEqual(len(self.cells), 46)
        self.assertEqual(
            len({int(cell["cell"]) for cell in self.cells}),
            46,
            "two action menu characters must not share an atlas cell",
        )

    def test_the_four_menu_rows_are_cut_from_the_generator_table(self):
        """The generator's table records each character's first position."""

        seen: set[str] = set()
        expected: dict[tuple[int, int], str] = {}
        for top, text in ACTION_MENU_ROWS:
            for index, character in enumerate(text):
                if character in seen:
                    continue
                seen.add(character)
                expected[(top, ACTION_MENU_LEFT + index * GLYPH_WIDTH)] = (
                    character
                )
        actual = {
            (int(cell["top"]), int(cell["left"])): str(cell["character"])
            for cell in self.cells
        }
        for position, character in expected.items():
            with self.subTest(character=character, position=position):
                self.assertEqual(actual.get(position), character)
        rows = {top for top, _text in ACTION_MENU_ROWS}
        in_rows = {
            position: character
            for position, character in actual.items()
            if position[0] in rows
            and ACTION_MENU_LEFT <= position[1] < ACTION_MENU_LEFT + 40
        }
        self.assertEqual(
            in_rows,
            expected,
            "the generator's table must name the menu rows' cells and "
            "nothing else",
        )


class ActionMenuGlyphCells(unittest.TestCase):
    """Every action-menu cell must equal the original frame."""

    def setUp(self):
        self.data = FONT_PATH.read_bytes()
        self.layout = _bmp_layout(self.data)
        self.pixels = _original_pixels()

    def test_every_action_menu_cell_matches_the_original_frame(self):
        for cell in _action_menu_cells():
            with self.subTest(character=cell["character"]):
                wanted = _cut_glyph_indices(
                    self.pixels, int(cell["left"]), int(cell["top"])
                )
                actual = _atlas_tile_indices(
                    self.data, self.layout, int(cell["cell"])
                )
                differing = sum(
                    1 for a, b in zip(actual, wanted) if a != b
                )
                self.assertEqual(
                    differing,
                    0,
                    f"{cell['character']} in the action menu font is "
                    f"{differing} pixels away from the original frame",
                )

    def test_all_seventeen_menu_row_cells_match_the_original_frame(self):
        """The same 17 cells the ledger receipt measured, labelled correctly.

        The ledger receipt compared the first cell of the first row with the
        atlas cell of 隐 and the second cell of the fourth row with the atlas
        cell of 年.  The original draws 瞬 and 字 there, so all 17 cells match.
        """

        for top, text in ACTION_MENU_ROWS:
            for index, character in enumerate(text):
                with self.subTest(character=character, top=top):
                    left = ACTION_MENU_LEFT + index * GLYPH_WIDTH
                    wanted = _cut_glyph_indices(self.pixels, left, top)
                    actual = _atlas_tile_indices(
                        self.data, self.layout, _cell_index(character)
                    )
                    differing = sum(
                        1 for a, b in zip(actual, wanted) if a != b
                    )
                    self.assertEqual(
                        differing,
                        0,
                        f"{character} in the action menu font is "
                        f"{differing} pixels away from the original frame",
                    )

    def test_the_atlas_outside_the_action_menu_cells_is_untouched(self):
        self.assertEqual(
            hashlib.sha256(
                _bytes_outside_action_menu_cells(self.data, self.layout)
            ).hexdigest(),
            ATLAS_OUTSIDE_ACTION_MENU_CELLS_SHA256,
            "a byte outside the action menu cells changed; the hand-fixed "
            "cells of the atlas must stay byte identical",
        )


class LedgerMislabelledCells(unittest.TestCase):
    """The 隐/「年」 cells of the ledger receipt are not action-menu cells."""

    def setUp(self):
        self.data = FONT_PATH.read_bytes()
        self.layout = _bmp_layout(self.data)
        self.pixels = _original_pixels()

    def test_the_frame_cells_resolve_to_the_right_characters(self):
        for mislabelled, left, top, actual in LEDGER_MISLABELLED_CELLS:
            with self.subTest(character=mislabelled):
                wanted = _cut_glyph_indices(self.pixels, left, top)
                cell = _cell_index(actual)
                stored = _atlas_tile_indices(self.data, self.layout, cell)
                self.assertEqual(
                    stored,
                    wanted,
                    f"the frame cell at ({left},{top}) is {actual!r}, not "
                    f"{mislabelled!r}",
                )

    def test_the_mislabelled_characters_are_not_action_menu_characters(self):
        action_characters = {
            str(cell["character"]) for cell in _action_menu_cells()
        }
        for mislabelled, _left, _top, _actual in LEDGER_MISLABELLED_CELLS:
            with self.subTest(character=mislabelled):
                self.assertNotIn(
                    mislabelled,
                    action_characters,
                    f"{mislabelled!r} is not a character of the S49 action "
                    f"menu; the ledger receipt mislabelled it",
                )

    def test_the_mislabelled_cells_do_not_shadow_an_action_menu_cell(self):
        """The 隐/「年」 cells must not carry an action-menu glyph."""

        action_cells = {
            int(cell["cell"]) for cell in _action_menu_cells()
        }
        for mislabelled, _left, _top, _actual in LEDGER_MISLABELLED_CELLS:
            with self.subTest(character=mislabelled):
                cell = _cell_index(mislabelled)
                self.assertNotIn(
                    cell,
                    action_cells,
                    f"{mislabelled!r} must not share a cell with an action "
                    f"menu character",
                )


class RepatchToolBehaviour(unittest.TestCase):
    """The repatch tool must fail closed and stay deterministic."""

    def setUp(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools.butano import repatch_battle_action_menu_font_glyphs as tool

        self.tool = tool

    def test_missing_original_frame_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.png"
            with self.assertRaises(self.tool.RepatchError):
                self.tool.repatch(
                    font_path=FONT_PATH,
                    original_path=missing,
                    output_path=Path(directory) / "out.bmp",
                )

    def test_a_foreign_byte_change_is_refused(self):
        data = FONT_PATH.read_bytes()
        layout = self.tool.parse_bmp_layout(data)
        cell = _cell_index("瞬")
        corrupted = bytearray(data)
        corrupted[0] = (corrupted[0] + 1) % 256
        with self.assertRaises(self.tool.RepatchError):
            self.tool.assert_only_tiles_changed(
                bytes(corrupted), data, layout, [cell]
            )

    def test_a_wrong_sized_tile_payload_is_refused(self):
        data = FONT_PATH.read_bytes()
        layout = self.tool.parse_bmp_layout(data)
        with self.assertRaises(self.tool.RepatchError):
            self.tool.splice_tiles(data, layout, {0: b"\x00" * 7})

    def test_the_shipped_atlas_needs_no_repatch(self):
        report = self.tool.repatch(
            font_path=FONT_PATH,
            original_path=ORIGINAL_FRAME,
            check_only=True,
        )
        self.assertEqual(report["cells_checked"], 46)
        self.assertEqual(
            report["cells_repatched"],
            0,
            "the shipped atlas already matches the original frame",
        )
        self.assertEqual(report["changed_bytes"], 0)

    def test_two_runs_produce_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.bmp"
            second = Path(directory) / "second.bmp"
            self.tool.repatch(
                font_path=FONT_PATH,
                original_path=ORIGINAL_FRAME,
                output_path=first,
            )
            self.tool.repatch(
                font_path=first,
                original_path=ORIGINAL_FRAME,
                output_path=second,
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                first.read_bytes(), FONT_PATH.read_bytes()
            )

    def test_a_broken_cell_is_repaired_without_touching_another_byte(self):
        """A damaged cell is repaired; the rest of the atlas must not move."""

        with tempfile.TemporaryDirectory() as directory:
            damaged = Path(directory) / "damaged.bmp"
            data = FONT_PATH.read_bytes()
            layout = self.tool.parse_bmp_layout(data)
            cell = _cell_index("瞬")
            start, end = self.tool.tile_byte_range(layout, cell)
            corrupted = bytearray(data)
            corrupted[start] = (corrupted[start] + 1) % 256
            damaged.write_bytes(bytes(corrupted))

            repaired = Path(directory) / "repaired.bmp"
            report = self.tool.repatch(
                font_path=damaged,
                original_path=ORIGINAL_FRAME,
                output_path=repaired,
            )
            self.assertEqual(report["cells_repatched"], 1)
            self.assertEqual(report["changed_bytes"], 1)
            self.assertEqual(
                repaired.read_bytes(), FONT_PATH.read_bytes()
            )


if __name__ == "__main__":
    unittest.main()
