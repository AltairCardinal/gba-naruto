import unittest
from pathlib import Path


class _MemoryState:
    def __init__(self):
        self.memory = bytearray(0x40000)

    def write(self, address, data):
        offset = address - 0x02000000
        self.memory[offset : offset + len(data)] = data

    def read_memory(self, address, size):
        offset = address - 0x02000000
        return bytes(self.memory[offset : offset + size])


class BattlefieldObjectEffectSeedFinderTest(unittest.TestCase):
    def test_reports_active_object_and_equipped_tool_seeds(self):
        from tools.find_battlefield_object_effect_seeds import inspect_state

        state = _MemoryState()
        obj = bytearray(0x10)
        obj[0] = 1
        obj[4] = 0xC3
        obj[6:8] = (2).to_bytes(2, "little")
        state.write(0x02026604 + 0x10, obj)
        unit = bytearray(0x1D4)
        unit[0] = 3
        unit[0xB0] = 1
        unit[0xB1] = 67
        state.write(0x020240C0 + 2 * 0x1D4, unit)

        result = inspect_state(state)
        self.assertEqual(
            result["active_special_objects"],
            [{"slot": 1, "state": 1, "encoded_action": "0xC3", "remaining_turns": 2}],
        )
        self.assertEqual(
            result["equipped_special_tools"],
            [{"unit_slot": 2, "character_id": 3, "tool_slot": 0, "ninja_tool_id": 67}],
        )

    def test_ignores_inactive_objects_and_unused_unit_bytes(self):
        from tools.find_battlefield_object_effect_seeds import inspect_state

        state = _MemoryState()
        obj = bytearray(0x10)
        obj[0] = 3
        obj[4] = 0xC4
        state.write(0x02026604 + 0x20, obj)
        unit = bytearray(0x1D4)
        unit[0xB1] = 68
        state.write(0x020240C0, unit)
        result = inspect_state(state)
        self.assertEqual(result["active_special_objects"], [])
        self.assertEqual(result["equipped_special_tools"], [])

    def test_missing_input_is_an_error_instead_of_a_zero_hit_scan(self):
        from tools.find_battlefield_object_effect_seeds import scan_paths

        result = scan_paths([Path("/definitely/not/a/real/savestate-root")])
        self.assertEqual(result["scanned"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("does not exist", result["errors"][0]["error"])


if __name__ == "__main__":
    unittest.main()
