import copy
import hashlib
import json
from pathlib import Path
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
                "task_pool_slot_count": 16,
                "resource_and_origin_correlation_count": 59,
                "frame_consistent_renderer_identity_count": 53,
                "frame_inconsistent_correlation_count": 6,
                "checkpoints_with_correlations": 12,
                "checkpoints_with_bindings": 9,
                "bound_task_slot_count": 8,
                "bound_resource_count": 6,
            },
            self.bindings["summary"],
        )

    def test_lineup_binds_three_oam_entries_to_exact_tasks_and_frames(self):
        checkpoint = self._checkpoint("scenario-46-lineup.ss9")
        rows = checkpoint["bindings"]

        self.assertEqual([12, 13, 14], [row["oam_index"] for row in rows])
        self.assertEqual([11, 13, 15], [row["task"]["slot"] for row in rows])
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
                "base": "0x030055F8",
                "record_size": 60,
                "slot_count": 16,
                "last_slot": "0x0300597C",
            },
            contract["task_pool"],
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

    def test_scope_does_not_overclaim_unmatched_oam_or_final_composition(self):
        self.assertEqual(
            {
                "all_tracked_checkpoints_scanned": True,
                "task_pool_layout_code_proven": True,
                "task_resource_fields_code_proven": True,
                "task_animation_state_code_proven": True,
                "task_origin_to_oam_renderer_code_proven": True,
                "frame_state_consistent_renderer_identity_observed": True,
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
