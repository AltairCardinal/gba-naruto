#!/usr/bin/env python3
"""ROM-backed tests for the complete 47-row battle-map canvas export."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_SHA256 = "977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c"


class MapCanvasExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_map_canvases import export_map_canvases

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "map-canvases"
        cls.manifest = export_map_canvases(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_all_rows_variants_and_deduplicated_resources(self):
        manifest = self.manifest
        self.assertEqual("map-canvases-v1", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x53D910,
                "gba_address": "0x0853D910",
                "entry_count": 47,
                "entry_size": 32,
                "sha256": TABLE_SHA256,
            },
            manifest["map_header_table"],
        )
        self.assertEqual(47, manifest["map_count"])
        self.assertEqual(61, manifest["canvas_count"])
        self.assertEqual(14, manifest["alternate_canvas_count"])
        self.assertEqual(
            {
                "tile_graphics": 34,
                "bg_palettes": 15,
                "primary_layouts": 35,
                "alternate_layouts": 12,
                "metatile_definitions": 35,
                "collision_grids": 35,
            },
            manifest["unique_resource_counts"],
        )
        self.assertEqual(
            289,
            len([path for path in self.output_dir.rglob("*") if path.is_file()]),
        )

    def test_map_40_matches_static_and_runtime_anchored_facts(self):
        entry = self.manifest["entries"][40]
        self.assertEqual(40, entry["map_id"])
        self.assertEqual("0x0053DE10", entry["header"]["file_offset_hex"])
        self.assertEqual([36, 44], entry["dimensions_tiles"])
        self.assertEqual([288, 352], entry["dimensions_pixels"])
        self.assertEqual([9, 22], entry["coarse_grid_dimensions"])
        self.assertIsNone(entry["resources"]["alternate_layout"])
        self.assertEqual(
            {
                "tile_graphics": (
                    12288,
                    "f7d4ac8b041bfcd7d5f1a2103e3402185fd57a35651a0f1d75e47e48d47a44c2",
                ),
                "bg_palette": (
                    384,
                    "3c86d041724735cc717fedffe8cca91ac9d717b7878c2296672e295eb12923e4",
                ),
                "primary_layout": (
                    792,
                    "950f9555a8b12c73b3c3fdabb50209917b849972ff1ee6c3e5b80ead5d472f6f",
                ),
                "metatile_definitions": (
                    1376,
                    "f557bf169836e7b1abdf2e6fac94887f0f50b9293a9976eb8e7c93d64e3bb3db",
                ),
                "collision_grid": (
                    396,
                    "b5519b9ecc7124c0da001af9f3901f2a1ef2bbd94799366474a12b016db66c91",
                ),
            },
            {
                name: (resource["decompressed_size"], resource["sha256"])
                for name, resource in entry["resources"].items()
                if resource is not None
            },
        )

        primary = entry["variants"][0]
        self.assertEqual("primary", primary["name"])
        self.assertEqual(
            "adc300b0566b30eb5988d7974e237dd5a4c16847908b2cffaf48bcb4f09015b9",
            primary["tilemap_sha256"],
        )
        self.assertEqual(
            "a4dd82c0d71778e2defc354375cb4819ceea66c5934af48725d6c9dad40cf419",
            primary["indexed_pixels_sha256"],
        )
        tilemap = (self.output_dir / primary["tilemap_bin"]).read_bytes()
        self.assertEqual(
            [0x4001, 0x4002, 0x4003, 0x4004],
            [
                int.from_bytes(tilemap[offset : offset + 2], "little")
                for offset in range(0, 8, 2)
            ],
        )
        # ROM-derived coordinate (x=12, y=16), independently traced through
        # coarse cell 8*9+3 and its left 2x2 metatile.
        index = 16 * 36 + 12
        self.assertEqual(
            0x3119,
            int.from_bytes(tilemap[index * 2 : index * 2 + 2], "little"),
        )
        self.assertEqual(363, primary["maximum_tile_index"])
        self.assertEqual(
            {"0": 1352, "1": 96, "2": 64, "3": 24, "4": 48},
            primary["palette_bank_usage"],
        )
        self.assertEqual(12, primary["horizontal_flip_count"])
        self.assertEqual(0, primary["vertical_flip_count"])

    def test_primary_canvases_match_preexisting_runtime_used_reconstructor(self):
        from tools.butano.generate_scenario_41_assets import reconstruct_map

        for map_id in (9, 41):
            expected = reconstruct_map(ROOT / "rom/base.gba", map_id)
            entry = self.manifest["entries"][map_id]
            primary = entry["variants"][0]
            self.assertEqual(
                hashlib.sha256(expected["pixels"]).hexdigest(),
                primary["indexed_pixels_sha256"],
            )
            with Image.open(self.output_dir / primary["canvas_png"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual(
                    (expected["width"], expected["height"]),
                    image.size,
                )
                self.assertEqual(expected["pixels"], image.tobytes())

    def test_alternate_layouts_are_exported_without_claiming_runtime_selection(self):
        alternate_entries = [
            entry
            for entry in self.manifest["entries"]
            if len(entry["variants"]) == 2
        ]
        self.assertEqual(14, len(alternate_entries))
        self.assertEqual(
            [0, 7, 8, 9, 10, 11, 12, 21, 22, 23, 31, 32, 34, 35],
            [entry["map_id"] for entry in alternate_entries],
        )
        for entry in alternate_entries:
            alternate = entry["variants"][1]
            self.assertEqual("alternate", alternate["name"])
            self.assertTrue(alternate["candidate_static_canvas"])
            self.assertFalse(alternate["runtime_selection_proven"])
            self.assertEqual(
                entry["dimensions_pixels"],
                [alternate["width"], alternate["height"]],
            )

    def test_runtime_selection_claim_is_limited_to_captured_map_41_primary(self):
        proven = []
        for entry in self.manifest["entries"]:
            for variant in entry["variants"]:
                self.assertEqual(variant["name"], variant["header_role"])
                if variant["runtime_selection_proven"]:
                    proven.append((entry["map_id"], variant["name"]))
        self.assertEqual([(41, "primary")], proven)

    def test_independent_verifier_rejects_tilemap_and_png_tampering(self):
        from tools.verify_map_canvases import verify_map_canvases

        result = verify_map_canvases(ROOT, self.output_dir)
        self.assertEqual([], result["errors"])
        self.assertEqual(47, result["verified_maps"])
        self.assertEqual(61, result["verified_canvases"])
        verifier_source = (ROOT / "tools/verify_map_canvases.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools.export_map_canvases", verifier_source)
        self.assertNotIn("reconstruct_map", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "tilemap"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "tilemaps/map-40-primary-u16le.bin"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            result = verify_map_canvases(ROOT, tampered_dir)
            self.assertEqual(60, result["verified_canvases"])
            self.assertTrue(
                any(str(path.relative_to(tampered_dir)) in error for error in result["errors"]),
                result["errors"],
            )

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "png"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "canvases/map-40-primary.png"
            with Image.open(path) as image:
                image.load()
                image.putpixel((0, 0), (image.getpixel((0, 0)) + 1) & 0xFF)
                image.save(path)
            result = verify_map_canvases(ROOT, tampered_dir)
            self.assertEqual(60, result["verified_canvases"])
            self.assertTrue(
                any(str(path.relative_to(tampered_dir)) in error for error in result["errors"]),
                result["errors"],
            )

    def test_cli_is_deterministic_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "export"
            command = [
                sys.executable,
                str(ROOT / "tools/export_map_canvases.py"),
                "--root",
                str(ROOT),
                "--output-dir",
                str(output_dir),
            ]
            subprocess.run(command, check=True, cwd=ROOT)
            first = (output_dir / "manifest.json").read_bytes()
            subprocess.run(command, check=True, cwd=ROOT)
            self.assertEqual(first, (output_dir / "manifest.json").read_bytes())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_map_canvases.py"),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(output_dir),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertIn('"errors": []', completed.stdout)


if __name__ == "__main__":
    unittest.main()
