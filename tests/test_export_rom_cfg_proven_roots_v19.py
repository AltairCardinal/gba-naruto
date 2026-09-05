#!/usr/bin/env python3
"""TDD contracts for the target-local CFG proven-roots v19 candidate."""

from __future__ import annotations

import ast
import json
import os
import shutil
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v19-luna-20260901"


class CfgProvenRootsV19ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_cfg_proven_roots_v19 as exporter
        from tools import rom_cfg_proven_roots_v19_contract as contract
        from tools import verify_rom_cfg_proven_roots_v19 as verifier

        cls.exporter = exporter
        cls.contract = contract
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter.build_payload(ROOT)

    def test_frozen_target_and_upstream_producer_contract(self) -> None:
        payload = self.payload

        self.assertEqual(self.contract.SCHEMA, payload["schema"])
        self.assertEqual(
            {"file_offset": 0x065728, "entry_sha256": self.contract.ROOT_ENTRY_SHA256},
            payload["root"],
        )
        self.assertEqual(
            [0x061092],
            [row["file_offset"] for row in payload["accepted_producers"]],
        )
        self.assertEqual(
            self.contract.UPSTREAM_ARTIFACT,
            payload["upstream_continuation_artifact"]["artifact_dir"],
        )
        self.assertEqual(
            self.contract.UPSTREAM_MANIFEST_SHA256,
            payload["upstream_continuation_artifact"]["manifest_sha256"],
        )
        self.assertEqual(
            self.contract.UPSTREAM_PAYLOAD_SHA256,
            payload["upstream_continuation_artifact"]["payload_sha256"],
        )

    def test_ranges_counts_hashes_and_scope_are_frozen(self) -> None:
        payload = self.payload
        promotion = payload["promotion"]

        self.assertEqual(self.contract.CODE_RANGES, tuple(map(tuple, promotion["code_ranges"])))
        self.assertEqual(self.contract.LITERAL_RANGES, tuple(map(tuple, promotion["literal_ranges"])))
        self.assertEqual(self.contract.HOLES, tuple(map(tuple, promotion["preserved_unknown_gaps"])))
        self.assertEqual((1600, 60, 1660, 12), tuple(promotion[key] for key in ("code_bytes", "literal_bytes", "promotion_bytes", "preserved_unknown_bytes")))
        self.assertEqual(798, payload["target_local_denominator"]["instruction_count"])
        self.assertEqual(54, payload["target_local_denominator"]["basic_block_count"])
        self.assertEqual(
            [[0x065D98, "indirect_pc_target"]],
            payload["target_local_denominator"]["frontiers"],
        )
        self.assertFalse(payload["scope"]["natural_runtime_reachability"])

    def test_raw_producer_and_rom_mutation_fail_closed(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("04f049fb", payload["accepted_producers"][0]["raw_hex"])
        bad = bytearray(self.rom)
        bad[0x061092] ^= 1
        with self.assertRaises(ValueError):
            self.exporter.build_payload(ROOT, bytes(bad))

    def test_atomic_candidate_passes_independent_verifier(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            self.exporter.export(ROOT, output)
            report = self.verifier.verify_root(ROOT, output)
            self.assertTrue(report["verified"])
            self.assertEqual(1660, report["promotion_bytes"])

    def test_verifier_is_independent_and_rejects_payload_mutation(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v19.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_cfg_proven_roots_v19" in ast.unparse(node) for node in imports))

        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            target = Path(raw) / "artifact"
            shutil.copytree(ROOT / "artifacts/rom-boot-interwork-continuation-v1", target / "upstream")
            self.exporter.export(ROOT, target / "candidate")
            artifact = target / "candidate"
            payload_path = artifact / self.contract.PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["promotion"]["promotion_bytes"] += 2
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_root(ROOT, artifact)["verified"])

    def test_verifier_does_not_share_cfg_exporter_implementations(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v19.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("tools.export_rom_cfg" in ast.unparse(node) for node in imports))

    def test_accepted_receipt_mutation_fails_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = Path(raw) / "candidate"
            shutil.copytree(EXPERIMENT / "candidate", artifact)
            manifest_path = artifact / self.contract.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text())
            manifest["verifier"]["report"]["errors"] = ["forged"]
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_root(ROOT, artifact)["verified"])

    def test_output_parent_symlink_escape_is_rejected_before_build(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            link = Path(raw) / "escape"
            os.symlink(outside, link)
            with self.assertRaises(ValueError):
                self.exporter.export(ROOT, link / "candidate")

    def test_independent_verifier_binds_opaque_targets_to_frozen_baseline_entries(self) -> None:
        owner = self.verifier._frozen_baseline_entry(ROOT, 0x063604)
        self.assertEqual(
            {
                "artifact": "artifacts/rom-cfg-inventory-v2",
                "block_id": "block-thumb-063604",
                "mode": "thumb",
                "range": [0x063604, 0x063620],
                "bytes_sha256": "40205ac89e11659a8bf30d5e7fe1c1d691266ad3da412ed5de6f92af91e5adce",
            },
            owner,
        )


if __name__ == "__main__":
    unittest.main()
