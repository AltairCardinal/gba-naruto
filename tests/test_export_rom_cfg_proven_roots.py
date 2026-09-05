#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools.export_rom_cfg_proven_roots import (
    PRODUCER_VECTOR_SHA256,
    ROOT_VECTOR_SHA256,
    SCHEMA,
    _producer_denominator,
    _source_evidence_contract,
    export_rom_cfg_proven_roots,
)
from tools.verify_rom_cfg_proven_roots import (
    _implementation as verifier_implementation,
    verify_rom_cfg_proven_roots,
)


ROOT = Path(__file__).resolve().parents[1]


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class RomCfgProvenRootProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_full_rom_thumb_bl_scan_finds_exactly_three_producers(self):
        result = _producer_denominator(self.rom)
        self.assertEqual(PRODUCER_VECTOR_SHA256, result["denominator_sha256"])
        self.assertEqual(
            [0x73688, 0x7443C, 0x74918],
            [record["file_offset"] for record in result["producers"]],
        )
        self.assertEqual(
            [0x81B70, 0x722A8, 0x722A8],
            [record["target_file_offset"] for record in result["producers"]],
        )

    def test_producer_scan_fails_closed_when_one_bl_changes(self):
        tampered = bytearray(self.rom)
        tampered[0x73688] ^= 1
        with self.assertRaisesRegex(ValueError, "producer denominator changed"):
            _producer_denominator(bytes(tampered))

    def test_source_evidence_contract_reads_every_claimed_root_file(self):
        paths = (
            Path("tools/verify_rom_cfg_inventory.py"),
            Path("tools/verify_rom_cfg_inventory_v3.py"),
            Path("notes/battle-controller-states-20260723.json"),
            Path("tools/verify_battlefield_object_effect_chain.py"),
        )
        with tempfile.TemporaryDirectory() as directory:
            fake_root = Path(directory).resolve()
            for relative in paths:
                target = fake_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            _source_evidence_contract(fake_root)
            target = fake_root / paths[-1]
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "source evidence identity"):
                _source_evidence_contract(fake_root)

    def test_verifier_implementation_hash_is_bound_to_the_requested_root(self):
        expected = hashlib.sha256(
            (ROOT / "tools/verify_rom_cfg_proven_roots.py").read_bytes()
        ).hexdigest()
        with mock.patch(
            "tools.verify_rom_cfg_proven_roots.__file__",
            "/tmp/non-repository-verifier-copy.py",
        ):
            implementation = verifier_implementation(ROOT)
        self.assertEqual(expected, implementation["verifier_sha256"])


class RomCfgProvenRootIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact = Path(cls.temporary.name).resolve() / "cfg-proven-roots"
        cls.manifest = export_rom_cfg_proven_roots(ROOT, cls.artifact)
        cls.payload_path = cls.artifact / "rom-cfg-proven-roots.json"
        cls.payload = json.loads(cls.payload_path.read_bytes())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_builds_the_exact_two_root_delta_without_reentering_v2_or_v3(self):
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual(ROOT_VECTOR_SHA256, self.payload["root_denominator_sha256"])
        self.assertEqual(
            [0x722A8, 0x81B70],
            [record["file_offset"] for record in self.payload["roots"]],
        )
        self.assertEqual(
            {
                "decoded_basic_block_count": 1_203,
                "decoded_instruction_count": 6_166,
                "frontier_count": 28,
                "frontier_reasons": {
                    "decode_failure": 1,
                    "indirect_pc_target": 27,
                },
                "reachable_instruction_bytes": 12_966,
            },
            self.payload["extension"]["summary"],
        )
        self.assertEqual(259, len(self.payload["extension"]["baseline_cross_edges"]))
        self.assertEqual(
            {"v2": 256, "v3": 3},
            self.payload["extension"]["cross_edge_summary"]["by_baseline"],
        )
        self.assertEqual(
            {"branch_target": 3, "call_target": 256},
            self.payload["extension"]["cross_edge_summary"]["by_kind"],
        )
        self.assertEqual(
            "e426acd731a1de146e09c4446420c89a76439fba22e9db7b5238e16c532f1512",
            self.payload["extension"]["frontier_denominator_sha256"],
        )
        self.assertEqual(
            "897401ae862b45444bd17792af2331def5be3b0a3426e67dde62c53cbae38739",
            self.payload["extension"]["cross_edge_denominator_sha256"],
        )
        self.assertFalse(self.payload["scope"]["indirect_target_resolution_complete"])
        self.assertFalse(self.payload["scope"]["runtime_reachability_complete"])

    def test_artifact_is_independently_verified(self):
        report = verify_rom_cfg_proven_roots(ROOT, self.artifact)
        self.assertTrue(report["verified"], report)
        self.assertEqual(2, report["root_count"])
        self.assertEqual(6_166, report["decoded_instruction_count"])
        self.assertEqual(12_966, report["reachable_instruction_bytes"])
        self.assertEqual(28, report["frontier_count"])
        self.assertEqual(259, report["baseline_cross_edge_count"])

    def test_repository_artifact_is_independently_verified(self):
        report = verify_rom_cfg_proven_roots(
            ROOT, ROOT / "artifacts/rom-cfg-proven-roots-v1"
        )
        self.assertTrue(report["verified"], report)
        self.assertEqual(6_166, report["decoded_instruction_count"])

    def test_verifier_rejects_cross_edge_tampering_after_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            forged = Path(directory).resolve() / "forged"
            shutil.copytree(self.artifact, forged)
            payload_path = forged / "rom-cfg-proven-roots.json"
            payload = json.loads(payload_path.read_bytes())
            payload["extension"]["baseline_cross_edges"][0]["target"][
                "instruction_offset"
            ] += 2
            payload_raw = _canonical_json(payload)
            payload_path.write_bytes(payload_raw)
            manifest_path = forged / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][payload_path.name] = {
                "size": len(payload_raw),
                "sha256": hashlib.sha256(payload_raw).hexdigest(),
            }
            manifest_path.write_bytes(_canonical_json(manifest))

            report = verify_rom_cfg_proven_roots(ROOT, forged)
            self.assertFalse(report["verified"], report)
            self.assertTrue(
                any("cross" in error.lower() for error in report["errors"]), report
            )

    def test_verifier_does_not_import_the_exporter(self):
        source = (ROOT / "tools/verify_rom_cfg_proven_roots.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("tools.export_rom_cfg_proven_roots", source)


if __name__ == "__main__":
    unittest.main()
