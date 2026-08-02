import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectFormationRouteAnalysisTest(unittest.TestCase):
    def _analysis(self):
        from tools.analyze_battle_effect_formation_routes import (
            build_battle_effect_formation_route_manifest,
        )

        return build_battle_effect_formation_route_manifest(ROOT)

    def test_scans_the_complete_formation_matrix_from_the_baseline_rom(self):
        result = self._analysis()
        self.assertEqual(result["formation_matrix"]["record_count"], 48 * 3 * 12)
        self.assertEqual(result["formation_matrix"]["record_stride"], 0xB8)
        self.assertEqual(result["formation_matrix"]["primary_action_slots_per_record"], 15)
        self.assertEqual(result["formation_matrix"]["bank_raw_mismatches"], [])

    def test_action_32_has_no_original_formation_route(self):
        result = self._analysis()
        action = result["actions"]["32"]
        self.assertEqual(action["display_name"], "雷切")
        self.assertEqual(action["sequence_ids"], [14])
        self.assertEqual(action["resource_group_ids"], [12])
        self.assertEqual(action["formation_occurrence_count"], 0)
        self.assertEqual(action["formation_records"], [])

    def test_battle_8_kakashi_record_excludes_action_32(self):
        result = self._analysis()
        record = result["records"]["g08_v0_r00"]
        self.assertEqual(record["selector"], 7)
        self.assertEqual(record["primary_action_ids"], [1, 2, 3, 5, 29, 30, 31])
        self.assertNotIn(32, record["primary_action_ids"])

    def test_group_12_is_explicitly_unavailable_via_static_formations(self):
        result = self._analysis()
        group = result["groups"]["12"]
        self.assertEqual(group["active_action_ids"], [32])
        self.assertEqual(group["formation_action_ids"], [])
        self.assertEqual(group["formation_record_count"], 0)
        self.assertFalse(group["has_original_formation_action_route"])


if __name__ == "__main__":
    unittest.main()
