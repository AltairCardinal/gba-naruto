#!/usr/bin/env python3
"""ROM-bound inventory for battle presentation selector scripts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlePresentationScriptAnalysisTests(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_presentation_scripts import (
            build_battle_presentation_manifest,
        )

        return build_battle_presentation_manifest(ROOT / "rom/base.gba")

    def test_binds_controller_interpreter_and_two_47_entry_tables(self):
        result = self._manifest()
        self.assertEqual(result["controller_callsite"], "0x080736F8")
        self.assertEqual(result["selector_builder"], "0x0808A534")
        self.assertEqual(result["presentation_runner"], "0x0808A588")
        self.assertEqual(result["interpreter"], "0x080977B8")
        self.assertEqual(result["dispatch_table"], "0x080977F4")
        self.assertEqual(result["battle_count"], 47)
        self.assertEqual(result["selector_table"], "0x08060E34")
        self.assertEqual(result["presentation_table"], "0x08060EF0")
        self.assertEqual(result["selector_non_null_count"], 46)
        self.assertEqual(result["presentation_non_null_count"], 46)
        self.assertEqual(result["battles"][0]["selector_root"], None)
        self.assertEqual(result["battles"][0]["presentation_root"], None)

    def test_control_dispatch_matches_the_original_interpreter(self):
        result = self._manifest()
        self.assertEqual(
            result["control_dispatch"],
            {
                "0x07": "0x08097D20",
                "0x32": "0x08097CF8",
                "0x33": "0x08097D2A",
                "0x34": "0x08097D4C",
                "0x35": "0x08097D86",
                "0x36": "0x08097DA6",
                "0x37": "0x08097DC4",
                "0x38": "0x08097DCE",
                "0x39": "0x08097DF6",
            },
        )
        self.assertEqual(result["complete_control_graph_count"], 46)
        self.assertEqual(result["partial_control_graph_battle_ids"], [])

    def test_all_400_presentation_cases_have_closed_payload_boundaries(self):
        result = self._manifest()
        self.assertEqual(result["presentation_case_count"], 400)
        self.assertEqual(result["complete_presentation_case_count"], 400)
        self.assertEqual(
            result["presentation_payload_opcode_counts"],
            {
                "0x00": 400,
                "0x01": 1074,
                "0x02": 140,
                "0x03": 3,
                "0x04": 163,
                "0x08": 1030,
                "0x0F": 1,
                "0x11": 37,
                "0x12": 317,
                "0x17": 4,
                "0x20": 44,
            },
        )
        for battle in result["battles"][1:]:
            for case in battle["presentation_cases"]:
                self.assertTrue(case["payload_complete"])
                self.assertEqual(case["commands"][-1]["opcode"], "0x00")

    def test_portrait_commands_have_rom_bound_structured_semantics(self):
        result = self._manifest()
        self.assertEqual(
            result["portrait_helpers"],
            {
                "show_portrait": {
                    "start": "0x080967E8",
                    "end": "0x080968EC",
                    "sha256": (
                        "3a4849197fc7786e7645f6c1a2d1ed0125a2057c7dd7faa"
                        "375bfc245d0a962df"
                    ),
                },
                "hide_portrait": {
                    "start": "0x08096668",
                    "end": "0x08096740",
                    "sha256": (
                        "23634345bdc0e80f725f9b11dd96c9e546d4df5e4afe923a"
                        "ffbe158451143e0b"
                    ),
                },
                "update_portrait": {
                    "start": "0x08096A04",
                    "end": "0x08096A34",
                    "sha256": (
                        "4cae8974a3dcae837944eee60d09d590658c91f08130aba2e"
                        "3cb49a1c307d726"
                    ),
                },
                "initialize_portrait_pair": {
                    "start": "0x080968EC",
                    "end": "0x08096A04",
                    "sha256": (
                        "ab4715cd5991475dc4596ba7aa86240e9418abb89eaeb6012"
                        "be309b9ec7d9f01"
                    ),
                },
                "animate_portrait": {
                    "start": "0x08096B74",
                    "end": "0x08096D16",
                    "sha256": (
                        "01587c0f3edfc01a912ad68b0da3b85c4ec6b01a30ee5082"
                        "21e478665d8062ec"
                    ),
                },
                "clear_portrait_focus": {
                    "start": "0x08096D8C",
                    "end": "0x08096DCA",
                    "sha256": (
                        "37e1d70134245831fe254ea5643ee7e1ab7e8fff2a365cf97"
                        "96429f65ecf9805"
                    ),
                },
                "set_portrait_focus": {
                    "start": "0x08096DD4",
                    "end": "0x08096E52",
                    "sha256": (
                        "a0bad94b78b489589e10075ce24144fff81a5e1d5798a2ee8"
                        "dd1ccafdf38a9e3"
                    ),
                },
            },
        )

        first = result["battles"][41]["presentation_cases"][0]["commands"]
        self.assertEqual(
            first[0],
            {
                **first[0],
                "name": "initialize_portrait_pair",
                "left_portrait_id": 1,
                "left_expression_id": 0,
                "right_portrait_id": 30,
                "right_expression_id": 0,
                "semantics": "initialize_left_and_right_portrait_slots",
            },
        )
        self.assertEqual(first[3]["name"], "update_portrait")
        self.assertEqual(first[3]["portrait_slot"], 0)
        self.assertEqual(first[3]["portrait_id"], 1)
        self.assertEqual(first[3]["expression_id"], 2)

        commands = [
            command
            for battle in result["battles"]
            for case in battle.get("presentation_cases", [])
            for command in case["commands"]
        ]
        hide = next(command for command in commands if command["opcode"] == "0x03")
        self.assertEqual(hide["name"], "hide_portrait")
        self.assertEqual(hide["portrait_slot"], 0xFF)
        self.assertEqual(hide["semantics"], "hide_all_portrait_slots")

        focus = next(command for command in commands if command["opcode"] == "0x11")
        self.assertEqual(focus["name"], "set_portrait_focus")
        self.assertEqual(focus["portrait_slot"], 1)

        motion = next(command for command in commands if command["opcode"] == "0x17")
        self.assertEqual(motion["name"], "animate_portrait")
        self.assertEqual(motion["portrait_slot"], 0)
        self.assertEqual(motion["motion_mode"], 2)
        self.assertEqual(motion["motion_parameter"], 1)
        self.assertEqual(
            motion["semantics"],
            "run_original_portrait_motion_state_machine",
        )

    def test_battle_41_is_a_two_case_data_driven_script(self):
        from tools.analyze_battle_presentation_scripts import (
            evaluate_round_side_selector_sequence,
        )

        result = self._manifest()
        battle = result["battles"][41]
        self.assertEqual(battle["selector_root"], "0x0805B28A")
        self.assertEqual(battle["presentation_root"], "0x0805B2AF")
        self.assertTrue(battle["selector_graph_complete"])
        self.assertEqual(
            battle["selector_opcode_counts"],
            {"0x00": 1, "0x33": 2, "0x34": 4},
        )
        self.assertEqual(
            battle["reachable_selector_sequences"],
            [[], [1], [1, 2], [2]],
        )
        self.assertEqual(
            battle["presentation_cases"],
            [
                {
                    "selector": 1,
                    "target": "0x0805B2B9",
                    "payload_complete": True,
                    "commands": battle["presentation_cases"][0]["commands"],
                },
                {
                    "selector": 2,
                    "target": "0x0805B405",
                    "payload_complete": True,
                    "commands": battle["presentation_cases"][1]["commands"],
                },
            ],
        )
        first_commands = battle["presentation_cases"][0]["commands"]
        self.assertEqual(
            [command["opcode"] for command in first_commands],
            [
                "0x12",
                "0x08",
                "0x01",
                "0x04",
                "0x08",
                "0x01",
                "0x08",
                "0x01",
                "0x08",
                "0x01",
                "0x04",
                "0x08",
                "0x01",
                "0x00",
            ],
        )
        self.assertEqual(first_commands[0]["address"], "0x0805B2B9")
        self.assertEqual(first_commands[0]["operand_hex"], "01001e00")
        self.assertEqual(first_commands[1]["name"], "select_message_speaker")
        self.assertEqual(first_commands[1]["speaker"], 30)
        self.assertEqual(first_commands[2]["name"], "render_encoded_text")
        self.assertEqual(first_commands[2]["encoded_text_hex"][:8], "81678aef")
        self.assertEqual(first_commands[-1]["address"], "0x0805B404")

        second_commands = battle["presentation_cases"][1]["commands"]
        self.assertEqual(
            [command["opcode"] for command in second_commands],
            ["0x12", "0x08", "0x01", "0x04", "0x08", "0x01", "0x00"],
        )
        self.assertEqual(second_commands[-1]["address"], "0x0805B479")
        self.assertEqual(
            battle["selector_nodes"][0]["comparison"], "greater_or_equal"
        )
        self.assertEqual(battle["selector_nodes"][0]["round_value"], 1)
        self.assertEqual(battle["selector_nodes"][0]["side"], 1)
        self.assertEqual(
            evaluate_round_side_selector_sequence(battle, 1, 0),
            [1],
        )
        self.assertEqual(
            evaluate_round_side_selector_sequence(battle, 2, 0),
            [2],
        )
        self.assertEqual(
            evaluate_round_side_selector_sequence(battle, 3, 0),
            [],
        )
        self.assertEqual(
            evaluate_round_side_selector_sequence(battle, 1, 1),
            [],
        )

    def test_non_41_cross_sample_uses_the_same_format_with_four_cases(self):
        from tools.analyze_battle_presentation_scripts import (
            evaluate_round_side_selector_sequence,
        )

        result = self._manifest()
        battle = result["battles"][44]
        self.assertTrue(battle["selector_graph_complete"])
        self.assertEqual(
            battle["reachable_selector_sequences"],
            [
                [],
                [1],
                [1, 2],
                [1, 2, 3],
                [1, 2, 3, 4],
                [1, 2, 4],
                [1, 3],
                [1, 3, 4],
                [1, 4],
                [2],
                [2, 3],
                [2, 3, 4],
                [2, 4],
                [3],
                [3, 4],
                [4],
            ],
        )
        self.assertEqual(
            [
                (case["selector"], case["target"])
                for case in battle["presentation_cases"]
            ],
            [
                (1, "0x0805B9D7"),
                (2, "0x0805BB7D"),
                (3, "0x0805BCC3"),
                (4, "0x0805BDFA"),
            ],
        )
        self.assertEqual(
            [command["opcode"]
             for command in battle["presentation_cases"][0]["commands"][:6]],
            ["0x12", "0x08", "0x01", "0x08", "0x01", "0x08"],
        )
        self.assertEqual(
            [
                evaluate_round_side_selector_sequence(battle, round_index, 0)
                for round_index in range(1, 6)
            ],
            [[1], [2], [3], [4], []],
        )

    def test_unit_flag_and_battle_state_conditions_have_closed_semantics(self):
        result = self._manifest()
        nodes = {
            opcode: next(
                node
                for node in result["battles"][1]["selector_nodes"]
                if node["opcode"] == opcode
            )
            for opcode in {"0x35", "0x36", "0x37", "0x38"}
        }
        self.assertEqual(
            nodes["0x35"]["semantics"],
            "branch_when_unit_relationship_result_matches_expected",
        )
        self.assertEqual(nodes["0x35"]["expected"], 0)
        self.assertEqual(nodes["0x35"]["relationship_mode"], 0)
        self.assertEqual(nodes["0x35"]["first_character_id"], 1)
        self.assertEqual(nodes["0x35"]["second_character_id"], 2)
        self.assertEqual(
            nodes["0x36"]["semantics"],
            "branch_when_unit_query_result_matches_expected",
        )
        self.assertEqual(nodes["0x37"]["semantics"], "set_script_flag")
        self.assertEqual(
            nodes["0x38"]["semantics"],
            "branch_when_script_flag_query_is_true",
        )
        state_node = next(
            node
            for node in result["battles"][4]["selector_nodes"]
            if node["opcode"] == "0x39"
        )
        self.assertEqual(
            state_node["semantics"],
            "branch_when_battle_state_matches",
        )

    def test_hash_or_pointer_corruption_fails_closed(self):
        from tools.analyze_battle_presentation_scripts import (
            build_battle_presentation_manifest,
        )

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x60E34 + 41 * 4] ^= 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.gba"
            path.write_bytes(rom)
            with self.assertRaisesRegex(ValueError, "selector table SHA-256"):
                build_battle_presentation_manifest(path)

    def test_portrait_helper_corruption_fails_closed(self):
        from tools.analyze_battle_presentation_scripts import (
            build_battle_presentation_manifest,
        )

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x0967E8] ^= 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.gba"
            path.write_bytes(rom)
            with self.assertRaisesRegex(ValueError, "show portrait helper SHA-256"):
                build_battle_presentation_manifest(path)

    def test_manifest_is_json_serializable_and_deterministic(self):
        first = self._manifest()
        second = self._manifest()
        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
