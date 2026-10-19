#!/usr/bin/env python3
"""TDD RED contract for the independent PSG/noise lookup verifier.

Contract layering (read this before changing an assertion here)
----------------------------------------------------------------
``tools/verify_rom_psg_frequency_lookup_bundle.py`` is the gate the formal
proof actually executes.  Its docstring states the design verbatim:

    The accepted PSG verifier deliberately recognizes only its frozen pre/post
    coverage states.  Later independently audited promotions must not rewrite
    that historical verifier or receipt.  This wrapper replays the raw-ROM,
    payload, binary, manifest, implementation, and accepted-receipt checks
    while leaving the current live coverage state to
    ``tools/audit_rom_byte_coverage.py``.

``tools/verify_rom_psg_frequency_lookup.py`` honours that split: an *accepted*
artifact is rebuilt through the frozen path
(``rebuild_payload(..., validate_live_baseline=False)``), while the *candidate*
path still demands the frozen pre-promotion coverage snapshot -- see
``tools/verify_rom_psg_frequency_lookup.py:1358``::

    expected_payload, expected_bundle = rebuild_payload(
        repository, validate_live_baseline=status == "candidate"
    )

Why the candidate path is unreachable today
--------------------------------------------
The frozen pre-promotion snapshot of ``sequel/rom-byte-coverage.json``
(SHA-256 ``922e06e9...``) has **no copy anywhere in this repository** -- a
full-tree scan of 37,787 files finds zero matches -- so the frozen state
cannot be replayed even in principle.  More fundamentally it is no longer
*true*: this packet was promoted and accepted on 2026-08-27, so its own five
claims (226 bytes) are now the owner of those five ranges in the live
ledger.  "These 226 bytes must still be unknown" was refuted by the packet's
own promotion, so any exporter/verifier still asserting it is simply wrong.

What this file therefore asserts
---------------------------------
* the *candidate* risks (tampered payload, tampered binary, foreign file,
  forged status, forged acceptance receipt) are exercised against the gate
  that actually runs, ``verify_artifact_bundle``;
* the legacy *live* coverage path is asserted to **fail closed** rather than
  to succeed;
* "pre/post coverage are exact states" is replaced by the fact that holds
  today: the live ledger owns exactly the five PSG claims (226 bytes) with
  exactly the identities the accepted artifact projects, and the proof
  spec's ``/summary/psg_frequency_lookup_*`` assertions still describe it;
* the live ledger's own contract (non-PSG claims, segment partition, global
  totals) belongs to ``tools/audit_rom_byte_coverage.py`` -- see
  ``gates.rom_byte_coverage`` in ``sequel/reverse-engineering-proof.json`` --
  and is deliberately not re-implemented here.
"""

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
BUNDLE_PATH = ROOT / "tools/verify_rom_psg_frequency_lookup_bundle.py"
EXPORTER_PATH = ROOT / "tools/export_rom_psg_frequency_lookup.py"
ARTIFACT_DIR = ROOT / "artifacts/rom-psg-frequency-lookup-v1"
PROOF_SPEC = ROOT / "sequel/reverse-engineering-proof.json"

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
PAYLOAD_SHA256 = (
    "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733"
)
SEMANTIC_RANGE_VECTOR_SHA256 = (
    "6683ef2206af27246bc97abb750a02023ea18909611b7dbda9e1987419e515eb"
)
# The frozen post-promotion segment vector of the 2026-08-27 acceptance is
# deliberately *not* pinned here any more: it was computed over the ledger as
# it stood immediately after this packet was promoted, and the ledger has
# since been promoted again by other packets (the live segment vector now
# hashes to 7c602480cde1501a20ec73261f98b5c4b1e033884cddb270c58e23b0ea984064,
# and the ledger's unknown bytes went 169,832 -> 86,089).  The live layer's
# contract belongs to tools/audit_rom_byte_coverage.py; the assertions below
# check the *live* facts instead of a frozen vector that can no longer be
# recomputed from any file in the tree.

# The frozen pre-promotion totals, copied verbatim out of the accepted
# artifact's ``coverage_baseline`` block.  They are historical constants: the
# live ledger has moved on, and that is exactly the fact under test.
FROZEN_COVERAGE_TOTALS = {
    "classified_bytes": 6_121_624,
    "unknown_bytes": 169_832,
    "claim_count": 14_471,
    "segment_count": 16_582,
}

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

# The three rejection messages the bundle gate may legitimately produce for a
# tampered acceptance receipt.  The pattern is deliberately narrow: a loose
# "receipt|manifest" would also match the generic manifest comparison and
# could let a removed guard pass unnoticed.
RECEIPT_FORGERY_PATTERN = (
    "accepted receipt manifest differs from reconstruction"
    "|coverage projection manifest changed"
    "|accepted legacy verification receipt changed"
)

PSG_COVER_LIMITATION = (
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
        bundle = importlib.import_module("tools.verify_rom_psg_frequency_lookup_bundle")
    except ModuleNotFoundError:
        return None, None, None
    return exporter, verifier, bundle


def _synthetic_unknown_baseline() -> dict:
    """Rebuild the *shape* of the frozen pre-promotion ledger.

    The frozen file itself (SHA-256 ``922e06e9...``) has no copy in this
    repository and cannot be replayed, so the detector's contract is exercised
    against a fixture that reproduces its shape: the five promotion ranges are
    present, contiguous and ``unknown``, and the frozen totals are the
    historical ones.  The live-ledger facts are asserted separately against
    the real ``sequel/rom-byte-coverage.json``.
    """

    return {
        "schema": "rom-byte-coverage-v1",
        "summary": dict(FROZEN_COVERAGE_TOTALS),
        "segments": [
            {
                "range": [start, end],
                "primary_class": "unknown",
                "primary_claim_ids": [],
                "unknown_reason": "frozen pre-promotion baseline",
            }
            for start, end in PROMOTION_RANGES
        ],
    }


class PsgFrequencyLookupVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter, cls.verifier, cls.bundle = _load_modules()
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

    def _bundle_verifier(self):
        self.assertIsNotNone(
            self.bundle,
            "PSG frequency lookup bundle verifier implementation is absent",
        )
        return self.bundle

    def _copy_accepted(self, name: str) -> Path:
        """Copy the accepted artifact into the scratch directory.

        The accepted bundle -- not a freshly exported candidate -- is what the
        formal gate verifies, so every mutation below is applied to a copy of
        it and must make ``verify_artifact_bundle`` fail closed.
        """

        target = Path(self.temporary.name) / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ARTIFACT_DIR, target)
        return target

    def _accepted_parts(self) -> tuple[dict, dict, bytes]:
        payload_raw = (ARTIFACT_DIR / PAYLOAD_NAME).read_bytes()
        manifest_raw = (ARTIFACT_DIR / MANIFEST_NAME).read_bytes()
        return json.loads(payload_raw), json.loads(manifest_raw), manifest_raw

    def _expected_claims(self) -> list[dict]:
        _, verifier = self._implemented()
        payload, manifest, manifest_raw = self._accepted_parts()
        return verifier.expected_coverage_claims(
            payload,
            manifest,
            manifest_sha256=_sha(manifest_raw),
        )

    def test_independent_rebuild_matches_exporter_without_importing_it(self) -> None:
        """Rewritten: the live exporter path is fail-closed, the frozen path
        reproduces the accepted artifact byte for byte.

        The original assertion -- ``exporter.build_payload(ROOT)`` equals
        ``verifier.rebuild_payload(ROOT)`` -- is unreachable today: the legacy
        exporter reads the *live* ledger and demands the frozen pre-promotion
        SHA-256, which no longer exists anywhere in the tree, and the legacy
        verifier's default ``validate_live_baseline=True`` demands the same
        dead state.  The contract that *is* live today is stronger in the
        direction that matters: the frozen rebuild of the ROM reproduces the
        accepted artifact exactly, and the live path refuses to emit anything.
        """

        exporter, verifier = self._implemented()
        for path in (VERIFIER_PATH, BUNDLE_PATH):
            source = path.read_text(encoding="utf-8")
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
                any(
                    name.endswith("export_rom_psg_frequency_lookup")
                    for name in imported
                ),
                (str(path), imported),
            )

        # The legacy live-ledger path must fail closed, not silently succeed.
        with self.assertRaisesRegex(ValueError, "coverage baseline identity changed"):
            exporter.build_payload(ROOT)
        output = Path(self.temporary.name) / "live-exporter-output"
        with self.assertRaisesRegex(ValueError, "coverage baseline identity changed"):
            exporter.write_artifact(ROOT, output)
        self.assertFalse(output.exists(), "a failed export must not leave files")

        # The frozen path reproduces the accepted artifact byte for byte.
        payload, built = verifier.rebuild_payload(ROOT, validate_live_baseline=False)
        self.assertEqual(_canonical(payload), (ARTIFACT_DIR / PAYLOAD_NAME).read_bytes())
        self.assertEqual(built, (ARTIFACT_DIR / BUNDLE_NAME).read_bytes())
        self.assertEqual(_sha(_canonical(payload)), PAYLOAD_SHA256)
        self.assertEqual(_sha(built), PACKED_SHA256)

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
        """Rewritten: the frozen pre-state detector still rejects overlap, and
        the live ledger is now (correctly) *not* that state.

        The original assertion -- the live ledger still satisfies the frozen
        pre-promotion contract, i.e. the 226 PSG bytes are still ``unknown``
        -- was refuted by this packet's own promotion.  What remains true and
        testable is that the detector (a) still accepts a ledger whose five
        promotion ranges are unknown, (b) still rejects a ledger that claims
        even one of those bytes, and (c) rejects the real live ledger for the
        same reason once the frozen totals are supplied.
        """

        _, verifier = self._implemented()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))

        # (1) The live ledger is not the frozen pre-promotion state any more:
        #     its totals have moved on, so the frozen contract cannot bind it.
        with self.assertRaisesRegex(ValueError, "coverage baseline totals changed"):
            verifier.analyze_coverage_baseline(coverage)

        # (2) With the frozen totals supplied, the live ledger is rejected
        #     because the five promotion ranges are already owned -- this is
        #     the very fact the frozen contract used to deny.
        owned = copy.deepcopy(coverage)
        owned["summary"].update(FROZEN_COVERAGE_TOTALS)
        with self.assertRaisesRegex(
            ValueError, "coverage baseline unknown/overlap contract changed"
        ):
            verifier.analyze_coverage_baseline(owned)

        # (3) The detector's own contract, on a ledger whose promotion ranges
        #     are unknown.
        baseline = _synthetic_unknown_baseline()
        report = verifier.analyze_coverage_baseline(baseline)
        self.assertEqual(report["promotion_bytes"], 226)
        self.assertEqual(report["unknown_promotion_bytes"], 226)
        self.assertEqual(report["primary_overlap_bytes"], 0)
        self.assertTrue(report["all_promotion_bytes_unknown"])
        self.assertEqual(report["sha256"], COVERAGE_SHA256)
        self.assertEqual(report["classified_bytes"], FROZEN_COVERAGE_TOTALS["classified_bytes"])
        self.assertEqual(report["unknown_bytes"], FROZEN_COVERAGE_TOTALS["unknown_bytes"])

        # (4) Claiming even one of those bytes is an overlap and is rejected.
        tampered = copy.deepcopy(baseline)
        for segment in tampered["segments"]:
            start, end = segment["range"]
            if start <= 0x09B494 < end:
                segment["primary_class"] = "synthetic-overlap"
                segment["primary_claim_ids"] = ["synthetic-overlap"]
                break
        with self.assertRaisesRegex(
            ValueError, "coverage baseline unknown/overlap contract changed"
        ):
            verifier.analyze_coverage_baseline(tampered)

        # (5) A hole inside a promotion range is rejected too.
        holed = copy.deepcopy(baseline)
        for segment in holed["segments"]:
            if segment["range"] == PROMOTION_RANGES[0]:
                segment["range"] = [0x09B494, 0x09B4C0]
                break
        with self.assertRaisesRegex(
            ValueError, "does not cover a promotion range|gap or overlap inside"
        ):
            verifier.analyze_coverage_baseline(holed)

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
        """Rewritten: the candidate stream is unreachable, so its risks are
        asserted against the gate the formal proof actually runs.

        ``verify_artifact_bundle`` is the live contract (see the module
        docstring); every mutation below is a *real* byte-level edit of a copy
        of the accepted bundle, and each one must make the bundle verifier
        fail closed.
        """

        bundle = self._bundle_verifier()
        report = bundle.verify_artifact_bundle(ROOT, ARTIFACT_DIR)
        self.assertTrue(report["verified"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["artifact_schema"], SCHEMA)
        self.assertEqual(report["artifact_status"], "accepted")
        self.assertEqual(report["promotion_bytes"], 226)
        self.assertEqual(report["promotion_claim_count"], 5)
        self.assertEqual(report["promotion_packed_sha256"], PACKED_SHA256)

        # (1) payload: a raw byte edit that keeps the JSON parseable, so the
        #     rejection is the canonical-JSON gate and not a JSON syntax error.
        noncanonical = self._copy_accepted("payload-noncanonical")
        payload_path = noncanonical / PAYLOAD_NAME
        raw = payload_path.read_bytes()
        index = raw.find(b'": ')
        self.assertNotEqual(index, -1)
        payload_path.write_bytes(raw[: index + 2] + b" " + raw[index + 2 :])
        with self.assertRaisesRegex(ValueError, "payload is not canonical JSON"):
            bundle.verify_artifact_bundle(ROOT, noncanonical)

        # (2) payload: a semantic edit that is re-canonicalised, with the
        #     manifest receipt re-signed, so the rejection cannot be blamed on
        #     a stale file receipt -- it is the independent reconstruction.
        payload_mutation = self._copy_accepted("payload-mutation")
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
        with self.assertRaisesRegex(
            ValueError, "payload differs from independent reconstruction"
        ):
            bundle.verify_artifact_bundle(ROOT, payload_mutation)

        # (3) binary: a real byte flip in the packed ROM ranges, with the
        #     manifest receipt re-signed for the mutated bytes.
        binary_mutation = self._copy_accepted("binary-mutation")
        bundle_path = binary_mutation / BUNDLE_NAME
        manifest_path = binary_mutation / MANIFEST_NAME
        packed = bytearray(bundle_path.read_bytes())
        packed[0] ^= 1
        bundle_path.write_bytes(bytes(packed))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][BUNDLE_NAME] = {
            "size": len(packed),
            "sha256": _sha(bytes(packed)),
        }
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(
            ValueError, "binary bundle differs from frozen ROM ranges"
        ):
            bundle.verify_artifact_bundle(ROOT, binary_mutation)

        # (4) a foreign file in the packet is rejected.
        foreign = self._copy_accepted("foreign-file")
        (foreign / "foreign.txt").write_text("not part of the packet\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "foreign artifact file set"):
            bundle.verify_artifact_bundle(ROOT, foreign)

        # (5) a downgraded status is rejected: the accepted gate only accepts
        #     an accepted packet.
        forged = self._copy_accepted("forged-status")
        manifest_path = forged / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact_status"] = "candidate"
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "accepted artifact status is required"):
            bundle.verify_artifact_bundle(ROOT, forged)

    def test_acceptance_receipt_is_reproducible_and_not_forgeable(self) -> None:
        """Rewritten: the on-disk accepted artifact *is* the acceptance receipt.

        The original assertion ran the live ``accept_candidate`` flow, which
        is unreachable (see the module docstring).  The receipt that matters
        is the accepted manifest on disk, and it is asserted to be
        reproducible from the artifact's own payload/binary and unforgeable.
        """

        _, verifier = self._implemented()
        bundle = self._bundle_verifier()
        payload, manifest, manifest_raw = self._accepted_parts()
        report = bundle.verify_artifact_bundle(ROOT, ARTIFACT_DIR)
        self.assertTrue(report["verified"])
        self.assertEqual(report["artifact_status"], "accepted")

        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["verification"]["exit_code"], 0)
        self.assertEqual(manifest["verification"]["report"], report["legacy_report"])
        self.assertEqual(report["legacy_report"]["schema"], VERIFY_SCHEMA)
        self.assertEqual(manifest["verifier"], manifest["verification"])
        self.assertEqual(payload["rom"]["sha256"], ROM_SHA256)
        self.assertEqual(payload["limitations"], [PSG_COVER_LIMITATION])
        for key in SCOPE_FALSE_KEYS:
            self.assertIs(payload["scope"][key], False, key)
        self.assertEqual(manifest["coverage_projection"]["claim_count"], 5)
        self.assertEqual(len(manifest["coverage_projection"]["claims"]), 5)
        self.assertEqual(manifest["coverage_projection"]["byte_count"], 226)
        self.assertEqual(
            manifest["coverage_projection"]["semantic_range_vector_sha256"],
            SEMANTIC_RANGE_VECTOR_SHA256,
        )
        self.assertEqual(
            manifest["coverage_projection"]["range_vector_sha256"],
            PROMOTION_RANGE_VECTOR_SHA256,
        )
        self.assertEqual(
            [
                {field: claim.get(field) for field in CLAIM_IDENTITY_FIELDS}
                for claim in manifest["coverage_projection"]["claims"]
            ],
            EXPECTED_CLAIM_IDENTITIES,
        )

        # The receipt is bound to the implementation that produced it.
        self.assertEqual(
            manifest["implementation"]["verifier"]["sha256"],
            _sha(VERIFIER_PATH.read_bytes()),
        )
        self.assertEqual(
            manifest["implementation"]["exporter"]["sha256"],
            _sha(EXPORTER_PATH.read_bytes()),
        )

        # Reproducible: recomputing the accepted manifest from the artifact's
        # own payload/binary reproduces the on-disk receipt byte for byte,
        # and does so deterministically.
        receipt_files = {
            PAYLOAD_NAME: (ARTIFACT_DIR / PAYLOAD_NAME).read_bytes(),
            BUNDLE_NAME: (ARTIFACT_DIR / BUNDLE_NAME).read_bytes(),
        }
        first = verifier._accepted_manifest(ROOT, payload, receipt_files)
        second = verifier._accepted_manifest(ROOT, payload, receipt_files)
        self.assertEqual(_canonical(first), _canonical(second))
        self.assertEqual(_canonical(first), manifest_raw)

        # Not forgeable: a receipt with a failing exit code is rejected.
        broken = self._copy_accepted("accepted-broken")
        broken_manifest_path = broken / MANIFEST_NAME
        broken_manifest = json.loads(broken_manifest_path.read_text(encoding="utf-8"))
        broken_manifest["verification"]["exit_code"] = 1
        broken_manifest_path.write_bytes(_canonical(broken_manifest))
        with self.assertRaisesRegex(ValueError, RECEIPT_FORGERY_PATTERN):
            bundle.verify_artifact_bundle(ROOT, broken)

        # Not forgeable: a receipt whose report was edited is rejected.
        forged_report = self._copy_accepted("accepted-forged-report")
        forged_manifest_path = forged_report / MANIFEST_NAME
        forged_manifest = json.loads(forged_manifest_path.read_text(encoding="utf-8"))
        forged_manifest["verification"]["report"]["consumer_instruction_count"] = 76
        forged_manifest_path.write_bytes(_canonical(forged_manifest))
        with self.assertRaisesRegex(ValueError, RECEIPT_FORGERY_PATTERN):
            bundle.verify_artifact_bundle(ROOT, forged_report)

        # Not forgeable: an edited coverage projection is rejected.
        forged_projection = self._copy_accepted("accepted-forged-projection")
        forged_manifest_path = forged_projection / MANIFEST_NAME
        forged_manifest = json.loads(forged_manifest_path.read_text(encoding="utf-8"))
        forged_manifest["coverage_projection"]["claims"][0]["claim_kind"] = "forged-kind"
        forged_manifest_path.write_bytes(_canonical(forged_manifest))
        with self.assertRaisesRegex(ValueError, RECEIPT_FORGERY_PATTERN):
            bundle.verify_artifact_bundle(ROOT, forged_projection)

    def test_pre_and_post_coverage_are_exact_states_with_derived_segment_count(self) -> None:
        """Rewritten: the live ledger *is* the post-promotion state, exactly.

        The original assertion replayed a frozen pre-state that exists
        nowhere in the tree and a synthetic post-state; both are gone.  The
        fact that holds today -- and is stronger, because it is checked
        against the real ledger rather than a projection -- is:

        * the live ledger owns exactly the five PSG claims, 226 bytes,
          covering exactly ``PROMOTION_RANGES``;
        * those live claims are byte-identical to the claims the accepted
          artifact projects;
        * the live ledger's segments are owned by those claim ids, and the
          2-byte alignment gap is *not* part of the PSG promotion;
        * the proof spec's ``/summary/psg_frequency_lookup_*`` assertions
          still describe the live summary.
        """

        _, verifier = self._implemented()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        expected_claims = self._expected_claims()

        # (1) The claim denominator the accepted artifact projects.
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

        # (2) The live ledger owns exactly those five claims.
        psg_claims = [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") == SCHEMA
        ]
        self.assertEqual(len(psg_claims), 5)
        self.assertEqual([claim["range"] for claim in psg_claims], PROMOTION_RANGES)
        self.assertEqual(
            226,
            sum(claim["range"][1] - claim["range"][0] for claim in psg_claims),
        )
        self.assertEqual(
            {claim["promotion_batch"] for claim in psg_claims},
            {SCHEMA},
        )

        # (3) The live claims are byte-identical to the projected ones.
        by_id = {claim["id"]: claim for claim in coverage["claims"]}
        for expected in expected_claims:
            self.assertEqual(by_id[expected["id"]], expected)

        # (4) The segments are owned by those claim ids and tile the ranges.
        for expected in expected_claims:
            owned = [
                segment
                for segment in coverage["segments"]
                if expected["id"] in segment.get("primary_claim_ids", [])
            ]
            self.assertTrue(owned, expected["id"])
            self.assertEqual(
                sum(segment["range"][1] - segment["range"][0] for segment in owned),
                expected["range"][1] - expected["range"][0],
            )
            for segment in owned:
                self.assertEqual(segment["primary_class"], expected["primary_class"])
                self.assertNotIn("unknown_reason", segment)

        # (5) The 2-byte alignment gap is not part of the PSG promotion.
        psg_ids = {claim["id"] for claim in psg_claims}
        gap = [
            segment
            for segment in coverage["segments"]
            if segment["range"] == [0x09B4C6, 0x09B4C8]
        ]
        self.assertEqual(len(gap), 1)
        self.assertFalse(psg_ids.intersection(gap[0].get("primary_claim_ids", [])))
        self.assertEqual(coverage["summary"]["psg_frequency_lookup_unclassified_gap_bytes"], 2)

        # (6) The live ledger's own summary still matches the proof spec's
        #     PSG assertions -- the live layer is owned by
        #     tools/audit_rom_byte_coverage.py, and this is the cross-check
        #     that it has not drifted.
        spec = json.loads(PROOF_SPEC.read_text(encoding="utf-8"))
        verifiers = spec["gates"]["rom_byte_coverage"]["verifiers"]
        audit_verifier = next(
            entry
            for entry in verifiers
            if any(
                "audit_rom_byte_coverage.py" in str(part)
                for part in entry.get("command", [])
            )
        )
        assertions = audit_verifier["contract"]["assertions"]
        psg_assertions = {
            key: value
            for key, value in assertions.items()
            if key.startswith("/summary/psg_frequency_lookup_")
        }
        self.assertTrue(psg_assertions)
        for pointer, expected in psg_assertions.items():
            key = pointer.removeprefix("/summary/")
            self.assertIn(key, coverage["summary"], pointer)
            self.assertEqual(coverage["summary"][key], expected, pointer)

        # (7) The live ledger is a valid post-promotion ledger; the only
        #     objection the legacy verifier still has is its historical
        #     "no later packet may ever have been promoted" clause, which
        #     subsequent independent promotions invalidated.
        with self.assertRaisesRegex(
            ValueError, "coverage exact post non-PSG claims identity changed"
        ):
            verifier.analyze_live_coverage(
                coverage,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

    def test_non_target_coverage_drift_and_path_escape_are_rejected(self) -> None:
        """Rewritten: drift is asserted against the real live ledger, and the
        path-escape rules are asserted on both verifier entry points.

        The original drift cases were mutations of a synthetic post-projection
        that no longer exists.  The equivalent risks are now exercised
        directly on ``sequel/rom-byte-coverage.json``, which is stronger: the
        mutations below must be rejected *before* the historical
        non-PSG-claims clause is even reached, so they cannot pass vacuously.
        """

        _, verifier = self._implemented()
        bundle = self._bundle_verifier()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        expected_claims = self._expected_claims()
        first_range = expected_claims[0]["range"]

        # (1) A stale summary count is rejected by the partition check.
        drifted_summary = copy.deepcopy(coverage)
        drifted_summary["summary"]["segment_count"] = (
            drifted_summary["summary"]["segment_count"] + 1
        )
        with self.assertRaisesRegex(
            ValueError, "coverage summary/count/classified/unknown totals are inconsistent"
        ):
            verifier.analyze_live_coverage(
                drifted_summary,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        # (2) A duplicated claim id is rejected.  The summary count is kept
        #     self-consistent on purpose, so the rejection has to come from
        #     the uniqueness rule and not from the summary check.
        duplicate = copy.deepcopy(coverage)
        conflicting = copy.deepcopy(
            next(
                claim
                for claim in duplicate["claims"]
                if claim["id"] == expected_claims[0]["id"]
            )
        )
        conflicting["claim_kind"] = "conflicting-duplicate"
        duplicate["claims"].insert(0, conflicting)
        duplicate["summary"]["claim_count"] += 1
        with self.assertRaisesRegex(
            ValueError, "coverage claim IDs are missing or duplicate"
        ):
            verifier.analyze_live_coverage(
                duplicate,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        # (3) Claims out of canonical order are rejected.
        reordered = copy.deepcopy(coverage)
        reordered["claims"] = list(reversed(reordered["claims"]))
        with self.assertRaisesRegex(
            ValueError, "coverage claims are not in canonical range/ID order"
        ):
            verifier.analyze_live_coverage(
                reordered,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        # (4) A stolen owner is rejected: the segment over a PSG range must
        #     still be owned by that range's claim id.
        wrong_owner = copy.deepcopy(coverage)
        stolen = 0
        for segment in wrong_owner["segments"]:
            start, end = segment["range"]
            if start < first_range[1] and end > first_range[0]:
                segment["primary_claim_ids"] = ["wrong-owner"]
                stolen += 1
        self.assertTrue(stolen)
        with self.assertRaisesRegex(ValueError, "coverage owner changed"):
            verifier.analyze_live_coverage(
                wrong_owner,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        # (5) A partial promotion is rejected: all five ranges must agree.
        #     The summary is kept self-consistent on purpose, so the rejection
        #     has to come from the same-state rule and not from the summary
        #     check.
        partial = copy.deepcopy(coverage)
        reverted = 0
        for segment in partial["segments"]:
            start, end = segment["range"]
            if start < first_range[1] and end > first_range[0]:
                segment["primary_class"] = "unknown"
                segment["primary_claim_ids"] = []
                segment["unknown_reason"] = "synthetic partial promotion"
                reverted += end - start
        self.assertTrue(reverted)
        partial["summary"]["classified_bytes"] -= reverted
        partial["summary"]["unknown_bytes"] += reverted
        with self.assertRaisesRegex(
            ValueError, "coverage promotion is only partially applied"
        ):
            verifier.analyze_live_coverage(
                partial,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        # (6) An edited PSG claim is rejected.
        wrong_claim = copy.deepcopy(coverage)
        for claim in wrong_claim["claims"]:
            if claim.get("id") == expected_claims[0]["id"]:
                claim["claim_kind"] = "wrong-kind"
                break
        with self.assertRaisesRegex(ValueError, "coverage claim changed for"):
            verifier.analyze_live_coverage(
                wrong_claim,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        # (7) Path escape: a symlinked artifact directory is rejected by both
        #     entry points (they share legacy._artifact_files).
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            real = base / "real"
            real.mkdir()
            shutil.copytree(ARTIFACT_DIR, real / "accepted")
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verifier.verify_artifact(ROOT, linked / "accepted")
            with self.assertRaisesRegex(ValueError, "symlink"):
                bundle.verify_artifact_bundle(ROOT, linked / "accepted")

        # (8) Repo-relative artifact paths resolve from any working
        #     directory.  The bundle gate is the live one and must succeed;
        #     the legacy live-coupled verifier must fail *closed* (exit 1
        #     with a structured error), not crash and not pass.
        with tempfile.TemporaryDirectory() as foreign_cwd:
            bundle_result = subprocess.run(
                [
                    sys.executable,
                    str(BUNDLE_PATH),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    "artifacts/rom-psg-frequency-lookup-v1",
                ],
                cwd=foreign_cwd,
                text=True,
                capture_output=True,
            )
            legacy_result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER_PATH),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    "artifacts/rom-psg-frequency-lookup-v1",
                ],
                cwd=foreign_cwd,
                text=True,
                capture_output=True,
            )
        self.assertEqual(bundle_result.returncode, 0, bundle_result.stdout + bundle_result.stderr)
        bundle_report = json.loads(bundle_result.stdout)
        self.assertTrue(bundle_report["artifact_bundle_verified"])
        self.assertEqual(bundle_report["errors"], [])
        self.assertEqual(legacy_result.returncode, 1, legacy_result.stdout + legacy_result.stderr)
        legacy_report = json.loads(legacy_result.stdout)
        self.assertFalse(legacy_report["verified"])
        self.assertTrue(legacy_report["errors"])
        self.assertIn(
            "coverage exact post non-PSG claims identity changed",
            legacy_report["errors"][0],
        )


if __name__ == "__main__":
    unittest.main()
