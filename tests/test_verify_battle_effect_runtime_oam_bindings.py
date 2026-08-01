import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerifyBattleEffectRuntimeOamBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_runtime_oam_bindings import export_bindings

        cls.temporary = tempfile.TemporaryDirectory()
        cls.bindings_path = Path(cls.temporary.name) / "bindings.json"
        export_bindings(ROOT, cls.bindings_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_independently_reconstructs_all_tracked_and_supplemental_matches(self):
        from tools.verify_battle_effect_runtime_oam_bindings import verify_bindings

        report = verify_bindings(ROOT, self.bindings_path)

        self.assertEqual(
            {
                "verified": True,
                "errors": [],
                "tracked_checkpoints": 93,
                "tracked_matches": 3,
                "supplemental_states": 5,
                "supplemental_matches": 9,
                "observed_group_ids": [1, 2, 5, 11, 14],
            },
            report,
        )

    def test_verifier_does_not_import_exporter(self):
        source = (
            ROOT / "tools/verify_battle_effect_runtime_oam_bindings.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("export_battle_effect_runtime_oam_bindings", source)

    def test_rejects_semantic_candidate_tampering(self):
        from tools.verify_battle_effect_runtime_oam_bindings import verify_bindings

        value = json.loads(self.bindings_path.read_text(encoding="utf-8"))
        state = next(
            item for item in value["tracked_checkpoints"] if item["matches"]
        )
        state["matches"][0]["best_candidates"][0]["frame_id"] = 0
        tampered = Path(self.temporary.name) / "tampered.json"
        tampered.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

        report = verify_bindings(ROOT, tampered)

        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
