#!/usr/bin/env python3
"""The move-range overlay assets must be liftable from the ROM, reproducibly.

The original S49 move-range overlay is a dedicated BG2 layer with its own tile
set and its own palette bank.  Both payloads live in the ROM as LZ77 records
(``0x080B9E94`` for the 32 tiles, ``0x080B9F5C`` for palette bank 12), and both
are already resident in the VRAM / PRAM dumps of the captured same-frame
receipts.  This gate pins that pipeline down:

* the exporter refuses to run on a ROM whose SHA-256 does not match;
* the LZ77 records decode to fixed byte lengths with fixed SHA-256 digests;
* the palette decodes to fixed 8-bit RGB values;
* re-running the exporter produces byte-identical artifacts;
* the exported payload equals the bytes the game had resident in VRAM / PRAM;
* the manifest agrees with the already signed mechanism receipt
  ``artifacts/s49-original-movegrid-mechanism-v1/mechanism.json``.

**Which receipt fields could NOT be cross-checked.**  The mechanism receipt is
a *mechanism* receipt: it describes the layer and the register state, it does
not carry the overlay's payload.  The following fields exist in neither the
receipt nor its referenced frame dumps, and are therefore established by this
suite alone (from the ROM bytes and from the VRAM / PRAM dumps):

* the decompressed tile bytes and their SHA-256;
* the decompressed palette bytes, the 16 BGR555 entries and their 8-bit RGB
  conversion;
* the VRAM window ``0x2000-0x2400`` and the PRAM window ``0x180-0x19F`` that
  carry the payload;
* the tile shapes (empty / edge / solid-with-border) and the tile-index to
  sheet-position layout.

The receipt also does **not** record the "212 changed BG2 tilemap cells"
figure: its baseline is the round-banner frame, and the numbers it does record
(``bg_tilemap_cells.bg2 == 706`` and ``bg2_region_bytes_changed == 706``) are
movegrid-versus-banner.  The 212 figure is a movegrid-versus-field number and
is recomputed here from the frame receipts the receipt points at, so it is
asserted as a derived value and never attributed to the receipt.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.butano.export_s49_movegrid_overlay import (  # noqa: E402
    DEFAULT_ROM_NAME,
    EXPECTED_ROM_SHA256,
    OUTPUT_MANIFEST,
    OUTPUT_PALETTE_BIN,
    OUTPUT_PALETTE_JSON,
    OUTPUT_TILES_BIN,
    OUTPUT_TILES_INDEX_PNG,
    OUTPUT_TILES_RENDER_PNG,
    ExportError,
    bgr555_to_rgb8,
    lz77_decompress,
)

ROM_PATH = REPO_ROOT / DEFAULT_ROM_NAME
EXPORTER = REPO_ROOT / "tools" / "butano" / "export_s49_movegrid_overlay.py"
MECHANISM_RECEIPT = (
    REPO_ROOT / "artifacts" / "s49-original-movegrid-mechanism-v1" / "mechanism.json"
)
FRAME_RECEIPTS = (
    "s49-original-field-frame-v1",
    "s49-original-movegrid-frame-v1",
    "s49-original-grid16-frame-v1",
    "s49-original-banner-frame-v1",
)

TILES_SHA256 = "0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40"
PALETTE_SHA256 = "d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84"

EXPECTED_PALETTE_RGB8 = [
    (0, 0, 0),
    (66, 107, 140),
    (24, 206, 255),
    (8, 107, 173),
    (255, 57, 0),
    (165, 41, 0),
    (255, 189, 0),
    (148, 107, 0),
    (173, 255, 0),
    (82, 132, 0),
    (74, 74, 74),
    (33, 33, 33),
    (0, 0, 0),
    (0, 0, 0),
    (0, 0, 0),
    (0, 0, 0),
]
EXPECTED_PALETTE_BGR555 = [
    0x0000,
    0x45A8,
    0x7F23,
    0x55A1,
    0x00FF,
    0x00B4,
    0x02FF,
    0x01B2,
    0x03F5,
    0x020A,
    0x2529,
    0x1084,
    0x0000,
    0x0000,
    0x0000,
    0x0000,
]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXPORTER), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )


class MovegridOverlayExportTests(unittest.TestCase):
    """Exporter behaviour: gates, decoding, determinism, cross-checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_dir = Path(cls._tmp.name) / "export"
        cls.result = run_cli(
            "--rom",
            str(ROM_PATH),
            "--out-dir",
            str(cls.out_dir),
            "--evidence-dir",
            "artifacts/s49-original-movegrid-frame-v1",
            "--evidence-dir",
            "artifacts/s49-original-grid16-frame-v1",
            "--evidence-dir",
            "artifacts/s49-original-field-frame-v1",
            "--evidence-dir",
            "artifacts/s49-original-banner-frame-v1",
            "--evidence-baseline",
            "artifacts/s49-original-field-frame-v1",
        )
        if cls.result.returncode != 0:
            raise AssertionError(
                f"exporter failed: rc={cls.result.returncode}\n"
                f"stdout={cls.result.stdout}\nstderr={cls.result.stderr}"
            )
        cls.manifest = json.loads(
            (cls.out_dir / OUTPUT_MANIFEST).read_text(encoding="utf-8")
        )
        cls.tiles = (cls.out_dir / OUTPUT_TILES_BIN).read_bytes()
        cls.palette = (cls.out_dir / OUTPUT_PALETTE_BIN).read_bytes()
        cls.mechanism = json.loads(MECHANISM_RECEIPT.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # -- gates ------------------------------------------------------------
    def test_rom_hash_gate_rejects_a_rom_with_one_flipped_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.gba"
            data = bytearray(ROM_PATH.read_bytes())
            data[0xB9E94] ^= 0x01
            broken.write_bytes(bytes(data))
            self.assertNotEqual(
                hashlib.sha256(broken.read_bytes()).hexdigest(),
                EXPECTED_ROM_SHA256,
            )
            result = run_cli("--rom", str(broken), "--out-dir", str(Path(tmp) / "out"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sha-256", result.stderr.lower())
            self.assertIn("refusing", result.stderr.lower())
            self.assertFalse(
                (Path(tmp) / "out" / OUTPUT_MANIFEST).exists(),
                "a refused run must not leave a manifest behind",
            )

    def test_rom_hash_gate_rejects_a_truncated_rom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "truncated.gba"
            broken.write_bytes(ROM_PATH.read_bytes()[: 1024 * 1024])
            result = run_cli("--rom", str(broken), "--out-dir", str(Path(tmp) / "out"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sha-256", result.stderr.lower())

    def test_missing_rom_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(
                "--rom", str(Path(tmp) / "nope.gba"), "--out-dir", str(Path(tmp) / "out")
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr.lower())

    # -- decoding --------------------------------------------------------
    def test_lz77_records_decode_to_the_expected_bytes_and_hashes(self) -> None:
        rom = ROM_PATH.read_bytes()
        tiles, tiles_end = lz77_decompress(rom, 0xB9E94, expected_bytes=1024)
        palette, palette_end = lz77_decompress(rom, 0xB9F5C, expected_bytes=32)
        self.assertEqual(len(tiles), 1024)
        self.assertEqual(len(palette), 32)
        self.assertEqual(hashlib.sha256(tiles).hexdigest(), TILES_SHA256)
        self.assertEqual(hashlib.sha256(palette).hexdigest(), PALETTE_SHA256)
        # The two records are adjacent: the tiles record ends two bytes before
        # the palette record starts (0x080B9F5A -> 0x080B9F5C).
        self.assertEqual(tiles_end, 0xB9F5A)
        self.assertEqual(palette_end, 0xB9F80)

    def test_lz77_refuses_a_record_with_a_wrong_header(self) -> None:
        rom = bytearray(ROM_PATH.read_bytes())
        rom[0xB9E94] = 0x11
        with self.assertRaises(ExportError):
            lz77_decompress(bytes(rom), 0xB9E94, expected_bytes=1024)

    def test_lz77_refuses_a_declared_size_that_does_not_match(self) -> None:
        rom = ROM_PATH.read_bytes()
        with self.assertRaises(ExportError):
            lz77_decompress(rom, 0xB9E94, expected_bytes=999)

    def test_lz77_refuses_a_truncated_stream(self) -> None:
        rom = ROM_PATH.read_bytes()[: 0xB9E98 + 4]
        with self.assertRaises(ExportError):
            lz77_decompress(rom, 0xB9E94, expected_bytes=1024)

    def test_palette_entries_decode_to_the_expected_8bit_rgb(self) -> None:
        for index, (raw, expected) in enumerate(
            zip(EXPECTED_PALETTE_BGR555, EXPECTED_PALETTE_RGB8)
        ):
            self.assertEqual(bgr555_to_rgb8(raw), expected, f"palette entry {index}")
        receipt = json.loads(
            (self.out_dir / OUTPUT_PALETTE_JSON).read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["bank"], 12)
        self.assertEqual(receipt["pram_destination"], "0x05000180")
        self.assertEqual(receipt["sha256"], PALETTE_SHA256)
        for index, entry in enumerate(receipt["entries"]):
            self.assertEqual(entry["index"], index)
            self.assertEqual(int(entry["bgr555"], 16), EXPECTED_PALETTE_BGR555[index])
            self.assertEqual(tuple(entry["rgb8"]), EXPECTED_PALETTE_RGB8[index])

    def test_tile_sheet_png_matches_the_4bpp_payload(self) -> None:
        from PIL import Image

        with Image.open(self.out_dir / OUTPUT_TILES_INDEX_PNG) as image:
            self.assertEqual(image.size, (64, 32))
            self.assertEqual(image.mode, "L")
            pixels = image.tobytes()
        for blob_index in range(32):
            for y in range(8):
                for x in range(8):
                    offset = blob_index * 32 + y * 4 + x // 2
                    byte = self.tiles[offset]
                    expected = byte >> 4 if x % 2 == 0 else byte & 0x0F
                    sheet_x = (blob_index % 8) * 8 + x
                    sheet_y = (blob_index // 8) * 8 + y
                    self.assertEqual(
                        pixels[sheet_y * 64 + sheet_x],
                        expected,
                        f"tile {blob_index} pixel ({x},{y})",
                    )
        self.assertTrue((self.out_dir / OUTPUT_TILES_RENDER_PNG).is_file())

    # -- determinism -----------------------------------------------------
    def test_export_is_byte_for_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"
            for target in (first, second):
                result = run_cli(
                    "--rom", str(ROM_PATH), "--out-dir", str(target)
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            names = sorted(path.name for path in first.iterdir())
            self.assertEqual(names, sorted(path.name for path in second.iterdir()))
            self.assertIn(OUTPUT_MANIFEST, names)
            for name in names:
                self.assertEqual(
                    (first / name).read_bytes(),
                    (second / name).read_bytes(),
                    f"{name} is not reproducible",
                )
        # The shipped artifact is the same one the CLI produces.
        shipped = REPO_ROOT / "artifacts" / "s49-original-movegrid-overlay-v1"
        self.assertTrue((shipped / OUTPUT_TILES_BIN).is_file())
        self.assertEqual(
            hashlib.sha256((shipped / OUTPUT_TILES_BIN).read_bytes()).hexdigest(),
            TILES_SHA256,
        )

    def test_verify_mode_accepts_a_fresh_export(self) -> None:
        result = run_cli(
            "--rom", str(ROM_PATH), "--out-dir", str(self.out_dir), "--verify"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified", result.stdout)

    def test_verify_mode_rejects_a_tampered_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "export"
            shutil.copytree(self.out_dir, target)
            payload = bytearray((target / OUTPUT_TILES_BIN).read_bytes())
            payload[0] ^= 0xFF
            (target / OUTPUT_TILES_BIN).write_bytes(bytes(payload))
            result = run_cli(
                "--rom", str(ROM_PATH), "--out-dir", str(target), "--verify"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL", result.stderr)

    # -- the payload equals what the game had resident --------------------
    def test_exported_payload_equals_the_same_frame_receipts(self) -> None:
        for receipt in FRAME_RECEIPTS:
            directory = REPO_ROOT / "artifacts" / receipt
            for index in range(6):
                vram = (directory / f"vram-{index:02d}.bin").read_bytes()
                pram = (directory / f"pram-{index:02d}.bin").read_bytes()
                self.assertEqual(
                    vram[0x2000:0x2400],
                    self.tiles,
                    f"{receipt} frame {index}: VRAM 0x2000-0x2400",
                )
                self.assertEqual(
                    pram[0x180:0x1A0],
                    self.palette,
                    f"{receipt} frame {index}: PRAM bank 12",
                )

    def test_cross_check_block_records_the_evidence(self) -> None:
        cross = self.manifest["cross_check"]
        self.assertEqual(cross["status"], "run")
        self.assertEqual(len(cross["evidence"]), 4)
        for entry in cross["evidence"]:
            self.assertTrue(entry["tiles_match_vram_window"])
            self.assertTrue(entry["palette_match_pram_bank12"])
            self.assertEqual(entry["bg2_tilemap"]["palette_banks_used"], [12])
        changed = {
            Path(entry["directory"]).name: entry["bg2_tilemap_changed_cells_vs_baseline"]
            for entry in cross["evidence"]
        }
        self.assertEqual(
            changed,
            {
                "s49-original-movegrid-frame-v1": 212,
                "s49-original-grid16-frame-v1": 164,
                "s49-original-field-frame-v1": 0,
                "s49-original-banner-frame-v1": 691,
            },
        )

    def test_bg2_tilemap_changed_cells_movegrid_versus_field(self) -> None:
        """Derived from the frame receipts, not from the mechanism receipt."""

        def cells(receipt: str) -> list[int]:
            vram = (
                REPO_ROOT / "artifacts" / receipt / "vram-00.bin"
            ).read_bytes()
            return [
                int.from_bytes(vram[0x1000 + 2 * i : 0x1002 + 2 * i], "little")
                for i in range(1024)
            ]

        field = cells("s49-original-field-frame-v1")
        movegrid = cells("s49-original-movegrid-frame-v1")
        grid16 = cells("s49-original-grid16-frame-v1")
        self.assertEqual(sum(1 for a, b in zip(field, movegrid) if a != b), 212)
        self.assertEqual(sum(1 for a, b in zip(field, grid16) if a != b), 164)
        for cell in movegrid:
            self.assertEqual((cell >> 12) & 0x0F, 12, "every BG2 cell uses bank 12")

    # -- the manifest agrees with the signed mechanism receipt -------------
    def test_manifest_agrees_with_the_mechanism_receipt(self) -> None:
        frame = self.mechanism["move_range_frame"]
        registers = frame["registers"]

        # DISPCNT: bit 10 is the BG2 enable and the receipt's movegrid frame
        # has it set.
        self.assertEqual(registers["dispcnt"], "0x1D40")
        self.assertEqual(int(registers["dispcnt"], 16) & (1 << 10), 1 << 10)

        # BGCNT of BG2, decoded with mGBA's GBA BGCNT layout (the layout the
        # receipt's own field table uses): char base bits 2-3, screen base
        # bits 8-12.
        bgcnt = int(registers["bgcnt"][2], 16)
        self.assertEqual(bgcnt, 0x0202)
        self.assertEqual((bgcnt >> 2) & 0x03, 0)  # character base block
        self.assertEqual((bgcnt >> 8) & 0x1F, 2)  # screen base block
        self.assertEqual(registers["bgcnt_fields"][2]["char_base_block"], 0)
        self.assertEqual(registers["bgcnt_fields"][2]["screen_base_block"], 2)
        self.assertEqual(registers["bgcnt_fields"][2]["palette_256"], 0)

        tiles = self.manifest["tiles"]
        self.assertEqual(tiles["bg_char_base_block"], 0)
        self.assertEqual(tiles["bg_char_base"], "0x06000000")
        self.assertEqual(tiles["bpp"], 4)
        self.assertEqual(tiles["vram_destination"], "0x06002000")
        self.assertEqual(
            tiles["vram_destination"],
            f"0x{0x06000000 + 256 * 32:08X}",
            "the payload is the BG2 character base plus tile 256",
        )
        self.assertEqual(self.manifest["palette"]["bank"], 12)
        self.assertEqual(self.manifest["palette"]["pram_destination"], "0x05000180")

        # The map layer's tile graphics are untouched between the two frames:
        # the overlay owns its own tiles instead of being a map copy.
        self.assertEqual(
            frame["map_layer_unchanged"]["bg0_tile_graphics_bytes_changed"], 0
        )
        self.assertEqual(
            frame["map_layer_unchanged"]["bg1_tile_graphics_bytes_changed"], 0
        )

        # The receipt's BG2 diffs are movegrid-versus-banner; recompute them.
        self.assertEqual(frame["bg_tilemap_cells"]["bg2"], 706)
        self.assertEqual(
            frame["map_layer_unchanged"]["bg2_region_bytes_changed"], 706
        )
        grid = (
            REPO_ROOT / "artifacts" / "s49-original-movegrid-frame-v1" / "vram-00.bin"
        ).read_bytes()
        banner = (
            REPO_ROOT / "artifacts" / "s49-original-banner-frame-v1" / "vram-00.bin"
        ).read_bytes()
        self.assertEqual(
            sum(
                1
                for a, b in zip(grid[0x1000:0x1800], banner[0x1000:0x1800])
                if a != b
            ),
            706,
        )
        self.assertEqual(
            sum(
                1
                for a, b in zip(grid[0x4000:0x8000], banner[0x4000:0x8000])
                if a != b
            ),
            0,
        )

    def test_manifest_records_the_not_established_scope(self) -> None:
        scope = self.manifest["scope"]
        self.assertIn("established", scope)
        self.assertIn("not_established", scope)
        joined = " ".join(scope["not_established"]).lower()
        for topic in (
            "runtime",
            "reachable",
            "natural execution",
        ):
            self.assertIn(topic, joined, f"{topic} must be listed as not established")
        established = " ".join(scope["established"]).lower()
        self.assertNotIn("natural execution", established)

    def test_manifest_declares_no_timestamp(self) -> None:
        self.assertEqual(self.manifest["determinism"]["timestamp"], "omitted")
        self.assertNotIn("generated_at", self.manifest)
        self.assertNotIn("timestamp", self.manifest["blobs"]["tiles"])


if __name__ == "__main__":
    unittest.main()
