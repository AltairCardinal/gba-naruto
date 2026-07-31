import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportResidualWramTilemapResourceOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_residual_wram_tilemap_resource_ownership import (
            export_artifact,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_all_seven_tilemap_resource_owners(self):
        self.assertEqual(
            {
                "tilemap_source_count": 7,
                "bg_control_complete_count": 7,
                "graphics_ownership_complete_count": 7,
                "palette_ownership_complete_count": 7,
                "remaining_unresolved_count": 0,
            },
            self.payload["summary"],
        )
        self.assertTrue(
            self.payload["scope"]["graphics_and_palette_ownership_complete"]
        )
        self.assertFalse(
            self.payload["scope"][
                "final_screen_pixel_and_timing_equivalence_complete"
            ]
        )
        self.assertEqual([], self.payload["remaining_unresolved"])

    def test_binds_expected_bg_graphics_and_palette_sources(self):
        expected = {
            "0x0834928C": (
                "BG0",
                "0x0006",
                "0x08348F00",
                ((1, "0x0834941C"),),
            ),
            "0x083F1C98": (
                "BG1",
                "0x1F0D",
                "0x085B6880",
                ((8, "0x083F0AF0"),),
            ),
            "0x085B67E0": (
                "BG1",
                "0x1F0D",
                "0x085B6880",
                ((9, "0x083F1E60"),),
            ),
            "0x083F2108": (
                "BG2",
                "0x020F",
                "0x085B6880",
                ((10, "0x083F1F08"),),
            ),
            "0x084634B8": (
                "BG1",
                "0x0105",
                "0x08463688",
                ((12, "0x084638D4"),),
            ),
            "0x0846356C": (
                "BG1",
                "0x0105",
                "0x08463688",
                ((13, "0x084638F4"),),
            ),
            "0x084635D8": (
                "BG1",
                "0x0105",
                "0x08463688",
                ((13, "0x084638F4"),),
            ),
        }
        records = {
            row["tilemap_source_pointer"]: row
            for row in self.payload["ownership_records"]
        }
        self.assertEqual(set(expected), set(records))
        for pointer, (
            bg_name,
            bg_control,
            graphics_source,
            palettes,
        ) in expected.items():
            with self.subTest(pointer=pointer):
                record = records[pointer]
                self.assertEqual(bg_name, record["bg"]["name"])
                self.assertEqual(bg_control, record["bg"]["control_value"])
                self.assertEqual(
                    graphics_source,
                    record["graphics"]["source_pointer"],
                )
                self.assertEqual(
                    palettes,
                    tuple(
                        (row["bank"], row["source_pointer"])
                        for row in record["palettes"]
                    ),
                )

    def test_effective_tiles_are_inside_owned_graphics_load(self):
        for record in self.payload["ownership_records"]:
            with self.subTest(pointer=record["tilemap_source_pointer"]):
                graphics = record["graphics"]
                used = record["effective_tile_index_range"]
                charbase = int(record["bg"]["charbase_address"], 16)
                loaded_at = int(graphics["vram_destination"], 16)
                loaded_end = loaded_at + graphics["decompressed_size"]
                used_start = charbase + used[0] * 32
                used_end = charbase + (used[1] + 1) * 32
                self.assertLessEqual(loaded_at, used_start)
                self.assertLessEqual(used_end, loaded_end)
                self.assertEqual(32, graphics["tile_bytes"])

    def test_payload_and_manifest_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_residual_wram_tilemap_resource_ownership.py",
                    "--root",
                    ".",
                    "--output",
                    str(second),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(self._hashes(self.output), self._hashes(second))

    def test_promoted_artifact_passes_independent_verifier(self):
        from tools.verify_residual_wram_tilemap_resource_ownership import (
            verify_artifact,
        )

        verifier_source = (
            ROOT
            / "tools/verify_residual_wram_tilemap_resource_ownership.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_residual_wram_tilemap_resource_ownership",
            verifier_source,
        )
        report = verify_artifact(
            ROOT,
            ROOT
            / "artifacts/residual-wram-tilemap-resource-ownership-v1",
        )
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(7, report["verified_ownership_records"])

    def test_verifier_rejects_rehashed_semantic_tamper(self):
        from tools.verify_residual_wram_tilemap_resource_ownership import (
            verify_artifact,
        )

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "resource-ownership.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["ownership_records"][0]["graphics"][
                "source_pointer"
            ] = "0x083F00C8"
            payload_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            payload_hash = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest["files"][payload_path.name] = payload_hash
            manifest["payload_sha256"] = payload_hash
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_verifier_rejects_rehashed_tilemap_destination_tamper(self):
        from tools.verify_residual_wram_tilemap_resource_ownership import (
            verify_artifact,
        )

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "resource-ownership.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["ownership_records"][0][
                "vram_destination"
            ] = "0x06000020"
            payload_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            payload_hash = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest["files"][payload_path.name] = payload_hash
            manifest["payload_sha256"] = payload_hash
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    @staticmethod
    def _hashes(path: Path):
        return {
            item.relative_to(path).as_posix(): hashlib.sha256(
                item.read_bytes()
            ).hexdigest()
            for item in path.rglob("*")
            if item.is_file()
        }
