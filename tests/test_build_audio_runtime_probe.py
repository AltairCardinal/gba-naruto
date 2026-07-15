import unittest
from pathlib import Path

from tools.build_audio_runtime_probe import HOOK, ROM_BASE, SCRATCH, STUB, STUB_OFFSET, build_probe

ROOT = Path(__file__).resolve().parent.parent


class AudioRuntimeProbeTest(unittest.TestCase):
    def test_builds_checked_non_destructive_probe(self):
        base = (ROOT / "rom/base.gba").read_bytes()
        probe = build_probe(base)
        self.assertEqual(len(probe), len(base))
        self.assertNotEqual(probe[HOOK - ROM_BASE:HOOK - ROM_BASE + 4], base[HOOK - ROM_BASE:HOOK - ROM_BASE + 4])
        self.assertEqual(int.from_bytes(probe[STUB_OFFSET + 0x30:STUB_OFFSET + 0x34], "little"), SCRATCH)
        changed = [i for i, (a, b) in enumerate(zip(base, probe)) if a != b]
        self.assertTrue(all(HOOK - ROM_BASE <= i < HOOK - ROM_BASE + 4 or STUB_OFFSET <= i < STUB_OFFSET + 56 for i in changed))


if __name__ == "__main__":
    unittest.main()
