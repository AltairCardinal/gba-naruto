#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_function_pointer_runtime_probe import (
    HOOKS,
    POINTER_TABLE,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    TRACE_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class FunctionPointerRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_dispatcher_calls_and_zero_filled_stub(self):
        self.assertEqual(TRACE_SIZE, 40)
        output = build_probe(self.base)
        differences = {
            index
            for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        for hook in HOOKS:
            allowed.update(range(hook - ROM_BASE, hook - ROM_BASE + 4))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)

    def test_variant_changes_only_selected_same_table_pointer(self):
        control = build_probe(self.base)
        variant = build_probe(self.base, callback_id=3, replacement_id=4)
        target = POINTER_TABLE + (3 - 1) * 4
        differences = {
            index
            for index, pair in enumerate(zip(control, variant))
            if pair[0] != pair[1]
        }
        self.assertTrue(differences)
        self.assertLessEqual(differences, set(range(target, target + 4)))
        self.assertEqual(
            variant[target : target + 4],
            self.base[POINTER_TABLE + 3 * 4 : POINTER_TABLE + 4 * 4],
        )

    def test_rejects_incomplete_or_out_of_range_replacement(self):
        with self.assertRaisesRegex(ValueError, "together"):
            build_probe(self.base, callback_id=1)
        with self.assertRaisesRegex(ValueError, "callback ID"):
            build_probe(self.base, callback_id=0, replacement_id=1)
        with self.assertRaisesRegex(ValueError, "replacement ID"):
            build_probe(self.base, callback_id=1, replacement_id=12)


if __name__ == "__main__":
    unittest.main()
