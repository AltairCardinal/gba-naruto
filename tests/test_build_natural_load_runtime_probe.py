import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_natural_load_runtime_probe import (  # noqa: E402
    HOOK,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


class NaturalLoadRuntimeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom" / "base.gba").read_bytes()

    def test_probe_changes_only_checked_call_and_zero_stub(self):
        patched = build_probe(self.base)
        changed = {index for index, (a, b) in enumerate(zip(self.base, patched)) if a != b}
        hook_offset = HOOK - ROM_BASE
        allowed = set(range(hook_offset, hook_offset + 4)) | set(
            range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE)
        )
        self.assertEqual(len(patched), len(self.base))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)

    def test_rejects_modified_base(self):
        modified = bytearray(self.base)
        modified[0] ^= 1
        with self.assertRaisesRegex(ValueError, "immutable base ROM"):
            build_probe(bytes(modified))


if __name__ == "__main__":
    unittest.main()
