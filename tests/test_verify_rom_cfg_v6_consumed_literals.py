#!/usr/bin/env python3
"""Independent verifier tests for proven-roots-v6 consumed literals."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools import export_rom_cfg_v6_consumed_literals as exporter


ROOT = Path(__file__).resolve().parents[1]


def _load_verifier():
    try:
        from tools import verify_rom_cfg_v6_consumed_literals as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v6 consumed-literal verifier is absent") from error
    return verifier


class CfgV6ConsumedLiteralsVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = _load_verifier()

    def _candidate(self, directory: Path) -> Path:
        candidate = directory / "candidate"
        shutil.copytree(ROOT / "artifacts/rom-cfg-v6-consumed-literals-v1", candidate)
        return candidate

    def test_independently_rebuilds_complete_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            report = self.verifier.verify_root(ROOT, self._candidate(Path(raw)))
        self.assertTrue(report["contract_ok"])
        self.assertTrue(report["verified"])
        self.assertEqual({"source_instruction_count": 800, "unique_target_word_count": 745, "target_bytes": 2980, "merged_target_range_count": 185}, report["summary"])
        self.assertEqual(2305, report["source_denominator"]["thumb_block_count"])
        self.assertEqual(12564, report["source_denominator"]["thumb_instruction_count"])

    def test_independent_decoder_and_direct_cli(self) -> None:
        self.assertEqual(4, self.verifier._thumb_instruction_width(bytes.fromhex("00f000f8"), 0, 4))
        self.assertEqual(2, self.verifier._thumb_instruction_width(bytes.fromhex("0048"), 0, 2))
        self.assertEqual(0x110, self.verifier._decode_ldr_literal_target(0x102, 0x4803))
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            result = subprocess.run(
                [sys.executable, "-I", "-S", "tools/verify_rom_cfg_v6_consumed_literals.py", "--root", ".", "--artifact", str(candidate)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(json.loads(result.stdout)["contract_ok"])

    def test_rejects_payload_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            payload_path = candidate / exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["source_to_target"][0]["target_file_offset"] += 4
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "payload identity|artifact file"):
                self.verifier.verify_root(ROOT, candidate)

    def test_rejects_foreign_members_and_artifact_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            (candidate / "foreign.txt").write_text("no")
            with self.assertRaisesRegex(ValueError, "artifact file set"):
                self.verifier.verify_root(ROOT, candidate)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            candidate = self._candidate(directory)
            alias = directory / "alias"
            alias.symlink_to(candidate, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.verifier.verify_root(ROOT, alias)

    def test_verifier_is_independent_of_exporters_and_generic_decoder(self) -> None:
        path = ROOT / "tools/verify_rom_cfg_v6_consumed_literals.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: list[str] = []
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Name):
                names.append(node.id)
        self.assertFalse(any("consumed_literals" in name for name in imports))
        self.assertNotIn("_decode_one", names)


if __name__ == "__main__":
    unittest.main()
