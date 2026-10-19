#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_battle_message_runtime_probe import (
    HOOK,
    MESSAGE_TABLE,
    ROM_BASE,
    STUB_OFFSET,
    STUB_SIZE,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleMessageRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_control_changes_only_selector_hook_and_stub(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(HOOK - ROM_BASE, HOOK - ROM_BASE + 4))
        allowed.update(range(STUB_OFFSET, STUB_OFFSET + STUB_SIZE))
        self.assertTrue(differences)
        self.assertLessEqual(differences, allowed)

    def test_variant_changes_only_selected_message_pointer(self):
        control = build_probe(self.base)
        changed = build_probe(self.base, message_id=12, replacement_id=45)
        target = MESSAGE_TABLE + 12 * 4
        differences = [
            index for index, pair in enumerate(zip(control, changed))
            if pair[0] != pair[1]
        ]
        self.assertTrue(differences)
        self.assertLessEqual(set(differences), set(range(target, target + 4)))
        self.assertEqual(
            changed[target:target + 4],
            self.base[MESSAGE_TABLE + 45 * 4:MESSAGE_TABLE + 46 * 4],
        )

    def test_rejects_message_ids_outside_table(self):
        with self.assertRaisesRegex(ValueError, "message ID"):
            build_probe(self.base, message_id=79, replacement_id=45)


if __name__ == "__main__":
    unittest.main()
