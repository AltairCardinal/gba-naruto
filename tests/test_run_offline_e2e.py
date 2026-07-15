#!/usr/bin/env python3
from __future__ import annotations

import unittest

from tools.run_offline_e2e import validate_build_identity, validate_runtime_snapshot


class OfflineE2ETests(unittest.TestCase):
    def test_build_identity_requires_report_sha_to_match_rom(self):
        report = {"output_rom": {"sha1": "abc", "size": 16}}
        self.assertEqual(
            validate_build_identity(report, actual_sha1="abc", actual_size=16),
            {"sha1_matches": True, "size_matches": True},
        )
        with self.assertRaisesRegex(ValueError, "SHA-1"):
            validate_build_identity(report, actual_sha1="def", actual_size=16)

    def test_runtime_snapshot_decodes_tracked_battle_boundary(self):
        snapshot = {
            "memory_dumps": [
                {"address": "0x02026804", "words": ["0x00002900"]},
                {"address": "0x0201BE28", "words": ["0x16092C24"]},
                {"address": "0x02024358", "words": ["0x00000A04"]},
                {"address": "0x0202452C", "words": ["0x00000404"]},
            ]
        }
        self.assertEqual(
            validate_runtime_snapshot(snapshot),
            {
                "battle_id": 41,
                "map": {"width": 36, "height": 44, "grid_width": 9, "grid_height": 22},
                "naruto": {"x": 4, "y": 10},
                "iruka": {"x": 4, "y": 4},
            },
        )

    def test_runtime_snapshot_rejects_wrong_battle(self):
        snapshot = {
            "memory_dumps": [
                {"address": "0x02026804", "words": ["0x00002800"]},
                {"address": "0x0201BE28", "words": ["0x16092C24"]},
                {"address": "0x02024358", "words": ["0x00000A04"]},
                {"address": "0x0202452C", "words": ["0x00000404"]},
            ]
        }
        with self.assertRaisesRegex(ValueError, "battle ID"):
            validate_runtime_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
