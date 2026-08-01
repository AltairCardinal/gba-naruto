from __future__ import annotations

import importlib
import unittest


class Group15NaturalRuntimeExporterTests(unittest.TestCase):
    def setUp(self):
        self.exporter = importlib.import_module(
            "tools.export_battle_effect_group15_natural_runtime"
        )

    def test_selects_exact_dynamic_side1_sequence17_chain(self):
        events = [
            {"name": name, "frame": frame, "cycle": str(cycle), **registers}
            for name, frame, cycle, registers in (
                ("runtime-copy-b", 1087, 10, {"r4": "0x02026CB8"}),
                ("presentation-entry", 1546, 20, {"r0": "0x02026CB8"}),
                ("classification-cmp", 1546, 30, {"r0": "0x00000000"}),
                ("dynamic-selector", 1546, 40, {"r4": "0x02026CB8"}),
                (
                    "dynamic-binder-call",
                    1546,
                    50,
                    {"r0": "0x00000001", "r1": "0x00000011", "r2": "0x00000770"},
                ),
                (
                    "binder-entry",
                    1546,
                    60,
                    {"r0": "0x00000001", "r1": "0x00000011", "r2": "0x00000770"},
                ),
            )
        ]
        selected = self.exporter.select_branch_chain(events)
        self.assertEqual(
            [row["name"] for row in selected],
            list(self.exporter.BRANCH_CHAIN_NAMES),
        )

    def test_rejects_special_sequence_or_wrong_binder_arguments(self):
        valid = [
            {"name": name, "frame": 10, "cycle": str(index + 1)}
            for index, name in enumerate(self.exporter.BRANCH_CHAIN_NAMES)
        ]
        valid[0]["frame"] = 9
        valid[0]["r4"] = "0x02026CB8"
        valid[1]["r0"] = "0x02026CB8"
        valid[2]["r0"] = "0x00000000"
        valid[3]["r4"] = "0x02026CB8"
        for row in valid[4:]:
            row.update(r0="0x00000001", r1="0x00000011", r2="0x00000770")
        with self.assertRaises(ValueError):
            self.exporter.select_branch_chain(
                valid + [{"name": "special-sequence-6", "frame": 10, "cycle": "7"}]
            )
        changed = [dict(row) for row in valid]
        changed[-1]["r1"] = "0x00000006"
        with self.assertRaises(ValueError):
            self.exporter.select_branch_chain(changed)

    def test_archive_denominator_is_fixed(self):
        members = self.exporter.expected_archive_members()
        self.assertEqual(len(members), 48)
        self.assertIn("source/input-state.ss9", members)
        self.assertIn("source/branch-final.ss9", members)
        self.assertIn("source/branch-final.png", members)
        self.assertIn("source/branch-done.json", members)
        self.assertIn("source/phase/ack-post/capture.ss9", members)

    def test_repository_dependency_denominator_covers_runtime_guard_chain(self):
        required = {
            "tools/run_macos_mgba_group15_natural_branch_trace.py",
            "tools/run_macos_mgba_replay.py",
            "tools/run_macos_mgba_input_sequence.py",
            "tools/run_macos_mgba_single_input.py",
            "tools/macos_mgba_runtime_residue.py",
            "tools/run_guarded.py",
            "tools/mgba_runtime_safety.py",
            "tools/project_resource_guard.py",
            "tools/thumb_branch.py",
            "tools/build_save_state_runtime_probe.py",
            "tests/test_run_macos_mgba_group15_natural_branch_trace.py",
        }
        self.assertTrue(required.issubset(set(self.exporter.REPOSITORY_FILES)))


if __name__ == "__main__":
    unittest.main()
