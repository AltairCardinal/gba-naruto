#!/usr/bin/env python3
"""TDD RED contract for the frozen PSG/noise frequency lookup packet.

The implementation is intentionally absent during this phase.  These tests are
the public contract for the later exporter: all promoted bytes are rebuilt from
the raw ROM, while the initializer and SoundInfo paths remain provenance-only.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
COVERAGE = ROOT / "sequel/rom-byte-coverage.json"

SCHEMA = "rom-psg-frequency-lookup-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6"
COVERAGE_TOTALS = {
    "classified_bytes": 6_121_624,
    "unknown_bytes": 169_832,
    "claim_count": 14_471,
    "segment_count": 16_582,
}

ROM_BASE = 0x08000000
PROMOTION_RANGES = [
    [0x09B494, 0x09B4C6],
    [0x09B4C8, 0x09B4CC],
    [0x09B4CC, 0x09B534],
    [0x09B534, 0x09B53C],
    [0x46475C, 0x464798],
]
PROMOTION_RANGE_SHA256 = [
    "969892b0f481afc4872493396ed034c0a696cd3c56ca07d4c0b5d68369e7365d",
    "73cbc760a9346eacd3a16553ac98763cb1a6ee27dbf7d5fa1bfafdb4ce74d9b5",
    "3c3471021d4b57c4d7708443ae8bd180d3b9919dbc049c7e10a41fecd3038e60",
    "89bce1ab76458db38f3a7d995c13f06abad02b6ab3ab8ba9ed7ecc53f913a6c0",
    "197f0679262884d48dd459dcfe690c0a41e8a73cf76cb62838119fc9cb0e7ab6",
]
PROMOTION_RANGE_VECTOR_SHA256 = (
    "5247ee79350c15d6292e52a5e1ef58bd7b7555f50a70bc157e3e936b8ffa0080"
)
PACKED_SHA256 = "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b"

TARGET_CONSUMER_CODE_RANGES = [
    [0x09B494, 0x09B4C6],
    [0x09B4CC, 0x09B534],
]
TARGET_CONSUMER_BLOCK_RANGES = [
    [0x09B494, 0x09B4A8],
    [0x09B4A8, 0x09B4AC],
    [0x09B4AC, 0x09B4B0],
    [0x09B4B0, 0x09B4BC],
    [0x09B4BC, 0x09B4BE],
    [0x09B4BE, 0x09B4C6],
    [0x09B4CC, 0x09B4D0],
    [0x09B4D0, 0x09B4D8],
    [0x09B4D8, 0x09B4E4],
    [0x09B4E4, 0x09B4EA],
    [0x09B4EA, 0x09B52E],
    [0x09B52E, 0x09B534],
]
TARGET_CONSUMER_CODE_SHA256 = (
    "91ac0a7fed3e5840bf3e76dfa8484aa70ad3ec71957b35283e878444163ed9ca"
)
UNKNOWN_GAP = [0x09B4C6, 0x09B4C8]

INITIALIZER_CODE_RANGE = [0x09ACF8, 0x09ADC0]
INITIALIZER_CODE_SHA256 = (
    "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a"
)
INITIALIZER_LITERAL_POOL_RANGE = [0x09ADC0, 0x09AE10]
INITIALIZER_LITERAL_POOL_SHA256 = (
    "5b0dd3fbbfc9f8c964f9c0f806548ccd9b72059ee6b67188c9432ac2342652b0"
)
INITIALIZER_BINDING_PAIR_RANGE = [0x09AD74, 0x09AD78]
INITIALIZER_BINDING_PAIR_SHA256 = (
    "45aee5a509e95eb1b4a273000f5f4d922f220ea3d36ff6131dbd021a351444fd"
)
INITIALIZER_PRODUCER = {
    "file_offset": 0x09AA56,
    "raw_hex": "00f04ff9",
    "bytes_sha256": (
        "3cb3a41522f6b753006d687eb512c8d607f7d4f09ea4864b2250713f1a94f71a"
    ),
    "target_file_offset": 0x09ACF8,
}

SOUNDINFO_CONTEXT_RANGE = [0x09A708, 0x09A8FE]
SOUNDINFO_CONTEXT_SHA256 = (
    "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e"
)
SOUNDINFO_CHAIN_RANGE = [0x09A8C6, 0x09A8D4]
SOUNDINFO_CHAIN_SHA256 = (
    "f683daef4ff9b013ba8ca92dd7de9727094514bcc126ceadcf7e0a8e0df59734"
)
TRAMPOLINE_RANGE = [0x09A684, 0x09A686]
TRAMPOLINE_SHA256 = (
    "477db9ac7ca5efc12e37f882656b8fe5a363ffeb99b2e565a953d10c3c91ab21"
)

DIRECT_TRAMPOLINE_BRANCHES = [
    {"file_offset": 0x09A444, "raw_hex": "00f01ef9", "mnemonic": "bl"},
    {"file_offset": 0x09A50E, "raw_hex": "00f0b9f8", "mnemonic": "bl"},
    {"file_offset": 0x09A52A, "raw_hex": "00f0abf8", "mnemonic": "bl"},
    {"file_offset": 0x09A63E, "raw_hex": "00f021f8", "mnemonic": "bl"},
    {"file_offset": 0x09A6BC, "raw_hex": "fff7e2ff", "mnemonic": "bl"},
    {"file_offset": 0x09A8D0, "raw_hex": "fff7d8fe", "mnemonic": "bl"},
]

CONSUMED_LITERAL_BINDINGS = [
    {
        "load_file_offset": 0x09B4BE,
        "load_raw_hex": "0248",
        "literal_range": [0x09B4C8, 0x09B4CC],
        "pointer": 0x0846475C,
        "target_file_offset": 0x46475C,
        "target_promoted": True,
        "target_semantics_claimed": True,
        "pointer_occurrences": [0x09B4C8],
    },
    {
        "load_file_offset": 0x09B4EA,
        "load_raw_hex": "124b",
        "literal_range": [0x09B534, 0x09B538],
        "pointer": 0x084646C0,
        "target_file_offset": 0x4646C0,
        "target_promoted": False,
        "target_semantics_claimed": False,
        "pointer_occurrences": [0x09B534],
    },
    {
        "load_file_offset": 0x09B4F0,
        "load_raw_hex": "114c",
        "literal_range": [0x09B538, 0x09B53C],
        "pointer": 0x08464744,
        "target_file_offset": 0x464744,
        "target_promoted": False,
        "target_semantics_claimed": False,
        "pointer_occurrences": [0x09B538],
    },
]

SEMANTIC_RANGE_SPECS = [
    {
        "id": "psg-frequency-code-a-09b494",
        "kind": "psg_frequency_consumer_thumb_code",
        "range": PROMOTION_RANGES[0],
        "sha256": PROMOTION_RANGE_SHA256[0],
        "semantic_class": "armv4t_psg_frequency_lookup_thumb_code",
        "claim_kind": "psg_frequency_lookup_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "psg-frequency-noise-literal-09b4c8",
        "kind": "psg_frequency_consumed_pointer_literal",
        "range": PROMOTION_RANGES[1],
        "sha256": PROMOTION_RANGE_SHA256[1],
        "semantic_class": "psg_frequency_lookup_consumed_pointer_literals",
        "claim_kind": "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "mode": None,
    },
    {
        "id": "psg-frequency-code-b-09b4cc",
        "kind": "psg_frequency_consumer_thumb_code",
        "range": PROMOTION_RANGES[2],
        "sha256": PROMOTION_RANGE_SHA256[2],
        "semantic_class": "armv4t_psg_frequency_lookup_thumb_code",
        "claim_kind": "psg_frequency_lookup_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "psg-frequency-nonnoise-literals-09b534",
        "kind": "psg_frequency_consumed_pointer_literal",
        "range": PROMOTION_RANGES[3],
        "sha256": PROMOTION_RANGE_SHA256[3],
        "semantic_class": "psg_frequency_lookup_consumed_pointer_literals",
        "claim_kind": "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "mode": None,
    },
    {
        "id": "psg-noise-register-table-46475c",
        "kind": "psg_noise_register_descriptor_table",
        "range": PROMOTION_RANGES[4],
        "sha256": PROMOTION_RANGE_SHA256[4],
        "semantic_class": "psg_noise_register_descriptor_table",
        "claim_kind": "psg_noise_register_descriptor_bytes",
        "mode": None,
    },
]
SEMANTIC_RANGE_VECTOR_SHA256 = (
    "6683ef2206af27246bc97abb750a02023ea18909611b7dbda9e1987419e515eb"
)

SCOPE_FALSE_KEYS = (
    "producer_source_instruction_membership_complete",
    "producer_bytes_promoted",
    "global_ram_or_computed_producer_denominator_complete",
    "global_writer_denominator_complete",
    "global_indirect_caller_denominator_complete",
    "global_caller_denominator_complete",
    "natural_runtime_reachability_complete",
    "non_noise_target_table_semantics_complete",
    "playback_behavior_proven",
    "editing_relocation_writeback_safe",
    "allocatable_free_space_proven",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_exporter():
    """Load lazily so the RED is an explicit missing-implementation failure."""
    try:
        return importlib.import_module("tools.export_rom_psg_frequency_lookup")
    except ModuleNotFoundError:
        return None


class PsgFrequencyLookupExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _load_exporter()

    def _implemented(self):
        self.assertIsNotNone(
            self.exporter,
            "PSG frequency lookup exporter implementation is absent",
        )
        return self.exporter

    def test_build_payload_freezes_five_ranges_and_packed_bytes(self) -> None:
        exporter = self._implemented()
        payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["rom"], {
            "path": "rom/base.gba",
            "size": 0x600000,
            "sha256": ROM_SHA256,
        })
        promotion = payload["promotion"]
        self.assertEqual(promotion["ranges"], PROMOTION_RANGES)
        self.assertEqual(promotion["range_count"], 5)
        self.assertEqual(promotion["byte_count"], 226)
        self.assertEqual(
            promotion["range_vector_sha256"], PROMOTION_RANGE_VECTOR_SHA256
        )
        self.assertEqual(promotion["packed_bytes_sha256"], PACKED_SHA256)
        self.assertEqual(len(bundle), 226)
        self.assertEqual(_sha(bundle), PACKED_SHA256)
        self.assertEqual(
            bundle,
            b"".join(self.rom[start:end] for start, end in PROMOTION_RANGES),
        )
        self.assertEqual(promotion["semantic_ranges"], SEMANTIC_RANGE_SPECS)
        self.assertEqual(
            promotion["semantic_range_vector_sha256"],
            SEMANTIC_RANGE_VECTOR_SHA256,
        )

    def test_range_and_semantic_vector_receipts_are_recomputed(self) -> None:
        exporter = self._implemented()
        for constant in (
            "PROMOTION_RANGE_VECTOR_SHA256",
            "SEMANTIC_RANGE_VECTOR_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                exporter, constant, "0" * 64
            ):
                with self.assertRaisesRegex(ValueError, "vector|receipt|identity"):
                    exporter.build_payload(ROOT)

    def test_current_coverage_baseline_keeps_every_promotion_byte_unknown(self) -> None:
        exporter = self._implemented()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        expected = {
            "path": "sequel/rom-byte-coverage.json",
            "schema": "rom-byte-coverage-v1",
            "sha256": COVERAGE_SHA256,
            **COVERAGE_TOTALS,
            "promotion_bytes": 226,
            "unknown_promotion_bytes": 226,
            "primary_overlap_bytes": 0,
            "all_promotion_bytes_unknown": True,
        }
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["coverage_baseline"], expected)
        self.assertEqual(exporter.analyze_coverage_baseline(coverage), expected)

        tampered = copy.deepcopy(coverage)
        for segment in tampered["segments"]:
            if segment["range"] == UNKNOWN_GAP:
                continue
            start, end = segment["range"]
            if start <= PROMOTION_RANGES[0][0] and PROMOTION_RANGES[0][1] <= end:
                segment["primary_class"] = "synthetic-overlap"
                segment["primary_claim_ids"] = ["synthetic-overlap"]
                break
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            exporter.analyze_coverage_baseline(tampered)

    def test_target_branch_and_pointer_denominators_are_exact_provenance(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        denominator = payload["producer_denominator"]
        self.assertEqual(denominator["scan"]["mode"], "thumb")
        self.assertEqual(denominator["scan"]["alignment_bytes"], 2)
        self.assertEqual(denominator["scan"]["range"], [0, 0x600000])
        self.assertEqual(denominator["scan"]["target_file_offset"], 0x09B494)
        self.assertEqual(denominator["scan"]["matching_producer_count"], 0)
        self.assertEqual(denominator["producers"], [])
        self.assertEqual(denominator["thumb_pointer_target"], 0x0809B495)
        self.assertEqual(denominator["thumb_pointer_occurrences"], [0x09AE04])
        self.assertFalse(denominator["producer_source_instruction_membership_proven"])
        self.assertFalse(denominator["producer_bytes_promoted"])

        initializer = payload["provenance"]["initializer"]
        self.assertEqual(initializer["producer"], INITIALIZER_PRODUCER)
        self.assertEqual(initializer["code_range"], INITIALIZER_CODE_RANGE)
        self.assertEqual(initializer["code_sha256"], INITIALIZER_CODE_SHA256)
        self.assertEqual(initializer["decoded_instruction_count"], 99)
        self.assertEqual(initializer["decoded_basic_block_count"], 4)
        self.assertEqual(
            initializer["block_ranges"],
            [
                [0x09ACF8, 0x09AD3A],
                [0x09AD3A, 0x09AD8A],
                [0x09AD8A, 0x09ADB8],
                [0x09ADB8, 0x09ADC0],
            ],
        )
        self.assertEqual(
            initializer["external_call_edges"],
            [{"source_file_offset": 0x09AD86, "target_file_offset": 0x09C0E0}],
        )
        self.assertEqual(initializer["frontier_count"], 0)
        self.assertTrue(initializer["cfg_closed"])
        self.assertTrue(initializer["return_closed"])
        self.assertEqual(initializer["pc_relative_literal_count"], 20)
        self.assertEqual(
            initializer["literal_pool_range"], INITIALIZER_LITERAL_POOL_RANGE
        )
        self.assertEqual(
            initializer["literal_pool_sha256"], INITIALIZER_LITERAL_POOL_SHA256
        )
        self.assertEqual(initializer["binding"], {
            "ldr_file_offset": 0x09AD74,
            "ldr_raw_hex": "2348",
            "literal_file_offset": 0x09AE04,
            "pointer": 0x0809B495,
            "str_file_offset": 0x09AD76,
            "str_raw_hex": "2063",
            "store": "str r0,[r4,#0x30]",
            "pair_range": INITIALIZER_BINDING_PAIR_RANGE,
            "pair_sha256": INITIALIZER_BINDING_PAIR_SHA256,
        })

    def test_soundinfo_slot_chain_and_trampoline_denominator_are_bound(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        slot = payload["provenance"]["soundinfo_slot"]
        self.assertEqual(slot["context_range"], SOUNDINFO_CONTEXT_RANGE)
        self.assertEqual(slot["context_sha256"], SOUNDINFO_CONTEXT_SHA256)
        self.assertEqual(slot["literal_load"], {
            "file_offset": 0x09A71A,
            "raw_hex": "7949",
            "literal_file_offset": 0x09A900,
            "literal_value": 0x03007FF0,
        })
        self.assertEqual(slot["dereference"], {
            "file_offset": 0x09A71C,
            "raw_hex": "0968",
            "operation": "ldr r1,[r1]",
        })
        self.assertEqual(slot["stack_store"], {
            "file_offset": 0x09A71E,
            "raw_hex": "0191",
            "operation": "str r1,[sp,#4]",
        })
        self.assertEqual(slot["stack_cell_liveness"], {
            "cell": "[sp,#4]",
            "overwritten_before_reload": False,
            "sp_adjustment_until_reload": 0,
            "reload_file_offset": 0x09A8CC,
            "reload_raw_hex": "019b",
        })
        self.assertEqual(slot["load_and_call"], {
            "load_file_offset": 0x09A8CE,
            "load_raw_hex": "1b6b",
            "field_offset": 0x30,
            "call_file_offset": 0x09A8D0,
            "call_raw_hex": "fff7d8fe",
            "trampoline_file_offset": 0x09A684,
        })
        self.assertEqual(slot["chain_range"], SOUNDINFO_CHAIN_RANGE)
        self.assertEqual(slot["chain_sha256"], SOUNDINFO_CHAIN_SHA256)
        self.assertEqual(slot["direct_trampoline_branch_denominator"], [
            {
                **row,
                "target_file_offset": 0x09A684,
            }
            for row in DIRECT_TRAMPOLINE_BRANCHES
        ])
        self.assertEqual(slot["accepted_slot_path_callsites"], [0x09A8D0])
        self.assertEqual(slot["trampoline"], {
            "range": TRAMPOLINE_RANGE,
            "sha256": TRAMPOLINE_SHA256,
            "raw_hex": "1847",
            "operation": "bx r3",
            "existing_owner": {
                "id": "cfg-thumb-0752-09a684",
                "primary_class": "armv4t_cfg_reachable_thumb_code",
                "range": TRAMPOLINE_RANGE,
            },
            "promoted": False,
        })

    def test_target_consumer_cfg_is_closed_but_gap_remains_unknown(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        consumer = payload["consumer"]
        self.assertEqual(consumer["root_file_offset"], 0x09B494)
        self.assertEqual(consumer["code_bytes"], 154)
        self.assertEqual(consumer["code_sha256"], TARGET_CONSUMER_CODE_SHA256)
        self.assertEqual(consumer["decoded_instruction_count"], 77)
        self.assertEqual(consumer["decoded_basic_block_count"], 12)
        self.assertEqual(consumer["code_ranges"], TARGET_CONSUMER_CODE_RANGES)
        self.assertEqual(consumer["block_ranges"], TARGET_CONSUMER_BLOCK_RANGES)
        self.assertEqual(consumer["internal_edge_count"], 16)
        self.assertEqual(consumer["external_call_edges"], [])
        self.assertEqual(consumer["frontier_count"], 0)
        self.assertEqual(consumer["structured_return_count"], 1)
        self.assertEqual(consumer["return_proof"], {
            "epilogue_range": [0x09B52E, 0x09B534],
            "epilogue_raw_hex": "f0bc02bc0847",
            "saved_lr_at_entry": True,
            "stack_adjustment_between_entry_and_epilogue": 0,
            "restored_lr_register": "r1",
            "return_instruction": "bx r1",
        })
        self.assertEqual(consumer["unclassified_unknown_ranges"], [UNKNOWN_GAP])
        promoted = {
            offset
            for start, end in PROMOTION_RANGES
            for offset in range(start, end)
        }
        self.assertTrue(
            all(offset not in promoted for offset in range(*UNKNOWN_GAP)),
            "the two-byte gap must not be promoted as padding",
        )

    def test_three_consumed_literals_and_nonnoise_targets_stay_narrow(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        literals = payload["literal_bindings"]
        self.assertEqual(literals, CONSUMED_LITERAL_BINDINGS)
        self.assertEqual(
            [row["literal_range"] for row in literals],
            [
                [0x09B4C8, 0x09B4CC],
                [0x09B534, 0x09B538],
                [0x09B538, 0x09B53C],
            ],
        )
        promoted = {tuple(row) for row in payload["promotion"]["ranges"]}
        self.assertNotIn((0x4646C0, 0x4646C4), promoted)
        self.assertNotIn((0x464744, 0x464748), promoted)
        for row in literals[1:]:
            self.assertFalse(row["target_promoted"])
            self.assertFalse(row["target_semantics_claimed"])

    def test_u8_type_key_formula_is_exhaustive_and_table_is_unique(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        table = payload["table"]
        self.assertEqual(table["range"], [0x46475C, 0x464798])
        self.assertEqual(table["entry_count"], 60)
        self.assertEqual(table["unique_entry_count"], 60)
        self.assertEqual(table["values_u8"], list(self.rom[0x46475C:0x464798]))
        self.assertEqual(table["sha256"], PROMOTION_RANGE_SHA256[4])

        lookup = payload["lookup"]
        self.assertEqual(lookup["type_input_width"], "u8")
        self.assertEqual(lookup["key_input_width"], "u8")
        self.assertEqual(lookup["type_selector"], 4)
        self.assertEqual(
            lookup["index_formula"],
            "0 if key<=20 else min(u8(key-21),59)",
        )
        self.assertTrue(lookup["type_input_truncated_before_dispatch"])
        self.assertTrue(lookup["key_input_truncated_before_index"])
        self.assertEqual(lookup["enumerated_type_domain"], [0, 255])
        self.assertEqual(lookup["enumerated_key_domain"], [0, 255])
        self.assertEqual(lookup["reachable_index_domain"], [0, 59])
        self.assertEqual(lookup["reachable_index_count"], 60)
        self.assertTrue(lookup["every_table_entry_reachable"])
        self.assertEqual(
            lookup["edge_indices"],
            {"20": 0, "21": 0, "22": 1, "79": 58, "80": 59, "255": 59},
        )

    def test_scope_keeps_global_runtime_and_editing_claims_false(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        scope = payload["scope"]
        self.assertTrue(scope["target_limited_raw_branch_denominator_complete"])
        self.assertTrue(scope["initializer_entry_proof_complete"])
        self.assertTrue(scope["target_consumer_cfg_closed"])
        self.assertTrue(scope["lookup_domain_complete_for_all_u8_inputs"])
        for key in SCOPE_FALSE_KEYS:
            self.assertFalse(scope[key], key)
        self.assertNotIn("padding_intent_proven", scope)
        self.assertNotIn("global_unreachable_proven", scope)

    def test_repository_local_candidate_output_is_allowed(self) -> None:
        exporter = self._implemented()
        active = ROOT / "build/experiments/active"
        with tempfile.TemporaryDirectory(dir=active) as temporary:
            output = Path(temporary) / "candidate"
            exporter.write_artifact(ROOT, output)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"manifest.json", "rom-psg-frequency-lookup.json", "rom-psg-frequency-lookup.bin"},
            )
            payload = json.loads(
                (output / "rom-psg-frequency-lookup.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload, exporter.build_payload(ROOT)[0])

    def test_foreign_or_symlink_output_is_rejected_without_overwrite(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            foreign = root / "foreign"
            foreign.mkdir()
            sentinel = foreign / "keep.txt"
            sentinel.write_text("foreign\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign|schema|non-empty"):
                exporter.write_artifact(ROOT, foreign)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "foreign\n")

            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.write_artifact(ROOT, linked / "candidate")
            self.assertEqual(list(real.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
