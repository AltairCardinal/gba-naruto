from __future__ import annotations

import ast
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group03-natural-pixel-ab-v1"
ARTIFACT_GROUP18 = ROOT / "artifacts/battle-effect-group18-natural-pixel-ab-v1"


class VerifyNaturalDelayedBattleEffectPixelAbTests(unittest.TestCase):
    def test_group18_pixel_locks_checkpoint_verifier_dependencies(self):
        from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence

        manifest = json.loads(
            (ARTIFACT_GROUP18 / "manifest.json").read_text(encoding="utf-8")
        )
        required = {
            "tools/verify_battle_effect_natural_checkpoint.py",
            "tools/verify_battlefield_object_producers.py",
        }
        self.assertTrue(required.issubset(manifest["repository_files"]))

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT_GROUP18, altered)
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["repository_files"][
                "tools/verify_battle_effect_natural_checkpoint.py"
            ] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, altered)
        self.assertFalse(result["verified"])

    def test_verifier_is_independent_of_builder_and_exporter(self):
        source = (
            ROOT / "tools/verify_natural_delayed_battle_effect_pixel_ab.py"
        ).read_text(encoding="utf-8")
        imports = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
        }
        imports.update(
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertNotIn(
            "tools.build_natural_delayed_battle_effect_pixel_ab", imports
        )
        self.assertNotIn(
            "tools.export_natural_delayed_battle_effect_pixel_ab", imports
        )

    def test_verifies_promoted_natural_pixel_artifact(self):
        from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual(result["group_id"], 3)
        self.assertTrue(result["natural_gameplay_route"])

    def test_verifies_group18_explicit_sequence_pixel_artifact(self):
        from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT_GROUP18)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual(result["group_id"], 18)
        self.assertTrue(result["natural_gameplay_route"])

    def test_rejects_resigned_group18_input_sequence_tampering(self):
        from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT_GROUP18, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["input"]["inputs"][0]["down_frame"] = 19
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest["repository_files"] = {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in manifest["repository_files"]
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, artifact)
        self.assertFalse(result["verified"])

    def test_rejects_resigned_natural_scope_tampering(self):
        from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["scope"]["natural_gameplay_route"] = False
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, altered)
            self.assertFalse(result["verified"])

    def test_rejects_resigned_pixel_count_tampering(self):
        from tools.verify_natural_delayed_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["scope"]["production_natural_pixel_ab"] = "18/18"
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, altered)
            self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
