#!/usr/bin/env python3
"""TDD contract for the frozen PSG/noise frequency lookup exporter.

What this file asserts, and why it was rewritten
------------------------------------------------
``tools/export_rom_psg_frequency_lookup.py`` is the *exporter* of the frozen
``rom-psg-frequency-lookup-v1`` packet.  It has exactly one live input --
``sequel/rom-byte-coverage.json`` -- and it reads it through
``_coverage_baseline()``, which demands the frozen pre-promotion SHA-256
``922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6``.

That frozen state is gone:

* the live ledger now hashes to
  ``9f8a819647afba8f2dc01791dd19bf6a5776012d324e5a2ff694fb51634efb26`` and
  has no copy anywhere in this repository, so the gate can never be satisfied;
* the packet itself was promoted and accepted on 2026-08-27, so its own five
  claims (226 bytes) are now the *owner* of those five ranges in the live
  ledger.  "These 226 bytes must still be unknown" was refuted by the
  packet's own promotion.

The contract layering the repository already documents (see the docstring of
``tools/verify_rom_psg_frequency_lookup_bundle.py``) is:

    The accepted PSG verifier deliberately recognizes only its frozen pre/post
    coverage states.  Later independently audited promotions must not rewrite
    that historical verifier or receipt.  This wrapper replays the raw-ROM,
    payload, binary, manifest, implementation, and accepted-receipt checks
    while leaving the current live coverage state to
    ``tools/audit_rom_byte_coverage.py``.

The exporter has **no** bundle wrapper: ``build_payload`` ->
``_build_payload_from_rom`` -> ``_coverage_baseline(root)`` is unconditional,
so the exporter's only reachable behaviour today is to **fail closed**.  This
file therefore pins:

* the live-ledger path fails closed with an exact message and leaves **no**
  file on disk (atomicity of the failure);
* the exporter's ledger-independent half -- ROM identity, the five
  ``PROMOTION_RANGES`` and their per-range digests, the range/semantic vector
  receipts, the packed bundle, and the ``promotion`` /
  ``producer_denominator`` / ``provenance`` / ``consumer`` /
  ``literal_bindings`` / ``table`` / ``lookup`` / ``scope`` / ``limitations``
  sections -- is still exact, by driving the exporter with its own frozen
  baseline instead of the dead live ledger;
* the frozen rebuild reproduces the accepted artifact byte for byte
  (payload SHA-256 ``d2631b1a...``, bundle SHA-256 ``e625a5fc...``);
* payload construction is deterministic.
"""

from __future__ import annotations

import contextlib
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
ARTIFACT_DIR = ROOT / "artifacts/rom-psg-frequency-lookup-v1"
ACTIVE = ROOT / "build/experiments/active"

SCHEMA = "rom-psg-frequency-lookup-v1"
PAYLOAD_NAME = "rom-psg-frequency-lookup.json"
BUNDLE_NAME = "rom-psg-frequency-lookup.bin"
MANIFEST_NAME = "manifest.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6"
# The frozen *pre-promotion* totals, copied verbatim out of the accepted
# artifact's ``coverage_baseline`` block.  They are historical constants: the
# live ledger has moved on, and that is exactly the fact under test.
FROZEN_COVERAGE_TOTALS = {
    "classified_bytes": 6_121_624,
    "unknown_bytes": 169_832,
    "claim_count": 14_471,
    "segment_count": 16_582,
}
PAYLOAD_SHA256 = "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733"
ACCEPTED_MANIFEST_SHA256 = (
    "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f"
)

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

# The exact rejection messages the exporter may legitimately produce.  The
# patterns are anchored so that "some other gate also failed" cannot satisfy
# them.
COVERAGE_IDENTITY_MESSAGE = r"^coverage baseline identity changed$"
RANGE_VECTOR_MESSAGE = r"^promotion range vector receipt identity changed$"
SEMANTIC_VECTOR_MESSAGE = r"^semantic range vector receipt identity changed$"
OVERLAP_MESSAGE = r"^coverage baseline unknown/overlap contract changed$"
COVERAGE_TOTALS_MESSAGE = r"^coverage baseline totals changed$"
COVERAGE_HOLE_MESSAGE = r"^coverage baseline does not cover a promotion range$"
FOREIGN_OUTPUT_MESSAGE = r"^foreign artifact output directory$"
SYMLINK_OUTPUT_MESSAGE = r"^artifact output uses a symlink component"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _load_modules():
    """Load lazily so RED reports a missing implementation explicitly."""

    try:
        exporter = importlib.import_module("tools.export_rom_psg_frequency_lookup")
        verifier = importlib.import_module("tools.verify_rom_psg_frequency_lookup")
    except ModuleNotFoundError:
        return None, None
    return exporter, verifier


def _frozen_ledger() -> dict:
    """Rebuild the *shape* of the frozen pre-promotion ledger.

    The frozen file itself (SHA-256 ``922e06e9...``) has no copy in this
    repository and cannot be replayed, so the exporter's pre-state detector is
    exercised against a fixture that reproduces its shape: the five promotion
    ranges are present, contiguous and ``unknown``, and the frozen totals are
    the historical ones.
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


@contextlib.contextmanager
def _frozen_coverage_stub(exporter):
    """Drive the exporter off the dead live ledger and onto its frozen state.

    Only the single live reader ``_coverage_baseline`` is replaced, with the
    exporter's own ``_frozen_coverage_baseline()``.  Every other section of
    the payload is still computed from the raw ROM by the real code, so the
    assertions below stay honest.
    """

    with mock.patch.object(
        exporter,
        "_coverage_baseline",
        lambda root: exporter._frozen_coverage_baseline(),
    ):
        yield


class PsgFrequencyLookupExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter, cls.verifier = _load_modules()
        # ``build/`` is gitignored scratch space; the repository-local output
        # convention needs it to exist.
        ACTIVE.mkdir(parents=True, exist_ok=True)

    def _implemented(self):
        self.assertIsNotNone(
            self.exporter,
            "PSG frequency lookup exporter implementation is absent",
        )
        return self.exporter

    def _frozen_payload(self):
        """Build the payload through the exporter's frozen coverage state."""

        exporter = self._implemented()
        with _frozen_coverage_stub(exporter):
            return exporter.build_payload(ROOT)

    # ------------------------------------------------------------------
    # The live-ledger path: today's only reachable exporter behaviour.
    # ------------------------------------------------------------------
    def test_live_coverage_path_fails_closed_and_leaves_no_output(self) -> None:
        """Rewritten: the live ledger path is unreachable, so it must fail
        closed instead of producing a payload.

        The original assertion demanded that the live ledger still satisfy the
        frozen pre-promotion contract (the 226 promoted bytes still
        ``unknown``).  That is false today: the packet's own 2026-08-27
        promotion made those bytes the owner of the live ledger, and the
        frozen ledger file has no copy in the tree, so the gate can never be
        satisfied.  What is true -- and what must be pinned -- is that the
        exporter refuses to emit anything and leaves no file behind.
        """

        exporter = self._implemented()
        live_raw = COVERAGE.read_bytes()
        self.assertNotEqual(
            _sha(live_raw),
            COVERAGE_SHA256,
            "the live ledger must not be the frozen pre-promotion snapshot",
        )

        with self.assertRaisesRegex(ValueError, COVERAGE_IDENTITY_MESSAGE):
            exporter.build_payload(ROOT)

        with tempfile.TemporaryDirectory(dir=ACTIVE) as temporary:
            parent = Path(temporary)
            output = parent / "candidate"
            with self.assertRaisesRegex(ValueError, COVERAGE_IDENTITY_MESSAGE):
                exporter.write_artifact(ROOT, output)
            self.assertFalse(
                output.exists(), "a failed export must not create its output"
            )
            self.assertEqual(
                sorted(path.name for path in parent.iterdir()),
                [],
                "a failed export must not leave a partial or temporary file",
            )

    # ------------------------------------------------------------------
    # The ledger-independent half of the exporter.
    # ------------------------------------------------------------------
    def test_build_payload_freezes_five_ranges_and_packed_bytes(self) -> None:
        """Rewritten: the frozen build still pins ROM identity, the five
        ranges, their per-range digests and the packed bundle.
        """

        exporter = self._implemented()
        payload, bundle = self._frozen_payload()
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
        # every individual range is re-digested from the raw ROM
        for index, (start, end) in enumerate(PROMOTION_RANGES):
            with self.subTest(range_index=index):
                self.assertEqual(
                    _sha(self.rom[start:end]), PROMOTION_RANGE_SHA256[index]
                )
        self.assertEqual(promotion["semantic_ranges"], SEMANTIC_RANGE_SPECS)
        self.assertEqual(
            promotion["semantic_range_vector_sha256"],
            SEMANTIC_RANGE_VECTOR_SHA256,
        )

    def test_range_and_semantic_vector_receipts_are_recomputed(self) -> None:
        """Rewritten: the two vector receipts are still recomputed, and the
        rejection text is pinned to the exact gate that produced it.
        """

        exporter = self._implemented()
        for constant, message in (
            ("PROMOTION_RANGE_VECTOR_SHA256", RANGE_VECTOR_MESSAGE),
            ("SEMANTIC_RANGE_VECTOR_SHA256", SEMANTIC_VECTOR_MESSAGE),
        ):
            with self.subTest(constant=constant), mock.patch.object(
                exporter, constant, "0" * 64
            ):
                with _frozen_coverage_stub(exporter):
                    with self.assertRaisesRegex(ValueError, message):
                        exporter.build_payload(ROOT)

    def test_frozen_coverage_baseline_is_the_historical_unknown_state(self) -> None:
        """Rewritten: the pre-promotion "226 unknown bytes" contract survives
        as a frozen constant plus a detector, and the live ledger is asserted
        to be the *other* state.

        The original assertion demanded the live ledger to still be that
        state.  The live ledger is now owned by the packet's own promotion, so
        the contract is re-expressed as: (a) the exporter still carries the
        frozen baseline verbatim, (b) its detector still accepts a ledger whose
        five promotion ranges are unknown and still rejects one that claims a
        single one of those bytes, and (c) the live ledger is *not* that state
        any more -- it is owned by the PSG claims.
        """

        exporter = self._implemented()
        expected = {
            "path": "sequel/rom-byte-coverage.json",
            "schema": "rom-byte-coverage-v1",
            "sha256": COVERAGE_SHA256,
            **FROZEN_COVERAGE_TOTALS,
            "promotion_bytes": 226,
            "unknown_promotion_bytes": 226,
            "primary_overlap_bytes": 0,
            "all_promotion_bytes_unknown": True,
        }
        self.assertEqual(exporter._frozen_coverage_baseline(), expected)
        # the detector still recognises the frozen shape
        self.assertEqual(
            exporter.analyze_coverage_baseline(_frozen_ledger()), expected
        )

        # claiming even one promoted byte is an overlap and is rejected
        tampered = copy.deepcopy(_frozen_ledger())
        for segment in tampered["segments"]:
            if segment["range"] == PROMOTION_RANGES[0]:
                segment["primary_class"] = "synthetic-overlap"
                segment["primary_claim_ids"] = ["synthetic-overlap"]
                break
        with self.assertRaisesRegex(ValueError, OVERLAP_MESSAGE):
            exporter.analyze_coverage_baseline(tampered)

        # a hole inside a promotion range is rejected too
        holed = copy.deepcopy(_frozen_ledger())
        for segment in holed["segments"]:
            if segment["range"] == PROMOTION_RANGES[0]:
                segment["range"] = [0x09B494, 0x09B4C0]
                break
        with self.assertRaisesRegex(ValueError, COVERAGE_HOLE_MESSAGE):
            exporter.analyze_coverage_baseline(holed)

        # the live ledger is not the frozen state: its totals have moved on
        live = json.loads(COVERAGE.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, COVERAGE_TOTALS_MESSAGE):
            exporter.analyze_coverage_baseline(live)

        # and with the frozen totals supplied it is still rejected, because the
        # five promotion ranges are now owned by this packet's own claims
        owned = copy.deepcopy(live)
        owned["summary"].update(FROZEN_COVERAGE_TOTALS)
        with self.assertRaisesRegex(ValueError, OVERLAP_MESSAGE):
            exporter.analyze_coverage_baseline(owned)

    def test_target_branch_and_pointer_denominators_are_exact_provenance(self) -> None:
        exporter = self._implemented()
        payload, _ = self._frozen_payload()
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
        payload, _ = self._frozen_payload()
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
        payload, _ = self._frozen_payload()
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
        payload, _ = self._frozen_payload()
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
        payload, _ = self._frozen_payload()
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
        payload, _ = self._frozen_payload()
        scope = payload["scope"]
        self.assertTrue(scope["target_limited_raw_branch_denominator_complete"])
        self.assertTrue(scope["initializer_entry_proof_complete"])
        self.assertTrue(scope["target_consumer_cfg_closed"])
        self.assertTrue(scope["lookup_domain_complete_for_all_u8_inputs"])
        for key in SCOPE_FALSE_KEYS:
            self.assertFalse(scope[key], key)
        self.assertNotIn("padding_intent_proven", scope)
        self.assertNotIn("global_unreachable_proven", scope)

        # the limitations block is part of the exported contract and was not
        # asserted at all before this rewrite
        self.assertEqual(payload["limitations"], [PSG_COVERAGE_LIMITATION])
        self.assertEqual(len(payload["limitations"]), 1)

    # ------------------------------------------------------------------
    # Output handling.
    # ------------------------------------------------------------------
    def test_candidate_output_reproduces_the_accepted_artifact(self) -> None:
        """Rewritten: the exporter's *write* path still emits exactly the
        accepted payload and bundle, and the candidate manifest receipts match
        the bytes on disk.

        The original assertion ran the live write path, which today fails
        closed (see
        ``test_live_coverage_path_fails_closed_and_leaves_no_output``).  The
        write path itself is still real, so it is driven with the frozen
        coverage state and the result is compared byte for byte with the
        accepted artifact.
        """

        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=ACTIVE) as temporary:
            output = Path(temporary) / "candidate"
            with _frozen_coverage_stub(exporter):
                payload = exporter.write_artifact(ROOT, output)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME},
            )
            written_payload = (output / PAYLOAD_NAME).read_bytes()
            self.assertEqual(
                written_payload, (ARTIFACT_DIR / PAYLOAD_NAME).read_bytes()
            )
            self.assertEqual(_sha(written_payload), PAYLOAD_SHA256)
            self.assertEqual(
                (output / BUNDLE_NAME).read_bytes(),
                (ARTIFACT_DIR / BUNDLE_NAME).read_bytes(),
            )
            self.assertEqual(payload, json.loads(written_payload))

            manifest = json.loads((output / MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_status"], "candidate")
            self.assertEqual(manifest["artifact_schema"], SCHEMA)
            self.assertEqual(
                manifest["coverage_baseline"], payload["coverage_baseline"]
            )
            self.assertEqual(manifest["promotion"], payload["promotion"])
            self.assertEqual(manifest["scope"], payload["scope"])
            self.assertEqual(manifest["limitations"], payload["limitations"])
            for name, receipt in manifest["files"].items():
                with self.subTest(file=name):
                    raw = (output / name).read_bytes()
                    self.assertEqual(receipt["size"], len(raw))
                    self.assertEqual(receipt["sha256"], _sha(raw))

    def test_foreign_or_symlink_output_is_rejected_without_overwrite(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            foreign = root / "foreign"
            foreign.mkdir()
            sentinel = foreign / "keep.txt"
            sentinel.write_text("foreign\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, FOREIGN_OUTPUT_MESSAGE):
                exporter.write_artifact(ROOT, foreign)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "foreign\n")

            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, SYMLINK_OUTPUT_MESSAGE):
                exporter.write_artifact(ROOT, linked / "candidate")
            self.assertEqual(list(real.iterdir()), [])

    def test_midway_failure_leaves_no_partial_output(self) -> None:
        """A failure after the payload was built must not leave a partial
        artifact directory or a stray temporary directory behind.
        """

        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=ACTIVE) as temporary:
            parent = Path(temporary)

            # (1) the manifest step fails: nothing is created at all
            output = parent / "manifest-failure"
            with _frozen_coverage_stub(exporter), mock.patch.object(
                exporter,
                "_candidate_manifest",
                side_effect=ValueError("manifest step failed"),
            ):
                with self.assertRaisesRegex(
                    ValueError, r"^manifest step failed$"
                ):
                    exporter.write_artifact(ROOT, output)
            self.assertFalse(output.exists())
            self.assertEqual(sorted(path.name for path in parent.iterdir()), [])

            # (2) the atomic replace fails: the staging directory is removed
            output = parent / "replace-failure"
            with _frozen_coverage_stub(exporter), mock.patch.object(
                exporter.os, "replace", side_effect=OSError("replace failed")
            ):
                with self.assertRaisesRegex(OSError, r"^replace failed$"):
                    exporter.write_artifact(ROOT, output)
            self.assertFalse(output.exists())
            self.assertEqual(sorted(path.name for path in parent.iterdir()), [])

    # ------------------------------------------------------------------
    # Replay of the accepted artifact, and determinism.
    # ------------------------------------------------------------------
    def test_accepted_artifact_is_reproduced_byte_for_byte(self) -> None:
        """The frozen rebuild reproduces the accepted artifact exactly, and
        the exporter's frozen path agrees with the independent verifier.
        """

        exporter = self._implemented()
        self.assertIsNotNone(
            self.verifier,
            "independent PSG frequency lookup verifier implementation is absent",
        )
        payload, built = self.verifier.rebuild_payload(
            ROOT, validate_live_baseline=False
        )
        accepted_payload = (ARTIFACT_DIR / PAYLOAD_NAME).read_bytes()
        accepted_bundle = (ARTIFACT_DIR / BUNDLE_NAME).read_bytes()
        self.assertEqual(_canonical(payload), accepted_payload)
        self.assertEqual(_sha(_canonical(payload)), PAYLOAD_SHA256)
        self.assertEqual(built, accepted_bundle)
        self.assertEqual(_sha(built), PACKED_SHA256)
        self.assertEqual(
            _sha((ARTIFACT_DIR / MANIFEST_NAME).read_bytes()),
            ACCEPTED_MANIFEST_SHA256,
        )

        # the exporter's own frozen path agrees byte for byte
        exported, exported_bundle = self._frozen_payload()
        self.assertEqual(_canonical(exported), _canonical(payload))
        self.assertEqual(exported_bundle, built)

    def test_payload_construction_is_deterministic(self) -> None:
        """The same input must always produce the same bytes."""

        exporter = self._implemented()
        with _frozen_coverage_stub(exporter):
            first, first_bundle = exporter.build_payload(ROOT)
            second, second_bundle = exporter.build_payload(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first_bundle, second_bundle)
        # the exporter's *own* serialiser must be stable across two builds
        raw = exporter._canonical(first)
        self.assertEqual(exporter._canonical(second), raw)
        # ... and stable under a JSON round trip
        self.assertEqual(exporter._canonical(json.loads(raw)), raw)
        # an independent canonicalisation agrees with the exporter's
        self.assertEqual(_canonical(first), raw)
        # and the accepted artifact on disk is exactly that canonical form
        self.assertEqual(raw, (ARTIFACT_DIR / PAYLOAD_NAME).read_bytes())


if __name__ == "__main__":
    unittest.main()
