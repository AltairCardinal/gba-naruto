from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group5-pixel-ab-v1"


class VerifyBattleEffectGroup5PixelAbEvidenceTests(unittest.TestCase):
    def test_promoted_json_contains_no_absolute_paths(self):
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)

        for path in ARTIFACT.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            absolute = [value for value in strings(payload) if value.startswith("/")]
            self.assertEqual([], absolute, path)

    def test_verifier_does_not_import_the_builder_or_exporter(self):
        source = (
            ROOT / "tools/verify_battle_effect_group5_pixel_ab_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.build_battle_effect_group5_pixel_ab",
            source,
        )
        self.assertNotIn(
            "from tools.export_battle_effect_group5_pixel_ab_evidence",
            source,
        )

    def test_verifies_promoted_artifact(self):
        from tools.verify_battle_effect_group5_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_rejects_resigned_semantic_tampering(self):
        from tools.verify_battle_effect_group5_pixel_ab_evidence import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime"]["pixels"]["changes"][0]["after_rgb"] = [0, 0, 0]
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["payload_sha256"] = digest
            manifest["files"]["runtime-evidence.json"] = digest
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_evidence(ROOT, copied)["verified"])


if __name__ == "__main__":
    unittest.main()
