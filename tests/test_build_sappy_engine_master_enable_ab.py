import unittest
from pathlib import Path

from tools.build_controlled_audio_runtime_probe import HOOK, ROM_BASE, STUB_OFFSET
from tools.build_sappy_engine_master_enable_ab import (
    CANDIDATE_IMMEDIATE,
    PATCH_OFFSET,
    build_pair,
)


ROOT = Path(__file__).resolve().parent.parent


class SappyEngineMasterEnableAbTests(unittest.TestCase):
    def test_pair_changes_only_the_master_enable_immediate(self):
        base = (ROOT / "rom/base.gba").read_bytes()

        baseline, candidate = build_pair(base, sound_id=101)

        self.assertEqual(baseline[PATCH_OFFSET:PATCH_OFFSET + 2], b"\x8f\x20")
        self.assertEqual(
            candidate[PATCH_OFFSET:PATCH_OFFSET + 2],
            bytes((CANDIDATE_IMMEDIATE, 0x20)),
        )
        self.assertEqual(
            [index for index, pair in enumerate(zip(baseline, candidate)) if pair[0] != pair[1]],
            [PATCH_OFFSET],
        )
        base_to_baseline = {
            index for index, pair in enumerate(zip(base, baseline)) if pair[0] != pair[1]
        }
        self.assertTrue(
            base_to_baseline
            and all(
                HOOK - ROM_BASE <= index < HOOK - ROM_BASE + 4
                or STUB_OFFSET <= index < STUB_OFFSET + 16
                for index in base_to_baseline
            )
        )


if __name__ == "__main__":
    unittest.main()
