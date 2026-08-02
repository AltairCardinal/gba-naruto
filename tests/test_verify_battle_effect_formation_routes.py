import copy
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectFormationRouteVerificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.analyze_battle_effect_formation_routes import (
            build_battle_effect_formation_route_manifest,
        )

        cls.manifest = build_battle_effect_formation_route_manifest(ROOT)

    def _verify(self, manifest):
        from tools.verify_battle_effect_formation_routes import verify_manifest

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return verify_manifest(ROOT, path)

    def test_accepts_the_complete_original_formation_inventory(self):
        result = self._verify(self.manifest)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["verified_record_count"], 1728)
        self.assertEqual(result["verified_action_count"], 87)

    def test_rejects_a_fabricated_action_32_formation_route(self):
        tampered = copy.deepcopy(self.manifest)
        tampered["actions"]["32"]["formation_records"] = ["g08_v0_r00"]
        tampered["actions"]["32"]["formation_record_count"] = 1
        tampered["actions"]["32"]["formation_occurrence_count"] = 1
        result = self._verify(tampered)
        self.assertTrue(result["errors"])

    def test_rejects_a_changed_primary_action_slot(self):
        tampered = copy.deepcopy(self.manifest)
        tampered["records"]["g08_v0_r00"]["primary_action_slot_ids"][0] = 32
        result = self._verify(tampered)
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
