#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_verifier():
    try:
        from tools import verify_rom_cfg_proven_roots_v16_consumed_literals as module
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v16 consumed-literals verifier is absent") from error
    return module


class VerifyV16ConsumedLiteralsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()

    def _candidate(self, directory: Path) -> Path:
        target = directory / "candidate"
        result = subprocess.run(
            [sys.executable, "tools/export_rom_cfg_proven_roots_v16_consumed_literals.py", "--root", ".", "--output", str(target)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return target

    def test_independent_raw_rebuild_and_isolated_cli(self):
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            report = self.verifier.verify_root(ROOT, candidate)
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual({"bindings": 51, "unique_target_words": 51, "promotion_bytes": 204}, report["summary"])
            result = subprocess.run(
                [sys.executable, "-I", "-S", "tools/verify_rom_cfg_proven_roots_v16_consumed_literals.py", "--root", ".", "--artifact", str(candidate)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(json.loads(result.stdout)["contract_ok"])

    def test_thumb_decoder_and_literal_formula(self):
        self.assertEqual(4, self.verifier._thumb_instruction_width(bytes.fromhex("00f000f8"), 0, 4))
        self.assertEqual(2, self.verifier._thumb_instruction_width(bytes.fromhex("0048"), 0, 2))
        self.assertEqual(0x110, self.verifier._decode_ldr_literal_target(0x102, 0x4803))

    def test_payload_manifest_foreign_file_and_symlink_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            payload = candidate / "rom-cfg-proven-roots-v16-consumed-literals.json"
            data = json.loads(payload.read_text())
            data["coverage_projection"]["remaining_unknown_bytes"] += 4
            payload.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "payload identity|artifact payload"):
                self.verifier.verify_root(ROOT, candidate)
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            (candidate / "foreign").write_text("no")
            with self.assertRaisesRegex(ValueError, "artifact file set"):
                self.verifier.verify_root(ROOT, candidate)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            candidate = self._candidate(directory)
            alias = directory / "alias"
            alias.symlink_to(candidate, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.verifier.verify_root(ROOT, alias)

    def test_verifier_is_independent_of_exporter_and_generic_decoder(self):
        tree = ast.parse((ROOT / "tools/verify_rom_cfg_proven_roots_v16_consumed_literals.py").read_text())
        imports = []
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Name):
                names.append(node.id)
        self.assertFalse(any("export_rom_cfg" in name for name in imports))
        self.assertNotIn("_decode_one", names)


if __name__ == "__main__":
    unittest.main()
