import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/motion-effect-parameter-pixel-ab-v1"


class VerifyMotionEffectParameterPixelAbTests(unittest.TestCase):
    def test_verifier_is_independent_of_builder_and_exporter(self):
        source = (ROOT / "tools/verify_motion_effect_parameter_pixel_ab.py").read_text(
            encoding="utf-8"
        )
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
        self.assertNotIn("tools.build_motion_effect_parameter_pixel_ab", imports)
        self.assertNotIn("tools.export_motion_effect_parameter_pixel_ab", imports)

    def test_verifies_the_promoted_artifact(self):
        from tools.verify_motion_effect_parameter_pixel_ab import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])
        self.assertTrue(result["natural_gameplay_route"])
        self.assertEqual(result["record_id"], 0)
        self.assertEqual(result["field"], "y_offset")

    def test_rejects_resigned_memory_allowlist_tampering(self):
        from tools.verify_motion_effect_parameter_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / "artifact"
            shutil.copytree(ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime"]["memory_differences"]["ack-post"]["hardware-oam.bin"] = [0, 1]
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest["repository_files"] = {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in manifest["repository_files"]
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            result = verify_evidence(ROOT, altered)
        self.assertFalse(result["verified"])

    def test_rejects_resigned_scope_overclaim(self):
        from tools.verify_motion_effect_parameter_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / "artifact"
            shutil.copytree(ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["scope"]["all_records_runtime_verified"] = True
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest["repository_files"] = {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in manifest["repository_files"]
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            result = verify_evidence(ROOT, altered)
        self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
