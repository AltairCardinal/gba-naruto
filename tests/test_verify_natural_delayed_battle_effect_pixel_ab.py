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


class VerifyNaturalDelayedBattleEffectPixelAbTests(unittest.TestCase):
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
