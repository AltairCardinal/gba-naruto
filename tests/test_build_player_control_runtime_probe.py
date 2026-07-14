import hashlib
import unittest
from pathlib import Path

from tools.build_player_control_runtime_probe import (
    BASE_SHA1,
    CURRENT_UNIT_HOOK,
    CURRENT_UNIT_MAGIC,
    CURRENT_UNIT_ORIGINAL,
    CURRENT_UNIT_SCRATCH,
    CURRENT_UNIT_STUB,
    CURRENT_UNIT_STUB_OFFSET,
    HOOK,
    MAGIC,
    ORIGINAL,
    ROM_BASE,
    SCRATCH,
    STUB,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)
from tools.thumb_branch import decode_thumb_bl, encode_thumb_bl
from tests.thumb_observer_machine import execute_stub

ROOT = Path(__file__).resolve().parent.parent


class PlayerControlRuntimeProbeTests(unittest.TestCase):
    def test_checked_call_is_replaced_by_transparent_wrapper(self):
        base = (ROOT / "rom/base.gba").read_bytes()
        probe = build_probe(base)
        hook_offset = HOOK - ROM_BASE

        self.assertEqual(hashlib.sha1(base).hexdigest(), BASE_SHA1)
        self.assertEqual(base[hook_offset : hook_offset + 4], encode_thumb_bl(HOOK, ORIGINAL))
        self.assertEqual(probe[hook_offset : hook_offset + 4], encode_thumb_bl(HOOK, STUB))
        first = int.from_bytes(probe[hook_offset : hook_offset + 2], "little")
        second = int.from_bytes(probe[hook_offset + 2 : hook_offset + 4], "little")
        self.assertEqual(decode_thumb_bl(HOOK, first, second), STUB)

    def test_wrapper_records_magic_count_and_arguments_then_tail_calls_original(self):
        base = (ROOT / "rom/base.gba").read_bytes()
        probe = build_probe(base)
        stub = probe[STUB_OFFSET : STUB_OFFSET + STUB_SIZE]
        initial = {
            "r0": 9,
            "r1": 0x12340000,
            "r2": 0x56780001,
            "r3": 0x33,
            "r4": 0x44,
            "sp": 0x03007E00,
            "lr": HOOK + 5,
        }
        state = execute_stub(
            stub,
            registers=initial,
            memory={0x0203F040: 6},
        )

        self.assertEqual(state.read_u32(SCRATCH), MAGIC)
        self.assertEqual(state.read_u32(SCRATCH + 4), 1)
        self.assertEqual(state.read_u32(SCRATCH + 8), 9)
        self.assertEqual(state.read_u16(SCRATCH + 12), 0)
        self.assertEqual(state.read_u16(SCRATCH + 14), 1)
        self.assertEqual(state.read_u32(SCRATCH + 16), 7)
        for register in ("r0", "r1", "r2", "r3", "r4", "sp", "lr"):
            self.assertEqual(state.registers[register], initial[register])
        self.assertEqual(state.branch_target, ORIGINAL | 1)

    def test_current_unit_call_uses_an_independent_transparent_wrapper(self):
        base = (ROOT / "rom/base.gba").read_bytes()
        probe = build_probe(base)
        hook_offset = CURRENT_UNIT_HOOK - ROM_BASE
        stub = probe[CURRENT_UNIT_STUB_OFFSET : CURRENT_UNIT_STUB_OFFSET + STUB_SIZE]

        self.assertEqual(
            base[hook_offset : hook_offset + 4],
            encode_thumb_bl(CURRENT_UNIT_HOOK, CURRENT_UNIT_ORIGINAL),
        )
        self.assertEqual(
            probe[hook_offset : hook_offset + 4],
            encode_thumb_bl(CURRENT_UNIT_HOOK, CURRENT_UNIT_STUB),
        )
        self.assertEqual(CURRENT_UNIT_STUB, 0x0809E880)
        self.assertEqual(STUB_SIZE, 96)
        self.assertIn(CURRENT_UNIT_SCRATCH.to_bytes(4, "little"), stub)
        self.assertIn(CURRENT_UNIT_MAGIC.to_bytes(4, "little"), stub)
        self.assertIn((CURRENT_UNIT_ORIGINAL | 1).to_bytes(4, "little"), stub)

    def test_patch_is_confined_to_checked_hook_and_zero_filled_cave(self):
        base = (ROOT / "rom/base.gba").read_bytes()
        probe = build_probe(base)
        changed = [index for index, pair in enumerate(zip(base, probe)) if pair[0] != pair[1]]
        hook_offset = HOOK - ROM_BASE

        self.assertEqual(len(probe), len(base))
        self.assertTrue(all(
            hook_offset <= index < hook_offset + 4
            or STUB_OFFSET <= index < STUB_OFFSET + STUB_SIZE
            or CURRENT_UNIT_HOOK - ROM_BASE <= index < CURRENT_UNIT_HOOK - ROM_BASE + 4
            or CURRENT_UNIT_STUB_OFFSET <= index < CURRENT_UNIT_STUB_OFFSET + STUB_SIZE
            for index in changed
        ))

    def test_rejects_wrong_base_call_and_occupied_cave(self):
        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[0] ^= 1
        with self.assertRaisesRegex(ValueError, "immutable base ROM"):
            build_probe(bytes(base))

        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        hook_offset = HOOK - ROM_BASE
        base[hook_offset] ^= 1
        with self.assertRaisesRegex(ValueError, "call-site bytes"):
            build_probe(bytes(base), verify_sha1=False)

        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[STUB_OFFSET] = 1
        with self.assertRaisesRegex(ValueError, "zero-filled"):
            build_probe(bytes(base), verify_sha1=False)

    def test_second_hook_and_cave_must_match(self):
        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[CURRENT_UNIT_HOOK - ROM_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "current-unit call-site"):
            build_probe(bytes(base), verify_sha1=False)

        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[CURRENT_UNIT_STUB - ROM_BASE] = 1
        with self.assertRaisesRegex(ValueError, "current-unit stub region"):
            build_probe(bytes(base), verify_sha1=False)


if __name__ == "__main__":
    unittest.main()
