#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.export_rom_unbound_lz77_inventory import (
    export_rom_unbound_lz77_inventory,
)
from tools.verify_rom_unbound_lz77_inventory import (
    decode_lz77_strict,
    verify_rom_unbound_lz77_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"


class RomUnboundLz77InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact_dir = Path(cls.temporary.name) / "artifact"
        cls.payload = export_rom_unbound_lz77_inventory(
            ROOT, cls.artifact_dir
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_the_fixed_strict_unknown_unreferenced_denominator(self):
        self.assertEqual("rom-unbound-lz77-inventory-v1", self.payload["schema"])
        self.assertEqual(ROM_SHA256, self.payload["rom"]["sha256"])
        self.assertEqual(
            {
                "strict_candidate_count": 1_099,
                "raw_unknown_unreferenced_candidate_count": 43,
                "raw_unknown_unreferenced_compressed_bytes": 14_737,
                "raw_unknown_unreferenced_decompressed_bytes": 30_774,
                "selected_record_count": 41,
                "selected_compressed_bytes": 14_725,
                "selected_decompressed_bytes": 30_772,
            },
            self.payload["summary"],
        )
        self.assertEqual(
            "2db24f2804ad3d6c11d2cee7cde9a0205e86ae06eab4a02339c7ade130e41505",
            self.payload["bundles"]["compressed"]["sha256"],
        )
        self.assertEqual(
            "7027b4c7ca61cf2b5f92dd3851cefe24bf5b244c7354756504432901055cdd65",
            self.payload["bundles"]["decompressed"]["sha256"],
        )

    def test_records_are_lossless_ordered_nonoverlapping_and_not_overclaimed(self):
        compressed = (self.artifact_dir / "streams.lz77.bin").read_bytes()
        decompressed = (self.artifact_dir / "payloads.bin").read_bytes()
        previous_end = -1
        for record in self.payload["records"]:
            start, end = record["range"]
            self.assertGreaterEqual(start, previous_end)
            self.assertEqual("lz77_syntax_unbound", record["classification"])
            self.assertEqual(0, record["aligned_pointer_reference_count"])
            self.assertFalse(record["runtime_reachability_claimed"])
            compressed_slice = compressed[
                record["compressed_bundle_offset"] :
                record["compressed_bundle_offset"] + record["compressed_size"]
            ]
            decompressed_slice = decompressed[
                record["decompressed_bundle_offset"] :
                record["decompressed_bundle_offset"]
                + record["decompressed_size"]
            ]
            self.assertEqual(end - start, len(compressed_slice))
            self.assertEqual(
                record["compressed_sha256"],
                hashlib.sha256(compressed_slice).hexdigest(),
            )
            self.assertEqual(
                record["decompressed_sha256"],
                hashlib.sha256(decompressed_slice).hexdigest(),
            )
            previous_end = end

        selected = {tuple(record["range"]) for record in self.payload["records"]}
        self.assertIn((0x3E51E8, 0x3E52C5), selected)
        self.assertNotIn((0x3E52C3, 0x3E52C9), selected)
        self.assertIn((0x3EA38C, 0x3EA472), selected)
        self.assertNotIn((0x3EA470, 0x3EA476), selected)

    def test_independent_verifier_reconstructs_scan_and_bundles(self):
        report = verify_rom_unbound_lz77_inventory(ROOT, self.artifact_dir)
        self.assertEqual(
            {
                "schema": "rom-unbound-lz77-inventory-verification-v1",
                "verified": True,
                **self.payload["summary"],
                "errors": [],
            },
            report,
        )

    def test_verifier_rejects_tampered_bundle_record_and_scope(self):
        cases = []
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base"
            shutil.copytree(self.artifact_dir, base)

            bundle = Path(directory) / "bundle"
            shutil.copytree(base, bundle)
            path = bundle / "streams.lz77.bin"
            data = bytearray(path.read_bytes())
            data[0] ^= 1
            path.write_bytes(data)
            cases.append(bundle)

            record = Path(directory) / "record"
            shutil.copytree(base, record)
            path = record / "inventory.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["records"][0]["range"][1] -= 1
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            cases.append(record)

            scope = Path(directory) / "scope"
            shutil.copytree(base, scope)
            path = scope / "inventory.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["scope"] = copy.deepcopy(payload["scope"])
            payload["scope"]["runtime_reachability_complete"] = True
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            cases.append(scope)

            for artifact in cases:
                with self.subTest(artifact=artifact.name):
                    report = verify_rom_unbound_lz77_inventory(ROOT, artifact)
                    self.assertFalse(report["verified"])
                    self.assertTrue(report["errors"])

    def test_strict_decoder_rejects_future_copy_overrun_and_truncation(self):
        self.assertIsNone(decode_lz77_strict(bytes.fromhex("10030000800000"), 0))
        self.assertIsNone(
            decode_lz77_strict(bytes.fromhex("1002000040aa0000"), 0)
        )
        self.assertIsNone(decode_lz77_strict(bytes.fromhex("1001000000"), 0))


if __name__ == "__main__":
    unittest.main()
