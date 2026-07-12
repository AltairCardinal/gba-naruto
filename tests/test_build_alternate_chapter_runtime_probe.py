import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_alternate_chapter_runtime_probe import (  # noqa: E402
    SELECTOR_OFFSET,
    build_probe,
)
from tools.build_chapter_script_probe import (  # noqa: E402
    HOOK,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
)


class AlternateChapterRuntimeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom" / "base.gba").read_bytes()

    def test_changes_only_selector_hook_and_diagnostic_stub(self):
        patched = build_probe(self.base)
        changed = {i for i, pair in enumerate(zip(self.base, patched)) if pair[0] != pair[1]}
        hook_offset = HOOK - ROM_BASE
        allowed = (
            set(range(SELECTOR_OFFSET, SELECTOR_OFFSET + 2))
            | set(range(hook_offset, hook_offset + 4))
            | set(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        )
        self.assertEqual(len(patched), len(self.base))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)

    def test_rejects_selector_mismatch(self):
        modified = bytearray(self.base)
        modified[SELECTOR_OFFSET] ^= 1
        with self.assertRaisesRegex(ValueError, "selector branch"):
            build_probe(bytes(modified))


if __name__ == "__main__":
    unittest.main()
