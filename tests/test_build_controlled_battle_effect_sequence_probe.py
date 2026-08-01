import hashlib
import unittest
from pathlib import Path

from tools import build_controlled_battle_effect_sequence_probe as probe


ROOT = Path(__file__).resolve().parent.parent


class ControlledBattleEffectSequenceProbeTests(unittest.TestCase):
    def test_builds_one_shot_sequence_dispatch_after_soundmain(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        changed = probe.build_probe(base, sequence_id=14)

        self.assertEqual(len(changed), len(base))
        self.assertEqual(
            changed[probe.HOOK_OFFSET:probe.HOOK_OFFSET + 4],
            probe.encode_thumb_bl(probe.HOOK, probe.STUB),
        )
        self.assertEqual(
            changed[probe.STUB_OFFSET + 20:probe.STUB_OFFSET + 22],
            (0x210E).to_bytes(2, "little"),
        )
        self.assertEqual(
            changed[probe.STUB_OFFSET + 22:probe.STUB_OFFSET + 26],
            probe.encode_thumb_bl(probe.STUB + 22, probe.SEQUENCE_BINDER),
        )
        self.assertEqual(
            changed[probe.STUB_OFFSET + 32:probe.STUB_OFFSET + 36],
            probe.SCRATCH.to_bytes(4, "little"),
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

    def test_rejects_sequence_outside_the_descriptor_table(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        for sequence_id in (0, 22):
            with self.subTest(sequence_id=sequence_id):
                with self.assertRaisesRegex(ValueError, "sequence ID"):
                    probe.build_probe(base, sequence_id=sequence_id)

    def test_fails_closed_on_wrong_rom_or_occupied_stub(self):
        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[0] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM SHA-1"):
            probe.build_probe(bytes(base), sequence_id=14)

        base = bytearray((ROOT / "rom/base.gba").read_bytes())
        base[probe.STUB_OFFSET] = 1
        old = probe.BASE_SHA1
        probe.BASE_SHA1 = hashlib.sha1(base).hexdigest()
        try:
            with self.assertRaisesRegex(ValueError, "stub region"):
                probe.build_probe(bytes(base), sequence_id=14)
        finally:
            probe.BASE_SHA1 = old


if __name__ == "__main__":
    unittest.main()
