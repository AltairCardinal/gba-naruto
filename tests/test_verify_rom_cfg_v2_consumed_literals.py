#!/usr/bin/env python3
"""Independent verifier tests for the frozen v2 consumed-literal artifact."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import export_rom_cfg_v2_consumed_literals as exporter


ROOT = Path(__file__).resolve().parents[1]


def _load_verifier():
    try:
        from tools import verify_rom_cfg_v2_consumed_literals as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v2 consumed-literal verifier is absent") from error
    return verifier


class CfgV2ConsumedLiteralsVerifierPresenceTests(unittest.TestCase):
    def test_verifier_product_is_present(self) -> None:
        verifier = _load_verifier()
        self.assertTrue(callable(verifier.verify_root))


class CfgV2ConsumedLiteralsVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = _load_verifier()

    def _candidate(self, root: Path) -> Path:
        candidate = root / "candidate"
        shutil.copytree(ROOT / "artifacts/rom-cfg-v2-consumed-literals-v1", candidate)
        return candidate

    def test_independently_rebuilds_complete_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            report = self.verifier.verify_root(ROOT, candidate)
        self.assertEqual(
            "rom-cfg-v2-consumed-literals-verification-v1", report["schema"]
        )
        self.assertEqual(
            {
                "source_instruction_count": 1841,
                "unique_target_word_count": 1699,
                "target_bytes": 6796,
                "merged_target_range_count": 653,
            },
            report["summary"],
        )
        self.assertEqual(7648, report["source_denominator"]["thumb_block_count"])
        self.assertEqual(40635, report["source_denominator"]["thumb_instruction_count"])
        self.assertTrue(report["contract_ok"])
        self.assertTrue(report["verified"])

    def test_verifier_has_independent_thumb_width_and_literal_decoder(self) -> None:
        verifier = self.verifier
        self.assertEqual(4, verifier._thumb_instruction_width(bytes.fromhex("00f000f8"), 0, 4))
        self.assertEqual(2, verifier._thumb_instruction_width(bytes.fromhex("0048"), 0, 2))
        self.assertEqual(0x104, verifier._decode_ldr_literal_target(0x100, 0x4800))
        self.assertEqual(0x110, verifier._decode_ldr_literal_target(0x102, 0x4803))

    def test_rejects_payload_tampering_even_when_json_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            payload_path = candidate / exporter.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["source_to_target"][0]["target_file_offset"] += 4
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "payload identity|artifact file"):
                self.verifier.verify_root(ROOT, candidate)

    def test_rejects_foreign_members_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            candidate = self._candidate(Path(raw))
            (candidate / "foreign.txt").write_text("no")
            with self.assertRaisesRegex(ValueError, "artifact file set"):
                self.verifier.verify_root(ROOT, candidate)

        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            candidate = self._candidate(directory)
            alias = directory / "candidate-symlink"
            alias.symlink_to(candidate, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.verifier.verify_root(ROOT, alias)

    def test_verifier_does_not_import_exporter_or_generic_cfg_decoder(self) -> None:
        path = ROOT / "tools/verify_rom_cfg_v2_consumed_literals.py"
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
        self.assertFalse(any("export_rom_cfg_v2_consumed_literals" in item for item in imports))
        self.assertNotIn("_decode_one", names)


if __name__ == "__main__":
    unittest.main()
