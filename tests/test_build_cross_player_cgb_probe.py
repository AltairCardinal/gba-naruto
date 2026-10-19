import struct
import unittest
from pathlib import Path

from tools.build_cross_player_cgb_probe import (
    HOOK,
    MASTER_OFFSET,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parent.parent


class CrossPlayerCgbProbeTests(unittest.TestCase):
    def test_clones_noise_cue_to_player_one_and_dispatches_both_players(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        probe = build_probe(
            base, source_sound_id=144, clone_sound_id=143, clone_player_slot=1
        )

        source = MASTER_OFFSET + 144 * 8
        clone = MASTER_OFFSET + 143 * 8
        self.assertEqual(probe[clone:clone + 4], probe[source:source + 4])
        self.assertEqual(struct.unpack_from("<H", probe, clone + 4)[0], 1)
        self.assertEqual(struct.unpack_from("<H", probe, clone + 6)[0], 1)
        self.assertEqual(
            probe[STUB_OFFSET + 6:STUB_OFFSET + 8],
            (0x208F).to_bytes(2, "little"),
        )
        self.assertEqual(
            probe[STUB_OFFSET + 12:STUB_OFFSET + 14],
            (0x2090).to_bytes(2, "little"),
        )
        changed = [
            index
            for index, (original, patched) in enumerate(zip(base, probe))
            if original != patched
        ]
        self.assertTrue(all(
            HOOK - ROM_BASE <= index < HOOK - ROM_BASE + 4
            or STUB_OFFSET <= index < STUB_OFFSET + STUB_SIZE
            or clone <= index < clone + 8
            for index in changed
        ))

    def test_rejects_using_the_same_master_entry_as_source_and_clone(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        with self.assertRaisesRegex(ValueError, "clone"):
            build_probe(
                base, source_sound_id=144, clone_sound_id=144,
                clone_player_slot=1,
            )


if __name__ == "__main__":
    unittest.main()
