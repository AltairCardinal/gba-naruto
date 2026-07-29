import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExportCharacterRuntimeUnitOamBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_character_runtime_unit_oam_bindings import (
            export_bindings,
        )

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "bindings.json"
        cls.bindings = export_bindings(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def _checkpoint(self, suffix):
        return next(
            checkpoint
            for checkpoint in self.bindings["checkpoints"]
            if checkpoint["path"].endswith(suffix)
        )

    def _observation(self, checkpoint, oam_index):
        return next(
            observation
            for observation in checkpoint["oam_unit_observations"]
            if observation["oam_index"] == oam_index
        )

    def test_scans_parent_corpus_and_separates_spatial_anchor_from_ownership(self):
        result = self.bindings

        self.assertEqual(
            "character-runtime-unit-oam-bindings-v1",
            result["schema"],
        )
        self.assertEqual(
            {
                "checkpoint_count": 91,
                "live_unit_record_count": 367,
                "oam_observation_count": 222,
                "observations_with_live_character_candidates": 220,
                "observations_without_live_character_candidates": 2,
                "unique_base_grid_anchor_observation_count": 208,
                "ambiguous_base_grid_anchor_observation_count": 0,
                "single_live_character_candidate_with_offset_count": 12,
                "unresolved_spatial_candidate_count": 0,
                "unit_ownership_binding_count": 0,
            },
            result["summary"],
        )
        self.assertEqual(91, len(result["checkpoints"]))
        self.assertTrue(
            all(
                observation["unit_ownership"] is None
                for checkpoint in result["checkpoints"]
                for observation in checkpoint["oam_unit_observations"]
            )
        )

    def test_selects_unique_32_by_16_grid_model_over_runner_up(self):
        selection = self.bindings["coordinate_model"]["model_selection"]

        self.assertEqual(
            {
                "pixels_per_grid": 32,
                "center_offset": 16,
                "matching_observation_count": 209,
            },
            selection["x"]["best"],
        )
        self.assertEqual(
            {
                "pixels_per_grid": 16,
                "center_offset": 80,
                "matching_observation_count": 56,
            },
            selection["x"]["runner_up"],
        )
        self.assertEqual(
            {
                "pixels_per_grid": 16,
                "center_offset": 8,
                "matching_observation_count": 208,
            },
            selection["y"]["best"],
        )
        self.assertEqual(
            {
                "pixels_per_grid": 32,
                "center_offset": 200,
                "matching_observation_count": 54,
            },
            selection["y"]["runner_up"],
        )
        self.assertEqual(220, selection["eligible_observation_count"])
        self.assertEqual(208, selection["joint_matching_observation_count"])

    def test_raw_unit_pool_offsets_and_coordinate_wrap_are_hand_locked(self):
        from tools.export_character_runtime_unit_oam_bindings import (
            _live_units,
            _predicted_origin,
        )
        from tools.inspect_mgba_savestate import load_gba_state
        from tools.verify_character_runtime_unit_oam_bindings import (
            _decode_live_records,
            _grid_projection,
        )

        state = load_gba_state(
            ROOT
            / "artifacts"
            / "runtime-checkpoints"
            / "scenario-46-battle-start.ss9"
        )
        raw_pool = state.read_memory(0x020240C0, 13 * 0x1D4)
        self.assertEqual(
            "27ba6d04ba39c1821595a401e26940dbd7e04a7de57aec07b93bd1a756a01c48",
            hashlib.sha256(raw_pool).hexdigest(),
        )
        self.assertEqual(
            [
                (1, 1, 11, 15),
                (2, 2, 9, 15),
                (3, 3, 13, 15),
                (4, 41, 1, 5),
                (5, 41, 6, 4),
                (6, 41, 7, 9),
                (7, 41, 11, 5),
                (8, 41, 7, 22),
            ],
            [
                (
                    slot,
                    raw_pool[slot * 0x1D4],
                    raw_pool[slot * 0x1D4 + 0xC4],
                    raw_pool[slot * 0x1D4 + 0xC5],
                )
                for slot in range(1, 13)
                if raw_pool[slot * 0x1D4]
            ],
        )

        exported = _live_units(raw_pool)
        verified = _decode_live_records(raw_pool)
        self.assertEqual(exported, verified)
        wrapped = next(unit for unit in exported if unit["slot"] == 8)
        self.assertEqual(
            {"x": 504, "y": 192},
            _predicted_origin(
                wrapped,
                bg0_hofs=248,
                bg0_vofs=168,
            ),
        )
        self.assertEqual(
            {"x": 504, "y": 192},
            _grid_projection(wrapped, 248, 168),
        )

    def test_two_x_samples_reject_the_24_pixel_single_sample_alias(self):
        from tools.export_character_runtime_unit_oam_bindings import (
            _axis_model_ranking,
        )
        from tools.verify_character_runtime_unit_oam_bindings import (
            _rank_single_axis,
        )

        exporter_rows = [
            {
                "bg0_hofs": 24,
                "bg0_vofs": 88,
                "origins": [{"x": 120, "y": 80}],
                "candidates": [{"grid_x": 4, "grid_y": 10}],
            },
            {
                "bg0_hofs": 248,
                "bg0_vofs": 168,
                "origins": [{"x": 120, "y": 80}],
                "candidates": [{"grid_x": 11, "grid_y": 15}],
            },
        ]
        verifier_rows = [
            {
                "horizontal_scroll": row["bg0_hofs"],
                "vertical_scroll": row["bg0_vofs"],
                "origins": row["origins"],
                "records": row["candidates"],
            }
            for row in exporter_rows
        ]

        exporter_best = _axis_model_ranking(
            exporter_rows,
            axis="x",
            pixels_min=1,
            pixels_max=64,
            modulus=512,
        )[0]
        verifier_best = _rank_single_axis(
            verifier_rows,
            coordinate="x",
            grid_coordinate="grid_x",
            scroll_coordinate="horizontal_scroll",
            maximum_scale=64,
            modulus=512,
        )[0]
        expected = {
            "pixels_per_grid": 32,
            "center_offset": 16,
            "matching_observation_count": 2,
        }
        self.assertEqual(expected, exporter_best)
        self.assertEqual(expected, verifier_best)

    def test_binds_scenario_41_player_turn_to_base_grid_anchor(self):
        checkpoint = self._checkpoint("scenario-41-player-turn.ss9")
        observation = self._observation(checkpoint, 11)

        self.assertEqual(
            {"bg0_hofs_raw": 24, "bg0_vofs_raw": 88},
            checkpoint["display_scroll"],
        )
        self.assertEqual(
            [
                {
                    "slot": 1,
                    "record_address": "0x02024294",
                    "character_id": 1,
                    "grid_x": 4,
                    "grid_y": 10,
                }
            ],
            observation["live_character_candidates"],
        )
        self.assertEqual(
            "unique_base_grid_anchor_observation",
            observation["spatial_resolution"],
        )
        self.assertEqual(
            [
                {
                    "slot": 1,
                    "observed_origin": {"x": 120, "y": 80},
                    "predicted_origin_mod": {"x": 120, "y": 80},
                }
            ],
            observation["base_grid_anchor_candidates"],
        )
        self.assertIsNone(observation["observed_offset"])
        self.assertIsNone(observation["unit_ownership"])

    def test_spatial_anchor_disambiguates_repeated_character_without_claiming_ownership(self):
        checkpoint = self._checkpoint("scenario-46-battle-start.ss9")
        observation = self._observation(checkpoint, 8)

        self.assertEqual(
            {"bg0_hofs_raw": 248, "bg0_vofs_raw": 168},
            checkpoint["display_scroll"],
        )
        self.assertEqual([4, 5, 6, 7, 8], [
            candidate["slot"]
            for candidate in observation["live_character_candidates"]
        ])
        self.assertEqual("ambiguous_best_source", observation["source_resolution"])
        self.assertEqual(
            [
                {
                    "slot": 8,
                    "observed_origin": {"x": -8, "y": 192},
                    "predicted_origin_mod": {"x": 504, "y": 192},
                }
            ],
            observation["base_grid_anchor_candidates"],
        )
        self.assertEqual(
            "unique_base_grid_anchor_observation",
            observation["spatial_resolution"],
        )
        self.assertIsNone(observation["unit_ownership"])

    def test_same_character_oam_objects_resolve_to_distinct_spatial_anchors(self):
        checkpoint = self._checkpoint(
            "scenario-50-battle-15-round9-objective16-sasuke46.ss9"
        )
        expected = {11: 6, 13: 9, 14: 5, 15: 8, 19: 7}

        self.assertEqual(
            expected,
            {
                oam_index: self._observation(checkpoint, oam_index)[
                    "base_grid_anchor_candidates"
                ][0]["slot"]
                for oam_index in expected
            },
        )
        for oam_index in expected:
            observation = self._observation(checkpoint, oam_index)
            self.assertEqual([5, 6, 7, 8, 9], [
                candidate["slot"]
                for candidate in observation["live_character_candidates"]
            ])
            self.assertIsNone(observation["unit_ownership"])

    def test_records_nonzero_presentation_offset_without_weakening_base_model(self):
        checkpoint = self._checkpoint("scenario-41-attack-confirmation.ss9")
        observation = self._observation(checkpoint, 9)

        self.assertEqual(
            "single_live_character_candidate_with_offset",
            observation["spatial_resolution"],
        )
        self.assertEqual([], observation["base_grid_anchor_candidates"])
        self.assertEqual(
            {
                "slot": 1,
                "observed_origin": {"x": 160, "y": 72},
                "predicted_origin_mod": {"x": 128, "y": 104},
                "delta": {"x": 32, "y": -32},
            },
            observation["observed_offset"],
        )
        self.assertIsNone(observation["unit_ownership"])

    def test_records_no_live_unit_as_an_explicit_boundary(self):
        for suffix, oam_index in [
            ("alternate-character-overview.ss9", 12),
            ("skill-list-pre-controller.ss9", 13),
        ]:
            observation = self._observation(
                self._checkpoint(suffix),
                oam_index,
            )
            self.assertEqual(
                "no_live_character_candidate",
                observation["spatial_resolution"],
            )
            self.assertEqual([], observation["live_character_candidates"])
            self.assertEqual([], observation["base_grid_anchor_candidates"])
            self.assertIsNone(observation["observed_offset"])

    def test_scope_does_not_overclaim_writer_trace_or_screen_composition(self):
        self.assertEqual(
            {
                "all_parent_oam_checkpoints_reused": True,
                "unit_pool_raw_bytes_hash_bound": True,
                "live_unit_records_observed": True,
                "character_id_overlap_recorded": True,
                "grid_to_non_affine_origin_base_model_observed": True,
                "repeated_character_spatial_candidates_disambiguated": True,
                "live_unit_oam_ownership_proven": False,
                "unit_constructor_or_selector_trace_complete": False,
                "camera_offset_writer_schedule_complete": False,
                "nonzero_presentation_offset_semantics_complete": False,
                "unit_animation_state_to_source_frame_complete": False,
                "all_live_units_visualized": False,
                "screen_space_composition_complete": False,
            },
            self.bindings["scope"],
        )

    def test_export_is_byte_deterministic(self):
        from tools.export_character_runtime_unit_oam_bindings import (
            export_bindings,
        )

        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "bindings.json"
            export_bindings(ROOT, second)
            self.assertEqual(self.output.read_bytes(), second.read_bytes())

    def test_independent_verifier_accepts_export_and_rejects_tampering(self):
        from tools.verify_character_runtime_unit_oam_bindings import (
            verify_bindings,
        )

        verifier_source = (
            ROOT
            / "tools"
            / "verify_character_runtime_unit_oam_bindings.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "export_character_runtime_unit_oam_bindings",
            verifier_source,
        )

        report = verify_bindings(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(91, report["checkpoints"])
        self.assertEqual(222, report["observations"])

        original = self.output.read_bytes()
        try:
            tampered = json.loads(original)
            tampered["checkpoints"][0]["unit_pool"]["sha256"] = "0" * 64
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
            tampered = json.loads(original)
            observation = next(
                observation
                for checkpoint in tampered["checkpoints"]
                for observation in checkpoint["oam_unit_observations"]
                if observation["live_character_candidates"]
            )
            observation["unit_ownership"] = observation[
                "live_character_candidates"
            ][0]["slot"]
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
                        / "export_character_runtime_unit_oam_bindings.py"
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
        from tools.verify_character_runtime_unit_oam_bindings import (
            verify_bindings,
        )

        artifact = (
            ROOT / "artifacts" / "character-runtime-unit-oam-bindings-v1"
        )
        bindings_path = artifact / "bindings.json"
        promotion = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        source_path = (
            ROOT
            / "artifacts"
            / "character-runtime-oam-bindings-v1"
            / "bindings.json"
        )

        self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
        self.assertEqual("accepted", promotion["artifact_status"])
        self.assertEqual(
            "character-runtime-unit-oam-bindings-v1",
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
            hashlib.sha256(source_path.read_bytes()).hexdigest(),
            promotion["source"]["source_oam_bindings_sha256"],
        )
        self.assertEqual(self.output.read_bytes(), bindings_path.read_bytes())
        self.assertTrue(verify_bindings(ROOT, bindings_path)["verified"])


if __name__ == "__main__":
    unittest.main()
