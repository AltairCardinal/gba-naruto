import hashlib
import unittest
from pathlib import Path

from tools import build_controlled_battle_effect_allocator_reset_probe as probe


ROOT = Path(__file__).resolve().parent.parent


class ControlledBattleEffectAllocatorResetProbeTests(unittest.TestCase):
    def test_resets_the_natural_resource_window_before_the_same_binder_boundary(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        changed = probe.build_probe(base, sequence_id=17, side=1)

        stub = changed[probe.STUB_OFFSET:probe.STUB_OFFSET + probe.STUB_SIZE]
        self.assertEqual(
            changed[probe.HOOK_OFFSET:probe.HOOK_OFFSET + 4],
            probe.encode_thumb_bl(probe.HOOK, probe.STUB),
        )
        self.assertEqual(
            stub[probe.RESET_CALL_OFFSET:probe.RESET_CALL_OFFSET + 4],
            probe.encode_thumb_bl(
                probe.STUB + probe.RESET_CALL_OFFSET,
                probe.RESOURCE_ALLOCATOR_RESET,
            ),
        )
        self.assertEqual(
            stub[probe.BINDER_ARGUMENT_OFFSET:probe.BINDER_ARGUMENT_OFFSET + 4],
            (0x2001).to_bytes(2, "little") + (0x2111).to_bytes(2, "little"),
        )
        self.assertEqual(
            probe.STUB + probe.BINDER_RETURN_OFFSET,
            probe.BINDER_RETURN,
        )
        self.assertEqual(
            stub[probe.BINDER_CALL_OFFSET:probe.BINDER_CALL_OFFSET + 4],
            probe.encode_thumb_bl(
                probe.STUB + probe.BINDER_CALL_OFFSET,
                probe.SEQUENCE_BINDER,
            ),
        )
        diffs = [
            index
            for index, (original, patched) in enumerate(zip(base, changed))
            if original != patched
        ]
        self.assertTrue(all(
            probe.HOOK_OFFSET <= index < probe.HOOK_OFFSET + 4
            or probe.STUB_OFFSET <= index < probe.STUB_OFFSET + probe.STUB_SIZE
            for index in diffs
        ))

    def test_side_is_a_single_valid_battle_side(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        for side in (-1, 2):
            with self.subTest(side=side), self.assertRaisesRegex(ValueError, "side"):
                probe.build_probe(base, sequence_id=17, side=side)

    def test_fails_closed_on_wrong_rom_or_occupied_stub(self):
        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[0] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM SHA-1"):
            probe.build_probe(bytes(base), sequence_id=17, side=0)

        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[probe.STUB_OFFSET] = 1
        old = probe.BASE_SHA1
        probe.BASE_SHA1 = hashlib.sha1(base).hexdigest()
        try:
            with self.assertRaisesRegex(ValueError, "stub region"):
                probe.build_probe(bytes(base), sequence_id=17, side=0)
        finally:
            probe.BASE_SHA1 = old


if __name__ == "__main__":
    unittest.main()
