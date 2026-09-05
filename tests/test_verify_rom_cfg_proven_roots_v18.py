#!/usr/bin/env python3
"""Independent verifier contracts for CFG proven-roots v18."""

import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-cfg-proven-roots-v18"


class CfgProvenRootsV18VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import verify_rom_cfg_proven_roots_v18 as verifier
        cls.verifier = verifier

    def test_independent_verifier_does_not_import_product(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v18.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_cfg_proven_roots_v18" in ast.unparse(node) for node in imports))

    def test_official_artifact_rebuilds_from_raw_inputs(self) -> None:
        report = self.verifier.verify_root(ROOT, ARTIFACT)
        self.assertTrue(report["verified"])
        self.assertEqual((2, 4, 1482, 4), tuple(report[key] for key in ("root_count", "accepted_producer_count", "promotion_bytes", "preserved_unknown_gap_count")))

    def test_payload_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "artifact"
            shutil.copytree(ARTIFACT, target)
            payload_path = target / "rom-cfg-proven-roots-v18.json"
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 2
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_root(ROOT, target)["verified"])


if __name__ == "__main__":
    unittest.main()
