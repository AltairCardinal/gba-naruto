import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from build_save_group_runtime_probe import SCRATCH, STUB_OFFSET, build_probe


class SaveGroupRuntimeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_embeds_scratch_and_only_uses_zero_stub(self):
        output = build_probe(self.base)
        window = output[STUB_OFFSET:STUB_OFFSET + 128]
        self.assertIn(SCRATCH.to_bytes(4, "little"), window)
        self.assertNotEqual(output, self.base)

    def test_rejects_modified_base(self):
        changed = bytearray(self.base)
        changed[1] ^= 1
        with self.assertRaises(ValueError):
            build_probe(bytes(changed))


if __name__ == "__main__":
    unittest.main()
