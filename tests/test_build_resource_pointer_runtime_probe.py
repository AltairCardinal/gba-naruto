#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_resource_pointer_runtime_probe import (
    HOOK,
    RESOURCE_TABLE,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class ResourcePointerRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_dedicated_call_and_zero_filled_stub(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4))
        allowed.update(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)

    def test_variant_changes_only_selected_descriptor_palette_pointer(self):
        control = build_probe(self.base)
        changed = build_probe(self.base, descriptor_id=2, palette_shift=8)
        target = RESOURCE_TABLE + 2 * 0x10 + 0x0C
        differences = [
            index for index, pair in enumerate(zip(control, changed))
            if pair[0] != pair[1]
        ]
        self.assertTrue(differences)
        self.assertLessEqual(set(differences), set(range(target, target + 4)))
        self.assertEqual(
            int.from_bytes(changed[target:target + 4], "little"),
            0x08170F98,
        )

    def test_rejects_out_of_range_descriptor_and_palette_shift(self):
        with self.assertRaisesRegex(ValueError, "descriptor ID"):
            build_probe(self.base, descriptor_id=5, palette_shift=8)
        with self.assertRaisesRegex(ValueError, "palette shift"):
            build_probe(self.base, descriptor_id=0, palette_shift=24)


if __name__ == "__main__":
    unittest.main()
