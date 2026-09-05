#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools.export_rom_cfg_inventory_v3 import (
    ORDERED_TARGET_VECTOR_SHA256,
    SCHEMA,
    _resolve_thumb_indexed_dispatches,
    export_rom_cfg_inventory_v3,
)
from tools.verify_rom_cfg_inventory_v3 import (
    _implementation as verifier_implementation,
    _resolve_thumb_indexed_dispatches_independently,
    verify_rom_cfg_inventory_v3,
)


ROOT = Path(__file__).resolve().parents[1]
V2_PAYLOAD = ROOT / "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class RomCfgInventoryV3DispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.v2_payload = json.loads(V2_PAYLOAD.read_bytes())

    def test_resolves_the_frozen_v2_thumb_dispatch_denominator_from_raw_bytes(self):
        resolution = _resolve_thumb_indexed_dispatches(
            self.rom, self.v2_payload
        )

        self.assertEqual(357, resolution["baseline_indirect_frontier_count"])
        self.assertEqual(29, resolution["resolved_frontier_count"])
        self.assertEqual(328, resolution["unresolved_baseline_indirect_frontier_count"])
        self.assertEqual(677, resolution["ordered_edge_count"])
        self.assertEqual(290, resolution["unique_target_count"])
        self.assertEqual(183, resolution["existing_fixed_root_target_count"])
        self.assertEqual(107, resolution["not_fixed_root_target_count"])
        self.assertEqual(
            ORDERED_TARGET_VECTOR_SHA256,
            resolution["ordered_target_vector_sha256"],
        )
        self.assertEqual(
            "ab4572dcb948a49e6172e18f2fd9c482e61ee018c42cf0be77bd0e67f0c86615",
            resolution["ordered_target_vector_sha256"],
        )
        self.assertEqual(29, len(resolution["dispatches"]))

        sparse = {
            item["source_frontier_id"]: item["allowed_indices"]
            for item in resolution["dispatches"]
            if item["allowed_indices"] != list(range(item["comparison_max"] + 1))
        }
        self.assertEqual(
            {
                "frontier-000124": [0, 2, 4, 6, 8],
                "frontier-000177": [0, 2, 4, 6, 8],
            },
            sparse,
        )
        for dispatch in resolution["dispatches"]:
            self.assertEqual(
                len(dispatch["allowed_indices"]), len(dispatch["targets"])
            )
            self.assertEqual(
                dispatch["ordered_target_vector_sha256"],
                hashlib.sha256(
                    b"".join(
                        target["raw_pointer"].to_bytes(4, "little")
                        for target in dispatch["targets"]
                    )
                ).hexdigest(),
            )

    def test_dispatch_resolution_fails_closed_when_a_tail_opcode_changes(self):
        rom = bytearray(self.rom)
        rom[0x064C98] ^= 1
        with self.assertRaisesRegex(ValueError, "raw Thumb dispatch tail"):
            _resolve_thumb_indexed_dispatches(bytes(rom), self.v2_payload)

    def test_dispatch_resolution_fails_closed_when_a_target_leaves_the_rom(self):
        rom = bytearray(self.rom)
        rom[0x064CA4 : 0x064CA8] = (0).to_bytes(4, "little")
        with self.assertRaisesRegex(ValueError, "target outside fixed ROM"):
            _resolve_thumb_indexed_dispatches(bytes(rom), self.v2_payload)

    def test_dispatch_resolution_is_bound_to_the_frozen_frontier_identity(self):
        payload = copy.deepcopy(self.v2_payload)
        frontiers = payload["frontiers"]
        frontier = next(
            item for item in frontiers if item["id"] == "frontier-000032"
        )
        frontier["source"]["instruction_offset"] += 2
        with self.assertRaisesRegex(ValueError, "frozen v2 frontier"):
            _resolve_thumb_indexed_dispatches(self.rom, payload)

    def test_independent_raw_resolver_rebuilds_the_same_dispatch_contract(self):
        exported = _resolve_thumb_indexed_dispatches(self.rom, self.v2_payload)
        rebuilt = _resolve_thumb_indexed_dispatches_independently(
            self.rom, self.v2_payload
        )
        self.assertEqual(exported, rebuilt)

    def test_verifier_implementation_hash_is_bound_to_the_requested_root(self):
        expected = hashlib.sha256(
            (ROOT / "tools/verify_rom_cfg_inventory_v3.py").read_bytes()
        ).hexdigest()
        with mock.patch(
            "tools.verify_rom_cfg_inventory_v3.__file__",
            "/tmp/non-repository-verifier-copy.py",
        ):
            implementation = verifier_implementation(ROOT)
        self.assertEqual(expected, implementation["verifier_sha256"])


class RomCfgInventoryV3IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact = Path(cls.temporary.name).resolve() / "cfg-v3"
        cls.manifest = export_rom_cfg_inventory_v3(ROOT, cls.artifact)
        cls.payload_raw = (cls.artifact / "rom-cfg-inventory-v3.json").read_bytes()
        cls.payload = json.loads(cls.payload_raw)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_extends_the_frozen_v2_graph_by_exactly_one_resolver_generation(self):
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual(
            "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3",
            self.payload["base_cfg"]["graph_denominator_sha256"],
        )
        self.assertEqual(263, self.payload["base_cfg"]["root_count"])
        self.assertEqual(357, self.payload["base_cfg"]["indirect_frontier_count"])
        resolution = self.payload["static_dispatches"]
        self.assertEqual(29, resolution["resolved_frontier_count"])
        self.assertEqual(328, resolution["unresolved_baseline_indirect_frontier_count"])
        self.assertEqual(677, resolution["ordered_edge_count"])
        self.assertEqual(189, self.payload["extension"]["base_entry_reference_count"])
        self.assertEqual(101, self.payload["extension"]["new_entry_seed_count"])
        self.assertEqual(
            {
                "decoded_basic_block_count": 891,
                "decoded_instruction_count": 4_698,
                "frontier_count": 16,
                "frontier_reasons": {
                    "indirect_pc_target": 15,
                    "unsupported_armv4t_instruction": 1,
                },
                "reachable_instruction_bytes": 9_902,
            },
            self.payload["extension"]["summary"],
        )
        self.assertEqual(45_570, self.payload["combined_summary"]["decoded_instruction_count"])
        self.assertEqual(8_616, self.payload["combined_summary"]["decoded_basic_block_count"])
        self.assertEqual(96_086, self.payload["combined_summary"]["reachable_instruction_bytes"])
        self.assertEqual(353, self.payload["combined_summary"]["frontier_count"])
        self.assertEqual(
            {"bios_swi_external": 7, "indirect_pc_target": 343, "unsupported_armv4t_instruction": 3},
            self.payload["combined_summary"]["frontier_reasons"],
        )
        self.assertEqual(290, self.payload["extension_policy"]["dispatch_target_count"])
        self.assertEqual(101, self.payload["extension_policy"]["new_entry_seed_count"])
        self.assertFalse(self.payload["extension_policy"]["recursive_resolution_performed"])

        remaining = {
            item["source"].get("instruction_offset")
            for item in self.payload["extension"]["frontiers"]
            if item["reason"] == "indirect_pc_target"
        }
        self.assertTrue({0x06EEE0, 0x081356}.issubset(remaining))

    def test_artifact_is_independently_verified(self):
        report = verify_rom_cfg_inventory_v3(ROOT, self.artifact)
        self.assertTrue(report["verified"], report)
        self.assertEqual(29, report["resolved_frontier_count"])
        self.assertEqual(101, report["new_entry_seed_count"])
        self.assertEqual(
            self.payload["extension"]["summary"]["decoded_instruction_count"],
            report["independently_rebuilt_instruction_count"],
        )

    def test_repository_artifact_is_independently_verified(self):
        report = verify_rom_cfg_inventory_v3(
            ROOT, ROOT / "artifacts/rom-cfg-inventory-v3"
        )
        self.assertTrue(report["verified"], report)
        self.assertEqual(29, report["resolved_frontier_count"])
        self.assertEqual(101, report["new_entry_seed_count"])
        self.assertEqual(4_698, report["independently_rebuilt_instruction_count"])

    def test_verifier_rejects_block_tampering_after_file_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            forged = Path(directory).resolve() / "forged"
            shutil.copytree(self.artifact, forged)
            payload_path = forged / "rom-cfg-inventory-v3.json"
            payload = json.loads(payload_path.read_bytes())
            payload["extension"]["blocks"][0]["bytes_sha256"] = "0" * 64
            payload_raw = _canonical_json(payload)
            payload_path.write_bytes(payload_raw)
            manifest_path = forged / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][payload_path.name] = {
                "size": len(payload_raw),
                "sha256": hashlib.sha256(payload_raw).hexdigest(),
            }
            manifest_path.write_bytes(_canonical_json(manifest))

            report = verify_rom_cfg_inventory_v3(ROOT, forged)
            self.assertFalse(report["verified"])
            self.assertTrue(
                any("block" in error.lower() for error in report["errors"]), report
            )


if __name__ == "__main__":
    unittest.main()
