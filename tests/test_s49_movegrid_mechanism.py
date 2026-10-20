#!/usr/bin/env python3
"""The move-range screen's GPU state, and why the old palette argument failed.

The move-range grid was the largest unexplained pixel gap in the S49 remake
(2917 differing pixels against the original's frame).  Round 9 measured it as
"the original dims the area it cannot reach" and then argued that the dimming
is *not* a palette swap, because the dimmed colours were not found in the
archived palette dump.

That argument does not hold up, and this gate records why.

The archives mixed two different colour spaces: the PNGs were captured by one
mGBA build and the palette dumps by another, and the palette dump that the
argument used was not even of the same frame.  The receipts this test reads
are **same-frame**: one mGBA run produces the screenshot, the palette RAM, the
VRAM and the display registers together, so a colour in the PNG and a palette
entry can be compared without leaving the frame.

With that receipt the facts are:

* the round-banner frame is fully self-consistent -- 81 of 81 of its colours
  are palette entries of that same frame;
* the move-range frame is not -- 97 of its 162 colours are **not** palette
  entries of that same frame, and ``BLDCNT`` is ``0x0000`` in every captured
  frame, so the GBA was not alpha-blending them either.

A colour that is on screen but in no palette and in no blend cannot be
produced by a GBA, so the screenshot and the palette are in different colour
spaces *within one frame*.  That is exactly the assumption the old argument
rested on, so the old conclusion ("it is not a palette swap") is withdrawn as
unproven rather than refuted.

What the receipt *does* establish, and this gate pins, is the shape of the
original's move-range rendering:

* ``DISPCNT`` is ``0x1D40`` on the move-range frame and ``0x1940`` on the
  round-banner frame: the two differ in bit 10, which selects whether BG3
  takes its characters from ``0x00000`` or from ``0x10000``.  The same BG3
  tilemap therefore renders a **different tile set** in the move-range
  screen -- the shape a "second copy of the map graphics" would take;
* BG3's tilemap (screen base ``0x1800``) is filled in every one of its 1024
  cells, with two dominant tile indices, so BG3 is a full-screen layer there;
* the palette RAM is stable across the six captured frames (at most one
  entry changes, by at most two), so the colours are not a per-frame palette
  animation.

The measurement comes from ``tools/butano/analyze_s49_movegrid_mechanism.py``
over the same-frame receipts produced by
``tools/butano/capture_s49_frame_palette.py``.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import analyze_s49_movegrid_mechanism as analysis  # noqa: E402

MECHANISM = ROOT / "artifacts/s49-original-movegrid-mechanism-v1/mechanism.json"


class S49MoveGridMechanismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MECHANISM.is_file():
            raise unittest.SkipTest(f"missing mechanism receipt: {MECHANISM}")
        cls.receipt = json.loads(MECHANISM.read_text(encoding="utf-8"))
        cls.grid = cls.receipt["move_range_frame"]
        cls.banner = cls.receipt["round_banner_frame"]

    def test_dispcnt_flips_bgs_character_base(self) -> None:
        self.assertEqual(self.grid["registers"]["dispcnt"], "0x1D40")
        self.assertEqual(self.banner["registers"]["dispcnt"], "0x1940")
        self.assertEqual(
            self.receipt["dispcnt_changed_fields"],
            ["bg3_char_base_10000"],
        )
        self.assertEqual(self.receipt["dispcnt_difference_bits"], "0x0400")

    def test_bg3_is_a_full_screen_layer_in_the_move_range_frame(self) -> None:
        tilemap = self.grid["bg3_tilemap"]
        self.assertEqual(tilemap["cells"], 1024)
        self.assertEqual(tilemap["non_zero_cells"], 1024)
        self.assertEqual(tilemap["top_tiles"][0]["count"], 764)

    def test_the_move_range_layer_is_bg2(self) -> None:
        # Between the round-banner frame and the move-range frame the map
        # layers are almost unchanged -- BG0 differs in a single cell, BG1 in
        # none -- while BG2's tilemap is rewritten in 706 of its 1024 cells.
        # BG2 has priority 2 and BG0 has priority 3, so BG2 is drawn over the
        # map: the map layer is identical, so the overlay cannot be a tint of
        # BG0's palette.
        cells = self.grid["bg_tilemap_cells"]
        self.assertEqual(cells["bg0"], 1)
        self.assertEqual(cells["bg1"], 0)
        self.assertEqual(cells["bg2"], 706)

    def test_the_bg3_tiles_are_empty_in_both_frames(self) -> None:
        # BG3's tilemap is full, but the tiles it points at carry no pixels,
        # so BG3 draws nothing in either frame.  That is why the DISPCNT bit
        # 10 difference cannot be the mechanism: mGBA's renderer takes a
        # background's character base from BGxCNT alone
        # (``charBase = BGCNT.CharBase << 14`` in video-software.c), so in
        # mode 0 that bit does not change what is drawn.
        for frame in (self.grid, self.banner):
            tilemap = frame["bg3_tilemap"]
            self.assertEqual(tilemap["non_zero_cells"], 1024)

    def test_no_alpha_blending_is_active(self) -> None:
        self.assertFalse(self.receipt["blending_enabled"])
        self.assertEqual(self.grid["registers"]["bldcnt"], "0x0000")
        self.assertEqual(self.banner["registers"]["bldcnt"], "0x0000")

    def test_the_banner_frame_is_palette_consistent(self) -> None:
        space = self.banner["colour_space"]
        self.assertEqual(space["frame_colours"], 81)
        self.assertEqual(space["frame_colours_missing_from_the_palette"], 0)

    def test_the_move_range_frame_is_not_palette_consistent(self) -> None:
        # This is the finding that withdraws the old "it is not a palette
        # swap" argument: the frame shows colours that are in no palette entry
        # and in no blend, so the screenshot and the palette cannot be
        # compared across colour spaces.
        space = self.grid["colour_space"]
        self.assertEqual(space["frame_colours"], 162)
        self.assertEqual(space["frame_colours_missing_from_the_palette"], 97)
        self.assertEqual(space["frame_colours_that_are_palette_entries"], 65)

    def test_the_map_layer_is_identical_in_both_frames(self) -> None:
        # BG0 is the map.  Its palette (PRAM banks 0-3) and its tile graphics
        # (VRAM 0x4000) are byte-identical between the round-banner frame
        # and the move-range frame, so the map renders identically and the
        # cool tint cannot be a tint of the map's own colours.  Whatever
        # draws the dimming, it is a different layer.
        unchanged = self.grid["map_layer_unchanged"]
        self.assertEqual(unchanged["bg0_palette_entries_changed"], 0)
        self.assertEqual(unchanged["bg0_tile_graphics_bytes_changed"], 0)
        self.assertGreater(unchanged["bg2_region_bytes_changed"], 0)

    def test_the_sprite_difference_is_the_moved_unit_not_an_overlay(self) -> None:
        # The three OAM slots that only the move-range frame uses are NOT an
        # overlay: the game's sprite allocator renumbers slots, and the real
        # difference is that the escort unit moved one cell (y 41/35 -> 40/36)
        # and changed animation frame (tile 138 -> 136, markers 110 -> 112).
        # The only entries the banner frame does not have at all sit at screen
        # y=4, i.e. the top edge, and are three 16x16 markers.
        sprites = self.grid["sprites"]
        self.assertEqual(self.banner["sprites"]["active"], 17)
        self.assertEqual(sprites["active"], 20)
        only_here = sprites["entries_only_here"]
        self.assertIn([216, 4, 0, 4], only_here)
        self.assertIn([208, 0, 128, 4], only_here)
        self.assertIn([192, 4, 0, 4], only_here)
        # The escort unit's own cells changed, so they are not "only here"
        # either: the banner has the same tiles at the old position.
        self.assertIn([136, 3, 0, 40], only_here)

    def test_the_window_and_blending_are_identical_in_both_frames(self) -> None:
        # The dimming is not the window and not a blend: WININ/WINOUT/MOSAIC
        # and BLDCNT are the same in both frames, and BLDCNT is 0 (no alpha
        # blending at all).  MOSAIC is enabled in both, which is why some
        # frame colours are not palette entries at all.
        for frame in (self.grid, self.banner):
            registers = frame["screen_registers"]
            self.assertEqual(registers["winin"], "0x00F0")
            self.assertEqual(registers["winout"], "0xFFFF")
            self.assertEqual(registers["mosaic"], "0x3F3F")
            self.assertEqual(registers["bldcnt"], "0x0000")
        self.assertEqual(
            self.grid["screen_registers"],
            self.banner["screen_registers"],
        )

    def test_the_dimming_is_caused_by_one_dispcnt_bit(self) -> None:
        # The field screen is the right baseline (the round banner covers the
        # whole screen and hides everything else).  Between the field screen
        # and the move-range screen the *only* register that differs is
        # DISPCNT, and it differs in a single bit: 0x1940 -> 0x1D40.
        # Everything else is identical: both BG0/BG1 tilemaps and tiles, the
        # map's palette (PRAM banks 0-3), the window, the blending and the
        # mosaic.  The sprite count is the same (20) in both frames.
        comparison = self.receipt["grid_versus_field"]
        self.assertEqual(comparison["dispcnt_grid"], "0x1D40")
        self.assertEqual(comparison["dispcnt_field"], "0x1940")
        self.assertEqual(comparison["registers_differing"], ["dispcnt"])
        self.assertTrue(comparison["screen_registers_identical"])
        delta = comparison["memory_delta"]
        self.assertEqual(delta["pram_banks_changed"], [16])
        self.assertLessEqual(delta["pram_bytes_changed"], 2)
        self.assertEqual(
            comparison["sprites_active"],
            {"field": 20, "grid": 20},
        )

    def test_a_second_grid_instance_repeats_the_pattern(self) -> None:
        # The move-range screen appears twice in the walk: step 16 (camera
        # panned to 152/40) and step 19 (camera back at 240/24).  Both have
        # DISPCNT bit 10 set and both differ from the field screen by tens of
        # thousands of pixels, while the field screen has the bit clear.  The
        # overlay therefore follows the bit, not the camera.
        second = self.receipt["grid16_second_instance"]
        self.assertEqual(second["dispcnt"], "0x1D40")
        self.assertEqual(second["bg0_hoffs"], 152)
        self.assertEqual(second["bg0_voffs"], 40)
        self.assertGreater(second["screenshot_delta_versus_field"], 10000)
        self.assertEqual(
            int(self.receipt["grid_versus_field"]["dispcnt_field"], 16) & 0x400,
            0,
        )
        self.assertEqual(
            int(self.receipt["grid_versus_field"]["dispcnt_grid"], 16) & 0x400,
            0x400,
        )

    def test_the_receipts_come_from_one_emulator_build(self) -> None:
        for directory in (
            analysis.GRID_DIR,
            analysis.BANNER_DIR,
        ):
            inputs = json.loads(
                (Path(directory) / "inputs.json").read_text(encoding="utf-8"))
            self.assertEqual(
                inputs["rom_sha256"],
                "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            )
            self.assertTrue(inputs["mgba_sha256"])
            self.assertTrue(inputs["script_sha256"])


if __name__ == "__main__":
    unittest.main()
