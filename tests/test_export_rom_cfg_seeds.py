#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.export_rom_cfg_seeds import _validate_output_dir, export_rom_cfg_seeds
from tools.verify_rom_cfg_seeds import rebuild_cfg_seeds, verify_rom_cfg_seeds


ROOT = Path(__file__).resolve().parents[1]


class RomCfgSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact_dir = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_rom_cfg_seeds(ROOT, cls.artifact_dir)
        cls.payload = json.loads(
            (cls.artifact_dir / "rom-cfg-seeds.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_fixed_dispatch_seed_denominator(self):
        summary = self.payload["summary"]
        self.assertEqual("rom-cfg-seeds-v1", self.payload["schema"])
        self.assertEqual(23, summary["dispatch_source_count"])
        self.assertEqual(18, summary["inline_dispatch_source_count"])
        self.assertEqual(5, summary["canonical_dispatch_source_count"])
        self.assertEqual(829, summary["raw_dispatch_slot_count"])
        self.assertEqual(263, summary["root_seed_count"])
        self.assertEqual(2, summary["arm_root_seed_count"])
        self.assertEqual(261, summary["thumb_root_seed_count"])
        self.assertEqual(261, summary["unique_dispatch_handler_count"])
        self.assertEqual(
            {
                "cfg_traversal_performed": False,
                "enumerated_proven_dispatch_root_denominator_complete": True,
                "global_dispatch_source_denominator_complete": False,
                "global_function_entry_denominator_complete": False,
                "independent_source_discovery_performed": False,
                "unbound_pointer_pools_excluded": True,
            },
            self.payload["scope"],
        )

        self.assertEqual(
            {
                "inline-05": (15, 2),
                "inline-06": (19, 3),
                "inline-07": (22, 4),
                "inline-08": (59, 16),
                "inline-09": (19, 9),
                "inline-10": (55, 6),
                "inline-12": (35, 12),
                "inline-13": (35, 11),
                "inline-15": (19, 5),
                "inline-16": (63, 24),
                "inline-17": (19, 3),
                "inline-18": (23, 4),
                "inline-19": (31, 3),
                "inline-20": (31, 4),
                "inline-22": (36, 13),
                "inline-24": (79, 7),
                "inline-26": (30, 5),
                "inline-27": (15, 15),
                "battle-status-action": (46, 13),
                "battle-effect-subtype": (63, 24),
                "scene-controller": (21, 8),
                "story-opcode": (58, 44),
                "m4a-track-command": (36, 26),
            },
            {
                source["id"]: (
                    source["slot_count"],
                    source["unique_target_count"],
                )
                for source in self.payload["dispatch_sources"]
            },
        )

    def test_seeds_are_unique_aligned_and_provenance_bound(self):
        seeds = self.payload["seeds"]
        self.assertEqual(263, len(seeds))
        self.assertEqual(
            [(0x000000, "arm"), (0x000104, "arm")],
            [
                (seed["file_offset"], seed["mode"])
                for seed in seeds
                if seed["mode"] == "arm"
            ],
        )
        self.assertEqual(
            263,
            len({(seed["file_offset"], seed["mode"]) for seed in seeds}),
        )
        for seed in seeds:
            self.assertEqual(0, seed["file_offset"] & (3 if seed["mode"] == "arm" else 1))
            self.assertTrue(seed["sources"])
            self.assertRegex(seed["entry_sha256"], r"^[0-9a-f]{64}$")

    def test_independent_verifier_rebuilds_all_sources_and_seeds(self):
        report = verify_rom_cfg_seeds(ROOT, self.artifact_dir)
        self.assertEqual(
            {
                "schema": "rom-cfg-seeds-verification-v1",
                "verified": True,
                "dispatch_source_count": 23,
                "raw_dispatch_slot_count": 829,
                "root_seed_count": 263,
                "arm_root_seed_count": 2,
                "thumb_root_seed_count": 261,
                "errors": [],
            },
            report,
        )

    def test_direct_cli_exports_and_verifies_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            exported = subprocess.run(
                [
                    sys.executable,
                    "tools/export_rom_cfg_seeds.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(artifact),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, exported.returncode, exported.stderr)
            verified = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_rom_cfg_seeds.py",
                    "--root",
                    ".",
                    "--artifact-dir",
                    str(artifact),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, verified.returncode, verified.stderr)

    def test_output_validator_refuses_repository_and_foreign_directory(self):
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            _validate_output_dir(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            _validate_output_dir(ROOT, ROOT.parent)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "foreign"
            output.mkdir()
            keep = output / "keep.txt"
            keep.write_text("user data\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replaceable CFG seed artifact"):
                _validate_output_dir(ROOT, output)
            self.assertEqual("user data\n", keep.read_text(encoding="utf-8"))

    def test_exporter_refuses_repository_before_writing(self):
        rom_path = ROOT / "rom/base.gba"
        rom_before = rom_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "repository root or ancestor"):
            export_rom_cfg_seeds(ROOT, ROOT)
        self.assertEqual(rom_before, rom_path.read_bytes())
        self.assertTrue((ROOT / "tools/export_rom_cfg_seeds.py").is_file())

    def test_rebuilder_rejects_dispatch_table_tampering(self):
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x064CA4] ^= 1
        with self.assertRaisesRegex(ValueError, "inline-05 table bytes changed"):
            rebuild_cfg_seeds(ROOT, bytes(rom))

    def test_verifier_rejects_rehashed_seed_or_scope_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(self.artifact_dir, artifact)
            payload_path = artifact / "rom-cfg-seeds.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["seeds"][0]["mode"] = "thumb"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

            manifest["files"]["rom-cfg-seeds.json"]["sha256"] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = verify_rom_cfg_seeds(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
