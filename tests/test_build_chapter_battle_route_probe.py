from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_chapter_battle_route_probe import BATTLE_COMMAND_OFFSET, build_probe


ROOT = Path(__file__).resolve().parents[1]


class ChapterBattleRouteProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_changes_only_primary_scenario39_selected_battle_id(self):
        output = build_probe(self.base, battle_id=8)
        self.assertEqual(len(output), len(self.base))
        self.assertEqual(output[BATTLE_COMMAND_OFFSET:BATTLE_COMMAND_OFFSET + 4], b"\x1a\x08\x02\x00")
        differences = [
            index for index, (before, after) in enumerate(zip(self.base, output, strict=True))
            if before != after
        ]
        self.assertEqual(differences, [BATTLE_COMMAND_OFFSET + 1])

    def test_rejects_nonexistent_battle_group(self):
        for battle_id in (-1, 47, 255):
            with self.subTest(battle_id=battle_id), self.assertRaises(ValueError):
                build_probe(self.base, battle_id=battle_id)

    def test_rejects_tampered_source_command(self):
        changed = bytearray(self.base)
        changed[BATTLE_COMMAND_OFFSET + 1] ^= 1
        with self.assertRaises(ValueError):
            build_probe(bytes(changed), battle_id=8, verify_sha1=False)


if __name__ == "__main__":
    unittest.main()
