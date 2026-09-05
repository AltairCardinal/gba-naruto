from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.verify_similar_table_candidates import (
    _consumer_tables,
    _remaining_candidate_tables,
    verify_manifest,
    verify_repository_manifests,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sequel/similar-table-candidates-v1.json"
ADJUDICATIONS = ROOT / "sequel/similar-table-adjudications-v1.json"


class SimilarTableCandidateManifestTests(unittest.TestCase):
    def test_cli_regenerates_scan_and_adjudications_from_canonical_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            scan = Path(directory) / "scan.json"
            adjudications = Path(directory) / "adjudications.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_similar_table_candidates.py",
                    "--root",
                    ".",
                    "--manifest",
                    str(scan),
                    "--adjudications",
                    str(adjudications),
                    "--regenerate-scan",
                    "--regenerate-adjudications",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            report = verify_repository_manifests(
                ROOT,
                json.loads(scan.read_text(encoding="utf-8")),
                json.loads(adjudications.read_text(encoding="utf-8")),
            )
            self.assertTrue(report["verified"], report["errors"])
            self.assertEqual(114, report["candidate_count"])
            self.assertEqual(0, report["open_candidate_count"])

    def test_current_full_rom_candidate_denominator_is_reproducible(self):
        report = verify_manifest(ROOT, json.loads(MANIFEST.read_text()))

        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(114, report["candidate_count"])
        self.assertEqual(114, report["open_candidate_count"])

    def test_rejects_a_reduced_candidate_denominator(self):
        manifest = json.loads(MANIFEST.read_text())
        tampered = copy.deepcopy(manifest)
        tampered["candidates"].pop()
        tampered["candidate_count"] -= 1

        report = verify_manifest(ROOT, tampered)

        self.assertFalse(report["verified"])
        self.assertIn("manifest differs from strict full-ROM scan", report["errors"])

    def test_current_repository_adjudications_close_only_proven_candidates(self):
        report = verify_repository_manifests(
            ROOT,
            json.loads(MANIFEST.read_text()),
            json.loads(ADJUDICATIONS.read_text()),
        )

        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(114, report["candidate_count"])
        self.assertEqual(114, report["adjudicated_candidate_count"])
        self.assertEqual(0, report["open_candidate_count"])
        self.assertEqual(
            {"accepted": 60, "alias_of": 26, "rejected": 28},
            report["decision_counts"],
        )

    def test_repository_verifier_rejects_a_removed_decision(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        tampered = copy.deepcopy(adjudications)
        tampered["adjudications"].pop()
        tampered["adjudication_count"] -= 1
        tampered["open_candidate_count"] += 1

        report = verify_repository_manifests(
            ROOT, json.loads(MANIFEST.read_text()), tampered
        )

        self.assertFalse(report["verified"])
        self.assertIn(
            "adjudication manifest differs from independently rebuilt evidence",
            report["errors"],
        )

    def test_repository_verifier_rejects_candidate_range_tampering(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        tampered = copy.deepcopy(adjudications)
        decision = next(
            item for item in tampered["adjudications"] if item["candidate_id"] == 28
        )
        decision["candidate_range"][1] -= 4

        report = verify_repository_manifests(
            ROOT, json.loads(MANIFEST.read_text()), tampered
        )

        self.assertFalse(report["verified"])
        self.assertIn(
            "adjudication manifest differs from independently rebuilt evidence",
            report["errors"],
        )

    def test_character_descriptor_terminal_zero_row_is_hash_bound(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        decision = next(
            item for item in adjudications["adjudications"] if item["candidate_id"] == 85
        )

        self.assertEqual("accepted", decision["status"])
        self.assertEqual(
            "canonical_table_plus_zero_terminator", decision["relation"]
        )
        self.assertEqual([5869628, 5869644], decision["terminal_zero_range"])
        self.assertEqual("00" * 16, decision["terminal_zero_hex"])

    def test_cross_table_heuristic_runs_are_rejected_with_contiguous_partitions(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        decisions = {item["candidate_id"]: item for item in adjudications["adjudications"]}

        for candidate_id in (88, 99):
            decision = decisions[candidate_id]
            self.assertEqual("rejected", decision["status"])
            self.assertEqual("crosses_canonical_table_boundary", decision["relation"])
            cursor = decision["candidate_range"][0]
            for partition in decision["partitions"]:
                self.assertEqual(cursor, partition["range"][0])
                cursor = partition["range"][1]
            self.assertEqual(decision["candidate_range"][1], cursor)

    def test_consumer_bound_batch_adjudicates_exact_alias_and_crossing_ranges(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        decisions = {
            item["candidate_id"]: item
            for item in adjudications["adjudications"]
        }

        for candidate_id in (11, 14, 21, 25, 90):
            decision = decisions[candidate_id]
            self.assertEqual("rejected", decision["status"])
            self.assertEqual(
                "crosses_canonical_table_boundary", decision["relation"]
            )
            cursor = decision["candidate_range"][0]
            for partition in decision["partitions"]:
                self.assertEqual(cursor, partition["range"][0])
                cursor = partition["range"][1]
            self.assertEqual(decision["candidate_range"][1], cursor)

        self.assertEqual(
            [
                "battle_effect_subtype_dispatch_table_literal",
                "battle_effect_subtype_dispatch_table",
            ],
            [
                item["semantic_type"]
                for item in decisions[14]["partitions"]
            ],
        )
        self.assertEqual(
            [
                "active_action_description_pointer_table",
                "message_command_pointer_table",
            ],
            [
                item["semantic_type"]
                for item in decisions[90]["partitions"]
            ],
        )

        exact = decisions[76]
        self.assertEqual("accepted", exact["status"])
        self.assertEqual("exact_canonical_table", exact["relation"])
        self.assertEqual([0x464534, 0x4645C4], exact["canonical_range"])
        self.assertEqual(
            "f18662620047b0851ca5ae6d181ac3810a115870add27bb5119d0612b5f6c6a6",
            exact["canonical_sha256"],
        )

        aliases = {
            101: (
                [0x5A6D04, 0x5A6E60],
                "a9bd263418cf363d7ff4280490576c650a236b6ffe01497a01a79b2edc24e091",
            ),
            102: (
                [0x5A7060, 0x5A7114],
                "1231c8f3ac946f9138d1becab3a330aed1421bedc698c746471e7b4157206b71",
            ),
        }
        for candidate_id, (canonical_range, canonical_sha) in aliases.items():
            decision = decisions[candidate_id]
            self.assertEqual("alias_of", decision["status"])
            self.assertEqual("strict_subrange", decision["relation"])
            self.assertEqual(canonical_range, decision["canonical_range"])
            self.assertEqual(canonical_sha, decision["canonical_sha256"])

    def test_candidate_14_literal_is_not_misclassified_as_dispatch_entry_zero(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        decision = next(
            item
            for item in adjudications["adjudications"]
            if item["candidate_id"] == 14
        )

        self.assertEqual([0x76F40, 0x77040], decision["candidate_range"])
        self.assertEqual([0x76F40, 0x76F44], decision["partitions"][0]["range"])
        self.assertEqual(
            [0x76F44, 0x77040], decision["partitions"][1]["range"]
        )

    def test_consumer_provider_rejects_literal_and_complete_table_tail_tampering(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        mutations = (
            (0x76F40, "battle-effect subtype table literal"),
            (0x4645C0, "M4A track-command dispatch table"),
            (0x5997C0, "message-command pointer table"),
            (0x5A6E5C, "low-detail action-name pointer table"),
            (0x5A7110, "passive auxiliary text pointer table"),
        )
        for offset, message in mutations:
            with self.subTest(offset=hex(offset)):
                tampered = bytearray(rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(ValueError, message):
                    _consumer_tables(ROOT, bytes(tampered))

    def test_previously_open_candidates_are_consumer_bound_aliases(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        decisions = {
            item["candidate_id"]: item
            for item in adjudications["adjudications"]
        }
        expected = {
            3: (
                [0x60E34, 0x60EF0],
                "d0abb00332b73cd36637dbfcf5a7811622438f9c6382dc8c8ff45b00455d00ae",
            ),
            4: (
                [0x60EF0, 0x60FA4],
                "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed",
            ),
            92: (
                [0x599F5C, 0x599FF4],
                "70e722a0521ed49bf2ac43cbbee960295332d4b857115b595163da29f7731110",
            ),
            93: (
                [0x59A104, 0x59A1B8],
                "98b063cc49b8ab7b036b612bd81fb3f564187b54fd963e36c9cdc78909d9876b",
            ),
        }
        for candidate_id, (canonical_range, canonical_sha256) in expected.items():
            decision = decisions[candidate_id]
            self.assertEqual("alias_of", decision["status"])
            self.assertEqual("strict_subrange", decision["relation"])
            self.assertEqual(canonical_range, decision["canonical_range"])
            self.assertEqual(canonical_sha256, decision["canonical_sha256"])

    def test_previously_open_consumer_tables_reject_bound_evidence_tampering(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        mutations = (
            (0x08A578, "candidate 3 table-base literal"),
            (0x060E34, "candidate 3 consumer-bound table"),
            (0x060EEC, "candidate 3 consumer-bound table"),
            (0x08A5CE, "candidate 4 table consumer"),
            (0x599FF0, "candidate 92 consumer-bound table"),
            (0x542294, "candidate 92 value-range map"),
            (0x093308, "candidate 93 table-base literal"),
        )
        for offset, message in mutations:
            with self.subTest(offset=hex(offset)):
                tampered = bytearray(rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(ValueError, message):
                    _remaining_candidate_tables(bytes(tampered))

    def test_new_consumer_bound_tables_and_inline_false_positives_are_adjudicated(self):
        adjudications = json.loads(ADJUDICATIONS.read_text())
        decisions = {
            item["candidate_id"]: item
            for item in adjudications["adjudications"]
        }

        accepted = {94, 95, 96, 105, 106, 107, 108, 109, 111, 112, 113, 114}
        self.assertTrue(all(decisions[item]["status"] == "accepted" for item in accepted))
        self.assertTrue(
            all(
                decisions[item]["relation"] == "exact_consumer_bound_table"
                for item in accepted
            )
        )
        self.assertEqual("alias_of", decisions[92]["status"])
        self.assertEqual("strict_subrange", decisions[92]["relation"])
        self.assertEqual(
            [0x599F5C, 0x599FF4], decisions[92]["canonical_range"]
        )
        self.assertEqual(
            "value_range_renderer_text_pointer_table_38",
            decisions[92]["semantic_type"],
        )

        inline = {5, 6, 7, 8, 9, 10, 12, 13, 15, 16, 17, 18, 19, 20, 22, 24, 26, 27}
        for candidate_id in inline:
            decision = decisions[candidate_id]
            self.assertEqual("rejected", decision["status"])
            self.assertEqual("crosses_canonical_table_boundary", decision["relation"])
            self.assertEqual(
                ["thumb_dispatch_literal_pool", "thumb_pc_relative_jump_table"],
                [partition["semantic_type"] for partition in decision["partitions"]],
            )

        self.assertEqual("rejected", decisions[23]["status"])
        self.assertEqual("thumb_literal_pool_not_indexed_table", decisions[23]["relation"])


if __name__ == "__main__":
    unittest.main()
