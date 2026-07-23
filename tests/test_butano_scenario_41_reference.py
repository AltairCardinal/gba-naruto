import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.butano import export_scenario_41_reference as reference


ROOT = Path(__file__).resolve().parents[1]


class Scenario41ReferenceTests(unittest.TestCase):
    def test_exports_deterministic_six_boundary_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"

            first_manifest = reference.export_reference(ROOT / "rom/base.gba", first)
            second_manifest = reference.export_reference(ROOT / "rom/base.gba", second)

            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(
                first_manifest["rom_sha256"], reference.EXPECTED_ROM_SHA256
            )
            self.assertEqual(
                set(first_manifest["boundaries"]), set(reference.CHECKPOINTS)
            )
            technique = first_manifest["boundaries"]["first-turn-technique-menu"]
            self.assertEqual(technique["screen"]["width"], 240)
            self.assertEqual(technique["screen"]["height"], 160)
            self.assertEqual(
                technique["screen"]["rgb_pixels_sha256"],
                "17644dae174acd0e26b9b004f3e8a03b9fd9a43b523cb3dff40f978b4f9b6eef",
            )

            for boundary_name, boundary in first_manifest["boundaries"].items():
                for region_name, region in boundary["regions"].items():
                    first_bytes = (first / boundary_name / region["file"]).read_bytes()
                    second_bytes = (second / boundary_name / region["file"]).read_bytes()
                    self.assertEqual(len(first_bytes), reference.REGIONS[region_name][1])
                    self.assertEqual(first_bytes, second_bytes)
                    self.assertEqual(
                        hashlib.sha256(first_bytes).hexdigest(), region["sha256"]
                    )
                self.assertEqual(
                    boundary["unit_pool"]["size"], reference.UNIT_POOL_SIZE
                )

            manifest_bytes = (first / "manifest.json").read_bytes()
            self.assertEqual(
                manifest_bytes,
                (json.dumps(first_manifest, indent=2, sort_keys=True) + "\n").encode(),
            )

    def test_fails_before_creating_output_for_bad_rom_or_checkpoint_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_rom = root / "bad.gba"
            shutil.copyfile(ROOT / "rom/base.gba", bad_rom)
            with bad_rom.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"BAD!")

            bad_rom_output = root / "bad-rom-output"
            with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
                reference.export_reference(bad_rom, bad_rom_output)
            self.assertFalse(bad_rom_output.exists())

            bad_checkpoint = root / "bad.ss9"
            source = ROOT / "artifacts/runtime-checkpoints/scenario-41-player-turn.ss9"
            shutil.copyfile(source, bad_checkpoint)
            with bad_checkpoint.open("ab") as stream:
                stream.write(b"BAD!")
            checkpoints = dict(reference.CHECKPOINTS)
            checkpoints["player-turn"] = reference.Checkpoint(
                bad_checkpoint, checkpoints["player-turn"].sha256
            )
            bad_checkpoint_output = root / "bad-checkpoint-output"
            with mock.patch.object(reference, "CHECKPOINTS", checkpoints):
                with self.assertRaisesRegex(ValueError, "checkpoint SHA-256"):
                    reference.export_reference(
                        ROOT / "rom/base.gba", bad_checkpoint_output
                    )
            self.assertFalse(bad_checkpoint_output.exists())

    def test_refuses_to_overwrite_an_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("user data", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                reference.export_reference(ROOT / "rom/base.gba", output)

            self.assertEqual(marker.read_text(encoding="utf-8"), "user data")


if __name__ == "__main__":
    unittest.main()
