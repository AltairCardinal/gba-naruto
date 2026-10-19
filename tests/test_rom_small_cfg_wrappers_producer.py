#!/usr/bin/env python3
"""TDD tests for the three-direct-wrapper pure producer."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import unittest

from tools import rom_small_cfg_wrappers_producer as producer


PACKET_DIR = Path(__file__).resolve().parent
REPO_ROOT = next(parent for parent in PACKET_DIR.parents if (parent / "rom/base.gba").is_file())
CONTRACT_PATH = REPO_ROOT / "tools/data/rom-small-cfg-dependency-v1/wrappers.json"
ROM_PATH = REPO_ROOT / "rom/base.gba"
BASELINE_PATH = REPO_ROOT / "notes/evidence/rom-evidence-selector-repair-20260905/coverage-after.json.gz"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _put_halfword(rom: bytearray, offset: int, value: int) -> None:
    rom[offset : offset + 2] = value.to_bytes(2, "little")


def _encode_b(source: int, target: int) -> int:
    displacement = target - (source + 4)
    if displacement % 2:
        raise ValueError("B target must be halfword aligned")
    immediate = displacement // 2
    if not -(1 << 10) <= immediate < (1 << 10):
        raise ValueError("B target does not fit")
    return 0xE000 | (immediate & 0x7FF)


def _encode_bcond(source: int, target: int, condition: int = 0) -> int:
    displacement = target - (source + 4)
    if displacement % 2:
        raise ValueError("conditional B target must be halfword aligned")
    immediate = displacement // 2
    if not -(1 << 7) <= immediate < (1 << 7):
        raise ValueError("conditional B target does not fit")
    return 0xD000 | ((condition & 0xF) << 8) | (immediate & 0xFF)


def _encode_bl(source: int, target: int) -> tuple[int, int]:
    displacement = target - (source + 4)
    if displacement % 2 or not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("BL target does not fit")
    encoded = displacement & 0x7FFFFF
    first = 0xF000 | ((encoded >> 12) & 0x7FF)
    second = 0xF800 | ((encoded >> 1) & 0x7FF)
    return first, second


class ProducerTests(unittest.TestCase):
    def test_scan_producers_decodes_signed_b_bcond_and_last_halfword(self) -> None:
        rom = bytearray(10)
        _put_halfword(rom, 0, _encode_b(0, 4))
        _put_halfword(rom, 2, _encode_bcond(2, 6))
        _put_halfword(rom, 8, _encode_b(8, 8))
        rows = producer.scan_producers(bytes(rom), [4, 6, 8])
        self.assertEqual(rows, [
            {"kind": "thumb_b", "source": 0, "target": 4, "raw_hex": "00e0", "size": 2},
            {"kind": "thumb_bcond", "source": 2, "target": 6, "raw_hex": "00d0", "size": 2},
            {"kind": "thumb_b", "source": 8, "target": 8, "raw_hex": "fee7", "size": 2},
        ])

    def test_scan_producers_decodes_signed_bl_in_both_directions(self) -> None:
        rom = bytearray(12)
        first, second = _encode_bl(0, 8)
        _put_halfword(rom, 0, first)
        _put_halfword(rom, 2, second)
        first, second = _encode_bl(4, 0)
        _put_halfword(rom, 4, first)
        _put_halfword(rom, 6, second)
        rows = producer.scan_producers(bytes(rom), [0, 8])
        self.assertEqual([(row["source"], row["target"], row["raw_hex"]) for row in rows], [
            (4, 0, rom[4:8].hex()),
            (0, 8, rom[0:4].hex()),
        ])
        self.assertTrue(all(row["kind"] == "thumb_bl" and row["size"] == 4 for row in rows))

    def test_relocated_closure_is_not_address_hardcoded(self) -> None:
        rom = bytearray(32)
        first, second = _encode_bl(0, 20)
        _put_halfword(rom, 0, first)
        _put_halfword(rom, 2, second)
        _put_halfword(rom, 4, 0x4800)  # PC + 4 = 8, literal at 8.
        _put_halfword(rom, 6, 0x4700)
        rom[8:12] = b"ABCD"
        _put_halfword(rom, 16, 0x4778)  # BX r15 is rejected as a high PC transfer.
        closure = producer.derive_closure(bytes(rom), [0], [[0, 8]], [[8, 12]], [20], [])
        self.assertEqual(closure["code_ranges"], [[0, 8]])
        self.assertEqual(closure["literal_bindings"], [[4, 8, "41424344"]])
        self.assertEqual(closure["frontiers"], [{"reason": "indirect_pc_target", "register": 0, "source": 6}])

    def test_branch_into_middle_literal_hole_or_outside_fails_closed(self) -> None:
        rom = bytearray(24)
        _put_halfword(rom, 0, _encode_b(0, 8))
        rom[8:12] = b"ABCD"
        with self.assertRaises(ValueError):
            producer.derive_closure(bytes(rom), [0], [[0, 2]], [[8, 12]], [], [[2, 8]])

        rom = bytearray(12)
        first, second = _encode_bl(0, 2)
        _put_halfword(rom, 0, first)
        _put_halfword(rom, 2, second)
        with self.assertRaises(ValueError):
            producer.derive_closure(bytes(rom), [0], [[0, 4]], [[8, 12]], [], [[4, 8]])

        rom = bytearray(16)
        _put_halfword(rom, 0, _encode_b(0, 16))
        with self.assertRaises(ValueError):
            producer.derive_closure(bytes(rom), [0], [[0, 2]], [[8, 12]], [], [[2, 8]])

    def test_missing_literal_word_and_unsupported_pc_writes_fail_closed(self) -> None:
        rom = bytearray(20)
        _put_halfword(rom, 4, 0x4800)
        _put_halfword(rom, 6, 0x4700)
        rom[8:12] = b"ABCD"
        rom[12:16] = b"EFGH"
        with self.assertRaises(ValueError):
            producer.derive_closure(bytes(rom), [0], [[0, 8]], [[8, 16]], [], [])

        for halfword in (0x4687, 0xDF00):
            with self.subTest(halfword=hex(halfword)):
                fixture = bytearray(12)
                _put_halfword(fixture, 0, halfword)
                _put_halfword(fixture, 2, 0x4800)
                _put_halfword(fixture, 4, 0x4700)
                fixture[8:12] = b"ABCD"
                with self.assertRaises(ValueError):
                    producer.derive_closure(bytes(fixture), [0], [[0, 6]], [[8, 12]], [], [])

    def test_real_derived_closure_matches_frozen_contract(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        rom = ROM_PATH.read_bytes()
        closure = producer.derive_closure(
            rom,
            contract["roots"],
            contract["code_ranges"],
            contract["literal_ranges"],
            contract["opaque_entries"],
            contract["holes"],
        )
        self.assertEqual(closure["nodes"], contract["expected_nodes"])
        self.assertEqual(closure["blocks"], contract["expected_blocks"])
        self.assertEqual(closure["frontiers"], contract["expected_frontiers"])
        self.assertEqual(closure["literal_bindings"], contract["expected_literal_bindings"])
        self.assertEqual(closure["summary"], {
            "basic_block_count": 5,
            "claim_count": 5,
            "code_bytes": 46,
            "frontier_count": 3,
            "instruction_count": 21,
            "literal_bytes": 8,
            "opaque_call_count": 2,
            "producer_count": 15,
            "promotion_bytes": 54,
            "root_count": 3,
            "structured_return_count": 0,
        })

    def test_real_build_payload_has_exact_top_level_and_provenance(self) -> None:
        contract_raw = CONTRACT_PATH.read_bytes()
        contract = json.loads(contract_raw)
        rom = ROM_PATH.read_bytes()
        baseline_raw = gzip.open(BASELINE_PATH, "rb").read()
        payload = producer.build_payload(rom, baseline_raw, contract_raw)
        self.assertEqual(list(payload), [
            "schema", "rom", "upstream_inputs", "baseline", "roots", "producers",
            "root_pointer_occurrences", "closure", "promotion", "scope",
        ])
        self.assertEqual(payload["schema"], contract["output_schema"])
        self.assertEqual(payload["closure"]["summary"], contract["expected_summary"])
        self.assertEqual(payload["producers"], contract["expected_producers"])
        self.assertEqual(payload["root_pointer_occurrences"], contract["root_pointer_occurrences"])
        self.assertEqual(payload["promotion"]["claim_count"], 5)
        self.assertEqual(payload["promotion"]["promotion_bytes"], 54)
        self.assertEqual(len(payload["promotion"]["claims"]), 5)
        for claim in payload["promotion"]["claims"]:
            self.assertEqual(set(claim), {"id", "kind", "range", "bytes_sha256", "baseline_owners"})
            self.assertTrue(claim["baseline_owners"])
            for segment in claim["baseline_owners"]:
                self.assertEqual(segment["primary_class"], "unknown")
                self.assertEqual(segment["primary_claim_ids"], [])
                self.assertEqual(segment["secondary_claim_ids"], [])

    def test_contract_rom_and_baseline_identity_mismatch_fails_before_parse(self) -> None:
        contract = CONTRACT_PATH.read_bytes()
        rom = ROM_PATH.read_bytes()
        baseline = gzip.open(BASELINE_PATH, "rb").read()
        with self.assertRaises(ValueError):
            producer.build_payload(rom, baseline, contract + b"\n")
        changed_rom = bytearray(rom)
        changed_rom[-1] ^= 1
        with self.assertRaises(ValueError):
            producer.build_payload(bytes(changed_rom), baseline, contract)
        with self.assertRaises(ValueError):
            producer.build_payload(rom, baseline + b"\n", contract)


if __name__ == "__main__":
    unittest.main()
