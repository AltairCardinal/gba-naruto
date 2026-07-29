#!/usr/bin/env python3
"""ROM-backed timelines and editor composites for all 24 story scenes."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONFIG_IDS = [
    4, 10, 14, 24, 17, 18, 21, 25, 29, 28, 34, 76,
    30, 47, 48, 49, 51, 52, 58, 61, 74, 16, 77, 5,
]


class StorySceneTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_story_scene_timelines import (
            export_story_scene_timelines,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "timelines"
        cls.manifest = export_story_scene_timelines(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_all_story_rows_with_exact_controller_phases(self):
        self.assertEqual("story-scene-timelines-v1", self.manifest["schema"])
        self.assertEqual(24, self.manifest["timeline_count"])
        self.assertEqual(
            CONFIG_IDS,
            [item["config_id"] for item in self.manifest["timelines"]],
        )
        self.assertEqual(
            {
                "installer_prelude_frames": 21,
                "installer_internal_update_ticks": 16,
                "controller_update_ticks": 90,
                "linked_update_ticks": 106,
                "palette_transform_frames": 16,
                "overlay_visible_frames": 240,
                "total_wall_frames": 383,
                "overlay_first_wall_frame": 144,
            },
            self.manifest["controller_timing"],
        )

    def test_records_every_linked_tick_and_actual_callback_family(self):
        by_config = {
            item["config_id"]: item for item in self.manifest["timelines"]
        }
        expected_modes = {
            4: "resource_swap_scroll",
            10: "alpha_enable_and_palette",
            17: "secondary_x_motion",
            61: "alpha_enable",
            74: "alpha_enable",
            16: "d_bg_flicker",
        }
        self.assertEqual(
            expected_modes,
            {
                config_id: item["callback_mode"]
                for config_id, item in by_config.items()
                if item["callback_mode"] != "common_only"
            },
        )
        for item in self.manifest["timelines"]:
            timeline_path = self.output_dir / item["timeline_json"]
            payload = json.loads(timeline_path.read_text(encoding="utf-8"))
            self.assertEqual(list(range(1, 107)), [
                state["linked_tick"] for state in payload["linked_ticks"]
            ])
            self.assertEqual(106, payload["linked_ticks"][-1]["task_counter"])
            self.assertEqual(
                383,
                payload["phases"][-1]["end_wall_frame"],
            )

    def test_closes_runtime_enable_and_resource_switch_facts(self):
        by_config = {
            item["config_id"]: item for item in self.manifest["timelines"]
        }
        self.assertEqual(32, by_config[10]["d_first_enabled_tick"])
        self.assertEqual(32, by_config[61]["d_first_enabled_tick"])
        self.assertEqual(32, by_config[74]["d_first_enabled_tick"])
        self.assertEqual(
            {
                "modulus": 4,
                "enabled_residues": [2],
                "disabled_residues": [0],
            },
            by_config[16]["d_flicker_task_counter_modulo"],
        )
        self.assertEqual(50, by_config[4]["c_resource_switch_tick"])
        self.assertEqual("D", by_config[4]["c_resource_after_switch"])

    def test_config_10_palette_brighten_uses_rom_phase_times_two(self):
        item = next(
            item
            for item in self.manifest["timelines"]
            if item["config_id"] == 10
        )
        payload = json.loads(
            (self.output_dir / item["timeline_json"]).read_text(
                encoding="utf-8"
            )
        )
        by_tick = {
            state["linked_tick"]: state for state in payload["linked_ticks"]
        }
        # 0x08098AA0..0x08098AB8 truncates phase to 0..7, then the
        # callback's lsl #17 supplies phase*2 to all three BGR channels.
        self.assertEqual(0, by_tick[48]["d_palette_brighten"])
        self.assertEqual(2, by_tick[56]["d_palette_brighten"])
        self.assertEqual(14, by_tick[106]["d_palette_brighten"])
        self.assertEqual(
            "6d9528a515f46794bc96b359c61134813ead82cf6e748f9962cbe552b4961498",
            item["contact_sheet_png_sha256"],
        )

    def test_writes_editor_contact_sheets_and_semantic_hashes(self):
        for item in self.manifest["timelines"]:
            image_path = self.output_dir / item["contact_sheet_png"]
            with Image.open(image_path) as image:
                self.assertEqual((1200, 190), image.size)
                self.assertEqual("RGBA", image.mode)
            self.assertEqual(64, len(item["contact_sheet_png_sha256"]))
            self.assertEqual(64, len(item["timeline_json_sha256"]))

    def test_verifier_rejects_valid_json_semantic_tampering(self):
        from tools.verify_story_scene_timelines import (
            verify_story_scene_timelines,
        )

        result = verify_story_scene_timelines(ROOT, self.output_dir)
        self.assertEqual("story-scene-timelines-verification-v1", result["schema"])
        self.assertEqual(24, result["verified_timelines"])
        self.assertEqual([], result["errors"])

        manifest_path = self.output_dir / "manifest.json"
        original = manifest_path.read_bytes()
        tampered = json.loads(original)
        tampered["controller_timing"]["linked_update_ticks"] = 90
        tampered["timelines"][1]["d_first_enabled_tick"] = None
        try:
            manifest_path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_story_scene_timelines(ROOT, self.output_dir)
        finally:
            manifest_path.write_bytes(original)
        self.assertIn(
            "manifest does not match ROM-derived timelines",
            result["errors"],
        )

    def test_verifier_rejects_timeline_schema_tampering_with_updated_hash(self):
        from tools.verify_story_scene_timelines import (
            verify_story_scene_timelines,
        )

        manifest_path = self.output_dir / "manifest.json"
        timeline_path = self.output_dir / self.manifest["timelines"][0][
            "timeline_json"
        ]
        original_manifest = manifest_path.read_bytes()
        original_timeline = timeline_path.read_bytes()
        tampered_manifest = json.loads(original_manifest)
        tampered_timeline = json.loads(original_timeline)
        tampered_timeline["linked_ticks"][0]["wall_frame"] = 999
        tampered_timeline["phases"][0]["end_wall_frame"] = 20
        tampered_bytes = (
            json.dumps(tampered_timeline, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        tampered_manifest["timelines"][0]["timeline_json_sha256"] = (
            hashlib.sha256(tampered_bytes).hexdigest()
        )
        try:
            timeline_path.write_bytes(tampered_bytes)
            manifest_path.write_text(
                json.dumps(
                    tampered_manifest,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            result = verify_story_scene_timelines(ROOT, self.output_dir)
        finally:
            timeline_path.write_bytes(original_timeline)
            manifest_path.write_bytes(original_manifest)
        self.assertIn(
            f"{timeline_path.name} wall frame sequence mismatch",
            result["errors"],
        )
        self.assertIn(
            f"{timeline_path.name} phase schedule mismatch",
            result["errors"],
        )

    def test_verifier_rejects_png_and_file_set_tampering(self):
        from tools.verify_story_scene_timelines import (
            verify_story_scene_timelines,
        )

        contact_path = self.output_dir / self.manifest["timelines"][0][
            "contact_sheet_png"
        ]
        unexpected_path = self.output_dir / "unexpected.tmp"
        original_contact = contact_path.read_bytes()
        try:
            contact_path.write_bytes(original_contact + b"tamper")
            unexpected_path.write_bytes(b"unexpected")
            result = verify_story_scene_timelines(ROOT, self.output_dir)
        finally:
            contact_path.write_bytes(original_contact)
            unexpected_path.unlink(missing_ok=True)
        self.assertIn(
            f"{contact_path.name} hash mismatch",
            result["errors"],
        )
        self.assertIn(
            f"{contact_path.name} composite rebuild mismatch",
            result["errors"],
        )
        self.assertIn(
            "artifact file set does not match manifest",
            result["errors"],
        )

    def test_verifier_checks_palette_formula_outside_rebuild(self):
        from tools.verify_story_scene_timelines import (
            verify_story_scene_timelines,
        )

        manifest_path = self.output_dir / "manifest.json"
        item = next(
            item
            for item in self.manifest["timelines"]
            if item["config_id"] == 10
        )
        timeline_path = self.output_dir / item["timeline_json"]
        original_manifest = manifest_path.read_bytes()
        original_timeline = timeline_path.read_bytes()
        tampered_manifest = json.loads(original_manifest)
        tampered_timeline = json.loads(original_timeline)
        tampered_timeline["linked_ticks"][105]["d_palette_brighten"] = 7
        tampered_bytes = (
            json.dumps(tampered_timeline, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        manifest_item = next(
            entry
            for entry in tampered_manifest["timelines"]
            if entry["config_id"] == 10
        )
        manifest_item["timeline_json_sha256"] = hashlib.sha256(
            tampered_bytes
        ).hexdigest()
        try:
            timeline_path.write_bytes(tampered_bytes)
            manifest_path.write_text(
                json.dumps(
                    tampered_manifest,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            result = verify_story_scene_timelines(ROOT, self.output_dir)
        finally:
            timeline_path.write_bytes(original_timeline)
            manifest_path.write_bytes(original_manifest)
        self.assertIn(
            f"{timeline_path.name} tick 106 D palette brighten mismatch",
            result["errors"],
        )

    def test_cli_and_committed_artifact_repeat_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timelines"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_story_scene_timelines.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("24 story scene timelines", completed.stdout)
            self.assertEqual(
                (self.output_dir / "manifest.json").read_bytes(),
                (output / "manifest.json").read_bytes(),
            )
            committed = ROOT / "artifacts/story-scene-timelines-v1"
            self.assertEqual(
                (self.output_dir / "manifest.json").read_bytes(),
                (committed / "manifest.json").read_bytes(),
            )
            for item in self.manifest["timelines"]:
                for key in ("timeline_json", "contact_sheet_png"):
                    self.assertEqual(
                        (self.output_dir / item[key]).read_bytes(),
                        (committed / item[key]).read_bytes(),
                    )


if __name__ == "__main__":
    unittest.main()
