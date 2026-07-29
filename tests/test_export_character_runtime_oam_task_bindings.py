import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExportCharacterRuntimeOamTaskBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_character_runtime_oam_task_bindings import export_bindings

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

    def test_exports_strict_frame_consistent_task_bindings(self):
        self.assertEqual(
            "character-runtime-oam-task-bindings-v1",
            self.bindings["schema"],
        )
        self.assertEqual(
            {
                "checkpoint_count": 91,
                "checkpoint_parse_error_count": 0,
                "task_pool_slot_count": 128,
                "resource_and_origin_correlation_count": 59,
                "frame_consistent_renderer_identity_count": 53,
                "frame_inconsistent_correlation_count": 6,
                "checkpoints_with_correlations": 12,
                "checkpoints_with_bindings": 9,
                "bound_task_slot_count": 8,
                "bound_resource_count": 6,
                "active_task_pointer_count": 741,
                "checkpoints_with_exact_dispatch_reconstruction": 91,
                "checkpoints_with_shadow_hardware_full_match": 80,
                "bound_tasks_with_unique_dispatch_membership": 53,
                "bound_shadow_hardware_slot_match_count": 53,
            },
            self.bindings["summary"],
        )

    def test_lineup_binds_three_oam_entries_to_exact_tasks_and_frames(self):
        checkpoint = self._checkpoint("scenario-46-lineup.ss9")
        rows = checkpoint["bindings"]

        self.assertEqual([12, 13, 14], [row["oam_index"] for row in rows])
        self.assertEqual([123, 125, 127], [row["task"]["slot"] for row in rows])
        self.assertEqual(
            ["0x0300588C", "0x03005904", "0x0300597C"],
            [row["task"]["address"] for row in rows],
        )
        self.assertEqual([18, 9, 0], [row["source"]["resource_id"] for row in rows])
        self.assertEqual([0, 0, 0], [row["source"]["frame_id"] for row in rows])
        self.assertEqual(
            [{"x": 200, "y": 96}, {"x": 120, "y": 96}, {"x": 40, "y": 96}],
            [row["task"]["origin"] for row in rows],
        )
        self.assertEqual(
            [row["oam"]["attr0"] for row in rows],
            [row["renderer_prediction"]["predicted_attr0"] for row in rows],
        )
        self.assertEqual(
            [row["oam"]["attr1"] for row in rows],
            [row["renderer_prediction"]["predicted_attr1"] for row in rows],
        )
        self.assertEqual(
            [row["oam"]["attr2"] for row in rows],
            [row["renderer_prediction"]["predicted_attr2"] for row in rows],
        )
        self.assertTrue(all(row["renderer_prediction"]["matches_oam"] for row in rows))

    def test_reconstructs_dispatch_order_and_observes_bound_shadow_oam_slots(self):
        lineup = self._checkpoint("scenario-46-lineup.ss9")

        self.assertEqual(
            {
                "active_count_address": "0x03005BB8",
                "pointer_list_address": "0x030059B8",
                "active_count": 7,
                "pointer_list_size": 28,
                "pointer_list_sha256": (
                    "b0ddc0f19ddf99406bddb2d963a98316d359c0a88caba7d7"
                    "80c0817305f8bb27"
                ),
                "active_task_slots": [121, 123, 125, 127, 122, 124, 126],
                "reconstructed_active_task_slots": [
                    121,
                    123,
                    125,
                    127,
                    122,
                    124,
                    126,
                ],
                "exact_reconstruction": True,
            },
            lineup["dispatcher_state"],
        )
        self.assertEqual(
            [1, 2, 3],
            [
                row["dispatch_and_oam_observation"]["dispatch_ordinal"]
                for row in lineup["bindings"]
            ],
        )
        self.assertEqual(
            [12, 13, 14],
            [
                row["dispatch_and_oam_observation"]["shadow_oam_index"]
                for row in lineup["bindings"]
            ],
        )
        self.assertTrue(
            all(
                row["dispatch_and_oam_observation"][
                    "unique_dispatch_membership"
                ]
                and row["dispatch_and_oam_observation"][
                    "renderer_prediction_matches_shadow"
                ]
                and row["dispatch_and_oam_observation"][
                    "shadow_matches_hardware"
                ]
                for row in lineup["bindings"]
            )
        )
        self.assertNotEqual(
            [1, 2, 3],
            [12, 13, 14],
            "dispatch ordinal must not be mislabeled as the OAM index",
        )
        self.assertTrue(
            lineup["shadow_oam_state"]["full_buffer_matches_hardware"]
        )

        phase_lagged = self._checkpoint(
            "scenario-50-battle-15-round12-objective4-stable-loop.ss9"
        )
        self.assertFalse(
            phase_lagged["shadow_oam_state"]["full_buffer_matches_hardware"]
        )
        self.assertEqual(
            [19, 20, 21, 22],
            phase_lagged["shadow_oam_state"]["differing_object_indices"],
        )
        self.assertTrue(
            all(
                row["dispatch_and_oam_observation"][
                    "shadow_matches_hardware"
                ]
                for row in phase_lagged["bindings"]
            )
        )

    def test_dispatch_comparator_covers_all_keys_and_sort_y_source(self):
        from tools.export_character_runtime_oam_task_bindings import (
            _dispatcher_precedes,
            _parse_tasks,
            _reconstruct_active_task_slots,
        )

        def task(slot, flags, sort_y):
            return {
                "slot": slot,
                "_flags_int": flags | 1,
                "_sort_y": sort_y,
            }

        self.assertTrue(
            _dispatcher_precedes(task(1, 0x40, 0), task(0, 0x80, 0))
        )
        self.assertTrue(
            _dispatcher_precedes(task(1, 0x100, 0), task(0, 0x200, 0))
        )
        self.assertTrue(
            _dispatcher_precedes(task(1, 0x40000, 0), task(0, 0, 0))
        )
        self.assertTrue(
            _dispatcher_precedes(
                task(1, 0x40000, 20),
                task(0, 0x40000, 10),
            )
        )
        self.assertFalse(
            _dispatcher_precedes(
                task(1, 0x40000, 10),
                task(0, 0x40000, 20),
            )
        )
        self.assertFalse(
            _dispatcher_precedes(task(1, 0, 10), task(0, 0, 10))
        )
        self.assertEqual(
            [3, 2, 1, 0],
            _reconstruct_active_task_slots(
                [
                    task(0, 0x80, 0),
                    task(1, 0x40, 0),
                    task(2, 0x40 | 0x40000, 10),
                    task(3, 0x40 | 0x40000, 20),
                ]
            ),
        )

        pool = bytearray(128 * 0x3C)
        struct.pack_into("<Ihh", pool, 0, 1, 0, 11)
        struct.pack_into(
            "<Ihh", pool, 0x3C, 1 | 0x02000000, 0, 22
        )
        struct.pack_into("<h", pool, 0x3C + 0x1A, 33)
        parsed = _parse_tasks(bytes(pool), {})
        self.assertEqual(11, parsed[0]["_sort_y"])
        self.assertEqual(33, parsed[1]["_sort_y"])

    def test_frame_inconsistent_correlations_are_not_promoted_to_bindings(self):
        checkpoint = self._checkpoint("scenario-46-victory-reward.ss9")

        self.assertEqual([], checkpoint["bindings"])
        self.assertEqual(3, len(checkpoint["correlations"]))
        self.assertEqual(
            {"frame_state_mismatch"},
            {row["resolution"] for row in checkpoint["correlations"]},
        )
        self.assertEqual(
            [0, 1, 2],
            [row["oam_index"] for row in checkpoint["correlations"]],
        )

    def test_static_contract_hash_binds_pool_renderer_and_owner_family(self):
        contract = self.bindings["static_contract"]

        self.assertEqual(
            {
                "base": "0x03003BB8",
                "record_size": 60,
                "slot_count": 128,
                "last_slot": "0x0300597C",
            },
            contract["task_pool"],
        )
        self.assertEqual("0x03005BB8", contract["dispatcher"]["active_count"])
        self.assertEqual("0x030059B8", contract["dispatcher"]["pointer_list"])
        self.assertEqual(
            "0x0300027C", contract["dispatcher"]["shadow_oam_base"]
        )
        self.assertEqual(
            "0x0300067C", contract["dispatcher"]["shadow_oam_end"]
        )
        self.assertEqual(
            "6c14764539f4a6071dfae9d1a0943a467ff931094f94aed74fbad587788db626",
            contract["presentation_owner_family"]["callback"]["sha256"],
        )
        self.assertEqual(
            "d8d926ab79fa74ba96a25552b7b6da57cb7ba3fc6fdac1c9d77df2aacd748ac1",
            contract["presentation_owner_family"]["selector"]["sha256"],
        )
        self.assertFalse(
            contract["presentation_owner_family"][
                "same_family_as_bound_field_tasks_proven"
            ]
        )

    def test_hashes_the_full_global_pool_not_only_the_last_sixteen_slots(self):
        from tools.inspect_mgba_savestate import load_gba_state

        checkpoint = self._checkpoint("scenario-46-lineup.ss9")
        self.assertEqual(
            {
                "address": "0x03003BB8",
                "size": 7680,
                "sha256": (
                    "4d6c12088c8477e30d5812722511def255782fa481a852688"
                    "9214e971c0d9b63"
                ),
                "recognized_resource_task_count": 4,
            },
            checkpoint["task_pool"],
        )

        state = load_gba_state(ROOT / checkpoint["path"])
        prefix = state.read_memory(0x03003BB8, 112 * 0x3C)
        self.assertEqual(
            "941f1c5364a0ec8a2c299882bb6582e939f2a3b63f025d236298406d2a8a6d80",
            hashlib.sha256(prefix).hexdigest(),
        )
        self.assertNotEqual(bytes(len(prefix)), prefix)

    def test_scope_does_not_overclaim_unmatched_oam_or_final_composition(self):
        self.assertEqual(
            {
                "all_tracked_checkpoints_scanned": True,
                "task_pool_layout_code_proven": True,
                "task_resource_fields_code_proven": True,
                "task_animation_state_code_proven": True,
                "task_origin_to_oam_renderer_code_proven": True,
                "frame_state_consistent_renderer_identity_observed": True,
                "active_task_pointer_list_reconstructed_all_checkpoints": True,
                "bound_task_unique_dispatch_membership_observed": True,
                "bound_predicted_oam_observed_in_shadow_and_hardware": True,
                "shadow_oam_full_buffer_equal_to_hardware_all_checkpoints": False,
                "shadow_to_hardware_copy_schedule_traced": False,
                "task_to_oam_writer_or_allocation_index_traced": False,
                "component_zero_dynamic_copy_subset_complete": True,
                "multi_component_dynamic_copy_binding_complete": False,
                "all_character_oam_task_bindings_complete": False,
                "presentation_owner_family_linked_to_bound_field_tasks": False,
                "unit_ownership_proven": False,
                "camera_and_viewport_complete": False,
                "blend_window_priority_complete": False,
                "screen_space_composition_complete": False,
            },
            self.bindings["scope"],
        )

    def test_renderer_identity_rejects_field_and_branch_mutations(self):
        from tools.export_character_runtime_oam_task_bindings import (
            _renderer_prediction,
        )

        row = next(
            row
            for checkpoint in self.bindings["checkpoints"]
            for row in checkpoint["bindings"]
            if row["source"]["source_tile_offset"] > 0
        )
        task = copy.deepcopy(row["task"])
        task["_flags_int"] = int(task["flags"], 16)
        source = copy.deepcopy(row["source"])
        component = {
            "width": source["component_width"],
            "height": source["component_height"],
            "horizontal_flip": source["component_horizontal_flip"],
            "vertical_flip": source["component_vertical_flip"],
        }
        oam = copy.deepcopy(row["oam"])

        self.assertTrue(
            _renderer_prediction(task, source, component, oam)["matches_oam"]
        )

        changed_tile = copy.deepcopy(task)
        changed_tile["tile_base"] += 1
        self.assertFalse(
            _renderer_prediction(
                changed_tile, source, component, oam
            )["matches_oam"]
        )

        changed_priority = copy.deepcopy(task)
        changed_priority["_flags_int"] ^= 0x40
        self.assertFalse(
            _renderer_prediction(
                changed_priority, source, component, oam
            )["matches_oam"]
        )

        changed_branch = copy.deepcopy(task)
        changed_branch["_flags_int"] &= ~0x00400000
        self.assertFalse(
            _renderer_prediction(
                changed_branch, source, component, oam
            )["matches_oam"]
        )

        changed_shape = copy.deepcopy(component)
        changed_shape["width"] = 8
        changed_shape["height"] = 8
        self.assertFalse(
            _renderer_prediction(
                task, source, changed_shape, oam
            )["matches_oam"]
        )

        changed_flip = copy.deepcopy(component)
        changed_flip["horizontal_flip"] = not changed_flip["horizontal_flip"]
        self.assertFalse(
            _renderer_prediction(
                task, source, changed_flip, oam
            )["matches_oam"]
        )

    def test_independent_verifier_reconstructs_and_rejects_tampering(self):
        from tools.verify_character_runtime_oam_task_bindings import verify_bindings

        report = verify_bindings(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(53, report["binding_count"])

        tampered = copy.deepcopy(self.bindings)
        lineup = next(
            checkpoint
            for checkpoint in tampered["checkpoints"]
            if checkpoint["path"].endswith("scenario-46-lineup.ss9")
        )
        lineup["bindings"][0]["task"]["origin"]["x"] += 1
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

        tampered = copy.deepcopy(self.bindings)
        lineup = next(
            checkpoint
            for checkpoint in tampered["checkpoints"]
            if checkpoint["path"].endswith("scenario-46-lineup.ss9")
        )
        lineup["dispatcher_state"]["active_task_slots"][0] = 127
        lineup["bindings"][0]["dispatch_and_oam_observation"][
            "shadow_entry_hex"
        ] = "00" * 8
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

    def test_promoted_artifact_is_hash_bound_and_reproducible(self):
        from tools.verify_character_runtime_oam_task_bindings import verify_bindings

        artifact = (
            ROOT / "artifacts" / "character-runtime-oam-task-bindings-v1"
        )
        bindings_path = artifact / "bindings.json"
        promotion = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
        self.assertEqual("accepted", promotion["artifact_status"])
        self.assertEqual(
            "character-runtime-oam-task-bindings-v1",
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
            hashlib.sha256(
                (
                    ROOT
                    / "tools"
                    / "export_character_runtime_oam_task_bindings.py"
                ).read_bytes()
            ).hexdigest(),
            promotion["producer"]["exporter_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (
                    ROOT
                    / "tools"
                    / "verify_character_runtime_oam_task_bindings.py"
                ).read_bytes()
            ).hexdigest(),
            promotion["verifier"]["verifier_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            promotion["producer"]["test_sha256"],
        )
        self.assertEqual(self.bindings, json.loads(bindings_path.read_text()))
        report = verify_bindings(ROOT, bindings_path)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report, promotion["verifier"]["report"])


if __name__ == "__main__":
    unittest.main()
