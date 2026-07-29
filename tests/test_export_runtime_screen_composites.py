import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportRuntimeScreenCompositesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_runtime_screen_composites import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.data = export_artifact(ROOT, cls.output)
        cls.promotion = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_all_serialized_gpu_domains_and_exactness(self):
        self.assertEqual("runtime-screen-composites-v1", self.data["schema"])
        self.assertEqual(91, self.data["summary"]["checkpoint_count"])
        self.assertEqual(89, self.data["summary"]["exact_rgb_count"])
        self.assertEqual(2, self.data["summary"]["screenshot_phase_mismatch_count"])
        self.assertEqual(0, self.data["summary"]["unexplained_mismatch_count"])
        self.assertEqual(1211, self.data["summary"]["active_oam_count"])
        self.assertEqual(91, self.data["summary"]["archive_member_count"])
        self.assertEqual(2, self.data["summary"]["affine_runtime_golden_count"])
        self.assertEqual(91, len(self.data["checkpoints"]))
        for row in self.data["checkpoints"]:
            self.assertEqual("hardware-oam-0x07000000", row["oam_input_domain"])
            expected_addresses = {
                "io": "0x04000000",
                "pram": "0x05000000",
                "vram": "0x06000000",
                "hardware_oam": "0x07000000",
                "shadow_oam": "0x0300027C",
            }
            for domain, address in expected_addresses.items():
                self.assertEqual(address, row["domains"][domain]["address"])
                self.assertEqual(64, len(row["domains"][domain]["sha256"]))
            self.assertEqual(64, len(row["rendered_rgb_sha256"]))
            self.assertEqual(64, len(row["screenshot_rgb_sha256"]))
        self.assertFalse(self.data["scope"]["cross_frame_timing_complete"])
        self.assertFalse(self.data["scope"]["all_game_visual_states_complete"])
        self.assertTrue(
            self.data["scope"][
                "natural_affine_obj_normal_and_mirror_bound_pixels_covered"
            ]
        )
        self.assertTrue(
            self.data["scope"]["synthetic_affine_double_size_covered"]
        )

    def test_binds_normal_and_mirrored_affine_runtime_object_goldens(self):
        goldens = self.data["affine_runtime_goldens"]
        self.assertEqual([2, 5], [row["object_index"] for row in goldens])
        self.assertEqual(
            [240, -240],
            [row["attributes"]["matrix"]["PA"] for row in goldens],
        )
        for row in goldens:
            self.assertTrue(row["attributes"]["affine"])
            self.assertFalse(row["attributes"]["double_size"])
            self.assertTrue(row["rgba_exact"])
            self.assertEqual(
                row["reference_png"]["rgba_sha256"],
                row["rendered_rgba_sha256"],
            )
            self.assertEqual(1, row["isolated_active_oam_count"])
            self.assertEqual(1, row["isolated_affine_oam_count"])

    def test_two_phase_mismatches_are_explicit_cursor_tiles(self):
        mismatches = [
            row for row in self.data["checkpoints"] if not row["rgb_exact"]
        ]
        self.assertEqual(
            [
                ("alternate-character-submenu.ss9", 0x3F4, 0x3FA, 53),
                ("skill-list-pre-controller.ss9", 0x3FA, 0x3F8, 30),
            ],
            [
                (
                    Path(row["path"]).name,
                    row["phase_classification"]["serialized_tile"],
                    row["phase_classification"]["screenshot_exact_tile"],
                    row["differing_pixels"],
                )
                for row in mismatches
            ],
        )
        self.assertTrue(
            all(
                row["phase_classification"]["single_oam_tile_substitution_exact"]
                for row in mismatches
            )
        )
        for row in mismatches:
            phase = row["phase_classification"]
            self.assertEqual(
                "embedded-png-cursor-tile-phase-mismatch",
                phase["classification"],
            )
            self.assertEqual(0, phase["oam_index"])
            self.assertTrue(phase["hardware_shadow_oam_equal"])
            self.assertTrue(phase["all_differences_within_object_rect"])
            self.assertEqual(0, phase["unexplained_difference_count"])
            self.assertEqual(16, len(phase["hardware_oam_entry_hex"]))
            self.assertEqual(
                phase["hardware_oam_entry_hex"],
                phase["shadow_oam_entry_hex"],
            )
            self.assertEqual(
                row["screenshot_rgb_sha256"],
                phase["counterfactual_rendered_rgb_sha256"],
            )

    def test_promotion_and_independent_verifier_accept_artifact(self):
        from tools.verify_runtime_screen_composites import verify_artifact

        self.assertEqual("git-artifact-promotion-v1", self.promotion["schema"])
        self.assertEqual("accepted", self.promotion["artifact_status"])
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(91, report["checkpoint_count"])
        self.assertEqual(89, report["exact_rgb_count"])
        source = (
            ROOT / "tools/verify_runtime_screen_composites.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            data_path = tampered / "runtime-screen-composites.json"
            data = json.loads(data_path.read_text(encoding="utf-8"))
            data["checkpoints"][0]["oam_input_domain"] = "shadow-oam"
            data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])
