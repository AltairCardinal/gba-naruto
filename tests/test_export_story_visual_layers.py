#!/usr/bin/env python3
"""Complete export of the 24 ROM-backed story visual text layers."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_SHA256 = "33acbc117fa59c56d7af11728c6519367c9d5db177de75c199ec91c1c59ec289"


def _encode_4bpp_tile(pixels: list[int]) -> bytes:
    if len(pixels) != 64:
        raise ValueError("test tile must contain 64 pixels")
    return bytes(
        pixels[index] | (pixels[index + 1] << 4)
        for index in range(0, len(pixels), 2)
    )


def _png_chunks(path: Path) -> dict[bytes, list[bytes]]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"{path} is not a PNG")
    chunks: dict[bytes, list[bytes]] = {}
    cursor = 8
    while cursor < len(data):
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4 : cursor + 8]
        payload = data[cursor + 8 : cursor + 8 + length]
        chunks.setdefault(kind, []).append(payload)
        cursor += 12 + length
    return chunks


class StoryVisualLayerExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_story_visual_layers import export_story_visual_layers

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "story-visual-layers"
        cls.manifest = export_story_visual_layers(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_renderer_applies_tile_base_and_both_flip_axes(self):
        from tools.export_story_visual_layers import (
            STORY_TILE_BASE,
            render_story_visual_indices,
        )

        tile_zero = bytes(32)
        tile_one_pixels = [
            (y * 8 + x) % 15 + 1
            for y in range(8)
            for x in range(8)
        ]
        tiles = tile_zero + _encode_4bpp_tile(tile_one_pixels)
        entries = [STORY_TILE_BASE] * (32 * 32)
        entries[0] = STORY_TILE_BASE + 1
        entries[1] = STORY_TILE_BASE + 1 | 1 << 10
        entries[32] = STORY_TILE_BASE + 1 | 1 << 11
        entries[33] = STORY_TILE_BASE + 1 | 3 << 10
        tilemap = struct.pack("<1024H", *entries)

        pixels = render_story_visual_indices(tiles, tilemap)

        def source(x: int, y: int) -> int:
            return tile_one_pixels[y * 8 + x]

        def pixel(x: int, y: int) -> int:
            return pixels[y * 256 + x]

        self.assertEqual(256 * 256, len(pixels))
        self.assertEqual(source(0, 0), pixel(0, 0))
        self.assertEqual(source(7, 7), pixel(7, 7))
        self.assertEqual(source(7, 0), pixel(8, 0))
        self.assertEqual(source(0, 0), pixel(15, 0))
        self.assertEqual(source(0, 7), pixel(0, 8))
        self.assertEqual(source(7, 7), pixel(8, 8))
        self.assertEqual(source(0, 0), pixel(15, 15))

    def test_exports_all_twenty_four_code_verified_descriptors(self):
        manifest = self.manifest
        self.assertEqual("story-visual-layer-export-v1", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x54229C,
                "gba_address": "0x0854229C",
                "entry_count": 24,
                "entry_size": 16,
                "sha256": TABLE_SHA256,
                "verification": "code_verified",
            },
            manifest["source_table"],
        )
        self.assertEqual(24, manifest["layer_count"])
        self.assertEqual(24, manifest["unique_graphics_count"])
        self.assertEqual(1, manifest["unique_palette_count"])
        self.assertEqual(24, manifest["unique_tilemap_count"])
        self.assertEqual(24, manifest["unique_layer_count"])
        self.assertEqual(24, len(manifest["layers"]))
        self.assertEqual(
            "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73",
            manifest["linked_visual_descriptor_bank"]["sha256"],
        )
        self.assertEqual(
            "code_verified",
            manifest["linked_visual_descriptor_bank"]["verification"],
        )
        self.assertEqual(
            25,
            len(list(self.output_dir.iterdir())),
        )

    def test_manifest_binds_every_layer_to_rom_and_linked_descriptor(self):
        first = self.manifest["layers"][0]
        self.assertEqual(
            {
                "layer_id": 0,
                "descriptor_file_offset": 0x54229C,
                "descriptor_gba_address": "0x0854229C",
                "config_id": 4,
                "linked_visual_descriptor_id": 4,
                "gfx_pointer": "0x0812FF50",
                "palette_pointer": "0x08130268",
                "tilemap_pointer": "0x08130290",
                "tile_base": 320,
                "tile_count": 39,
                "tile_index_min": 320,
                "tile_index_max": 358,
                "palette_banks": [15],
            },
            {
                key: first[key]
                for key in (
                    "layer_id",
                    "descriptor_file_offset",
                    "descriptor_gba_address",
                    "config_id",
                    "linked_visual_descriptor_id",
                    "gfx_pointer",
                    "palette_pointer",
                    "tilemap_pointer",
                    "tile_base",
                    "tile_count",
                    "tile_index_min",
                    "tile_index_max",
                    "palette_banks",
                )
            },
        )
        self.assertEqual(1248, first["gfx"]["decompressed_size"])
        self.assertEqual(
            "eebb3c181bd2c146fcdab6d46aea34cb1765409c9d15cc282715dafd3b128399",
            first["gfx"]["decompressed_sha256"],
        )
        self.assertEqual(32, first["palette"]["decompressed_size"])
        self.assertEqual(
            "5b4a67a7354e94cd7f8f99541ceaf43bdf2a978d5783b77b0d9c46c91432ce35",
            first["palette"]["decompressed_sha256"],
        )
        self.assertEqual(2048, first["tilemap"]["decompressed_size"])
        self.assertEqual(
            "0d67a5681a8e05c9c527c0ee9122871732fb0a44e59f218faef6095889fd98ff",
            first["tilemap"]["decompressed_sha256"],
        )
        self.assertEqual(
            "9ed626efa9ff6599eee12706d3037ec9801f0ae5d2db4dc89d814a6a749247d0",
            first["png_sha256"],
        )

        rom = (ROOT / "rom/base.gba").read_bytes()
        bank = json.loads(
            (ROOT / "sequel/content/battle-encounters/bank.json").read_text(
                encoding="utf-8"
            )
        )
        for layer in self.manifest["layers"]:
            offset = layer["descriptor_file_offset"]
            gfx, palette, tilemap, config = struct.unpack_from(
                "<IIII",
                rom,
                offset,
            )
            self.assertEqual(f"0x{gfx:08X}", layer["gfx_pointer"])
            self.assertEqual(f"0x{palette:08X}", layer["palette_pointer"])
            self.assertEqual(f"0x{tilemap:08X}", layer["tilemap_pointer"])
            self.assertEqual(config, layer["config_id"])
            self.assertEqual(
                bank["entries"][layer["layer_id"]]["config_id"],
                layer["linked_visual_descriptor_id"],
            )
            self.assertEqual(
                layer["tile_base"] + layer["tile_count"] - 1,
                layer["tile_index_max"],
            )
            png = self.output_dir / layer["png"]
            self.assertEqual(
                layer["png_sha256"],
                hashlib.sha256(png.read_bytes()).hexdigest(),
            )

    def test_runtime_literals_anchor_bg3_layout_and_linked_table(self):
        from tools.export_story_visual_layers import STORY_TILE_BASE

        rom = (ROOT / "rom/base.gba").read_bytes()
        character_base = struct.unpack_from("<I", rom, 0x87DBC)[0]
        graphics_destination = struct.unpack_from("<I", rom, 0x87EF0)[0]
        palette_destination = struct.unpack_from("<I", rom, 0x87EF4)[0]
        linked_table = struct.unpack_from("<I", rom, 0x87E30)[0]
        tilemap_destination = struct.unpack_from("<I", rom, 0x87EFC)[0]

        self.assertEqual(0x0600C000, character_base)
        self.assertEqual(0x0600E800, graphics_destination)
        self.assertEqual(
            STORY_TILE_BASE,
            (graphics_destination - character_base) // 32,
        )
        self.assertEqual(0x050001E0, palette_destination)
        self.assertEqual(0x085A320C, linked_table)
        self.assertEqual(0x06001800, tilemap_destination)

    def test_outputs_indexed_transparent_256_by_256_layers(self):
        first = self.output_dir / self.manifest["layers"][0]["png"]
        chunks = _png_chunks(first)
        width, height, bit_depth, color_type, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", chunks[b"IHDR"][0])
        )
        self.assertEqual((256, 256), (width, height))
        self.assertEqual((8, 3), (bit_depth, color_type))
        self.assertEqual((0, 0, 0), (compression, filtering, interlace))
        self.assertEqual(16 * 3, len(chunks[b"PLTE"][0]))
        self.assertEqual(16, len(chunks[b"tRNS"][0]))
        self.assertEqual(0, chunks[b"tRNS"][0][0])
        self.assertEqual({255}, set(chunks[b"tRNS"][0][1:]))

    def test_cli_repeats_the_export_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cli-export"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_story_visual_layers.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("24 story visual layers", completed.stdout)
            self.assertEqual(
                (self.output_dir / "manifest.json").read_bytes(),
                (output / "manifest.json").read_bytes(),
            )
            for layer in self.manifest["layers"]:
                self.assertEqual(
                    (self.output_dir / layer["png"]).read_bytes(),
                    (output / layer["png"]).read_bytes(),
                )

    def test_committed_artifacts_match_a_fresh_export(self):
        committed = ROOT / "artifacts/story-visual-layers-v1"
        expected_names = {
            "manifest.json",
            *(layer["png"] for layer in self.manifest["layers"]),
        }
        self.assertEqual(
            expected_names,
            {path.name for path in committed.iterdir() if path.is_file()},
        )
        self.assertEqual(
            (self.output_dir / "manifest.json").read_bytes(),
            (committed / "manifest.json").read_bytes(),
        )
        for layer in self.manifest["layers"]:
            self.assertEqual(
                (self.output_dir / layer["png"]).read_bytes(),
                (committed / layer["png"]).read_bytes(),
            )

    def test_independent_verifier_recomputes_committed_pixels(self):
        from tools.verify_story_visual_layer_export import (
            verify_story_visual_layer_export,
        )

        result = verify_story_visual_layer_export(
            ROOT,
            ROOT / "artifacts/story-visual-layers-v1",
        )
        self.assertEqual(
            "story-visual-layer-verification-v1",
            result["schema"],
        )
        self.assertEqual(24, result["verified_layers"])
        self.assertEqual(24, result["unique_png_count"])
        self.assertEqual([], result["errors"])


if __name__ == "__main__":
    unittest.main()
