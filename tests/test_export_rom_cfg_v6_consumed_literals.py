#!/usr/bin/env python3
"""TDD contract tests for proven-roots-v6 consumed literals."""

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
PACKET = ROOT / "build/experiments/active/cfg-v6-consumed-literals/preflight-20260831"
CONTRACT = json.loads((PACKET / "CONTRACT.json").read_text(encoding="utf-8"))


def _load_exporter():
    try:
        from tools import export_rom_cfg_v6_consumed_literals as exporter
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v6 consumed-literal exporter is absent") from error
    return exporter


class CfgV6ConsumedLiteralsExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load_exporter()
        cls.payload = cls.exporter.build_payload(ROOT)

    def test_exact_frozen_denominator_and_projection(self) -> None:
        payload = self.payload
        self.assertEqual(CONTRACT["artifact"]["payload_schema"], payload["schema"])
        self.assertEqual(CONTRACT["coverage_baseline"], payload["coverage_baseline"])
        self.assertEqual(CONTRACT["coverage_projection"], payload["coverage_projection"])
        self.assertEqual(
            {"block_count": 2305, "instruction_count": 12564, "instruction_bytes": 27224},
            payload["source_denominator"]["summary"],
        )
        self.assertEqual(800, len(payload["source_to_target"]))
        self.assertEqual(745, len(payload["target_words"]))
        self.assertEqual(185, len(payload["promotion"]["ranges"]))
        self.assertEqual(2980, sum(b - a for a, b in payload["promotion"]["ranges"]))
        for key, value in CONTRACT["literal_denominator"].items():
            if key.endswith("sha256") or key.endswith("count") or key == "target_bytes":
                self.assertEqual(value, payload["literal_denominator"][key])

    def test_relation_and_ranges_are_sorted_and_unique(self) -> None:
        payload = self.payload
        sources = payload["source_to_target"]
        targets = payload["target_words"]
        ranges = payload["promotion"]["ranges"]
        self.assertEqual(sorted(sources, key=lambda row: (row["source_file_offset"], row["target_file_offset"])), sources)
        self.assertEqual(sorted(targets, key=lambda row: row["target_file_offset"]), targets)
        self.assertEqual(sorted(ranges), ranges)
        self.assertEqual(len(targets), len({row["target_file_offset"] for row in targets}))

    def test_export_and_direct_cli_write_only_two_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=PACKET) as raw:
            output = Path(raw) / "candidate"
            result = subprocess.run(
                [sys.executable, "tools/export_rom_cfg_v6_consumed_literals.py", "--root", ".", "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"manifest.json", CONTRACT["artifact"]["payload"]}, {path.name for path in output.iterdir()})
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            payload_path = output / CONTRACT["artifact"]["payload"]
            self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(hashlib.sha256(payload_path.read_bytes()).hexdigest(), manifest["files"][payload_path.name]["sha256"])

    def test_mutated_rom_fails_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x1234] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            self.exporter.build_payload(ROOT, bytes(rom))

    def test_exporter_does_not_import_new_verifier(self) -> None:
        tree = ast.parse((ROOT / "tools/export_rom_cfg_v6_consumed_literals.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("verify_rom_cfg_v6_consumed_literals" in name for name in imports))


if __name__ == "__main__":
    unittest.main()
