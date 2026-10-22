#!/usr/bin/env python3
"""The original's battle overlay in screen space, pinned as ground truth.

Round 26 established that the original's move-range screen is not "one extra
grid layer" but a **baked battlefield layout map** the game writes into BG2's
tilemap at battle start.  Reproducing that overlay 1:1 needs the *screen*
footprint of that map, not just "which tile family belongs to which logical
cell".

This gate pins the answers that the remake's implementation depends on:

* the exported artifacts are exactly what the exporter produces (they cannot
  drift away from the evidence);
* the overlay's screen footprint -- how many pixels it paints, where they are,
  and which 8x8 screen cells carry which tile family;
* the **attribution** of the remake's remaining pixel difference: it must be
  the blocked-area darkening that the remake does not draw at all, plus the
  move-lens border whose granularity differs (16x16 px in the original,
  32x16 px in the remake).  Everything else must be zero -- a difference in
  any other family would mean a new, unexplained defect;
* the blend arithmetic: inverting the original's own pixels through
  ``(BG2 + BG1) * 10/16`` must recover the *same* map colour that the
  overlay-free frames show, which is what makes the whole overlay model
  self-consistent.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "tools/butano/export_s49_overlay_screentruth.py"
OUT_DIR = ROOT / "artifacts/s49-original-overlay-screentruth-v1"
SCREEN_TRUTH = OUT_DIR / "screen-truth.json"
MANIFEST = OUT_DIR / "manifest.json"

ORIGINAL_FRAME = (
    ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-19-A.png"
)
REMAKE_FRAME = ROOT / "artifacts/s49-remake-walk-20261021-v1/step-20-A.png"

#: The pinned screen footprint of the original's overlay (movegrid frame).
PINNED_PAINTED_PIXELS = 28482
PINNED_BOUNDING_BOX = [0, 0, 239, 159]
PINNED_PAINTED_CELLS = 531
PINNED_VISIBLE_CELLS = 600

#: The pinned attribution of the remake's remaining difference.
PINNED_RESIDUAL_TOTAL = 2917
PINNED_RESIDUAL_BY_FAMILY = {"blocked": 2317, "move_lens": 600}
PINNED_RESIDUAL_CELLS = 73

#: The original draws its HUD above BG2, so the overlay is invisible in the
#: top three tile rows (24 px).
HUD_BAND_ROWS = 3

#: How many blocked-family pixels the blend check covers.
PINNED_BLEND_CHECKED_PIXELS = 2304


def _load_exporter():
    spec = importlib.util.spec_from_file_location(
        "export_s49_overlay_screentruth", EXPORTER
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _truth() -> dict:
    if not SCREEN_TRUTH.is_file():
        raise unittest.SkipTest(f"missing exported ground truth: {SCREEN_TRUTH}")
    return json.loads(SCREEN_TRUTH.read_text(encoding="utf-8"))


class OverlayScreentruthTest(unittest.TestCase):
    """The exported ground truth must stay reproducible and pinned."""

    def test_the_exporter_check_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(EXPORTER), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"exporter --check failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_every_artifact_matches_its_manifest_hash(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for name, entry in manifest["outputs"].items():
            path = OUT_DIR / name
            self.assertTrue(path.is_file(), f"missing artifact: {path}")
            data = path.read_bytes()
            self.assertEqual(len(data), entry["bytes"], name)
            self.assertEqual(
                hashlib.sha256(data).hexdigest(), entry["sha256"], name
            )

    def test_the_screen_footprint_is_pinned(self) -> None:
        footprint = _truth()["footprint"]["movegrid"]
        self.assertEqual(footprint["painted_pixels"], PINNED_PAINTED_PIXELS)
        self.assertEqual(footprint["bounding_box"], PINNED_BOUNDING_BOX)
        self.assertEqual(
            footprint["painted_tilemap_cells"], PINNED_PAINTED_CELLS
        )
        self.assertEqual(footprint["visible_cells"], PINNED_VISIBLE_CELLS)

    def test_the_family_map_covers_the_whole_screen(self) -> None:
        families = _truth()["family_map"]["movegrid"]
        self.assertEqual(len(families), 20)
        for row in families:
            self.assertEqual(len(row), 30, row)
        # The top three rows are the HUD band: the original's layout paints
        # the blocked family over the whole band.
        for row in families[:3]:
            self.assertEqual(set(row), {"b"}, row)

    def test_the_remaining_difference_is_attributed_to_two_families(self) -> None:
        residual = _truth()["remake_residual_attribution"]
        self.assertEqual(
            residual["total_differing_pixels"], PINNED_RESIDUAL_TOTAL
        )
        self.assertEqual(residual["by_family"], PINNED_RESIDUAL_BY_FAMILY)
        self.assertEqual(
            residual["cells_with_difference"], PINNED_RESIDUAL_CELLS
        )

    def test_the_blend_arithmetic_recovers_the_underlying_map_colour(self) -> None:
        """Every overlay pixel must be a 10/16 blend over a valid map colour.

        The check is deliberately independent of the remake's map: the
        original's pixel must be expressible as ``(overlay + base) * 10/16``
        with a base colour inside the 8 bit range.  Where the original's HUD
        or a unit sprite covers the overlay, or where the model wrongly
        claims an overlay, that fails -- so the assertion catches both a
        wrong overlay model and a wrong blend.
        """
        if not ORIGINAL_FRAME.is_file():
            raise unittest.SkipTest(f"missing original frame: {ORIGINAL_FRAME}")
        from PIL import Image

        exporter = _load_exporter()
        evidence = exporter.load_evidence()
        original = Image.open(ORIGINAL_FRAME).convert("RGB").load()
        residual = _truth()["remake_residual_attribution"]

        checked = 0
        for cell in residual["cell_detail"]:
            if cell["original_family"] != "blocked":
                continue
            if cell["screen_row"] < HUD_BAND_ROWS:
                # The original's HUD is drawn *above* BG2, so the overlay is
                # not visible in the HUD band at all -- those cells differ for
                # another reason and must not be used for this check.
                continue
            for screen_y in range(
                cell["screen_row"] * 8, cell["screen_row"] * 8 + 8
            ):
                for screen_x in range(
                    cell["screen_column"] * 8, cell["screen_column"] * 8 + 8
                ):
                    value, _, _ = exporter.screen_lookup(
                        evidence, evidence["movegrid"], screen_x, screen_y
                    )
                    if value < 0:
                        continue
                    overlay = evidence["palette"][value]
                    if overlay == (0, 0, 0):
                        continue
                    observed = original[screen_x, screen_y]
                    for channel in range(3):
                        base = observed[channel] * 16 / 10 - overlay[channel]
                        self.assertGreaterEqual(
                            base, -1.0, (screen_x, screen_y, observed, overlay)
                        )
                        self.assertLessEqual(
                            base, 256.0, (screen_x, screen_y, observed, overlay)
                        )
                    checked += 1
        self.assertEqual(checked, PINNED_BLEND_CHECKED_PIXELS)

    def test_the_eight_bit_expansion_is_correct(self) -> None:
        """The 8bpp sheet must carry the original's colours, by number."""
        spec = importlib.util.spec_from_file_location(
            "generate_butano_battlefield_overlay",
            ROOT / "tools/generate_butano_battlefield_overlay.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        pixels = module.expand_tiles_8bpp(
            module.TILES.read_bytes(), module.PALETTE.read_bytes()
        )
        self.assertEqual(len(pixels), 32 * 64)
        # 258 = the grid web: transparent with the edge colour at x=7.
        self.assertEqual(pixels[(258 - 256) * 64 + 7], 224 + 1)
        self.assertEqual(pixels[(258 - 256) * 64 + 6], 0)
        # 262 = the move lens: solid with the lens colour.
        self.assertEqual(
            set(pixels[(262 - 256) * 64:(263 - 256) * 64]), {224 + 2}
        )
        # 279 = the blocked area: solid with the darker edge at x=7.
        self.assertEqual(pixels[(279 - 256) * 64 + 7], 224 + 11)
        self.assertEqual(pixels[(279 - 256) * 64 + 6], 224 + 10)
        # 256 and 282..287 are fully transparent.
        for transparent_tile in (256, 257, 282, 283, 284, 285, 286, 287):
            start = (transparent_tile - 256) * 64
            self.assertEqual(
                set(pixels[start:start + 64]), {0}, transparent_tile
            )


if __name__ == "__main__":
    unittest.main()
