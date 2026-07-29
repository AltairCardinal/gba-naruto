import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.export_battle_effect_affine_runtime import (
    export_battle_effect_affine_runtime,
)
from tools.inspect_mgba_savestate import load_gba_state
from tools.verify_battle_effect_affine_runtime import (
    verify_battle_effect_affine_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "battle-effect-affine-runtime-v1"
RAW = ARTIFACT / "raw"
MIRROR_RAW = ARTIFACT / "mirror-raw"


class BattleEffectAffineRuntimeExportTests(unittest.TestCase):
    def test_exports_hash_bound_runtime_oam_golden(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "artifact"
            manifest = export_battle_effect_affine_runtime(
                ROOT, RAW, MIRROR_RAW, output
            )

            self.assertEqual("battle-effect-affine-runtime-v1", manifest["schema"])
            self.assertEqual(154, manifest["capture"]["original_frame"])
            self.assertEqual(
                "60028c26e1a529c9542b1e9644dcd35d341cfcfe593cde1b3359c1e2817e3c93",
                manifest["capture"]["savestate_sha256"],
            )
            self.assertEqual(
                {
                    "index": 2,
                    "attr0": "0x0550",
                    "attr1": "0x80A0",
                    "attr2": "0x79D8",
                    "position": {"x": 160, "y": 80},
                    "dimensions": {"width": 32, "height": 32},
                    "affine": True,
                    "double_size": False,
                    "matrix_index": 0,
                    "matrix": {"PA": 240, "PB": 0, "PC": 0, "PD": 240},
                    "tile_index": 472,
                    "priority": 2,
                    "palette_bank": 7,
                    "object_mode": "semi_transparent",
                },
                manifest["object"],
            )
            self.assertEqual(
                {
                    "index": 5,
                    "attr0": "0x0550",
                    "attr1": "0x82A0",
                    "attr2": "0x79D8",
                    "position": {"x": 160, "y": 80},
                    "dimensions": {"width": 32, "height": 32},
                    "affine": True,
                    "double_size": False,
                    "matrix_index": 1,
                    "matrix": {"PA": -240, "PB": 0, "PC": 0, "PD": 240},
                    "tile_index": 472,
                    "priority": 2,
                    "palette_bank": 7,
                    "object_mode": "semi_transparent",
                },
                manifest["mirror_capture"]["object"],
            )
            self.assertEqual("0x03005940", manifest["mirror_capture"]["task_address"])
            self.assertEqual("0xC000B681", manifest["mirror_capture"]["patched_flags"])
            self.assertEqual(2, manifest["mirror_capture"]["capture_frame"])
            self.assertTrue(manifest["mirror_capture"]["audit_success"])
            binding = manifest["resource_binding"]
            self.assertEqual(2, binding["group_id"])
            self.assertTrue(binding["vram_tiles_match_rom"])
            self.assertTrue(binding["pram_palette_matches_rom"])
            self.assertTrue(binding["runtime_pixels_match_source_model"])
            self.assertEqual(
                "0fc78c8d612c9307624420bb276dd35c3dc4396761bddfd0703cd4a62fe375f1",
                binding["runtime_pixel_sha256"],
            )
            self.assertEqual(
                {
                    "frame_start": 152,
                    "frame_end": 179,
                    "frame_count": 28,
                    "affine_component_instances": 44,
                    "matrix_counts": [
                        {
                            "matrix": {
                                "PA": 240,
                                "PB": 0,
                                "PC": 0,
                                "PD": 240,
                            },
                            "component_instances": 44,
                        }
                    ],
                },
                manifest["sequence_coverage"],
            )
            self.assertEqual(46, manifest["artifact_file_count"])
            with Image.open(output / "runtime-object-02.png") as image:
                self.assertEqual((32, 32), image.size)
                self.assertEqual("P", image.mode)
            with Image.open(output / "runtime-object-mirrored.png") as image:
                self.assertEqual((32, 32), image.size)
                self.assertEqual("P", image.mode)
            with Image.open(output / "raw" / "state-0154.png") as image:
                self.assertEqual((240, 160), image.size)

    def test_tracked_artifact_verifies_without_original_build_directory(self):
        result = verify_battle_effect_affine_runtime(ROOT, ARTIFACT)
        self.assertEqual(
            {
                "errors": [],
                "verified_object_count": 2,
                "verified_runtime_frame": 154,
            },
            result,
        )

    def test_mirrored_checkpoint_contains_the_persisted_gpu_golden(self):
        state = load_gba_state(MIRROR_RAW / "mirrored.ss9")

        self.assertEqual(
            state.read_memory(0x07000000, 0x400),
            (MIRROR_RAW / "oam.bin").read_bytes(),
        )
        self.assertEqual(
            state.read_memory(0x05000000, 0x400),
            (MIRROR_RAW / "pram.bin").read_bytes(),
        )
        self.assertEqual(
            state.read_memory(0x06000000, 0x18000),
            (MIRROR_RAW / "vram.bin").read_bytes(),
        )

    def test_scope_closes_mirror_without_overclaiming_physical_hardware(self):
        manifest = export_battle_effect_affine_runtime(
            ROOT, RAW, MIRROR_RAW, None
        )
        self.assertEqual(
            {
                "normal_runtime_oam_golden_complete": True,
                "mirror_runtime_oam_golden_complete": True,
                "physical_gba_capture_complete": False,
                "full_screen_composition_complete": False,
            },
            manifest["scope"],
        )

    def test_independent_verifier_rejects_matrix_manifest_tampering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            path = artifact / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["object"]["matrix"]["PA"] = 239
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            result = verify_battle_effect_affine_runtime(ROOT, artifact)
            self.assertIn("object manifest mismatch", result["errors"])


if __name__ == "__main__":
    unittest.main()
