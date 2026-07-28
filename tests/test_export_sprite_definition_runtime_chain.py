#!/usr/bin/env python3
"""ROM-backed evidence for the 43 generic sprite definition pairs."""

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
PAIR_TABLE_SHA256 = (
    "5873ae022e9b6290f876aab367b6dbe95b7a97b9b7a2f15d0861dc747196f3f8"
)
TILE_OFFSET_TABLE_SHA256 = (
    "86d57e438c3b3e9a877ebea8d910e2782c30b5bcbf8ca4f305df1deee6d231d6"
)
COMPONENT_WINDOWS_SHA256 = (
    "439eb69f5ee2eadefe6fbd66b88ba27fb53c6552ac184267a803917fe8e98248"
)
GRAPHICS_COMPRESSED_SHA256 = (
    "57367318445ab783ee8b4ff4fd58deb37105e106a70f0608a531a756e9b059e2"
)
GRAPHICS_SHA256 = (
    "1472c4df7436428d41c668fd6ebb21f58c2a13b0876f372fe3f4b5d602aaa256"
)
PALETTE_COMPRESSED_SHA256 = (
    "7aad1ded0576b67924b8a9e6e8f24698b226929839502a3ef16b43dd6821df69"
)
PALETTE_SHA256 = (
    "043a3dbc0b648314d4289bea8eeca660c17085ddd1c2fb225e50ace435f95ab6"
)


class SpriteDefinitionRuntimeChainExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_sprite_definition_runtime_chain import (
            export_sprite_definition_runtime_chain,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "sprite-definition-chain"
        cls.manifest = export_sprite_definition_runtime_chain(
            ROOT,
            cls.output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_exact_tables_and_all_component_lists(self):
        manifest = self.manifest
        self.assertEqual("sprite-definition-assets-v2", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x53F140,
                "gba_address": "0x0853F140",
                "entry_count": 43,
                "entry_size": 8,
                "sha256": PAIR_TABLE_SHA256,
            },
            manifest["pair_table"],
        )
        self.assertEqual(
            {
                "file_offset": 0x53F298,
                "gba_address": "0x0853F298",
                "entry_count": 43,
                "entry_size": 2,
                "sha256": TILE_OFFSET_TABLE_SHA256,
            },
            manifest["tile_offset_table"],
        )
        self.assertEqual(
            COMPONENT_WINDOWS_SHA256,
            manifest["resolved_window_0x28_sha256"],
        )
        self.assertEqual(43, manifest["entry_count"])
        self.assertEqual(45, manifest["component_count"])
        self.assertEqual([37, 38], manifest["multi_component_entry_ids"])
        self.assertEqual(47, len(list(self.output_dir.iterdir())))

    def test_exports_static_lz77_graphics_palette_and_exact_tile_coverage(self):
        resources = self.manifest["static_resources"]
        self.assertEqual(
            {
                "file_offset": 0x12F298,
                "gba_address": "0x0812F298",
                "compressed_size": 745,
                "compressed_sha256": GRAPHICS_COMPRESSED_SHA256,
                "decompressed_size": 1568,
                "decompressed_sha256": GRAPHICS_SHA256,
                "tile_count": 49,
                "output_bin": "sprite-pack-4bpp.bin",
            },
            resources["graphics"],
        )
        self.assertEqual(
            {
                "file_offset": 0x12F584,
                "gba_address": "0x0812F584",
                "compressed_size": 20,
                "compressed_sha256": PALETTE_COMPRESSED_SHA256,
                "decompressed_size": 32,
                "decompressed_sha256": PALETTE_SHA256,
                "color_count": 16,
                "transparent_index": 0,
                "output_bin": "palette-16-bgr555.bin",
            },
            resources["palette"],
        )
        coverage = self.manifest["tile_coverage"]
        self.assertEqual(list(range(49)), coverage["referenced_tile_indices"])
        self.assertEqual([], coverage["missing_tile_indices"])
        self.assertEqual([], coverage["duplicate_tile_indices"])
        self.assertTrue(coverage["all_tiles_referenced_exactly_once"])
        self.assertEqual(
            GRAPHICS_SHA256,
            hashlib.sha256(
                (self.output_dir / "sprite-pack-4bpp.bin").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            PALETTE_SHA256,
            hashlib.sha256(
                (self.output_dir / "palette-16-bgr555.bin").read_bytes()
            ).hexdigest(),
        )

    def test_runtime_tile_offsets_are_the_exact_43_values(self):
        self.assertEqual(
            [
                0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
                25, 26, 27, 28, 29, 30, 31, 32, 33, 34,
                37, 38, 39, 40, 41, 42, 43, 44, 45, 46,
                10, 11, 35, 36, 47, 48, 12, 13, 18, 21,
                22, 23, 24,
            ],
            [entry["tile_base_offset"] for entry in self.manifest["entries"]],
        )

    def test_normal_and_multi_component_descriptors_remain_distinct(self):
        normal = self.manifest["entries"][0]
        self.assertEqual("0x0812F5B0", normal["definition_pointer"])
        self.assertEqual("0x0812F5BC", normal["animation_pointer"])
        self.assertEqual("0x0812F598", normal["component_list_pointer"])
        self.assertEqual(
            [
                {
                    "index": 0,
                    "tile_offset": 0,
                    "flag_02": 0,
                    "flag_03": 0,
                    "horizontal_position_input": 0,
                    "vertical_position_input": 0,
                    "width": 8,
                    "height": 8,
                    "transform_factor_0c": 0x100,
                    "transform_factor_0e": 0x100,
                    "unknown_10_byte": 0xFF,
                    "oam_attribute_byte": 0,
                    "unknown_12": 0,
                    "raw_hex": "00000000000000000800080000010001ff000000",
                }
            ],
            normal["components"],
        )
        self.assertEqual("ffff0000", normal["terminator_raw_hex"])

        wide = self.manifest["entries"][37]
        self.assertEqual("0x0812F7CC", wide["definition_pointer"])
        self.assertEqual("0x0812F7A0", wide["component_list_pointer"])
        self.assertEqual(
            [(0, 8, 8), (1, 32, 8)],
            [
                (
                    component["tile_offset"],
                    component["width"],
                    component["height"],
                )
                for component in wide["components"]
            ],
        )
        narrow = self.manifest["entries"][38]
        self.assertEqual(
            [(0, 8, 8), (1, 16, 8)],
            [
                (
                    component["tile_offset"],
                    component["width"],
                    component["height"],
                )
                for component in narrow["components"]
            ],
        )

    def test_static_loader_and_remaining_runtime_boundary_are_explicit(self):
        runtime = self.manifest["runtime_chain"]
        self.assertEqual("0x08080A48", runtime["static_resource_loader"])
        self.assertEqual("0x0812F298", runtime["graphics_source"])
        self.assertEqual("0x0812F584", runtime["palette_source"])
        self.assertEqual("0x0202CA24", runtime["tile_base_global"])
        self.assertEqual("0x0202CA26", runtime["palette_bank_global"])
        self.assertEqual("0x06010000", runtime["obj_vram_base"])
        self.assertEqual("0x05000200", runtime["obj_palette_base"])
        self.assertEqual(
            "task.tile_base = u16[0x0202CA24] + tile_base_offset[id]",
            runtime["task_tile_base_formula"],
        )
        self.assertEqual(
            "attr2.tile = task.tile_base + component.tile_offset",
            runtime["attr2_tile_formula"],
        )
        self.assertEqual(
            "attr2.palette = u8[0x0202CA26] << 12",
            runtime["attr2_palette_formula"],
        )
        scope = self.manifest["scope"]
        self.assertFalse(scope["pixel_payload_in_pair_table"])
        self.assertTrue(scope["canonical_static_pixels_exported"])
        self.assertTrue(scope["canonical_static_palette_exported"])
        self.assertFalse(scope["runtime_capture_required_for_canonical_assets"])
        self.assertFalse(scope["scene_specific_overwrite_checked"])

    def test_per_id_pngs_reconstruct_component_positions_and_palette(self):
        expected = {
            0: ((8, 8), [0]),
            37: ((40, 8), [13, 14, 15, 16, 17]),
            38: ((24, 8), [18, 19, 20]),
            42: ((8, 8), [24]),
        }
        for entry_id, (size, tile_indices) in expected.items():
            entry = self.manifest["entries"][entry_id]
            asset = entry["asset"]
            self.assertEqual(tile_indices, asset["tile_indices"])
            self.assertEqual(list(size), [asset["width"], asset["height"]])
            with Image.open(self.output_dir / asset["png"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual(size, image.size)
                self.assertEqual(0, image.info["transparency"])

    def test_independent_verifier_rejects_manifest_tampering(self):
        from tools.verify_sprite_definition_runtime_chain import (
            verify_sprite_definition_runtime_chain,
        )

        result = verify_sprite_definition_runtime_chain(ROOT, self.output_dir)
        self.assertEqual([], result["errors"])
        self.assertEqual(43, result["verified_entries"])
        self.assertEqual(45, result["verified_components"])
        self.assertEqual(43, result["verified_assets"])
        self.assertEqual(49, result["verified_tiles"])

        verifier_source = (
            ROOT / "tools/verify_sprite_definition_runtime_chain.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "manifest"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "manifest.json"
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["entries"][37]["components"][1]["width"] = 31
            path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_sprite_definition_runtime_chain(
                ROOT,
                tampered_dir,
            )
            self.assertTrue(
                any(
                    "entries[37].components[1].width" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "binary"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "sprite-pack-4bpp.bin"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            result = verify_sprite_definition_runtime_chain(
                ROOT,
                tampered_dir,
            )
            self.assertTrue(
                any("sprite-pack-4bpp.bin" in error for error in result["errors"]),
                result["errors"],
            )

    def test_exporter_and_verifier_clis_run_from_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "sprite-definition-chain"
            export = subprocess.run(
                [
                    sys.executable,
                    "tools/export_sprite_definition_runtime_chain.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, export.returncode, export.stderr)
            verify = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_sprite_definition_runtime_chain.py",
                    "--root",
                    ".",
                    "--artifact-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, verify.returncode, verify.stderr)
            report = json.loads(verify.stdout)
            self.assertEqual([], report["errors"])


if __name__ == "__main__":
    unittest.main()
