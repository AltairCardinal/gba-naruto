import unittest
from pathlib import Path

from tools.build_natural_save_runtime_probe import HOOK, ROM_BASE, SCRATCH, STUB_OFFSET, build_probe

ROOT = Path(__file__).resolve().parent.parent


class NaturalSaveRuntimeProbeTest(unittest.TestCase):
    def test_patch_is_contained_to_checked_call_and_zero_cave(self):
        base = (ROOT/'rom/base.gba').read_bytes(); probe = build_probe(base)
        changed = [i for i,(a,b) in enumerate(zip(base,probe)) if a!=b]
        self.assertEqual(len(probe),len(base))
        self.assertTrue(all(HOOK-ROM_BASE <= i < HOOK-ROM_BASE+4 or STUB_OFFSET <= i < STUB_OFFSET+32 for i in changed))
        self.assertEqual(int.from_bytes(probe[STUB_OFFSET+28:STUB_OFFSET+32],'little'),SCRATCH)


if __name__ == '__main__': unittest.main()
