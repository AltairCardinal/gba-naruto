import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleActionTemplateSemanticsAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_action_template_semantics import (
            build_action_template_semantics_manifest,
        )

        return build_action_template_semantics_manifest(ROOT, ROOT / "rom/base.gba")

    def test_rom_code_and_both_content_banks_are_hash_bound(self):
        result = self._manifest()
        self.assertEqual(result["content"]["active_actions"]["entry_count"], 87)
        self.assertEqual(result["content"]["ninja_tools"]["entry_count"], 94)
        self.assertEqual(result["evidence"]["active_initializer"]["sha256"],
                         "dd78df15b6599a2bc73fd04e5b04f8a58cb8d761f7d7ae3a0460a5daae9daa7f")
        self.assertEqual(result["evidence"]["tool_initializer"]["sha256"],
                         "032c35e2fa3295e906a741e1f58a5351417686fd17826d7849af7c1959138268")
        self.assertEqual(result["evidence"]["target_policy"]["sha256"],
                         "a30e7de2bdc628e4e631407a4b37d51a77c1aaa7132bf788bb1a56668375f9d4")
        self.assertEqual(result["evidence"]["event_builder"]["sha256"],
                         "bd90433b9b831de35d1bc4a62652c02b4a7bebe0c6b530577137c96580faedde")
        self.assertEqual(result["evidence"]["resolver_dispatch"]["sha256"],
                         "e45b03dec38fddb123ab43af2b47a08e7d67e49435cabe64f59dc28d453fbbd4")

    def test_cost_effect_target_and_presentation_are_orthogonal(self):
        result = self._manifest()
        self.assertEqual(
            result["semantics"]["runtime_layout"],
            {
                "+0": "cost_kind",
                "+1": "display_animation_family",
                "+2_low_6": "effect_code",
                "+2_high_2": "effect_flags",
                "+3_low_3": "target_policy",
                "+3_high_5": "target_flags",
                "+4": "potency",
                "+5": "base_hit_count",
                "+6": "success_rate_percent",
                "+7": "distance_and_line_flags",
                "+8": "area_range_and_shape_flags",
                "+9": "duration_turns",
                "+A..+B": "scalar_resource_cost_u16",
            },
        )
        self.assertEqual(
            result["semantics"]["cost_kinds"],
            {
                "0": "none",
                "1": "current_chakra",
                "2": "current_hp",
                "3": "no_scalar_resource_special",
                "5": "battle_local_ninja_tool_slot",
            },
        )

    def test_known_active_actions_decode_without_skill_name_heuristics(self):
        actions = {row["action_id"]: row for row in self._manifest()["active_actions"]}
        teleport = actions[2]
        self.assertEqual(teleport["cost"], {"kind": 1, "name": "current_chakra", "scalar": 1})
        self.assertEqual(teleport["effect"], {"code": 3, "flags": 0, "handler": "0x080770D0"})
        self.assertEqual(teleport["target"], {"policy": 4, "name": "empty_tile", "flags": 0})

        heal = actions[6]
        self.assertEqual(heal["cost"]["name"], "no_scalar_resource_special")
        self.assertIsNone(heal["cost"]["scalar"])
        self.assertEqual(heal["effect"]["code"], 6)
        self.assertEqual(heal["target"]["policy"], 5)

        lion_barrage = actions[19]
        self.assertEqual(lion_barrage["cost"], {"kind": 2, "name": "current_hp", "scalar": 80})

    def test_ninja_tools_use_slot_cost_but_share_effect_and_target_dispatch(self):
        tools = {row["ninja_tool_id"]: row for row in self._manifest()["ninja_tools"]}
        tool = tools[1]
        self.assertEqual(tool["cost"], {"kind": 5, "name": "battle_local_ninja_tool_slot", "scalar": None})
        self.assertEqual(tool["display_animation_family"], 1)
        self.assertEqual(tool["effect"], {"code": 1, "flags": 0, "handler": "0x08077040"})
        self.assertEqual(tool["target"], {"policy": 2, "name": "opponent_unit", "flags": 0})

    def test_every_nonempty_template_resolves_through_the_data_driven_jump_table(self):
        result = self._manifest()
        for collection in (result["active_actions"], result["ninja_tools"]):
            for row in collection:
                if row["is_empty"]:
                    continue
                self.assertGreaterEqual(row["effect"]["code"], 1)
                self.assertLessEqual(row["effect"]["code"], 0x3F)
                self.assertRegex(row["effect"]["handler"], r"^0x080[0-9A-F]{5}$")

        handlers = result["semantics"]["effect_dispatch"]["handlers"]
        self.assertEqual(handlers["01"], "0x08077040")
        self.assertEqual(handlers["04"], handlers["09"])
        self.assertEqual(handlers["1E"], handlers["25"])
        self.assertEqual(handlers["3F"], "0x0807755C")


if __name__ == "__main__":
    unittest.main()
