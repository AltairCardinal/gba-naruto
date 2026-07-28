#!/usr/bin/env python3
"""Complete, ROM-bound export of the menu/story portrait matrix."""

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
TABLE_SHA256 = "bfc995240519eca9035e140a45e506a5c1f6f561e05827a589b5ac03543bba7e"


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


class MenuPortraitExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_menu_portraits import export_menu_portraits

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "menu-portraits"
        cls.manifest = export_menu_portraits(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_six_component_layout_reconstructs_every_canvas_pixel(self):
        from tools.export_menu_portraits import (
            PORTRAIT_BYTES,
            render_portrait_indices,
        )

        graphics = bytearray(PORTRAIT_BYTES)
        expected_sources = {
            (0, 0): 2304,
            (7, 0): 2311,
            (8, 0): 2368,
            (0, 8): 2816,
            (63, 63): 6399,
            (64, 0): 768,
            (72, 0): 832,
            (64, 8): 896,
            (64, 32): 256,
            (0, 64): 1792,
            (32, 64): 1280,
            (64, 64): 0,
        }
        for value, source_offset in enumerate(
            expected_sources.values(),
            start=1,
        ):
            graphics[source_offset] = value

        pixels = render_portrait_indices(bytes(graphics))

        def pixel(x: int, y: int) -> int:
            return pixels[y * 80 + x]

        self.assertEqual(80 * 80, len(pixels))
        for value, coordinate in enumerate(expected_sources, start=1):
            self.assertEqual(value, pixel(*coordinate), coordinate)
        self.assertEqual(set(range(13)), set(pixels))

    def test_exports_the_complete_matrix_and_global_variant(self):
        manifest = self.manifest
        self.assertEqual("menu-portrait-export-v1", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x5A4DEC,
                "gba_address": "0x085A4DEC",
                "entry_count": 63,
                "entry_size": 40,
                "variants_per_entry": 5,
                "sha256": TABLE_SHA256,
                "verification": "runtime_verified",
            },
            manifest["source_table"],
        )
        self.assertEqual(310, manifest["matrix_portrait_count"])
        self.assertEqual(1, manifest["special_portrait_count"])
        self.assertEqual(311, manifest["portrait_count"])
        self.assertEqual(74, manifest["unique_resource_count"])
        self.assertEqual(70, manifest["unique_graphics_count"])
        self.assertEqual(311, len(manifest["portraits"]))

        output_names = {row["png"] for row in manifest["portraits"]}
        self.assertEqual(311, len(output_names))
        self.assertEqual(
            312,
            len(list(self.output_dir.iterdir())),
        )
        self.assertTrue((self.output_dir / "manifest.json").is_file())

    def test_manifest_binds_each_output_to_rom_bytes_and_source_pair(self):
        portraits = self.manifest["portraits"]
        naruto = portraits[0]
        self.assertEqual(
            {
                "portrait_id": 1,
                "variant": 0,
                "kind": "matrix",
                "pair_file_offset": 0x5A4E14,
                "pair_gba_address": "0x085A4E14",
                "gfx_pointer": "0x08408BD8",
                "palette_pointer": "0x084098C4",
            },
            {
                key: naruto[key]
                for key in (
                    "portrait_id",
                    "variant",
                    "kind",
                    "pair_file_offset",
                    "pair_gba_address",
                    "gfx_pointer",
                    "palette_pointer",
                )
            },
        )
        self.assertEqual(6400, naruto["decompressed_size"])
        self.assertEqual(
            "a7eb566c2b1dcfb0357dfa93a526af1132c97fec3d6cfa683760cd3d7e41c64b",
            naruto["decompressed_sha256"],
        )
        self.assertEqual(128, naruto["palette_size"])
        self.assertEqual(
            "cb61b78fb80795ed2f2fc59ed7ceb8f2fd70bde7af7827c0b1a8b9232a01d48c",
            naruto["palette_sha256"],
        )
        self.assertEqual(
            "40cf158dc46eba1e4213dc58ffe278994738a5343931d3e7a992cde93d9d737f",
            naruto["png_sha256"],
        )

        special = portraits[-1]
        self.assertIsNone(special["portrait_id"])
        self.assertEqual(5, special["variant"])
        self.assertEqual("global_special", special["kind"])
        self.assertEqual(0x5A4DE4, special["pair_file_offset"])
        self.assertEqual("0x0840D1A8", special["gfx_pointer"])
        self.assertEqual("0x0840DE80", special["palette_pointer"])
        self.assertEqual(
            "ebf1af7a781d25dde81f4815a0af4c9743b3ffa439b30cceb6604a9a6360012f",
            special["decompressed_sha256"],
        )

        rom = (ROOT / "rom/base.gba").read_bytes()
        matrix = json.loads(
            (ROOT / "sequel/content/menu-ui/bank.json").read_text(
                encoding="utf-8"
            )
        )
        for row in portraits:
            offset = row["pair_file_offset"]
            gfx_pointer, palette_pointer = struct.unpack_from("<II", rom, offset)
            self.assertEqual(f"0x{gfx_pointer:08X}", row["gfx_pointer"])
            self.assertEqual(
                f"0x{palette_pointer:08X}",
                row["palette_pointer"],
            )
            png_path = self.output_dir / row["png"]
            self.assertEqual(
                row["png_sha256"],
                hashlib.sha256(png_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(80 * 80, row["pixel_count"])

            if row["kind"] == "matrix":
                source = matrix["entries"][row["portrait_id"]]
                self.assertEqual(
                    source[f"gfx_ptr_{row['variant']}"],
                    gfx_pointer,
                )
                self.assertEqual(
                    source[f"palette_ptr_{row['variant']}"],
                    palette_pointer,
                )

    def test_duplicate_matrix_pairs_share_resource_identity_and_png_bytes(self):
        rows = {
            (row["portrait_id"], row["variant"]): row
            for row in self.manifest["portraits"]
            if row["kind"] == "matrix"
        }
        duplicate_rows = [rows[(4, variant)] for variant in range(5)]
        self.assertEqual(
            1,
            len({row["resource_id"] for row in duplicate_rows}),
        )
        self.assertEqual(
            1,
            len({row["png_sha256"] for row in duplicate_rows}),
        )
        self.assertEqual(
            1,
            len(
                {
                    (row["decompressed_sha256"], row["palette_sha256"])
                    for row in duplicate_rows
                }
            ),
        )

    def test_outputs_lossless_indexed_png_with_obj_transparency(self):
        naruto = self.output_dir / self.manifest["portraits"][0]["png"]
        chunks = _png_chunks(naruto)
        width, height, bit_depth, color_type, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", chunks[b"IHDR"][0])
        )
        self.assertEqual((80, 80), (width, height))
        self.assertEqual((8, 3), (bit_depth, color_type))
        self.assertEqual((0, 0, 0), (compression, filtering, interlace))
        self.assertEqual(64 * 3, len(chunks[b"PLTE"][0]))
        self.assertEqual(64, len(chunks[b"tRNS"][0]))
        self.assertEqual(0, chunks[b"tRNS"][0][0])
        self.assertEqual({255}, set(chunks[b"tRNS"][0][1:]))

    def test_cli_repeats_the_export_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cli-export"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_menu_portraits.py",
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
            self.assertIn("311 portraits", completed.stdout)
            self.assertEqual(
                (self.output_dir / "manifest.json").read_bytes(),
                (output / "manifest.json").read_bytes(),
            )
            for row in self.manifest["portraits"]:
                self.assertEqual(
                    (self.output_dir / row["png"]).read_bytes(),
                    (output / row["png"]).read_bytes(),
                )

    def test_committed_artifacts_match_a_fresh_export(self):
        committed = ROOT / "artifacts/menu-portraits-v1"
        expected_names = {
            "manifest.json",
            *(row["png"] for row in self.manifest["portraits"]),
        }
        self.assertEqual(
            expected_names,
            {path.name for path in committed.iterdir() if path.is_file()},
        )
        self.assertEqual(
            (self.output_dir / "manifest.json").read_bytes(),
            (committed / "manifest.json").read_bytes(),
        )
        for row in self.manifest["portraits"]:
            self.assertEqual(
                (self.output_dir / row["png"]).read_bytes(),
                (committed / row["png"]).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
