from __future__ import annotations

import importlib
import hashlib
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-observed-frame-phases-v1"


class BattleEffectObservedFramePhaseVerifierTests(unittest.TestCase):
    def test_independent_verifier_accepts_production_coverage(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_observed_frame_phases"
        )
        source = inspect.getsource(verifier)
        self.assertNotIn(
            "from tools.export_battle_effect_observed_frame_phases", source
        )
        self.assertNotIn(
            "from export_battle_effect_observed_frame_phases", source
        )
        result = verifier.verify_coverage(ROOT, ARTIFACT)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["verified"])
        self.assertEqual(result["phase_verified_groups"], 10)
        self.assertEqual(result["all_groups"], 18)
        self.assertEqual(result["production_pixel_ab_groups"], 12)

    def test_rejects_observed_group_source_without_matching_parent_manifest(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_observed_frame_phases"
        )
        for field in ("manifest_sha256", "payload_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                artifact = Path(tmp) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                coverage_path = artifact / "coverage.json"
                coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
                coverage["sources"]["observed_task_bindings"][field] = "0" * 64
                coverage_path.write_text(
                    json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                manifest_path = artifact / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"]["coverage.json"] = hashlib.sha256(
                    coverage_path.read_bytes()
                ).hexdigest()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                result = verifier.verify_coverage(ROOT, artifact)
                self.assertIn(
                    "observed group source manifest mismatch", result["errors"]
                )

    def test_rejects_missing_imported_parent_verifier_hash_lock(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_observed_frame_phases"
        )
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["producer"]["repository_files"].pop(
                "tools/verify_battle_effect_runtime_oam_task_bindings.py", None
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_coverage(ROOT, artifact)
            self.assertIn(
                "coverage repository hash lock is incomplete", result["errors"]
            )


if __name__ == "__main__":
    unittest.main()
