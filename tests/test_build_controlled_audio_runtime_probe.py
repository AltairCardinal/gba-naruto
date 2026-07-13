import unittest
from pathlib import Path

from tools.build_controlled_audio_runtime_probe import (
    HOOK,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parent.parent


class ControlledAudioRuntimeProbeTests(unittest.TestCase):
    def test_builds_checked_init_then_sound_dispatch_probe(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        probe = build_probe(base, sound_id=101)

        self.assertEqual(len(probe), len(base))
        self.assertNotEqual(
            probe[HOOK - ROM_BASE:HOOK - ROM_BASE + 4],
            base[HOOK - ROM_BASE:HOOK - ROM_BASE + 4],
        )
        self.assertEqual(
            probe[STUB_OFFSET + 6:STUB_OFFSET + 8],
            (0x2065).to_bytes(2, "little"),
        )
        changed = [
            i for i, (original, patched) in enumerate(zip(base, probe))
            if original != patched
        ]
        self.assertTrue(all(
            HOOK - ROM_BASE <= i < HOOK - ROM_BASE + 4
            or STUB_OFFSET <= i < STUB_OFFSET + STUB_SIZE
            for i in changed
        ))

    def test_rejects_sound_ids_that_do_not_fit_the_public_dispatcher(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        with self.assertRaisesRegex(ValueError, "sound ID"):
            build_probe(base, sound_id=256)

    def test_can_dispatch_two_cues_before_the_first_soundmain(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        probe = build_probe(base, sound_ids=(101, 106))

        self.assertEqual(
            probe[STUB_OFFSET + 6:STUB_OFFSET + 8],
            (0x2065).to_bytes(2, "little"),
        )
        self.assertEqual(
            probe[STUB_OFFSET + 12:STUB_OFFSET + 14],
            (0x206A).to_bytes(2, "little"),
        )
        changed = [
            i for i, (original, patched) in enumerate(zip(base, probe))
            if original != patched
        ]
        self.assertTrue(all(
            HOOK - ROM_BASE <= i < HOOK - ROM_BASE + 4
            or STUB_OFFSET <= i < STUB_OFFSET + 22
            for i in changed
        ))


if __name__ == "__main__":
    unittest.main()
