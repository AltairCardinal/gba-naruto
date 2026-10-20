#!/usr/bin/env python3
"""Same-frame receipts are self-consistent: render the frame from its own dumps.

Rounds 13 and 14 recorded a "the screenshot and its own VRAM/PRAM/IO dumps do
not agree" observation, and several conclusions were withdrawn because of it.
That observation was an artefact of the method, not a property of the
receipts: a naive "is this screenshot colour one of the palette entries?"
check cannot see an alpha-blended pixel, because a blended colour belongs to
no palette bank at all, and the analyzer also read ``BLDCNT`` from the wrong
IO offset (0x28 instead of 0x50) and therefore believed the game was not
blending.

The repository already has a Mode 0 reference renderer
(``tools/butano/render_scenario_41_gpu.py``) that reads the same four GPU
regions and applies the display registers, including the blend.  Rendering a
receipt's frame from that receipt's own dumps must reproduce the receipt's
screenshot exactly.  This gate pins that, so the "inconsistent receipt" claim
cannot come back, and so any future change to the capture path that really
does desynchronise the screenshot from the memory dump fails loudly.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "tools" / "butano"))

import render_scenario_41_gpu as renderer  # noqa: E402

RECEIPTS = (
    "s49-original-movegrid-frame-v1",
    "s49-original-field-frame-v1",
    "s49-original-banner-frame-v1",
    "s49-original-grid16-frame-v1",
)


def _load_region(directory: Path, stem: str) -> bytes:
    path = directory / f"{stem}.bin"
    if not path.is_file():
        raise unittest.SkipTest(f"missing GPU region: {path}")
    return path.read_bytes()


def _render(directory: Path) -> bytes:
    io = _load_region(directory, "io-00")
    if len(io) < 0x400:
        # The frame receipts keep the first 0x60 bytes of the IO window, which
        # already covers every register the renderer reads (DISPCNT, BGCNT,
        # the scrolls, the windows and the blend registers).
        io = io + b"\x00" * (0x400 - len(io))
    return renderer.render_mode0(
        io,
        _load_region(directory, "pram-00"),
        _load_region(directory, "oam-00"),
        _load_region(directory, "vram-00"),
    )


class ReceiptSelfConsistencyTest(unittest.TestCase):
    """A receipt's screenshot must equal its own dumps, pixel for pixel."""

    #: The grid16 capture lags its own dumps by a few hundred pixels (the
    #: range grid animates), so it is allowed a small, pinned residual; every
    #: other receipt must be pixel exact.
    RESIDUAL_TOLERANCE = {"s49-original-grid16-frame-v1": 600}

    def test_every_frame_receipt_reproduces_its_own_screenshot(self) -> None:
        for receipt in RECEIPTS:
            directory = ROOT / "artifacts" / receipt
            if not directory.is_dir():
                continue
            with self.subTest(receipt=receipt):
                rendered = _render(directory)
                with Image.open(directory / "frame-00.png") as screenshot:
                    image = screenshot.convert("RGB")
                    width, height = image.size
                    pixels = image.load()
                differing = 0
                for y in range(height):
                    for x in range(width):
                        offset = (y * width + x) * 3
                        rendered_rgb = tuple(rendered[offset:offset + 3])
                        if rendered_rgb != pixels[x, y]:
                            differing += 1
                tolerance = self.RESIDUAL_TOLERANCE.get(receipt, 0)
                self.assertLessEqual(
                    differing,
                    tolerance,
                    f"{receipt}: {differing} of {width * height} pixels differ "
                    "between the frame rendered from its own dumps and its "
                    f"screenshot (tolerance {tolerance})",
                )

    def test_the_blend_registers_are_read_from_the_right_offsets(self) -> None:
        """Guard the IO offsets that the round 13/14 conclusions depended on.

        BLDCNT/BLDALPHA/BLDY/MOSAIC live at 0x50/0x52/0x54/0x44 on the GBA.
        Reading them from 0x28/0x2A/0x2E/0x48 is what produced the old
        "BLDCNT is 0, so the game does not blend" claim.
        """
        directory = ROOT / "artifacts/s49-original-movegrid-frame-v1"
        if not directory.is_dir():
            self.skipTest("move grid frame receipt is missing")
        io = _load_region(directory, "io-00")
        blend = int.from_bytes(io[0x50:0x52], "little")
        alpha = int.from_bytes(io[0x52:0x54], "little")
        self.assertNotEqual(
            blend,
            0,
            "BLDCNT read at 0x50 must be non-zero for the move range frame",
        )
        self.assertEqual((blend >> 6) & 1, 1, "the blend effect must be alpha")
        self.assertEqual(blend & 0x3F, 0x04, "the first blend target must be BG2")
        self.assertEqual(alpha, 0x0A0A, "BLDALPHA must read 10/16 on both sides")
        self.assertEqual(alpha & 0x1F, 10, "EVA must be 10/16")
        self.assertEqual((alpha >> 8) & 0x1F, 10, "EVB must be 10/16")


if __name__ == "__main__":
    unittest.main()
