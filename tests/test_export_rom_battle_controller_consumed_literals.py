#!/usr/bin/env python3
"""TDD contract tests for battle-controller consumed Thumb literals."""

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
PACKET = ROOT / "build/experiments/active/battle-controller-consumed-literals/preflight-20260901"
CONTRACT = PACKET / "CONTRACT.json"


def _load_exporter():
    try:
        from tools import export_rom_battle_controller_consumed_literals as exporter
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("battle-controller consumed-literal exporter is absent") from error
    return exporter


class BattleControllerConsumedLiteralsExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load_exporter()
        cls.payload = cls.exporter.build_payload(ROOT)
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_frozen_denominator_and_projection(self) -> None:
        payload = self.payload
        self.assertEqual(self.contract["artifact"]["payload_schema"], payload["schema"])
        self.assertEqual(self.contract["coverage_baseline"], payload["coverage_baseline"])
        self.assertEqual(self.contract["coverage_projection"], payload["coverage_projection"])
        self.assertEqual(
            {"block_count": 739, "instruction_count": 2756, "instruction_bytes": 6172},
            payload["source_denominator"]["summary"],
        )
        self.assertEqual(
            {
                "raw_source_instruction_count": 226,
                "raw_unique_target_word_count": 209,
                "source_owner_eligible_instruction_count": 226,
                "excluded_non_battle_controller_owner_source_count": 0,
                "excluded_non_unknown_target_source_count": 85,
            },
            payload["source_denominator"]["selection_funnel"],
        )
        self.assertEqual(141, len(payload["source_to_target"]))
        self.assertEqual(134, len(payload["target_words"]))
        self.assertEqual(46, len(payload["promotion"]["ranges"]))
        self.assertEqual(536, sum(end - start for start, end in payload["promotion"]["ranges"]))
        for key, value in self.contract["literal_denominator"].items():
            self.assertEqual(value, payload["literal_denominator"][key])

    def test_relation_ranges_and_target_filter_are_sorted_and_unique(self) -> None:
        payload = self.payload
        sources = payload["source_to_target"]
        targets = payload["target_words"]
        ranges = payload["promotion"]["ranges"]
        self.assertEqual(sorted(sources, key=lambda row: (row["source_file_offset"], row["target_file_offset"])), sources)
        self.assertEqual(sorted(targets, key=lambda row: row["target_file_offset"]), targets)
        self.assertEqual(sorted(ranges), ranges)
        self.assertEqual(len(targets), len({row["target_file_offset"] for row in targets}))
        self.assertTrue(all(len(bytes.fromhex(row["target_raw_hex"])) == 4 for row in targets))
        self.assertEqual(0, payload["v3_packet_target_overlap_word_count"])
        self.assertEqual(0, payload["proven_roots_batch_target_overlap_word_count"])

    def test_export_and_cli_write_only_two_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "candidate"
            result = subprocess.run(
                [sys.executable, "tools/export_rom_battle_controller_consumed_literals.py", "--root", ".", "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"manifest.json", self.exporter.PAYLOAD_NAME}, {path.name for path in output.iterdir()})
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            payload_path = output / self.exporter.PAYLOAD_NAME
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(hashlib.sha256(payload_path.read_bytes()).hexdigest(), manifest["files"][payload_path.name]["sha256"])

    def test_mutated_rom_fails_closed(self) -> None:
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x1234] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            self.exporter.build_payload(ROOT, bytes(rom))

    def test_exporter_binds_source_and_overlap_inputs(self) -> None:
        self.assertEqual(
            {
                self.exporter.SOURCE_MANIFEST: self.exporter.IDENTITIES[self.exporter.SOURCE_MANIFEST],
                self.exporter.SOURCE_PAYLOAD: self.exporter.IDENTITIES[self.exporter.SOURCE_PAYLOAD],
                self.exporter.SOURCE_EXPORTER: self.exporter.IDENTITIES[self.exporter.SOURCE_EXPORTER],
                self.exporter.SOURCE_VERIFIER: self.exporter.IDENTITIES[self.exporter.SOURCE_VERIFIER],
                self.exporter.SOURCE_TEST: self.exporter.IDENTITIES[self.exporter.SOURCE_TEST],
                self.exporter.COVERAGE_PATH: self.exporter.IDENTITIES[self.exporter.COVERAGE_PATH],
            },
            {path: self.exporter.IDENTITIES[path] for path in self.exporter.IDENTITIES},
        )
        self.assertEqual(self.contract["source_artifact"], self.payload["source_artifact"])
        self.assertEqual(self.contract["overlap_baseline"], self.payload["overlap_baseline"])

    def test_exporter_does_not_import_new_verifier(self) -> None:
        tree = ast.parse((ROOT / "tools/export_rom_battle_controller_consumed_literals.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("verify_rom_battle_controller_consumed_literals" in name for name in imports))


if __name__ == "__main__":
    unittest.main()
