from __future__ import annotations

import ast
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group11-pixel-ab-v1"
GROUP14_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-14-fire-action.json"
GROUP14_ARTIFACT = ROOT / "artifacts/battle-effect-group14-pixel-ab-v1"


class VerifyBattleEffectPixelAbEvidenceTests(unittest.TestCase):
    def test_accepts_active_action_confirmation_checkpoint_contract(self):
        from tools.verify_battle_effect_pixel_ab_evidence import _verify_checkpoint

        profile = json.loads(GROUP14_PROFILE.read_text(encoding="utf-8"))
        _verify_checkpoint(ROOT, profile)

    def test_independent_ledger_uses_production_lowercase_pointer_id(self):
        from tools.verify_battle_effect_pixel_ab_evidence import _ledger

        profile = json.loads(GROUP14_PROFILE.read_text(encoding="utf-8"))
        source = (
            ROOT / profile["source_graphics"]
        ).read_bytes()
        ledger = _ledger(
            profile, profile["source_graphics_sha256"], source
        )

        self.assertEqual(
            ledger[1]["id"], "battle-effect-graphics-000.pointer-59918c"
        )

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

        for artifact in (ARTIFACT, GROUP14_ARTIFACT):
            for path in artifact.rglob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    [],
                    [value for value in strings(payload) if value.startswith("/")],
                    path,
                )

    def test_verifier_does_not_import_builder_or_exporter(self):
        source = (
            ROOT / "tools/verify_battle_effect_pixel_ab_evidence.py"
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
        self.assertNotIn("tools.build_battle_effect_pixel_ab", imports)
        self.assertNotIn("tools.export_battle_effect_pixel_ab_evidence", imports)

    def test_verifies_promoted_artifact(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_verifies_promoted_active_action_artifact(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, GROUP14_ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_rejects_resigned_semantic_tampering(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "artifact"
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

    def test_rejects_resigned_runtime_tool_provenance(self):
        from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence

        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            for variant in ("baseline", "candidate"):
                for name in ("audit.json", "sentinel.json"):
                    path = copied / "raw" / variant / name
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["replay_script_sha256"] = "0" * 64
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                evidence["runs"][variant]["replay_script_sha256"] = "0" * 64
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["payload_sha256"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest["files"] = {
                path.relative_to(copied).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(copied.rglob("*"))
                if path.is_file() and path.name != "manifest.json"
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_evidence(ROOT, copied)["verified"])


if __name__ == "__main__":
    unittest.main()
