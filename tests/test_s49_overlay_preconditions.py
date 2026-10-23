#!/usr/bin/env python3
"""The S49 overlay wiring must start on verified ground.

``docs/butano-wiring-roadmap.md`` (W2) refuses to let the overlay work start
by editing code, because the 26th round measured 16,533 differing pixels
against a 2,917 baseline and never found out why: three facts were never
checked.

These tests pin down the four verdicts the precondition verifier produces,
and -- more importantly -- they pin down the *failure* behaviour, because a
check that cannot fail is not a check:

* the remake's 8bpp overlay tiles must decode back to the original's 4bpp
  tiles, and the 4bpp byte's **low** nibble is the left pixel;
* the visible 30x20 window must be the one the original's own scroll
  registers select, and the recipe's tile indices must stay inside the
  original's overlay tile set;
* the S49 battle overlay's closed original side is **this tree's runtime
  receipt**, not a reverse family -- the reverse family
  ``overview-gradient-overlay-v1`` is the character-overview gradient
  overlay on BG0, a different layer with a different palette bank and a
  different tile set;
* the new upload must fit the 8bpp tile set without growing it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "verify_s49_overlay_preconditions.py"
REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")

sys.path.insert(0, str(ROOT))

from tools.butano.verify_s49_overlay_preconditions import (  # noqa: E402
    check_source_identity,
    check_tiles,
    check_upload,
    check_visible_window,
    decode_4bpp_tile,
)


class TileDecodingTest(unittest.TestCase):
    def test_the_low_nibble_is_the_left_pixel(self) -> None:
        """Getting the nibble order backwards is a 2,917 -> 16,533 error.

        The 26th round's correction: a 4bpp byte holds two pixels and the
        **low** nibble is the left one.
        """
        block = bytes([0x12] + [0x00] * 31)
        pixels = decode_4bpp_tile(block)
        self.assertEqual(pixels[0], 2)
        self.assertEqual(pixels[1], 1)


class PreconditionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = None

    def _run(self) -> dict:
        out_dir = ROOT / "artifacts" / "s49-overlay-preconditions-v1"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(ROOT),
                "--reverse-root",
                str(REVERSE_ROOT),
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(
            (out_dir / "preconditions.json").read_text(encoding="utf-8")
        )

    def test_every_precondition_holds(self) -> None:
        payload = self._run()
        failed = [check["check"] for check in payload["checks"] if not check["ok"]]
        self.assertEqual(failed, [], failed)
        self.assertTrue(payload["ok"])

    def test_the_four_checks_are_the_ones_the_roadmap_names(self) -> None:
        payload = self._run()
        self.assertEqual(
            sorted(check["check"] for check in payload["checks"]),
            ["source_identity", "tiles", "upload", "visible_window"],
        )


class CheckBehaviourTest(unittest.TestCase):
    """A check that cannot fail is not a check."""

    def test_a_tampered_tile_is_rejected(self) -> None:
        # The sheet has to be full size: 32 blocks of 4bpp and 32 of 8bpp.
        original = bytearray(32 * 32)
        original[0] = 0x12
        expanded = [0x00] * (32 * 64)
        # 0x12 is two pixels: the low nibble (2) is the left one, the high
        # nibble (1) the right one.  The expansion is 224 + v.
        expanded[0] = 226
        expanded[1] = 225
        self.assertTrue(check_tiles(bytes(original), expanded)["ok"])
        expanded[1] = 0  # the second pixel is not expanded
        self.assertFalse(check_tiles(bytes(original), expanded)["ok"])

    def test_a_window_that_leaves_the_original_tile_set_is_rejected(self) -> None:
        tilemap = [0xC100] * (32 * 32)
        states = {
            "movegrid-frame-v1": {
                "visible_map_cols": [(column + 30) % 32 for column in range(30)],
                "visible_map_rows": [(row + 3) % 32 for row in range(20)],
                "bg2_hoffs": 240,
                "bg2_voffs": 24,
            }
        }
        self.assertTrue(check_visible_window(tilemap, states)["ok"])
        # A tile outside 256..287 must be rejected.
        tilemap[3 * 32 + 30] = 0xC000 | 99
        result = check_visible_window(tilemap, states)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("outside" in problem for problem in result["problems"]),
            result["problems"],
        )

    def test_a_window_that_ignores_the_scroll_is_rejected(self) -> None:
        tilemap = [0] * (32 * 32)
        for row in range(32):
            for column in range(32):
                # The value has to depend on the column too, otherwise any
                # column permutation would look identical.
                tilemap[row * 32 + column] = 0xC100 | (256 + (row + column) % 30)
        states = {
            "movegrid-frame-v1": {
                "visible_map_cols": [(column + 30) % 32 for column in range(30)],
                "visible_map_rows": [(row + 3) % 32 for row in range(20)],
                "bg2_hoffs": 240,
                "bg2_voffs": 24,
            }
        }
        self.assertTrue(check_visible_window(tilemap, states)["ok"])
        # A declared window that does not follow the scroll is a disagreement.
        states["movegrid-frame-v1"]["visible_map_cols"] = list(range(30))
        result = check_visible_window(tilemap, states)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("scroll formula" in problem for problem in result["problems"]),
            result["problems"],
        )

    def test_a_growing_upload_is_rejected(self) -> None:
        plan = {
            "overlay_layer": {
                "tiles": {"logical_tiles_now": 77, "bytes_now": 4928},
                "map": {"bytes": 2048},
            }
        }
        self.assertTrue(check_upload(plan)["ok"])
        plan["overlay_layer"]["tiles"]["bytes_now"] = 1024
        result = check_upload(plan)
        self.assertFalse(result["ok"])

    def test_the_reverse_family_is_not_the_s49_overlay(self) -> None:
        family = {
            "generated": {
                "tiles": {"tile_count": 11},
                "palette": {"palette_bank": 13},
                "tilemap": {"dimensions": [30, 20]},
            },
            "runtime_binding": {"bg0cnt": "0x0002", "checkpoint": "x.ss9"},
            "controller": {"gba_address": "0x0808DCE0"},
        }
        receipt = {
            "outputs": {
                "bg2-tiles-4bpp.bin": {"bytes": 1024},
                "bg2-palette.bin": {"bytes": 32},
            }
        }
        result = check_source_identity(family, receipt)
        self.assertTrue(result["ok"])
        self.assertEqual(result["facts"]["reverse_family"]["layer"], "BG0")
        self.assertEqual(result["facts"]["s49_overlay_source"]["layer"], "BG2")
        self.assertEqual(result["facts"]["reverse_family"]["palette_bank"], 13)
        self.assertEqual(result["facts"]["s49_overlay_source"]["palette_bank"], 12)


if __name__ == "__main__":
    unittest.main()
