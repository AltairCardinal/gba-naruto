from __future__ import annotations

import ast
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group18-controlled-pixel-ab-v1"
GROUP3_ARTIFACT = ROOT / "artifacts/battle-effect-group03-controlled-pixel-ab-v1"
GROUP6_ARTIFACT = ROOT / "artifacts/battle-effect-group06-controlled-pixel-ab-v1"


class VerifyControlledBattleEffectPixelAbTests(unittest.TestCase):
    def test_independently_verifies_group6_sequence_pixel_writeback(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        result = verify_evidence(ROOT, GROUP6_ARTIFACT)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["verified"])
        self.assertEqual(result["group_id"], 6)
        self.assertEqual(result["sequence_id"], 8)
        self.assertEqual(result["production_modified_rom_pixel_ab"], "13/18")

    def test_verifier_is_independent_of_builder_and_exporter(self):
        source = (
            ROOT / "tools/verify_controlled_battle_effect_pixel_ab.py"
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
        self.assertNotIn("tools.build_controlled_battle_effect_pixel_ab", imports)
        self.assertNotIn("tools.export_controlled_battle_effect_pixel_ab", imports)

    def test_verifies_promoted_controlled_single_pixel_artifact(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_rejects_resigned_scope_tampering(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["scope"]["natural_gameplay_route"] = True
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, altered)
            self.assertFalse(result["verified"])

    def test_rejects_promoting_raw_mgba_capture_to_pixel_ab(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["scope"]["mgba_capture_pixel_ab"] = True
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, altered)
            self.assertFalse(result["verified"])

    def test_raw_tar_rejects_excess_member_count(self):
        from tools.verify_controlled_battle_effect_pixel_ab import _tar_payloads

        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "oversized.tar"
            with tarfile.open(archive_path, "w", format=tarfile.USTAR_FORMAT) as archive:
                for index in range(103):
                    info = tarfile.TarInfo(f"member-{index:03d}")
                    info.size = 0
                    archive.addfile(info, io.BytesIO())
            with self.assertRaisesRegex(ValueError, "member count"):
                _tar_payloads(archive_path, 102)

    def test_verifies_group3_shared_alias_split_pixel_artifact(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        result = verify_evidence(ROOT, GROUP3_ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual(result["group_id"], 3)
        self.assertFalse(result["natural_gameplay_route"])

    def test_group3_rejects_claiming_full_source_palette_equality(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(GROUP3_ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime"]["full_source_palette_equal"] = True
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, altered)
            self.assertFalse(result["verified"])

    def test_group3_rejects_expanding_the_redirect_to_the_group2_alias(self):
        from tools.verify_controlled_battle_effect_pixel_ab import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            altered = Path(temporary) / "artifact"
            shutil.copytree(GROUP3_ARTIFACT, altered)
            evidence_path = altered / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["build"]["pointer_offsets"] = [0x59912C, 0x599134]
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = altered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import hashlib

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
