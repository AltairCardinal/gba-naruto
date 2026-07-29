import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportSceneVisualPacksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_scene_visual_packs import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_exact_rom_table_and_consumers(self):
        manifest = self.manifest
        self.assertEqual("scene-visual-packs-v1", manifest["schema"])
        self.assertEqual(
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            manifest["rom"]["sha256"],
        )
        self.assertEqual(
            {
                "gba_address": "0x085A4CE8",
                "entry_count": 9,
                "entry_size": 28,
                "sha256": (
                    "b562062061a088aac2e5ce2f2d9f8bbfd34f0cb53a794a7"
                    "ea5b0f270ecf909b3"
                ),
            },
            manifest["source_table"],
        )
        self.assertEqual(
            {
                "setup_and_initial_row": (
                    "49e5707f975743b374bc93b685bdeb8465674c46b17bf543"
                    "574ed010f318929f"
                ),
                "indexed_row_loader": (
                    "804b19345db90905040aeb7c71e9e5d2464d9ee0fcf821bc"
                    "6f3fc4ceead08f2a"
                ),
                "sprite_spawner": (
                    "3fd57f3a23dd6e1a1c1030f272b0213c596b7c3679069d47"
                    "c0e7b4b82b5b05d3"
                ),
                "sprite_motion_callback": (
                    "ee6f94b5978f5824f37d73b77344cbec1f474c1f6535b846"
                    "9f90e8e910a95515"
                ),
                "presentation_selector": (
                    "ba2a35a498752085f4fbcab7a18667f1cd404199b5278eb4c"
                    "77842ea57c0804e"
                ),
                "controller": (
                    "c515f1996f65fd8c7a73eb86429fc4bd798a62f4b5cad6b3"
                    "6075fb9aba1ac03b"
                ),
                "sprite_task_allocator": (
                    "1b0a793b761f650bfe43d75ad76186c395d6315dd67a130b"
                    "9575184b11ce2f87"
                ),
                "animation_frame_selector": (
                    "d02024aa1d1688f2915f35496f457d5cc4d123b706e98013"
                    "7f9ce3d19e331686"
                ),
                "obj_attr2_writer": (
                    "3a8ba305e8ed98f95bda2f6e81361571db10e20f0c2158d9"
                    "9930573e4d24ba83"
                ),
                "animation_timing_consumer": (
                    "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c"
                    "9cf6567eed468be0"
                ),
                "packed_tilemap_copier": (
                    "844be072d9572bd9a657357e745977ed9435c647d0ec0e811"
                    "f66c953c84a1bd6"
                ),
            },
            {
                key: value["sha256"]
                for key, value in manifest["consumer_evidence"].items()
            },
        )
        self.assertEqual(
            {
                "loop_index_selects_animation": True,
                "loop_index_selects_palette_bank": True,
                "timeline_frame_id_selects_definition_frame": True,
                "current_rows_map_animation_to_same_numbered_frame": True,
            },
            manifest["obj_selection_chain"],
        )

    def test_exports_all_nine_backgrounds_and_sixteen_obj_frames(self):
        packs = self.manifest["packs"]
        self.assertEqual(9, len(packs))
        self.assertEqual(list(range(9)), [pack["pack_id"] for pack in packs])
        self.assertEqual(
            [
                [19, 20],
                [21, 20],
                [20, 20],
                [23, 20],
                [22, 20],
                [18, 20],
                [21, 20],
                [23, 20],
                [20, 20],
            ],
            [
                [
                    pack["background"]["width_tiles"],
                    pack["background"]["height_tiles"],
                ]
                for pack in packs
            ],
        )
        self.assertEqual(
            [224, 234, 210, 227, 234, 168, 243, 236, 181],
            [pack["background"]["tile_count"] for pack in packs],
        )
        self.assertEqual(
            [88, 76, 72, 80, 64, 72, 40, 64, 40],
            [pack["obj"]["tile_count"] for pack in packs],
        )
        self.assertEqual(
            [3, 11, 17, 25, 56, 34, 48, 31, 0],
            [pack["presentation_id"] for pack in packs],
        )
        self.assertEqual(
            [2, 2, 2, 2, 2, 2, 1, 2, 1],
            [pack["spawn_count"] for pack in packs],
        )
        self.assertEqual(16, self.manifest["summary"]["obj_frame_count"])
        self.assertEqual(16, self.manifest["summary"]["obj_animation_count"])

        for pack in packs:
            background = pack["background"]
            self.assertEqual(8, background["bits_per_pixel"])
            self.assertTrue(background["all_tiles_referenced"])
            self.assertEqual(
                background["width_tiles"] * 8,
                background["canvas"]["width"],
            )
            self.assertEqual(160, background["canvas"]["height"])
            self.assertTrue((self.output / background["canvas"]["file"]).is_file())

            obj = pack["obj"]
            self.assertEqual(4, obj["bits_per_pixel"])
            self.assertTrue(obj["all_tiles_referenced"])
            self.assertEqual(pack["spawn_count"], len(obj["frames"]))
            self.assertEqual(pack["spawn_count"], len(obj["animations"]))
            for frame in obj["frames"]:
                self.assertEqual(frame["frame_id"], frame["palette_bank"])
                self.assertTrue((self.output / frame["png"]["file"]).is_file())
            for animation in obj["animations"]:
                self.assertEqual(0, animation["duration_ticks"])
                self.assertEqual(65536, animation["timer_period_updates"])
                self.assertEqual("loop", animation["termination_policy"])
                self.assertEqual(
                    [
                        {
                            "frame_id": animation["frame_id"],
                            "start_update": 0,
                            "end_update_exclusive": 65536,
                        }
                    ],
                    animation["playback"],
                )
                timeline = self.output / animation["timeline_file"]
                self.assertTrue(timeline.is_file())
                self.assertEqual(
                    animation,
                    json.loads(timeline.read_text(encoding="utf-8")),
                )

    def test_records_shared_obj_palettes_and_scope_without_overclaiming(self):
        palettes = self.manifest["shared_obj_palettes"]
        self.assertEqual(
            ["0x083F2794", "0x083F2CB0"],
            [palette["gba_address"] for palette in palettes],
        )
        self.assertEqual(
            [
                "14975f2391f88813040bbadc136bbfcaa736a408521af3701054bf0470d5a4f9",
                "bb58f9bc0be9a3b7ad2604ced29815b23d55660c89e70e59430959cf7aed8b2f",
            ],
            [palette["sha256"] for palette in palettes],
        )
        self.assertEqual(
            {
                "all_table_rows_exported": True,
                "native_background_canvases_complete": True,
                "obj_definition_frames_complete": True,
                "obj_animation_frame_sets_complete": True,
                "obj_animation_timing_complete": True,
                "screen_space_composition_complete": False,
                "natural_language_scene_names_complete": False,
                "final_viewport_crop_complete": False,
            },
            self.manifest["scope"],
        )
        self.assertEqual(
            {
                "spawner_requested_flags": "0x000000A0",
                "allocator_active_bit": "0x00000001",
                "initial_task_flags": "0x000000A1",
                "termination_policy_bits": "0x20",
                "timer_storage": "u16",
                "timer_initial": 0,
                "timer_increment_per_update": 1,
                "duration_compare": (
                    "duration_ticks == timer_after_increment"
                ),
                "zero_duration_first_expiry_updates": 65536,
                "terminator_frame_index": -1,
                "terminator_policy": (
                    "reset_frame_cursor_and_timer_then_loop"
                ),
            },
            self.manifest["obj_animation_runtime"],
        )

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_scene_visual_packs import verify_artifact

        source = (
            ROOT / "tools" / "verify_scene_visual_packs.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(9, report["pack_count"])
        self.assertEqual(16, report["obj_frame_count"])
        self.assertEqual(16, report["obj_animation_count"])

        for relative in (
            "manifest.json",
            self.manifest["packs"][0]["background"]["canvas"]["file"],
            self.manifest["packs"][0]["obj"]["frames"][0]["png"]["file"],
        ):
            with tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], relative)
                self.assertTrue(report["errors"], relative)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            animation = manifest["packs"][0]["obj"]["animations"][0]
            animation["duration_ticks"] = 1
            timeline = tampered / animation["timeline_file"]
            timeline.write_text(
                json.dumps(animation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_scene_visual_packs import export_artifact

        committed = ROOT / "artifacts/scene-visual-packs-v1"
        self.assertEqual(
            directory_hashes(self.output),
            directory_hashes(committed),
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            second = export_artifact(ROOT, output)
            self.assertEqual(self.manifest, second)
            self.assertEqual(directory_hashes(self.output), directory_hashes(output))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_scene_visual_packs.py",
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
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('"obj_frame_count": 16', result.stdout)
            self.assertTrue((output / "manifest.json").is_file())

    def test_output_target_rejects_repository_and_unrelated_data(self):
        from tools.export_scene_visual_packs import (
            export_artifact,
            validate_output_target,
        )

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT.parent)

        with tempfile.TemporaryDirectory() as temporary:
            unrelated = Path(temporary) / "unrelated"
            unrelated.mkdir()
            sentinel = unrelated / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, unrelated)
            self.assertEqual("user data", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
