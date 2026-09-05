#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.verify_disproved_bank_candidates import (
    DISPROVED_SPECS,
    verify_disproved_bank_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
PROOFS = json.loads((ROOT / "sequel/bank-proofs.json").read_bytes())["banks"]
ROM = (ROOT / "rom/base.gba").read_bytes()

EXPECTED_SLUGS = {
    "battle-handlers",
    "character-stats-b",
    "encounter-zones",
    "fonts",
    "items",
    "resource-pointers",
    "sprite-animations",
    "story-c",
    "story-d",
    "story-e",
}

EXPECTED_PHYSICAL_ALIAS_BINDINGS = {
    "battle-handlers": {
        "candidate_base_pointer_offsets": [],
        "canonical_base_pointer_offsets": [0x7FA38, 0x7FD88],
        "consumer_code_range": [0x7F934, 0x7F968],
    },
    "character-stats-b": {
        "candidate_base_pointer_offsets": [],
        "canonical_base_pointer_offsets": [0x6D998],
        "consumer_code_range": [0x6D964, 0x6D994],
    },
    "encounter-zones": {
        "candidate_base_pointer_offsets": [
            0x68FE0,
            0x690DC,
            0x6924C,
            0x6927C,
            0x7AB00,
            0x80734,
            0x809C4,
            0x8F508,
        ],
        "canonical_base_pointer_offsets": [
            0x68FE0,
            0x690DC,
            0x6924C,
            0x6927C,
            0x7AB00,
            0x80734,
            0x809C4,
            0x8F508,
        ],
        "consumer_code_range": [0x6921C, 0x6922C],
    },
    "items": {
        "candidate_base_pointer_offsets": [],
        "canonical_base_pointer_offsets": [
            0x6D960,
            0x78F04,
            0x78FC0,
            0x8FC38,
            0x8FFC4,
            0x953A0,
            0x9545C,
        ],
        "consumer_code_range": None,
    },
    "resource-pointers": {
        "candidate_base_pointer_offsets": [0x7B278],
        "canonical_base_pointer_offsets": [],
        "consumer_code_range": [0x7B220, 0x7B25A],
    },
    "sprite-animations": {
        "candidate_base_pointer_offsets": [],
        "canonical_base_pointer_offsets": [0x80B54],
        "consumer_code_range": [0x80B08, 0x80B52],
    },
}


class DisprovedBankCandidateVerifierTests(unittest.TestCase):
    def test_all_fixed_disproved_banks_are_independently_rebuilt(self):
        self.assertEqual(EXPECTED_SLUGS, set(DISPROVED_SPECS))
        for slug in sorted(EXPECTED_SLUGS):
            with self.subTest(slug=slug):
                report = verify_disproved_bank_candidate(ROOT, slug)
                proof = PROOFS[slug]
                self.assertTrue(report["verified"], report)
                self.assertEqual([], report["errors"])
                self.assertEqual(
                    "disproved-bank-candidate-verification-v1", report["schema"]
                )
                self.assertEqual(slug, report["bank"])
                self.assertTrue(report["rejected"])
                self.assertEqual(
                    "independent_physical_bank_candidate",
                    report["rejection_scope"],
                )
                self.assertFalse(
                    report["alternative_logical_consumers_exhaustively_excluded"]
                )
                self.assertEqual(proof["candidate_range"], report["candidate_range"])
                self.assertEqual(proof["candidate_sha256"], report["candidate_sha256"])
                self.assertEqual(proof["bank_sha256"], report["bank_sha256"])
                self.assertEqual(
                    {
                        item["path"]: item["sha256"]
                        for item in proof["evidence"]
                    },
                    report["evidence_sha256"],
                )
                self.assertIn(
                    report["proof_kind"],
                    {
                        "canonical_table_alias",
                        "misaligned_canonical_table_slice",
                        "mixed_font_and_handler_extent",
                        "canonical_visual_matrix_slice",
                        "m4a_song_header_subfield",
                    },
                )

    def test_physical_alias_proofs_bind_literal_denominators_and_consumers(self):
        for slug, expected in EXPECTED_PHYSICAL_ALIAS_BINDINGS.items():
            with self.subTest(slug=slug):
                report = verify_disproved_bank_candidate(ROOT, slug)
                self.assertTrue(report["verified"], report)
                details = report["details"]
                self.assertEqual(
                    expected["candidate_base_pointer_offsets"],
                    details["candidate_base_pointer_offsets"],
                )
                self.assertEqual(
                    expected["canonical_base_pointer_offsets"],
                    details["canonical_base_pointer_offsets"],
                )
                self.assertEqual(
                    expected["consumer_code_range"],
                    details["consumer_code_range"],
                )

    def test_alias_proof_fails_if_fixed_literal_denominator_gains_a_reference(self):
        with patch(
            "tools.verify_disproved_bank_candidates._pointer_offsets",
            return_value=[0x1234],
        ):
            report = verify_disproved_bank_candidate(ROOT, "battle-handlers")
        self.assertFalse(report["verified"], report)
        self.assertTrue(
            any("pointer denominator changed" in error for error in report["errors"]),
            report,
        )

    def test_encounter_alias_binds_runtime_row_and_static_flag_consumer(self):
        report = verify_disproved_bank_candidate(ROOT, "encounter-zones")
        self.assertTrue(report["verified"], report)
        self.assertEqual(
            {
                "map_id": 41,
                "row_file_offset": 0x53DE30,
                "row_stride": 32,
                "flag_byte_offset": 0x1D,
                "resource_checks_all_passed": True,
            },
            report["details"]["runtime_map_binding"],
        )

    def test_every_candidate_fails_closed_when_its_rom_bytes_change(self):
        for slug, spec in DISPROVED_SPECS.items():
            with self.subTest(slug=slug):
                tampered = bytearray(ROM)
                tampered[spec["candidate_range"][0]] ^= 1
                report = verify_disproved_bank_candidate(
                    ROOT, slug, rom=bytes(tampered)
                )
                self.assertFalse(report["verified"], report)
                self.assertTrue(report["errors"])

    def test_unknown_bank_is_rejected_without_falling_back_to_labels(self):
        report = verify_disproved_bank_candidate(ROOT, "not-a-bank")
        self.assertFalse(report["verified"])
        self.assertTrue(any("unsupported" in error for error in report["errors"]))

    def test_story_candidates_are_bound_to_the_descriptor_plus_four_field(self):
        expected = {
            "story-c": (8, 0x538FEC, 0x08464A40),
            "story-d": (11, 0x53AB74, 0x08464B48),
            "story-e": (14, 0x53C3BC, 0x08464C5C),
        }
        for slug, (sound_id, descriptor_offset, voicegroup_pointer) in expected.items():
            with self.subTest(slug=slug):
                report = verify_disproved_bank_candidate(ROOT, slug)
                self.assertEqual(sound_id, report["details"]["sound_id"])
                self.assertEqual(
                    descriptor_offset, report["details"]["descriptor_offset"]
                )
                self.assertEqual(
                    voicegroup_pointer, report["details"]["voicegroup_pointer"]
                )


if __name__ == "__main__":
    unittest.main()
