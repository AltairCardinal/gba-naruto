import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_skill_runtime_probe import (  # noqa: E402
    HOOK,
    ROM_BASE,
    SKILL_BYTE_04,
    SKILL_2_RECORD,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


class SkillRuntimeProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_hook_and_stub(self):
        output = build_probe(self.base, skill_byte_04=6)
        changed = {i for i, pair in enumerate(zip(self.base, output)) if pair[0] != pair[1]}
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4)) | set(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)

    def test_changed_rom_adds_only_skill_2_byte_04(self):
        control = build_probe(self.base, skill_byte_04=6)
        changed = build_probe(self.base, skill_byte_04=7)
        differences = [i for i, pair in enumerate(zip(control, changed)) if pair[0] != pair[1]]
        self.assertEqual(differences, [SKILL_BYTE_04])
        self.assertEqual(changed[SKILL_BYTE_04], 7)

    def test_rejects_out_of_range_skill_byte(self):
        with self.assertRaisesRegex(ValueError, "u8"):
            build_probe(self.base, skill_byte_04=256)

    def test_ui_field_overrides_change_only_requested_skill_bytes(self):
        control = build_probe(self.base)
        changed = build_probe(self.base, skill_overrides={0: 2, 2: 2, 5: 4, 6: 80})
        differences = [i for i, pair in enumerate(zip(control, changed)) if pair[0] != pair[1]]
        self.assertEqual(differences, [SKILL_2_RECORD + offset for offset in (0, 2, 5, 6)])

    def test_rejects_override_outside_skill_record(self):
        with self.assertRaisesRegex(ValueError, "offset"):
            build_probe(self.base, skill_overrides={16: 1})


if __name__ == "__main__":
    unittest.main()
