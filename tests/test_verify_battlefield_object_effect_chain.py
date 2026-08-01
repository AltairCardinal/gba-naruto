import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlefieldObjectEffectChainVerifierTest(unittest.TestCase):
    def _write_manifest(self, directory: Path) -> Path:
        from tools.analyze_battlefield_object_effect_chain import (
            build_battlefield_object_effect_chain_manifest,
        )

        manifest = build_battlefield_object_effect_chain_manifest(
            ROOT, ROOT / "rom/base.gba"
        )
        path = directory / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_accepts_fresh_manifest_by_rechecking_original_rom(self):
        from tools.verify_battlefield_object_effect_chain import verify_manifest

        with tempfile.TemporaryDirectory() as temporary:
            result = verify_manifest(
                ROOT, ROOT / "rom/base.gba", self._write_manifest(Path(temporary))
            )
        self.assertTrue(result["verified"])
        self.assertEqual(result["errors"], [])

    def test_rejects_a_mapping_that_overclaims_natural_runtime(self):
        from tools.verify_battlefield_object_effect_chain import verify_manifest

        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_manifest(Path(temporary))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["natural_runtime_observed"] = True
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify_manifest(ROOT, ROOT / "rom/base.gba", path)
        self.assertFalse(result["verified"])
        self.assertTrue(any("natural_runtime_observed" in error for error in result["errors"]))

    def test_rejects_expanded_or_redirected_handler_mapping(self):
        from tools.verify_battlefield_object_effect_chain import verify_manifest

        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_manifest(Path(temporary))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["mappings"][0]["primary_handler"] = "0x08000001"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify_manifest(ROOT, ROOT / "rom/base.gba", path)
        self.assertFalse(result["verified"])
        self.assertTrue(any("primary_handler" in error for error in result["errors"]))

    def test_rejects_a_rewritten_chain_address(self):
        from tools.verify_battlefield_object_effect_chain import verify_manifest

        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_manifest(Path(temporary))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["chain"]["object_action_read"] = "0x08000000"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify_manifest(ROOT, ROOT / "rom/base.gba", path)
        self.assertFalse(result["verified"])
        self.assertTrue(any("chain" in error for error in result["errors"]))

    def test_rejects_rewritten_source_and_boundary_claims(self):
        from tools.verify_battlefield_object_effect_chain import verify_manifest

        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_manifest(Path(temporary))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["rom"] = "unrelated.gba"
            manifest["source_semantics"] = "tampered.json"
            manifest["boundary"] = "已完成自然 UI、到期和 handler 运行时闭环。"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify_manifest(ROOT, ROOT / "rom/base.gba", path)
        self.assertFalse(result["verified"])
        self.assertTrue(any("source_semantics" in error for error in result["errors"]))
        self.assertTrue(any("boundary" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
