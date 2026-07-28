#!/usr/bin/env python3
"""ROM-backed tests for the complete battle-effect resource-pair export."""

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
TABLE_SHA256 = "7d9f94e05b975940bd2e17f55681120782cb7b6f07d0ab6245adef7260d24130"


class BattleEffectResourcePairExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_resource_pairs import (
            export_battle_effect_resource_pairs,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "battle-effect-resources"
        cls.manifest = export_battle_effect_resource_pairs(
            ROOT,
            cls.output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_complete_hash_bound_table(self):
        manifest = self.manifest
        self.assertEqual("battle-effect-resource-pairs-v1", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x59911C,
                "gba_address": "0x0859911C",
                "entry_count": 19,
                "entry_size": 8,
                "valid_group_ids": list(range(1, 19)),
                "sha256": TABLE_SHA256,
            },
            manifest["resource_pair_table"],
        )
        self.assertEqual(18, manifest["valid_resource_pair_count"])
        self.assertEqual(18, len(manifest["entries"]))
        self.assertEqual(55, len(list(self.output_dir.iterdir())))

    def test_preserves_exact_pointer_pairs_and_resource_sizes(self):
        self.assertEqual(
            [
                ("0x083406F0", "0x083409D0"),
                ("0x08340AF8", "0x08341FA8"),
                ("0x08340AF8", "0x08342340"),
                ("0x083426D8", "0x08342898"),
                ("0x08342938", "0x08342DC8"),
                ("0x0834311C", "0x0834330C"),
                ("0x08343760", "0x08343A5C"),
                ("0x08343D88", "0x083442A0"),
                ("0x08344580", "0x083447AC"),
                ("0x08344E18", "0x08344F04"),
                ("0x0834529C", "0x08345484"),
                ("0x08345568", "0x083459BC"),
                ("0x08345AC8", "0x08345CF4"),
                ("0x08345E64", "0x083466C0"),
                ("0x08346918", "0x08346F30"),
                ("0x0834716C", "0x0834747C"),
                ("0x0834754C", "0x083475B4"),
                ("0x083478F4", "0x083480C8"),
            ],
            [
                (entry["graphics"]["gba_address"], entry["palette"]["gba_address"])
                for entry in self.manifest["entries"]
            ],
        )
        self.assertEqual(
            [
                1024,
                9728,
                9728,
                2048,
                3840,
                960,
                1024,
                2304,
                1024,
                768,
                1664,
                2176,
                1952,
                5120,
                3584,
                2560,
                256,
                3584,
            ],
            [entry["graphics"]["decompressed_size"] for entry in self.manifest["entries"]],
        )
        self.assertTrue(
            all(
                entry["palette"]["decompressed_size"] == 32
                for entry in self.manifest["entries"]
            )
        )

    def test_all_binary_and_png_assets_are_rom_exact(self):
        for entry in self.manifest["entries"]:
            graphics = entry["graphics"]
            palette = entry["palette"]
            atlas = entry["atlas"]
            self.assertEqual(
                graphics["decompressed_sha256"],
                hashlib.sha256(
                    (self.output_dir / graphics["output_bin"]).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                palette["decompressed_sha256"],
                hashlib.sha256(
                    (self.output_dir / palette["output_bin"]).read_bytes()
                ).hexdigest(),
            )
            with Image.open(self.output_dir / atlas["png"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual(
                    (atlas["width"], atlas["height"]),
                    image.size,
                )
                self.assertEqual(0, image.info["transparency"])

        group_18 = self.manifest["entries"][17]
        self.assertEqual(18, group_18["group_id"])
        self.assertEqual(112, group_18["graphics"]["tile_count"])
        self.assertEqual(
            "9162bda2e90536bbe5982e94b4d4de9b18111538b548137ca057701d36b7bc55",
            group_18["graphics"]["decompressed_sha256"],
        )
        self.assertEqual(
            "d53a7a56bded0b6727002a3fb4ad69454dccee15e8f849ad3a16c3b5639244c1",
            group_18["palette"]["decompressed_sha256"],
        )

    def test_group_17_records_its_actual_eight_tile_row(self):
        group_17 = self.manifest["entries"][16]
        self.assertEqual(8, group_17["graphics"]["tile_count"])
        self.assertEqual(8, group_17["atlas"]["tiles_per_row"])
        self.assertEqual(64, group_17["atlas"]["width"])
        self.assertEqual(
            "GBA 4bpp tiles, row-major, 8 tiles per row",
            group_17["atlas"]["tile_order"],
        )

    def test_verifier_decoders_match_hand_written_gba_fixtures(self):
        from tools.verify_battle_effect_resource_pairs import (
            _atlas_pixels,
            _read_lz77,
        )

        lz77 = bytes.fromhex("10060000104142430002")
        compressed, decompressed = _read_lz77(lz77, 0)
        self.assertEqual(lz77, compressed)
        self.assertEqual(b"ABCABC", decompressed)

        graphics = bytes.fromhex("10325476") + bytes(28)
        pixels, width, height, tiles_per_row = _atlas_pixels(graphics)
        self.assertEqual((8, 8, 1), (width, height, tiles_per_row))
        self.assertEqual(bytes(range(8)), pixels[:8])
        self.assertEqual(bytes(56), pixels[8:])

    def test_scope_does_not_overclaim_sequence_or_timing_semantics(self):
        self.assertEqual(
            {
                "canonical_static_graphics_exported": True,
                "canonical_static_palettes_exported": True,
                "resource_group_to_sequence_mapping_complete": False,
                "oam_composition_complete": False,
                "frame_hold_timing_complete": False,
                "audio_binding_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_rejects_manifest_and_binary_tampering(self):
        from tools.verify_battle_effect_resource_pairs import (
            verify_battle_effect_resource_pairs,
        )

        result = verify_battle_effect_resource_pairs(ROOT, self.output_dir)
        self.assertEqual([], result["errors"])
        self.assertEqual(18, result["verified_resource_pairs"])
        self.assertEqual(18, result["verified_atlases"])

        verifier_source = (
            ROOT / "tools/verify_battle_effect_resource_pairs.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "manifest"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "manifest.json"
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["entries"][5]["graphics"]["decompressed_size"] += 32
            path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_resource_pairs(ROOT, tampered_dir)
            self.assertTrue(
                any(
                    "entries[5].graphics.decompressed_size" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "binary"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "group-18-graphics-4bpp.bin"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            result = verify_battle_effect_resource_pairs(ROOT, tampered_dir)
            self.assertTrue(
                any("group-18-graphics-4bpp.bin" in error for error in result["errors"]),
                result["errors"],
            )

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "png"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "group-17-atlas.png"
            with Image.open(path) as image:
                image.load()
                image.putpixel((0, 0), (image.getpixel((0, 0)) + 1) & 0x0F)
                image.save(path, transparency=0)
            result = verify_battle_effect_resource_pairs(ROOT, tampered_dir)
            self.assertTrue(
                any("group-17-atlas.png" in error for error in result["errors"]),
                result["errors"],
            )

    def test_cli_export_is_deterministic_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "export"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/export_battle_effect_resource_pairs.py"),
                    "--root",
                    str(ROOT),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                cwd=ROOT,
            )
            first = (output_dir / "manifest.json").read_bytes()
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/export_battle_effect_resource_pairs.py"),
                    "--root",
                    str(ROOT),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                cwd=ROOT,
            )
            self.assertEqual(first, (output_dir / "manifest.json").read_bytes())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_battle_effect_resource_pairs.py"),
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
