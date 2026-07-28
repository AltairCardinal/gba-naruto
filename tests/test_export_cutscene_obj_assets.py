#!/usr/bin/env python3
"""ROM-backed export of the four cutscene OBJ visual bundles."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RESOURCE_TABLE_SHA256 = (
    "16b13c432f37ba159697cd9d9d6d5d5147adc41c44c8cc0cc44ce7f2935f1401"
)
SPRITE_TABLE_SHA256 = (
    "1c76f2100b2067e78abd713e312bd845d7c874b030f51ef08f968961862e198a"
)
COMBINED_TABLE_SHA256 = (
    "1e6d5016b58d0e565c5a40791a7f2684d6129e0a1c4e85e79317af4d2b1a7f62"
)


class CutsceneObjAssetExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_cutscene_obj_assets import (
            export_cutscene_obj_assets,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "cutscene-obj"
        cls.manifest = export_cutscene_obj_assets(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def _resource(self, resource_id: int) -> dict:
        return self.manifest["resources"][resource_id]

    def test_exports_both_exact_tables_and_all_static_frames(self):
        manifest = self.manifest
        self.assertEqual("cutscene-obj-export-v1", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x53DF70,
                "gba_address": "0x0853DF70",
                "entry_count": 4,
                "entry_size": 8,
                "sha256": RESOURCE_TABLE_SHA256,
            },
            manifest["resource_table"],
        )
        self.assertEqual(
            {
                "file_offset": 0x53DF90,
                "gba_address": "0x0853DF90",
                "entry_count": 4,
                "entry_size": 8,
                "sha256": SPRITE_TABLE_SHA256,
            },
            manifest["sprite_table"],
        )
        self.assertEqual(COMBINED_TABLE_SHA256, manifest["combined_table_sha256"])
        self.assertEqual(4, manifest["resource_count"])
        self.assertEqual(10, manifest["frame_count"])
        self.assertEqual(4, manifest["atlas_count"])
        self.assertEqual(1, manifest["unique_palette_count"])
        self.assertEqual([2, 2, 2, 4], manifest["frame_counts"])
        self.assertEqual(4, len(manifest["resources"]))
        self.assertEqual(15, len(list(self.output_dir.iterdir())))

    def test_resource_zero_is_two_complete_64_pixel_frames(self):
        resource = self._resource(0)
        self.assertEqual("0x0812D9E4", resource["gfx_pointer"])
        self.assertEqual("0x0812DEE4", resource["palette_pointer"])
        self.assertEqual("0x0812DF2C", resource["definition_table_pointer"])
        self.assertEqual("0x0812DF44", resource["animation_table_pointer"])
        self.assertEqual(1112, resource["gfx"]["compressed_size"])
        self.assertEqual(
            "f75f0d9d2c1176394672cef9ef68461857897974d594c3a2833ed6b13ecd7ade",
            resource["gfx"]["compressed_sha256"],
        )
        self.assertEqual(4096, resource["gfx"]["decompressed_size"])
        self.assertEqual(
            "ff3e1b090a18378eb51b2c25ad7e9115ea33d6c9afe11ceeb09cbd392a5496c5",
            resource["gfx"]["decompressed_sha256"],
        )
        self.assertEqual(2, resource["frame_count"])
        self.assertEqual((128, 64), (
            resource["atlas"]["width"],
            resource["atlas"]["height"],
        ))
        first, second = resource["frames"]
        self.assertEqual((0, 64), (
            first["tile_offset"],
            second["tile_offset"],
        ))
        for frame in (first, second):
            self.assertEqual((-32, -32), (
                frame["x_offset"],
                frame["y_offset"],
            ))
            self.assertEqual((64, 64), (
                frame["width"],
                frame["height"],
            ))
            self.assertEqual((8, 8), (
                frame["width_tiles"],
                frame["height_tiles"],
            ))
        self.assertEqual([0, 1, 0xFFFF, 0], first["animation_words"])
        self.assertEqual([1, 0, 0xFFFF, 0], second["animation_words"])

    def test_resource_three_is_four_complete_32_pixel_frames(self):
        resource = self._resource(3)
        self.assertEqual("0x0812E9B0", resource["gfx_pointer"])
        self.assertEqual("0x0812ED58", resource["palette_pointer"])
        self.assertEqual("0x0812EDD0", resource["definition_table_pointer"])
        self.assertEqual("0x0812EE00", resource["animation_table_pointer"])
        self.assertEqual(935, resource["gfx"]["compressed_size"])
        self.assertEqual(2048, resource["gfx"]["decompressed_size"])
        self.assertEqual(
            "d2b44e9c68dc23771249bedfb7397de35f19e6769f99a91f86512b7604b43ec1",
            resource["gfx"]["decompressed_sha256"],
        )
        self.assertEqual(4, resource["frame_count"])
        self.assertEqual((128, 32), (
            resource["atlas"]["width"],
            resource["atlas"]["height"],
        ))
        self.assertEqual(
            [0, 16, 32, 48],
            [frame["tile_offset"] for frame in resource["frames"]],
        )
        for index, frame in enumerate(resource["frames"]):
            self.assertEqual((-16, -16), (
                frame["x_offset"],
                frame["y_offset"],
            ))
            self.assertEqual((32, 32), (
                frame["width"],
                frame["height"],
            ))
            self.assertEqual(
                [index, 0 if index else 1, 0xFFFF, 0],
                frame["animation_words"],
            )

    def test_all_palettes_and_raw_definition_records_are_rom_bound(self):
        expected_palette_hash = (
            "99d45ddc5929d60c150146f1292cd55f56d89afbff70ffd0f377128fe75352af"
        )
        expected_gfx_hashes = [
            "ff3e1b090a18378eb51b2c25ad7e9115ea33d6c9afe11ceeb09cbd392a5496c5",
            "1494d4db49423aaf026f3a1d45df4a63c70db9a0c6c7bae72621f7f7688bae0d",
            "ff180630c246cf7c9e161576b33c0e734157a2a927c07be6bc90a80619654079",
            "d2b44e9c68dc23771249bedfb7397de35f19e6769f99a91f86512b7604b43ec1",
        ]
        for resource, expected_gfx_hash in zip(
            self.manifest["resources"],
            expected_gfx_hashes,
            strict=True,
        ):
            self.assertEqual(
                expected_gfx_hash,
                resource["gfx"]["decompressed_sha256"],
            )
            self.assertEqual(22, resource["palette"]["compressed_size"])
            self.assertEqual(32, resource["palette"]["decompressed_size"])
            self.assertEqual(
                expected_palette_hash,
                resource["palette"]["decompressed_sha256"],
            )
            self.assertEqual(
                resource["frame_count"] * 12,
                int(resource["animation_table_pointer"], 16)
                - int(resource["definition_table_pointer"], 16),
            )
            for frame in resource["frames"]:
                self.assertEqual(48, len(frame["definition_raw_hex"]))
                self.assertEqual(16, len(frame["animation_raw_hex"]))
                self.assertEqual(0xFFFF, frame["animation_words"][2])

    def test_outputs_are_indexed_transparent_atlases_and_native_frames(self):
        for resource in self.manifest["resources"]:
            with Image.open(
                self.output_dir / resource["atlas"]["png"]
            ) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual(
                    (resource["atlas"]["width"], resource["atlas"]["height"]),
                    image.size,
                )
                self.assertEqual(0, image.info["transparency"])
            for frame in resource["frames"]:
                with Image.open(self.output_dir / frame["png"]) as image:
                    image.load()
                    self.assertEqual("P", image.mode)
                    self.assertEqual(
                        (frame["width"], frame["height"]),
                        image.size,
                    )
                    self.assertEqual(0, image.info["transparency"])

    def test_independent_verifier_recomputes_every_pixel_and_record(self):
        from tools.verify_cutscene_obj_export import (
            _decode_lz_record,
            verify_cutscene_obj_export,
        )

        self.assertEqual(
            b"ABABAB",
            _decode_lz_record(
                bytes.fromhex("100600002041421001")
            ),
        )
        verifier_source = (
            ROOT / "tools/verify_cutscene_obj_export.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.", verifier_source)
        result = verify_cutscene_obj_export(ROOT, self.output_dir)
        self.assertEqual("cutscene-obj-verification-v1", result["schema"])
        self.assertEqual(4, result["verified_resources"])
        self.assertEqual(10, result["verified_frames"])
        self.assertEqual(4, result["verified_atlases"])
        self.assertEqual([], result["errors"])

    def test_independent_verifier_cli_runs_from_the_repository_root(self):
        completed = subprocess.run(
            [
                sys.executable,
                "tools/verify_cutscene_obj_export.py",
                "--root",
                ".",
                "--artifact-dir",
                str(self.output_dir),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual([], report["errors"])
        self.assertEqual(10, report["verified_frames"])

    def test_independent_verifier_rejects_manifest_semantic_tampering(self):
        from tools.verify_cutscene_obj_export import (
            verify_cutscene_obj_export,
        )

        manifest_path = self.output_dir / "manifest.json"
        original = manifest_path.read_bytes()
        tampered = json.loads(original)
        tampered["frame_count"] = 9
        tampered["resources"][0]["frames"][0]["tile_offset"] = 1
        try:
            manifest_path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_cutscene_obj_export(ROOT, self.output_dir)
        finally:
            manifest_path.write_bytes(original)

        joined = "\n".join(result["errors"])
        self.assertIn("frame_count mismatch", joined)
        self.assertIn(
            "resource 0: resource metadata does not match the ROM",
            joined,
        )

    def test_cli_and_committed_artifacts_repeat_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            cli_output = Path(directory) / "cli"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_cutscene_obj_assets.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(cli_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("10 static OBJ frames", completed.stdout)

            expected_names = {
                path.name
                for path in self.output_dir.iterdir()
                if path.is_file()
            }
            self.assertEqual(
                expected_names,
                {path.name for path in cli_output.iterdir() if path.is_file()},
            )
            for name in expected_names:
                self.assertEqual(
                    (self.output_dir / name).read_bytes(),
                    (cli_output / name).read_bytes(),
                )

            committed = ROOT / "artifacts/cutscene-obj-v1"
            self.assertEqual(
                expected_names,
                {path.name for path in committed.iterdir() if path.is_file()},
            )
            for name in expected_names:
                self.assertEqual(
                    (self.output_dir / name).read_bytes(),
                    (committed / name).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
