#!/usr/bin/env python3
"""ROM-backed tests for complete battle-effect sequence bindings."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RUNTIME_TABLE_SHA256 = (
    "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b"
)
ACTIVE_ACTION_SLICE_SHA256 = (
    "373b8c02a0e768f15843be31a3f1282346986fd9bb52584be5649e3f01696b22"
)
NINJA_TOOL_SELECTOR_SLICE_SHA256 = (
    "7b329765f680d1638a5899bfa67b3501e8c32cda6399a83b38ef88b35c21cfb4"
)
NINJA_TOOL_TEMPLATE_TABLE_SHA256 = (
    "e586bbeeb364a14639e5062491c26c163905cb4c5501985bbafb5ed0ba3cd0fd"
)
DESCRIPTOR_TABLE_SHA256 = (
    "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f"
)


class BattleEffectSequenceBindingExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_sequence_bindings import (
            export_battle_effect_sequence_bindings,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "sequence-bindings"
        cls.manifest = export_battle_effect_sequence_bindings(
            ROOT,
            cls.output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_hash_bound_complete_tables(self):
        self.assertEqual(
            "battle-effect-sequence-bindings-v1",
            self.manifest["schema"],
        )
        self.assertEqual(ROM_SHA256, self.manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x53E596,
                "gba_address": "0x0853E596",
                "entry_count": 256,
                "entry_size": 1,
                "sha256": RUNTIME_TABLE_SHA256,
            },
            self.manifest["runtime_state_sequence_table"],
        )
        self.assertEqual(
            {
                "start_index": 0,
                "entry_count": 87,
                "sha256": ACTIVE_ACTION_SLICE_SHA256,
            },
            self.manifest["active_action_slice"],
        )
        self.assertEqual(
            {
                "file_offset": 0x545458,
                "gba_address": "0x08545458",
                "entry_count": 87,
                "entry_size": 16,
                "sha256": "d36979d06334807da33a348174de6de4bb834bca762bbb3d23deb2472a2aa966",
            },
            self.manifest["active_action_template_table"],
        )
        self.assertEqual(
            {
                "start_index": 0x80,
                "entry_count": 94,
                "sha256": NINJA_TOOL_SELECTOR_SLICE_SHA256,
            },
            self.manifest["ninja_tool_selector_slice"],
        )
        self.assertEqual(
            {
                "file_offset": 0x545BE4,
                "gba_address": "0x08545BE4",
                "entry_count": 94,
                "entry_size": 16,
                "sha256": NINJA_TOOL_TEMPLATE_TABLE_SHA256,
            },
            self.manifest["ninja_tool_template_table"],
        )
        self.assertEqual(
            {
                "file_offset": 0x53EF30,
                "gba_address": "0x0853EF30",
                "entry_count": 22,
                "entry_size": 24,
                "sha256": DESCRIPTOR_TABLE_SHA256,
                "next_structure_gba_address": "0x0853F140",
            },
            self.manifest["sequence_descriptor_table"],
        )
        self.assertEqual(256, len(self.manifest["runtime_state_bindings"]))
        self.assertEqual(87, len(self.manifest["active_action_bindings"]))
        self.assertEqual(94, len(self.manifest["ninja_tool_bindings"]))
        self.assertEqual(22, len(self.manifest["sequences"]))

    def test_preserves_complete_runtime_table_and_active_action_slice(self):
        runtime = self.manifest["runtime_state_bindings"]
        self.assertEqual(list(range(256)), [item["runtime_state_value"] for item in runtime])
        self.assertEqual(
            Counter({0: 171, 6: 40, 13: 36, 16: 3, 15: 3, 17: 2, 14: 1}),
            Counter(item["sequence_id"] for item in runtime),
        )
        bindings = self.manifest["active_action_bindings"]
        self.assertEqual(list(range(87)), [item["action_id"] for item in bindings])
        self.assertEqual(
            Counter({0: 41, 6: 37, 16: 3, 15: 3, 17: 2, 14: 1}),
            Counter(item["sequence_id"] for item in bindings),
        )
        reverse = {
            item["sequence_id"]: item["active_action_ids"]
            for item in self.manifest["sequences"]
            if item["active_action_ids"]
        }
        self.assertEqual([32], reverse[14])
        self.assertEqual([61, 76, 77], reverse[15])
        self.assertEqual([16, 17, 18], reverse[16])
        self.assertEqual([64, 65], reverse[17])
        self.assertEqual(37, len(reverse[6]))
        self.assertEqual(41, len(reverse[0]))
        self.assertEqual(5, bindings[80]["display_animation_family"])
        self.assertEqual(6, bindings[80]["sequence_id"])
        self.assertEqual(
            {6, 14, 15, 16, 17},
            {
                item["sequence_id"]
                for item in bindings
                if item["display_animation_family"] == 1
            },
        )
        self.assertEqual(
            {
                "active_action_template_table": "0x08545458",
                "event_action_id_field": "+0x0C",
                "runtime_state_action_id_field": "+0x770",
                "selector_is_parallel_id_table": True,
                "sequence_derived_from_template_fields": False,
            },
            self.manifest["active_action_join_evidence"],
        )

    def test_joins_high_bit_action_encoding_to_all_ninja_tool_templates(self):
        bindings = self.manifest["ninja_tool_bindings"]
        self.assertEqual(list(range(94)), [item["ninja_tool_id"] for item in bindings])
        self.assertEqual(
            list(range(0x80, 0xDE)),
            [item["encoded_action_id"] for item in bindings],
        )
        self.assertEqual(
            Counter({0: 55, 13: 36, 6: 3}),
            Counter(item["sequence_id"] for item in bindings),
        )
        self.assertTrue(all(len(item["template_raw_hex"]) == 32 for item in bindings))
        self.assertEqual(
            {
                "encoded_action_high_bit": "0x80",
                "ninja_tool_id_mask": "0x7F",
                "ninja_tool_template_table": "0x08545BE4",
                "event_preserves_encoded_action_id_at": "+0x0C",
                "runtime_state_action_id_field": "+0x770",
                "selector_is_parallel_encoded_action_id_table": True,
            },
            self.manifest["ninja_tool_join_evidence"],
        )

    def test_preserves_all_resource_groups_and_callback_pointers(self):
        sequences = self.manifest["sequences"]
        self.assertEqual(
            [0, 1, 2, 3, 4, 1, 5, 18, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 16, 17, 2],
            [item["resource_group_ids"][0] for item in sequences],
        )
        self.assertTrue(
            all(item["resource_group_ids"][1:] == [0, 0, 0] for item in sequences)
        )
        self.assertEqual("0x00000000", sequences[0]["init_once_callback_thumb"])
        self.assertEqual("0x00000000", sequences[0]["tick_callback_thumb"])
        self.assertEqual("0x08080555", sequences[1]["init_once_callback_thumb"])
        self.assertEqual("0x0808055D", sequences[1]["tick_callback_thumb"])
        self.assertEqual("0x08080661", sequences[18]["init_once_callback_thumb"])
        self.assertEqual("0x08080815", sequences[18]["tick_callback_thumb"])
        self.assertEqual("0x08080965", sequences[21]["tick_callback_thumb"])

    def test_direct_selector_calls_prove_descriptor_upper_bound(self):
        calls = self.manifest["selector_callsites"]
        self.assertEqual(67, len(calls))
        constant = [item for item in calls if item["sequence_id"] is not None]
        dynamic = [item for item in calls if item["sequence_id"] is None]
        self.assertEqual(66, len(constant))
        self.assertEqual([21], [max(item["sequence_id"] for item in constant)])
        self.assertEqual(
            ["0x0807C602"],
            [item["gba_address"] for item in dynamic],
        )
        self.assertEqual(
            list(range(1, 13)) + [18, 19, 20, 21],
            sorted({item["sequence_id"] for item in constant}),
        )

    def test_scope_closes_static_bindings_without_overclaiming_animation(self):
        self.assertEqual(
            {
                "runtime_state_to_sequence_mapping_complete": True,
                "active_action_slice_join_complete": True,
                "active_action_to_sequence_mapping_complete": True,
                "ninja_tool_slice_join_complete": True,
                "ninja_tool_to_sequence_mapping_complete": True,
                "sequence_to_resource_group_mapping_complete": True,
                "callback_pointer_identity_complete": True,
                "callback_scheduler_role_complete": True,
                "callback_internal_animation_semantics_complete": False,
                "oam_composition_complete": False,
                "frame_hold_timing_complete": False,
                "audio_binding_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_rejects_manifest_tampering(self):
        from tools.verify_battle_effect_sequence_bindings import (
            verify_battle_effect_sequence_bindings,
        )

        result = verify_battle_effect_sequence_bindings(ROOT, self.output_dir)
        self.assertEqual(
            "battle-effect-sequence-bindings-verification-v1",
            result["schema"],
        )
        self.assertTrue(result["verified"])
        self.assertEqual([], result["errors"])
        self.assertEqual(256, result["verified_runtime_state_bindings"])
        self.assertEqual(87, result["verified_active_action_bindings"])
        self.assertEqual(94, result["verified_ninja_tool_bindings"])
        self.assertEqual(22, result["verified_sequences"])

        verifier_source = (
            ROOT / "tools/verify_battle_effect_sequence_bindings.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.", verifier_source)

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "tampered"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["active_action_bindings"][32]["sequence_id"] = 6
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sequence_bindings(ROOT, tampered_dir)
            self.assertTrue(
                any(
                    "active_action_bindings[32].sequence_id" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["active_action_bindings"][32]["sequence_id"] = 14
            manifest["ninja_tool_bindings"][0]["sequence_id"] = 13
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_battle_effect_sequence_bindings(ROOT, tampered_dir)
            self.assertTrue(
                any(
                    "ninja_tool_bindings[0].sequence_id" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

    def test_cli_export_is_deterministic_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "export"
            command = [
                sys.executable,
                str(ROOT / "tools/export_battle_effect_sequence_bindings.py"),
                "--root",
                str(ROOT),
                "--output-dir",
                str(output_dir),
            ]
            subprocess.run(command, check=True, cwd=ROOT)
            first = (output_dir / "manifest.json").read_bytes()
            subprocess.run(command, check=True, cwd=ROOT)
            self.assertEqual(first, (output_dir / "manifest.json").read_bytes())
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/verify_battle_effect_sequence_bindings.py"),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(output_dir),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertIn('"errors": []', completed.stdout)


if __name__ == "__main__":
    unittest.main()
