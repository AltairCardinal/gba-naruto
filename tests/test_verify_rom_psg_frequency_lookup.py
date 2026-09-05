#!/usr/bin/env python3
"""TDD RED contract for the independent PSG/noise lookup verifier."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
COVERAGE = ROOT / "sequel/rom-byte-coverage.json"
VERIFIER_PATH = ROOT / "tools/verify_rom_psg_frequency_lookup.py"

SCHEMA = "rom-psg-frequency-lookup-v1"
VERIFY_SCHEMA = "rom-psg-frequency-lookup-verification-v1"
PAYLOAD_NAME = "rom-psg-frequency-lookup.json"
BUNDLE_NAME = "rom-psg-frequency-lookup.bin"
MANIFEST_NAME = "manifest.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6"

PROMOTION_RANGES = [
    [0x09B494, 0x09B4C6],
    [0x09B4C8, 0x09B4CC],
    [0x09B4CC, 0x09B534],
    [0x09B534, 0x09B53C],
    [0x46475C, 0x464798],
]
PROMOTION_RANGE_VECTOR_SHA256 = (
    "5247ee79350c15d6292e52a5e1ef58bd7b7555f50a70bc157e3e936b8ffa0080"
)
PACKED_SHA256 = "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b"
SEMANTIC_RANGE_VECTOR_SHA256 = (
    "6683ef2206af27246bc97abb750a02023ea18909611b7dbda9e1987419e515eb"
)
POST_SEGMENTS_SHA256 = (
    "7912231dc77663aefe52df6d99beeffafba082bb1ddba081a047c6d5187dc8dd"
)

EXPECTED_CLAIM_IDENTITIES = [
    {
        "id": "psg-frequency-code-a-09b494",
        "range": PROMOTION_RANGES[0],
        "primary_class": "armv4t_psg_frequency_lookup_thumb_code",
        "claim_kind": "psg_frequency_lookup_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "psg-frequency-noise-literal-09b4c8",
        "range": PROMOTION_RANGES[1],
        "primary_class": "psg_frequency_lookup_consumed_pointer_literals",
        "claim_kind": "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "mode": None,
    },
    {
        "id": "psg-frequency-code-b-09b4cc",
        "range": PROMOTION_RANGES[2],
        "primary_class": "armv4t_psg_frequency_lookup_thumb_code",
        "claim_kind": "psg_frequency_lookup_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "psg-frequency-nonnoise-literals-09b534",
        "range": PROMOTION_RANGES[3],
        "primary_class": "psg_frequency_lookup_consumed_pointer_literals",
        "claim_kind": "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "mode": None,
    },
    {
        "id": "psg-noise-register-table-46475c",
        "range": PROMOTION_RANGES[4],
        "primary_class": "psg_noise_register_descriptor_table",
        "claim_kind": "psg_noise_register_descriptor_bytes",
        "mode": None,
    },
]
CLAIM_IDENTITY_FIELDS = ("id", "range", "primary_class", "claim_kind", "mode")

PSG_COVERAGE_LIMITATION = (
    "The PSG frequency lookup artifact classifies exactly 226 frozen bytes: "
    "154 bytes in two bounded Thumb code ranges, twelve bytes in three consumed "
    "pointer literals, and a 60-byte channel-4 noise register descriptor table. "
    "The two-byte 0x09B4C6..0x09B4C8 alignment gap remains unknown. Entry proof "
    "is limited to one fixed initializer-to-logical-SoundInfo+0x30-to-BX-r3 "
    "chain; global RAM/computed producers, writers, indirect callers, natural "
    "runtime reachability, the two non-noise target-table semantics, playback, "
    "editing, writeback, relocation, and allocatable space remain unclaimed."
)

DIRECT_TRAMPOLINE_BRANCHES = [
    {"file_offset": 0x09A444, "raw_hex": "00f01ef9", "mnemonic": "bl"},
    {"file_offset": 0x09A50E, "raw_hex": "00f0b9f8", "mnemonic": "bl"},
    {"file_offset": 0x09A52A, "raw_hex": "00f0abf8", "mnemonic": "bl"},
    {"file_offset": 0x09A63E, "raw_hex": "00f021f8", "mnemonic": "bl"},
    {"file_offset": 0x09A6BC, "raw_hex": "fff7e2ff", "mnemonic": "bl"},
    {"file_offset": 0x09A8D0, "raw_hex": "fff7d8fe", "mnemonic": "bl"},
]

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


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _encode_thumb_bl(callsite: int, target: int) -> bytes:
    displacement = target - (callsite + 4)
    if displacement & 1 or not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("synthetic Thumb-1 BL target is out of range")
    encoded = displacement & 0x7FFFFF
    first = 0xF000 | ((encoded >> 12) & 0x07FF)
    second = 0xF800 | ((encoded >> 1) & 0x07FF)
    return first.to_bytes(2, "little") + second.to_bytes(2, "little")


def _load_modules():
    """Load lazily so RED reports missing exporter/verifier APIs explicitly."""
    try:
        exporter = importlib.import_module("tools.export_rom_psg_frequency_lookup")
        verifier = importlib.import_module("tools.verify_rom_psg_frequency_lookup")
    except ModuleNotFoundError:
        return None, None
    return exporter, verifier


def _project_post_coverage(coverage: dict, expected_claims: list[dict]) -> dict:
    """Project only the five exact claims; derive, never guess, segment count."""
    projected = copy.deepcopy(coverage)
    projected["claims"].extend(copy.deepcopy(expected_claims))
    projected["claims"].sort(key=lambda claim: (claim["range"], claim["id"]))
    endpoints = sorted({value for claim in expected_claims for value in claim["range"]})
    segments = []
    for segment in coverage["segments"]:
        start, end = segment["range"]
        cuts = [start, *(value for value in endpoints if start < value < end), end]
        for left, right in zip(cuts, cuts[1:]):
            owner = next(
                (
                    claim
                    for claim in expected_claims
                    if claim["range"][0] <= left and right <= claim["range"][1]
                ),
                None,
            )
            replacement = copy.deepcopy(segment)
            replacement["range"] = [left, right]
            if owner is not None:
                replacement["primary_class"] = owner["primary_class"]
                replacement["primary_claim_ids"] = [owner["id"]]
                replacement.pop("unknown_reason", None)
            segments.append(replacement)
    projected["segments"] = segments
    projected["summary"]["classified_bytes"] += 226
    projected["summary"]["unknown_bytes"] -= 226
    projected["summary"]["claim_count"] += 5
    projected["summary"]["segment_count"] = len(segments)
    projected["summary"].update(
        {
            "psg_frequency_lookup_promotion_batch": SCHEMA,
            "psg_frequency_lookup_bytes": 226,
            "psg_frequency_lookup_claim_count": 5,
            "psg_frequency_lookup_range_vector_sha256": (
                PROMOTION_RANGE_VECTOR_SHA256
            ),
            "psg_frequency_lookup_packed_bytes_sha256": PACKED_SHA256,
            "psg_frequency_lookup_semantic_range_vector_sha256": (
                SEMANTIC_RANGE_VECTOR_SHA256
            ),
            "psg_frequency_lookup_class_bytes": {
                "armv4t_psg_frequency_lookup_thumb_code": 154,
                "psg_frequency_lookup_consumed_pointer_literals": 12,
                "psg_noise_register_descriptor_table": 60,
            },
            "psg_frequency_lookup_class_claim_counts": {
                "armv4t_psg_frequency_lookup_thumb_code": 2,
                "psg_frequency_lookup_consumed_pointer_literals": 2,
                "psg_noise_register_descriptor_table": 1,
            },
            "psg_frequency_lookup_direct_branch_producer_count": 0,
            "psg_frequency_lookup_thumb_pointer_occurrence_count": 1,
            "psg_frequency_lookup_consumer_instruction_count": 77,
            "psg_frequency_lookup_consumer_block_count": 12,
            "psg_frequency_lookup_consumer_frontier_count": 0,
            "psg_frequency_lookup_noise_table_entry_count": 60,
            "psg_frequency_lookup_noise_index_domain": [0, 59],
            "psg_frequency_lookup_unclassified_gap_bytes": 2,
        }
    )
    projected["limitations"].append(PSG_COVERAGE_LIMITATION)
    return projected


class PsgFrequencyLookupVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter, cls.verifier = _load_modules()
        cls.temporary = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _implemented(self):
        self.assertIsNotNone(
            self.exporter,
            "PSG frequency lookup exporter implementation is absent",
        )
        self.assertIsNotNone(
            self.verifier,
            "independent PSG frequency lookup verifier implementation is absent",
        )
        return self.exporter, self.verifier

    def _candidate(self, name: str = "candidate") -> Path:
        exporter, _ = self._implemented()
        candidate = Path(self.temporary.name) / name
        if candidate.exists():
            shutil.rmtree(candidate)
        exporter.write_artifact(ROOT, candidate)
        return candidate

    def _copy_candidate(self, name: str) -> Path:
        source = Path(self.temporary.name) / "candidate"
        if not source.exists():
            self._candidate()
        target = Path(self.temporary.name) / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return target

    def test_independent_rebuild_matches_exporter_without_importing_it(self) -> None:
        exporter, verifier = self._implemented()
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
                imported.extend(
                    f"{node.module}.{alias.name}" for alias in node.names
                )
        self.assertFalse(
            any(name.endswith("export_rom_psg_frequency_lookup") for name in imported),
            imported,
        )
        expected_payload, expected_bundle = exporter.build_payload(ROOT)
        rebuilt_payload, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(rebuilt_payload, expected_payload)
        self.assertEqual(rebuilt_bundle, expected_bundle)

    def test_independent_raw_provenance_and_cfg_contracts_are_exact(self) -> None:
        _, verifier = self._implemented()
        producer = verifier.independent_producer_denominator(self.rom)
        self.assertEqual(producer["scan"]["target_file_offset"], 0x09B494)
        self.assertEqual(producer["scan"]["matching_producer_count"], 0)
        self.assertEqual(producer["producers"], [])
        self.assertEqual(producer["thumb_pointer_occurrences"], [0x09AE04])

        initializer = verifier.independent_initializer_provenance(self.rom)
        self.assertEqual(initializer["producer"]["file_offset"], 0x09AA56)
        self.assertEqual(initializer["producer"]["raw_hex"], "00f04ff9")
        self.assertEqual(initializer["code_range"], [0x09ACF8, 0x09ADC0])
        self.assertEqual(initializer["code_sha256"],
                         "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a")
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

        slot = verifier.independent_slot_consumer_provenance(self.rom)
        self.assertEqual(slot["context_range"], [0x09A708, 0x09A8FE])
        self.assertEqual(slot["context_sha256"],
                         "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e")
        self.assertEqual(slot["chain_range"], [0x09A8C6, 0x09A8D4])
        self.assertEqual(slot["chain_sha256"],
                         "f683daef4ff9b013ba8ca92dd7de9727094514bcc126ceadcf7e0a8e0df59734")
        self.assertEqual(slot["direct_trampoline_branch_denominator"], [
            {**row, "target_file_offset": 0x09A684}
            for row in DIRECT_TRAMPOLINE_BRANCHES
        ])
        self.assertEqual(slot["accepted_slot_path_callsites"], [0x09A8D0])

        consumer = verifier.independent_consumer_contract(self.rom)
        self.assertEqual(consumer["decoded_instruction_count"], 77)
        self.assertEqual(consumer["decoded_basic_block_count"], 12)
        self.assertEqual(
            consumer["code_ranges"],
            [[0x09B494, 0x09B4C6], [0x09B4CC, 0x09B534]],
        )
        self.assertEqual(
            consumer["block_ranges"],
            [
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
            ],
        )
        self.assertEqual(consumer["internal_edge_count"], 16)
        self.assertEqual(consumer["frontier_count"], 0)
        self.assertEqual(consumer["external_call_edges"], [])
        self.assertEqual(consumer["structured_return_count"], 1)
        self.assertEqual(consumer["unclassified_unknown_ranges"], [[0x09B4C6, 0x09B4C8]])

        literals = verifier.independent_literal_bindings(self.rom)
        self.assertEqual([row["load_file_offset"] for row in literals],
                         [0x09B4BE, 0x09B4EA, 0x09B4F0])
        self.assertEqual([row["pointer"] for row in literals],
                         [0x0846475C, 0x084646C0, 0x08464744])

    def test_semantic_mutations_fail_after_slice_hashes_are_resigned(self) -> None:
        _, verifier = self._implemented()
        for label, function in (
            ("consumer", verifier.independent_consumer_contract),
            ("initializer", verifier.independent_initializer_provenance),
            ("slot", verifier.independent_slot_consumer_provenance),
        ):
            with self.subTest(hash_parameter=label):
                with self.assertRaisesRegex(ValueError, "hash|identity"):
                    function(self.rom, expected_sha256="0" * 64)

        for offset in (
            0x09B494,
            0x09B4A6,
            0x09B4BE,
            0x09B4C4,
            0x09B4CC,
            0x09B4D6,
            0x09B52E,
        ):
            with self.subTest(offset=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                digest = _sha(
                    bytes(mutated[0x09B494:0x09B4C6])
                    + bytes(mutated[0x09B4CC:0x09B534])
                )
                with self.assertRaisesRegex(
                    ValueError, "consumer|CFG|return|semantic|literal"
                ):
                    verifier.independent_consumer_contract(
                        bytes(mutated), expected_sha256=digest
                    )

        for offset in (0x09ACF8, 0x09AD74, 0x09AD76, 0x09AD86, 0x09ADBE):
            with self.subTest(initializer_offset=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                digest = _sha(bytes(mutated[0x09ACF8:0x09ADC0]))
                with self.assertRaisesRegex(
                    ValueError, "initializer|producer|CFG|binding|return|semantic"
                ):
                    verifier.independent_initializer_provenance(
                        bytes(mutated), expected_sha256=digest
                    )

        for offset in (
            0x09A71A,
            0x09A71C,
            0x09A71E,
            0x09A8CC,
            0x09A8CE,
            0x09A8D0,
            0x09A684,
        ):
            with self.subTest(slot_offset=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                digest = _sha(bytes(mutated[0x09A708:0x09A8FE]))
                with self.assertRaisesRegex(
                    ValueError, "slot|SoundInfo|provenance|trampoline|semantic"
                ):
                    verifier.independent_slot_consumer_provenance(
                        bytes(mutated), expected_sha256=digest
                    )

        mutated = bytearray(self.rom)
        mutated[0x5FFFFC:0x600000] = (0x0809B495).to_bytes(4, "little")
        with self.assertRaisesRegex(ValueError, "pointer|denominator|occurrence"):
            verifier.independent_producer_denominator(bytes(mutated))

        mutated = bytearray(self.rom)
        negative_callsite = 0x49B000
        mutated[negative_callsite : negative_callsite + 4] = _encode_thumb_bl(
            negative_callsite, 0x09B494
        )
        with self.assertRaisesRegex(ValueError, "producer|denominator|branch"):
            verifier.independent_producer_denominator(bytes(mutated))

        mutated = bytearray(self.rom)
        newline_callsite = 0x10007C
        newline_branch = _encode_thumb_bl(newline_callsite, 0x09B494)
        self.assertEqual(newline_branch.hex(), "9bf70afa")
        mutated[newline_callsite : newline_callsite + 4] = newline_branch
        with self.assertRaisesRegex(ValueError, "producer|denominator|branch"):
            verifier.independent_producer_denominator(bytes(mutated))

        mutated = bytearray(self.rom)
        extra_trampoline_callsite = 0x09A000
        mutated[
            extra_trampoline_callsite : extra_trampoline_callsite + 4
        ] = _encode_thumb_bl(extra_trampoline_callsite, 0x09A684)
        with self.assertRaisesRegex(ValueError, "trampoline|denominator|branch"):
            verifier.independent_slot_consumer_provenance(bytes(mutated))

        mutated = bytearray(self.rom)
        newline_trampoline_callsite = 0x10006C
        newline_trampoline_branch = _encode_thumb_bl(
            newline_trampoline_callsite, 0x09A684
        )
        self.assertEqual(newline_trampoline_branch.hex(), "9af70afb")
        mutated[
            newline_trampoline_callsite : newline_trampoline_callsite + 4
        ] = newline_trampoline_branch
        with self.assertRaisesRegex(ValueError, "trampoline|denominator|branch"):
            verifier.independent_slot_consumer_provenance(bytes(mutated))

        for offset in (0x09B4C8, 0x09B534, 0x09B538):
            with self.subTest(literal_offset=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                with self.assertRaisesRegex(ValueError, "literal|pointer"):
                    verifier.independent_literal_bindings(bytes(mutated))

    def test_u8_lookup_domain_and_table_mutations_fail_closed_independently(self) -> None:
        _, verifier = self._implemented()
        table_raw = self.rom[0x46475C:0x464798]
        table = verifier.analyze_noise_table(table_raw)
        self.assertEqual(table["entry_count"], 60)
        self.assertEqual(table["unique_entry_count"], 60)
        self.assertEqual(table["reachable_index_domain"], [0, 59])
        self.assertTrue(table["every_table_entry_reachable"])
        self.assertEqual(table["edge_indices"],
                         {"20": 0, "21": 0, "22": 1, "79": 58, "80": 59, "255": 59})

        for index in (0, 59):
            mutated = bytearray(table_raw)
            mutated[index] ^= 1
            with self.assertRaisesRegex(ValueError, "noise|table|byte|unique"):
                verifier.analyze_noise_table(bytes(mutated))

        self.assertEqual(verifier.lookup_index(0x104, 20), 0)
        self.assertEqual(verifier.lookup_index(4, 0x100 + 22), 1)
        self.assertIsNone(verifier.lookup_index(0x105, 22))

    def test_coverage_baseline_overlap_is_rejected_independently(self) -> None:
        _, verifier = self._implemented()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        baseline = verifier.analyze_coverage_baseline(coverage)
        self.assertEqual(baseline["promotion_bytes"], 226)
        self.assertEqual(baseline["unknown_promotion_bytes"], 226)
        self.assertEqual(baseline["primary_overlap_bytes"], 0)

        tampered = copy.deepcopy(coverage)
        for segment in tampered["segments"]:
            start, end = segment["range"]
            if start <= 0x09B494 < end:
                segment["primary_class"] = "synthetic-overlap"
                segment["primary_claim_ids"] = ["synthetic-overlap"]
                break
        with self.assertRaisesRegex(ValueError, "unknown|overlap|coverage"):
            verifier.analyze_coverage_baseline(tampered)

    def test_verifier_recomputes_range_and_semantic_vector_receipts(self) -> None:
        _, verifier = self._implemented()
        for constant in (
            "PROMOTION_RANGE_VECTOR_SHA256",
            "SEMANTIC_RANGE_VECTOR_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                verifier, constant, "0" * 64
            ):
                with self.assertRaisesRegex(ValueError, "vector|receipt|identity"):
                    verifier.rebuild_payload(ROOT)

    def test_candidate_payload_binary_foreign_and_status_mutations_fail_closed(self) -> None:
        _, verifier = self._implemented()
        candidate = self._candidate()
        report = verifier.verify_artifact(ROOT, candidate)
        self.assertEqual(report["schema"], VERIFY_SCHEMA)
        self.assertTrue(report["verified"])
        self.assertEqual(report["artifact_schema"], SCHEMA)
        self.assertEqual(report["artifact_status"], "candidate")
        self.assertEqual(report["promotion_bytes"], 226)
        self.assertEqual(report["promotion_claim_count"], 5)

        payload_mutation = self._copy_candidate("payload-mutation")
        payload_path = payload_mutation / PAYLOAD_NAME
        manifest_path = payload_mutation / MANIFEST_NAME
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["scope"]["natural_runtime_reachability_complete"] = True
        payload_raw = _canonical(payload)
        payload_path.write_bytes(payload_raw)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][PAYLOAD_NAME] = {
            "size": len(payload_raw),
            "sha256": _sha(payload_raw),
        }
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "payload|reconstruction|scope"):
            verifier.verify_artifact(ROOT, payload_mutation)

        binary_mutation = self._copy_candidate("binary-mutation")
        bundle_path = binary_mutation / BUNDLE_NAME
        manifest_path = binary_mutation / MANIFEST_NAME
        bundle = bytearray(bundle_path.read_bytes())
        bundle[0] ^= 1
        bundle_path.write_bytes(bundle)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][BUNDLE_NAME] = {
            "size": len(bundle),
            "sha256": _sha(bytes(bundle)),
        }
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "binary|bundle|ROM"):
            verifier.verify_artifact(ROOT, binary_mutation)

        foreign = self._copy_candidate("foreign-file")
        (foreign / "foreign.txt").write_text("not part of the packet\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "foreign|file set"):
            verifier.verify_artifact(ROOT, foreign)

        forged = self._copy_candidate("forged-status")
        manifest_path = forged / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact_status"] = "accepted"
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "accepted|candidate|receipt"):
            verifier.verify_artifact(ROOT, forged)

    def test_acceptance_receipt_is_reproducible_and_not_forgeable(self) -> None:
        _, verifier = self._implemented()
        candidate = self._candidate("accept-candidate")
        accepted = Path(self.temporary.name) / "accepted"
        verifier.accept_candidate(ROOT, candidate, accepted)
        report = verifier.verify_artifact(ROOT, accepted)
        self.assertTrue(report["verified"])
        self.assertEqual(report["artifact_status"], "accepted")

        manifest_path = accepted / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["verification"]["exit_code"], 0)
        self.assertEqual(manifest["verification"]["report"], report)
        self.assertEqual(manifest["verifier"], manifest["verification"])
        self.assertEqual(manifest["coverage_projection"]["claim_count"], 5)
        self.assertEqual(len(manifest["coverage_projection"]["claims"]), 5)
        self.assertEqual(manifest["coverage_projection"]["byte_count"], 226)
        self.assertEqual(
            manifest["coverage_projection"]["semantic_range_vector_sha256"],
            SEMANTIC_RANGE_VECTOR_SHA256,
        )
        self.assertEqual(
            [
                {field: claim.get(field) for field in CLAIM_IDENTITY_FIELDS}
                for claim in manifest["coverage_projection"]["claims"]
            ],
            EXPECTED_CLAIM_IDENTITIES,
        )

        second = Path(self.temporary.name) / "accepted-second"
        verifier.accept_candidate(ROOT, candidate, second)
        for name in (PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME):
            self.assertEqual((accepted / name).read_bytes(), (second / name).read_bytes())

        broken = Path(self.temporary.name) / "accepted-broken"
        shutil.copytree(accepted, broken)
        broken_manifest_path = broken / MANIFEST_NAME
        broken_manifest = json.loads(broken_manifest_path.read_text(encoding="utf-8"))
        broken_manifest["verification"]["exit_code"] = 1
        broken_manifest_path.write_bytes(_canonical(broken_manifest))
        with self.assertRaisesRegex(ValueError, "receipt|manifest|verification"):
            verifier.verify_artifact(ROOT, broken)

    def test_pre_and_post_coverage_are_exact_states_with_derived_segment_count(self) -> None:
        _, verifier = self._implemented()
        accepted = Path(self.temporary.name) / "accepted-for-coverage"
        candidate = self._candidate("coverage-candidate")
        verifier.accept_candidate(ROOT, candidate, accepted)
        payload = json.loads((accepted / PAYLOAD_NAME).read_text(encoding="utf-8"))
        manifest_raw = (accepted / MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        expected_claims = verifier.expected_coverage_claims(
            payload,
            manifest,
            manifest_sha256=_sha(manifest_raw),
        )
        self.assertEqual(len(expected_claims), 5)
        self.assertEqual(
            226,
            sum(claim["range"][1] - claim["range"][0] for claim in expected_claims),
        )
        self.assertEqual(
            PROMOTION_RANGES,
            [claim["range"] for claim in expected_claims],
        )
        self.assertEqual(
            [
                {field: claim.get(field) for field in CLAIM_IDENTITY_FIELDS}
                for claim in expected_claims
            ],
            EXPECTED_CLAIM_IDENTITIES,
        )

        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        pre = verifier.analyze_live_coverage(
            coverage,
            artifact_status="accepted",
            expected_claims=expected_claims,
        )
        post_coverage = _project_post_coverage(coverage, expected_claims)
        self.assertEqual(post_coverage["summary"]["classified_bytes"], 6_121_850)
        self.assertEqual(post_coverage["summary"]["unknown_bytes"], 169_606)
        self.assertEqual(post_coverage["summary"]["claim_count"], 14_476)
        self.assertEqual(post_coverage["summary"]["segment_count"], 16_589)
        self.assertEqual(len(post_coverage["segments"]), 16_589)
        self.assertEqual(
            _sha(_canonical(post_coverage["segments"])),
            POST_SEGMENTS_SHA256,
        )
        target_claim_ids = {claim["id"] for claim in expected_claims}
        for segment in post_coverage["segments"]:
            if target_claim_ids.intersection(segment.get("primary_claim_ids", [])):
                self.assertNotIn("unknown_reason", segment)
        post = verifier.analyze_live_coverage(
            post_coverage,
            artifact_status="accepted",
            expected_claims=expected_claims,
        )
        self.assertEqual(pre, post)
        self.assertEqual(
            pre,
            {
                "coverage_contract_verified": True,
                "promotion_bytes": 226,
                "promotion_claim_count": 5,
            },
        )
        with mock.patch.object(
            verifier,
            "_read_live_coverage",
            return_value=(_canonical(post_coverage), post_coverage),
        ):
            report = verifier.verify_artifact(ROOT, accepted)
        self.assertTrue(report["verified"])
        self.assertEqual(report["artifact_status"], "accepted")

        wrong_owner = copy.deepcopy(post_coverage)
        for segment in wrong_owner["segments"]:
            if segment["range"] == expected_claims[0]["range"]:
                segment["primary_claim_ids"] = ["wrong-owner"]
                break
        with self.assertRaisesRegex(ValueError, "coverage|owner|claim"):
            verifier.analyze_live_coverage(
                wrong_owner,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        wrong_claim = copy.deepcopy(post_coverage)
        for claim in wrong_claim["claims"]:
            if claim.get("id") == expected_claims[0]["id"]:
                claim["claim_kind"] = "wrong-kind"
                break
        with self.assertRaisesRegex(ValueError, "coverage|owner|claim"):
            verifier.analyze_live_coverage(
                wrong_claim,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        for position in (0, len(post_coverage["claims"])):
            with self.subTest(duplicate_position=position):
                duplicate = copy.deepcopy(post_coverage)
                conflicting = copy.deepcopy(expected_claims[0])
                conflicting["claim_kind"] = "conflicting-duplicate"
                duplicate["claims"].insert(position, conflicting)
                duplicate["summary"]["claim_count"] += 1
                with self.assertRaisesRegex(ValueError, "duplicate|unique|claim"):
                    verifier.analyze_live_coverage(
                        duplicate,
                        artifact_status="accepted",
                        expected_claims=expected_claims,
                    )

        stale_summary = copy.deepcopy(post_coverage)
        stale_summary["summary"].update({
            "classified_bytes": 6_121_624,
            "unknown_bytes": 169_832,
            "claim_count": 14_471,
            "segment_count": 16_582,
        })
        with self.assertRaisesRegex(ValueError, "summary|count|classified|unknown"):
            verifier.analyze_live_coverage(
                stale_summary,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        partial = copy.deepcopy(post_coverage)
        first_start, first_end = expected_claims[0]["range"]
        for segment in partial["segments"]:
            if segment["range"] == [first_start, first_end]:
                segment["primary_class"] = "unknown"
                segment["primary_claim_ids"] = []
                segment["unknown_reason"] = "synthetic partial promotion"
                break
        partial["summary"]["classified_bytes"] -= first_end - first_start
        partial["summary"]["unknown_bytes"] += first_end - first_start
        with self.assertRaisesRegex(ValueError, "partial|coverage"):
            verifier.analyze_live_coverage(
                partial,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

    def test_non_target_coverage_drift_and_path_escape_are_rejected(self) -> None:
        exporter, verifier = self._implemented()
        accepted = Path(self.temporary.name) / "accepted-for-drift"
        candidate = self._candidate("drift-candidate")
        verifier.accept_candidate(ROOT, candidate, accepted)
        payload = json.loads((accepted / PAYLOAD_NAME).read_text(encoding="utf-8"))
        manifest_raw = (accepted / MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        expected_claims = verifier.expected_coverage_claims(
            payload,
            manifest,
            manifest_sha256=_sha(manifest_raw),
        )
        baseline = json.loads(COVERAGE.read_text(encoding="utf-8"))
        post = _project_post_coverage(baseline, expected_claims)

        drifted_pre = copy.deepcopy(baseline)
        drifted_pre["claims"][0]["limitations"] = ["forged non-target evidence"]
        with self.assertRaisesRegex(ValueError, "coverage|baseline|claim|identity"):
            verifier.analyze_live_coverage(
                drifted_pre,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_claim = copy.deepcopy(post)
        drifted_claim["claims"][0]["limitations"] = ["forged non-target evidence"]
        with self.assertRaisesRegex(ValueError, "coverage|post|claim|identity"):
            verifier.analyze_live_coverage(
                drifted_claim,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_segment = copy.deepcopy(post)
        drifted_segment["segments"][0]["forged_metadata"] = True
        with self.assertRaisesRegex(ValueError, "coverage|post|segment|identity"):
            verifier.analyze_live_coverage(
                drifted_segment,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_summary = copy.deepcopy(post)
        drifted_summary["summary"]["cfg_root_count"] = -1
        with self.assertRaisesRegex(ValueError, "coverage|post|summary|identity"):
            verifier.analyze_live_coverage(
                drifted_summary,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_limitation = copy.deepcopy(post)
        drifted_limitation["limitations"].append("forged limitation")
        with self.assertRaisesRegex(ValueError, "coverage|post|limitation|identity"):
            verifier.analyze_live_coverage(
                drifted_limitation,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            real = base / "real"
            real.mkdir()
            shutil.copytree(candidate, real / "candidate")
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verifier.verify_artifact(ROOT, linked / "candidate")

        active = ROOT / "build/experiments/active"
        with tempfile.TemporaryDirectory(dir=active) as repository_temporary:
            repository_candidate = Path(repository_temporary) / "candidate"
            exporter.write_artifact(ROOT, repository_candidate)
            relative = repository_candidate.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as foreign_cwd:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(VERIFIER_PATH),
                        "--root",
                        str(ROOT),
                        "--artifact-dir",
                        str(relative),
                    ],
                    cwd=foreign_cwd,
                    text=True,
                    capture_output=True,
                )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
