#!/usr/bin/env python3
"""TDD tests for proven-roots-v1 consumed-literal exporter."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "build/experiments/active/cfg-v1-consumed-literals/preflight-20260831"
CONTRACT = json.loads((PACKET / "CONTRACT.json").read_text())


def _load():
    try:
        from tools import export_rom_cfg_v1_consumed_literals as exporter
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v1 consumed-literal exporter is absent") from error
    return exporter


class CfgV1ConsumedLiteralsExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load()
        cls.payload = cls.exporter.build_payload(ROOT)

    def test_exact_denominator_and_projection(self) -> None:
        p = self.payload
        self.assertEqual(CONTRACT["artifact"]["payload_schema"], p["schema"])
        self.assertEqual(CONTRACT["coverage_baseline"], p["coverage_baseline"])
        self.assertEqual(CONTRACT["coverage_projection"], p["coverage_projection"])
        self.assertEqual({"block_count": 1203, "instruction_count": 6166, "instruction_bytes": 12966}, p["source_denominator"]["summary"])
        self.assertEqual((398, 349, 108, 1396), (len(p["source_to_target"]), len(p["target_words"]), len(p["promotion"]["ranges"]), sum(b-a for a,b in p["promotion"]["ranges"])))
        for key, value in CONTRACT["literal_denominator"].items():
            if key.endswith("sha256") or key.endswith("count") or key == "target_bytes":
                self.assertEqual(value, p["literal_denominator"][key])

    def test_vectors_sorted_and_unique(self) -> None:
        p = self.payload
        self.assertEqual(sorted(p["source_to_target"], key=lambda row: (row["source_file_offset"], row["target_file_offset"])), p["source_to_target"])
        self.assertEqual(sorted(p["target_words"], key=lambda row: row["target_file_offset"]), p["target_words"])
        self.assertEqual(len(p["target_words"]), len({row["target_file_offset"] for row in p["target_words"]}))
        self.assertEqual(sorted(p["promotion"]["ranges"]), p["promotion"]["ranges"])

    def test_direct_cli_writes_promotion_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=PACKET) as raw:
            output = Path(raw) / "candidate"
            result = subprocess.run([sys.executable, "tools/export_rom_cfg_v1_consumed_literals.py", "--root", ".", "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"manifest.json", CONTRACT["artifact"]["payload"]}, {x.name for x in output.iterdir()})
            manifest = json.loads((output / "manifest.json").read_text())
            payload = output / CONTRACT["artifact"]["payload"]
            self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
            self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), manifest["files"][payload.name]["sha256"])

    def test_mutated_rom_and_verifier_import_fail_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes()); rom[0x1234] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            self.exporter.build_payload(ROOT, bytes(rom))
        tree = ast.parse((ROOT / "tools/export_rom_cfg_v1_consumed_literals.py").read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
        self.assertFalse(any("verify_rom_cfg_v1_consumed_literals" in name for name in imports))


if __name__ == "__main__": unittest.main()
