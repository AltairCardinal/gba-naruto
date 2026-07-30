import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.export_scene_visual_composites import export_scene_visual_composites
from tools.verify_scene_visual_composites import verify_scene_visual_composites


ROOT = Path(__file__).resolve().parents[1]


class ExportSceneVisualCompositesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.output = Path(self.temporary.name) / "scene-visual-composites-v1"
        export_scene_visual_composites(ROOT, self.output)
        self.payload = json.loads(
            (self.output / "scene-visual-composites.json").read_text()
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _resign_payload(self, payload):
        payload_path = self.output / "scene-visual-composites.json"
        payload_path.write_text(json.dumps(payload, indent=2) + "\n")
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        payload_hash = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest["payload_sha256"] = payload_hash
        manifest["files"]["scene-visual-composites.json"] = payload_hash
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    def test_closes_the_controller_main_and_exit_denominator(self):
        self.assertEqual(
            [
                (0, list(range(4))),
                (1, list(range(8))),
            ],
            [
                (mode["mode"], mode["main_pack_ids"])
                for mode in self.payload["controller_modes"]
            ],
        )
        self.assertEqual(12, len(self.payload["main_composites"]))
        self.assertEqual(2, len(self.payload["exit_composites"]))
        self.assertEqual(
            [(0, 4, 8), (1, 8, 8)],
            [
                (
                    item["mode"],
                    item["obj_pack_id"],
                    item["background_pack_id"],
                )
                for item in self.payload["exit_composites"]
            ],
        )

    def test_records_controller_derived_scroll_and_stable_task_positions(self):
        mode_zero = [
            item
            for item in self.payload["main_composites"]
            if item["mode"] == 0
        ]
        self.assertTrue(
            all(item["background_scroll_pixels"] == [0, 0] for item in mode_zero)
        )
        self.assertEqual(
            [[192, 10], [160, 70]],
            mode_zero[0]["task_positions"],
        )
        self.assertEqual(
            [[192, -160], [160, 240]],
            mode_zero[0]["task_initial_positions"],
        )

        mode_one = [
            item
            for item in self.payload["main_composites"]
            if item["mode"] == 1
        ]
        self.assertEqual(
            [
                item["background_width_pixels"] - 240
                for item in mode_one
            ],
            [item["background_scroll_pixels"][0] for item in mode_one],
        )
        self.assertEqual([[48, 10], [16, 70]], mode_one[0]["task_positions"])
        self.assertEqual(
            [[48, -160], [16, 240]],
            mode_one[0]["task_initial_positions"],
        )

        self.assertTrue(
            all(
                item["background_scroll_pixels"] == [-40, 0]
                and item["task_initial_positions"] == [[240, 128]]
                and item["task_positions"] == [[85, 128]]
                for item in self.payload["exit_composites"]
            )
        )
        self.assertEqual(
            {
                "counter_initial_by_task_index": [0, 1],
                "last_updated_counter": 31,
                "fraction_bits": 12,
                "counter_step_q12": 128,
                "division": "signed_truncate_toward_zero",
            },
            self.payload["motion_model"],
        )

    def test_scope_does_not_claim_transition_frames_or_runtime_equivalence(self):
        scope = self.payload["scope"]
        self.assertTrue(scope["stable_pack_row_bg_obj_layouts_complete"])
        self.assertTrue(scope["bg_obj_priority_order_complete"])
        self.assertFalse(scope["transition_intermediate_frames_complete"])
        self.assertFalse(scope["presentation_overlay_composition_complete"])
        self.assertFalse(scope["window_blend_mosaic_runtime_complete"])
        self.assertFalse(scope["runtime_pixel_equivalence"])
        self.assertNotIn("main_stable_layouts_complete", scope)
        self.assertNotIn("exit_stable_layouts_complete", scope)

    def test_applies_main_and_exit_obj_priority_against_bg0(self):
        self.assertEqual(
            {
                "bg0cnt": "0x4086",
                "background_priority": 2,
                "main_obj_flags": "0xA0",
                "main_obj_priority": 2,
                "exit_obj_flags": "0xE0",
                "exit_obj_priority": 3,
                "equal_priority_rule": "obj_over_bg",
                "obj_tie_rule": "lower_oam_index_in_front",
            },
            self.payload["layering"],
        )
        self.assertTrue(
            all(
                item["background_priority"] == 2
                and item["obj_priority"] == 2
                and all(
                    placement["occluded_by_background_pixel_count"] == 0
                    for placement in item["obj_placements"]
                )
                for item in self.payload["main_composites"]
            )
        )
        self.assertTrue(
            all(
                item["background_priority"] == 2
                and item["obj_priority"] == 3
                and any(
                    placement["occluded_by_background_pixel_count"] > 0
                    for placement in item["obj_placements"]
                )
                for item in self.payload["exit_composites"]
            )
        )

    def test_outputs_exact_240_by_160_composites_and_verifies(self):
        files = [
            item["file"]
            for key in ("main_composites", "exit_composites")
            for item in self.payload[key]
        ]
        self.assertEqual(14, len(files))
        self.assertEqual(14, len(set(files)))
        for relative in files:
            data = (self.output / relative).read_bytes()
            self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])

        report = verify_scene_visual_composites(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(14, report["composite_count"])

    def test_independent_verifier_rejects_resigned_semantic_tamper(self):
        payload = json.loads(
            (self.output / "scene-visual-composites.json").read_text()
        )
        payload["main_composites"][0]["task_positions"][0][0] += 1
        self._resign_payload(payload)

        report = verify_scene_visual_composites(ROOT, self.output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("task positions" in error for error in report["errors"]),
            report["errors"],
        )

    def test_verifier_rejects_resigned_signedness_and_priority_tamper(self):
        payload = json.loads(
            (self.output / "scene-visual-composites.json").read_text()
        )
        payload["controller_modes"][0]["main_task_initial_y"][1] = -16
        payload["layering"]["exit_obj_priority"] = 2
        self._resign_payload(payload)

        report = verify_scene_visual_composites(ROOT, self.output)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any(
                "controller mode declarations" in error
                for error in report["errors"]
            ),
            report["errors"],
        )
        self.assertTrue(
            any("layering model" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
