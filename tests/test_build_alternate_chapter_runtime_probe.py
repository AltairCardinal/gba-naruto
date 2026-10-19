import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_alternate_chapter_runtime_probe import (  # noqa: E402
    DISPATCH_HOOK,
    DISPATCH_STUB_OFFSET,
    DISPATCH_STUB_SIZE,
    SELECTOR_CAPTURE_HOOK,
    SELECTOR_OFFSET,
    SELECTOR_STUB_OFFSET,
    SELECTOR_STUB_SIZE,
    build_probe,
)

ROM_BASE = 0x08000000


class AlternateChapterRuntimeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom" / "base.gba").read_bytes()

    def test_changes_only_selector_hook_and_diagnostic_stub(self):
        patched = build_probe(self.base)
        changed = {i for i, pair in enumerate(zip(self.base, patched)) if pair[0] != pair[1]}
        allowed = (
            set(range(SELECTOR_OFFSET, SELECTOR_OFFSET + 2))
            | set(range(SELECTOR_CAPTURE_HOOK - ROM_BASE, SELECTOR_CAPTURE_HOOK - ROM_BASE + 4))
            | set(range(DISPATCH_HOOK - ROM_BASE, DISPATCH_HOOK - ROM_BASE + 4))
            | set(range(SELECTOR_STUB_OFFSET, SELECTOR_STUB_OFFSET + SELECTOR_STUB_SIZE))
            | set(range(DISPATCH_STUB_OFFSET, DISPATCH_STUB_OFFSET + DISPATCH_STUB_SIZE))
        )
        self.assertEqual(len(patched), len(self.base))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)

    def test_patches_selector_capture_and_generic_dispatch_hooks(self):
        patched = build_probe(self.base)
        for hook in (SELECTOR_CAPTURE_HOOK, DISPATCH_HOOK):
            offset = hook - ROM_BASE
            self.assertNotEqual(patched[offset:offset + 4], self.base[offset:offset + 4])

        scenario_39 = int.from_bytes(self.base[0x60D54 + 39 * 4:0x60D58 + 39 * 4], "little")
        self.assertEqual(scenario_39, 0x08031281)
        script = self.base[scenario_39 - ROM_BASE:0x0803142F - ROM_BASE]
        self.assertNotIn(0x1A, script)

    def test_natural_mode_preserves_primary_alternate_selector_branch(self):
        patched = build_probe(self.base, force_alternate=False)
        self.assertEqual(
            patched[SELECTOR_OFFSET:SELECTOR_OFFSET + 2],
            self.base[SELECTOR_OFFSET:SELECTOR_OFFSET + 2],
        )
        for hook in (SELECTOR_CAPTURE_HOOK, DISPATCH_HOOK):
            offset = hook - ROM_BASE
            self.assertNotEqual(patched[offset:offset + 4], self.base[offset:offset + 4])

    def test_rejects_selector_mismatch(self):
        modified = bytearray(self.base)
        modified[SELECTOR_OFFSET] ^= 1
        with self.assertRaisesRegex(ValueError, "selector branch"):
            build_probe(bytes(modified))


if __name__ == "__main__":
    unittest.main()
