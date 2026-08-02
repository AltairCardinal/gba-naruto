from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group18-natural-checkpoint-v1"


class BattleEffectNaturalCheckpointVerifierTests(unittest.TestCase):
    def test_accepts_group18_zero_event_checkpoint(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_natural_checkpoint"
        )
        result = verifier.verify_artifact(ARTIFACT)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["group_id"], 18)
        self.assertEqual(result["sequence_id"], 7)
        self.assertEqual(result["object_raw_hex"], "010d0600c300000001000202ac560003")
        self.assertEqual(result["verified_static_selector_paths"], 3)
        self.assertEqual(
            result["verified_source_states"], ["object-created", "first-submit"]
        )

    def test_rejects_checkpoint_contract_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_natural_checkpoint"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["delayed_object"]["remaining_turns"] = 1
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn("delayed object contract mismatch", result["errors"])

    def test_rejects_audit_without_clean_owned_process_tree(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_natural_checkpoint"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            audit_path = artifact / "raw/expiry-route-audit.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["pgid_clean"] = False
            audit_path.write_text(
                json.dumps(audit, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn("expiry-ready process tree is not clean", result["errors"])


if __name__ == "__main__":
    unittest.main()
