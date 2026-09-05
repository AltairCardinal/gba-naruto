from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RomBootInterworkContinuationExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import rom_boot_interwork_continuation_contract as contract
        from tools import export_rom_boot_interwork_continuation as exporter

        cls.contract = contract
        cls.exporter = exporter

    def test_frozen_contract_and_raw_ranges(self) -> None:
        payload = self.exporter.build_payload(ROOT)

        self.assertEqual(payload["schema"], self.contract.SCHEMA)
        self.assertEqual(payload["producer"]["unique_direct_bl_offsets"], [0x061086])
        self.assertEqual(payload["producer"]["continuation_root"], 0x06108A)
        self.assertEqual(payload["callee_arm_closure"]["frontier_count"], 0)
        self.assertEqual(
            payload["callee_arm_closure"]["return_offsets"],
            [0x03A4, 0x03B8],
        )

        promotion = payload["promotion"]
        self.assertEqual(promotion["code_ranges"], [[0x06108A, 0x0610D4]])
        self.assertEqual(
            promotion["literal_ranges"],
            [[0x0610D4, 0x0610D8], [0x0610D8, 0x0610DC],
             [0x0610DC, 0x0610E0], [0x0610E0, 0x0610E4],
             [0x0610E4, 0x0610E8]],
        )
        self.assertEqual(promotion["code_bytes"], 74)
        self.assertEqual(promotion["literal_bytes"], 20)
        self.assertEqual(promotion["promotion_bytes"], 94)
        self.assertEqual(
            promotion["union_packed_sha256"],
            "837d10f9c983e6f0530ef9c9eb1afda32dc5fb1b2ec35e5da3fd6dee38a666e0",
        )

    def test_five_literal_bindings_are_exact(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        bindings = payload["thumb_continuation"]["literal_bindings"]

        self.assertEqual(len(bindings), 5)
        self.assertEqual(
            [(row["load_offset"], row["literal_offset"]) for row in bindings],
            [(0x0610A2, 0x0610D4), (0x0610AA, 0x0610D8),
             (0x0610AE, 0x0610DC), (0x0610BA, 0x0610E0),
             (0x0610CA, 0x0610E4)],
        )

    def test_current_unknown_owner_and_scope_are_bound(self) -> None:
        payload = self.exporter.build_payload(ROOT)

        self.assertEqual(
            payload["coverage_baseline"],
            {
                "artifact": "artifacts/rom-boot-interwork-continuation-precoverage-v1",
                "manifest_sha256": "1274d157a6a61c61d1e9b8709f31d97355174118574310d667a5c8f906118bb5",
                "archive_sha256": "7be5ee2d603ac73d77d39bd1911acd5fda4ab1c0ff07d8583e411fcf882645eb",
                "raw_sha256": "984eb8ed8ef72691e1b580b00465d24e1762bb5c0604c35fe76db40153fc42e0",
                "classified_bytes": 6_155_318,
                "unknown_bytes": 136_138,
            },
        )
        self.assertEqual(
            payload["current_unknown_owner"],
            {
                "range": [0x06108A, 0x0610E8],
                "primary_class": "unknown",
                "primary_claim_ids": [],
                "secondary_claim_ids": [],
            },
        )
        self.assertFalse(payload["scope"]["natural_runtime_reachability_complete"])
        self.assertFalse(payload["scope"]["reset_to_root_path_complete"])
        self.assertFalse(payload["scope"]["business_semantics_proven"])
        self.assertFalse(payload["scope"]["holes_padding_free_or_edit_safe"])


if __name__ == "__main__":
    unittest.main()
