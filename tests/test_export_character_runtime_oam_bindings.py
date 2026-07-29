import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportCharacterRuntimeOamBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_character_runtime_oam_bindings import export_bindings

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "bindings.json"
        cls.bindings = export_bindings(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_scans_every_tracked_checkpoint_and_indexes_natural_character_objects(self):
        result = self.bindings

        self.assertEqual("character-runtime-oam-bindings-v1", result["schema"])
        self.assertEqual(
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            result["rom"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (
                    ROOT
                    / "artifacts"
                    / "character-battle-visuals-v1"
                    / "manifest.json"
                ).read_bytes()
            ).hexdigest(),
            result["source_artifact"]["manifest_sha256"],
        )
        self.assertEqual(
            {
                "checkpoint_count": 91,
                "checkpoint_parse_error_count": 0,
                "one_dimensional_obj_mapping_count": 91,
                "active_oam_object_count": 1211,
                "matched_oam_object_count": 222,
                "unmatched_oam_object_count": 989,
                "checkpoints_with_matches": 57,
                "unique_best_source_count": 133,
                "ambiguous_best_source_count": 89,
                "palette_exact_match_count": 11,
                "palette_difference_at_most_one_count": 205,
            },
            result["summary"],
        )
        self.assertEqual(91, len(result["checkpoints"]))
        self.assertEqual(
            sorted(
                path.relative_to(ROOT).as_posix()
                for path in (
                    ROOT / "artifacts" / "runtime-checkpoints"
                ).glob("*.ss9")
            ),
            [checkpoint["path"] for checkpoint in result["checkpoints"]],
        )

    def test_binds_known_naruto_runtime_oam_to_source_frames_and_palette_delta(self):
        checkpoint = next(
            item
            for item in self.bindings["checkpoints"]
            if item["path"].endswith("scenario-41-player-turn.ss9")
        )
        match = next(
            item
            for item in checkpoint["matches"]
            if item["oam_index"] == 11
        )

        self.assertEqual(32, match["width"])
        self.assertEqual(64, match["height"])
        self.assertEqual(0, match["tile_index"])
        self.assertEqual(0, match["palette_bank"])
        self.assertEqual(2, match["priority"])
        self.assertEqual("unique_best_source", match["resolution"])
        self.assertEqual(1, len(match["best_sources"]))
        source = match["best_sources"][0]
        self.assertEqual(0, source["resource_id"])
        self.assertEqual(4, source["frame_id"])
        self.assertEqual(0, source["component_index"])
        self.assertEqual(128, source["source_tile_offset"])
        self.assertEqual([1], source["character_ids"])
        self.assertEqual([0], source["visual_slots"])
        self.assertEqual(
            {"x": match["screen_x"] + 16, "y": match["screen_y"] + 56},
            source["non_affine_task_origin_candidate"],
        )
        self.assertEqual(1, source["palette_difference_count"])
        self.assertEqual(
            [
                {
                    "color_index": 15,
                    "source_bgr555": "0x0421",
                    "runtime_bgr555": "0x7FE0",
                }
            ],
            source["palette_differences"],
        )

    def test_hash_locks_every_gpu_region_used_for_matching(self):
        from tools.inspect_mgba_savestate import load_gba_state

        checkpoint = next(
            item
            for item in self.bindings["checkpoints"]
            if item["path"].endswith("scenario-41-player-turn.ss9")
        )
        state = load_gba_state(ROOT / checkpoint["path"])
        expected = {
            "io": state.read_memory(0x04000000, 0x400),
            "pram": state.read_memory(0x05000000, 0x400),
            "oam": state.read_memory(0x07000000, 0x400),
            "vram": state.read_memory(0x06000000, 0x18000),
        }

        self.assertEqual(
            {
                name: {
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                for name, payload in expected.items()
            },
            checkpoint["regions"],
        )

    def test_preexisting_gpu_decoder_independently_agrees_with_all_emitted_oam_fields(self):
        from tools.butano.analyze_scenario_41_gpu import decode_gpu
        from tools.inspect_mgba_savestate import load_gba_state

        for checkpoint in self.bindings["checkpoints"]:
            state = load_gba_state(ROOT / checkpoint["path"])
            decoded = decode_gpu(
                state.read_memory(0x04000000, 0x400),
                state.read_memory(0x07000000, 0x400),
            )
            objects = {
                item["index"]: item for item in decoded["objects"]
            }
            self.assertEqual(
                checkpoint["active_oam_object_count"],
                len(objects),
            )
            for match in checkpoint["matches"]:
                obj = objects[match["oam_index"]]
                self.assertEqual(
                    [match["width"], match["height"]],
                    obj["dimensions"],
                )
                self.assertEqual(match["screen_x"], obj["position"]["x"])
                self.assertEqual(match["screen_y"], obj["position"]["y"])
                self.assertEqual(match["tile_index"], obj["tile_index"])
                self.assertEqual(match["priority"], obj["priority"])
                self.assertEqual(match["palette_bank"], obj["palette_bank"])
                self.assertEqual(match["affine"], obj["affine"])
                self.assertEqual(
                    match["horizontal_flip"],
                    obj["horizontal_flip"],
                )
                self.assertEqual(
                    match["vertical_flip"],
                    obj["vertical_flip"],
                )

    def test_manual_runtime_tile_and_palette_golden_matches_naruto_source_bytes(self):
        import struct

        from tools.inspect_mgba_savestate import load_gba_state

        checkpoint = next(
            item
            for item in self.bindings["checkpoints"]
            if item["path"].endswith("scenario-41-player-turn.ss9")
        )
        match = next(
            item
            for item in checkpoint["matches"]
            if item["oam_index"] == 11
        )
        source = match["best_sources"][0]
        state = load_gba_state(ROOT / checkpoint["path"])
        vram = state.read_memory(0x06000000, 0x18000)
        pram = state.read_memory(0x05000000, 0x400)
        source_dir = (
            ROOT / "artifacts" / "character-battle-visuals-v1"
        )
        source_manifest = json.loads(
            (source_dir / "manifest.json").read_text(encoding="utf-8")
        )
        resource = source_manifest["resources"][source["resource_id"]]
        graphics = (source_dir / resource["graphics"]["file"]).read_bytes()
        palette = (source_dir / resource["palette"]["file"]).read_bytes()
        byte_count = match["width"] * match["height"] // 2
        runtime_tiles = vram[
            0x10000 + match["tile_index"] * 32 :
            0x10000 + match["tile_index"] * 32 + byte_count
        ]
        source_tiles = graphics[
            source["source_tile_offset"] * 32 :
            source["source_tile_offset"] * 32 + byte_count
        ]
        runtime_palette = pram[
            0x200 + match["palette_bank"] * 32 :
            0x220 + match["palette_bank"] * 32
        ]

        self.assertEqual(source_tiles, runtime_tiles)
        self.assertEqual(
            [(15, 0x0421, 0x7FE0)],
            [
                (index, source_color, runtime_color)
                for index, (source_color, runtime_color) in enumerate(
                    zip(
                        struct.unpack("<16H", palette),
                        struct.unpack("<16H", runtime_palette),
                    )
                )
                if source_color != runtime_color
            ],
        )

    def test_records_multiple_characters_without_overclaiming_ambiguous_sources(self):
        checkpoint = next(
            item
            for item in self.bindings["checkpoints"]
            if item["path"].endswith("scenario-46-battle-start.ss9")
        )

        character_ids = {
            character_id
            for match in checkpoint["matches"]
            for source in match["best_sources"]
            for character_id in source["character_ids"]
        }
        self.assertTrue({1, 2, 3, 41}.issubset(character_ids))
        self.assertTrue(
            any(
                match["resolution"] == "ambiguous_best_source"
                for match in checkpoint["matches"]
            )
        )

    def test_scope_distinguishes_observed_bindings_from_complete_composition(self):
        self.assertEqual(
            {
                "all_tracked_checkpoints_scanned": True,
                "matched_oam_graphics_bound_to_source_components": True,
                "runtime_palette_differences_recorded": True,
                "observed_screen_coordinates_and_priority_recorded": True,
                "natural_task_and_selector_trace_complete": False,
                "all_character_slots_runtime_observed": False,
                "camera_writer_schedule_complete": False,
                "blend_window_and_bg_pixel_composition_complete": False,
                "screen_space_composition_complete": False,
            },
            self.bindings["scope"],
        )

    def test_export_is_byte_deterministic(self):
        from tools.export_character_runtime_oam_bindings import export_bindings

        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "bindings.json"
            export_bindings(ROOT, second)
            self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_independent_verifier_accepts_export_and_rejects_tampering(self):
        from tools.verify_character_runtime_oam_bindings import verify_bindings

        verifier_source = (
            ROOT / "tools" / "verify_character_runtime_oam_bindings.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "export_character_runtime_oam_bindings",
            verifier_source,
        )
        self.assertIn(
            "from tools.butano.analyze_scenario_41_gpu import decode_gpu",
            verifier_source,
        )

        report = verify_bindings(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(91, report["checkpoints"])
        self.assertEqual(222, report["matches"])

        original = self.output.read_bytes()
        try:
            tampered = json.loads(original)
            tampered["checkpoints"][0]["sha256"] = "0" * 64
            self.output.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rejected = verify_bindings(ROOT, self.output)
            self.assertFalse(rejected["verified"])
            self.assertIn(
                "bindings do not match independently reconstructed evidence",
                rejected["errors"],
            )
        finally:
            self.output.write_bytes(original)

    def test_cli_writes_only_the_requested_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested" / "bindings.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "tools"
                        / "export_character_runtime_oam_bindings.py"
                    ),
                    "--root",
                    str(ROOT),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(output.is_file())
            self.assertEqual(
                [output],
                [path for path in output.parent.rglob("*") if path.is_file()],
            )

    def test_committed_artifact_is_the_verified_promoted_output(self):
        from tools.verify_character_runtime_oam_bindings import verify_bindings

        artifact = (
            ROOT / "artifacts" / "character-runtime-oam-bindings-v1"
        )
        bindings_path = artifact / "bindings.json"
        promotion = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        source_manifest = (
            ROOT
            / "artifacts"
            / "character-battle-visuals-v1"
            / "manifest.json"
        )

        self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
        self.assertEqual("accepted", promotion["artifact_status"])
        self.assertEqual(
            "character-runtime-oam-bindings-v1",
            promotion["artifact_schema"],
        )
        self.assertEqual(
            {
                "bindings.json": hashlib.sha256(
                    bindings_path.read_bytes()
                ).hexdigest()
            },
            promotion["files"],
        )
        self.assertEqual(
            hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
            promotion["source"]["source_artifact_manifest_sha256"],
        )
        self.assertEqual(
            self.output.read_bytes(),
            bindings_path.read_bytes(),
        )
        self.assertTrue(
            verify_bindings(ROOT, bindings_path)["verified"]
        )


if __name__ == "__main__":
    unittest.main()
