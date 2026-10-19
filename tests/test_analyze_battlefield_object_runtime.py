import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlefieldObjectRuntimeAnalysisTest(unittest.TestCase):
    def test_creation_fields_are_bound_to_effect_handlers(self):
        from tools.analyze_battlefield_object_runtime import (
            build_battlefield_object_runtime_manifest,
        )

        result = build_battlefield_object_runtime_manifest(
            ROOT / "rom/base.gba"
        )
        self.assertEqual(result["object_table"]["address"], "0x02026604")
        self.assertEqual(result["object_table"]["record_size"], 16)
        self.assertEqual(result["object_table"]["slot_count"], 32)
        self.assertEqual(
            result["creation"],
            {
                "0x0C": {
                    "handler": "0x0807726E",
                    "type": 2,
                    "payload_u16_at_4": "event_u8_at_0x0C",
                    "duration_u16_at_6": "event_u8_at_0x11_times_2",
                    "source_u16_at_8": "unused_zero",
                },
                "0x18": {
                    "handler": "0x08077514",
                    "type": 1,
                    "payload_u16_at_4": "event_u8_at_0x0C",
                    "duration_u16_at_6": "event_u8_at_0x11_times_2",
                    "source_u16_at_8": "event_u8_at_0x00",
                },
            },
        )

    def test_side_end_tick_and_expiration_paths_are_bound(self):
        from tools.analyze_battlefield_object_runtime import (
            build_battlefield_object_runtime_manifest,
        )

        result = build_battlefield_object_runtime_manifest(
            ROOT / "rom/base.gba"
        )
        self.assertEqual(
            result["lifecycle"],
            {
                "side_end_callsite": "0x08073688",
                "side_toggle": "0x080736B6",
                "tick_function": "0x08081B70",
                "type_2_entry": "0x08081B9A",
                "type_2_free": "0x08081C14",
                "type_1_entry": "0x08081C34",
                "type_1_payload_lookup": "0x08081CB4",
                "type_1_free": "0x08081F8E",
                "free_function": "0x08081084",
            },
        )
        self.assertEqual(
            result["semantics"]["duration"],
            "decremented_once_before_each_side_toggle",
        )
        self.assertEqual(
            result["semantics"]["type_1"],
            "resolve_payload_area_then_free",
        )
        self.assertEqual(
            result["semantics"]["type_2"],
            "play_expiry_effect_then_free",
        )
        self.assertEqual(
            result["type_2_presentation"],
            {
                "coordinate_effect_call": "0x08081BB0 -> 0x0806F210",
                "effect_builder_call": "0x08081BD4 -> 0x0807FDCC",
                "tile_index_start": 0x0300,
                "tile_index_end": 0x037F,
                "palette_bank_start": 12,
                "palette_bank_end": 14,
                "effect_sequence": 7,
                "effect_sequence_call": "0x08081BDA -> 0x0807FE2C",
                "sequence_resource_group": 0x12,
                "graphics_pointer": "0x083478F4",
                "palette_pointer": "0x083480C8",
                "graphics_decompressed_size": 0x0E00,
                "graphics_frame_count": 7,
                "wait_state": 3,
                "free_after_wait": "0x08081C14",
            },
        )
        self.assertEqual(
            result["grid_binding"],
            {
                "set_call": "0x08081068 -> 0x08080FC8",
                "clear_call": "0x08081098 -> 0x08080FF8",
                "cell_buffer": "0x02021E2C",
                "map_width": "0x0201BE2A",
                "object_slot_shift": 6,
                "object_slot_mask": "0x07C0",
                "rendering": "grid_metadata_not_visible_sprite",
            },
        )


if __name__ == "__main__":
    unittest.main()
