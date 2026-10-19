#!/usr/bin/env python3
"""TDD tests for the callback alignment-gap pure producer."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import unittest

from tools import rom_small_cfg_callback_gaps_producer as producer


PACKET_DIR = Path(__file__).resolve().parent
REPO_ROOT = next(parent for parent in PACKET_DIR.parents if (parent / "rom/base.gba").is_file())
CONTRACT_PATH = REPO_ROOT / "tools/data/rom-small-cfg-dependency-v1/callback_gaps.json"
ROM_PATH = REPO_ROOT / "rom/base.gba"
SOURCE_PATH = REPO_ROOT / "artifacts/rom-task-callback-078e38-closure-v1/rom-task-callback-078e38-closure-v1.json"
BASELINE_PATH = REPO_ROOT / "notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _put_halfword(rom: bytearray, offset: int, value: int) -> None:
    rom[offset : offset + 2] = value.to_bytes(2, "little")


def _align4_fixture(final_halfword: int, *, literal_value: bytes = b"ABCD") -> tuple[bytes, list[list[int]], list[list[int]], list[list[object]]]:
    rom = bytearray(64)
    code_ranges = [[4, 10]]
    literal_ranges = [[12, 16]]
    _put_halfword(rom, 8, final_halfword)
    rom[12:16] = literal_value
    # LDR literal at 0x06: align(0x06 + 4, 4) + 1 * 4 = 0x0c.
    _put_halfword(rom, 6, 0x4801)
    binding = [[6, 12, literal_value.hex()]]
    return bytes(rom), code_ranges, literal_ranges, binding


class ProducerTests(unittest.TestCase):
    def test_relocated_thumb_b_positive_and_negative(self) -> None:
        cases = [
            (0xE006, 24),  # target = 0x08 + 4 + 0x0c = 0x18
            (0xE7FD, 6),  # signed imm11 = -3, target = 0x0c - 0x06 = 0x06
        ]
        for halfword, expected_target in cases:
            with self.subTest(halfword=hex(halfword)):
                rom, code, literals, bindings = _align4_fixture(halfword)
                rows = producer.derive_boundaries(rom, code, literals, bindings)
                self.assertEqual(len(rows), 1)
                terminal = rows[0]["terminal"]
                self.assertEqual(terminal["kind"], "unconditional_branch")
                self.assertEqual(terminal["offset"], 8)
                self.assertEqual(terminal["raw_hex"], halfword.to_bytes(2, "little").hex())
                self.assertEqual(terminal["target"], expected_target)

    def test_relocated_bx_r0_is_indirect_pc_target(self) -> None:
        rom, code, literals, bindings = _align4_fixture(0x4700)
        rows = producer.derive_boundaries(rom, code, literals, bindings)
        self.assertEqual(rows[0]["terminal"], {
            "kind": "indirect_pc_target",
            "offset": 8,
            "raw_hex": "0047",
            "register": 0,
        })

    def test_zero_gap_is_not_promoted(self) -> None:
        rom = bytearray(32)
        _put_halfword(rom, 6, 0xE000)
        _put_halfword(rom, 4, 0x4800)
        rom[8:12] = b"ABCD"
        self.assertEqual(producer.derive_boundaries(bytes(rom), [[0, 8]], [[8, 12]], [[4, 8, "41424344"]]), [])

    def test_nonzero_gap_fails_closed(self) -> None:
        rom, code, literals, bindings = _align4_fixture(0xE006)
        mutated = bytearray(rom)
        mutated[10] = 1
        with self.assertRaises(ValueError):
            producer.derive_boundaries(bytes(mutated), code, literals, bindings)

    def test_fallthrough_and_conditional_branch_fail_closed(self) -> None:
        for final_halfword in (0x1C00, 0xD001):
            with self.subTest(final_halfword=hex(final_halfword)):
                rom, code, literals, bindings = _align4_fixture(final_halfword)
                with self.assertRaises(ValueError):
                    producer.derive_boundaries(rom, code, literals, bindings)

    def test_range_overlap_fails_closed(self) -> None:
        rom, _, literals, bindings = _align4_fixture(0xE006)
        with self.assertRaises(ValueError):
            producer.derive_boundaries(rom, [[0, 10], [8, 12]], literals, bindings)
        with self.assertRaises(ValueError):
            producer.derive_boundaries(rom, [[4, 10]], [[8, 16]], bindings)

    def test_missing_or_erroneous_literal_binding_fails_closed(self) -> None:
        rom, code, literals, bindings = _align4_fixture(0xE006)
        for bad_bindings in ([], [[6, 12, "00000000"]], [[6, 16, "41424344"]], [[8, 12, "41424344"]]):
            with self.subTest(bad_bindings=bad_bindings):
                with self.assertRaises(ValueError):
                    producer.derive_boundaries(rom, code, literals, bad_bindings)

    def test_known_baseline_overlap_fails_closed(self) -> None:
        rom = bytearray(range(32))
        rom[10:12] = b"\x00\x00"
        segments = [
            {"range": [0, 10], "primary_class": "unknown", "primary_claim_ids": [], "secondary_claim_ids": [], "unknown_reason": "fixture"},
            {"range": [10, 12], "primary_class": "fixed_table", "primary_claim_ids": ["known"], "secondary_claim_ids": []},
            {"range": [12, 32], "primary_class": "unknown", "primary_claim_ids": [], "secondary_claim_ids": [], "unknown_reason": "fixture"},
        ]
        with self.assertRaises(ValueError):
            producer.project_baseline_owners(bytes(rom), [[4, 10]], [[12, 16]], segments, [[10, 12]])

    def test_input_identity_mismatches_fail_before_parsing(self) -> None:
        rom = ROM_PATH.read_bytes()
        source = SOURCE_PATH.read_bytes()
        baseline = gzip.open(BASELINE_PATH, "rb").read()
        contract = CONTRACT_PATH.read_bytes()
        with self.assertRaises(ValueError):
            producer.build_payload(rom, source, baseline, contract + b"\n")
        changed_rom = bytearray(rom)
        changed_rom[0] ^= 1
        with self.assertRaises(ValueError):
            producer.build_payload(bytes(changed_rom), source, baseline, contract)
        with self.assertRaises(ValueError):
            producer.build_payload(rom, source + b"\n", baseline, contract)
        with self.assertRaises(ValueError):
            producer.build_payload(rom, source, baseline + b"\n", contract)

    def test_real_build_has_five_gaps_and_preserves_unknown_provenance(self) -> None:
        rom = ROM_PATH.read_bytes()
        source = SOURCE_PATH.read_bytes()
        baseline = gzip.open(BASELINE_PATH, "rb").read()
        contract = CONTRACT_PATH.read_bytes()
        payload = producer.build_payload(rom, source, baseline, contract)

        self.assertEqual(list(payload), ["schema", "rom", "source_inputs", "baseline", "summary", "boundaries", "promotion", "scope"])
        self.assertEqual(payload["schema"], "rom-task-callback-078e38-alignment-gaps-v1")
        self.assertEqual(payload["summary"], {
            "gap_count": 5,
            "indirect_pc_target_count": 1,
            "promotion_bytes": 10,
            "unconditional_branch_count": 4,
        })
        self.assertEqual(len(payload["boundaries"]), 5)
        self.assertEqual(payload["promotion"]["claim_count"], 5)
        self.assertEqual(payload["promotion"]["promotion_bytes"], 10)
        self.assertTrue(all(set(claim) == {"id", "kind", "range", "bytes_sha256"} for claim in payload["promotion"]["claims"]))
        for row in payload["boundaries"]:
            start, end = row["range"]
            self.assertEqual(rom[start:end], b"\x00" * (end - start))
            self.assertEqual(row["bytes_sha256"], _sha(rom[start:end]))
            self.assertTrue(row["baseline_owners"]["gap"])
            for segment in row["baseline_owners"]["gap"]:
                self.assertEqual(segment["primary_class"], "unknown")
                self.assertEqual(segment["primary_claim_ids"], [])
                self.assertEqual(segment["secondary_claim_ids"], [])
            self.assertTrue(row["baseline_owners"]["left"])
            self.assertTrue(row["baseline_owners"]["right"])


if __name__ == "__main__":
    unittest.main()
