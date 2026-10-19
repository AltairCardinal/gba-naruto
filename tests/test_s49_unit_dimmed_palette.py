#!/usr/bin/env python3
"""The original's dimmed-unit palette must stay read out of palette RAM.

S49's command menu shows the acting unit in colour and the other one in
greyscale; the remake draws both in colour.  The dimming is not an asset the
remake failed to extract: `battle_unit_visual_catalog.json` gives every one of
the 62 characters x 9 slots its own `palette_pointer`, and none of those 534
palettes is greyscale.  The greys therefore come from something the game writes
into palette RAM while it runs.

`tools/butano/capture_s49_gpu_state.py` reads PRAM straight out of the original
ROM, and at the command-menu frame one of the five OBJ banks in use is greyscale
in 15 of its 16 entries.  These gates keep the palette **tied to that dump** so
it can never quietly become a hand-typed table:

* the probe receipt must be present and name its own input hashes;
* the palette the generator reads must equal the one recorded here;
* the shipped BMP must carry exactly those sixteen colours;
* every greyscale colour the recorded frame shows must be explained by the bank,
  and the bank must itself be ≥15/16 greyscale — that ratio is what rules out a
  computed desaturation, which reproduces at most 8 of the frame's greys.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]

DUMP = ROOT / "artifacts/s49-original-gpu-20261020-v2/step-18-cmdmenu"
RECEIPT = ROOT / "artifacts/s49-original-gpu-20261020-v2/dimmed-palette-receipt.json"
FRAME = ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-18-A.png"
BMP = ROOT / "butano-sequel/graphics/battle_unit_dimmed_palette.bmp"
JSON_SIDECAR = ROOT / "butano-sequel/graphics/battle_unit_dimmed_palette.json"

# Read out of PRAM at walk-original-a24/step-18-A.ss9, OBJ palette bank 3.
DIMMED: tuple[tuple[int, int, int], ...] = (
    (165, 165, 165),
    (33, 33, 33),
    (90, 90, 90),
    (99, 99, 99),
    (49, 49, 49),
    (198, 198, 198),
    (148, 148, 148),
    (90, 90, 90),
    (107, 107, 107),
    (74, 74, 74),
    (214, 214, 214),
    (156, 156, 156),
    (255, 255, 255),
    (206, 206, 206),
    (165, 165, 165),
    (0, 8, 8),
)
# OBJ palette bank 1 from the same frame: the same unit in full colour.
COLOUR: tuple[tuple[int, int, int], ...] = (
    (198, 132, 255),
    (33, 33, 33),
    (82, 90, 99),
    (41, 41, 99),
    (255, 0, 0),
    (239, 189, 165),
    (198, 132, 107),
    (132, 82, 49),
    (123, 132, 115),
    (74, 74, 74),
    (74, 107, 206),
    (49, 49, 115),
    (255, 255, 255),
    (206, 206, 206),
    (165, 165, 165),
    (0, 8, 8),
)


def _generator():
    import sys

    sys.path.insert(0, str(ROOT))
    from tools.butano import generate_unit_dimmed_palette as module

    return module


def _dump_available() -> bool:
    return all(
        (DUMP / name).is_file()
        for name in ("pram.bin", "oam.bin", "io.bin", "vram.bin", "inputs.json")
    )


class DimmedPaletteProvenance(unittest.TestCase):
    def test_probe_receipt_is_complete(self):
        if not _dump_available():
            self.skipTest("the GPU probe dump is unavailable")
        inputs = json.loads((DUMP / "inputs.json").read_text(encoding="utf-8"))
        self.assertEqual(inputs["schema"], "konoha.mgba-gpu-state-inputs.v1")
        for key in (
            "input_state_sha256",
            "rom_sha256",
            "mgba_sha256",
            "script_sha256",
            "guard_sha256",
        ):
            self.assertRegex(
                inputs[key], r"^[0-9a-f]{64}$", f"{key} is not pinned in the receipt"
            )
        self.assertEqual(
            inputs["rom_sha256"],
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            "the dump was taken from a different ROM than the one under study",
        )

    def test_the_palette_is_read_from_palette_ram_not_asserted(self):
        if not _dump_available():
            self.skipTest("the GPU probe dump is unavailable")
        dimmed, colour = _generator().dimmed_palette(DUMP)
        self.assertEqual(tuple(dimmed), DIMMED)
        self.assertEqual(tuple(colour), COLOUR)

    def test_the_colour_bank_is_the_index_twin_of_the_dimmed_one(self):
        """The two banks are index-for-index siblings, not two unrelated sets."""

        self.assertEqual(len(DIMMED), len(COLOUR))
        unchanged = [
            index
            for index, (dimmed, colour) in enumerate(zip(DIMMED, COLOUR))
            if dimmed == colour
        ]
        self.assertEqual(
            unchanged,
            [1, 9, 12, 13, 14, 15],
            "the greys that survive in both banks are the outline ramp",
        )
        self.assertGreaterEqual(
            sum(
                1
                for dimmed, colour in zip(DIMMED, COLOUR)
                if dimmed[0] == dimmed[1] == dimmed[2]
            ),
            10,
        )


class DimmedPaletteShape(unittest.TestCase):
    def test_the_bank_is_greyscale(self):
        grey = [c for c in DIMMED if c[0] == c[1] == c[2]]
        self.assertGreaterEqual(len(grey), 15, "the dimmed bank is not greyscale")

    def test_the_colour_bank_is_not(self):
        grey = [c for c in COLOUR if c[0] == c[1] == c[2]]
        self.assertLessEqual(
            len(grey), 8, "the acting unit's palette should be in colour"
        )

    def test_index_zero_is_not_the_transparent_magenta_any_more(self):
        """A real consequence worth naming: the dimmed bank has no magenta."""

        self.assertEqual(COLOUR[0], (198, 132, 255))
        self.assertNotEqual(DIMMED[0], (198, 132, 255))


class DimmedPaletteExplainsTheFrame(unittest.TestCase):
    def test_every_grey_the_frame_shows_is_in_the_bank(self):
        if not FRAME.is_file():
            self.skipTest("the original walk is unavailable")
        frame = Image.open(FRAME).convert("RGB")
        pixels = frame.load()
        greys = {
            pixels[x, y]
            for y in range(46, 104)
            for x in range(84, 116)
            if pixels[x, y][0] == pixels[x, y][1] == pixels[x, y][2]
        }
        self.assertGreaterEqual(len(greys), 10)
        self.assertEqual(
            sorted(greys - set(DIMMED)),
            [],
            "the frame shows greys the bank does not account for",
        )


class ShippedDimmedPaletteAsset(unittest.TestCase):
    def test_the_shipped_bmp_carries_the_palette(self):
        if not BMP.is_file():
            self.skipTest("the dimmed palette asset is not generated")
        with Image.open(BMP) as image:
            self.assertEqual(image.mode, "P")
            flat = image.getpalette()
        self.assertEqual(
            [tuple(flat[index * 3:index * 3 + 3]) for index in range(16)],
            list(DIMMED),
        )

    def test_the_sidecar_declares_a_sprite_palette(self):
        if not JSON_SIDECAR.is_file():
            self.skipTest("the dimmed palette asset is not generated")
        payload = json.loads(JSON_SIDECAR.read_text(encoding="utf-8"))
        self.assertEqual(payload, {"type": "sprite_palette"})

    def test_the_receipt_names_the_probe_it_came_from(self):
        if not RECEIPT.is_file():
            self.skipTest("the dimmed palette receipt is not written")
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "konoha.s49-unit-dimmed-palette.v1")
        self.assertEqual(
            [tuple(entry) for entry in payload["dimmed"]],
            list(DIMMED),
        )
        self.assertEqual(payload["source"]["obj_palette_bank"], 3)
        self.assertRegex(payload["source"]["pram_sha256"], r"^[0-9a-f]{64}$")


class DimmedBankPaintsTheInactiveUnit(unittest.TestCase):
    """Bank 3 must be what draws the greyscale unit, and nothing else.

    A palette found in PRAM is only meaningful once it is tied to the pixels it
    produces.  Zeroing one OBJ bank and re-rendering the frame is the cheapest
    way to get that answer without guessing from the OAM, which also sidesteps
    the coordinate arithmetic: the recorded screen rectangle is whatever comes
    out of the render, not whatever the OAM fields appear to say.
    """

    STEP = "step-18"

    def _render(self, pram: bytes) -> Image.Image:
        import sys

        sys.path.insert(0, str(ROOT / "tools/butano"))
        import render_scenario_41_gpu as renderer

        dump = ROOT / "artifacts/s49-original-gpu-20261020-v2" / self.STEP
        if not (dump / "pram.bin").is_file():
            self.skipTest("the GPU probe dump is unavailable")
        return Image.frombytes(
            "RGB",
            (240, 160),
            renderer.render_mode0(
                (dump / "io.bin").read_bytes(),
                pram,
                (dump / "oam.bin").read_bytes(),
                (dump / "vram.bin").read_bytes(),
            ),
        )

    def test_zeroing_the_bank_removes_exactly_the_unit(self):
        dump = ROOT / "artifacts/s49-original-gpu-20261020-v2" / self.STEP
        if not (dump / "pram.bin").is_file():
            self.skipTest("the GPU probe dump is unavailable")
        pram = bytearray((dump / "pram.bin").read_bytes())
        base = self._render(bytes(pram))
        # OBJ palette RAM starts at 0x200; bank 3 is 32 bytes into it.
        offset = 0x200 + 3 * 32
        from tools.butano.capture_s49_gpu_state import palette_entries

        self.assertEqual(
            tuple(palette_entries(bytes(pram))[16 + 3]), DIMMED,
            "bank 3 in the dump is not the recorded dimmed palette",
        )
        for index in range(32):
            pram[offset + index] = 0
        cleared = self._render(bytes(pram))

        difference = ImageChops.difference(base, cleared).convert("L")
        histogram = difference.histogram()
        differing = difference.size[0] * difference.size[1] - histogram[0]
        self.assertGreater(differing, 400)
        box = difference.point(lambda v: 255 if v > 0 else 0).getbbox()
        self.assertEqual(box, (80, 50, 109, 102))

    def test_the_original_tiles_carry_no_index_zero(self):
        """Why this blocks a straight palette swap, stated as a gate.

        The remake's unit atlases make index 0 the transparent magenta and use it
        for about half the sprite; the dimmed bank's index 0 is light grey.  A
        naive swap would therefore paint every dimmed unit with a grey box.  The
        original does not: zeroing the bank turns the unit into a black silhouette
        of the *same outline* with the grass still showing through, which is only
        possible when the tiles never reference index 0.

        So the dimmed palette is ready but cannot be wired in until that index
        difference is settled.  This gate records the blocker instead of hiding
        it; it goes away when the remake's unit atlases match the original's
        transparent index.
        """

        atlas = Image.open(
            ROOT / "butano-sequel/graphics/battle_unit_01_idle.bmp"
        ).convert("P")
        pixels = atlas.load()
        width, height = atlas.size
        used = {
            pixels[x, y] for y in range(height) for x in range(width)
        }
        self.assertIn(
            0,
            used,
            "the remake's unit tiles no longer use index 0; revisit the "
            "dimmed-palette wiring instead of assuming it is blocked",
        )
        self.assertEqual(
            tuple(atlas.getpalette()[0:3]),
            (197, 131, 255),
            "the remake's index 0 is the transparent magenta",
        )


if __name__ == "__main__":
    unittest.main()
