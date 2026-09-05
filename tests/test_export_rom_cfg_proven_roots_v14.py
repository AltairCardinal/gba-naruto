#!/usr/bin/env python3
"""TDD contract tests for the frozen CFG proven-roots v14 exporter."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v14-red-20260830"
CONTRACT = json.loads(
    (
        ROOT
        / "build/experiments/active/cfg-proven-roots-v14-preflight-20260830/CONTRACT.json"
    ).read_text(encoding="utf-8")
)
TARGETS = CONTRACT["targets"]


def _products():
    try:
        from tools import export_rom_cfg_proven_roots_v14 as exporter
        from tools import verify_rom_cfg_proven_roots_v14 as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v14 product modules are absent") from error
    return exporter, verifier


class CfgProvenRootsV14ProductPresenceTests(unittest.TestCase):
    def test_exporter_and_independent_verifier_are_present(self) -> None:
        exporter, verifier = _products()
        self.assertTrue(callable(exporter.build_cfg_proven_roots_v14_payload))
        self.assertTrue(callable(verifier.verify_rom_cfg_proven_roots_v14))


class CfgProvenRootsV14ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_rebuilds_two_roots_five_producers_and_exact_promotion(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v14_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v14", payload["schema"])
        self.assertEqual([402_624, 402_704], [row["root"]["file_offset"] for row in payload["targets"]])
        self.assertEqual([2, 3], [len(row["producers"]) for row in payload["targets"]])
        self.assertEqual([32, 28], [row["summary"]["decoded_instruction_count"] for row in payload["targets"]])
        self.assertEqual([5, 5], [row["summary"]["decoded_basic_block_count"] for row in payload["targets"]])
        self.assertEqual([64, 56], [row["summary"]["reachable_instruction_bytes"] for row in payload["targets"]])
        self.assertEqual([1, 1], [row["summary"]["frontier_count"] for row in payload["targets"]])
        self.assertEqual([[402_686, "indirect_pc_target"]], payload["targets"][0]["frontiers"])
        self.assertEqual([[402_758, "indirect_pc_target"]], payload["targets"][1]["frontiers"])
        self.assertEqual(CONTRACT["promotion"]["ranges"], payload["promotion"]["ranges"])
        self.assertEqual(160, payload["promotion"]["promotion_bytes"])
        self.assertEqual(120, payload["promotion"]["promotion_code_bytes"])
        self.assertEqual(40, payload["promotion"]["promotion_literal_bytes"])
        self.assertEqual(0, payload["promotion"]["hole_bytes"])
        self.assertEqual(CONTRACT["promotion"]["packed_sha256"], payload["promotion"]["packed_sha256"])

    def test_target_vectors_match_the_frozen_public_contract(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v14_payload(ROOT)
        for actual, frozen in zip(payload["targets"], TARGETS, strict=True):
            self.assertEqual(frozen["root"], actual["root"]["file_offset"])
            self.assertEqual(frozen["envelope"], actual["envelope"])
            self.assertEqual(frozen["code_ranges"], actual["code_ranges"])
            self.assertEqual(frozen["literal_ranges"], actual["literal_ranges"])
            self.assertEqual(frozen["block_ranges"], actual["block_ranges"])
            self.assertEqual(frozen["frontiers"], actual["frontiers"])
            self.assertEqual(frozen["semantic_instruction_vector_sha256"], actual["semantic_instruction_vector_sha256"])
            self.assertEqual(frozen["instruction_internal_edge_vector_sha256"], actual["instruction_internal_edge_vector_sha256"])
            self.assertEqual(frozen["block_internal_edge_vector_sha256"], actual["block_internal_edge_vector_sha256"])
            self.assertEqual(frozen["literal_binding_vector_sha256"], actual["literal_binding_vector_sha256"])
            self.assertEqual(frozen["packed_promotion_sha256"], actual["packed_promotion_sha256"])

    def test_full_rom_producer_denominators_and_upstream_membership_are_exact(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v14_payload(ROOT)
        for actual, frozen in zip(payload["targets"], TARGETS, strict=True):
            denominator = self.exporter._producer_denominator(
                self.rom, frozen["root"]
            )
            self.assertEqual(frozen["producer_denominator"]["vector"], denominator["vector"])
            self.assertEqual(frozen["producer_denominator"]["vector_sha256"], denominator["vector_sha256"])
            self.assertEqual(
                [row["file_offset"] for row in frozen["producers"]],
                [row["file_offset"] for row in actual["producers"]],
            )
            self.assertTrue(all(row["artifact_node"]["accepted"] for row in actual["producers"]))
            self.assertTrue(all(row["artifact_node"]["mnemonic"] == "bl" for row in actual["producers"]))
        self.assertEqual(CONTRACT["inputs"]["upstream"], payload["upstream"])

    def test_coverage_identity_scope_and_nonclaims_fail_closed(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v14_payload(ROOT)
        self.assertEqual(CONTRACT["inputs"]["coverage_baseline"], payload["coverage_baseline"])
        for key, expected in CONTRACT["scope"].items():
            self.assertEqual(expected, payload["scope"][key], key)
        self.assertTrue(payload["scope"]["nonclaims"])
        self.assertTrue(
            all(
                node.get("flow_kind") != "structured_return"
                for target in payload["targets"]
                for node in target["nodes"]
            )
        )

    def test_raw_rom_mutations_fail_during_independent_rebuild(self) -> None:
        checks = [
            (411_028, lambda rom: self.exporter._producer_denominator(rom, 402_624)),
            (414_260, lambda rom: self.exporter._producer_denominator(rom, 402_624)),
            (410_866, lambda rom: self.exporter._producer_denominator(rom, 402_704)),
            (410_924, lambda rom: self.exporter._producer_denominator(rom, 402_704)),
            (414_296, lambda rom: self.exporter._producer_denominator(rom, 402_704)),
            (402_624, lambda rom: self.exporter._target_worklist(rom, 0)),
            (402_686, lambda rom: self.exporter._target_worklist(rom, 0)),
            (402_704, lambda rom: self.exporter._target_worklist(rom, 1)),
            (402_758, lambda rom: self.exporter._target_worklist(rom, 1)),
            (402_760, lambda rom: self.exporter._target_worklist(rom, 1)),
        ]
        for offset, helper in checks:
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                helper(bytes(mutated))

    def test_export_is_atomic_and_requires_independent_verifier(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            output = parent / "candidate"
            manifest = self.exporter.export_rom_cfg_proven_roots_v14(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({"manifest.json", "rom-cfg-proven-roots-v14.json"}, {path.name for path in output.iterdir()})
            self.assertEqual(self.verifier.EXPECTED_REPORT, self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, output))
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with mock.patch.object(
                self.exporter,
                "_run_isolated_verifier",
                side_effect=ValueError("forced verifier failure"),
            ), self.assertRaisesRegex(ValueError, "forced verifier failure"):
                self.exporter.export_rom_cfg_proven_roots_v14(ROOT, output)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_verifier_is_independent_and_clis_require_isolated_runtime(self) -> None:
        verifier_path = ROOT / "tools/verify_rom_cfg_proven_roots_v14.py"
        tree = ast.parse(verifier_path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v14" in name for name in imports))
        for script in (
            ROOT / "tools/export_rom_cfg_proven_roots_v14.py",
            verifier_path,
        ):
            ordinary = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, ordinary.returncode)
            self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)
            isolated = subprocess.run(
                [sys.executable, "-I", "-S", str(script), "--help"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, isolated.returncode, isolated.stdout + isolated.stderr)


if __name__ == "__main__":
    unittest.main()
