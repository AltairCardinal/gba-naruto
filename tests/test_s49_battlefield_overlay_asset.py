#!/usr/bin/env python3
"""The original's baked battlefield overlay tilemap, as a pinned asset.

Round 22 established that the original's move-range screen is not "one extra
grid layer" but a **whole battlefield layout map** that the game writes into
BG2's tilemap when the battle starts; the move-range screen merely enables
BG2 (``DISPCNT`` bit 10).  The layout therefore has to be carried over as a
**static asset**, and this gate pins it.

The asset lives in ``artifacts/s49-original-battlefield-overlay-v1/``:

* ``bg2-tilemap-field.bin`` -- the layout as it stands in the plain field
  frame (BG2 still disabled);
* ``bg2-tilemap-movegrid.bin`` -- the same tilemap in the frame where BG2 is
  enabled;
* ``manifest.json`` -- the hashes and the list of entries that differ.

The gate re-derives the binary from the decoded tilemap JSON in
``artifacts/s49-original-movegrid-tilemap-v1/`` so the asset can never drift
away from its evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/s49-original-battlefield-overlay-v1"
SOURCE = ROOT / "artifacts/s49-original-movegrid-tilemap-v1"


def _decoded(instance: str) -> list[dict]:
    path = SOURCE / f"{instance}.bg2-tilemap.json"
    if not path.is_file():
        raise unittest.SkipTest(f"missing decoded tilemap: {path}")
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def _binary(cells: list[dict]) -> bytes:
    return b"".join(
        int(cell["raw_hex"], 16).to_bytes(2, "little") for cell in cells
    )


class BakedOverlayAssetTest(unittest.TestCase):
    """The shipped asset must be the decoded tilemap, byte for byte."""

    def test_the_field_asset_is_the_decoded_field_tilemap(self) -> None:
        expected = _binary(_decoded("field-frame-v1"))
        actual = (ARTIFACTS / "bg2-tilemap-field.bin").read_bytes()
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 32 * 32 * 2)

    def test_the_movegrid_asset_is_the_decoded_movegrid_tilemap(self) -> None:
        expected = _binary(_decoded("movegrid-frame-v1"))
        actual = (ARTIFACTS / "bg2-tilemap-movegrid.bin").read_bytes()
        self.assertEqual(actual, expected)

    def test_the_manifest_records_the_hashes_and_the_changed_entries(self) -> None:
        manifest = json.loads(
            (ARTIFACTS / "manifest.json").read_text(encoding="utf-8")
        )
        field = (ARTIFACTS / "bg2-tilemap-field.bin").read_bytes()
        movegrid = (ARTIFACTS / "bg2-tilemap-movegrid.bin").read_bytes()
        self.assertEqual(
            manifest["field_tilemap_sha256"],
            hashlib.sha256(field).hexdigest(),
        )
        self.assertEqual(
            manifest["movegrid_tilemap_sha256"],
            hashlib.sha256(movegrid).hexdigest(),
        )
        differing = [
            index // 2
            for index, (left, right) in enumerate(zip(field, movegrid))
            if left != right
        ]
        self.assertEqual(len(differing), 212)
        self.assertEqual(manifest["changed_entries"], differing)

    def test_the_layout_has_sixteen_cell_signatures(self) -> None:
        """The layout is not a flat fill: it mixes families per region."""
        cells = _decoded("field-frame-v1")
        grid = [
            [cells[row * 32 + column]["tile"] for column in range(32)]
            for row in range(32)
        ]
        signatures = set()
        for row in range(16):
            for column in range(16):
                signatures.add(
                    (
                        grid[2 * row][2 * column],
                        grid[2 * row][2 * column + 1],
                        grid[2 * row + 1][2 * column],
                        grid[2 * row + 1][2 * column + 1],
                    )
                )
        self.assertEqual(len(signatures), 16)


if __name__ == "__main__":
    unittest.main()
