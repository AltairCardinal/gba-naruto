#!/usr/bin/env python3
"""TDD contract tests for the frozen v2 consumed-literal exporter."""

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
PACKET = ROOT / "build/experiments/active/cfg-v2-consumed-literals/preflight-20260831"
CONTRACT = json.loads((PACKET / "CONTRACT.json").read_text(encoding="utf-8"))


def _load_exporter():
    try:
        from tools import export_rom_cfg_v2_consumed_literals as exporter
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v2 consumed-literal exporter is absent") from error
    return exporter


class CfgV2ConsumedLiteralsExporterPresenceTests(unittest.TestCase):
    def test_exporter_product_is_present(self) -> None:
        exporter = _load_exporter()
        self.assertTrue(callable(exporter.build_cfg_v2_consumed_literals_payload))
        self.assertTrue(callable(exporter.export_rom_cfg_v2_consumed_literals))


class CfgV2ConsumedLiteralsExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load_exporter()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = cls.exporter.build_cfg_v2_consumed_literals_payload(ROOT)

    def test_payload_binds_frozen_inputs_and_exact_projection(self) -> None:
        payload = self.payload
        self.assertEqual(CONTRACT["artifact"]["payload_schema"], payload["schema"])
        self.assertEqual(
            {
                "path": CONTRACT["base_rom"]["path"],
                "size": CONTRACT["base_rom"]["size"],
                "sha256": CONTRACT["base_rom"]["sha256"],
            },
            payload["rom"],
        )
        self.assertEqual(CONTRACT["source_artifact"]["directory"], payload["source_artifact"]["path"])
        self.assertEqual(CONTRACT["source_artifact"]["manifest_sha256"], payload["source_artifact"]["manifest_sha256"])
        self.assertEqual(CONTRACT["source_artifact"]["payload_sha256"], payload["source_artifact"]["payload_sha256"])
        self.assertEqual(CONTRACT["coverage_baseline"], payload["coverage_baseline"])
        self.assertEqual(
            {
                "block_count": CONTRACT["source_artifact"]["thumb_block_count"],
                "instruction_count": CONTRACT["source_artifact"]["thumb_instruction_count"],
                "instruction_bytes": CONTRACT["source_artifact"]["thumb_instruction_bytes"],
            },
            payload["source_denominator"]["summary"],
        )
        self.assertEqual(CONTRACT["literal_denominator"]["source_instruction_count"], payload["summary"]["source_instruction_count"])
        self.assertEqual(CONTRACT["literal_denominator"]["unique_target_word_count"], payload["summary"]["unique_target_word_count"])
        self.assertEqual(CONTRACT["literal_denominator"]["target_bytes"], payload["summary"]["target_bytes"])
        self.assertEqual(CONTRACT["literal_denominator"]["merged_target_range_count"], payload["summary"]["merged_target_range_count"])
        self.assertEqual(CONTRACT["coverage_projection"], payload["coverage_projection"])

    def test_source_to_target_relation_is_sorted_deduplicated_and_exact(self) -> None:
        payload = self.payload
        bindings = payload["source_to_target"]
        targets = payload["target_words"]
        claims = payload["promotion"]["ranges"]
        self.assertEqual(1841, len(bindings))
        self.assertEqual(1699, len(targets))
        self.assertEqual(653, len(claims))
        self.assertEqual(
            sorted(
                bindings,
                key=lambda row: (
                    row["source_file_offset"],
                    row["target_file_offset"],
                ),
            ),
            bindings,
        )
        self.assertEqual(
            sorted(targets, key=lambda row: row["target_file_offset"]),
            targets,
        )
        self.assertEqual(
            sorted(claims),
            claims,
        )
        self.assertEqual(
            len({row["target_file_offset"] for row in targets}),
            len(targets),
        )
        self.assertEqual(6796, sum(end - start for start, end in claims))
        self.assertEqual(
            CONTRACT["literal_denominator"]["source_vector_sha256"],
            payload["literal_denominator"]["source_vector_sha256"],
        )
        self.assertEqual(
            CONTRACT["literal_denominator"]["target_vector_sha256"],
            payload["literal_denominator"]["target_vector_sha256"],
        )
        self.assertEqual(
            CONTRACT["literal_denominator"]["range_vector_sha256"],
            payload["literal_denominator"]["range_vector_sha256"],
        )
        self.assertEqual(
            CONTRACT["literal_denominator"]["packed_target_bytes_sha256"],
            payload["literal_denominator"]["packed_target_bytes_sha256"],
        )

    def test_export_writes_only_candidate_artifact_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=PACKET) as raw:
            output = Path(raw) / "candidate-artifact"
            manifest = self.exporter.export_rom_cfg_v2_consumed_literals(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
            self.assertEqual(0, manifest["verifier"]["exit_code"])
            self.assertEqual(
                [
                    "python3",
                    "-I",
                    "-S",
                    "tools/verify_rom_cfg_v2_consumed_literals.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/rom-cfg-v2-consumed-literals-v1",
                ],
                manifest["verifier"]["command"],
            )
            self.assertEqual(
                {"manifest.json", CONTRACT["artifact"]["payload"]},
                {path.name for path in output.iterdir()},
            )
            payload_path = output / CONTRACT["artifact"]["payload"]
            self.assertEqual(
                manifest["files"][payload_path.name]["sha256"],
                hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            )

    def test_cli_runs_directly_from_repository_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=PACKET) as raw:
            output = Path(raw) / "candidate-artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_rom_cfg_v2_consumed_literals.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((output / "manifest.json").is_file())

    def test_mutated_rom_fails_closed_before_projection(self) -> None:
        mutated = bytearray(self.rom)
        mutated[0x1234] ^= 1
        with self.assertRaisesRegex(ValueError, "base ROM identity changed"):
            self.exporter.build_cfg_v2_consumed_literals_payload(ROOT, bytes(mutated))

    def test_exporter_does_not_import_the_new_verifier(self) -> None:
        path = ROOT / "tools/export_rom_cfg_v2_consumed_literals.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("verify_rom_cfg_v2_consumed_literals" in name for name in imports))


if __name__ == "__main__":
    unittest.main()
