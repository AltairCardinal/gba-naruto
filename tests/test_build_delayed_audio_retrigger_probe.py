import unittest
from pathlib import Path

from tools.build_delayed_audio_retrigger_probe import (
    INIT_HOOK,
    INIT_STUB_OFFSET,
    INIT_STUB_SIZE,
    MAIN_HOOK,
    MAIN_STUB_OFFSET,
    MAIN_STUB_SIZE,
    ROM_BASE,
    build_probe,
)


ROOT = Path(__file__).resolve().parent.parent


class DelayedAudioRetriggerProbeTests(unittest.TestCase):
    def test_uses_the_per_frame_soundmain_wrapper_call(self):
        self.assertEqual(MAIN_HOOK, 0x08061F76)

    def test_builds_checked_active_cue_replacement_probe(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        probe = build_probe(
            base,
            first_sound_id=101,
            replacement_sound_id=102,
            switch_after_invocations=8,
        )

        self.assertEqual(
            probe[INIT_STUB_OFFSET + 8:INIT_STUB_OFFSET + 10],
            (0x2007).to_bytes(2, "little"),
        )
        self.assertEqual(
            probe[INIT_STUB_OFFSET + 12:INIT_STUB_OFFSET + 14],
            (0x2065).to_bytes(2, "little"),
        )
        self.assertEqual(
            probe[MAIN_STUB_OFFSET + 22:MAIN_STUB_OFFSET + 24],
            (0x2066).to_bytes(2, "little"),
        )
        changed = [
            index
            for index, (original, patched) in enumerate(zip(base, probe))
            if original != patched
        ]
        self.assertTrue(all(
            INIT_HOOK - ROM_BASE <= index < INIT_HOOK - ROM_BASE + 4
            or MAIN_HOOK - ROM_BASE <= index < MAIN_HOOK - ROM_BASE + 4
            or INIT_STUB_OFFSET <= index < INIT_STUB_OFFSET + INIT_STUB_SIZE
            or MAIN_STUB_OFFSET <= index < MAIN_STUB_OFFSET + MAIN_STUB_SIZE
            for index in changed
        ))

    def test_rejects_nonpositive_switch_delay(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        with self.assertRaisesRegex(ValueError, "invocations"):
            build_probe(
                base,
                first_sound_id=101,
                replacement_sound_id=102,
                switch_after_invocations=0,
            )


if __name__ == "__main__":
    unittest.main()
