#!/usr/bin/env python3
"""ROM-backed evidence for the 43 generic sprite definition pairs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
        self.assertEqual("sprite-definition-runtime-chain-v1", manifest["schema"])
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
        self.assertEqual(1, len(list(self.output_dir.iterdir())))

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

    def test_runtime_formula_and_unresolved_pixel_boundary_are_explicit(self):
        runtime = self.manifest["runtime_chain"]
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
        self.assertFalse(scope["runtime_pixels_exported"])
        self.assertTrue(scope["obj_vram_capture_required"])
        self.assertTrue(scope["obj_palette_capture_required"])

    def test_independent_verifier_rejects_manifest_tampering(self):
        from tools.verify_sprite_definition_runtime_chain import (
            verify_sprite_definition_runtime_chain,
        )

        result = verify_sprite_definition_runtime_chain(ROOT, self.output_dir)
        self.assertEqual([], result["errors"])
        self.assertEqual(43, result["verified_entries"])
        self.assertEqual(45, result["verified_components"])

        path = self.output_dir / "manifest.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["entries"][37]["components"][1]["width"] = 31
        path.write_text(
            json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = verify_sprite_definition_runtime_chain(ROOT, self.output_dir)
        self.assertTrue(
            any("entries[37].components[1].width" in error for error in result["errors"]),
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
