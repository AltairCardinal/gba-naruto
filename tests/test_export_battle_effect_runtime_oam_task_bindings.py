import hashlib
import json
import struct
import copy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectTaskParsingTests(unittest.TestCase):
    def test_group_identity_uses_definition_animation_pair_not_graphics_field(self):
        from tools.export_battle_effect_runtime_oam_task_bindings import (
            TASK_POOL_SIZE,
            _parse_effect_tasks,
        )

        pool = bytearray(TASK_POOL_SIZE)
        slot = 3
        offset = slot * 0x3C
        struct.pack_into("<I", pool, offset, 1)
        struct.pack_into("<hh", pool, offset + 0x04, 150, 33)
        struct.pack_into("<HHH", pool, offset + 0x14, 0, 1, 2)
        struct.pack_into(
            "<III",
            pool,
            offset + 0x1C,
            0x08340000,
            0x08340100,
            0x08123456,
        )
        group = {
            "group_id": 7,
            "definition_pointer_table": "0x08340000",
            "animation_pointer_table": "0x08340100",
            "graphics": {"gba_address": "0x0834F000"},
            "animations": [
                {
                    "animation_id": 0,
                    "keyframes": [
                        {"frame_id": 4, "hold_frames": 3},
                        {"frame_id": 5, "hold_frames": 6},
                    ],
                }
            ],
        }

        tasks = _parse_effect_tasks(bytes(pool), {(0x08340000, 0x08340100): group})

        task = tasks[slot]
        self.assertEqual(7, task["group_id"])
        self.assertEqual(5, task["animation_state"]["selected_frame_id"])
        self.assertEqual("0x08123456", task["dynamic_tile_source"])
        self.assertNotEqual(group["graphics"]["gba_address"], task["dynamic_tile_source"])

    def test_exporter_rejects_parent_source_provenance_drift(self):
        from tools.export_battle_effect_runtime_oam_task_bindings import (
            _validate_source_provenance,
        )

        parent = json.loads(
            (
                ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json"
            ).read_text(encoding="utf-8")
        )
        promotion = json.loads(
            (
                ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        source_raw = (
            ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
        ).read_bytes()
        source = json.loads(source_raw)
        bad_parent = copy.deepcopy(parent)
        bad_parent["source_artifact"]["manifest_sha256"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "source provenance"):
            _validate_source_provenance(
                bad_parent,
                promotion,
                source,
                hashlib.sha256(source_raw).hexdigest(),
            )


class ExportBattleEffectRuntimeOamTaskBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_runtime_oam_task_bindings import build_bindings

        cls.bindings = build_bindings(ROOT)

    def test_scans_the_existing_parent_denominators_without_redefining_them(self):
        result = self.bindings
        self.assertEqual("battle-effect-runtime-oam-task-bindings-v1", result["schema"])
        self.assertEqual(93, result["summary"]["tracked_checkpoint_count"])
        self.assertEqual(5, result["summary"]["supplemental_state_count"])
        self.assertEqual(3, result["summary"]["tracked_parent_match_count"])
        self.assertEqual(9, result["summary"]["supplemental_parent_match_count"])
        self.assertEqual(0, result["summary"]["parse_error_count"])
        self.assertEqual(98, result["summary"]["exact_dispatch_reconstruction_count"])
        self.assertEqual(82, result["summary"]["shadow_hardware_full_match_count"])
        self.assertEqual(16, result["summary"]["code_proven_pending_difference_count"])
        self.assertEqual(0, result["summary"]["unexplained_submission_difference_count"])
        self.assertEqual(
            hashlib.sha256(
                (
                    ROOT
                    / "artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json"
                ).read_bytes()
            ).hexdigest(),
            result["parent_artifact"]["payload_sha256"],
        )

    def test_tracked_group1_tasks_reproduce_all_three_parent_oam_entries(self):
        checkpoint = next(
            item
            for item in self.bindings["tracked_checkpoints"]
            if item["path"].endswith(
                "scenario-50-battle-15-escort-12hp-player-turn.ss9"
            )
        )

        self.assertEqual([113, 114, 115], checkpoint["active_effect_task_slots"])
        self.assertEqual(3, checkpoint["accepted_binding_count"])
        self.assertEqual(
            [(113, 17), (114, 18), (115, 19)],
            [
                (item["task"]["slot"], item["oam"]["oam_index"])
                for item in checkpoint["accepted_bindings"]
            ],
        )
        for binding in checkpoint["accepted_bindings"]:
            self.assertEqual(1, binding["task"]["group_id"])
            self.assertEqual(6, binding["task"]["animation_state"]["selected_frame_id"])
            self.assertEqual(6, binding["source"]["frame_id"])
            self.assertEqual(0, binding["source"]["component_index"])
            self.assertTrue(binding["renderer_prediction"]["matches_parent_oam"])
            self.assertTrue(all(binding["renderer_prediction"]["checks"].values()))
            self.assertNotEqual(
                binding["dispatch_ordinal"], binding["oam"]["oam_index"]
            )
            self.assertTrue(binding["shadow_matches_hardware"])

    def test_runtime_offset_table_is_part_of_the_identity_evidence(self):
        checkpoint = next(
            item
            for item in self.bindings["tracked_checkpoints"]
            if item["accepted_binding_count"]
        )

        self.assertEqual("0x03000054", checkpoint["runtime_offset_table"]["address"])
        self.assertEqual(
            [{"x_q8_8": 0, "y_q8_8": 6144}, {"x_q8_8": 0, "y_q8_8": 6144},
             {"x_q8_8": 0, "y_q8_8": 6144}, {"x_q8_8": 0, "y_q8_8": 0}],
            checkpoint["runtime_offset_table"]["entries"],
        )
        for binding in checkpoint["accepted_bindings"]:
            prediction = binding["renderer_prediction"]
            self.assertEqual(0, prediction["runtime_offset_x"])
            self.assertEqual(24, prediction["runtime_offset_y"])

    def test_supplemental_task_frames_are_preserved_as_phase_observations(self):
        result = self.bindings

        self.assertEqual([1], result["summary"]["tracked_observed_group_ids"])
        self.assertEqual(
            [1, 2, 5, 11, 14],
            result["summary"]["all_persisted_observed_group_ids"],
        )
        self.assertTrue(
            all(item["active_effect_task_slots"] for item in result["supplemental_states"])
        )
        self.assertFalse(result["scope"]["all_effect_groups_runtime_observed"])
        self.assertFalse(result["scope"]["all_group_frames_runtime_observed"])
        self.assertFalse(result["scope"]["cross_frame_timing_complete"])
        self.assertTrue(result["scope"]["parent_oam_content_matches_preserved"])
        self.assertTrue(result["scope"]["task_group_identity_uses_pointer_pair"])


class PromotedBattleEffectRuntimeOamTaskBindingsTests(unittest.TestCase):
    def test_promoted_artifact_is_hash_locked_and_independently_verified(self):
        from tools.verify_battle_effect_runtime_oam_task_bindings import verify_bindings

        directory = ROOT / "artifacts/battle-effect-runtime-oam-task-bindings-v1"
        bindings_path = directory / "bindings.json"
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            "battle-effect-runtime-oam-task-bindings-v1", manifest["artifact_schema"]
        )
        self.assertEqual(
            hashlib.sha256(bindings_path.read_bytes()).hexdigest(),
            manifest["files"]["bindings.json"],
        )
        for key, relative in (
            ("exporter_sha256", "tools/export_battle_effect_runtime_oam_task_bindings.py"),
            ("verifier_sha256", "tools/verify_battle_effect_runtime_oam_task_bindings.py"),
            ("exporter_test_sha256", "tests/test_export_battle_effect_runtime_oam_task_bindings.py"),
            ("verifier_test_sha256", "tests/test_verify_battle_effect_runtime_oam_task_bindings.py"),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                manifest["producer"][key],
            )
        report = verify_bindings(ROOT, bindings_path)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report, manifest["verifier"]["result"])


if __name__ == "__main__":
    unittest.main()
