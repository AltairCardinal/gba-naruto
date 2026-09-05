#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools.export_rom_cfg_proven_roots_v2 import (
    CROSS_EDGE_VECTOR_SHA256,
    FRONTIER_VECTOR_SHA256,
    PRODUCER_VECTOR_SHA256,
    ROOT_VECTOR_SHA256,
    _producer_denominator,
    _root_seeds,
    build_cfg_proven_roots_v2_payload,
    export_rom_cfg_proven_roots_v2,
)
from tools.verify_rom_cfg_proven_roots_v2 import (
    _implementation as verifier_implementation,
    verify_rom_cfg_proven_roots_v2,
)


ROOT = Path(__file__).resolve().parents[1]


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class RomCfgProvenRootsV2ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_full_rom_thumb_bl_scan_finds_exact_five_producers(self):
        result = _producer_denominator(self.rom)
        self.assertEqual(
            "8cc04030df779e573950c4d1ad00b480368444439af3cc4ec97f62624c6c76c3",
            PRODUCER_VECTOR_SHA256,
        )
        self.assertEqual(PRODUCER_VECTOR_SHA256, result["denominator_sha256"])
        self.assertEqual(
            [
                (0x73690, 0x6B49C, "f7f704ff"),
                (0x7425A, 0x851F8, "10f0cdff"),
                (0x7434E, 0x851F8, "10f053ff"),
                (0x74448, 0x6B49C, "f7f728f8"),
                (0x74F2C, 0x689A4, "f3f73afd"),
            ],
            [
                (
                    record["file_offset"],
                    record["target_file_offset"],
                    record["raw_hex"],
                )
                for record in result["producers"]
            ],
        )

    def test_producer_scan_fails_closed_when_either_end_changes(self):
        for offset in (0x73690, 0x74F2C):
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(
                    ValueError, "producer denominator changed"
                ):
                    _producer_denominator(bytes(tampered))

    def test_root_seeds_bind_three_roots_to_their_producers(self):
        roots = _root_seeds(self.rom)
        self.assertEqual(
            "36e5c9045b5d7ffb931c3dc145d790b1965c18829757bf9b8ca347ed00caae19",
            ROOT_VECTOR_SHA256,
        )
        self.assertEqual(
            [0x689A4, 0x6B49C, 0x851F8],
            [record["file_offset"] for record in roots],
        )
        self.assertEqual(
            [
                ["controller_save_wrapper"],
                ["controller_state_1100", "action_resolution"],
                ["enemy_preparation_primary", "enemy_preparation_secondary"],
            ],
            [
                [source["producer_id"] for source in record["sources"]]
                for record in roots
            ],
        )
        self.assertEqual(
            ["70b50023", "f0b55746", "f0b55746"],
            [self.rom[record["file_offset"] : record["file_offset"] + 4].hex()
             for record in roots],
        )


class RomCfgProvenRootsV2IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_cfg_proven_roots_v2_payload(ROOT)

    def test_freezes_v2_v3_and_first_proven_root_batch_as_opaque_baselines(self):
        self.assertEqual(
            ["proven_roots_v1", "v2", "v3"],
            sorted(self.payload["frozen_baseline"]),
        )
        self.assertEqual(
            "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54",
            self.payload["frozen_baseline"]["proven_roots_v1"]["payload_sha256"],
        )

    def test_builds_exact_three_root_delta_without_reentering_any_baseline(self):
        self.assertEqual("rom-cfg-proven-roots-v2", self.payload["schema"])
        self.assertEqual(
            {
                "decoded_basic_block_count": 835,
                "decoded_instruction_count": 4_809,
                "frontier_count": 28,
                "frontier_reasons": {
                    "indirect_pc_target": 27,
                    "unsupported_armv4t_instruction": 1,
                },
                "reachable_instruction_bytes": 9_876,
            },
            self.payload["extension"]["summary"],
        )
        self.assertEqual(82, len(self.payload["extension"]["baseline_cross_edges"]))
        self.assertEqual(
            {"v2": 82},
            self.payload["extension"]["cross_edge_summary"]["by_baseline"],
        )
        self.assertEqual(
            {"call_target": 82},
            self.payload["extension"]["cross_edge_summary"]["by_kind"],
        )
        self.assertEqual(
            "5878c2596fecd2eeabe4205f688413f03488f006491440fd71e48e404d671838",
            FRONTIER_VECTOR_SHA256,
        )
        self.assertEqual(
            FRONTIER_VECTOR_SHA256,
            self.payload["extension"]["frontier_denominator_sha256"],
        )
        self.assertEqual(
            "b0123d804c3e083bcf123cece476c79f555f949f053f33a5c73b18ab0b765698",
            CROSS_EDGE_VECTOR_SHA256,
        )
        self.assertEqual(
            CROSS_EDGE_VECTOR_SHA256,
            self.payload["extension"]["cross_edge_denominator_sha256"],
        )
        self.assertEqual(
            [0x689A4, 0x6B49C, 0x851F8],
            [record["file_offset"] for record in self.payload["roots"]],
        )
        self.assertEqual(
            [
                (433, 94, 900, 5),
                (264, 54, 568, 1),
                (4_112, 687, 8_408, 22),
            ],
            [
                (
                    record["reachable_instruction_count"],
                    record["reachable_block_count"],
                    record["reachable_instruction_bytes"],
                    record["frontier_count"],
                )
                for record in self.payload["roots"]
            ],
        )
        self.assertFalse(self.payload["scope"]["runtime_reachability_complete"])


class RomCfgProvenRootsV2RepositoryArtifactTests(unittest.TestCase):
    def test_repository_artifact_is_independently_verified(self):
        report = verify_rom_cfg_proven_roots_v2(
            ROOT, ROOT / "artifacts/rom-cfg-proven-roots-v2"
        )
        self.assertTrue(report["verified"], report)
        self.assertEqual(4_809, report["decoded_instruction_count"])


class RomCfgProvenRootsV2ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact = Path(cls.temporary.name).resolve() / "cfg-proven-roots-v2"
        cls.manifest = export_rom_cfg_proven_roots_v2(ROOT, cls.artifact)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_artifact_is_independently_verified(self):
        report = verify_rom_cfg_proven_roots_v2(ROOT, self.artifact)
        self.assertTrue(report["verified"], report)
        self.assertEqual(3, report["root_count"])
        self.assertEqual(4_809, report["decoded_instruction_count"])
        self.assertEqual(835, report["decoded_basic_block_count"])
        self.assertEqual(9_876, report["reachable_instruction_bytes"])
        self.assertEqual(28, report["frontier_count"])
        self.assertEqual(82, report["baseline_cross_edge_count"])

    def test_verifier_implementation_hash_is_bound_to_requested_root(self):
        expected = hashlib.sha256(
            (ROOT / "tools/verify_rom_cfg_proven_roots_v2.py").read_bytes()
        ).hexdigest()
        with mock.patch(
            "tools.verify_rom_cfg_proven_roots_v2.__file__",
            "/tmp/non-repository-verifier-copy.py",
        ):
            implementation = verifier_implementation(ROOT)
        self.assertEqual(expected, implementation["verifier_sha256"])

    def test_verifier_rejects_rehashed_cross_edge_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            forged = Path(directory).resolve() / "forged"
            shutil.copytree(self.artifact, forged)
            payload_path = forged / "rom-cfg-proven-roots-v2.json"
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
            report = verify_rom_cfg_proven_roots_v2(ROOT, forged)
            self.assertFalse(report["verified"], report)
            self.assertTrue(
                any("cross" in error.lower() for error in report["errors"]), report
            )

    def test_replacement_preflight_allows_only_implementation_hash_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            prior = Path(directory).resolve() / "prior"
            shutil.copytree(self.artifact, prior)
            payload_path = prior / "rom-cfg-proven-roots-v2.json"
            payload = json.loads(payload_path.read_bytes())
            prior_implementation = {
                "exporter_sha256": "0" * 64,
                "verifier_sha256": "1" * 64,
                "test_sha256": "2" * 64,
            }
            payload["implementation"] = prior_implementation
            payload_raw = _canonical_json(payload)
            payload_path.write_bytes(payload_raw)
            manifest_path = prior / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["implementation"] = prior_implementation
            manifest["files"][payload_path.name] = {
                "size": len(payload_raw),
                "sha256": hashlib.sha256(payload_raw).hexdigest(),
            }
            manifest_path.write_bytes(_canonical_json(manifest))

            strict = verify_rom_cfg_proven_roots_v2(ROOT, prior)
            self.assertFalse(strict["verified"], strict)
            replacement_preflight = verify_rom_cfg_proven_roots_v2(
                ROOT, prior, allow_implementation_drift=True
            )
            self.assertTrue(replacement_preflight["verified"], replacement_preflight)

    def test_verifier_does_not_import_the_exporter(self):
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v2.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("tools.export_rom_cfg_proven_roots_v2", source)


if __name__ == "__main__":
    unittest.main()
