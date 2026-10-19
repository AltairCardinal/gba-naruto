import json
import subprocess
import sys
import unittest
from pathlib import Path

from tools.analyze_battle_side_start_passives import (
    build_side_start_passive_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleSideStartPassiveAnalysisTest(unittest.TestCase):
    def test_side_start_passive_consumer_is_bound_to_original_rom(self):
        manifest = build_side_start_passive_manifest(
            ROOT / "rom/base.gba"
        )

        self.assertEqual(
            manifest["identity"],
            "battle_side_start_passive_consumers",
        )
        self.assertEqual(
            manifest["controller"]["callsite"],
            "0x080736DE",
        )
        self.assertTrue(
            manifest["controller"]["side_flip_before_call"]
        )
        self.assertEqual(
            manifest["query_priority"],
            ["0x1D", "0x1E", "0x1F", "0x20"],
        )

        nine_tail = manifest["families"]["0x1D"]
        self.assertEqual(nine_tail["passive_id"], 24)
        self.assertEqual(
            nine_tail["trigger"],
            "current_hp <= 9",
        )
        self.assertEqual(
            nine_tail["effects"],
            [
                "hp += value_a, clamped to max_hp",
                "current_chakra = max_chakra",
            ],
        )
        self.assertIsNone(nine_tail["raw_duration"])

        berserk = manifest["families"]["0x1E"]
        self.assertEqual(berserk["passive_id"], 25)
        self.assertEqual(
            berserk["trigger"],
            "current_hp <= 9",
        )
        self.assertEqual(berserk["status_code"], "0x1E")
        self.assertEqual(berserk["raw_duration"], 5)
        self.assertEqual(
            berserk["status_value"],
            "value_a low byte",
        )
        self.assertEqual(berserk["healing"], "value_b")

        inner = manifest["families"]["0x1F"]
        self.assertEqual(inner["passive_id"], 26)
        self.assertEqual(
            inner["trigger"],
            "current_hp <= floor(max_hp / 4)",
        )
        self.assertEqual(inner["status_code"], "0x1E")
        self.assertEqual(inner["raw_duration"], 3)

        unresolved = manifest["families"]["0x20"]
        self.assertEqual(unresolved["passive_id"], 35)
        self.assertEqual(unresolved["battle_id_gate"], 11)
        self.assertEqual(
            unresolved["implementation_status"],
            "withheld_pending_semantics",
        )

        latch = manifest["shared_latch"]
        self.assertEqual(latch["unit_offset"], "0xBE")
        self.assertFalse(
            latch["retrigger_while_below_threshold"]
        )
        self.assertTrue(
            latch["rearm_after_condition_clears"]
        )

    def test_direct_cli_emits_the_same_manifest(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools/analyze_battle_side_start_passives.py"
                ),
                "--rom",
                str(ROOT / "rom/base.gba"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = json.loads(completed.stdout)
        self.assertEqual(
            manifest["identity"],
            "battle_side_start_passive_consumers",
        )


if __name__ == "__main__":
    unittest.main()
