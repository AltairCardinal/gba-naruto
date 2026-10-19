"""Tier-1 projection and real Tier-2 acceptance of the post-story four-packet batch."""

from __future__ import annotations

import gzip
import hashlib
import inspect
import json
import unittest
from pathlib import Path
from unittest import mock

from tools import audit_rom_byte_coverage as auditor


ROOT = Path(__file__).resolve().parents[1]
BATCHES = {
    "rom-fixed-index-u8-tail-v1": (1, 4),
    "rom-story-selector-dependency-cfg-v1": (1, 80),
    "rom-task-callback-078e38-closure-v1": (16, 778),
    "rom-cfg-proven-roots-v21": (3, 116),
}
BUILDERS = (
    "_fixed_index_u8_tail_claims",
    "_story_selector_dependency_cfg_claims",
    "_task_callback_078e38_closure_claims",
    "_cfg_proven_roots_v21_claims",
)
CODE_KIND = "cfg_proven_roots_v21_reachable_instruction_bytes"
LITERAL_KIND = "cfg_proven_roots_v21_consumed_literal_word_bytes"
RECEIPTS = ROOT / "notes/evidence/rom-post-story-four-packet-tier2-20260905"
HOLES = (
    (0x078E6E, 0x078E70), (0x078F02, 0x078F04),
    (0x07905E, 0x079060), (0x079106, 0x079108), (0x079146, 0x079148),
)
CFG_EXPECTED = {
    "cfg_reachable_thumb_code_bytes": 173_058,
    "cfg_promoted_unknown_bytes": 174_046,
    "cfg_primary_claim_count": 4_059,
    "cfg_code_claim_kind_count": 54,
    "cfg_code_claim_kind_denominator_sha256":
        "c8ffed470f28393f8a829d3312ac74083d60ae4e719d82614993d6b973fa3f11",
}


def read_historical_coverage():
    path = ROOT / "notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz"
    raw = gzip.decompress(path.read_bytes())
    if hashlib.sha256(raw).hexdigest() != (
            "1c6af01a54f3522ba277a4744b5b821d53588b853b3e7755902c65431df584b6"):
        raise ValueError("historical canonical identity changed")
    return json.loads(raw)


def read_baseline():
    coverage = read_historical_coverage()
    # Replay the entire batch from the same pre-promotion claim set even after
    # the real canonical advances; never promote an already promoted sibling.
    return [row for row in coverage["claims"]
            if row.get("promotion_batch") not in BATCHES]


def primary_ranges(claims):
    return sorted(tuple(row["range"]) for row in claims
                  if row.get("role") == "primary")


class V21QuickProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.PRIOR = read_baseline()
        cls.CLAIMS = auditor._cfg_proven_roots_v21_claims(ROOT, cls.ROM, cls.PRIOR)

    def test_exact_unknown_ranges_preserve_cross_owner_instruction(self):
        self.assertEqual(
            [(0x063400, 0x06345E), (0x06347E, 0x063490), (0x063490, 0x063494)],
            [tuple(row["range"]) for row in self.CLAIMS],
        )
        self.assertEqual((3, 116), (len(self.CLAIMS), sum(
            b - a for a, b in primary_ranges(self.CLAIMS))))
        self.assertEqual([CODE_KIND, CODE_KIND, LITERAL_KIND],
                         [row["claim_kind"] for row in self.CLAIMS])
        self.assertEqual(["thumb", "thumb", None],
                         [row["mode"] for row in self.CLAIMS])
        self.assertTrue(all(row["current_unknown_verified_by_auditor"]
                            and row["unresolved_frontier_preserved"]
                            and not row["structured_return_claimed"]
                            for row in self.CLAIMS))
        owner = next(row for row in self.PRIOR if row["id"] ==
                     "consumer-code-battle_effect_sequence_bindings-06345e")
        self.assertEqual([0x06345E, 0x06347E], owner["range"])

    def test_wiring_identity_and_active_only_registry(self):
        source = inspect.getsource(auditor.build_manifest)
        previous = f"claims += {BUILDERS[-2]}(root, rom, claims)"
        packet = f"claims += {BUILDERS[-1]}(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertIn(CODE_KIND, auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])
        self.assertEqual(hashlib.sha256(
            (ROOT / "tools/verify_rom_cfg_proven_roots_v21.py").read_bytes()
        ).hexdigest(), auditor.CFG_PROVEN_ROOTS_V21_VERIFIER_SHA256)
        # Absent staged claims must not alter the old canonical denominator.
        self.assertEqual(51, auditor._cfg_code_aggregate(self.PRIOR)[
            "cfg_code_claim_kind_count"])

    def test_rejects_non_unknown_bytes_and_unaccepted_verifier_report(self):
        prior = [*self.PRIOR, {
            "id": "synthetic-v21-overlap", "range": [0x06347E, 0x063480],
            "role": "primary", "primary_class": "synthetic", "claim_kind": "synthetic",
        }]
        with self.assertRaisesRegex(ValueError, "current unknown"):
            auditor._cfg_proven_roots_v21_claims(ROOT, self.ROM, prior)
        from tools import verify_rom_cfg_proven_roots_v21 as verifier
        original = verifier.verify_artifact

        def candidate_report(*args, **kwargs):
            return {**original(*args, **kwargs), "artifact_status": "candidate"}

        with mock.patch.object(verifier, "verify_artifact", side_effect=candidate_report):
            with self.assertRaisesRegex(ValueError, "verifier contract"):
                auditor._cfg_proven_roots_v21_claims(ROOT, self.ROM, self.PRIOR)


class PostStoryFourPacketQuickProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.PRIOR = read_baseline()
        cls.CLAIMS = []
        for builder in BUILDERS:
            cls.CLAIMS.extend(getattr(auditor, builder)(
                ROOT, cls.ROM, [*cls.PRIOR, *cls.CLAIMS]))

    def test_exact_four_packet_denominator_and_linear_union(self):
        for batch, expected in BATCHES.items():
            selected = [row for row in self.CLAIMS if row["promotion_batch"] == batch]
            self.assertEqual(expected, (len(selected), sum(
                b - a for a, b in primary_ranges(selected))), batch)
        ranges = primary_ranges([*self.PRIOR, *self.CLAIMS])
        self.assertTrue(all(left[1] <= right[0]
                            for left, right in zip(ranges, ranges[1:])))
        classified = sum(end - start for start, end in ranges)
        self.assertEqual((6_203_707, 87_749),
                         (classified, len(self.ROM) - classified))
        self.assertEqual((21, 978), (len(self.CLAIMS), sum(
            end - start for start, end in primary_ranges(self.CLAIMS))))
        for start, end in HOLES:
            self.assertFalse(any(a < end and start < b for a, b in ranges))

    def test_combined_cfg_aggregate_is_derived_from_all_packet_claims(self):
        aggregate = auditor._cfg_code_aggregate([*self.PRIOR, *self.CLAIMS])
        self.assertEqual(CFG_EXPECTED,
                         {key: aggregate[key] for key in CFG_EXPECTED})


class PostStoryFourPacketCanonicalTests(unittest.TestCase):
    def test_real_canonical_claims_segments_and_unknown_holes(self):
        coverage = read_historical_coverage()
        self.assertEqual((6_203_707, 87_749, 16_891), tuple(
            coverage["summary"][key] for key in
            ("classified_bytes", "unknown_bytes", "claim_count")))
        for batch, expected in BATCHES.items():
            selected = [row for row in coverage["claims"]
                        if row.get("promotion_batch") == batch]
            self.assertEqual(expected, (len(selected), sum(
                b - a for a, b in primary_ranges(selected))), batch)
        end = classified = unknown = 0
        for segment in coverage["segments"]:
            start, stop = segment["range"]
            self.assertEqual(end, start)
            self.assertGreater(stop, start)
            end = stop
            if segment["primary_class"] == "unknown":
                unknown += stop - start
            else:
                self.assertEqual(1, len(segment["primary_claim_ids"]))
                classified += stop - start
        self.assertEqual((6_291_456, 6_203_707, 87_749), (end, classified, unknown))
        self.assertEqual(coverage["summary"]["segment_count"], len(coverage["segments"]))
        aggregate = auditor._cfg_code_aggregate(coverage["claims"])
        self.assertEqual(CFG_EXPECTED, {key: aggregate[key] for key in CFG_EXPECTED})
        for start, end in HOLES:
            owner = next(row for row in coverage["segments"]
                         if row["range"][0] <= start and end <= row["range"][1])
            self.assertEqual("unknown", owner["primary_class"])
        owner = next(row for row in coverage["segments"]
                     if row["range"][0] <= 0x06347C < row["range"][1])
        self.assertEqual(["consumer-code-battle_effect_sequence_bindings-06345e"],
                         owner["primary_claim_ids"])

    def test_real_rebuild_receipt_is_non_degraded(self):
        receipt = json.loads((RECEIPTS / "coverage-guard.json").read_text())
        self.assertEqual(("completed", 0, False), tuple(
            receipt[key] for key in ("reason", "exit_code", "degraded")))
        command = " ".join(receipt["command"])
        self.assertIn("tools/audit_rom_byte_coverage.py", command)
        self.assertIn("--write", command)
        self.assertIn("sequel/rom-byte-coverage.json", command)

    def test_persistent_receipt_binds_historical_canonical_and_raw_guard(self):
        # A fresh checkout must not need an ignored build/ experiment directory.
        manifest = json.loads((RECEIPTS / "manifest.json").read_text())
        self.assertEqual("rom-post-story-four-packet-tier2-receipts-v1", manifest["schema"])
        # This receipt predates the selector repair. Preserve its original input
        # identity while the separate proof test continues binding live canonical.
        history = ROOT / "notes/evidence/rom-evidence-selector-repair-20260905"
        previous = gzip.decompress((history / "coverage-before.json.gz").read_bytes())
        self.assertEqual(hashlib.sha256(previous).hexdigest(),
                         manifest["canonical_coverage_sha256"])
        self.assertEqual(hashlib.sha256((history / "proof-before.json").read_bytes()).hexdigest(),
                         manifest["proof_spec_sha256"])
        guard_raw = (RECEIPTS / "coverage-guard.json").read_bytes()
        self.assertEqual(hashlib.sha256(guard_raw).hexdigest(),
                         manifest["files"]["coverage-guard.json"]["sha256"])
        self.assertEqual(len(guard_raw),
                         manifest["files"]["coverage-guard.json"]["size_bytes"])


class PostStoryFourPacketProofSpecTests(unittest.TestCase):
    def test_proof_binds_real_canonical_and_ten_batch_evidence_files(self):
        gate = json.loads((ROOT / "sequel/reverse-engineering-proof.json")
                          .read_text())["gates"]["rom_byte_coverage"]
        evidence = {row["path"]: row["sha256"] for row in gate["evidence"]}
        payloads = (
            ("rom-fixed-index-u8-tail-v1", "rom-fixed-index-u8-tail.json"),
            ("rom-story-selector-dependency-cfg-v1", "rom-story-selector-dependency-cfg-v1.json"),
            ("rom-task-callback-078e38-closure-v1", "rom-task-callback-078e38-closure-v1.json"),
            ("rom-cfg-proven-roots-v21", "rom-cfg-proven-roots-v21.json"),
            ("rom-post-story-dependency-precoverage-v1", "rom-byte-coverage.json.gz"),
        )
        for directory, payload in payloads:
            for name in ("manifest.json", payload):
                path = f"artifacts/{directory}/{name}"
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                                 evidence.get(path), path)
        canonical_raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
        self.assertEqual(hashlib.sha256(canonical_raw).hexdigest(),
                         evidence["sequel/rom-byte-coverage.json"])
        coverage_verifiers = [row for row in gate["verifiers"]
                              if "tools/audit_rom_byte_coverage.py" in row["command"]]
        self.assertEqual(1, len(coverage_verifiers))
        verifier = coverage_verifiers[0]
        self.assertEqual(hashlib.sha256((ROOT / "tools/audit_rom_byte_coverage.py")
                                       .read_bytes()).hexdigest(), verifier["script_sha256"])
        # Historical replay above remains fixed; the live contract must follow
        # the real canonical, independently checked by each batch's acceptance.
        summary = json.loads(canonical_raw)["summary"]
        expected = {key: summary[key] for key in (
            "classified_bytes", "unknown_bytes", "claim_count", "segment_count",
            *CFG_EXPECTED)}
        for key, value in expected.items():
            self.assertEqual(value, verifier["contract"]["assertions"][f"/summary/{key}"])
        commands = [row["command"] for row in gate["verifiers"]]
        for script in ("verify_rom_fixed_index_u8_tail.py",
                       "verify_rom_story_selector_dependency_cfg.py",
                       "verify_rom_task_callback_078e38_closure.py",
                       "verify_rom_cfg_proven_roots_v21.py"):
            self.assertFalse(any(f"tools/{script}" in command for command in commands))
        self.assertGreaterEqual(len(gate["evidence"]), 183)
        self.assertGreaterEqual(len(gate["verifiers"]), 96)


if __name__ == "__main__":
    unittest.main()
