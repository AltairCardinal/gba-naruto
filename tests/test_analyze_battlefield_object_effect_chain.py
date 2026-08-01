import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlefieldObjectEffectChainAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battlefield_object_effect_chain import (
            build_battlefield_object_effect_chain_manifest,
        )

        return build_battlefield_object_effect_chain_manifest(
            ROOT, ROOT / "rom/base.gba"
        )

    def test_six_ninja_tools_map_exactly_to_the_six_special_actions(self):
        result = self._manifest()
        self.assertEqual(
            [row["ninja_tool_id"] for row in result["mappings"]],
            list(range(67, 73)),
        )
        self.assertEqual(
            [row["encoded_action"] for row in result["mappings"]],
            [f"0x{value:02X}" for value in range(0xC3, 0xC9)],
        )
        self.assertEqual(
            [row["expiry_action"] for row in result["mappings"]],
            [f"0x{value:02X}" for value in range(0xE4, 0xEA)],
        )
        self.assertTrue(all(row["effect_code"] == 0x18 for row in result["mappings"]))
        self.assertTrue(
            all(row["resolver_handler"] == "0x08077514" for row in result["mappings"])
        )

    def test_object_lifecycle_and_presentation_chain_are_rom_bound(self):
        result = self._manifest()
        self.assertEqual(
            result["chain"],
            {
                "event_action_store": "0x080755FA",
                "type_1_object_builder": "0x08077514",
                "object_allocator_callsite": "0x0807752C",
                "object_allocator": "0x08081024",
                "side_end_caller": "0x08073688",
                "expiry_event_builder": "0x08081B70",
                "object_action_read": "0x08081D74",
                "expiry_action_delta": 0x21,
                "presentation_initializer_callsite": "0x08081F60",
                "presentation_initializer": "0x0807AB34",
                "effect_orchestrator_callsite": "0x0807ABD4",
                "effect_orchestrator": "0x0807F414",
                "special_action_threshold": "action > 0xE3",
                "wide_allocator_reset_callsite": "0x0807FD14",
                "primary_dispatch_load": "0x0807FD28",
                "trampoline_callsite": "0x0807FD3A",
                "native_handler": "0x0807F208",
            },
        )
        self.assertTrue(all(row["primary_handler"] == "0x0807F209" for row in result["mappings"]))
        self.assertTrue(all(row["secondary_handler"] is None for row in result["mappings"]))

    def test_scope_does_not_overclaim_natural_runtime_completion(self):
        result = self._manifest()
        self.assertEqual(result["evidence_level"], "static_end_to_end_producer_chain")
        self.assertFalse(result["natural_runtime_observed"])
        self.assertFalse(result["natural_gameplay_route_closed"])
        self.assertIn("自然", result["boundary"])


if __name__ == "__main__":
    unittest.main()
