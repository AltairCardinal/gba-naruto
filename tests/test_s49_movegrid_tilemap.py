#!/usr/bin/env python3
"""The move-range overlay's BG2 tilemap must stay decoded from the receipts.

`notes/s49-dispcnt-bit10-layer-20261020.md` established that the original's
move-range overlay is an independent background layer: `DISPCNT` bit 10 is
`BG2 enable`, `BG2`'s `BGCNT` is `0x0202` (screen base block 2 -> tilemap at
VRAM `0x06001000`, char base block 0), and the overlay tile set is the 32 tiles
256..287 resident at VRAM `0x06002000` with palette bank 12.

`tools/butano/export_s49_movegrid_tilemap.py` turns the captured VRAM/PRAM/IO
receipts into that content.  These gates keep the decode honest:

* the measured changed-cell counts (against the field-frame reference) are
  pinned per receipt -- 212 for the move-range frame, 164 for the 16x16-grid
  frame, 212 for the GPU-state dump of the same state, 0 for the reference;
* every decoded tile index stays inside the overlay tile set, the lit cells
  use palette bank 12, and no cell uses H/V flip;
* the screen window is *derived* from the BG2 scroll registers rather than
  assumed;
* the export is deterministic (two runs, byte-identical outputs);
* the tile graphics and the palette decoded from the receipt are byte-identical
  to the ones the ROM-side export produces;
* a corrupted receipt fails closed instead of decoding garbage.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/butano"))

import export_s49_movegrid_tilemap as exporter  # noqa: E402

ARTIFACTS = ROOT / "artifacts"
MOVEGRID = ARTIFACTS / "s49-original-movegrid-frame-v1"
GRID16 = ARTIFACTS / "s49-original-grid16-frame-v1"
MOVEGRID_STATE = ARTIFACTS / "s49-original-movegrid-v1"
FIELD = ARTIFACTS / "s49-original-field-frame-v1"
BANNER = ARTIFACTS / "s49-original-banner-frame-v1"

# The ROM-side export of the very same tile set / palette, produced by
# `tools/butano/export_s49_movegrid_overlay.py` from ROM 0x080B9E94 and
# ROM 0x080B9F5C.  It is written by another agent; when it is absent the
# byte-for-byte comparison is skipped, but `test_rom_side_export_present`
# still fails loudly so the gap cannot pass unnoticed.
ROM_SIDE_DIR = ARTIFACTS / "s49-original-movegrid-overlay-v1"
ROM_SIDE_TILES = ROM_SIDE_DIR / "movegrid-tiles-4bpp.bin"
ROM_SIDE_PALETTE = ROM_SIDE_DIR / "movegrid-palette.bin"

# Measured against the field-frame reference receipt (`field-frame-v1`).
# The 212 figure is the number the earlier layer note reported; it is
# reproduced exactly, see notes/s49-movegrid-overlay-tilemap-20261020.md.
EXPECTED_CHANGED = {
    "movegrid-frame-v1": 212,
    "grid16-frame-v1": 164,
    "movegrid-v1": 212,
    "field-frame-v1": 0,
    "banner-frame-v1": 691,
}

# Measured counts of cells that reference a non-blank overlay tile.
EXPECTED_LIT = {
    "movegrid-frame-v1": 640,
    "grid16-frame-v1": 497,
    "movegrid-v1": 640,
    "field-frame-v1": 598,
    "banner-frame-v1": 1,
}

OVERLAY_TILE_SET = set(range(256, 288))
PALETTE_BANK = 12


class ReceiptDecodeTest(unittest.TestCase):
    """Decoding a receipt must produce the pinned content."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = exporter.read_receipt(FIELD)
        cls.receipts = {
            "movegrid-frame-v1": exporter.read_receipt(MOVEGRID),
            "grid16-frame-v1": exporter.read_receipt(GRID16),
            "movegrid-v1": exporter.read_receipt(MOVEGRID_STATE),
            "field-frame-v1": exporter.read_receipt(FIELD),
            "banner-frame-v1": exporter.read_receipt(BANNER),
        }

    def analysis(self, name: str) -> dict:
        return exporter.analyse_receipt(self.receipts[name], self.reference)

    def test_changed_cell_count_against_field_reference(self) -> None:
        for name, expected in sorted(EXPECTED_CHANGED.items()):
            with self.subTest(receipt=name):
                analysis = self.analysis(name)
                self.assertEqual(
                    len(analysis["changed_cells"]),
                    expected,
                    f"{name}: changed-cell count against field-frame-v1",
                )

    def test_movegrid_changed_cell_count_is_212(self) -> None:
        # 212 is the number the layer note reported; this run reproduces it
        # exactly, so no delta has to be explained away.
        analysis = self.analysis("movegrid-frame-v1")
        self.assertEqual(len(analysis["changed_cells"]), 212)

    def test_lit_cell_counts(self) -> None:
        for name, expected in sorted(EXPECTED_LIT.items()):
            with self.subTest(receipt=name):
                analysis = self.analysis(name)
                self.assertEqual(len(analysis["lit_cells"]), expected)

    def test_all_tile_indices_are_inside_the_overlay_tile_set(self) -> None:
        for name in sorted(EXPECTED_CHANGED):
            with self.subTest(receipt=name):
                analysis = self.analysis(name)
                tiles = {cell["tile"] for cell in analysis["cells"]}
                self.assertTrue(
                    tiles <= OVERLAY_TILE_SET,
                    f"{name}: tiles outside 256..287: "
                    f"{sorted(tiles - OVERLAY_TILE_SET)}",
                )

    def test_changed_cells_use_only_the_expected_new_tiles(self) -> None:
        expected = {
            "movegrid-frame-v1": set(range(256, 266)),
            "movegrid-v1": set(range(256, 266)),
        }
        for name, allowed in sorted(expected.items()):
            with self.subTest(receipt=name):
                analysis = self.analysis(name)
                used = {
                    entry["new"]["tile"] for entry in analysis["changed_cells"]
                }
                self.assertTrue(
                    used <= allowed,
                    f"{name}: unexpected new tiles {sorted(used - allowed)}",
                )

    def test_lit_cells_use_palette_bank_12(self) -> None:
        for name in sorted(EXPECTED_CHANGED):
            with self.subTest(receipt=name):
                analysis = self.analysis(name)
                banks = {cell["palette_bank"] for cell in analysis["lit_cells"]}
                self.assertEqual(banks, {PALETTE_BANK})

    def test_changed_cells_use_palette_bank_12_and_no_flip(self) -> None:
        for name in sorted(EXPECTED_CHANGED):
            with self.subTest(receipt=name):
                analysis = self.analysis(name)
                for entry in analysis["changed_cells"]:
                    self.assertEqual(entry["new"]["palette_bank"], PALETTE_BANK)
                    self.assertFalse(entry["new"]["hflip"])
                    self.assertFalse(entry["new"]["vflip"])

    def test_every_cell_is_decoded(self) -> None:
        analysis = self.analysis("movegrid-frame-v1")
        self.assertEqual(len(analysis["cells"]), 1024)
        self.assertEqual(
            [cell["index"] for cell in analysis["cells"]], list(range(1024))
        )
        self.assertEqual(
            [(cell["map_x"], cell["map_y"]) for cell in analysis["cells"]],
            [(index % 32, index // 32) for index in range(1024)],
        )

    def test_screen_window_is_derived_from_the_bg2_scroll_registers(self) -> None:
        analysis = self.analysis("movegrid-frame-v1")
        window = analysis["window"]
        # BG2HOFS = 240, BG2VOFS = 24 -> the 240x160 window shows map tiles
        # 30, 31, 0..27 in x and 3..22 in y (the 256x256 background wraps).
        self.assertEqual(window["bg2_hoffs"], 240)
        self.assertEqual(window["bg2_voffs"], 24)
        self.assertEqual(window["visible_map_row_count"], 20)
        self.assertEqual(window["visible_map_col_count"], 30)
        self.assertEqual(window["visible_map_rows"], list(range(3, 23)))
        self.assertEqual(
            window["visible_map_cols"],
            [30, 31] + list(range(0, 28)),
        )

    def test_screen_position_wraps_like_a_gba_background(self) -> None:
        analysis = self.analysis("movegrid-frame-v1")
        by_index = {cell["index"]: cell for cell in analysis["cells"]}
        # map tile column 30 is the left edge of the screen at hofs = 240.
        self.assertEqual(by_index[3 * 32 + 30]["screen_px_x"], 0)
        self.assertEqual(by_index[3 * 32 + 30]["screen_px_y"], 0)
        self.assertTrue(by_index[3 * 32 + 30]["visible"])
        # map tile column 0 wraps to screen x = 16.
        self.assertEqual(by_index[3 * 32 + 0]["screen_px_x"], 16)
        # map tile row 23 is below the 160 px window.
        self.assertFalse(by_index[23 * 32 + 0]["visible"])

    def test_cell_field_extraction_uses_the_gba_bit_layout(self) -> None:
        # tile = bits 0-9, palette bank = bits 12-15, hflip = bit 11,
        # vflip = bit 10.  The captured data happens to have no flipped cell,
        # so the extraction has to be pinned on synthetic values too.
        cases = {
            0x0000: (0, 0, False, False),
            0x03FF: (0x3FF, 0, False, False),
            0xF800: (0, 0x0F, True, False),
            0xB4A5: (0x0A5, 0x0B, False, True),
            0x5800: (0, 5, True, False),
            0x3400: (0, 3, False, True),
        }
        for raw, (tile, bank, hflip, vflip) in sorted(cases.items()):
            with self.subTest(raw=hex(raw)):
                decoded = exporter.decode_cell(raw)
                self.assertEqual(decoded["tile"], tile)
                self.assertEqual(decoded["palette_bank"], bank)
                self.assertEqual(decoded["hflip"], hflip)
                self.assertEqual(decoded["vflip"], vflip)

    def test_decoded_fields_re_encode_to_the_raw_cell(self) -> None:
        # Round-trip: rebuilding the 16-bit entry from the decoded fields must
        # reproduce the receipt bytes exactly, for every cell of every receipt.
        for name in sorted(EXPECTED_CHANGED):
            receipt = self.receipts[name]
            raw_cells = exporter.read_tilemap(receipt["vram"])
            for index, raw in enumerate(raw_cells):
                decoded = exporter.decode_cell(raw)
                rebuilt = (
                    decoded["tile"]
                    | (decoded["palette_bank"] << 12)
                    | (int(decoded["hflip"]) << 11)
                    | (int(decoded["vflip"]) << 10)
                )
                self.assertEqual(rebuilt, raw, f"{name} cell {index}")

    def test_blank_tiles_paint_nothing(self) -> None:
        receipt = self.receipts["movegrid-frame-v1"]
        for tile in (256, 257):
            pixels = exporter.tile_pixels(receipt["vram"], tile)
            self.assertTrue(
                all(value == 0 for row in pixels for value in row),
                f"tile {tile} is not blank",
            )

    def test_bank_12_palette_is_read_out_of_pram(self) -> None:
        receipt = self.receipts["movegrid-frame-v1"]
        entries = exporter.palette_entries(receipt["pram"])
        self.assertEqual(len(entries), 16)
        expected = {
            0: "0x0000",
            1: "0x45A8",
            2: "0x7F23",
            3: "0x55A1",
            4: "0x00FF",
            5: "0x00B4",
            6: "0x02FF",
            7: "0x01B2",
            8: "0x03F5",
            9: "0x020A",
            10: "0x2529",
            11: "0x1084",
            12: "0x0000",
            13: "0x0000",
            14: "0x0000",
            15: "0x0000",
        }
        for index, word in expected.items():
            self.assertEqual(entries[index]["bgr555"], word)
        self.assertEqual(entries[2]["rgb8"], [24, 206, 255])

    def test_overlay_tile_set_is_identical_in_every_receipt(self) -> None:
        blobs = set()
        for name, receipt in self.receipts.items():
            blobs.add(
                bytes(
                    receipt["vram"][
                        0x2000:0x2400
                    ]
                )
            )
        self.assertEqual(len(blobs), 1, f"tile set differs between receipts")


class RomSideCrossCheckTest(unittest.TestCase):
    """The receipt-side decode must agree with the ROM-side export."""

    @unittest.skipUnless(
        ROM_SIDE_DIR.is_dir(),
        f"ROM-side export {ROM_SIDE_DIR} is not present yet",
    )
    def test_rom_side_tile_graphics_match(self) -> None:
        receipt = exporter.read_receipt(MOVEGRID)
        decoded = bytes(receipt["vram"][0x2000:0x2400])
        self.assertEqual(decoded, ROM_SIDE_TILES.read_bytes())

    @unittest.skipUnless(
        ROM_SIDE_DIR.is_dir(),
        f"ROM-side export {ROM_SIDE_DIR} is not present yet",
    )
    def test_rom_side_palette_matches(self) -> None:
        receipt = exporter.read_receipt(MOVEGRID)
        decoded = bytes(receipt["pram"][0x180:0x1A0])
        self.assertEqual(decoded, ROM_SIDE_PALETTE.read_bytes())

    def test_rom_side_export_present(self) -> None:
        # Placeholder that must fail loudly (not silently pass) while the
        # ROM-side export is missing, so the cross-check above cannot be
        # mistaken for a completed comparison.
        self.assertTrue(
            ROM_SIDE_DIR.is_dir(),
            f"ROM-side export {ROM_SIDE_DIR} is missing: the byte-for-byte "
            f"cross-check against the ROM cannot be performed",
        )


class ExportRunTest(unittest.TestCase):
    """The exporter's on-disk output must be deterministic and complete."""

    def run_export(self, out_dir: Path) -> dict:
        return exporter.export(out_dir)

    def test_two_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.run_export(Path(first))
            self.run_export(Path(second))
            names = sorted(path.name for path in Path(first).iterdir())
            self.assertEqual(names, sorted(path.name for path in Path(second).iterdir()))
            self.assertIn("manifest.json", names)
            for name in names:
                with self.subTest(output=name):
                    self.assertEqual(
                        (Path(first) / name).read_bytes(),
                        (Path(second) / name).read_bytes(),
                    )

    def test_export_writes_json_and_png_per_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            manifest = self.run_export(out_dir)
            for name in EXPECTED_CHANGED:
                with self.subTest(receipt=name):
                    self.assertTrue((out_dir / f"{name}.bg2-tilemap.json").is_file())
                    self.assertTrue((out_dir / f"{name}.bg2-cells.png").is_file())
                    self.assertTrue((out_dir / f"{name}.bg2-layer.png").is_file())
            for name in (
                "bg2-tiles-4bpp.bin",
                "bg2-tiles-index.png",
                "bg2-tiles-render.png",
                "bg2-palette.bin",
                "bg2-palette.json",
                "bg2-palette.png",
            ):
                with self.subTest(output=name):
                    self.assertTrue((out_dir / name).is_file())
            self.assertIn("movegrid-frame-v1", manifest["summary"])
            self.assertEqual(
                manifest["summary"]["movegrid-frame-v1"]["counts"][
                    "changed_cells_vs_reference"
                ],
                212,
            )

    def test_manifest_hashes_match_the_files_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            manifest = self.run_export(out_dir)
            for name, entry in manifest["outputs"].items():
                with self.subTest(output=name):
                    path = out_dir / name
                    self.assertEqual(path.stat().st_size, entry["bytes"])
                    self.assertEqual(
                        exporter.sha256(path.read_bytes()), entry["sha256"]
                    )


class FailClosedTest(unittest.TestCase):
    """A damaged receipt must stop the export, not decode garbage."""

    def corrupt_copy(self, tmp: Path, truncate_vram: bool = True) -> Path:
        target = tmp / "receipt"
        target.mkdir()
        shutil.copy(MOVEGRID / "io-00.bin", target / "io-00.bin")
        shutil.copy(MOVEGRID / "pram-00.bin", target / "pram-00.bin")
        vram = (MOVEGRID / "vram-00.bin").read_bytes()
        if truncate_vram:
            vram = vram[:-1]
        (target / "vram-00.bin").write_bytes(vram)
        return target

    def test_truncated_vram_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.corrupt_copy(Path(tmp))
            with self.assertRaises(exporter.ReceiptError) as caught:
                exporter.read_receipt(broken)
            self.assertIn("expected exactly", str(caught.exception))

    def test_truncated_pram_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.corrupt_copy(Path(tmp), truncate_vram=False)
            (broken / "pram-00.bin").write_bytes(
                (MOVEGRID / "pram-00.bin").read_bytes()[:16]
            )
            with self.assertRaises(exporter.ReceiptError):
                exporter.read_receipt(broken)

    def test_missing_receipt_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(exporter.ReceiptError):
                exporter.read_receipt(Path(tmp) / "does-not-exist")

    def test_missing_vram_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.corrupt_copy(Path(tmp), truncate_vram=False)
            (broken / "vram-00.bin").unlink()
            with self.assertRaises(exporter.ReceiptError):
                exporter.read_receipt(broken)

    def test_wrong_bgcnt_screen_base_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.corrupt_copy(Path(tmp), truncate_vram=False)
            io = bytearray((MOVEGRID / "io-00.bin").read_bytes())
            # BG2CNT lives at IO 0x0C; the screen base block is its high byte.
            io[0x0D] = 0x01  # screen base block 2 -> 1
            (broken / "io-00.bin").write_bytes(bytes(io))
            with self.assertRaises(exporter.ReceiptError) as caught:
                exporter.read_receipt(broken)
            self.assertIn("screen base block", str(caught.exception))

    def test_export_aborts_on_a_broken_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = self.corrupt_copy(Path(tmp))
            original = exporter.RECEIPTS
            exporter.RECEIPTS = (
                ("movegrid-frame-v1", str(broken)),
                *original[1:],
            )
            try:
                with self.assertRaises(exporter.ReceiptError):
                    exporter.export(Path(tmp) / "out")
            finally:
                exporter.RECEIPTS = original


class CommittedArtifactTest(unittest.TestCase):
    """The committed artifact must agree with a fresh run of the exporter."""

    ARTIFACT = ARTIFACTS / "s49-original-movegrid-tilemap-v1"

    def test_committed_manifest_matches_a_fresh_run(self) -> None:
        if not (self.ARTIFACT / "manifest.json").is_file():
            self.skipTest("artifact not generated yet")
        with tempfile.TemporaryDirectory() as tmp:
            fresh = exporter.export(Path(tmp))
            committed = json.loads(
                (self.ARTIFACT / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                fresh["outputs"], committed["outputs"],
                "committed artifact is stale; re-run the exporter",
            )


if __name__ == "__main__":
    unittest.main()
