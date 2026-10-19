"""Pin the renderer script pointer-pool promotion in the live canonical ledger.

The permanent receipt under ``notes/evidence/rom-small-cfg-batch-formal-20260930-v1``
keeps the historical 87,631-byte ledger state frozen; this module checks the
live canonical, which advances with every accepted promotion.
"""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BATCH = "rom-renderer-script-pointer-pool-records-v1"
CLAIM_ID = "renderer-script-pointer-pool-0cea"
POOL_RANGE = (0x0CEA, 0x12F0)
POOL_BYTES = 1_542
RECORD_COUNT = 27
PRIMARY_CLASS = "fixed_cfg_consumer_renderer_command_script"
CLAIM_KIND = "fixed_cfg_consumer_renderer_command_script_bytes"
ROM_BYTES = 6_291_456
ARTIFACT = Path("artifacts/rom-renderer-script-pointer-pool-records-v1")
VERIFIER = Path("tools/verify_rom_renderer_script_pointer_pool_records.py")


def _coverage():
    return json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8"))


def _proof():
    return json.loads((ROOT / "sequel/reverse-engineering-proof.json").read_text(encoding="utf-8"))


class LiveCanonicalTests(unittest.TestCase):
    def setUp(self):
        self.coverage = _coverage()

    def test_pool_claim_is_materialized_in_the_live_canonical(self):
        claims = [
            row for row in self.coverage["claims"] if row.get("promotion_batch") == BATCH
        ]
        self.assertEqual(len(claims), 1)
        claim = claims[0]
        self.assertEqual(claim["id"], CLAIM_ID)
        self.assertEqual(tuple(claim["range"]), POOL_RANGE)
        self.assertEqual(claim["primary_class"], PRIMARY_CLASS)
        self.assertEqual(claim["claim_kind"], CLAIM_KIND)
        self.assertTrue(claim["current_unknown_verified_by_auditor"])
        self.assertTrue(claim["pointer_pool_slot_denominator_verified"])
        self.assertFalse(claim["runtime_reachability_claimed"])
        self.assertFalse(claim["editing_writeback_relocation_safe_claimed"])
        self.assertFalse(claim["free_or_allocatable_space_claimed"])

    def test_pool_bytes_match_the_rom(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        start, end = POOL_RANGE
        self.assertEqual(end - start, POOL_BYTES)
        claim = next(row for row in self.coverage["claims"] if row["id"] == CLAIM_ID)
        self.assertEqual(
            hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
        )

    def test_pool_claim_owns_its_segments_exclusively(self):
        claim = next(row for row in self.coverage["claims"] if row["id"] == CLAIM_ID)
        start, end = POOL_RANGE
        segments = [
            row
            for row in self.coverage["segments"]
            if row["range"][0] < end and start < row["range"][1]
        ]
        self.assertTrue(segments)
        for segment in segments:
            self.assertNotEqual(segment["primary_class"], "unknown")
            self.assertIn(CLAIM_ID, segment["primary_claim_ids"])

    def test_live_canonical_stays_internally_consistent(self):
        summary = self.coverage["summary"]
        self.assertEqual(
            summary["classified_bytes"] + summary["unknown_bytes"], ROM_BYTES
        )
        self.assertEqual(self.coverage["summary"]["accounted_bytes"], ROM_BYTES)
        self.assertTrue(self.coverage["state_inventory_complete"])
        self.assertFalse(self.coverage["semantic_classification_complete"])


class ProofBindingTests(unittest.TestCase):
    def test_proof_binds_the_new_artifact_and_the_live_canonical(self):
        gate = _proof()["gates"]["rom_byte_coverage"]
        evidence = {row["path"]: row["sha256"] for row in gate["evidence"]}
        for path in (
            ARTIFACT / "manifest.json",
            ARTIFACT / "rom-renderer-script-pointer-pool-records.json",
        ):
            self.assertIn(path.as_posix(), evidence)
            self.assertEqual(
                evidence[path.as_posix()],
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
            )
        self.assertEqual(
            evidence["sequel/rom-byte-coverage.json"],
            hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
        )

    def test_proof_binds_the_package_verifier_contract(self):
        gate = _proof()["gates"]["rom_byte_coverage"]
        verifiers = [
            row for row in gate["verifiers"] if VERIFIER.as_posix() in row["command"]
        ]
        self.assertEqual(len(verifiers), 1)
        entry = verifiers[0]
        self.assertEqual(
            entry["script_sha256"],
            hashlib.sha256((ROOT / VERIFIER).read_bytes()).hexdigest(),
        )
        assertions = entry["contract"]["assertions"]
        self.assertEqual(assertions["/verified"], True)
        self.assertEqual(assertions["/errors"], [])
        self.assertEqual(assertions["/record_count"], RECORD_COUNT)
        self.assertEqual(assertions["/promotion_bytes"], POOL_BYTES)

    def test_historical_receipt_still_pins_the_old_ledger_state(self):
        receipt = ROOT / "notes/evidence/rom-small-cfg-batch-formal-20260930-v1"
        report = json.loads((receipt / "formal-report.json").read_text(encoding="utf-8"))
        gate = report["gate_results"]["rom_byte_coverage"]
        self.assertEqual(gate["rom_coverage_audit"]["summary"]["unknown_bytes"], 87_631)
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["blockers"]), 175)


if __name__ == "__main__":
    unittest.main()
