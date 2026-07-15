#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_levels_runtime_probe import (
    ACTIVATION_OFFSET,
    HOOK,
    LEVELS_TABLE,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    TARGET_RECORD_ID,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class LevelsRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_call_and_stub_without_rom_slot_activation(self):
        output = build_probe(self.base)
        differences = {
            index
            for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4))
        allowed.update(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)
        self.assertEqual(
            output[ACTIVATION_OFFSET:ACTIVATION_OFFSET + 4],
            self.base[ACTIVATION_OFFSET:ACTIVATION_OFFSET + 4],
        )

    def test_variant_changes_only_target_record_base_a(self):
        control = build_probe(self.base)
        variant = build_probe(self.base, base_a=6)
        target = LEVELS_TABLE + TARGET_RECORD_ID * 12 + 2
        differences = {
            index
            for index, pair in enumerate(zip(control, variant))
            if pair[0] != pair[1]
        }
        self.assertEqual(differences, {target})

    def test_rejects_out_of_range_base_a(self):
        with self.assertRaisesRegex(ValueError, "u16"):
            build_probe(self.base, base_a=0x10000)


if __name__ == "__main__":
    unittest.main()
