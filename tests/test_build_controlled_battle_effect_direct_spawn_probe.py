import importlib
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class ControlledBattleEffectDirectSpawnProbeTests(unittest.TestCase):
    def test_builds_the_four_static_direct_entry_contracts(self):
        builder = importlib.import_module(
            "tools.build_controlled_battle_effect_direct_spawn_probe"
        )
        base = (ROOT / "rom/base.gba").read_bytes()

        for case in builder.CASES:
            with self.subTest(case=case.case_id):
                output = builder.build_probe(base, case_id=case.case_id)
                stub = output[
                    builder.STUB_OFFSET:builder.STUB_OFFSET + builder.STUB_SIZE
                ]
                self.assertEqual(
                    output[builder.HOOK_OFFSET:builder.HOOK_OFFSET + 4],
                    builder.encode_thumb_bl(builder.HOOK, builder.STUB),
                )
                self.assertEqual(
                    stub[
                        builder.SOUND_MAIN_CALLSITE - builder.STUB:
                        builder.SOUND_MAIN_CALLSITE - builder.STUB + 4
                    ],
                    builder.encode_thumb_bl(
                        builder.SOUND_MAIN_CALLSITE, builder.SOUND_MAIN
                    ),
                )
                self.assertEqual(
                    stub[
                        builder.RESET_CALLSITE - builder.STUB:
                        builder.RESET_CALLSITE - builder.STUB + 4
                    ],
                    builder.encode_thumb_bl(
                        builder.RESET_CALLSITE, builder.RESOURCE_ALLOCATOR_RESET
                    ),
                )
                reset_args = struct.unpack_from(
                    "<7H", stub, builder.RESET_ARGS_OFFSET
                )
                self.assertEqual(
                    reset_args,
                    builder.encode_allocator_reset_arguments(case),
                )
                selector_offset = case.selector_callsite - builder.STUB
                self.assertEqual(
                    stub[selector_offset - 2:selector_offset],
                    struct.pack("<H", 0x2000 | case.sequence_id),
                )
                self.assertEqual(
                    stub[selector_offset + 4:selector_offset + 6],
                    struct.pack("<H", 0x6060),
                )
                self.assertEqual(
                    stub[selector_offset:selector_offset + 4],
                    builder.encode_thumb_bl(case.selector_callsite, builder.SEQUENCE_SELECTOR),
                )
                spawn_offset = case.spawn_callsite - builder.STUB
                self.assertEqual(
                    struct.unpack_from("<3H", stub, spawn_offset - 6),
                    builder.encode_spawn_arguments(case),
                )
                self.assertEqual(
                    stub[spawn_offset:spawn_offset + 4],
                    builder.encode_thumb_bl(case.spawn_callsite, case.spawn_function),
                )
                done_offset = spawn_offset + 4
                self.assertEqual(
                    struct.unpack_from("<3H", stub, done_offset),
                    (0xBC10, 0xBC01, 0x4700),
                )
                branch_halfword = struct.unpack_from(
                    "<H", stub, builder.DONE_BRANCH_OFFSET
                )[0]
                self.assertEqual(
                    builder.decode_conditional_branch_target(
                        builder.DONE_BRANCH_OFFSET, branch_halfword
                    ),
                    done_offset,
                )
                self.assertEqual(len(output), len(base))

    def test_group3_covers_both_sides_with_noncentral_x_and_wide_allocator(self):
        builder = importlib.import_module(
            "tools.build_controlled_battle_effect_direct_spawn_probe"
        )

        group3 = [case for case in builder.CASES if case.group_id == 3]
        self.assertEqual([case.side for case in group3], [0, 1])
        self.assertTrue(all(case.spawn_x != 120 for case in group3))
        self.assertTrue(all(case.allocator_tile_start == 0x100 for case in group3))
        self.assertTrue(all(case.allocator_tile_end == 0x39F for case in group3))
        self.assertTrue(all(case.allocator_palette_start == 4 for case in group3))
        self.assertTrue(all(case.allocator_palette_end == 14 for case in group3))
        self.assertGreaterEqual(
            group3[0].allocator_tile_end - group3[0].allocator_tile_start + 1,
            304,
        )

        group18 = [case for case in builder.CASES if case.group_id == 18]
        self.assertTrue(all(case.allocator_tile_start == 0x300 for case in group18))
        self.assertTrue(all(case.allocator_tile_end == 0x37F for case in group18))
        self.assertTrue(all(case.allocator_palette_start == 12 for case in group18))
        self.assertTrue(all(case.allocator_palette_end == 14 for case in group18))

    def test_rejects_unknown_case_and_noncanonical_base(self):
        builder = importlib.import_module(
            "tools.build_controlled_battle_effect_direct_spawn_probe"
        )
        base = (ROOT / "rom/base.gba").read_bytes()

        with self.assertRaises(ValueError):
            builder.build_probe(base, case_id="group-99-sequence-99-direct-spawn")
        with self.assertRaises(ValueError):
            builder.build_probe(base[:-1] + bytes([base[-1] ^ 1]), case_id=builder.CASES[0].case_id)


if __name__ == "__main__":
    unittest.main()
