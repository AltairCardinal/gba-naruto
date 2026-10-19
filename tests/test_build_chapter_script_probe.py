import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from build_chapter_script_probe import HOOK, ROM_BASE, SCRATCH, STUB_OFFSET, build_probe


class ChapterScriptProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_probe_changes_only_hook_and_zero_filled_stub(self):
        output = build_probe(self.base)
        changed = [i for i, (before, after) in enumerate(zip(self.base, output)) if before != after]
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4)) | set(range(STUB_OFFSET, STUB_OFFSET + 36))
        self.assertTrue(set(changed) <= allowed)
        self.assertIn(SCRATCH.to_bytes(4, "little"), output[STUB_OFFSET:STUB_OFFSET + 36])
        self.assertNotEqual(hashlib.sha256(output).digest(), hashlib.sha256(self.base).digest())

    def test_rejects_non_base_rom(self):
        changed = bytearray(self.base)
        changed[0x100] ^= 1
        with self.assertRaises(ValueError):
            build_probe(bytes(changed))


if __name__ == "__main__":
    unittest.main()
