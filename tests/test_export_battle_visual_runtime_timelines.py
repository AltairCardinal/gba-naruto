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
SENTINEL_IDS = [13, 31, 32, 46]


def directory_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class BattleVisualRuntimeTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_visual_runtime_timelines import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _ticks(self, descriptor_id):
        entry = self.manifest["entries"][descriptor_id]
        payload = json.loads(
            (self.output / entry["timeline_json"]).read_text(encoding="utf-8")
        )
        return {
            tick["linked_tick"]: tick
            for tick in payload["linked_ticks"]
        }

    def test_exports_all_consumers_and_marks_only_true_sentinels_unplayable(self):
        self.assertEqual(
            "battle-visual-runtime-timelines-v1",
            self.manifest["schema"],
        )
        self.assertEqual(79, len(self.manifest["entries"]))
        self.assertEqual(75, self.manifest["summary"]["playable_count"])
        self.assertEqual(SENTINEL_IDS, self.manifest["summary"]["sentinel_ids"])
        for descriptor_id, entry in enumerate(self.manifest["entries"]):
            self.assertEqual(descriptor_id, entry["descriptor_id"])
            self.assertEqual(descriptor_id + 1, entry["consumer_id"])
            if descriptor_id in SENTINEL_IDS:
                self.assertFalse(entry["playable"])
                self.assertIsNone(entry["timeline_json"])
                self.assertIsNone(entry["contact_sheet_png"])
            else:
                self.assertTrue(entry["playable"])
                ticks = self._ticks(descriptor_id)
                self.assertEqual(list(range(1, 107)), list(ticks))

    def test_closes_mode_2_and_mode_3_within_standard_consumer(self):
        mode_2 = self._ticks(0)
        self.assertEqual("paired_x_shake_without_d", mode_2[1]["callback_mode"])
        self.assertEqual(1, mode_2[32]["callback_phase"])
        self.assertEqual(72, mode_2[32]["callback_origin_x"])
        self.assertEqual([70, 0], mode_2[33]["position_pixels"])
        self.assertEqual([14, 0], mode_2[89]["position_pixels"])
        self.assertEqual(255, mode_2[90]["callback_phase"])
        self.assertEqual([0, 0], mode_2[90]["position_pixels"])
        self.assertEqual(0, mode_2[90]["scroll_fixed_8_8"]["C"][0])

        mode_3 = self._ticks(2)
        self.assertEqual("paired_x_shake_then_d", mode_3[1]["callback_mode"])
        self.assertEqual(20, mode_3[90]["callback_phase"])
        self.assertTrue(mode_3[90]["bg_enabled"]["D"])
        self.assertEqual(1, mode_3[90]["runtime_flags"] & 1)
        self.assertEqual(1 << 8, mode_3[91]["scroll_fixed_8_8"]["D"][0])
        self.assertEqual(-16 << 8, mode_3[106]["scroll_fixed_8_8"]["D"][0])

    def test_closes_flag_0100_c_alpha_enable_sequence(self):
        ticks = self._ticks(1)
        self.assertFalse(ticks[16]["bg_enabled"]["C"])
        self.assertTrue(ticks[17]["bg_enabled"]["C"])
        self.assertEqual(
            {
                "mode": "alpha_c_over_b",
                "eva": 0,
                "evb": 16,
                "evy": 0,
            },
            ticks[17]["blend"],
        )
        self.assertIn("cue_137", ticks[8]["events"])
        self.assertEqual(16, ticks[80]["blend"]["eva"])
        self.assertEqual("none", ticks[81]["blend"]["mode"])
        self.assertEqual("0x0000", ticks[81]["registers"]["BLDCNT"])
        self.assertEqual("0x0010", ticks[81]["registers"]["BLDALPHA"])

    def test_records_standard_intro_geometry_and_compact_editor_keyframes(self):
        for entry in self.manifest["entries"]:
            if not entry["playable"]:
                continue
            intro = entry["standard_intro"]
            count = intro["binding_slot_count"]
            self.assertEqual(17, intro["a_scroll_frames"])
            self.assertEqual(8, intro["glyph_pre_delay_frames"])
            self.assertEqual(
                max(0, 6 * count - 1),
                intro["glyph_slot_wait_frames"],
            )
            self.assertEqual(60, intro["glyph_hold_frames"])
            self.assertEqual(
                84 + 6 * count,
                intro["total_before_linked_installer_frames"],
            )
            for slot in intro["glyph_slots"]:
                expected_x = slot["slot"] * 24 - count * 12 + 132
                self.assertEqual(expected_x, slot["x"])
                self.assertEqual(16, slot["y"])
                self.assertEqual(13, slot["palette_bank"])

            image_path = self.output / entry["contact_sheet_png"]
            with Image.open(image_path) as image:
                self.assertEqual((1440, 190), image.size)
                self.assertEqual("RGBA", image.mode)
            self.assertEqual([16, 32, 50, 81, 106], entry["key_ticks"])

    def test_scope_distinguishes_offline_model_from_mgba_pixel_equivalence(self):
        self.assertEqual(
            {
                "standard_consumer_intro_timing_complete": True,
                "message_obj_geometry_complete": True,
                "all_playable_linked_timelines_complete": True,
                "all_callback_modes_within_standard_consumer_complete": True,
                "flag_0100_alpha_sequence_complete": True,
                "offline_keyframe_composites_complete": True,
                "runtime_pixel_equivalence_complete": False,
                "remaining_runtime_validation": [
                    "shadow_register_commit_order",
                    "window_mask_edges",
                    "representative_mgba_golden_frames",
                ],
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_rejects_semantic_and_png_tampering(self):
        from tools.verify_battle_visual_runtime_timelines import verify_artifact

        verifier_source = (
            ROOT / "tools" / "verify_battle_visual_runtime_timelines.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "export_battle_visual_runtime_timelines",
            verifier_source,
        )
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(75, report["verified_timeline_count"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            entry = self.manifest["entries"][0]
            timeline_path = tampered / entry["timeline_json"]
            payload = json.loads(timeline_path.read_text(encoding="utf-8"))
            payload["linked_ticks"][32]["position_pixels"][0] += 1
            timeline_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            image_path = tampered / entry["contact_sheet_png"]
            image_path.write_bytes(image_path.read_bytes() + b"tamper")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(any(
                "timeline semantic mismatch" in error
                for error in report["errors"]
            ))
            self.assertTrue(any(
                "contact sheet" in error
                for error in report["errors"]
            ))

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            manifest_path = tampered / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            image_path = tampered / data["entries"][0]["contact_sheet_png"]
            with Image.open(image_path) as source:
                image = source.convert("RGBA")
            image.putpixel((0, 0), (255, 0, 255, 255))
            image.save(
                image_path,
                format="PNG",
                optimize=False,
                compress_level=9,
            )
            data["entries"][0]["contact_sheet_png_sha256"] = hashlib.sha256(
                image_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(any(
                "contact sheet pixel rebuild mismatch" in error
                for error in report["errors"]
            ))

    def test_verifier_rejects_manifest_contract_tampering(self):
        from tools.verify_battle_visual_runtime_timelines import verify_artifact

        mutations = {
            "source artifact": lambda data: data["source_artifact"].update(
                manifest_sha256="0" * 64
            ),
            "summary": lambda data: data["summary"].update(
                playable_count=74
            ),
            "key ticks": lambda data: data["entries"][0].update(
                key_ticks=[16, 32, 50, 80, 106]
            ),
            "intro summary": lambda data: data["entries"][0][
                "standard_intro"
            ].update(a_scroll_frames=16),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                manifest_path = tampered / "manifest.json"
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(data)
                manifest_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], name)
                self.assertTrue(report["errors"], name)

    def test_cli_runs_from_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_battle_visual_runtime_timelines.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((output / "manifest.json").is_file())

    def test_export_matches_committed_artifact(self):
        self.assertEqual(
            directory_hashes(self.output),
            directory_hashes(
                ROOT / "artifacts/battle-visual-runtime-timelines-v1"
            ),
        )

    def test_tick_payloads_use_compact_deterministic_json(self):
        for entry in self.manifest["entries"]:
            if entry["playable"]:
                payload = (self.output / entry["timeline_json"]).read_bytes()
                self.assertEqual(1, payload.count(b"\n"))


if __name__ == "__main__":
    unittest.main()
