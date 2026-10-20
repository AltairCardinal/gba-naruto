#!/usr/bin/env python3
"""The original S49 move-range overlay must land in the remake as a real asset.

The original game's move-range overlay is a dedicated BG2 layer that owns its
own 4bpp tile set (32 tiles) and its own 16 colour palette (bank 12).  Both
payloads live in the ROM as two adjacent LZ77 records:

* ``0x080B9E94`` -> 198 compressed bytes -> 1024 bytes (32 tiles of 4bpp),
  SHA-256 ``0f86c803...``;
* ``0x080B9F5C`` -> 36 compressed bytes -> 32 bytes (16 BGR555 entries),
  SHA-256 ``d198ec85...``.

``tools/generate_butano_movegrid_overlay_assets.py`` lifts both payloads out of
the pinned ROM and writes them into the remake's asset pipeline:

* ``butano-sequel/graphics/battle_movegrid_overlay_tiles.bmp`` -- a 64x32
  4bpp indexed bitmap (8 columns x 4 rows of 8x8 tiles, tile 256 at the
  top-left) that Butano's graphics tool can turn into a regular BG tile set;
* ``butano-sequel/graphics/battle_movegrid_overlay_tiles.json`` -- the
  graphics descriptor plus the ROM provenance of every input;
* ``butano-sequel/game/include/konoha/generated_battle_movegrid_overlay_content.h``
  -- a generated C++ header with the palette and the tile bytes as
  ``constexpr`` data.

This gate pins that pipeline down:

* the generator refuses to run on a ROM whose SHA-256 does not match, and it
  leaves no output behind when it refuses;
* the bitmap's pixel bytes are the ROM's decompressed 4bpp tile bytes, tile
  for tile;
* the bitmap's palette is the ROM's decompressed palette, and it equals the
  already exported ``movegrid-palette.json``;
* the header's palette and tile bytes match the bitmap;
* two runs produce byte-identical files;
* the committed assets are the ones the generator produces;
* the M0 provenance audit still passes with the new generator registered.

**What this suite does NOT establish.**  The rule that picks a tile for a
given tilemap cell is owned by another agent (see
``notes/s49-movegrid-overlay-implementation-spec-20261020.md``); this suite
only proves that the graphics and the palette are the original's bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.generate_butano_movegrid_overlay_assets import (  # noqa: E402
    AUXILIARY_PRODUCTS,
    BASE_TILE_INDEX,
    GENERATED_PRODUCTS,
    GRAPHICS_BMP_NAME,
    GRAPHICS_JSON_NAME,
    HEADER_NAME,
    PALETTE_COMPRESSED_BYTES,
    PALETTE_DECOMPRESSED_BYTES,
    PALETTE_DECOMPRESSED_SHA256,
    PALETTE_FILE_OFFSET,
    PALETTE_ROM_ADDRESS,
    SHEET_COLS,
    SHEET_HEIGHT,
    SHEET_ROWS,
    SHEET_WIDTH,
    TILE_COUNT,
    TILE_BYTES,
    TILES_COMPRESSED_BYTES,
    TILES_DECOMPRESSED_BYTES,
    TILES_DECOMPRESSED_SHA256,
    TILES_FILE_OFFSET,
    TILES_ROM_ADDRESS,
)

ROM_PATH = REPO_ROOT / "rom" / "base.gba"
GENERATOR = REPO_ROOT / "tools" / "generate_butano_movegrid_overlay_assets.py"
AUDITOR = REPO_ROOT / "tools" / "audit_butano_reverse_provenance.py"
REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")

EXPORT_DIR = REPO_ROOT / "artifacts" / "s49-original-movegrid-overlay-v1"
EXPORT_TILES = EXPORT_DIR / "movegrid-tiles-4bpp.bin"
EXPORT_PALETTE_BIN = EXPORT_DIR / "movegrid-palette.bin"
EXPORT_PALETTE_JSON = EXPORT_DIR / "movegrid-palette.json"

SHIPPED_BMP = REPO_ROOT / "butano-sequel" / "graphics" / GRAPHICS_BMP_NAME
SHIPPED_JSON = REPO_ROOT / "butano-sequel" / "graphics" / GRAPHICS_JSON_NAME
SHIPPED_HEADER = (
    REPO_ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / HEADER_NAME
)


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )


def parse_4bpp_bmp(
    data: bytes,
) -> tuple[int, int, list[int], list[tuple[int, int, int]]]:
    """Decode an uncompressed 4bpp indexed BMP.

    Returns ``(width, height, pixels, palette)`` with the pixels in top-down
    row-major order and the palette as RGB tuples.
    """

    if data[:2] != b"BM":
        raise AssertionError("not a BMP file")
    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    header_size = struct.unpack_from("<I", data, 14)[0]
    if header_size != 40:
        raise AssertionError(f"unexpected DIB header size: {header_size}")
    width, height = struct.unpack_from("<ii", data, 18)
    planes, bits, compression = struct.unpack_from("<HHI", data, 26)
    if (planes, bits, compression) != (1, 4, 0):
        raise AssertionError(
            f"expected an uncompressed 4bpp BMP, got {(planes, bits, compression)}"
        )
    colors_used = struct.unpack_from("<I", data, 46)[0]
    if colors_used != 16:
        raise AssertionError(f"expected 16 palette entries, got {colors_used}")

    palette: list[tuple[int, int, int]] = []
    for index in range(16):
        blue, green, red, _ = data[54 + index * 4 : 58 + index * 4]
        palette.append((red, green, blue))

    packed_width = (width + 1) // 2
    row_size = (packed_width + 3) & ~3
    pixels: list[int] = []
    for y in range(height):
        start = pixel_offset + (height - 1 - y) * row_size
        row = data[start : start + packed_width]
        for x in range(width):
            byte = row[x // 2]
            pixels.append(byte >> 4 if x % 2 == 0 else byte & 0x0F)
    return width, height, pixels, palette


def header_rgb5(text: str) -> list[tuple[int, int, int]]:
    match = re.search(
        r"battle_movegrid_overlay_palette_rgb5\s*=\s*\{\{(.*?)\}\};",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("the header has no rgb5 palette")
    entries = re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}", match.group(1))
    return [tuple(int(value) for value in entry) for entry in entries]


def header_rgb8(text: str) -> list[tuple[int, int, int]]:
    match = re.search(
        r"battle_movegrid_overlay_palette_rgb8\s*=\s*\{\{(.*?)\}\};",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("the header has no rgb8 palette")
    entries = re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}", match.group(1))
    return [tuple(int(value) for value in entry) for entry in entries]


def header_bytes(text: str, name: str) -> bytes:
    match = re.search(
        rf"{name}\s*=\s*\{{\{{\s*(.*?)\s*\}}\}};",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"the header has no {name} array")
    values = re.findall(r"0x([0-9a-fA-F]{1,2})\b", match.group(1))
    return bytes(int(value, 16) for value in values)


def header_words(text: str, name: str) -> list[int]:
    match = re.search(
        rf"{name}\s*=\s*\{{\{{\s*(.*?)\s*\}}\}};",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"the header has no {name} array")
    values = re.findall(r"0x([0-9a-fA-F]{8})\b", match.group(1))
    return [int(value, 16) for value in values]


class MovegridOverlayAssetTests(unittest.TestCase):
    """The generated assets must be the original's bytes, reproducibly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out_dir = Path(cls._tmp.name) / "out"
        cls.graphics_dir = cls.out_dir / "graphics"
        cls.header_path = cls.out_dir / "include" / HEADER_NAME
        cls.result = run_generator(
            "--rom",
            str(ROM_PATH),
            "--graphics-dir",
            str(cls.graphics_dir),
            "--header",
            str(cls.header_path),
        )
        if cls.result.returncode != 0:
            raise AssertionError(
                f"generator failed: rc={cls.result.returncode}\n"
                f"stdout={cls.result.stdout}\nstderr={cls.result.stderr}"
            )
        cls.bmp_path = cls.graphics_dir / GRAPHICS_BMP_NAME
        cls.json_path = cls.graphics_dir / GRAPHICS_JSON_NAME
        cls.bmp = cls.bmp_path.read_bytes()
        cls.sidecar = json.loads(cls.json_path.read_text(encoding="utf-8"))
        cls.header = cls.header_path.read_text(encoding="utf-8")
        cls.rom_tiles = cls._rom_tiles()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @staticmethod
    def _rom_tiles() -> bytes:
        from tools.butano.export_s49_movegrid_overlay import lz77_decompress

        rom = ROM_PATH.read_bytes()
        tiles, _ = lz77_decompress(
            rom, TILES_FILE_OFFSET, expected_bytes=TILES_DECOMPRESSED_BYTES
        )
        return tiles

    # -- the bitmap ------------------------------------------------------
    def test_bmp_is_a_64x32_4bpp_indexed_bitmap(self) -> None:
        width, height, pixels, palette = parse_4bpp_bmp(self.bmp)
        self.assertEqual((width, height), (SHEET_WIDTH, SHEET_HEIGHT))
        self.assertEqual((SHEET_COLS, SHEET_ROWS), (8, 4))
        self.assertEqual(len(pixels), SHEET_WIDTH * SHEET_HEIGHT)
        self.assertEqual(len(palette), 16)

    def test_bmp_pixel_bytes_equal_the_rom_tile_bytes(self) -> None:
        """Every tile of the sheet is the ROM's tile, byte for byte."""

        _, _, pixels, _ = parse_4bpp_bmp(self.bmp)
        tiles = self.rom_tiles
        self.assertEqual(len(tiles), TILE_COUNT * TILE_BYTES)
        for blob_index in range(TILE_COUNT):
            origin_x = (blob_index % SHEET_COLS) * 8
            origin_y = (blob_index // SHEET_COLS) * 8
            for y in range(8):
                for x in range(8):
                    packed = tiles[blob_index * TILE_BYTES + y * 4 + x // 2]
                    expected = packed >> 4 if x % 2 == 0 else packed & 0x0F
                    self.assertEqual(
                        pixels[(origin_y + y) * SHEET_WIDTH + origin_x + x],
                        expected,
                        f"tile {blob_index} pixel ({x},{y})",
                    )
        # And the sheet, regrouped tile by tile, is the ROM payload: the sheet
        # is the blob order, row major over 8 columns, and every tile of the
        # sheet is 8 rows of 4 bytes.
        sheet_tiles = bytearray()
        for blob_index in range(TILE_COUNT):
            origin_x = (blob_index % SHEET_COLS) * 8
            origin_y = (blob_index // SHEET_COLS) * 8
            for y in range(8):
                for x in range(0, 8, 2):
                    sheet_tiles.append(
                        (pixels[(origin_y + y) * SHEET_WIDTH + origin_x + x] << 4)
                        | pixels[(origin_y + y) * SHEET_WIDTH + origin_x + x + 1]
                    )
        self.assertEqual(len(sheet_tiles), TILE_COUNT * TILE_BYTES)
        self.assertEqual(bytes(sheet_tiles), tiles)

    def test_bmp_palette_equals_the_exported_palette(self) -> None:
        _, _, _, palette = parse_4bpp_bmp(self.bmp)
        exported = json.loads(EXPORT_PALETTE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(exported["sha256"], PALETTE_DECOMPRESSED_SHA256)
        for index, entry in enumerate(exported["entries"]):
            self.assertEqual(palette[index], tuple(entry["rgb8"]), f"entry {index}")
            self.assertEqual(exported["entries"][index]["index"], index)
        # The raw palette bytes are the ROM's 32 bytes, unchanged.
        self.assertEqual(
            EXPORT_PALETTE_BIN.read_bytes(),
            b"".join(
                int(entry["bgr555"], 16).to_bytes(2, "little")
                for entry in exported["entries"]
            ),
        )

    def test_bmp_palette_survives_the_8bit_round_trip(self) -> None:
        """The 5-bit channels survive the BMP round trip exactly."""

        _, _, _, palette = parse_4bpp_bmp(self.bmp)
        exported = json.loads(EXPORT_PALETTE_JSON.read_text(encoding="utf-8"))
        for index, entry in enumerate(exported["entries"]):
            for channel, value in enumerate(entry["rgb8"]):
                five_bit = entry["rgb5"][channel]
                self.assertEqual(
                    value >> 3,
                    five_bit,
                    f"entry {index} channel {channel}",
                )
                self.assertEqual(
                    (five_bit << 3) | (five_bit >> 2),
                    value,
                    f"entry {index} channel {channel} is not 5-bit exact",
                )
            self.assertEqual(len(palette), 16)

    # -- the header ------------------------------------------------------
    def test_header_palette_matches_the_bitmap(self) -> None:
        _, _, _, palette = parse_4bpp_bmp(self.bmp)
        self.assertEqual(header_rgb8(self.header), palette)
        exported = json.loads(EXPORT_PALETTE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(
            header_rgb5(self.header),
            [tuple(entry["rgb5"]) for entry in exported["entries"]],
        )

    def test_header_tile_data_matches_the_bitmap(self) -> None:
        tiles = self.rom_tiles
        self.assertEqual(header_bytes(self.header, "battle_movegrid_overlay_tile_data"), tiles)
        words = header_words(self.header, "battle_movegrid_overlay_tile_words")
        self.assertEqual(len(words), len(tiles) // 4)
        self.assertEqual(
            b"".join(word.to_bytes(4, "little") for word in words),
            tiles,
        )

    def test_header_exposes_the_tile_indices_and_the_layout(self) -> None:
        match = re.search(
            r"battle_movegrid_overlay_tile_indices\s*=\s*\{(.*?)\};",
            self.header,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        indices = [
            int(value) for value in re.findall(r"(\d+)", match.group(1))
        ]
        self.assertEqual(
            indices,
            [BASE_TILE_INDEX + index for index in range(TILE_COUNT)],
        )
        self.assertIn("battle_movegrid_overlay_base_tile_index = 256", self.header)
        self.assertIn("battle_movegrid_overlay_tile_count = 32", self.header)
        self.assertIn("battle_movegrid_overlay_sheet_cols = 8", self.header)
        self.assertIn("battle_movegrid_overlay_sheet_rows = 4", self.header)
        self.assertIn("battle_movegrid_overlay_sheet_width = 64", self.header)
        self.assertIn("battle_movegrid_overlay_sheet_height = 32", self.header)

    def test_header_declares_its_provenance(self) -> None:
        self.assertIn(
            "// Generated by tools/generate_butano_movegrid_overlay_assets.py.",
            self.header,
        )
        self.assertIn("// provenance-carrier: c-header-comment", self.header)
        self.assertIn("// reverse-source: rom-pointer-lz77-inventory-v1 @ ", self.header)
        self.assertIn(
            f"// reverse-source-rom: 0x{TILES_FILE_OFFSET:06X}+"
            f"{TILES_COMPRESSED_BYTES} sha256 ",
            self.header,
        )
        self.assertIn(
            f"// reverse-source-rom: 0x{PALETTE_FILE_OFFSET:06X}+"
            f"{PALETTE_COMPRESSED_BYTES} sha256 ",
            self.header,
        )

    # -- the sidecar -----------------------------------------------------
    def test_sidecar_records_the_rom_provenance(self) -> None:
        sidecar = self.sidecar
        self.assertEqual(sidecar["type"], "regular_bg_tiles")
        self.assertEqual(sidecar["bpp_mode"], "bpp_4")
        self.assertEqual(sidecar["rom"]["sha256"], self._rom_sha256())
        tiles = sidecar["blobs"]["tiles"]
        self.assertEqual(tiles["rom_address"], f"0x{TILES_ROM_ADDRESS:08X}")
        self.assertEqual(tiles["file_offset"], TILES_FILE_OFFSET)
        self.assertEqual(tiles["compressed_bytes"], TILES_COMPRESSED_BYTES)
        self.assertEqual(tiles["decompressed_bytes"], TILES_DECOMPRESSED_BYTES)
        self.assertEqual(tiles["decompressed_sha256"], TILES_DECOMPRESSED_SHA256)
        palette = sidecar["blobs"]["palette"]
        self.assertEqual(palette["rom_address"], f"0x{PALETTE_ROM_ADDRESS:08X}")
        self.assertEqual(palette["file_offset"], PALETTE_FILE_OFFSET)
        self.assertEqual(palette["compressed_bytes"], PALETTE_COMPRESSED_BYTES)
        self.assertEqual(palette["decompressed_bytes"], PALETTE_DECOMPRESSED_BYTES)
        self.assertEqual(palette["decompressed_sha256"], PALETTE_DECOMPRESSED_SHA256)

    def test_sidecar_records_the_tile_layout(self) -> None:
        layout = self.sidecar["tiles"]["layout"]
        self.assertEqual(len(layout), TILE_COUNT)
        for blob_index, entry in enumerate(layout):
            self.assertEqual(entry["blob_index"], blob_index)
            self.assertEqual(entry["tile_index"], BASE_TILE_INDEX + blob_index)
            self.assertEqual(entry["sheet_col"], blob_index % SHEET_COLS)
            self.assertEqual(entry["sheet_row"], blob_index // SHEET_COLS)
            self.assertEqual(entry["x"], (blob_index % SHEET_COLS) * 8)
            self.assertEqual(entry["y"], (blob_index // SHEET_COLS) * 8)

    def test_sidecar_declares_no_timestamp(self) -> None:
        text = self.json_path.read_text(encoding="utf-8")
        for token in ("generated_at", "timestamp", "created"):
            self.assertNotIn(token, text)

    @staticmethod
    def _rom_sha256() -> str:
        return hashlib.sha256(ROM_PATH.read_bytes()).hexdigest()

    # -- gates -----------------------------------------------------------
    def test_generator_refuses_a_rom_with_one_flipped_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.gba"
            data = bytearray(ROM_PATH.read_bytes())
            data[TILES_FILE_OFFSET] ^= 0x01
            broken.write_bytes(bytes(data))
            self.assertNotEqual(
                hashlib.sha256(broken.read_bytes()).hexdigest(),
                self._rom_sha256(),
            )
            out = Path(tmp) / "out"
            result = run_generator(
                "--rom",
                str(broken),
                "--graphics-dir",
                str(out / "graphics"),
                "--header",
                str(out / HEADER_NAME),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sha-256", result.stderr.lower())
            self.assertFalse(
                (out / "graphics" / GRAPHICS_BMP_NAME).exists(),
                "a refused run must not leave a bitmap behind",
            )
            self.assertFalse(
                (out / HEADER_NAME).exists(),
                "a refused run must not leave a header behind",
            )
            self.assertFalse(
                (out / "graphics").exists(),
                "a refused run must not create the output directory",
            )

    def test_generator_refuses_a_missing_rom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_generator(
                "--rom",
                str(Path(tmp) / "nope.gba"),
                "--graphics-dir",
                str(Path(tmp) / "graphics"),
                "--header",
                str(Path(tmp) / HEADER_NAME),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr.lower())

    def test_generator_is_byte_for_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for name in ("a", "b"):
                graphics = Path(tmp) / name / "graphics"
                header = Path(tmp) / name / HEADER_NAME
                result = run_generator(
                    "--rom",
                    str(ROM_PATH),
                    "--graphics-dir",
                    str(graphics),
                    "--header",
                    str(header),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(
                    {
                        GRAPHICS_BMP_NAME: (graphics / GRAPHICS_BMP_NAME).read_bytes(),
                        GRAPHICS_JSON_NAME: (graphics / GRAPHICS_JSON_NAME).read_bytes(),
                        HEADER_NAME: header.read_bytes(),
                    }
                )
            self.assertEqual(outputs[0], outputs[1])

    def test_committed_assets_are_the_generated_ones(self) -> None:
        self.assertTrue(SHIPPED_BMP.is_file())
        self.assertTrue(SHIPPED_JSON.is_file())
        self.assertTrue(SHIPPED_HEADER.is_file())
        self.assertEqual(
            SHIPPED_BMP.read_bytes(),
            self.bmp,
            "the committed bitmap is not the generated one",
        )
        self.assertEqual(
            SHIPPED_JSON.read_bytes(),
            self.json_path.read_bytes(),
            "the committed sidecar is not the generated one",
        )
        self.assertEqual(
            SHIPPED_HEADER.read_text(encoding="utf-8"),
            self.header,
            "the committed header is not the generated one",
        )

    def test_the_generated_bitmap_matches_the_exported_tile_payload(self) -> None:
        self.assertTrue(EXPORT_TILES.is_file())
        self.assertEqual(
            hashlib.sha256(EXPORT_TILES.read_bytes()).hexdigest(),
            TILES_DECOMPRESSED_SHA256,
        )
        self.assertEqual(EXPORT_TILES.read_bytes(), self.rom_tiles)

    # -- the registry and the M0 audit ------------------------------------
    def test_every_written_file_is_declared(self) -> None:
        written = {
            f"butano-sequel/graphics/{GRAPHICS_BMP_NAME}",
            f"butano-sequel/graphics/{GRAPHICS_JSON_NAME}",
            f"butano-sequel/game/include/konoha/{HEADER_NAME}",
        }
        declared = set(GENERATED_PRODUCTS) | set(AUXILIARY_PRODUCTS)
        self.assertEqual(declared, written)
        self.assertEqual(
            set(GENERATED_PRODUCTS),
            {f"butano-sequel/game/include/konoha/{HEADER_NAME}"},
        )

    def test_the_provenance_audit_still_passes(self) -> None:
        if not (REVERSE_ROOT / "artifacts").is_dir():
            self.skipTest(f"the reverse work tree is absent: {REVERSE_ROOT}")
        result = subprocess.run(
            [sys.executable, str(AUDITOR)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("problems: none", result.stdout)
        self.assertIn(
            f"butano-sequel/game/include/konoha/{HEADER_NAME}"
            " -> rom-pointer-lz77-inventory-v1",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
