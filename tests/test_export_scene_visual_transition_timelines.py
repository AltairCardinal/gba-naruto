from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SceneVisualTransitionTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_scene_visual_transition_timelines import (
            export_scene_visual_transition_timelines,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = (
            Path(cls.temporary.name) / "scene-visual-transition-timelines-v1"
        )
        cls.payload = export_scene_visual_transition_timelines(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _resign_payload(self, output, payload):
        payload_path = output / "scene-visual-transition-timelines.json"
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload_hash = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["payload_sha256"] = payload_hash
        manifest["files"][payload_path.name] = payload_hash
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _resign_archive_and_payload(self, output, payload):
        archive = output / payload["frame_archive"]["file"]
        archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        payload["frame_archive"]["sha256"] = archive_hash
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][archive.name] = archive_hash
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._resign_payload(output, payload)

    def test_separates_403_background_writes_from_521_task_witnesses(
        self,
    ):
        summary = self.payload["summary"]
        self.assertEqual(8, summary["main_background_track_count"])
        self.assertEqual(1, summary["exit_background_track_count"])
        self.assertEqual(342, summary["main_background_scroll_write_count"])
        self.assertEqual(61, summary["exit_background_scroll_write_count"])
        self.assertEqual(403, summary["background_scroll_write_count"])
        self.assertEqual(15, summary["main_task_track_count"])
        self.assertEqual(1, summary["exit_task_track_count"])
        self.assertEqual(521, summary["task_callback_witness_state_count"])
        self.assertEqual(924, summary["archive_entry_count"])
        self.assertEqual(
            [39, 43, 41, 47, 45, 37, 43, 47, 61],
            [
                track["state_count"]
                for track in self.payload["background_scroll_tracks"]
            ],
        )

    def test_main_background_scrolls_before_spawning_any_obj(self):
        track = self.payload["background_scroll_tracks"][0]
        self.assertEqual("main_background", track["kind"])
        self.assertEqual([152, 0], track["states"][0]["background_scroll"])
        self.assertEqual("state_0_initial_scroll_write", track["states"][0]["handler"])
        self.assertEqual(1, track["states"][0]["controller_dispatch_number"])
        self.assertEqual(0, track["states"][0]["write_order_in_dispatch"])
        self.assertEqual([], track["states"][0]["obj_placements"])
        self.assertEqual([], track["states"][0]["spawned_tasks"])
        self.assertEqual([148, 0], track["states"][1]["background_scroll"])
        self.assertEqual("state_0_fallthrough_state_1", track["states"][1]["handler"])
        self.assertEqual(1, track["states"][1]["controller_dispatch_number"])
        self.assertEqual(1, track["states"][1]["write_order_in_dispatch"])
        self.assertEqual([0, 0], track["states"][-1]["background_scroll"])
        self.assertEqual([], track["states"][-1]["obj_placements"])
        self.assertEqual(
            [
                {"task_index": 0, "counter": 0, "position": [192, -160]},
                {"task_index": 1, "counter": 1, "position": [160, 240]},
            ],
            track["states"][-1]["spawned_tasks"],
        )
        self.assertTrue(track["states"][-1]["spawner_called"])

    def test_exit_background_scrolls_before_spawning_any_obj(self):
        track = self.payload["background_scroll_tracks"][-1]
        self.assertEqual("exit_background", track["kind"])
        self.assertEqual([-40, -240], track["states"][0]["background_scroll"])
        self.assertEqual("state_10", track["states"][0]["handler"])
        self.assertEqual([], track["states"][0]["obj_placements"])
        self.assertEqual([], track["states"][0]["spawned_tasks"])
        self.assertEqual([-40, -236], track["states"][1]["background_scroll"])
        self.assertEqual("state_11", track["states"][1]["handler"])
        self.assertEqual([-40, 0], track["states"][-1]["background_scroll"])
        self.assertEqual([], track["states"][-1]["obj_placements"])
        self.assertEqual(
            [{"task_index": 0, "counter": 0, "position": [240, 128]}],
            track["states"][-1]["spawned_tasks"],
        )

    def test_task_motion_is_independent_and_stops_writing_after_counter_31(self):
        first = self.payload["task_callback_tracks"][0]
        self.assertEqual("main_task", first["kind"])
        self.assertEqual(0, first["task_index"])
        self.assertEqual(33, first["state_count"])
        self.assertEqual(0, first["states"][0]["counter"])
        self.assertFalse(first["states"][0]["callback_executed"])
        self.assertEqual([192, -160], first["states"][0]["position"])
        self.assertEqual(31, first["states"][-2]["counter"])
        self.assertTrue(first["states"][-2]["position_written"])
        self.assertEqual([192, 10], first["states"][-2]["position"])
        self.assertEqual(32, first["states"][-1]["counter"])
        self.assertFalse(first["states"][-1]["position_written"])
        self.assertTrue(first["states"][-1]["first_stable_callback"])
        self.assertEqual(first["states"][-2]["position"], first["states"][-1]["position"])

        second = self.payload["task_callback_tracks"][1]
        self.assertEqual(1, second["task_index"])
        self.assertEqual(32, second["state_count"])
        self.assertEqual(1, second["states"][0]["counter"])
        self.assertEqual([160, 240], second["states"][0]["position"])
        self.assertEqual(32, second["states"][-1]["counter"])

        exit_track = self.payload["task_callback_tracks"][-1]
        self.assertEqual("exit_task", exit_track["kind"])
        self.assertEqual([240, 128], exit_track["states"][0]["position"])
        self.assertEqual([85, 128], exit_track["states"][-2]["position"])
        self.assertEqual(exit_track["states"][-2]["position"], exit_track["states"][-1]["position"])

    def test_records_finite_holds_without_claiming_external_wait_or_scheduler(self):
        controller = self.payload["controller_model"]
        self.assertEqual(64, controller["state_2_hold"]["callback_count"])
        self.assertEqual(64, controller["state_2_hold"]["transition_counter"])
        self.assertEqual(212, controller["state_20_hold"]["callback_count"])
        self.assertEqual(212, controller["state_20_hold"]["exit_counter"])
        self.assertEqual("external_global_equals_2", controller["state_3_wait"]["condition"])

        scope = self.payload["scope"]
        self.assertTrue(scope["background_pre_spawn_order_complete"])
        self.assertTrue(scope["finite_task_position_writes_complete"])
        self.assertTrue(scope["state_2_and_state_20_counter_bounds_complete"])
        self.assertFalse(scope["full_controller_timeline_complete"])
        self.assertFalse(scope["cross_task_scheduler_order_complete"])
        self.assertFalse(scope["vblank_or_wall_frame_timing_complete"])
        self.assertFalse(scope["runtime_pixel_equivalence"])

    def test_repeated_export_is_byte_identical(self):
        from tools.export_scene_visual_transition_timelines import (
            export_scene_visual_transition_timelines,
        )

        repeated = Path(self.temporary.name) / "repeated"
        export_scene_visual_transition_timelines(ROOT, repeated)
        for name in (
            "frames.zip",
            "scene-visual-transition-timelines.json",
            "manifest.json",
        ):
            self.assertEqual(
                (self.output / name).read_bytes(),
                (repeated / name).read_bytes(),
                name,
            )

    def test_archive_is_canonical_and_has_one_png_per_record(self):
        archive = self.output / self.payload["frame_archive"]["file"]
        self.assertEqual(
            self.payload["frame_archive"]["sha256"],
            hashlib.sha256(archive.read_bytes()).hexdigest(),
        )
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(b"", bundle.comment)
            infos = bundle.infolist()
            self.assertEqual(924, len(infos))
            self.assertEqual(924, len({info.filename for info in infos}))
            for info in infos:
                self.assertEqual((1980, 1, 1, 0, 0, 0), info.date_time)
                self.assertEqual(zipfile.ZIP_STORED, info.compress_type)
                self.assertEqual(3, info.create_system)
                self.assertEqual(0o100644 << 16, info.external_attr)
                self.assertEqual(b"", info.extra)
                self.assertEqual(b"", info.comment)
                self.assertEqual(b"\x89PNG\r\n\x1a\n", bundle.read(info)[:8])

    def test_independent_verifier_accepts_and_rejects_resigned_semantic_tamper(self):
        from tools.verify_scene_visual_transition_timelines import (
            verify_scene_visual_transition_timelines,
        )

        report = verify_scene_visual_transition_timelines(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(924, report["archive_entry_count"])

        tampered = Path(self.temporary.name) / "tampered-semantic"
        shutil.copytree(self.output, tampered)
        payload = json.loads(
            (tampered / "scene-visual-transition-timelines.json").read_text()
        )
        payload["background_scroll_tracks"][0]["states"][0][
            "spawner_called"
        ] = True
        self._resign_payload(tampered, payload)
        report = verify_scene_visual_transition_timelines(ROOT, tampered)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("controller background records mismatch" in error for error in report["errors"]),
            report["errors"],
        )

    def test_independent_verifier_rejects_resigned_zip_metadata_tamper(self):
        from tools.verify_scene_visual_transition_timelines import (
            verify_scene_visual_transition_timelines,
        )

        tampered = Path(self.temporary.name) / "tampered-zip"
        shutil.copytree(self.output, tampered)
        payload = json.loads(
            (tampered / "scene-visual-transition-timelines.json").read_text()
        )
        archive = tampered / payload["frame_archive"]["file"]
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.comment = b"resigned metadata tamper"
        self._resign_archive_and_payload(tampered, payload)
        report = verify_scene_visual_transition_timelines(ROOT, tampered)
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("archive comment mismatch" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
