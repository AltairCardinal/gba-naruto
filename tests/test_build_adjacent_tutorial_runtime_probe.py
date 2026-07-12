#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_adjacent_tutorial_runtime_probe import (
    IRUKA_RECORD,
    build_probe,
)
from tools.build_battle_message_runtime_probe import build_probe as build_message_probe


ROOT = Path(__file__).resolve().parents[1]


class AdjacentTutorialRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_default_changes_only_iruka_x_and_y(self):
        output = build_probe(self.base)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        self.assertEqual(differences, {IRUKA_RECORD + 2, IRUKA_RECORD + 3})
        self.assertEqual(output[IRUKA_RECORD + 2:IRUKA_RECORD + 4], bytes((5, 10)))

    def test_rejects_out_of_grid_coordinate(self):
        with self.assertRaisesRegex(ValueError, "coordinate"):
            build_probe(self.base, x=9, y=10)

    def test_optional_ally_changes_only_affiliation_and_coordinates(self):
        output = build_probe(self.base, affiliation=0)
        differences = {
            index for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        self.assertEqual(
            differences,
            {IRUKA_RECORD + 1, IRUKA_RECORD + 2, IRUKA_RECORD + 3},
        )

    def test_message_trace_composes_checked_probe_before_formation_patch(self):
        expected = bytearray(build_message_probe(self.base))
        expected[IRUKA_RECORD + 1:IRUKA_RECORD + 4] = bytes((0, 5, 10))
        self.assertEqual(
            build_probe(self.base, affiliation=0, trace="battle-message"),
            bytes(expected),
        )


if __name__ == "__main__":
    unittest.main()
