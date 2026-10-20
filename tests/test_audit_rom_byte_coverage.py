from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools import audit_rom_byte_coverage as coverage_auditor
from tools import verify_rom_menu_portrait_lz77_palette_alignment_gaps as menu_gap_verifier
from tools import verify_rom_tile_bg_lz77_palette_alignment_gaps as tile_bg_gap_verifier
from tools import verify_rom_boot_thumb_code_literal_alignment_gaps as boot_code_literal_gap_verifier

from tools.audit_rom_byte_coverage import (
    BATTLE_CONTROLLER_CFG_CONTROLLER_RANGE,
    BATTLE_CONTROLLER_CFG_EXCLUDED_PRODUCER_RANGES,
    BATTLE_CONTROLLER_CFG_MANIFEST_SHA256,
    BATTLE_CONTROLLER_CFG_PAYLOAD_SHA256,
    BATTLE_CONTROLLER_CFG_PAYLOAD_SIZE,
    BATTLE_CONTROLLER_CFG_PROMOTED_CODE_BYTES,
    BATTLE_CONTROLLER_CFG_PROMOTED_CODE_CLAIM_COUNT,
    BATTLE_CONTROLLER_CFG_VERIFIER,
    BATTLE_CONTROLLER_CFG_VERIFIER_SHA256,
    BATTLE_EFFECT_SPRITE_SOURCE_BATCH,
    BATTLE_EFFECT_SPRITE_SOURCE_CLASS_BYTES,
    BATTLE_EFFECT_SPRITE_SOURCE_CLASS_COUNTS,
    BATTLE_EFFECT_SPRITE_SOURCE_CLAIM_DENOMINATOR_SHA256,
    BATTLE_EFFECT_SPRITE_SOURCE_CLAIM_KIND,
    BATTLE_EFFECT_SPRITE_SOURCE_EXPECTED_BYTES,
    BATTLE_EFFECT_SPRITE_SOURCE_EXPECTED_CLAIM_COUNT,
    BATTLE_EFFECT_SPRITE_SOURCE_EXPECTED_REPORT,
    BATTLE_EFFECT_SPRITE_SOURCE_MANIFEST_SHA256,
    BATTLE_EFFECT_SPRITE_SOURCE_VERIFIER,
    BATTLE_EFFECT_SPRITE_SOURCE_VERIFIER_SHA256,
    REFERENCED_TEXT_SLOT_PADDING_BATCH,
    REFERENCED_TEXT_SLOT_PADDING_CLASS_BYTES,
    REFERENCED_TEXT_SLOT_PADDING_CLASS_COUNTS,
    REFERENCED_TEXT_SLOT_PADDING_EXPECTED_REPORT,
    REFERENCED_TEXT_SLOT_PADDING_MANIFEST_SHA256,
    REFERENCED_TEXT_SLOT_PADDING_RANGE_DENOMINATOR_SHA256,
    REFERENCED_TEXT_SLOT_PADDING_VERIFIER,
    REFERENCED_TEXT_SLOT_PADDING_VERIFIER_SHA256,
    SELECTOR_DIRECT_SOURCE_RECORDS_BATCH,
    SELECTOR_DIRECT_SOURCE_RECORDS_EXPECTED_REPORT,
    SELECTOR_DIRECT_SOURCE_RECORDS_MANIFEST_SHA256,
    SELECTOR_DIRECT_SOURCE_RECORDS_RANGE_DENOMINATOR_SHA256,
    SELECTOR_DIRECT_SOURCE_RECORDS_VERIFIER,
    SELECTOR_DIRECT_SOURCE_RECORDS_VERIFIER_SHA256,
    SELECTOR_CODE_WINDOWS_BATCH,
    SELECTOR_CODE_WINDOWS_EXPECTED_REPORT,
    SELECTOR_CODE_WINDOWS_MANIFEST_SHA256,
    SELECTOR_CODE_WINDOWS_PROMOTION_RANGE_DENOMINATOR_SHA256,
    SELECTOR_CODE_WINDOWS_VERIFIER,
    SELECTOR_CODE_WINDOWS_VERIFIER_SHA256,
    MENU_PORTRAIT_PALETTE_BATCH,
    MENU_PORTRAIT_PALETTE_EXPECTED_REPORT,
    MENU_PORTRAIT_PALETTE_MANIFEST_SHA256,
    MENU_PORTRAIT_PALETTE_RANGE_DENOMINATOR_SHA256,
    MENU_PORTRAIT_PALETTE_VERIFIER,
    MENU_PORTRAIT_PALETTE_VERIFIER_SHA256,
    SCENE_VISUAL_SOURCE_BATCH,
    SCENE_VISUAL_SOURCE_CLASS_BYTES,
    SCENE_VISUAL_SOURCE_CLASS_COUNTS,
    SCENE_VISUAL_SOURCE_EXPECTED_REPORT,
    SCENE_VISUAL_SOURCE_MANIFEST_SHA256,
    SCENE_VISUAL_SOURCE_PROMOTION_RANGE_DENOMINATOR_SHA256,
    SCENE_VISUAL_SOURCE_VERIFIER,
    SCENE_VISUAL_SOURCE_VERIFIER_SHA256,
    CUTSCENE_OBJ_SOURCE_BATCH,
    CUTSCENE_OBJ_SOURCE_CLASS_BYTES,
    CUTSCENE_OBJ_SOURCE_CLASS_COUNTS,
    CUTSCENE_OBJ_SOURCE_EXPECTED_REPORT,
    CUTSCENE_OBJ_SOURCE_MANIFEST_SHA256,
    CUTSCENE_OBJ_SOURCE_RANGE_DENOMINATOR_SHA256,
    CUTSCENE_OBJ_SOURCE_VERIFIER,
    CUTSCENE_OBJ_SOURCE_VERIFIER_SHA256,
    VERIFIED_REUSE_ARTIFACTS,
    VERIFIED_REUSE_RANGE_SPECS,
    _battle_controller_cfg_claims,
    _battle_effect_sprite_animation_source_claims,
    _bg_canvas_descriptor_claims,
    _battle_message_text_claims,
    _boot_interwork_claims,
    _boot_framebuffer_claims,
    _chapter_script_claims,
    _chapter_speaker_label_claims,
    _cfg_inventory_claims,
    _cfg_inventory_v3_claims,
    _cfg_proven_roots_claims,
    _cfg_proven_roots_v2_claims,
    _consumer_code_slice_claims,
    _dialogue_padding_claims,
    _fixed_consumer_text_claims,
    _profile_text_claims,
    _referenced_text_slot_padding_claims,
    _renderer_text_claims,
    _selector_direct_source_record_claims,
    _selector_code_window_claims,
    _menu_portrait_palette_claims,
    _scene_visual_source_range_claims,
    _cutscene_obj_source_range_claims,
    _selector_text_binding_claims,
    _sprite_definition_tile_offset_claims,
    _sprite_definition_resolved_window_claims,
    _training_text_script_claims,
    _unbound_lz77_claims,
    _value_range_text_claims,
    _verified_artifact_reuse_claims,
    atomize_claims,
    audit_manifest,
    build_manifest,
)
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v3_claims
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v4_claims
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v5_claims
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v6_claims
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v7_claims
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v8_claims
from tools.audit_rom_byte_coverage import _cfg_proven_roots_v9_claims


ROOT = Path(__file__).resolve().parents[1]

# The dependency chain below already reached the canonical ledger, so it cannot be
# projected a second time against that same ledger: the producer's own
# current-unknown gate rejects the re-projection with
# "<label> is not current unknown" (or the packet's own
# "<label> are not current unknown").  Every quick-projection test that rebuilds
# one of these packets must therefore start from a baseline with the rebuilt
# batches removed and re-project them in the original chain order.
REPROJECTED_PACKET_CHAIN = (
    ("rom-text-bg-loop-continuation-v1", "_text_bg_loop_continuation_claims"),
    ("rom-boot-copy-sources-v1", "_boot_copy_source_claims"),
    ("rom-text-bg-task-closure-v1", "_text_bg_task_closure_claims"),
    ("rom-fixed-renderer-script-records-v1", "_fixed_renderer_script_record_claims"),
)


def _reproject_chain(
    coverage: dict, rom: bytes, upto: int, excluded: tuple[str, ...] = ()
) -> list[dict]:
    """Rebuild the first `upto` packets of the already-promoted chain.

    `coverage["claims"]` is the canonical ledger.  The first `upto` chain packets
    are removed from it and re-projected in the original order, so the returned
    claim list covers exactly the same bytes as the ledger does, while the
    individual producers can run their own current-unknown gate again.

    `excluded` names additional batches that must be dropped from the baseline
    *without* being re-projected.  A packet that the caller projects itself
    still lives in the canonical ledger, so leaving it in the baseline would
    make the producer's current-unknown gate reject the caller's own
    projection.
    """
    rebuilt_batches = {batch for batch, _ in REPROJECTED_PACKET_CHAIN[:upto]}
    dropped_batches = rebuilt_batches | set(excluded)
    claims = [
        claim
        for claim in coverage["claims"]
        if claim.get("promotion_batch") not in dropped_batches
    ]
    for _, helper_name in REPROJECTED_PACKET_CHAIN[:upto]:
        claims = [
            *claims,
            *getattr(coverage_auditor, helper_name)(ROOT, rom, claims),
        ]
    return claims


def _reproject_chain_baseline(coverage: dict, upto: int) -> list[dict]:
    """Canonical ledger minus the first `upto` chain packets (not re-projected)."""
    rebuilt_batches = {batch for batch, _ in REPROJECTED_PACKET_CHAIN[:upto]}
    return [
        claim
        for claim in coverage["claims"]
        if claim.get("promotion_batch") not in rebuilt_batches
    ]


def _window_tiles(claims: list[dict], segments: list[dict], start: int, end: int):
    """Return (tiles, owner) for the window [start, end).

    `tiles` is the ordered list of ``(begin, stop, primary_class)`` pieces the
    segment table lays over the window; `owner` maps every byte of the window
    to the ``(primary_class, promotion_batch)`` of the primary claim that owns
    it, or to ``("unknown", None)`` when no primary claim owns it.

    The segment table is the byte-wise projection of the primary claim table,
    so comparing the two is a stronger contract than pinning a frozen interval
    key: a later batch may legitimately subdivide an interval that was unknown
    when the contract was written, and a frozen key would then fail on a
    ledger that is still correct.
    """
    owner: dict[int, tuple[str, str | None]] = {}
    for claim in claims:
        if claim.get("role") != "primary":
            continue
        claim_start, claim_end = claim["range"]
        if claim_end <= start or claim_start >= end:
            continue
        for offset in range(max(claim_start, start), min(claim_end, end)):
            owner[offset] = (claim["primary_class"], claim.get("promotion_batch"))
    for offset in range(start, end):
        owner.setdefault(offset, ("unknown", None))
    tiles: list[tuple[int, int, str]] = []
    for piece in segments:
        piece_start, piece_end = piece["range"]
        if piece_end <= start or piece_start >= end:
            continue
        tiles.append(
            (max(piece_start, start), min(piece_end, end), piece["primary_class"])
        )
    tiles.sort()
    return tiles, owner


def _ledger_window_tiles(manifest: dict, start: int, end: int):
    """`_window_tiles` over the committed ledger."""
    return _window_tiles(manifest["claims"], manifest["segments"], start, end)


def _expected_cfg_registry_sha256(claims: list[dict]) -> str:
    """Recompute the bounded-CFG code-kind denominator digest from the live registry.

    The digest hashes the auditor's frozen code-kind registry plus the staged
    kinds that the input actually observes.  Pinning one literal digest froze the
    registry version, so a new registered kind invalidated the assertion even
    though nothing about the exclusion contract changed; the digest therefore has
    to be derived from the live registry instead of hard-coded.
    """

    def _has_semantic_token(claim: dict, token: str) -> bool:
        return any(
            token in str(claim.get(field, "")).lower().split("_")
            for field in ("claim_kind", "primary_class")
        )

    observed_code_like_kinds = {
        str(claim.get("claim_kind"))
        for claim in claims
        if claim.get("role") == "primary"
        and (
            _has_semantic_token(claim, "code")
            or _has_semantic_token(claim, "instruction")
        )
    }
    active_staged_thumb_kinds = sorted(
        set(coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])
        & observed_code_like_kinds
    )
    return hashlib.sha256(
        json.dumps(
            {
                "stable": coverage_auditor.CFG_CODE_KIND_REGISTRY,
                "active_staged_thumb_only": active_staged_thumb_kinds,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class RomByteCoverageWritePathTests(unittest.TestCase):
    def test_write_mode_builds_once_and_verifies_the_exact_readback(self):
        manifest = {
            "schema": "rom-byte-coverage-v1",
            "state_inventory_complete": True,
            "semantic_classification_complete": False,
            "summary": {"classified_bytes": 5, "unknown_bytes": 1},
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "coverage.json"
            with mock.patch.object(
                coverage_auditor, "build_manifest", return_value=manifest
            ) as build, mock.patch.object(
                coverage_auditor,
                "audit_manifest",
                side_effect=AssertionError("write mode rebuilt the manifest"),
            ) as audit, mock.patch("builtins.print") as emit:
                exit_code = coverage_auditor.main(
                    [
                        "--root",
                        str(ROOT),
                        "--manifest",
                        str(output),
                        "--write",
                    ]
                )

            self.assertEqual(0, exit_code)
            build.assert_called_once_with(ROOT)
            audit.assert_not_called()
            self.assertEqual(manifest, json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(["coverage.json"], [path.name for path in Path(directory).iterdir()])
            report = json.loads(emit.call_args.args[0])
            self.assertTrue(report["verified"])
            self.assertEqual(manifest["summary"], report["summary"])


class RomByteCoverageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository_manifest = build_manifest(ROOT)

    def test_atomizes_primary_and_secondary_claims_without_hiding_unknown_bytes(self):
        segments = atomize_claims(
            6,
            [
                {
                    "id": "table",
                    "range": [1, 3],
                    "role": "primary",
                    "primary_class": "fixed_table",
                },
                {
                    "id": "resource",
                    "range": [3, 5],
                    "role": "primary",
                    "primary_class": "lz77_resource",
                },
                {
                    "id": "consumer",
                    "range": [2, 4],
                    "role": "secondary",
                    "claim_kind": "consumer_window",
                },
            ],
        )

        self.assertEqual(
            [
                {
                    "range": [0, 1],
                    "primary_class": "unknown",
                    "primary_claim_ids": [],
                    "secondary_claim_ids": [],
                    "unknown_reason": "no accepted primary classification claim",
                },
                {
                    "range": [1, 2],
                    "primary_class": "fixed_table",
                    "primary_claim_ids": ["table"],
                    "secondary_claim_ids": [],
                },
                {
                    "range": [2, 3],
                    "primary_class": "fixed_table",
                    "primary_claim_ids": ["table"],
                    "secondary_claim_ids": ["consumer"],
                },
                {
                    "range": [3, 4],
                    "primary_class": "lz77_resource",
                    "primary_claim_ids": ["resource"],
                    "secondary_claim_ids": ["consumer"],
                },
                {
                    "range": [4, 5],
                    "primary_class": "lz77_resource",
                    "primary_claim_ids": ["resource"],
                    "secondary_claim_ids": [],
                },
                {
                    "range": [5, 6],
                    "primary_class": "unknown",
                    "primary_claim_ids": [],
                    "secondary_claim_ids": [],
                    "unknown_reason": "no accepted primary classification claim",
                },
            ],
            segments,
        )

    def test_rejects_overlapping_primary_classifications(self):
        with self.assertRaisesRegex(ValueError, "conflicting primary claims"):
            atomize_claims(
                4,
                [
                    {
                        "id": "a",
                        "range": [0, 3],
                        "role": "primary",
                        "primary_class": "fixed_table",
                    },
                    {
                        "id": "b",
                        "range": [2, 4],
                        "role": "primary",
                        "primary_class": "lz77_resource",
                    },
                ],
            )

    def test_repository_manifest_accounts_for_every_byte_but_is_not_semantically_complete(self):
        manifest = self.repository_manifest
        summary = manifest["summary"]

        self.assertEqual(6_291_456, summary["rom_bytes"])
        self.assertEqual(132_116, summary["padding_ff_bytes"])
        self.assertEqual(1_733_430, summary["pointer_reachable_lz77_bytes"])
        self.assertEqual(648, summary["lz77_alignment_padding_bytes"])
        self.assertEqual(341, summary["lz77_alignment_padding_claim_count"])
        self.assertEqual(14_725, summary["unbound_lz77_syntax_bytes"])
        self.assertEqual(41, summary["unbound_lz77_syntax_claim_count"])
        self.assertEqual(956, summary["cfg_reachable_arm_code_bytes"])
        self.assertGreaterEqual(summary["cfg_reachable_thumb_code_bytes"], 153_466)
        self.assertGreaterEqual(summary["cfg_promoted_unknown_bytes"], 154_454)
        self.assertGreaterEqual(summary["cfg_primary_claim_count"], 3_878)
        self.assertGreaterEqual(summary["cfg_code_claim_kind_count"], 35)
        self.assertEqual(
            _expected_cfg_registry_sha256(manifest["claims"]),
            summary["cfg_code_claim_kind_denominator_sha256"],
        )
        self.assertEqual(9_060, summary["cfg_v3_extension_code_bytes"])
        self.assertEqual(113, summary["cfg_v3_extension_code_claim_count"])
        self.assertEqual(448, summary["cfg_v3_dispatch_table_bytes"])
        self.assertEqual(112, summary["cfg_v3_dispatch_table_claim_count"])
        self.assertEqual(
            32, summary["cfg_v3_sparse_dispatch_masked_residual_bytes"]
        )
        self.assertEqual(
            8, summary["cfg_v3_sparse_dispatch_masked_residual_claim_count"]
        )
        self.assertEqual(
            "f12097bd30174bd08f177f083fd886995edbdfc05de91c178b2d5ee96a65f9a5",
            summary[
                "cfg_v3_sparse_dispatch_masked_residual_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            12_946, summary["cfg_proven_roots_extension_code_bytes"]
        )
        self.assertEqual(
            116, summary["cfg_proven_roots_extension_code_claim_count"]
        )
        self.assertEqual(12, summary["cfg_proven_roots_producer_code_bytes"])
        self.assertEqual(3, summary["cfg_proven_roots_producer_claim_count"])
        self.assertEqual(
            9_876, summary["cfg_proven_roots_v2_extension_code_bytes"]
        )
        self.assertEqual(
            86, summary["cfg_proven_roots_v2_extension_code_claim_count"]
        )
        self.assertEqual(20, summary["cfg_proven_roots_v2_producer_code_bytes"])
        self.assertEqual(5, summary["cfg_proven_roots_v2_producer_claim_count"])
        self.assertEqual(
            110, summary["cfg_proven_roots_v3_extension_code_bytes"]
        )
        self.assertEqual(
            8, summary["cfg_proven_roots_v3_extension_code_claim_count"]
        )
        self.assertEqual(
            1_044, summary["cfg_proven_roots_v4_extension_code_bytes"]
        )
        self.assertEqual(
            118, summary["cfg_proven_roots_v4_extension_code_claim_count"]
        )
        self.assertEqual(1_252, summary["cfg_proven_roots_v5_extension_code_bytes"])
        self.assertEqual(124, summary["cfg_proven_roots_v5_extension_code_claim_count"])
        self.assertEqual(25_926, summary["cfg_proven_roots_v6_extension_code_bytes"])
        self.assertEqual(2_212, summary["cfg_proven_roots_v6_extension_code_claim_count"])
        self.assertEqual(332, summary["cfg_proven_roots_v7_extension_code_bytes"])
        self.assertEqual(38, summary["cfg_proven_roots_v7_extension_code_claim_count"])
        self.assertEqual(
            36, summary["cfg_proven_roots_v7_dispatch_table_bytes"]
        )
        self.assertEqual(
            9, summary["cfg_proven_roots_v7_dispatch_table_claim_count"]
        )
        self.assertEqual(
            "f01bf5984428f386feeed6b009913a5775ee6f23d41101a3ea423fb4047c6e9d",
            summary[
                "cfg_proven_roots_v7_dispatch_table_range_denominator_sha256"
            ],
        )
        self.assertEqual(246, summary["cfg_proven_roots_v8_extension_code_bytes"])
        self.assertEqual(20, summary["cfg_proven_roots_v8_extension_code_claim_count"])
        self.assertEqual(628, summary["cfg_proven_roots_v9_extension_code_bytes"])
        self.assertEqual(62, summary["cfg_proven_roots_v9_extension_code_claim_count"])
        self.assertEqual(72, summary["cfg_proven_roots_v10_extension_code_bytes"])
        self.assertEqual(7, summary["cfg_proven_roots_v10_extension_code_claim_count"])
        self.assertEqual(8, summary["cfg_proven_roots_v10_consumed_literal_bytes"])
        self.assertEqual(2, summary["cfg_proven_roots_v10_consumed_literal_claim_count"])
        self.assertEqual(80, summary["cfg_proven_roots_v10_promotion_bytes"])
        self.assertEqual(9, summary["cfg_proven_roots_v10_promotion_claim_count"])
        self.assertEqual(62, summary["cfg_proven_roots_v11_extension_code_bytes"])
        self.assertEqual(
            6, summary["cfg_proven_roots_v11_extension_code_claim_count"]
        )
        self.assertEqual(62, summary["cfg_proven_roots_v11_promotion_bytes"])
        self.assertEqual(6, summary["cfg_proven_roots_v11_promotion_claim_count"])
        self.assertEqual(372, summary["cfg_proven_roots_v12_extension_code_bytes"])
        self.assertEqual(
            4, summary["cfg_proven_roots_v12_extension_code_claim_count"]
        )
        self.assertEqual(
            128, summary["cfg_proven_roots_v12_consumed_literal_bytes"]
        )
        self.assertEqual(
            4, summary["cfg_proven_roots_v12_consumed_literal_claim_count"]
        )
        self.assertEqual(500, summary["cfg_proven_roots_v12_promotion_bytes"])
        self.assertEqual(8, summary["cfg_proven_roots_v12_promotion_claim_count"])
        self.assertEqual(4, summary["cfg_proven_roots_v12_unclassified_hole_bytes"])
        self.assertEqual(312, summary["cfg_proven_roots_v13_extension_code_bytes"])
        self.assertEqual(
            3, summary["cfg_proven_roots_v13_extension_code_claim_count"]
        )
        self.assertEqual(
            80, summary["cfg_proven_roots_v13_consumed_literal_bytes"]
        )
        self.assertEqual(
            3, summary["cfg_proven_roots_v13_consumed_literal_claim_count"]
        )
        self.assertEqual(392, summary["cfg_proven_roots_v13_promotion_bytes"])
        self.assertEqual(6, summary["cfg_proven_roots_v13_promotion_claim_count"])
        self.assertEqual(4, summary["cfg_proven_roots_v13_unclassified_hole_bytes"])
        v13_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("promotion_batch") == "cfg-proven-roots-v13"
        ]
        self.assertEqual(
            [
                [0x0651F8, 0x06523C],
                [0x06523C, 0x06524C],
                [0x06524C, 0x0652DE],
                [0x0652E0, 0x065308],
                [0x065308, 0x06536A],
                [0x06536C, 0x065384],
            ],
            [claim["range"] for claim in v13_claims],
        )
        for hole in ([0x0652DE, 0x0652E0], [0x06536A, 0x06536C]):
            self.assertIn(
                {
                    "range": hole,
                    "primary_class": "unknown",
                    "primary_claim_ids": [],
                    "secondary_claim_ids": [],
                    "unknown_reason": "no accepted primary classification claim",
                },
                manifest["segments"],
            )
        self.assertTrue(
            any(
                "one-generation 29-dispatch extension" in limitation
                and "328 baseline" in limitation
                and "15 newly discovered indirect frontiers" in limitation
                for limitation in manifest["limitations"]
            )
        )
        self.assertEqual(348_018, summary["fixed_table_bytes"])
        self.assertEqual(2_023_076, summary["character_battle_visual_bytes"])
        self.assertEqual(1_299, summary["character_battle_visual_claim_count"])
        self.assertEqual(887_018, summary["m4a_audio_bytes"])
        self.assertEqual(842, summary["m4a_audio_claim_count"])
        self.assertEqual(144_416, summary["dialogue_font_bytes"])
        self.assertEqual(30, summary["dialogue_font_claim_count"])
        self.assertEqual(2_848, summary["dialogue_font_source_padding_bytes"])
        self.assertEqual(19, summary["dialogue_font_source_padding_claim_count"])
        self.assertEqual(155_188, summary["boot_framebuffer_bytes"])
        self.assertEqual(14, summary["boot_framebuffer_claim_count"])
        self.assertEqual(96, summary["direct_cpuset_palette_bytes"])
        self.assertEqual(3, summary["direct_cpuset_palette_claim_count"])
        self.assertEqual(6_100, summary["dialogue_pointer_table_bytes"])
        self.assertEqual(1, summary["dialogue_pointer_table_claim_count"])
        self.assertEqual(18_207, summary["dialogue_encoded_text_bytes"])
        self.assertEqual(1_220, summary["dialogue_encoded_text_claim_count"])
        self.assertEqual(
            16_814, summary["dialogue_inter_record_zero_padding_bytes"]
        )
        self.assertEqual(
            1_219, summary["dialogue_inter_record_zero_padding_claim_count"]
        )
        self.assertEqual(1_148, summary["battle_presentation_message_bytes"])
        self.assertEqual(79, summary["battle_presentation_message_claim_count"])
        self.assertEqual(1_293, summary["battle_presentation_text_padding_bytes"])
        self.assertEqual(78, summary["battle_presentation_text_padding_claim_count"])
        self.assertEqual(1_794, summary["battle_presentation_table_bytes"])
        self.assertEqual(3, summary["battle_presentation_table_claim_count"])
        self.assertEqual(32, summary["battle_presentation_palette_bytes"])
        self.assertEqual(1, summary["battle_presentation_palette_claim_count"])
        self.assertEqual(6_304, summary["candidate_adjudication_bytes"])
        self.assertEqual(55, summary["candidate_adjudication_claim_count"])
        self.assertEqual(9_984, summary["tile_bg_palette_bytes"])
        self.assertEqual(107, summary["tile_bg_palette_claim_count"])
        self.assertEqual(27_404, summary["consumer_code_slice_bytes"])
        self.assertEqual(116, summary["consumer_code_slice_claim_count"])
        self.assertEqual(164, summary["profile_selector_code_slice_bytes"])
        self.assertEqual(2, summary["profile_selector_code_slice_claim_count"])
        self.assertEqual(64, summary["chapter_selector_code_slice_bytes"])
        self.assertEqual(1, summary["chapter_selector_code_slice_claim_count"])
        self.assertEqual(36, summary["sprite_loader_tail_bytes"])
        self.assertEqual(1, summary["sprite_loader_tail_claim_count"])
        self.assertEqual(1_856, summary["battle_status_bar_caller_slice_bytes"])
        self.assertEqual(1, summary["battle_status_bar_caller_slice_claim_count"])
        self.assertEqual(224, summary["bg_canvas_descriptor_bytes"])
        self.assertEqual(1, summary["bg_canvas_descriptor_claim_count"])
        self.assertEqual(334_060, summary["chapter_script_bytes"])
        self.assertEqual(92, summary["chapter_script_claim_count"])
        self.assertEqual(86, summary["sprite_tile_offset_table_bytes"])
        self.assertEqual(1, summary["sprite_tile_offset_table_claim_count"])
        self.assertEqual(1_720, summary["sprite_definition_resolved_window_bytes"])
        self.assertEqual(3, summary["sprite_definition_resolved_window_claim_count"])
        self.assertEqual(251, summary["chapter_speaker_label_bytes"])
        self.assertEqual(49, summary["chapter_speaker_label_claim_count"])
        self.assertEqual(22_588, summary["renderer_text_bytes"])
        self.assertEqual(625, summary["renderer_text_claim_count"])
        self.assertEqual(12_431, summary["renderer_text_zero_padding_bytes"])
        self.assertEqual(548, summary["renderer_text_zero_padding_claim_count"])
        self.assertEqual(6_798, summary["profile_text_bytes"])
        self.assertEqual(46, summary["profile_text_claim_count"])
        self.assertEqual(38, summary["profile_text_alignment_padding_bytes"])
        self.assertEqual(
            19, summary["profile_text_alignment_padding_claim_count"]
        )
        self.assertEqual(3_000, summary["fixed_consumer_pointer_table_bytes"])
        self.assertEqual(
            11, summary["fixed_consumer_pointer_table_claim_count"]
        )
        self.assertEqual(11_177, summary["fixed_consumer_renderer_text_bytes"])
        self.assertEqual(
            735, summary["fixed_consumer_renderer_text_claim_count"]
        )
        self.assertEqual(
            6_738, summary["fixed_consumer_text_zero_padding_bytes"]
        )
        self.assertEqual(
            590, summary["fixed_consumer_text_zero_padding_claim_count"]
        )
        self.assertEqual(
            "rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1",
            summary[
                "dialogue_font_sjis_empty_lookup_rows_promotion_batch"
            ],
        )
        self.assertEqual(
            "dialogue_font_sjis_empty_lookup_row_bytes",
            summary["dialogue_font_sjis_empty_lookup_rows_claim_kind"],
        )
        self.assertEqual(
            40, summary["dialogue_font_sjis_empty_lookup_rows_bytes"]
        )
        self.assertEqual(
            1, summary["dialogue_font_sjis_empty_lookup_rows_claim_count"]
        )
        self.assertEqual(
            "000c60331b7d3e7da1c3597ac8ef3578b5f99a4cc24c811b5be5b38a079a676f",
            summary[
                "dialogue_font_sjis_empty_lookup_rows_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "2c34ce1df23b838c5abf2a7f6437cca3d3067ed509ff25f11df6b11b582b51eb",
            summary[
                "dialogue_font_sjis_empty_lookup_rows_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1",
            summary[
                "dialogue_font_sjis_empty_lookup_rows_full_table_sha256"
            ],
        )
        self.assertEqual(
            "rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1",
            summary["motion_spawn_sequence_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "motion_spawn_sequence_descriptor_alignment_gap_bytes",
            summary["motion_spawn_sequence_alignment_gap_claim_kind"],
        )
        self.assertEqual(2, summary["motion_spawn_sequence_alignment_gap_bytes"])
        self.assertEqual(
            1, summary["motion_spawn_sequence_alignment_gap_claim_count"]
        )
        self.assertEqual(
            "6646067a0bc46bcc6c2fde5aa94299022ac51d7454b946048e51d929b0a58d03",
            summary[
                "motion_spawn_sequence_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d",
            summary["motion_spawn_sequence_alignment_gap_motion_table_sha256"],
        )
        self.assertEqual(
            "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f",
            summary["motion_spawn_sequence_alignment_gap_sequence_table_sha256"],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            summary["motion_spawn_sequence_alignment_gap_packed_bytes_sha256"],
        )
        self.assertEqual(
            "rom-battle-presentation-tile-assets-alignment-gap-coverage-v1",
            summary[
                "battle_presentation_tile_assets_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "battle_presentation_tile_assets_alignment_gap_bytes",
            summary["battle_presentation_tile_assets_alignment_gap_claim_kind"],
        )
        self.assertEqual(
            2, summary["battle_presentation_tile_assets_alignment_gap_bytes"]
        )
        self.assertEqual(
            1,
            summary[
                "battle_presentation_tile_assets_alignment_gap_claim_count"
            ],
        )
        self.assertEqual(
            "7649610dfb23720aa7a052893bf3fec739e423ddc826720e9cfa8529bea1882c",
            summary[
                "battle_presentation_tile_assets_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8",
            summary[
                "battle_presentation_tile_assets_alignment_gap_binding_table_sha256"
            ],
        )
        self.assertEqual(
            "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73",
            summary[
                "battle_presentation_tile_assets_alignment_gap_tile_assets_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            summary[
                "battle_presentation_tile_assets_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(
            "rom-runtime-state-handler-table-alignment-gap-coverage-v1",
            summary[
                "runtime_state_handler_table_alignment_gap_promotion_batch"
            ],
        )
        self.assertEqual(
            "runtime_state_handler_table_alignment_gap_bytes",
            summary["runtime_state_handler_table_alignment_gap_claim_kind"],
        )
        self.assertEqual(
            2, summary["runtime_state_handler_table_alignment_gap_bytes"]
        )
        self.assertEqual(
            1, summary["runtime_state_handler_table_alignment_gap_claim_count"]
        )
        self.assertEqual(
            "11a9249d8cf1654cfbfa44bf13fa9fafc94677f7f1b075b892319e5e524f275c",
            summary[
                "runtime_state_handler_table_alignment_gap_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b",
            summary[
                "runtime_state_handler_table_alignment_gap_selector_table_sha256"
            ],
        )
        self.assertEqual(
            "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945",
            summary[
                "runtime_state_handler_table_alignment_gap_handler_table_sha256"
            ],
        )
        self.assertEqual(
            "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            summary[
                "runtime_state_handler_table_alignment_gap_packed_bytes_sha256"
            ],
        )
        self.assertEqual(2_505, summary["training_text_script_bytes"])
        self.assertEqual(44, summary["training_text_script_claim_count"])
        self.assertEqual(152, summary["value_range_text_map_bytes"])
        self.assertEqual(1, summary["value_range_text_map_claim_count"])
        self.assertEqual(862, summary["value_range_renderer_text_bytes"])
        self.assertEqual(38, summary["value_range_renderer_text_claim_count"])
        self.assertEqual(324, summary["selector_direct_text_bytes"])
        self.assertEqual(46, summary["selector_direct_text_claim_count"])
        self.assertEqual(316, summary["selector_configured_text_bytes"])
        self.assertEqual(38, summary["selector_configured_text_claim_count"])
        self.assertEqual(164, summary["selector_configuration_list_bytes"])
        self.assertEqual(1, summary["selector_configuration_list_claim_count"])
        self.assertEqual(12, summary["selector_configuration_pointer_bytes"])
        self.assertEqual(1, summary["selector_configuration_pointer_claim_count"])
        self.assertEqual(1_411, summary["battle_message_renderer_text_bytes"])
        self.assertEqual(79, summary["battle_message_renderer_text_claim_count"])
        self.assertEqual(1_329, summary["battle_message_zero_padding_bytes"])
        self.assertEqual(79, summary["battle_message_zero_padding_claim_count"])
        self.assertEqual(372, summary["boot_interwork_arm_code_bytes"])
        self.assertEqual(2, summary["boot_interwork_arm_code_claim_count"])
        self.assertEqual(6, summary["boot_interwork_thumb_code_bytes"])
        self.assertEqual(2, summary["boot_interwork_thumb_code_claim_count"])
        self.assertEqual(36, summary["boot_interwork_literal_pool_bytes"])
        self.assertEqual(1, summary["boot_interwork_literal_pool_claim_count"])
        self.assertEqual(3_919, summary["verified_artifact_reuse_bytes"])
        self.assertEqual(37, summary["verified_artifact_reuse_claim_count"])
        self.assertEqual(11_120, summary["battle_effect_sprite_source_bytes"])
        self.assertEqual(
            237, summary["battle_effect_sprite_source_claim_count"]
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_CLASS_BYTES,
            summary["battle_effect_sprite_source_class_bytes"],
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_CLASS_COUNTS,
            summary["battle_effect_sprite_source_class_claim_counts"],
        )
        self.assertEqual(550, summary["selector_direct_text_slot_padding_bytes"])
        self.assertEqual(46, summary["selector_direct_text_slot_padding_claim_count"])
        self.assertEqual(368, summary["selector_configured_text_slot_padding_bytes"])
        self.assertEqual(38, summary["selector_configured_text_slot_padding_claim_count"])
        self.assertEqual(337, summary["chapter_speaker_label_slot_padding_bytes"])
        self.assertEqual(49, summary["chapter_speaker_label_slot_padding_claim_count"])
        self.assertEqual(1_255, summary["referenced_text_slot_padding_bytes"])
        self.assertEqual(133, summary["referenced_text_slot_padding_claim_count"])
        self.assertEqual(
            REFERENCED_TEXT_SLOT_PADDING_RANGE_DENOMINATOR_SHA256,
            summary["referenced_text_slot_padding_range_denominator_sha256"],
        )
        self.assertEqual(
            SELECTOR_DIRECT_SOURCE_RECORDS_BATCH,
            summary["selector_direct_source_record_promotion_batch"],
        )
        self.assertEqual(920, summary["selector_direct_source_record_bytes"])
        self.assertEqual(46, summary["selector_direct_source_record_claim_count"])
        self.assertEqual(
            SELECTOR_DIRECT_SOURCE_RECORDS_RANGE_DENOMINATOR_SHA256,
            summary["selector_direct_source_record_range_denominator_sha256"],
        )
        self.assertEqual(
            SELECTOR_CODE_WINDOWS_BATCH,
            summary["selector_code_window_promotion_batch"],
        )
        self.assertEqual(
            "consumer_code_slice", summary["selector_code_window_claim_kind"]
        )
        self.assertEqual(1_252, summary["selector_code_window_bytes"])
        self.assertEqual(19, summary["selector_code_window_claim_count"])
        self.assertEqual(
            SELECTOR_CODE_WINDOWS_PROMOTION_RANGE_DENOMINATOR_SHA256,
            summary["selector_code_window_range_denominator_sha256"],
        )
        self.assertEqual(
            MENU_PORTRAIT_PALETTE_BATCH,
            summary["menu_portrait_palette_promotion_batch"],
        )
        self.assertEqual(
            "menu_portrait_palette_source_range",
            summary["menu_portrait_palette_claim_kind"],
        )
        self.assertEqual(8_960, summary["menu_portrait_palette_bytes"])
        self.assertEqual(70, summary["menu_portrait_palette_claim_count"])
        self.assertEqual(
            MENU_PORTRAIT_PALETTE_RANGE_DENOMINATOR_SHA256,
            summary["menu_portrait_palette_range_denominator_sha256"],
        )
        self.assertEqual(
            SCENE_VISUAL_SOURCE_BATCH,
            summary["scene_visual_source_promotion_batch"],
        )
        self.assertEqual(
            "scene_visual_source_range",
            summary["scene_visual_source_claim_kind"],
        )
        self.assertEqual(3_257, summary["scene_visual_source_bytes"])
        self.assertEqual(29, summary["scene_visual_source_claim_count"])
        self.assertEqual(
            SCENE_VISUAL_SOURCE_CLASS_BYTES,
            summary["scene_visual_source_class_bytes"],
        )
        self.assertEqual(
            SCENE_VISUAL_SOURCE_CLASS_COUNTS,
            summary["scene_visual_source_class_claim_counts"],
        )
        self.assertEqual(
            SCENE_VISUAL_SOURCE_PROMOTION_RANGE_DENOMINATOR_SHA256,
            summary["scene_visual_source_range_denominator_sha256"],
        )
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_BATCH,
            summary["cutscene_obj_source_promotion_batch"],
        )
        self.assertEqual(
            "cutscene_obj_source_range",
            summary["cutscene_obj_source_claim_kind"],
        )
        self.assertEqual(400, summary["cutscene_obj_source_bytes"])
        self.assertEqual(28, summary["cutscene_obj_source_claim_count"])
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_CLASS_BYTES,
            summary["cutscene_obj_source_class_bytes"],
        )
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_CLASS_COUNTS,
            summary["cutscene_obj_source_class_claim_counts"],
        )
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_RANGE_DENOMINATOR_SHA256,
            summary["cutscene_obj_source_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-positions-aux-dispatch-v1",
            summary["positions_aux_dispatch_promotion_batch"],
        )
        self.assertEqual(
            "positions_aux_dispatch_cell_table_bytes",
            summary["positions_aux_dispatch_claim_kind"],
        )
        self.assertEqual(9_216, summary["positions_aux_dispatch_bytes"])
        self.assertEqual(144, summary["positions_aux_dispatch_claim_count"])
        self.assertEqual(
            "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68",
            summary["positions_aux_dispatch_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1",
            summary["cutscene_obj_alignment_gap_promotion_batch"],
        )
        self.assertEqual(
            "cutscene_obj_palette_definition_alignment_gap_bytes",
            summary["cutscene_obj_alignment_gap_claim_kind"],
        )
        self.assertEqual(8, summary["cutscene_obj_alignment_gap_bytes"])
        self.assertEqual(4, summary["cutscene_obj_alignment_gap_claim_count"])
        self.assertEqual(
            "dae7c87fa52a1e1e9f1a72279fc7839d8f26f07b126e80aca07450286abcc137",
            summary["cutscene_obj_alignment_gap_claim_denominator_sha256"],
        )
        self.assertEqual(
            "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6",
            summary["cutscene_obj_alignment_gap_range_vector_sha256"],
        )
        self.assertEqual(
            "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc",
            summary["cutscene_obj_alignment_gap_packed_bytes_sha256"],
        )
        self.assertEqual(
            "c89ed50357f1497139aa81bc29e4b67c5947608c640fc572f0ff66ed01dd8f41",
            summary[
                "cutscene_obj_alignment_gap_independent_verifier_report_sha256"
            ],
        )
        self.assertEqual(
            "rom-parser-bound-zero-padding-v1",
            summary["parser_bound_zero_padding_promotion_batch"],
        )
        self.assertEqual(198, summary["parser_bound_zero_padding_bytes"])
        self.assertEqual(
            142, summary["parser_bound_zero_padding_claim_count"]
        )
        self.assertEqual(
            {
                "chapter_terminal_to_fixed_root_zero_padding": 85,
                "m4a_wave_alignment_zero_padding": 113,
            },
            summary["parser_bound_zero_padding_class_bytes"],
        )
        self.assertEqual(
            {
                "chapter_terminal_to_fixed_root_zero_padding": 85,
                "m4a_wave_alignment_zero_padding": 57,
            },
            summary["parser_bound_zero_padding_class_claim_counts"],
        )
        self.assertEqual(
            "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1",
            summary["parser_bound_zero_padding_range_denominator_sha256"],
        )
        self.assertEqual(
            "rom-direct-cpuset-bound-palette-coverage-v1",
            summary["direct_cpuset_bound_palette_promotion_batch"],
        )
        self.assertEqual(
            "direct_cpuset_bound_palette_source_range",
            summary["direct_cpuset_bound_palette_claim_kind"],
        )
        self.assertEqual(192, summary["direct_cpuset_bound_palette_bytes"])
        self.assertEqual(6, summary["direct_cpuset_bound_palette_claim_count"])
        self.assertEqual(12, summary["direct_cpuset_bound_palette_candidate_count"])
        self.assertEqual(6, summary["direct_cpuset_bound_palette_preowned_count"])
        self.assertEqual(
            "37ea9a17c34454a25866f790eb26b72d4b40b7a7a663b7f15366a6e3ad7fcf1f",
            summary["direct_cpuset_bound_palette_range_denominator_sha256"],
        )
        self.assertEqual(
            "2381d20aeadf065b45306538b729c5b5ceecf41edcb4bbd6f3c40070a495607e",
            summary["direct_cpuset_bound_palette_candidate_denominator_sha256"],
        )
        self.assertEqual(
            "4a03b75179c008e012ed89e2b571f052bd326a22cc2f1c5ae8fd82b073348225",
            summary["direct_cpuset_bound_palette_preowned_denominator_sha256"],
        )
        self.assertEqual(
            "056a3625cc3a6735e56921aaec6ee37e646380bf31040cb6ad63fa8dbe757b70",
            summary["direct_cpuset_bound_palette_packed_bytes_sha256"],
        )
        self.assertEqual(
            "rom-boot-interwork-padding-coverage-v1",
            summary["boot_interwork_padding_promotion_batch"],
        )
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop_bytes",
            summary["boot_interwork_padding_claim_kind"],
        )
        self.assertEqual(2, summary["boot_interwork_padding_bytes"])
        self.assertEqual(1, summary["boot_interwork_padding_claim_count"])
        self.assertEqual(
            "639f595e03eb779de859b21c42fb77388cd5a93c26be5514b7c1f700fe1d09b9",
            summary["boot_interwork_padding_range_denominator_sha256"],
        )
        self.assertEqual(
            "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676",
            summary["boot_interwork_padding_packed_bytes_sha256"],
        )
        self.assertGreaterEqual(summary["classified_bytes"], 6_151_436)
        self.assertLessEqual(summary["unknown_bytes"], 140_020)
        self.assertGreaterEqual(summary["claim_count"], 16_061)
        self.assertGreaterEqual(summary["segment_count"], 17_483)
        self.assertEqual(summary["rom_bytes"], summary["accounted_bytes"])
        self.assertTrue(manifest["state_inventory_complete"])
        self.assertFalse(manifest["semantic_classification_complete"])

        visual_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "character_battle_visual_source_range"
        ]
        self.assertEqual(1_299, len(visual_claims))
        self.assertEqual(
            {
                "animation_pointer_table": 250,
                "component_region": 250,
                "descriptor_table": 1,
                "frame_pointer_table": 250,
                "graphics": 250,
                "palette": 48,
                "timeline_region": 250,
            },
            {
                source_kind: sum(
                    claim["source_kind"] == source_kind
                    for claim in visual_claims
                )
                for source_kind in {
                    claim["source_kind"] for claim in visual_claims
                }
            },
        )

        font_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "dialogue_font_source_range"
        ]
        self.assertEqual(30, len(font_claims))
        self.assertEqual(
            {
                "dialogue_font_byte_2bpp": 3_072,
                "dialogue_font_byte_table": 16,
                "dialogue_font_sjis_2bpp": 141_120,
                "dialogue_font_sjis_table": 208,
            },
            {
                primary_class: sum(
                    claim["range"][1] - claim["range"][0]
                    for claim in font_claims
                    if claim["primary_class"] == primary_class
                )
                for primary_class in {
                    claim["primary_class"] for claim in font_claims
                }
            },
        )

        def class_at(offset: int) -> str:
            return next(
                segment["primary_class"]
                for segment in manifest["segments"]
                if segment["range"][0] <= offset < segment["range"][1]
            )

        self.assertEqual("armv4t_cfg_reachable_thumb_code", class_at(0x061D7C))
        self.assertEqual("dialogue_font_byte_2bpp", class_at(0x09CD54))
        self.assertEqual(
            "dialogue_font_source_inter_entry_zero_padding",
            class_at(0x09E6F4),
        )
        self.assertEqual("dialogue_font_sjis_2bpp", class_at(0x09E954))
        self.assertEqual("dialogue_font_sjis_table", class_at(0x53D644))
        self.assertEqual(
            "dialogue_font_sjis_empty_lookup_rows", class_at(0x53D714)
        )
        self.assertEqual(
            "dialogue_font_sjis_empty_lookup_rows", class_at(0x53D73B)
        )
        self.assertEqual("dialogue_font_byte_table", class_at(0x53D73C))
        self.assertEqual("fixed_table", class_at(0x53EF2D))
        self.assertEqual(
            "motion_spawn_to_sequence_descriptor_4byte_alignment_gap",
            class_at(0x53EF2E),
        )
        self.assertEqual(
            "motion_spawn_to_sequence_descriptor_4byte_alignment_gap",
            class_at(0x53EF2F),
        )
        self.assertEqual(
            "battle_effect_sequence_descriptor_table", class_at(0x53EF30)
        )
        self.assertEqual("dialogue_font_sjis_2bpp", class_at(0x5B5FFF))
        self.assertEqual("lz77_resource", class_at(0x5B6000))
        self.assertEqual("unknown", class_at(0x5B9FFF))
        self.assertEqual("boot_mode3_framebuffer_bgr555", class_at(0x5BA000))
        self.assertEqual("arm_code", class_at(0x5CCC00))
        self.assertEqual("literal_pool", class_at(0x5CCD40))
        self.assertEqual("alignment_ff", class_at(0x5CCDEC))
        self.assertEqual("boot_mode3_framebuffer_bgr555", class_at(0x5CCE00))
        self.assertEqual("arm_code", class_at(0x5DFA00))
        self.assertEqual("literal_pool", class_at(0x5DFB40))
        self.assertEqual("padding_ff", class_at(0x5DFBEC))
        self.assertEqual("palette_bgr555", class_at(0x3F1E60))
        self.assertEqual("palette_bgr555", class_at(0x3F1F08))
        self.assertEqual("palette_bgr555", class_at(0x406010))
        self.assertEqual("dialogue_encoded_text", class_at(0x459414))
        self.assertEqual("dialogue_encoded_text", class_at(0x45943D))
        self.assertEqual(
            "dialogue_inter_record_zero_padding", class_at(0x45943E)
        )
        self.assertEqual(
            "dialogue_inter_record_zero_padding", class_at(0x459463)
        )
        self.assertEqual("dialogue_encoded_text", class_at(0x459464))
        self.assertEqual("dialogue_encoded_text", class_at(0x461CE0))
        self.assertEqual("unknown", class_at(0x461CE1))
        self.assertEqual("dialogue_pointer_table", class_at(0x461CE4))
        self.assertEqual("palette_bgr555", class_at(0x3E4AF0))
        self.assertEqual("battle_presentation_encoded_text", class_at(0x5A2170))
        self.assertEqual(
            "battle_presentation_inter_record_zero_padding",
            class_at(0x5A2181),
        )
        self.assertEqual("battle_presentation_message_pointer_table", class_at(0x5A2B08))
        self.assertEqual("battle_presentation_glyph_pointer_table", class_at(0x5A2C44))
        self.assertEqual("battle_presentation_message_glyph_binding_table", class_at(0x5A2EF4))
        self.assertEqual(
            "battle_presentation_binding_to_tile_assets_4byte_alignment_gap",
            class_at(0x5A320A),
        )
        self.assertEqual(
            "battle_presentation_binding_to_tile_assets_4byte_alignment_gap",
            class_at(0x5A320B),
        )
        self.assertEqual("fixed_table", class_at(0x5A320C))
        self.assertEqual("thumb_dispatch_literal_pool", class_at(0x064CA0))
        self.assertEqual("thumb_pc_relative_jump_table", class_at(0x064CA4))
        self.assertEqual("thumb_literal_pool", class_at(0x093C38))
        self.assertEqual("unbound_thumb_code_pointer_pool", class_at(0x53DF04))
        self.assertEqual("map_sprite_callback_pointer_pair", class_at(0x53F138))
        self.assertEqual(
            "value_range_renderer_text_pointer_table_38", class_at(0x599F5C)
        )
        self.assertEqual(
            "value_range_renderer_text_pointer_table_38", class_at(0x599FF3)
        )
        self.assertEqual("unknown", class_at(0x599FF4))
        self.assertEqual("consumer_bound_pointer_table", class_at(0x060E38))
        self.assertEqual("consumer_bound_pointer_table", class_at(0x060EF4))
        self.assertEqual("consumer_bound_pointer_table", class_at(0x59A108))
        self.assertEqual("palette_bgr555", class_at(0x349E74))
        self.assertEqual("consumer_code_slice", class_at(0x0612BC))
        self.assertEqual("consumer_code_slice", class_at(0x07AE04))
        self.assertEqual("consumer_code_slice", class_at(0x088348))
        self.assertEqual("consumer_code_slice", class_at(0x08C214))
        self.assertEqual("consumer_code_slice", class_at(0x08D934))
        self.assertEqual("consumer_code_slice", class_at(0x08DCE0))
        self.assertEqual("consumer_code_slice", class_at(0x090AEC))
        self.assertEqual("consumer_code_slice", class_at(0x090CC8))
        self.assertEqual("consumer_code_slice", class_at(0x096168))
        self.assertEqual("consumer_code_slice", class_at(0x096324))
        self.assertEqual("thumb_dispatch_literal_pool", class_at(0x096340))
        self.assertEqual("thumb_pc_relative_jump_table", class_at(0x096344))
        self.assertEqual("consumer_code_slice", class_at(0x096480))
        self.assertEqual("consumer_code_slice", class_at(0x096B74))
        self.assertEqual("consumer_code_slice", class_at(0x096D4C))
        self.assertEqual("arm_code", class_at(0x000000))
        self.assertEqual("gba_header", class_at(0x000004))
        self.assertEqual("arm_code", class_at(0x0000C0))
        self.assertEqual("unknown", class_at(0x0000C4))
        self.assertEqual("arm_code", class_at(0x0000C8))
        self.assertEqual("literal_pool", class_at(0x0000F4))
        self.assertEqual("arm_code", class_at(0x000104))
        self.assertEqual("literal_pool", class_at(0x000244))
        self.assertEqual("boot_interwork_arm_code", class_at(0x00024C))
        self.assertEqual("boot_interwork_arm_code", class_at(0x0003BB))
        self.assertEqual("boot_interwork_literal_pool", class_at(0x0003BC))
        self.assertEqual("boot_interwork_literal_pool", class_at(0x0003DF))
        self.assertEqual("unknown", class_at(0x0003E0))
        self.assertEqual("boot_interwork_thumb_code", class_at(0x061086))
        self.assertEqual("boot_interwork_thumb_code", class_at(0x09C56C))
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop",
            class_at(0x09C56E),
        )
        self.assertEqual("boot_interwork_arm_code", class_at(0x09C570))
        self.assertEqual("armv4t_cfg_reachable_thumb_code", class_at(0x09C574))
        self.assertEqual("training_text_command_script", class_at(0x007554))
        self.assertEqual("training_text_command_script", class_at(0x007F1C))
        # 0x007F1D 当初是 unknown，后来被 rom-battle-condition-result-text-v1
        # 认领为 battle_condition_result_renderer_text（claim
        # battle-condition-result-text-000）。单字节断言天然抗切段，
        # 只需把期望值更新为当前类别。
        self.assertEqual(
            "battle_condition_result_renderer_text", class_at(0x007F1D)
        )
        self.assertEqual("consumer_code_slice", class_at(0x0663A6))
        self.assertEqual("consumer_code_slice", class_at(0x0663B3))
        self.assertEqual("consumer_code_slice", class_at(0x08AFE0))
        self.assertEqual("consumer_code_slice", class_at(0x08B07B))
        self.assertEqual("value_range_renderer_text_record", class_at(0x00542E))
        self.assertEqual("value_range_renderer_text_record", class_at(0x00578B))
        self.assertEqual("unknown", class_at(0x00578C))
        self.assertEqual("u8_indexed_u16_pair_lookup", class_at(0x59F5EF))
        self.assertEqual("selector_direct_source_record", class_at(0x59F5F0))
        self.assertEqual("selector_direct_source_record", class_at(0x59F987))
        self.assertEqual("profile_text_record", class_at(0x59F988))
        self.assertEqual(
            "selector_direct_renderer_text_prefix", class_at(0x5A5ACB)
        )
        self.assertEqual(
            "selector_direct_text_slot_zero_padding", class_at(0x5A5AD4)
        )
        self.assertEqual(
            "selector_configured_copy_text_prefix", class_at(0x5A5F77)
        )
        self.assertEqual(
            "selector_configured_text_slot_zero_padding", class_at(0x5A5F82)
        )
        self.assertEqual("unknown", class_at(0x5A6343))
        self.assertEqual(
            "selector_configuration_lists", class_at(0x5A6344)
        )
        self.assertEqual(
            "selector_configuration_pointer_table", class_at(0x5A63E8)
        )
        self.assertEqual("value_range_text_selector_u16_pairs", class_at(0x542204))
        self.assertEqual("value_range_text_selector_u16_pairs", class_at(0x54229B))
        self.assertEqual("fixed_table", class_at(0x54229C))
        self.assertEqual("lz77_syntax_unbound", class_at(0x09C8D4))
        self.assertEqual(
            "bg_canvas_resource_descriptor_table", class_at(0x59903C)
        )
        self.assertEqual("chapter_script_record", class_at(0x009F2E))
        self.assertEqual(
            "chapter_terminal_to_fixed_root_zero_padding",
            class_at(0x00BFC8),
        )
        self.assertEqual("chapter_script_record", class_at(0x00BFC9))
        self.assertEqual(
            "m4a_wave_alignment_zero_padding", class_at(0x46E881)
        )
        self.assertEqual(
            "thumb_indexed_dispatch_table_cell", class_at(0x06E868)
        )
        self.assertEqual(
            "thumb_sparse_dispatch_masked_residual_cell", class_at(0x06EE9C)
        )
        self.assertEqual("unknown", class_at(0x031068))
        self.assertEqual(
            "dialogue_font_source_inter_entry_zero_padding",
            class_at(0x09E6F4),
        )
        self.assertEqual("chapter_script_record", class_at(0x03106C))
        self.assertEqual("unknown", class_at(0x04BE31))
        self.assertEqual("chapter_script_record", class_at(0x04C616))
        self.assertEqual("unknown", class_at(0x04C633))
        self.assertEqual("chapter_script_record", class_at(0x04C64E))
        self.assertEqual("chapter_script_record", class_at(0x05C5DD))
        self.assertEqual("sprite_tile_base_offset_table", class_at(0x53F298))
        self.assertEqual("speaker_label_renderer_text", class_at(0x5A57D0))
        self.assertEqual(
            "chapter_speaker_label_slot_zero_padding", class_at(0x5A57D5)
        )
        self.assertEqual("unknown", class_at(0x5A5AAC))
        self.assertEqual("unknown", class_at(0x5A5AB8))
        self.assertEqual("renderer_text_record", class_at(0x59A1B8))
        self.assertEqual(
            "renderer_text_inter_record_zero_padding", class_at(0x59A1BB)
        )
        self.assertEqual(
            "fixed_consumer_renderer_text_record", class_at(0x5A63F4)
        )
        self.assertEqual(
            "fixed_consumer_text_inter_record_zero_padding",
            class_at(0x5A641B),
        )
        self.assertEqual(
            "fixed_consumer_text_pointer_table", class_at(0x5A65C8)
        )
        self.assertEqual("unknown", class_at(0x5A65EC))
        self.assertEqual(
            "fixed_consumer_renderer_text_record", class_at(0x001CD0)
        )
        self.assertEqual(
            "fixed_consumer_text_pointer_table", class_at(0x599280)
        )
        self.assertEqual(
            "fixed_consumer_text_pointer_table", class_at(0x5997C3)
        )
        self.assertEqual(
            "fixed_consumer_text_pointer_table", class_at(0x5AAEDC)
        )
        self.assertEqual(
            "unclassified_ui_resource_pointer_table_24", class_at(0x5A7FCC)
        )
        self.assertEqual("canonical_thumb_dispatch_table", class_at(0x06FF30))
        self.assertEqual(
            "battle_effect_runtime_state_sequence_table", class_at(0x53E596)
        )
        self.assertEqual(
            "runtime_state_sequence_table_to_handler_pair_table_4byte_alignment_gap",
            class_at(0x53E696),
        )
        self.assertEqual(
            "battle_effect_sequence_descriptor_table", class_at(0x53EF30)
        )
        self.assertEqual("battle_effect_resource_pair_table", class_at(0x59911C))
        self.assertEqual("battle_effect_sprite_pair_table", class_at(0x5991B4))
        self.assertEqual("scene_visual_pack_source_table", class_at(0x5A4CE8))
        self.assertEqual("world_map_background_table", class_at(0x5A802C))
        self.assertEqual("world_map_label_table", class_at(0x5A8038))
        self.assertEqual("consumer_code_slice", class_at(0x08EE28))
        self.assertEqual("palette_bgr555", class_at(0x34941C))

        palette_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "direct_cpuset_gpu_source_range"
        ]
        self.assertEqual(3, len(palette_claims))
        self.assertEqual(
            [0x3F1E60, 0x3F1F08, 0x406010],
            [claim["range"][0] for claim in palette_claims],
        )
        self.assertTrue(
            all(claim["primary_class"] == "palette_bgr555" for claim in palette_claims)
        )

        battle_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind", "").startswith("battle_presentation_")
        ]
        self.assertEqual(162, len(battle_claims))
        self.assertEqual(
            1,
            sum(
                claim.get("claim_kind")
                == "battle_presentation_tile_assets_alignment_gap_bytes"
                for claim in battle_claims
            ),
        )

        handler_gap_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind")
            == "runtime_state_handler_table_alignment_gap_bytes"
        ]
        self.assertEqual(1, len(handler_gap_claims))
        self.assertEqual([0x53E696, 0x53E698], handler_gap_claims[0]["range"])
        self.assertFalse(handler_gap_claims[0]["cross_table_dataflow_claimed"])

        candidate_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "similar_table_adjudicated_range"
        ]
        self.assertEqual(55, len(candidate_claims))

        tile_palette_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "tile_bg_palette_source_range"
        ]
        merged_palette = next(
            claim
            for claim in tile_palette_claims
            if claim["range"] == [0x349E74, 0x349EB4]
        )
        self.assertEqual(2, len(merged_palette["source_ranges"]))
        promoted_claim = next(
            claim
            for claim in manifest["claims"]
            if claim["id"] == "consumer-code-overview_gradient_overlay-08dce0"
        )
        self.assertEqual(
            "artifacts/overview-gradient-overlay-v1/overview-gradient-overlay.json",
            promoted_claim["evidence_path"],
        )
        self.assertEqual(
            "artifacts/overview-gradient-overlay-v1/manifest.json",
            promoted_claim["promotion_manifest_path"],
        )

        unbound_lz77_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "unbound_strict_lz77_syntax_range"
        ]
        self.assertEqual(41, len(unbound_lz77_claims))
        self.assertEqual(
            14_725,
            sum(
                claim["range"][1] - claim["range"][0]
                for claim in unbound_lz77_claims
            ),
        )
        self.assertTrue(
            all(
                claim["primary_class"] == "lz77_syntax_unbound"
                and claim["runtime_reachability_claimed"] is False
                and claim["aligned_pointer_reference_count"] == 0
                for claim in unbound_lz77_claims
            )
        )

        cfg_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "cfg_reachable_instruction_bytes"
        ]
        self.assertEqual(787, len(cfg_claims))
        self.assertEqual(
            74_962,
            sum(claim["range"][1] - claim["range"][0] for claim in cfg_claims),
        )
        self.assertEqual(
            6_932,
            sum(claim["source_block_count"] for claim in cfg_claims),
        )
        self.assertTrue(
            all(
                claim["primary_class"] == "armv4t_cfg_reachable_thumb_code"
                for claim in cfg_claims
            )
        )

        reuse_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("promotion_batch") == "verified-artifact-reuse-v1"
        ]
        self.assertEqual(37, len(reuse_claims))
        self.assertEqual(
            3_919,
            sum(claim["range"][1] - claim["range"][0] for claim in reuse_claims),
        )
        self.assertEqual(
            {
                "battle_effect_resource_pair_table": 152,
                "battle_effect_runtime_state_sequence_table": 245,
                "battle_effect_sequence_descriptor_table": 520,
                "battle_effect_sprite_pair_table": 152,
                "canonical_thumb_dispatch_table": 812,
                "consumer_code_slice": 1_598,
                "palette_bgr555": 128,
                "scene_visual_pack_source_table": 252,
                "world_map_background_table": 12,
                "world_map_label_table": 48,
            },
            {
                primary_class: sum(
                    claim["range"][1] - claim["range"][0]
                    for claim in reuse_claims
                    if claim["primary_class"] == primary_class
                )
                for primary_class in {
                    claim["primary_class"] for claim in reuse_claims
                }
            },
        )
        self.assertTrue(
            all(claim["baseline_unknown_only"] is True for claim in reuse_claims)
        )
        self.assertFalse(
            any(
                "character-runtime-oam-task-bindings-v1"
                in claim["evidence_path"]
                for claim in reuse_claims
            )
        )

        dialogue_padding_claims = [
            claim
            for claim in manifest["claims"]
            if claim.get("claim_kind") == "dialogue_inter_record_zero_padding"
        ]
        self.assertEqual(1_219, len(dialogue_padding_claims))
        self.assertEqual(
            16_814,
            sum(
                claim["range"][1] - claim["range"][0]
                for claim in dialogue_padding_claims
            ),
        )
        self.assertTrue(
            all(
                claim["primary_class"] == "dialogue_inter_record_zero_padding"
                and claim["safe_allocatable_space_claimed"] is False
                and claim["runtime_reachability_claimed"] is False
                and claim["text_semantics_claimed"] is False
                for claim in dialogue_padding_claims
            )
        )

    def test_consumer_code_slice_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x0612BC] ^= 1

        with self.assertRaisesRegex(ValueError, "consumer-code bytes changed"):
            _consumer_code_slice_claims(ROOT, bytes(tampered))

    def test_boot_startup_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x104] ^= 1

        with self.assertRaisesRegex(ValueError, "boot framebuffer"):
            _boot_framebuffer_claims(ROOT, bytes(tampered))

    def test_promoted_consumer_code_slice_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x08DCE0] ^= 1

        with self.assertRaisesRegex(ValueError, "consumer-code bytes changed"):
            _consumer_code_slice_claims(ROOT, bytes(tampered))

    def test_bg_canvas_descriptor_claim_rejects_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x59903C] ^= 1

        with self.assertRaisesRegex(ValueError, "descriptor table changed"):
            _bg_canvas_descriptor_claims(ROOT, bytes(tampered))

    def test_chapter_script_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x009F2E] ^= 1

        with self.assertRaisesRegex(ValueError, "chapter-script bytes changed"):
            _chapter_script_claims(ROOT, bytes(tampered))

    def test_sprite_tile_offset_claim_rejects_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x53F298] ^= 1

        with self.assertRaisesRegex(ValueError, "sprite tile-offset table changed"):
            _sprite_definition_tile_offset_claims(ROOT, bytes(tampered))

    def test_chapter_speaker_label_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x5A57D0] ^= 1

        with self.assertRaisesRegex(ValueError, "speaker-label bytes changed"):
            _chapter_speaker_label_claims(ROOT, bytes(tampered))

    def test_renderer_text_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x59A1B8] ^= 1

        with self.assertRaisesRegex(ValueError, "renderer-text bytes changed"):
            _renderer_text_claims(ROOT, bytes(tampered))

    def test_profile_text_claims_cover_the_fixed_record_and_padding_partition(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _profile_text_claims(ROOT, rom)
        records = [
            claim
            for claim in claims
            if claim["claim_kind"] == "profile_text_record_bytes"
        ]
        padding = [
            claim
            for claim in claims
            if claim["claim_kind"] == "profile_text_alignment_zero_padding"
        ]
        self.assertEqual(46, len(records))
        self.assertEqual(
            6_798,
            sum(end - start for start, end in (claim["range"] for claim in records)),
        )
        self.assertEqual(19, len(padding))
        self.assertEqual(
            38,
            sum(end - start for start, end in (claim["range"] for claim in padding)),
        )
        ranges = sorted(claim["range"] for claim in claims)
        cursor = 0x59F988
        for start, end in ranges:
            self.assertEqual(cursor, start)
            cursor = end
        self.assertEqual(0x5A143C, cursor)

    def test_profile_text_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x59F988] ^= 1
        with self.assertRaisesRegex(ValueError, "profile-text"):
            _profile_text_claims(ROOT, bytes(tampered))

    def test_profile_text_claims_require_the_independent_verifier(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_profile_text_inventory",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _profile_text_claims(ROOT, rom)

    def test_fixed_consumer_text_claims_cover_only_tables_and_parser_records(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _fixed_consumer_text_claims(ROOT, rom)
        tables = [
            claim
            for claim in claims
            if claim["claim_kind"] == "fixed_consumer_text_pointer_table_bytes"
        ]
        records = [
            claim
            for claim in claims
            if claim["claim_kind"] == "fixed_consumer_renderer_text_record_bytes"
        ]
        self.assertEqual(11, len(tables))
        self.assertEqual(3_000, sum(b - a for a, b in (claim["range"] for claim in tables)))
        self.assertEqual(735, len(records))
        self.assertEqual(11_177, sum(b - a for a, b in (claim["range"] for claim in records)))
        ranges = sorted(claim["range"] for claim in claims)
        self.assertEqual(746, len(ranges))
        self.assertTrue(
            all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:]))
        )
        self.assertFalse(any(start <= 0x5A65EC < end for start, end in ranges))
        self.assertFalse(any(start <= 0x5A7FCC < end for start, end in ranges))

    def test_fixed_consumer_text_claims_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        tampered = bytearray(rom)
        tampered[0x5A63F4] ^= 1
        with self.assertRaisesRegex(ValueError, "fixed-consumer-text"):
            _fixed_consumer_text_claims(ROOT, bytes(tampered))
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_fixed_consumer_text_inventory",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _fixed_consumer_text_claims(ROOT, rom)

    def test_training_text_script_claims_cover_only_interpreter_consumed_records(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _training_text_script_claims(ROOT, rom)
        self.assertEqual(44, len(claims))
        self.assertEqual(
            2_505,
            sum(end - start for start, end in (claim["range"] for claim in claims)),
        )
        self.assertEqual([0x7554, 0x7587], claims[0]["range"])
        self.assertEqual([0x7EE4, 0x7F1D], claims[-1]["range"])
        self.assertTrue(
            all(
                left["range"][1] == right["range"][0]
                for left, right in zip(claims, claims[1:])
            )
        )
        self.assertTrue(
            all(
                claim["claim_kind"] == "training_text_command_script_bytes"
                and claim["primary_class"] == "training_text_command_script"
                for claim in claims
            )
        )

    def test_training_text_script_claims_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        tampered = bytearray(rom)
        tampered[0x7554] ^= 1
        with self.assertRaisesRegex(ValueError, "training-text-script"):
            _training_text_script_claims(ROOT, bytes(tampered))
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_training_text_script_inventory",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _training_text_script_claims(ROOT, rom)

    def test_value_range_text_claims_cover_only_map_and_parser_records(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _value_range_text_claims(ROOT, rom)
        maps = [claim for claim in claims if claim["claim_kind"] == "value_range_text_map_bytes"]
        records = [
            claim
            for claim in claims
            if claim["claim_kind"] == "value_range_renderer_text_record_bytes"
        ]
        self.assertEqual(1, len(maps))
        self.assertEqual([0x542204, 0x54229C], maps[0]["range"])
        self.assertEqual(38, len(records))
        self.assertEqual(862, sum(end - start for start, end in (claim["range"] for claim in records)))
        self.assertEqual([0x542E, 0x5445], records[0]["range"])
        self.assertEqual([0x5779, 0x578C], records[-1]["range"])
        self.assertFalse(any(claim["range"] == [0x599F5C, 0x599FF4] for claim in claims))

    def test_value_range_text_claims_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        tampered = bytearray(rom)
        tampered[0x542E] ^= 1
        with self.assertRaisesRegex(ValueError, "value-range-text"):
            _value_range_text_claims(ROOT, bytes(tampered))
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_value_range_text_inventory",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _value_range_text_claims(ROOT, rom)

    def test_selector_text_claims_cover_only_consumed_prefixes_and_config(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _selector_text_binding_claims(ROOT, rom)
        direct = [
            claim
            for claim in claims
            if claim["claim_kind"] == "selector_direct_renderer_text_prefix_bytes"
        ]
        configured = [
            claim
            for claim in claims
            if claim["claim_kind"] == "selector_configured_copy_text_prefix_bytes"
        ]
        lists = [
            claim
            for claim in claims
            if claim["claim_kind"] == "selector_configuration_list_bytes"
        ]
        pointers = [
            claim
            for claim in claims
            if claim["claim_kind"] == "selector_configuration_pointer_bytes"
        ]
        self.assertEqual((46, 324), (len(direct), sum(b - a for a, b in (claim["range"] for claim in direct))))
        self.assertEqual((38, 316), (len(configured), sum(b - a for a, b in (claim["range"] for claim in configured))))
        self.assertEqual([[0x5A6344, 0x5A63E8]], [claim["range"] for claim in lists])
        self.assertEqual([[0x5A63E8, 0x5A63F4]], [claim["range"] for claim in pointers])
        ranges = sorted(claim["range"] for claim in claims)
        self.assertEqual(86, len(ranges))
        self.assertTrue(all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:])))
        self.assertFalse(any(start <= 0x5A5AD4 < end for start, end in ranges))
        self.assertFalse(any(start <= 0x5A6343 < end for start, end in ranges))

    def test_selector_text_claims_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        tampered = bytearray(rom)
        tampered[0x5A5ACB] ^= 1
        with self.assertRaisesRegex(ValueError, "selector-text"):
            _selector_text_binding_claims(ROOT, bytes(tampered))
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_selector_text_bindings",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _selector_text_binding_claims(ROOT, rom)

    def test_battle_message_text_claims_close_records_and_zero_padding(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _battle_message_text_claims(ROOT, rom)
        records = [
            claim
            for claim in claims
            if claim["claim_kind"] == "battle_message_renderer_text_record_bytes"
        ]
        padding = [
            claim
            for claim in claims
            if claim["claim_kind"] == "battle_message_inter_record_zero_padding"
        ]
        self.assertEqual(
            (79, 1_411),
            (
                len(records),
                sum(end - start for start, end in (claim["range"] for claim in records)),
            ),
        )
        self.assertEqual(
            (79, 1_329),
            (
                len(padding),
                sum(end - start for start, end in (claim["range"] for claim in padding)),
            ),
        )
        ranges = sorted(claim["range"] for claim in claims)
        self.assertEqual(158, len(ranges))
        cursor = 0x5A1580
        for start, end in ranges:
            self.assertEqual(cursor, start)
            cursor = end
        self.assertEqual(0x5A2034, cursor)
        self.assertFalse(any(start < 0x5A1580 for start, _ in ranges))
        self.assertFalse(any(start <= 0x5A2034 < end for start, end in ranges))
        self.assertTrue(
            all(
                claim.get("safe_allocatable_space_claimed") is False
                for claim in padding
            )
        )

    def test_battle_message_text_claims_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        tampered = bytearray(rom)
        tampered[0x5A1580] ^= 1
        with self.assertRaisesRegex(ValueError, "battle-message-text"):
            _battle_message_text_claims(ROOT, bytes(tampered))
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_battle_message_text_inventory",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _battle_message_text_claims(ROOT, rom)

    def test_boot_interwork_claims_only_the_closed_root_spine_and_literals(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _boot_interwork_claims(ROOT, rom)
        self.assertEqual(
            [
                [0x00024C, 0x0003BC],
                [0x0003BC, 0x0003E0],
                [0x061086, 0x06108A],
                [0x09C56C, 0x09C56E],
                [0x09C570, 0x09C574],
            ],
            [claim["range"] for claim in claims],
        )
        self.assertEqual(414, sum(end - start for start, end in (claim["range"] for claim in claims)))
        self.assertEqual(
            [
                "boot_interwork_arm_instruction_bytes",
                "boot_interwork_literal_pool_bytes",
                "boot_interwork_thumb_instruction_bytes",
                "boot_interwork_thumb_instruction_bytes",
                "boot_interwork_arm_instruction_bytes",
            ],
            [claim["claim_kind"] for claim in claims],
        )
        self.assertTrue(all(claim["runtime_reachability_claimed"] is False for claim in claims))
        self.assertFalse(any(start <= 0x09C56E < end for start, end in (claim["range"] for claim in claims)))
        self.assertFalse(any(start < 0x00024C or end > 0x0003E0 for start, end in (claim["range"] for claim in claims[:2])))

    def test_boot_interwork_claims_fail_closed(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        tampered = bytearray(rom)
        tampered[0x24C] ^= 1
        with self.assertRaisesRegex(ValueError, "boot-interwork"):
            _boot_interwork_claims(ROOT, bytes(tampered))
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_boot_interwork",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                _boot_interwork_claims(ROOT, rom)

    def test_unbound_lz77_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x09C8D4] ^= 1

        with self.assertRaisesRegex(ValueError, "unbound LZ77"):
            _unbound_lz77_claims(ROOT, bytes(tampered))

    def test_cfg_inventory_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x061D7C] ^= 1
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind") != "cfg_reachable_instruction_bytes"
        ]

        with self.assertRaisesRegex(ValueError, "CFG inventory"):
            _cfg_inventory_claims(ROOT, bytes(tampered), baseline)

    def test_cfg_v3_promotes_only_current_unknown_code_and_allowed_table_cells(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind")
            not in {
                "cfg_v3_reachable_instruction_bytes",
                "cfg_v3_indexed_dispatch_table_cell",
                "cfg_v3_sparse_dispatch_masked_residual_cell",
            }
        ]
        claims = _cfg_inventory_v3_claims(ROOT, rom, baseline)
        code_claims = [
            claim
            for claim in claims
            if claim["claim_kind"] == "cfg_v3_reachable_instruction_bytes"
        ]
        table_claims = [
            claim
            for claim in claims
            if claim["claim_kind"] == "cfg_v3_indexed_dispatch_table_cell"
        ]
        residual_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_v3_sparse_dispatch_masked_residual_cell"
        ]
        self.assertEqual(113, len(code_claims))
        self.assertEqual(
            9_060,
            sum(claim["range"][1] - claim["range"][0] for claim in code_claims),
        )
        self.assertEqual(112, len(table_claims))
        self.assertEqual(
            448,
            sum(claim["range"][1] - claim["range"][0] for claim in table_claims),
        )
        self.assertEqual(8, len(residual_claims))
        self.assertEqual(
            32,
            sum(
                claim["range"][1] - claim["range"][0]
                for claim in residual_claims
            ),
        )
        self.assertEqual(
            [
                0x06EE9C,
                0x06EEA4,
                0x06EEAC,
                0x06EEB4,
                0x07BED4,
                0x07BEDC,
                0x07BEE4,
                0x07BEEC,
            ],
            [claim["range"][0] for claim in residual_claims],
        )
        self.assertTrue(
            all(
                claim["primary_class"]
                == "thumb_sparse_dispatch_masked_residual_cell"
                and claim["dispatch_selected"] is False
                and claim["runtime_reachability_claimed"] is False
                and claim["target_reachability_claimed"] is False
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["range_denominator_sha256"]
                == "f12097bd30174bd08f177f083fd886995edbdfc05de91c178b2d5ee96a65f9a5"
                for claim in residual_claims
            )
        )
        self.assertTrue(
            all(claim["promoted_from_primary_class"] == "unknown" for claim in claims)
        )

        sparse_holes = {
            *(range(0x06EE98 + 4, 0x06EE98 + 9 * 4, 8)),
            *(range(0x07BED0 + 4, 0x07BED0 + 9 * 4, 8)),
        }
        claimed_table_starts = {claim["range"][0] for claim in table_claims}
        self.assertTrue(sparse_holes.isdisjoint(claimed_table_starts))
        self.assertEqual(sparse_holes, {claim["range"][0] for claim in residual_claims})

    def test_cfg_v3_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x06EEE0] ^= 1
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind")
            not in {
                "cfg_v3_reachable_instruction_bytes",
                "cfg_v3_indexed_dispatch_table_cell",
                "cfg_v3_sparse_dispatch_masked_residual_cell",
            }
        ]
        with self.assertRaisesRegex(ValueError, "CFG v3"):
            _cfg_inventory_v3_claims(ROOT, bytes(tampered), baseline)

    def test_cfg_v3_residual_cells_fail_closed_on_partial_or_duplicate_baseline(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        v3_kinds = {
            "cfg_v3_reachable_instruction_bytes",
            "cfg_v3_indexed_dispatch_table_cell",
            "cfg_v3_sparse_dispatch_masked_residual_cell",
        }
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind") not in v3_kinds
        ]
        synthetic_known = {
            "id": "synthetic-v3-residual-known-overlap",
            "range": [0x06EE9C, 0x06EE9D],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "partially unknown"):
            _cfg_inventory_v3_claims(ROOT, rom, [*baseline, synthetic_known])
        with self.assertRaisesRegex(ValueError, "pre-v3 baseline"):
            _cfg_inventory_v3_claims(ROOT, rom, self.repository_manifest["claims"])

    def test_cfg_proven_roots_promotes_unknown_delta_and_three_direct_producers(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        kinds = {
            "cfg_proven_roots_reachable_instruction_bytes",
            "cfg_proven_roots_direct_thumb_bl_producer",
        }
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind") not in kinds
        ]
        claims = _cfg_proven_roots_claims(ROOT, rom, baseline)
        code_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_proven_roots_reachable_instruction_bytes"
        ]
        producer_claims = [
            claim
            for claim in claims
            if claim["claim_kind"] == "cfg_proven_roots_direct_thumb_bl_producer"
        ]
        self.assertEqual(116, len(code_claims))
        self.assertEqual(
            12_946,
            sum(claim["range"][1] - claim["range"][0] for claim in code_claims),
        )
        self.assertEqual(
            [0x73688, 0x7443C, 0x74918],
            [claim["range"][0] for claim in producer_claims],
        )
        self.assertEqual(
            12,
            sum(
                claim["range"][1] - claim["range"][0]
                for claim in producer_claims
            ),
        )
        self.assertTrue(
            all(
                claim["promoted_from_primary_class"] == "unknown"
                for claim in claims
            )
        )
        promoted = {
            byte
            for claim in claims
            for byte in range(claim["range"][0], claim["range"][1])
        }
        self.assertTrue(set(range(0x7A0CA, 0x7A0D4)).isdisjoint(promoted))
        self.assertTrue(set(range(0x7A222, 0x7A22C)).isdisjoint(promoted))

    def test_cfg_proven_roots_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x722A8] ^= 1
        kinds = {
            "cfg_proven_roots_reachable_instruction_bytes",
            "cfg_proven_roots_direct_thumb_bl_producer",
        }
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind") not in kinds
        ]
        with self.assertRaisesRegex(ValueError, "CFG proven-root"):
            _cfg_proven_roots_claims(ROOT, bytes(tampered), baseline)

    def test_cfg_proven_roots_v2_promotes_three_root_delta_and_five_producers(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        kinds = {
            "cfg_proven_roots_v2_reachable_instruction_bytes",
            "cfg_proven_roots_v2_direct_thumb_bl_producer",
        }
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind") not in kinds
        ]
        claims = _cfg_proven_roots_v2_claims(ROOT, rom, baseline)
        code_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_proven_roots_v2_reachable_instruction_bytes"
        ]
        producer_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_proven_roots_v2_direct_thumb_bl_producer"
        ]
        self.assertEqual(86, len(code_claims))
        self.assertEqual(
            9_876,
            sum(claim["range"][1] - claim["range"][0] for claim in code_claims),
        )
        self.assertEqual(
            [0x73690, 0x7425A, 0x7434E, 0x74448, 0x74F2C],
            [claim["range"][0] for claim in producer_claims],
        )
        self.assertEqual(
            20,
            sum(
                claim["range"][1] - claim["range"][0]
                for claim in producer_claims
            ),
        )
        self.assertTrue(
            all(
                claim["promoted_from_primary_class"] == "unknown"
                for claim in claims
            )
        )

    def test_cfg_proven_roots_v2_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x851F8] ^= 1
        kinds = {
            "cfg_proven_roots_v2_reachable_instruction_bytes",
            "cfg_proven_roots_v2_direct_thumb_bl_producer",
        }
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind") not in kinds
        ]
        with self.assertRaisesRegex(ValueError, "CFG proven-root v2"):
            _cfg_proven_roots_v2_claims(ROOT, bytes(tampered), baseline)

    def test_dialogue_padding_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x45943E] ^= 1
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind")
            not in {
                "dialogue_inter_record_zero_padding",
                "cfg_reachable_instruction_bytes",
            }
        ]

        with self.assertRaisesRegex(ValueError, "dialogue padding"):
            _dialogue_padding_claims(ROOT, bytes(tampered), baseline)

    def test_dialogue_padding_claims_refuse_to_overwrite_existing_primary_semantics(self):
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("claim_kind")
            not in {
                "dialogue_inter_record_zero_padding",
                "cfg_reachable_instruction_bytes",
            }
        ]
        baseline.append(
            {
                "id": "conflicting-existing-semantic",
                "range": [0x45943E, 0x45943F],
                "role": "primary",
                "primary_class": "existing_semantic",
            }
        )

        with self.assertRaisesRegex(ValueError, "baseline unknown"):
            _dialogue_padding_claims(
                ROOT, (ROOT / "rom/base.gba").read_bytes(), baseline
            )

    def test_verified_artifact_reuse_claims_reject_rom_tampering(self):
        tampered = bytearray((ROOT / "rom/base.gba").read_bytes())
        tampered[0x06FF30] ^= 1
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("promotion_batch") != "verified-artifact-reuse-v1"
        ]

        with self.assertRaisesRegex(ValueError, "verified artifact reuse"):
            _verified_artifact_reuse_claims(ROOT, bytes(tampered), baseline)

    def test_verified_artifact_reuse_claims_fail_closed_on_verifier_failure(self):
        baseline = [
            claim
            for claim in self.repository_manifest["claims"]
            if claim.get("promotion_batch") != "verified-artifact-reuse-v1"
        ]
        failed = {
            "schema": "rom-cfg-seeds-verification-v1",
            "verified": False,
            "errors": ["injected failure"],
        }
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_cfg_seeds",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _verified_artifact_reuse_claims(
                    ROOT, (ROOT / "rom/base.gba").read_bytes(), baseline
                )

    def test_verified_artifact_reuse_selectors_resolve_to_fixed_source_records(self):
        artifacts = {spec["id"]: spec for spec in VERIFIED_REUSE_ARTIFACTS}

        def select(document, selector):
            selected = document
            for part in selector.removeprefix("/").split("/"):
                if isinstance(selected, dict):
                    selected = selected[part]
                else:
                    selected = selected[int(part)]
            return selected

        def record_range(record):
            if "table_range" in record:
                return record["table_range"]
            if "file_offset" in record:
                size = record.get("size")
                if (
                    size is None
                    and isinstance(record.get("gba_start"), str)
                    and isinstance(record.get("gba_end"), str)
                ):
                    return [
                        record["file_offset"],
                        int(record["gba_end"], 16) - 0x08000000,
                    ]
                if size is None:
                    size = record["entry_count"] * record["entry_size"]
                return [record["file_offset"], record["file_offset"] + size]
            if "gba_address" in record:
                size = record.get("size")
                if size is None:
                    size = record["entry_count"] * record["entry_size"]
                start = int(record["gba_address"], 16) - 0x08000000
                return [start, start + size]
            if "gba_range" in record:
                return [int(value, 16) - 0x08000000 for value in record["gba_range"]]
            if "source_pointer" in record:
                start = int(record["source_pointer"], 16) - 0x08000000
                return [start, start + record["size"]]
            return [
                int(record["start"], 16) - 0x08000000,
                int(record["end_exclusive"], 16) - 0x08000000,
            ]

        for source in VERIFIED_REUSE_RANGE_SPECS:
            with self.subTest(source=source["id"]):
                self.assertEqual(
                    set(source["artifact_ids"]),
                    set(source["evidence_selectors"]),
                )
                for artifact_id, selector in source[
                    "evidence_selectors"
                ].items():
                    artifact = artifacts[artifact_id]
                    evidence_name = next(
                        iter(artifact["payloads"]), "manifest.json"
                    )
                    document = json.loads(
                        (
                            ROOT
                            / artifact["artifact"]
                            / evidence_name
                        ).read_text(encoding="utf-8")
                    )
                    record = select(document, selector)
                    self.assertEqual(list(source["range"]), record_range(record))
                    self.assertEqual(
                        source["sha256"],
                        record.get("table_sha256", record.get("sha256")),
                    )

    def test_auditor_rejects_a_tampered_segment(self):
        manifest = self.repository_manifest
        tampered = copy.deepcopy(manifest)
        tampered["segments"][0]["range"][1] += 1

        report = audit_manifest(ROOT, tampered)

        self.assertFalse(report["verified"])
        self.assertIn("manifest differs from reproducible scan", report["errors"])

    def test_direct_cli_writes_and_reverifies_the_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "coverage.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/audit_rom_byte_coverage.py",
                    "--root",
                    ".",
                    "--manifest",
                    str(output),
                    "--write",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertTrue(report["verified"])
            self.assertFalse(report["semantic_classification_complete"])

    def test_require_semantic_complete_rejects_explicit_unknown_bytes(self):
        completed = subprocess.run(
            [
                sys.executable,
                "tools/audit_rom_byte_coverage.py",
                "--root",
                ".",
                "--require-semantic-complete",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(2, completed.returncode, completed.stderr)
        self.assertTrue(report["verified"])
        self.assertFalse(report["semantic_classification_complete"])


class BootInterworkPaddingCoverageTests(unittest.TestCase):
    def _baseline(self) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch")
            != "rom-boot-interwork-padding-coverage-v1"
            and claim.get("claim_kind")
            != "boot_interwork_veneer_alignment_nop_bytes"
        ]

    def test_promotes_only_verified_two_byte_gap(self):
        helper = coverage_auditor._boot_interwork_padding_claims
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()

        claims = helper(ROOT, rom, baseline)

        self.assertEqual(1, len(claims))
        claim = claims[0]
        self.assertEqual([0x09C56E, 0x09C570], claim["range"])
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop",
            claim["primary_class"],
        )
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop_bytes",
            claim["claim_kind"],
        )
        self.assertEqual(
            "rom-boot-interwork-padding-coverage-v1",
            claim["promotion_batch"],
        )
        self.assertEqual(
            "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676",
            claim["bytes_sha256"],
        )
        self.assertEqual(
            "639f595e03eb779de859b21c42fb77388cd5a93c26be5514b7c1f700fe1d09b9",
            claim["range_denominator_sha256"],
        )
        self.assertEqual(
            [
                "/producer_chain/interwork_spine/1",
                "/producer_chain/skipped_padding_range",
                "/producer_chain/skipped_padding_sha256",
                "/producer_chain/interwork_spine/2",
            ],
            claim["evidence_selectors"],
        )
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertFalse(claim["all_zero"])
        self.assertEqual(0, claim["zero_byte_count"])
        self.assertEqual(0x46C0, claim["encoding_halfword_le"])
        self.assertEqual("mov r8, r8", claim["decoded_instruction"])
        self.assertTrue(claim["alignment_padding"])
        self.assertFalse(claim["bound_spine_executes_padding"])
        self.assertFalse(claim["runtime_reachability_claimed"])
        self.assertFalse(claim["code_reachability_claimed"])
        self.assertFalse(claim["safe_allocatable_space_claimed"])

        payload = json.loads(
            (ROOT / claim["evidence_path"]).read_text(encoding="utf-8")
        )
        selected_values = []
        for selector in claim["evidence_selectors"]:
            selected = payload
            for token in selector.lstrip("/").split("/"):
                selected = (
                    selected[int(token)]
                    if isinstance(selected, list)
                    else selected[token]
                )
            selected_values.append(selected)
        self.assertEqual("thumb_bx_pc", selected_values[0]["kind"])
        self.assertEqual([0x09C56C, 0x09C56E], selected_values[0]["range"])
        self.assertEqual("0x0809C570", selected_values[0]["target"])
        self.assertEqual([0x09C56E, 0x09C570], selected_values[1])
        self.assertEqual(claim["bytes_sha256"], selected_values[2])
        self.assertEqual("arm_b", selected_values[3]["kind"])
        self.assertEqual([0x09C570, 0x09C574], selected_values[3]["range"])
        self.assertEqual("0x0800024C", selected_values[3]["target"])

        segments = atomize_claims(len(rom), baseline + claims)
        segment_at = lambda offset: next(
            item
            for item in segments
            if item["range"][0] <= offset < item["range"][1]
        )
        self.assertEqual(
            "boot_interwork_thumb_code", segment_at(0x09C56D)["primary_class"]
        )
        self.assertEqual(
            "boot_interwork_veneer_alignment_nop",
            segment_at(0x09C56E)["primary_class"],
        )
        self.assertEqual(
            "boot_interwork_arm_code", segment_at(0x09C570)["primary_class"]
        )

    def test_fails_closed(self):
        helper = coverage_auditor._boot_interwork_padding_claims
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()

        with self.assertRaisesRegex(ValueError, "spine claim denominator"):
            helper(ROOT, rom, [])

        occupied = {
            "id": "forced-partial-owner",
            "range": [0x09C56E, 0x09C56F],
            "role": "primary",
            "primary_class": "forced_owner",
            "claim_kind": "forced_owner",
        }
        with self.assertRaisesRegex(ValueError, "existing primary claim"):
            helper(ROOT, rom, baseline + [occupied])

        explicit_unknown = {
            "id": "forced-explicit-unknown-owner",
            "range": [0x09C56E, 0x09C570],
            "role": "primary",
            "primary_class": "unknown",
            "claim_kind": "forced_explicit_unknown_owner",
        }
        with self.assertRaisesRegex(ValueError, "existing primary claim"):
            helper(ROOT, rom, baseline + [explicit_unknown])

        duplicate = {
            "id": "forced-duplicate",
            "range": [0x09C56E, 0x09C570],
            "role": "primary",
            "primary_class": "forced_owner",
            "claim_kind": "boot_interwork_veneer_alignment_nop_bytes",
            "promotion_batch": "rom-boot-interwork-padding-coverage-v1",
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(ROOT, rom, baseline + [duplicate])

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_boot_interwork",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verifier failed"):
                helper(ROOT, rom, baseline)

        with mock.patch.object(
            coverage_auditor,
            "BOOT_INTERWORK_PAYLOAD_SHA256",
            "0" * 64,
        ):
            with self.assertRaisesRegex(ValueError, "payload changed"):
                helper(ROOT, rom, baseline)


class MotionSpawnSequenceAlignmentGapCoverageTests(unittest.TestCase):
    """Frozen contract for the two-byte motion/sequence table alignment gap."""

    BATCH = "rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1"
    PRIMARY_CLASS = "motion_spawn_to_sequence_descriptor_4byte_alignment_gap"
    CLAIM_KIND = "motion_spawn_sequence_descriptor_alignment_gap_bytes"
    CANDIDATE_RANGE = [0x53EF2E, 0x53EF30]
    CANDIDATE_GBA_RANGE = [0x0853EF2E, 0x0853EF30]
    CANDIDATE_BYTES_SHA256 = (
        "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
    )
    RANGE_DENOMINATOR_SHA256 = (
        "6646067a0bc46bcc6c2fde5aa94299022ac51d7454b946048e51d929b0a58d03"
    )
    LEFT_TABLE_RANGE = [0x53EE98, 0x53EF2E]
    LEFT_TABLE_SHA256 = (
        "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d"
    )
    LEFT_LAST_RECORD_RANGE = [0x53EF24, 0x53EF2E]
    LEFT_LAST_RECORD_SHA256 = (
        "64be90aacfd3a0218cd44111cb6b37eba5277b1cd14172a6be8f0292848e21b8"
    )
    RIGHT_FULL_RANGE = [0x53EF30, 0x53F140]
    RIGHT_FULL_SHA256 = (
        "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f"
    )
    RIGHT_PRIMARY_RANGE = [0x53EF30, 0x53F138]
    LEFT_OWNER_ID = "bank-palettes-000"
    LEFT_OWNER_RANGE = [0x53EE98, 0x53EF2E]
    LEFT_OWNER_CLASS = "fixed_table"
    RIGHT_OWNER_ID = "verified-reuse-battle-effect-sequence-descriptors-53ef30"
    RIGHT_OWNER_RANGE = [0x53EF30, 0x53F138]
    RIGHT_OWNER_CLASS = "battle_effect_sequence_descriptor_table"
    LEFT_MANIFEST_PATH = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
    LEFT_MANIFEST_SHA256 = (
        "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848"
    )
    LEFT_VERIFIER_PATH = "tools/verify_battle_effect_sprite_animations.py"
    LEFT_VERIFIER_SHA256 = (
        "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b"
    )
    LEFT_UPSTREAM_TEST_PATH = "tests/test_export_battle_effect_sprite_animations.py"
    LEFT_UPSTREAM_TEST_SHA256 = (
        "5285b55f1e7a7ec525800a69d1130ef23f97c10f1e2913b7af15daef1f2f0b35"
    )
    RIGHT_MANIFEST_PATH = "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
    RIGHT_MANIFEST_SHA256 = (
        "ec8f41571bb132577ecb7bc57f946a85f219b4c05f3697c89b75be73385b0c73"
    )
    RIGHT_VERIFIER_PATH = "tools/verify_battle_effect_sequence_bindings.py"
    RIGHT_VERIFIER_SHA256 = (
        "5d0012a1f0a03c6068d0150df16074bdd16cb426325dbb4508db521fc6555a2b"
    )
    RIGHT_UPSTREAM_TEST_PATH = "tests/test_export_battle_effect_sequence_bindings.py"
    RIGHT_UPSTREAM_TEST_SHA256 = (
        "e453b7f99ebb2f3223c66d101d64634525d192946bcc664d52e5c80c84de7ab1"
    )

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
        ]

    @staticmethod
    def _select(document: object, selector: str) -> object:
        selected = document
        for token in selector.removeprefix("/").split("/"):
            if isinstance(selected, dict):
                selected = selected[token]
            elif isinstance(selected, list):
                selected = selected[int(token)]
            else:
                raise AssertionError(f"unresolved selector {selector}")
        return selected

    def test_promotes_only_the_exact_two_byte_alignment_gap(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        claims = helper(ROOT, self._rom(), self._baseline())

        self.assertEqual(1, len(claims))
        claim = claims[0]
        self.assertEqual(self.CANDIDATE_RANGE, claim["range"])
        self.assertEqual(self.CANDIDATE_GBA_RANGE, claim["gba_range"])
        self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
        self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
        self.assertEqual(self.BATCH, claim["promotion_batch"])
        self.assertEqual("primary", claim["role"])
        self.assertEqual("unknown", claim["promoted_from_primary_class"])
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["bytes_sha256"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["packed_bytes_sha256"])
        self.assertEqual(
            self.RANGE_DENOMINATOR_SHA256, claim["range_denominator_sha256"]
        )
        self.assertEqual(2, claim["zero_byte_count"])
        self.assertTrue(claim["all_zero"])

        self.assertEqual(self.LEFT_TABLE_RANGE, claim["motion_spawn_table_range"])
        self.assertEqual(
            self.LEFT_TABLE_SHA256, claim["motion_spawn_table_sha256"]
        )
        self.assertEqual(15, claim["motion_spawn_table_entry_count"])
        self.assertEqual(10, claim["motion_spawn_table_entry_size"])
        self.assertEqual(14, claim["motion_spawn_last_record_index"])
        self.assertEqual(
            self.LEFT_LAST_RECORD_RANGE, claim["motion_spawn_last_record_range"]
        )
        self.assertEqual(
            "ffff0000000000000000", claim["motion_spawn_last_record_raw_hex"]
        )
        self.assertEqual(
            self.LEFT_LAST_RECORD_SHA256,
            claim["motion_spawn_last_record_sha256"],
        )
        self.assertEqual([-1, 0, 0, 0, 0], claim["motion_spawn_last_record_decoded"])
        self.assertEqual("<hhhhh", claim["motion_spawn_last_record_struct"])
        self.assertEqual(5, claim["motion_spawn_last_record_field_count"])
        self.assertEqual(2, claim["motion_spawn_last_record_field_width_bytes"])
        self.assertTrue(claim["motion_spawn_last_record_is_terminator"])

        self.assertEqual(self.RIGHT_FULL_RANGE, claim["sequence_descriptor_full_source_range"])
        self.assertEqual(
            self.RIGHT_FULL_SHA256, claim["sequence_descriptor_full_source_sha256"]
        )
        self.assertEqual(
            self.RIGHT_FULL_RANGE, claim["sequence_descriptor_table_range"]
        )
        self.assertEqual(
            self.RIGHT_PRIMARY_RANGE, claim["sequence_descriptor_primary_range"]
        )
        self.assertEqual(22, claim["sequence_descriptor_entry_count"])
        self.assertEqual(24, claim["sequence_descriptor_entry_size"])

        self.assertEqual(
            self.LEFT_OWNER_ID, claim["previous_owner_id"]
        )
        self.assertEqual(self.LEFT_OWNER_RANGE, claim["previous_owner_range"])
        self.assertEqual(self.LEFT_OWNER_CLASS, claim["previous_owner_class"])
        self.assertEqual(self.RIGHT_OWNER_ID, claim["next_owner_id"])
        self.assertEqual(self.RIGHT_OWNER_RANGE, claim["next_owner_range"])
        self.assertEqual(self.RIGHT_OWNER_CLASS, claim["next_owner_class"])

        self.assertEqual(0x53EF30, claim["alignment_target"])
        self.assertEqual("(0x53EF2E + 3) & ~3 == 0x53EF30", claim["alignment_formula"])
        self.assertEqual(2, claim["alignment_gap_bytes"])
        self.assertEqual(
            ["/motion_spawn_table", "/motion_spawn_records/14"],
            claim["previous_owner_evidence_selectors"],
        )
        self.assertEqual(
            ["/sequence_descriptor_table"],
            claim["next_owner_evidence_selectors"],
        )

        self.assertFalse(claim["reserved_space_claimed"])
        self.assertFalse(claim["free_space_claimed"])
        self.assertFalse(claim["natural_runtime_reachability_claimed"])
        self.assertFalse(claim["global_unreachable_claimed"])
        self.assertFalse(claim["editing_or_relocation_safety_claimed"])
        self.assertFalse(claim["editable_claimed"])
        self.assertFalse(claim["relocatable_claimed"])
        self.assertFalse(claim["safe_allocatable_space_claimed"])
        self.assertFalse(claim["adjacent_bytes_claimed"])
        self.assertEqual(
            [
                "Only the exact two current-unknown bytes between the frozen 15x10-byte motion spawn table and the frozen 22x24-byte sequence descriptor table are classified as the bytes needed to reach the next 4-byte boundary.",
                "This is not a reserved-space, free-space, natural-runtime reachability, global-unreachability, editing, relocation, safe-allocation, adjacent-byte, or additional table-field semantics claim.",
            ],
            claim["limitations"],
        )

    def test_verifies_two_evidence_manifests_selectors_and_identities(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        claim = helper(ROOT, self._rom(), self._baseline())[0]
        self.assertEqual(self.LEFT_MANIFEST_PATH, claim["previous_owner_evidence_path"])
        self.assertEqual(self.LEFT_MANIFEST_SHA256, claim["previous_owner_evidence_sha256"])
        self.assertEqual(self.LEFT_VERIFIER_PATH, claim["previous_owner_verifier_path"])
        self.assertEqual(self.LEFT_VERIFIER_SHA256, claim["previous_owner_verifier_sha256"])
        self.assertEqual(self.LEFT_UPSTREAM_TEST_PATH, claim["previous_owner_upstream_test_path"])
        self.assertEqual(self.LEFT_UPSTREAM_TEST_SHA256, claim["previous_owner_upstream_test_sha256"])
        self.assertEqual(self.RIGHT_MANIFEST_PATH, claim["next_owner_evidence_path"])
        self.assertEqual(self.RIGHT_MANIFEST_SHA256, claim["next_owner_evidence_sha256"])
        self.assertEqual(self.RIGHT_VERIFIER_PATH, claim["next_owner_verifier_path"])
        self.assertEqual(self.RIGHT_VERIFIER_SHA256, claim["next_owner_verifier_sha256"])
        self.assertEqual(self.RIGHT_UPSTREAM_TEST_PATH, claim["next_owner_upstream_test_path"])
        self.assertEqual(self.RIGHT_UPSTREAM_TEST_SHA256, claim["next_owner_upstream_test_sha256"])

    def test_fails_closed_on_unknown_overlap_duplicate_batch_and_secondary_overlap(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        rom = self._rom()
        baseline = self._baseline()
        for role, message in (("primary", "current unknown"), ("secondary", "secondary")):
            with self.subTest(role=role):
                injected = {
                    "id": f"injected-{role}-overlap",
                    "range": [0x53EF2E, 0x53EF2F],
                    "role": role,
                    "primary_class": "injected_known" if role == "primary" else None,
                    "claim_kind": "injected_overlap",
                }
                if role == "secondary":
                    injected.pop("primary_class")
                with self.assertRaisesRegex(ValueError, message):
                    helper(ROOT, rom, [*baseline, injected])

        duplicate = {
            "id": "injected-duplicate-batch",
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": "injected_duplicate",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(ROOT, rom, [*baseline, duplicate])

        duplicate_kind = {
            "id": "injected-duplicate-kind",
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": self.CLAIM_KIND,
            "promotion_batch": "injected-other-batch",
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(ROOT, rom, [*baseline, duplicate_kind])

    def test_fails_closed_on_identity_verifier_and_constant_drift(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        rom = self._rom()
        baseline = self._baseline()
        failed = {"verified": False, "errors": ["forced failure"]}
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sprite_animations",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sequence_bindings",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)

        for constant in (
            "MOTION_SPAWN_SEQUENCE_GAP_BYTES_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_RANGE_DENOMINATOR_SHA256",
            "MOTION_SPAWN_TABLE_SHA256",
            "SEQUENCE_DESCRIPTOR_TABLE_SHA256",
            "SEQUENCE_DESCRIPTOR_FULL_SOURCE_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_LEFT_MANIFEST_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_LEFT_VERIFIER_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_LEFT_UPSTREAM_TEST_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_MANIFEST_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_VERIFIER_SHA256",
            "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_UPSTREAM_TEST_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaisesRegex(ValueError, "contract|identity|changed|candidate"):
                        helper(ROOT, rom, baseline)

    def test_fails_closed_on_batch_and_owner_literal_drift(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        rom = self._rom()
        baseline = self._minimal_owner_baseline()
        left_report = {
            "schema": "battle-effect-sprite-animations-verification-v1",
            "verified": True,
            "verified_groups": 18,
            "verified_frames": 178,
            "verified_components": 437,
            "verified_animations": 23,
            "errors": [],
        }
        right_report = {
            "schema": "battle-effect-sequence-bindings-verification-v1",
            "verified": True,
            "verified_runtime_state_bindings": 256,
            "verified_active_action_bindings": 87,
            "verified_ninja_tool_bindings": 94,
            "verified_sequences": 22,
            "errors": [],
        }

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sprite_animations",
            return_value=left_report,
        ), mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sequence_bindings",
            return_value=right_report,
        ):
            with self.subTest(constant="MOTION_SPAWN_SEQUENCE_GAP_BATCH"):
                with mock.patch.object(
                    coverage_auditor,
                    "MOTION_SPAWN_SEQUENCE_GAP_BATCH",
                    "drifted-motion-gap-batch",
                ):
                    with self.assertRaisesRegex(ValueError, "batch.*contract"):
                        helper(ROOT, rom, baseline)

            identity_cases = (
                (
                    "MOTION_SPAWN_SEQUENCE_GAP_LEFT_OWNER_ID",
                    self.LEFT_OWNER_ID,
                    "id",
                    "drifted-left-owner",
                ),
                (
                    "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_OWNER_ID",
                    self.RIGHT_OWNER_ID,
                    "id",
                    "drifted-right-owner",
                ),
                (
                    "MOTION_SPAWN_SEQUENCE_GAP_LEFT_OWNER_RANGE",
                    self.LEFT_OWNER_ID,
                    "range",
                    (0x53EE99, 0x53EF2E),
                ),
                (
                    "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_OWNER_RANGE",
                    self.RIGHT_OWNER_ID,
                    "range",
                    (0x53EF30, 0x53F130),
                ),
            )
            for constant, owner_id, field, drifted in identity_cases:
                with self.subTest(constant=constant):
                    changed = []
                    for claim in baseline:
                        item = dict(claim)
                        if item["id"] == owner_id:
                            item[field] = (
                                list(drifted) if field == "range" else drifted
                            )
                        changed.append(item)
                    with mock.patch.object(coverage_auditor, constant, drifted):
                        with self.assertRaisesRegex(
                            ValueError, "owner.*contract|owner.*identity"
                        ):
                            helper(ROOT, rom, changed)

            for constant, drifted in (
                (
                    "MOTION_SPAWN_SEQUENCE_GAP_LEFT_OWNER_PRIMARY_CLASS",
                    "drifted-left-class",
                ),
                (
                    "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_OWNER_PRIMARY_CLASS",
                    "drifted-right-class",
                ),
            ):
                with self.subTest(constant=constant):
                    with mock.patch.object(coverage_auditor, constant, drifted):
                        with self.assertRaisesRegex(
                            ValueError, "owner.*contract|owner.*identity"
                        ):
                            helper(ROOT, rom, baseline)

    def test_fails_closed_on_noncanonical_same_hash_paths(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        baseline = self._minimal_owner_baseline()
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as temp_dir:
            temp_root = Path(temp_dir)
            verifier_copy = temp_root / "verifier-copy.py"
            shutil.copy2(
                ROOT / self.LEFT_VERIFIER_PATH,
                verifier_copy,
            )
            with self.subTest(path="left-verifier-copy"):
                with mock.patch.object(
                    coverage_auditor,
                    "MOTION_SPAWN_SEQUENCE_GAP_LEFT_VERIFIER",
                    verifier_copy.relative_to(ROOT),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "canonical|path contract"
                    ):
                        helper(ROOT, self._rom(), baseline)

            right_artifact_copy = temp_root / "right-artifact-copy"
            right_artifact_copy.mkdir()
            shutil.copy2(
                ROOT / self.RIGHT_MANIFEST_PATH,
                right_artifact_copy / "manifest.json",
            )
            with self.subTest(path="right-artifact-copy"):
                with mock.patch.object(
                    coverage_auditor,
                    "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_ARTIFACT",
                    right_artifact_copy.relative_to(ROOT),
                ), mock.patch.object(
                    coverage_auditor,
                    "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_MANIFEST_PATH",
                    (right_artifact_copy / "manifest.json").relative_to(ROOT),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "canonical|path contract"
                    ):
                        helper(ROOT, self._rom(), baseline)

    def test_fails_closed_on_rom_tamper_and_symlink_or_out_of_tree_evidence(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        baseline = self._baseline()
        tampered = bytearray(self._rom())
        tampered[0x53EF2E] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM|identity|changed"):
            helper(ROOT, bytes(tampered), baseline)

        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as temp_dir:
            temp_root = Path(temp_dir)
            linked_artifact = temp_root / "artifact-link"
            linked_artifact.symlink_to(ROOT / "artifacts/battle-effect-sprite-animations-v1", target_is_directory=True)
            with mock.patch.object(
                coverage_auditor,
                "MOTION_SPAWN_SEQUENCE_GAP_LEFT_ARTIFACT",
                linked_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "artifact.*canonical|artifact.*symlink|artifact.*unsafe|invalid",
                ):
                    helper(ROOT, self._rom(), baseline)

            linked_verifier = temp_root / "verifier-link.py"
            linked_verifier.symlink_to(ROOT / "tools/verify_battle_effect_sequence_bindings.py")
            with mock.patch.object(
                coverage_auditor,
                "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_VERIFIER",
                linked_verifier.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "verifier.*canonical|verifier.*symlink|verifier.*unsafe|invalid",
                ):
                    helper(ROOT, self._rom(), baseline)

        with tempfile.TemporaryDirectory() as outside_dir:
            outside_test = Path(outside_dir) / "upstream-test-copy.py"
            shutil.copy2(ROOT / self.RIGHT_UPSTREAM_TEST_PATH, outside_test)
            with mock.patch.object(
                coverage_auditor,
                "MOTION_SPAWN_SEQUENCE_GAP_RIGHT_UPSTREAM_TEST",
                outside_test,
            ):
                with self.assertRaisesRegex(
                    ValueError, "canonical|outside|invalid"
                ):
                    helper(ROOT, self._rom(), baseline)

    def test_fails_closed_on_local_boundary_and_atomization_drift(self):
        helper = getattr(
            coverage_auditor, "_motion_spawn_sequence_alignment_gap_claims"
        )
        baseline = self._baseline()
        drift_cases = {
            "MOTION_SPAWN_SEQUENCE_GAP_RANGE": (0x53EF2D, 0x53EF30),
            "MOTION_SPAWN_TABLE_RANGE": (0x53EE98, 0x53EF24),
            "SEQUENCE_DESCRIPTOR_TABLE_RANGE": (0x53EF30, 0x53F130),
            "SEQUENCE_DESCRIPTOR_FULL_SOURCE_RANGE": (0x53EF30, 0x53F138),
            "MOTION_SPAWN_TABLE_ENTRY_COUNT": 14,
            "SEQUENCE_DESCRIPTOR_ENTRY_SIZE": 23,
        }
        for constant, drifted in drift_cases.items():
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, drifted):
                    with self.assertRaisesRegex(ValueError, "contract|denominator|identity|candidate|alignment"):
                        helper(ROOT, self._rom(), baseline)

        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("atomize_claims must not be called"),
        ):
            claims = helper(ROOT, self._rom(), self._minimal_owner_baseline())
        self.assertEqual([self.CANDIDATE_RANGE], [claim["range"] for claim in claims])

    @classmethod
    def _minimal_owner_baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("id") in {cls.LEFT_OWNER_ID, cls.RIGHT_OWNER_ID}
        ]


class SjisEmptyLookupRowsCoverageTests(unittest.TestCase):
    """RED contract for the five empty rows in the 31-row SJIS lookup table."""

    BATCH = "rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1"
    PRIMARY_CLASS = "dialogue_font_sjis_empty_lookup_rows"
    CLAIM_KIND = "dialogue_font_sjis_empty_lookup_row_bytes"
    CANDIDATE_RANGE = [0x53D714, 0x53D73C]
    CANDIDATE_GBA_RANGE = [0x0853D714, 0x0853D73C]
    CANDIDATE_BYTES_SHA256 = (
        "2c34ce1df23b838c5abf2a7f6437cca3d3067ed509ff25f11df6b11b582b51eb"
    )
    RANGE_DENOMINATOR_SHA256 = (
        "000c60331b7d3e7da1c3597ac8ef3578b5f99a4cc24c811b5be5b38a079a676f"
    )
    FULL_TABLE_RANGE = [0x53D644, 0x53D73C]
    FULL_TABLE_SHA256 = (
        "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"
    )
    EMPTY_ROW_INDICES = [26, 27, 28, 29, 30]
    EMPTY_ROW_SHA256 = (
        "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc"
    )
    EMPTY_ROW_RANGES = [
        [0x53D714, 0x53D71C],
        [0x53D71C, 0x53D724],
        [0x53D724, 0x53D72C],
        [0x53D72C, 0x53D734],
        [0x53D734, 0x53D73C],
    ]
    EVIDENCE_PATH = (
        "artifacts/rom-fixed-consumer-text-inventory-v1/"
        "fixed-consumer-text-inventory.json"
    )
    EVIDENCE_SHA256 = (
        "fd73b9dedf34aee5a4537c451f30d8479dd43f849dfb3ab81c18360a0883e461"
    )
    MANIFEST_PATH = "artifacts/rom-fixed-consumer-text-inventory-v1/manifest.json"
    MANIFEST_SHA256 = (
        "560464a6fed43de1a77c6339362dc2ef28534a7374ff976df572d05a9bad6b94"
    )
    VERIFIER_PATH = "tools/verify_rom_fixed_consumer_text_inventory.py"
    VERIFIER_SHA256 = (
        "3642d029654c7fadaaf34e354ed350e89d40d1085858aded689ad70cdcae2e44"
    )
    LOOKUP_RANGE = [0x065E80, 0x065EB6]
    LOOKUP_SHA256 = (
        "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e"
    )
    PARSER_RANGE = [0x06626C, 0x066736]
    PARSER_SHA256 = (
        "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
    )
    FONT_MANIFEST_PATH = "artifacts/dialogue-font-v2/manifest.json"
    FONT_MANIFEST_SHA256 = (
        "818684d7533ae44bbe4f56b4b6df9a6d6f69612a43ae041dfb5a7b0b0698e69c"
    )
    EVIDENCE_SELECTORS = [
        "/consumer_evidence/sjis_lookup",
        "/consumer_evidence/sjis_range_table",
        "/consumer_evidence/renderer_parser",
        "/consumer_evidence/decoded_semantics/renderer_grammar",
    ]

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
        ]

    @classmethod
    def _minimal_baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        owner_ids = {
            "dialogue-font-sjis-table",
            "dialogue-font-byte-table",
        }
        return [
            claim for claim in coverage["claims"] if claim.get("id") in owner_ids
        ]

    @staticmethod
    def _select(payload: object, selector: str) -> object:
        selected = payload
        for token in selector.lstrip("/").split("/"):
            selected = (
                selected[int(token)]
                if isinstance(selected, list)
                else selected[token]
            )
        return selected

    def test_promotes_only_the_five_verified_empty_lookup_rows(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()

        claims = helper(ROOT, rom, baseline)

        self.assertEqual(1, len(claims))
        claim = claims[0]
        self.assertEqual(self.CANDIDATE_RANGE, claim["range"])
        self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
        self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
        self.assertEqual(self.BATCH, claim["promotion_batch"])
        self.assertEqual("primary", claim["role"])
        self.assertEqual("unknown", claim["promoted_from_primary_class"])
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertEqual(40, claim["range"][1] - claim["range"][0])
        self.assertEqual(40, claim["zero_byte_count"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["bytes_sha256"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["packed_bytes_sha256"])
        self.assertEqual(
            self.RANGE_DENOMINATOR_SHA256, claim["range_denominator_sha256"]
        )
        self.assertEqual(self.FULL_TABLE_RANGE, claim["full_table_range"])
        self.assertEqual(self.FULL_TABLE_SHA256, claim["full_table_sha256"])
        self.assertEqual(31, claim["full_table_entry_count"])
        self.assertEqual(8, claim["full_table_row_stride"])
        self.assertEqual(5, claim["empty_row_count"])
        self.assertEqual([26, 31], claim["empty_row_index_range"])
        self.assertEqual(self.EMPTY_ROW_INDICES, claim["empty_row_indices"])
        self.assertEqual(self.EMPTY_ROW_RANGES, claim["empty_row_ranges"])
        self.assertEqual("<HBBI>", claim["empty_row_struct"])
        self.assertEqual([0, 0, 0, 0], claim["empty_row_value"])
        self.assertEqual(self.EMPTY_ROW_SHA256, claim["empty_row_sha256"])
        self.assertTrue(claim["all_claimed_rows_zero"])
        self.assertNotIn("all_rows_zero", claim)
        self.assertEqual([0, 31], claim["lookup_index_range"])
        self.assertEqual(
            "lower <= code < lower + range_size",
            claim["lookup_match_interval_semantics"],
        )
        self.assertEqual([0x0853D714, 0x0853D73C], claim["gba_range"])

        self.assertEqual(
            [0x53D644, 0x53D714], claim["previous_owner_range"]
        )
        self.assertEqual(
            "dialogue_font_sjis_table", claim["previous_owner_primary_class"]
        )
        self.assertEqual([0x53D73C, 0x53D74C], claim["next_owner_range"])
        self.assertEqual(
            "dialogue_font_byte_table", claim["next_owner_primary_class"]
        )
        self.assertEqual(self.FONT_MANIFEST_PATH, claim["owner_evidence_path"])
        self.assertEqual(
            self.FONT_MANIFEST_SHA256, claim["owner_evidence_sha256"]
        )
        self.assertEqual(
            "tools/verify_dialogue_font_atlases.py",
            claim["owner_independent_verifier_path"],
        )
        self.assertEqual(
            "0ff9cf6fe24d1dc8ce8e7e8050b82ce31269ca3b0044e5ce9ba07804afee7b90",
            claim["owner_independent_verifier_sha256"],
        )
        self.assertEqual(
            "/sjis_table", claim["previous_owner_evidence_selector"]
        )
        self.assertEqual("/byte_table", claim["next_owner_evidence_selector"])

        self.assertEqual(self.EVIDENCE_PATH, claim["evidence_path"])
        self.assertEqual(self.EVIDENCE_SHA256, claim["evidence_sha256"])
        self.assertEqual(self.EVIDENCE_SELECTORS, claim["evidence_selectors"])
        self.assertEqual(self.MANIFEST_PATH, claim["promotion_manifest_path"])
        self.assertEqual(self.MANIFEST_SHA256, claim["promotion_manifest_sha256"])
        self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
        self.assertEqual(
            self.VERIFIER_SHA256, claim["independent_verifier_sha256"]
        )
        self.assertEqual(self.LOOKUP_RANGE, claim["sjis_lookup_range"])
        self.assertEqual(self.LOOKUP_SHA256, claim["sjis_lookup_sha256"])
        self.assertEqual(self.PARSER_RANGE, claim["renderer_parser_range"])
        self.assertEqual(self.PARSER_SHA256, claim["renderer_parser_sha256"])

        for field in (
            "padding_claimed",
            "reserved_space_claimed",
            "reserved_author_intent_claimed",
            "free_space_claimed",
            "editable_claimed",
            "relocatable_claimed",
            "global_unreachable_claimed",
            "natural_runtime_reachability_claimed",
            "all_consumers_claimed",
            "unicode_mapping_complete_claimed",
            "safe_allocatable_space_claimed",
            "editing_or_relocation_safety_claimed",
        ):
            self.assertIs(False, claim[field])
        self.assertEqual(
            [
                "Only the five exact current-unknown empty rows at the tail of the frozen 31-row SJIS lookup table are classified.",
                "This is not a padding, reserved-space, free-space, editable, relocatable, globally unreachable, natural-runtime, all-consumers, or complete Unicode mapping claim.",
            ],
            claim["limitations"],
        )

        payload = json.loads((ROOT / claim["evidence_path"]).read_text())
        selected = [self._select(payload, selector) for selector in claim["evidence_selectors"]]
        self.assertEqual(self.LOOKUP_RANGE, selected[0]["range"])
        self.assertEqual(self.LOOKUP_SHA256, selected[0]["sha256"])
        self.assertEqual(
            {
                "entry_count": 31,
                "entry_size": 8,
                "range": self.FULL_TABLE_RANGE,
                "sha256": self.FULL_TABLE_SHA256,
            },
            {
                key: selected[1][key]
                for key in ("entry_count", "entry_size", "range", "sha256")
            },
        )
        self.assertEqual(self.PARSER_RANGE, selected[2]["range"])
        self.assertEqual(self.PARSER_SHA256, selected[2]["sha256"])
        self.assertEqual(31, selected[3]["sjis_range_count"])
        self.assertEqual(8, selected[3]["sjis_entry_size"])
        self.assertEqual("0x08065E80", selected[3]["sjis_lookup"])
        self.assertEqual("0x0853D644", selected[3]["sjis_range_table"])

        segments = atomize_claims(len(rom), baseline + claims)
        segment_at = lambda offset: next(
            item
            for item in segments
            if item["range"][0] <= offset < item["range"][1]
        )
        self.assertEqual(
            "dialogue_font_sjis_table", segment_at(0x53D713)["primary_class"]
        )
        self.assertEqual(self.PRIMARY_CLASS, segment_at(0x53D714)["primary_class"])
        self.assertEqual(self.PRIMARY_CLASS, segment_at(0x53D73B)["primary_class"])
        self.assertEqual(
            "dialogue_font_byte_table", segment_at(0x53D73C)["primary_class"]
        )

    def test_fails_closed_on_baseline_partition_overlap_and_duplicates(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()

        without_previous_owner = [
            claim for claim in baseline if claim.get("id") != "dialogue-font-sjis-table"
        ]
        with self.assertRaisesRegex(ValueError, "owner|denominator|baseline"):
            helper(ROOT, rom, without_previous_owner)

        without_next_owner = [
            claim for claim in baseline if claim.get("id") != "dialogue-font-byte-table"
        ]
        with self.assertRaisesRegex(ValueError, "owner|denominator|baseline"):
            helper(ROOT, rom, without_next_owner)

        occupied = {
            "id": "synthetic-sjis-empty-known-owner",
            "range": self.CANDIDATE_RANGE,
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "fully current unknown|existing primary"):
            helper(ROOT, rom, [*baseline, occupied])

        explicit_unknown = {
            "id": "synthetic-sjis-empty-explicit-unknown-owner",
            "range": self.CANDIDATE_RANGE,
            "role": "primary",
            "primary_class": "unknown",
            "claim_kind": "synthetic_explicit_unknown",
        }
        with self.assertRaisesRegex(ValueError, "existing primary|fully current unknown"):
            helper(ROOT, rom, [*baseline, explicit_unknown])

        partial_overlap = {
            "id": "synthetic-sjis-empty-partial-owner",
            "range": [self.CANDIDATE_RANGE[0], self.CANDIDATE_RANGE[0] + 1],
            "role": "primary",
            "primary_class": "synthetic_partial_owner",
            "claim_kind": "synthetic_partial_owner",
        }
        with self.assertRaisesRegex(ValueError, "existing primary|fully current unknown"):
            helper(ROOT, rom, [*baseline, partial_overlap])

        duplicate_batch = {
            "id": "synthetic-sjis-empty-duplicate-batch",
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "already present|duplicate"):
            helper(ROOT, rom, [*baseline, duplicate_batch])

        duplicate_kind = {
            "id": "synthetic-sjis-empty-duplicate-kind",
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": self.CLAIM_KIND,
            "promotion_batch": "synthetic_duplicate_kind",
        }
        with self.assertRaisesRegex(ValueError, "already present|duplicate"):
            helper(ROOT, rom, [*baseline, duplicate_kind])

    def test_fails_closed_on_secondary_overlay(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        secondary = {
            "id": "synthetic-sjis-empty-secondary-overlay",
            "range": self.CANDIDATE_RANGE,
            "role": "secondary",
            "claim_kind": "synthetic_secondary_overlay",
        }

        with self.assertRaisesRegex(
            ValueError,
            "whole current unknown|secondary|existing claim",
        ):
            helper(ROOT, rom, [*self._minimal_baseline(), secondary])

    def test_uses_linear_targeted_baseline_validation(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()

        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("unexpected global atomization"),
        ):
            claims = helper(ROOT, rom, self._minimal_baseline())

        self.assertEqual([self.CANDIDATE_RANGE], [claim["range"] for claim in claims])

    def test_fails_closed_on_dialogue_font_verifier_identity(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._minimal_baseline()
        verifier_spec = coverage_auditor.CONSUMER_CODE_ARTIFACTS["dialogue_font"]

        with mock.patch.dict(
            verifier_spec,
            {"verifier_sha256": "0" * 64},
        ):
            with self.assertRaisesRegex(ValueError, "dialogue font verifier"):
                helper(ROOT, rom, baseline)

        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as temp_dir:
            verifier_link = Path(temp_dir) / "dialogue-font-verifier.py"
            verifier_link.symlink_to(
                ROOT / "tools/verify_dialogue_font_atlases.py"
            )
            with mock.patch.dict(
                verifier_spec,
                {"verifier": verifier_link.relative_to(ROOT)},
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "dialogue font verifier.*symlink|dialogue font verifier.*invalid",
                ):
                    helper(ROOT, rom, baseline)

    def test_fails_closed_on_dialogue_font_artifact_tree(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._minimal_baseline()
        source_artifact = ROOT / coverage_auditor.DIALOGUE_FONT_ARTIFACT

        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as temp_dir:
            temp_root = Path(temp_dir)
            for case in ("member-symlink", "nested-member"):
                with self.subTest(case=case):
                    artifact = temp_root / case
                    shutil.copytree(source_artifact, artifact)
                    if case == "member-symlink":
                        member = artifact / "byte-full-source-2bpp.bin"
                        member.unlink()
                        member.symlink_to(source_artifact / member.name)
                    else:
                        nested = artifact / "unexpected"
                        nested.mkdir()
                        (nested / "member.bin").write_bytes(b"unexpected")
                    with mock.patch.object(
                        coverage_auditor,
                        "DIALOGUE_FONT_ARTIFACT",
                        artifact.relative_to(ROOT),
                    ):
                        with self.assertRaisesRegex(
                            ValueError,
                            "dialogue font artifact.*symlink|dialogue font artifact.*denominator|artifact files",
                        ):
                            helper(ROOT, rom, baseline)

    def test_fails_closed_on_verifier_and_bound_hash_drift(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_fixed_consumer_text_inventory",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent.*verif|verifier"):
                helper(ROOT, rom, baseline)

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_dialogue_font_atlases",
            return_value={"verified": False, "errors": ["forced failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "dialogue font|verif|verifier"):
                helper(ROOT, rom, baseline)

        for constant in (
            "FIXED_CONSUMER_TEXT_MANIFEST_SHA256",
            "FIXED_CONSUMER_TEXT_PAYLOAD_SHA256",
            "FIXED_CONSUMER_TEXT_VERIFIER_SHA256",
            "DIALOGUE_FONT_MANIFEST_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaisesRegex(
                        ValueError,
                        "manifest|payload|verifier|dialogue font|changed",
                    ):
                        helper(ROOT, rom, baseline)

        drift_offsets = {
            "full-table-boundary": 0x53D644,
            "empty-row": 0x53D714,
            "sjis-lookup": 0x065E80,
            "renderer-parser": 0x06626C,
            "byte-table-boundary": 0x53D73C,
        }
        for label, offset in drift_offsets.items():
            with self.subTest(label=label):
                mutated = bytearray(rom)
                mutated[offset] ^= 0x01
                with self.assertRaisesRegex(ValueError, "ROM|hash|identity|changed"):
                    helper(ROOT, bytes(mutated), baseline)

    def test_fails_closed_on_frozen_local_contract_constant_drift(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._minimal_baseline()
        drift_cases = {
            "SJIS_EMPTY_LOOKUP_ROWS_RANGE": (0x53D715, 0x53D73C),
            "SJIS_EMPTY_LOOKUP_ROWS_BYTES_SHA256": "0" * 64,
            "SJIS_EMPTY_LOOKUP_ROWS_RANGE_DENOMINATOR_SHA256": "0" * 64,
            "SJIS_EMPTY_LOOKUP_ROWS_FULL_TABLE_RANGE": (0x53D644, 0x53D734),
            "SJIS_EMPTY_LOOKUP_ROWS_FULL_TABLE_SHA256": "0" * 64,
            "SJIS_EMPTY_LOOKUP_ROWS_EMPTY_ROW_INDICES": (25, 26, 27, 28, 29),
            "SJIS_EMPTY_LOOKUP_ROWS_EMPTY_ROW_SHA256": "0" * 64,
            "SJIS_EMPTY_LOOKUP_ROWS_LOOKUP_RANGE": (0x065E80, 0x065EB4),
            "SJIS_EMPTY_LOOKUP_ROWS_LOOKUP_SHA256": "0" * 64,
            "SJIS_EMPTY_LOOKUP_ROWS_RENDERER_PARSER_RANGE": (
                0x06626C,
                0x06633A,
            ),
            "SJIS_EMPTY_LOOKUP_ROWS_RENDERER_PARSER_SHA256": "0" * 64,
        }

        with (
            mock.patch.object(
                coverage_auditor,
                "_fixed_consumer_text_claims",
                return_value=[],
            ),
            mock.patch.object(
                coverage_auditor,
                "_dialogue_font_claims",
                return_value=baseline,
            ),
        ):
            for constant, drifted_value in drift_cases.items():
                with self.subTest(constant=constant):
                    with mock.patch.object(
                        coverage_auditor,
                        constant,
                        drifted_value,
                    ):
                        with self.assertRaisesRegex(
                            ValueError,
                            "contract|denominator|identity|candidate|row|selector",
                        ):
                            helper(ROOT, rom, baseline)

    def test_fails_closed_on_artifact_symlink_and_member_denominator(self):
        helper = getattr(coverage_auditor, "_sjis_empty_lookup_row_claims")
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        source_artifact = ROOT / coverage_auditor.FIXED_CONSUMER_TEXT_ARTIFACT

        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as temp_dir:
            temp_root = Path(temp_dir)

            artifact_link = temp_root / "artifact-link"
            artifact_link.symlink_to(source_artifact, target_is_directory=True)
            with mock.patch.object(
                coverage_auditor,
                "FIXED_CONSUMER_TEXT_ARTIFACT",
                artifact_link.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "artifact.*symlink|artifact.*invalid"):
                    helper(ROOT, rom, baseline)

            member_symlink_artifact = temp_root / "member-symlink-artifact"
            shutil.copytree(source_artifact, member_symlink_artifact)
            member_bundle = member_symlink_artifact / "fixed-consumer-text-bytes.bin"
            member_bundle.unlink()
            member_bundle.symlink_to(source_artifact / member_bundle.name)
            with mock.patch.object(
                coverage_auditor,
                "FIXED_CONSUMER_TEXT_ARTIFACT",
                member_symlink_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "symlink|unsafe|file set|denominator"):
                    helper(ROOT, rom, baseline)

            extra_member_artifact = temp_root / "extra-member-artifact"
            shutil.copytree(source_artifact, extra_member_artifact)
            (extra_member_artifact / "unexpected.bin").write_bytes(b"unexpected")
            with mock.patch.object(
                coverage_auditor,
                "FIXED_CONSUMER_TEXT_ARTIFACT",
                extra_member_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "file set|denominator"):
                    helper(ROOT, rom, baseline)

            tampered_artifact = temp_root / "tampered-payload-artifact"
            shutil.copytree(source_artifact, tampered_artifact)
            tampered_payload = tampered_artifact / "fixed-consumer-text-inventory.json"
            payload_raw = tampered_payload.read_bytes()
            tampered_payload.write_bytes(payload_raw + b"\n")
            with (
                mock.patch.object(
                    coverage_auditor,
                    "FIXED_CONSUMER_TEXT_ARTIFACT",
                    tampered_artifact.relative_to(ROOT),
                ),
                mock.patch.object(
                    coverage_auditor,
                    "FIXED_CONSUMER_TEXT_PAYLOAD",
                    tampered_payload.relative_to(ROOT),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "payload|artifact identity|changed"):
                    helper(ROOT, rom, baseline)


class CfgInventoryV3ResidualCoverageTests(unittest.TestCase):
    KINDS = {
        "cfg_v3_reachable_instruction_bytes",
        "cfg_v3_indexed_dispatch_table_cell",
        "cfg_v3_sparse_dispatch_masked_residual_cell",
    }

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind") not in self.KINDS
        ]

    def test_promotes_exact_sparse_masked_residual_cells(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_inventory_v3_claims(ROOT, rom, self._baseline())
        residual_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_v3_sparse_dispatch_masked_residual_cell"
        ]
        self.assertEqual(
            [
                0x06EE9C,
                0x06EEA4,
                0x06EEAC,
                0x06EEB4,
                0x07BED4,
                0x07BEDC,
                0x07BEE4,
                0x07BEEC,
            ],
            [claim["range"][0] for claim in residual_claims],
        )
        self.assertEqual(32, sum(c["range"][1] - c["range"][0] for c in residual_claims))
        self.assertTrue(
            all(
                claim["primary_class"]
                == "thumb_sparse_dispatch_masked_residual_cell"
                and claim["dispatch_selected"] is False
                and claim["runtime_reachability_claimed"] is False
                and claim["target_reachability_claimed"] is False
                and claim["range_denominator_sha256"]
                == "f12097bd30174bd08f177f083fd886995edbdfc05de91c178b2d5ee96a65f9a5"
                for claim in residual_claims
            )
        )

    def test_fails_closed_on_partial_or_duplicate_baseline(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        synthetic_known = {
            "id": "synthetic-v3-residual-known-overlap",
            "range": [0x06EE9C, 0x06EE9D],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "partially unknown"):
            _cfg_inventory_v3_claims(
                ROOT, rom, [*self._baseline(), synthetic_known]
            )
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        duplicate = {
            "id": "synthetic-v3-residual-duplicate",
            "range": [0, 1],
            "role": "secondary",
            "primary_class": "synthetic_duplicate",
            "claim_kind": "cfg_v3_sparse_dispatch_masked_residual_cell",
        }
        with self.assertRaisesRegex(ValueError, "pre-v3 baseline"):
            _cfg_inventory_v3_claims(ROOT, rom, [*coverage["claims"], duplicate])


class CfgProvenRootsV3CoverageTests(unittest.TestCase):
    def test_promotes_exact_110_unknown_bytes_without_reclaiming_producers(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "cfg_proven_roots_v3_reachable_instruction_bytes"
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_proven_roots_v3_claims(ROOT, rom, prior)
        self.assertEqual(8, len(claims))
        self.assertEqual(
            110,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertTrue(
            all(
                claim["claim_kind"]
                == "cfg_proven_roots_v3_reachable_instruction_bytes"
                and claim["promoted_from_primary_class"] == "unknown"
                for claim in claims
            )
        )
        for producer_start in (0x74192, 0x74836):
            self.assertFalse(
                any(
                    claim["range"][0] < producer_start + 4
                    and producer_start < claim["range"][1]
                    for claim in claims
                )
            )


class CfgProvenRootsV4CoverageTests(unittest.TestCase):
    def test_promotes_exact_1044_unknown_bytes_without_reclaiming_producers(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "cfg_proven_roots_v4_reachable_instruction_bytes"
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_proven_roots_v4_claims(ROOT, rom, prior)
        self.assertEqual(118, len(claims))
        self.assertEqual(
            1_044,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertTrue(
            all(
                claim["claim_kind"]
                == "cfg_proven_roots_v4_reachable_instruction_bytes"
                and claim["promoted_from_primary_class"] == "unknown"
                for claim in claims
            )
        )
        for producer_start in (0x73696, 0x736C4, 0x7444E, 0x749CE):
            self.assertFalse(
                any(
                    claim["range"][0] < producer_start + 4
                    and producer_start < claim["range"][1]
                    for claim in claims
                )
            )


class CfgProvenRootsV5CoverageTests(unittest.TestCase):
    def test_promotes_exact_1252_unknown_bytes_without_reclaiming_producers(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        prior = [claim for claim in coverage["claims"] if claim.get("claim_kind") != "cfg_proven_roots_v5_reachable_instruction_bytes"]
        claims = _cfg_proven_roots_v5_claims(ROOT, (ROOT / "rom/base.gba").read_bytes(), prior)
        self.assertEqual(124, len(claims))
        self.assertEqual(1_252, sum(c["range"][1] - c["range"][0] for c in claims))
        for producer_start in (0x736DE, 0x73702, 0x73780):
            self.assertFalse(any(c["range"][0] < producer_start + 4 and producer_start < c["range"][1] for c in claims))


class CfgProvenRootsV6CoverageTests(unittest.TestCase):
    def test_promotes_exact_current_unknown_intersection(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "cfg_proven_roots_v6_reachable_instruction_bytes"
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_proven_roots_v6_claims(ROOT, rom, prior)
        self.assertEqual(
            25_926,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )


class CfgProvenRootsV7CoverageTests(unittest.TestCase):
    def test_promotes_exact_current_unknown_intersection(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        v7_kinds = {
            "cfg_proven_roots_v7_reachable_instruction_bytes",
            "cfg_proven_roots_v7_indexed_dispatch_table_cell",
        }
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind") not in v7_kinds
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_proven_roots_v7_claims(ROOT, rom, prior)
        code_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_proven_roots_v7_reachable_instruction_bytes"
        ]
        table_claims = [
            claim
            for claim in claims
            if claim["claim_kind"]
            == "cfg_proven_roots_v7_indexed_dispatch_table_cell"
        ]
        self.assertEqual(38, len(code_claims))
        self.assertEqual(
            332,
            sum(claim["range"][1] - claim["range"][0] for claim in code_claims),
        )
        self.assertEqual(9, len(table_claims))
        self.assertEqual(
            36,
            sum(claim["range"][1] - claim["range"][0] for claim in table_claims),
        )
        self.assertEqual(
            [
                0x06E868,
                0x06E86C,
                0x06E870,
                0x06E874,
                0x06E878,
                0x06E87C,
                0x06E880,
                0x0928F4,
                0x0928F8,
            ],
            [claim["range"][0] for claim in table_claims],
        )
        self.assertTrue(
            all(
                claim["primary_class"] == "thumb_indexed_dispatch_table_cell"
                and claim["dispatch_selected"] is True
                and claim["runtime_reachability_claimed"] is False
                and claim["target_reachability_claimed"] is False
                and claim["range_denominator_sha256"]
                == "f01bf5984428f386feeed6b009913a5775ee6f23d41101a3ea423fb4047c6e9d"
                for claim in table_claims
            )
        )
        self.assertTrue(
            all(claim["promoted_from_primary_class"] == "unknown" for claim in claims)
        )

    def test_dispatch_cells_fail_closed_on_partial_or_duplicate_baseline(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        rom = (ROOT / "rom/base.gba").read_bytes()
        v7_kinds = {
            "cfg_proven_roots_v7_reachable_instruction_bytes",
            "cfg_proven_roots_v7_indexed_dispatch_table_cell",
        }
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind") not in v7_kinds
        ]
        synthetic_known = {
            "id": "synthetic-v7-table-known-overlap",
            "range": [0x06E868, 0x06E869],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "partially unknown"):
            _cfg_proven_roots_v7_claims(ROOT, rom, [*prior, synthetic_known])
        with self.assertRaisesRegex(ValueError, "pre-v7 baseline"):
            _cfg_proven_roots_v7_claims(ROOT, rom, coverage["claims"])


class CfgProvenRootsV8CoverageTests(unittest.TestCase):
    def test_promotes_only_twenty_verified_unknown_block_pieces(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "cfg_proven_roots_v8_reachable_instruction_bytes"
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_proven_roots_v8_claims(ROOT, rom, prior)
        self.assertEqual(20, len(claims))
        self.assertEqual(
            246,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertTrue(
            all(
                claim["promoted_from_primary_class"] == "unknown"
                and claim["primary_class"]
                == "armv4t_cfg_proven_roots_v8_reachable_thumb_code"
                and claim["source_block_count"] == 1
                and claim["range"] == claim["source_blocks"][0]["range"]
                for claim in claims
            )
        )
        self.assertFalse(
            any(
                claim["range"][0] < 0x08BE60
                and 0x08BE5C < claim["range"][1]
                for claim in claims
            )
        )
        for gap_start, gap_end in (
            (0x08BA0E, 0x08BA18),
            (0x08BA6C, 0x08BA7C),
        ):
            self.assertFalse(
                any(
                    claim["range"][0] < gap_end
                    and gap_start < claim["range"][1]
                    for claim in claims
                )
            )


class CfgProvenRootsV9CoverageTests(unittest.TestCase):
    def test_auditor_binds_the_exact_promotion_manifest_contract(self):
        manifest_path = ROOT / "artifacts/rom-cfg-proven-roots-v9/manifest.json"
        payload_path = (
            ROOT
            / "artifacts/rom-cfg-proven-roots-v9/rom-cfg-proven-roots-v9.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        self.assertEqual(
            "1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b",
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            "fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b",
            hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            43_782,
            coverage_auditor.CFG_PROVEN_ROOTS_V9_MANIFEST_SIZE,
        )
        self.assertEqual(99_730, coverage_auditor.CFG_PROVEN_ROOTS_V9_PAYLOAD_SIZE)
        self.assertEqual(
            "1914d6244ceaa7791cb4c77d97143151b4f28183ea857c052c9c51d3c8a09e6b",
            coverage_auditor.CFG_PROVEN_ROOTS_V9_MANIFEST_SHA256,
        )
        self.assertEqual(
            "fb961c6d0ba5cdb56c016a5d10b149d87e5ce9158bcb1e6e9deae8664c46555b",
            coverage_auditor.CFG_PROVEN_ROOTS_V9_PAYLOAD_SHA256,
        )
        self.assertEqual(
            "b75ed5bad517fb08ebf2ae08d336c1dcee6ab334c4927559f41a2fcfad399935",
            coverage_auditor.CFG_PROVEN_ROOTS_V9_VERIFIER_SHA256,
        )
        self.assertEqual(
            {
                "artifact_schema",
                "artifact_status",
                "baseline_cross_edge_count",
                "coverage_baseline",
                "extension_summary",
                "files",
                "frozen_baseline",
                "implementation",
                "opaque_return_exit_count",
                "producer",
                "producer_summary",
                "promotion",
                "rom",
                "root_count",
                "schema",
                "scope",
                "source",
                "verifier",
            },
            set(manifest),
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V9_COVERAGE_BASELINE,
            manifest["coverage_baseline"],
        )
        self.assertEqual(
            "058f90da96cf556a2b406fbea2952435bbd64c302654657c4981841587fd7aeb",
            manifest["coverage_baseline"][
                "promotion_block_range_denominator_sha256"
            ],
        )
        self.assertEqual(
            [block["range"] for block in payload["extension"]["blocks"]],
            manifest["coverage_baseline"]["promotion_block_ranges"],
        )
        self.assertEqual(
            628,
            sum(
                end - start
                for start, end in manifest["coverage_baseline"][
                    "promotion_block_ranges"
                ]
            ),
        )

    def test_promotes_all_sixty_two_verified_unknown_blocks_without_producers(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "cfg_proven_roots_v9_reachable_instruction_bytes"
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = _cfg_proven_roots_v9_claims(ROOT, rom, prior)
        self.assertEqual(62, len(claims))
        self.assertEqual(
            628,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertTrue(
            all(
                claim["promoted_from_primary_class"] == "unknown"
                and claim["primary_class"]
                == "armv4t_cfg_proven_roots_v9_reachable_thumb_code"
                and claim["source_block_count"] == 1
                and claim["range"] == claim["source_blocks"][0]["range"]
                and claim["fixed_root_count"] == 8
                and claim["fixed_direct_producer_count"] == 11
                and claim["controller_source_count"] == 9
                and claim["excluded_source_count"] == 2
                and claim["opaque_return_exit_count"] == 7
                for claim in claims
            )
        )
        merged = []
        for claim in sorted(claims, key=lambda item: item["range"]):
            start, end = claim["range"]
            if merged and merged[-1][1] == start:
                merged[-1][1] = end
            else:
                merged.append([start, end])
        self.assertEqual(
            [
                [0x06C010, 0x06C09E],
                [0x06C308, 0x06C364],
                [0x06C40C, 0x06C418],
                [0x06D46C, 0x06D49A],
                [0x070DD8, 0x070DEE],
                [0x073000, 0x073048],
                [0x075350, 0x0753F2],
                [0x0753F8, 0x075436],
                [0x07543C, 0x07544E],
            ],
            merged,
        )
        producer_offsets = {
            0x07363E,
            0x07365A,
            0x07367C,
            0x073680,
            0x0736A4,
            0x0736E4,
            0x073D92,
            0x07416C,
            0x074184,
            0x07445C,
            0x075058,
        }
        self.assertFalse(
            any(
                start < claim["range"][1] and claim["range"][0] < start + 4
                for start in producer_offsets
                for claim in claims
            )
        )
        segments = atomize_claims(len(rom), prior)

        def class_at(offset: int) -> str:
            return next(
                segment["primary_class"]
                for segment in segments
                if segment["range"][0] <= offset < segment["range"][1]
            )

        self.assertEqual("unknown", class_at(0x0736A4))
        self.assertEqual("unknown", class_at(0x07445C))
        for offset in producer_offsets - {0x0736A4, 0x07445C}:
            self.assertEqual(
                "armv4t_cfg_battle_controller_reachable_thumb_code",
                class_at(offset),
            )

    def test_rejects_current_known_overlap_and_an_already_applied_batch(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        prior = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "cfg_proven_roots_v9_reachable_instruction_bytes"
        ]
        rom = (ROOT / "rom/base.gba").read_bytes()
        synthetic_known = {
            "id": "synthetic-v9-current-known-overlap",
            "range": [0x06C010, 0x06C011],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "not fully current unknown"):
            _cfg_proven_roots_v9_claims(ROOT, rom, [*prior, synthetic_known])
        with self.assertRaisesRegex(ValueError, "requires a pre-v9 baseline"):
            _cfg_proven_roots_v9_claims(ROOT, rom, coverage["claims"])


class CfgProvenRootsV10CoverageTests(unittest.TestCase):
    BATCH = "cfg-proven-roots-v10"
    CODE_KIND = "cfg_proven_roots_v10_reachable_instruction_bytes"
    LITERAL_KIND = "cfg_proven_roots_v10_consumed_literal_bytes"
    CODE_CLASS = "armv4t_cfg_proven_roots_v10_reachable_thumb_code"
    LITERAL_CLASS = "armv4t_cfg_proven_roots_v10_consumed_literal_pool"
    CODE_RANGES = [
        [0x08B278, 0x08B284],
        [0x08B284, 0x08B290],
        [0x08B290, 0x08B298],
        [0x08B298, 0x08B2A4],
        [0x08B2A4, 0x08B2B0],
        [0x08B2B4, 0x08B2BC],
        [0x08B2BC, 0x08B2C4],
    ]
    LITERAL_RANGES = [[0x08B2B0, 0x08B2B4], [0x08B2C4, 0x08B2C8]]

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") not in {self.CODE_KIND, self.LITERAL_KIND}
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return coverage_auditor._cfg_proven_roots_v10_claims(
            ROOT,
            (ROOT / "rom/base.gba").read_bytes(),
            self._baseline() if baseline is None else baseline,
        )

    def test_auditor_binds_exact_accepted_artifact_and_verifier_receipt(self):
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v10"
        manifest_path = artifact / "manifest.json"
        payload_path = artifact / "rom-cfg-proven-roots-v10.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(227_848, coverage_auditor.CFG_PROVEN_ROOTS_V10_MANIFEST_SIZE)
        self.assertEqual(220_851, coverage_auditor.CFG_PROVEN_ROOTS_V10_PAYLOAD_SIZE)
        self.assertEqual(
            "7bc6a70cb8409b44075df6e1031b9d80bdb19898605735dedd2a2acf9d495991",
            coverage_auditor.CFG_PROVEN_ROOTS_V10_MANIFEST_SHA256,
        )
        self.assertEqual(
            "5edad0689b630e68c6ee304aac2f56e3d5c83e65ee7c2c7a7308e0fd980fd50e",
            coverage_auditor.CFG_PROVEN_ROOTS_V10_PAYLOAD_SHA256,
        )
        self.assertEqual(
            "88606960fdede458a25aebc10f6e78766d16fe5cf4b08f85c3cc1e7ec1203ba3",
            coverage_auditor.CFG_PROVEN_ROOTS_V10_VERIFIER_SHA256,
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V10_MANIFEST_SHA256,
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V10_PAYLOAD_SHA256,
            hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("rom-cfg-proven-roots-v10", manifest["artifact_schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            {"rom-cfg-proven-roots-v10.json": coverage_auditor.CFG_PROVEN_ROOTS_V10_PAYLOAD_SHA256},
            manifest["files"],
        )
        self.assertEqual(0, manifest["verifier"]["exit_code"])
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V10_EXPECTED_REPORT,
            manifest["verifier"]["report"],
        )

    def test_promotes_exact_seven_code_and_two_literal_claims(self):
        claims = self._claims()
        code = [claim for claim in claims if claim["claim_kind"] == self.CODE_KIND]
        literals = [claim for claim in claims if claim["claim_kind"] == self.LITERAL_KIND]
        self.assertEqual(9, len(claims))
        self.assertEqual(7, len(code))
        self.assertEqual(2, len(literals))
        self.assertEqual(72, sum(end - start for start, end in (claim["range"] for claim in code)))
        self.assertEqual(8, sum(end - start for start, end in (claim["range"] for claim in literals)))
        self.assertEqual(self.CODE_RANGES, [claim["range"] for claim in code])
        self.assertEqual(self.LITERAL_RANGES, [claim["range"] for claim in literals])
        self.assertEqual(
            sorted(self.CODE_RANGES + self.LITERAL_RANGES),
            [claim["range"] for claim in sorted(claims, key=lambda item: item["range"])],
        )
        self.assertTrue(
            all(
                claim["role"] == "primary"
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["promotion_batch"] == self.BATCH
                for claim in claims
            )
        )
        self.assertTrue(all(claim["primary_class"] == self.CODE_CLASS for claim in code))
        self.assertTrue(all(claim["primary_class"] == self.LITERAL_CLASS for claim in literals))
        self.assertTrue(all(claim["mode"] == "thumb" for claim in code))
        self.assertEqual([0x08B294, 0x08B2B8], [claim["ldr_file_offset"] for claim in literals])
        for producer in (0x08B428, 0x08B4F8, 0x08B640):
            self.assertFalse(
                any(start <= producer < end for start, end in (claim["range"] for claim in claims))
            )

    def test_rejects_known_overlap_already_applied_batch_and_identity_drift(self):
        baseline = self._baseline()
        synthetic_known = {
            "id": "synthetic-v10-known-overlap",
            "range": [0x08B278, 0x08B279],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, synthetic_known])
        synthetic_batch = {
            "id": "synthetic-v10-duplicate-batch",
            "range": [0x08B278, 0x08B284],
            "role": "primary",
            "primary_class": "synthetic_duplicate_batch",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "pre-v10|already"):
            self._claims([*baseline, synthetic_batch])
        synthetic_kind = {
            "id": "synthetic-v10-duplicate-kind",
            "range": [0x08B278, 0x08B284],
            "role": "primary",
            "primary_class": self.CODE_CLASS,
            "claim_kind": self.CODE_KIND,
        }
        with self.assertRaisesRegex(ValueError, "pre-v10|already"):
            self._claims([*baseline, synthetic_kind])
        for constant in (
            "CFG_PROVEN_ROOTS_V10_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_V10_PAYLOAD_SHA256",
            "CFG_PROVEN_ROOTS_V10_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64, create=True):
                    with self.assertRaises(ValueError):
                        self._claims()

    def test_rejects_independent_verifier_failure_and_code_range_drift(self):
        with mock.patch.object(
            coverage_auditor,
            "verify_rom_cfg_proven_roots_v10",
            return_value={
                "schema": "rom-cfg-proven-roots-verification-v10",
                "verified": False,
                "errors": ["forced verifier failure"],
            },
        ):
            with self.assertRaisesRegex(ValueError, "independent verification failed"):
                self._claims()

        drifted_ranges = [list(value) for value in self.CODE_RANGES]
        drifted_ranges[4] = [0x08B2A4, 0x08B2B4]
        with mock.patch.object(
            coverage_auditor,
            "CFG_PROVEN_ROOTS_V10_CODE_RANGES",
            drifted_ranges,
        ):
            with self.assertRaisesRegex(ValueError, "code block identity changed"):
                self._claims()

        out_of_envelope_ranges = [list(value) for value in self.CODE_RANGES]
        out_of_envelope_ranges[-1] = [0x08B2C8, 0x08B2CA]
        with mock.patch.object(
            coverage_auditor,
            "CFG_PROVEN_ROOTS_V10_CODE_RANGES",
            out_of_envelope_ranges,
        ):
            with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
                self._claims()


class CfgProvenRootsV11CoverageTests(unittest.TestCase):
    BATCH = "cfg-proven-roots-v11"
    CODE_KIND = "cfg_proven_roots_v11_reachable_instruction_bytes"
    CODE_CLASS = "armv4t_cfg_proven_roots_v11_reachable_thumb_code"
    CODE_RANGES = [
        [0x0633C0, 0x0633D0],
        [0x0633D0, 0x0633DE],
        [0x0633DE, 0x0633E8],
        [0x0633E8, 0x0633EE],
        [0x0633EE, 0x0633F8],
        [0x0633F8, 0x0633FE],
    ]

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") != self.CODE_KIND
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return coverage_auditor._cfg_proven_roots_v11_claims(
            ROOT,
            (ROOT / "rom/base.gba").read_bytes(),
            self._baseline() if baseline is None else baseline,
        )

    def test_auditor_binds_exact_accepted_artifact_and_verifier_receipt(self):
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v11"
        manifest_path = artifact / "manifest.json"
        payload_path = artifact / "rom-cfg-proven-roots-v11.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(463_680, coverage_auditor.CFG_PROVEN_ROOTS_V11_MANIFEST_SIZE)
        self.assertEqual(456_466, coverage_auditor.CFG_PROVEN_ROOTS_V11_PAYLOAD_SIZE)
        self.assertEqual(
            "3c0a4ae64b82a417e0577d28ea82b5f774ea3150d210ed4c117414938bc2b0d4",
            coverage_auditor.CFG_PROVEN_ROOTS_V11_MANIFEST_SHA256,
        )
        self.assertEqual(
            "4d62230f3477abd29ac24790eb9fc98870c95f79e1da8df4e49783fbf6d18480",
            coverage_auditor.CFG_PROVEN_ROOTS_V11_PAYLOAD_SHA256,
        )
        self.assertEqual(
            "4dbcd849eba9b674ed9e3739e0ce8be278a4347b7c113a98d834ac2e4a82c563",
            coverage_auditor.CFG_PROVEN_ROOTS_V11_VERIFIER_SHA256,
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V11_MANIFEST_SHA256,
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V11_PAYLOAD_SHA256,
            hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("rom-cfg-proven-roots-v11", manifest["artifact_schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            {"rom-cfg-proven-roots-v11.json": coverage_auditor.CFG_PROVEN_ROOTS_V11_PAYLOAD_SHA256},
            manifest["files"],
        )
        self.assertEqual(9, manifest["producer_denominator"]["scan"]["matching_producer_count"])
        self.assertEqual(
            [
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "accepted_fixed_tick_callback_closure",
                "excluded_unproven_source",
            ],
            [item["status"] for item in manifest["producer_denominator"]["producers"]],
        )
        self.assertEqual(0x080D7C, manifest["producer_denominator"]["producers"][-1]["file_offset"])
        self.assertEqual(0, manifest["verifier"]["exit_code"])
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V11_EXPECTED_REPORT,
            manifest["verifier"]["report"],
        )

    def test_promotes_only_exact_six_target_blocks(self):
        claims = self._claims()
        self.assertEqual(6, len(claims))
        self.assertEqual(self.CODE_RANGES, [claim["range"] for claim in claims])
        self.assertEqual(
            62,
            sum(end - start for start, end in (claim["range"] for claim in claims)),
        )
        self.assertTrue(
            all(
                claim["role"] == "primary"
                and claim["primary_class"] == self.CODE_CLASS
                and claim["claim_kind"] == self.CODE_KIND
                and claim["mode"] == "thumb"
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["promotion_batch"] == self.BATCH
                and claim["raw_target_producer_count"] == 9
                and claim["accepted_target_producer_count"] == 8
                and claim["excluded_unproven_source_count"] == 1
                for claim in claims
            )
        )
        for excluded in (0x080D7C, 0x062788):
            self.assertFalse(
                any(start <= excluded < end for start, end in (claim["range"] for claim in claims))
            )
        segments = coverage_auditor.atomize_claims(
            6_291_456, [*self._baseline(), *claims]
        )
        excluded_segment = next(
            segment
            for segment in segments
            if segment["range"][0] <= 0x080D7C < segment["range"][1]
        )
        self.assertEqual("unknown", excluded_segment["primary_class"])
        self.assertEqual([], excluded_segment["primary_claim_ids"])

    def test_rejects_target_rom_tamper_before_promotion(self):
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x0633C0] ^= 0x01
        with self.assertRaisesRegex(ValueError, "ROM identity changed"):
            coverage_auditor._cfg_proven_roots_v11_claims(
                ROOT,
                bytes(rom),
                self._baseline(),
            )

    def test_rejects_known_overlap_already_applied_batch_and_identity_drift(self):
        baseline = self._baseline()
        synthetic_known = {
            "id": "synthetic-v11-known-overlap",
            "range": [0x0633C0, 0x0633C1],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, synthetic_known])
        synthetic_batch = {
            "id": "synthetic-v11-duplicate-batch",
            "range": [0x0633C0, 0x0633D0],
            "role": "primary",
            "primary_class": "synthetic_duplicate_batch",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "pre-v11|already"):
            self._claims([*baseline, synthetic_batch])
        synthetic_kind = {
            "id": "synthetic-v11-duplicate-kind",
            "range": [0x0633C0, 0x0633D0],
            "role": "primary",
            "primary_class": self.CODE_CLASS,
            "claim_kind": self.CODE_KIND,
        }
        with self.assertRaisesRegex(ValueError, "pre-v11|already"):
            self._claims([*baseline, synthetic_kind])
        for constant in (
            "CFG_PROVEN_ROOTS_V11_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_V11_PAYLOAD_SHA256",
            "CFG_PROVEN_ROOTS_V11_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64, create=True):
                    with self.assertRaises(ValueError):
                        self._claims()

    def test_rejects_independent_verifier_failure_and_code_range_drift(self):
        with mock.patch.object(
            coverage_auditor,
            "verify_rom_cfg_proven_roots_v11",
            return_value={
                "schema": "rom-cfg-proven-roots-verification-v11",
                "verified": False,
                "errors": ["forced verifier failure"],
            },
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification failed"):
                self._claims()

        drifted_ranges = [list(value) for value in self.CODE_RANGES]
        drifted_ranges[4] = [0x0633EE, 0x0633FA]
        with mock.patch.object(
            coverage_auditor,
            "CFG_PROVEN_ROOTS_V11_CODE_RANGES",
            drifted_ranges,
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "code block identity changed"):
                self._claims()

        out_of_envelope_ranges = [list(value) for value in self.CODE_RANGES]
        out_of_envelope_ranges[-1] = [0x0633F8, 0x063460]
        with mock.patch.object(
            coverage_auditor,
            "CFG_PROVEN_ROOTS_V11_CODE_RANGES",
            out_of_envelope_ranges,
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
                self._claims()


class CfgProvenRootsV12CoverageTests(unittest.TestCase):
    BATCH = "cfg-proven-roots-v12"
    CODE_KIND = "cfg_proven_roots_v12_reachable_instruction_bytes"
    LITERAL_KIND = "cfg_proven_roots_v12_consumed_literal_bytes"
    CODE_CLASS = "armv4t_cfg_proven_roots_v12_reachable_thumb_code"
    LITERAL_CLASS = "armv4t_cfg_proven_roots_v12_consumed_literal_pool"
    CODE_RANGES = [
        [0x064478, 0x0644C2],
        [0x0644D8, 0x06450A],
        [0x064518, 0x064558],
        [0x064574, 0x06462C],
    ]
    LITERAL_RANGES = [
        [0x0644C4, 0x0644D8],
        [0x06450C, 0x064518],
        [0x064558, 0x064574],
        [0x06462C, 0x064670],
    ]
    HOLES = [[0x0644C2, 0x0644C4], [0x06450A, 0x06450C]]

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") not in {self.CODE_KIND, self.LITERAL_KIND}
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return coverage_auditor._cfg_proven_roots_v12_claims(
            ROOT,
            (ROOT / "rom/base.gba").read_bytes(),
            self._baseline() if baseline is None else baseline,
        )

    def test_auditor_binds_exact_accepted_artifact_and_verifier_receipt(self):
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v12"
        manifest_path = artifact / "manifest.json"
        payload_path = artifact / "rom-cfg-proven-roots-v12.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(335_832, coverage_auditor.CFG_PROVEN_ROOTS_V12_MANIFEST_SIZE)
        self.assertEqual(327_605, coverage_auditor.CFG_PROVEN_ROOTS_V12_PAYLOAD_SIZE)
        self.assertEqual(
            "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
            coverage_auditor.CFG_PROVEN_ROOTS_V12_MANIFEST_SHA256,
        )
        self.assertEqual(
            "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
            coverage_auditor.CFG_PROVEN_ROOTS_V12_PAYLOAD_SHA256,
        )
        self.assertEqual(
            "1043291dfb16b90ef025242b976a4bf89a6a0173a0ac4904fc3534d625acbede",
            coverage_auditor.CFG_PROVEN_ROOTS_V12_VERIFIER_SHA256,
        )
        self.assertEqual(
            "ee1d50f3018b5d78d652eb5ed6d1f7108670669b60e5518b9956df987b60275a",
            coverage_auditor.CFG_PROVEN_ROOTS_V12_BUNDLE_VERIFIER_SHA256,
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V12_MANIFEST_SHA256,
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V12_PAYLOAD_SHA256,
            hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("rom-cfg-proven-roots-v12", manifest["artifact_schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            {
                "rom-cfg-proven-roots-v12.json": {
                    "size": coverage_auditor.CFG_PROVEN_ROOTS_V12_PAYLOAD_SIZE,
                    "sha256": coverage_auditor.CFG_PROVEN_ROOTS_V12_PAYLOAD_SHA256,
                }
            },
            manifest["files"],
        )
        self.assertEqual(0, manifest["verifier"]["exit_code"])
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V12_EXPECTED_REPORT,
            manifest["verifier"]["report"],
        )
        auditor_source = (ROOT / "tools/audit_rom_byte_coverage.py").read_text()
        self.assertNotIn(
            "from tools.verify_rom_cfg_proven_roots_v12_bundle import",
            auditor_source,
        )

    def test_promotes_exact_four_code_and_four_literal_ranges_but_not_holes(self):
        claims = self._claims()
        code = [claim for claim in claims if claim["claim_kind"] == self.CODE_KIND]
        literals = [claim for claim in claims if claim["claim_kind"] == self.LITERAL_KIND]
        self.assertEqual(8, len(claims))
        self.assertEqual(self.CODE_RANGES, [claim["range"] for claim in code])
        self.assertEqual(self.LITERAL_RANGES, [claim["range"] for claim in literals])
        self.assertEqual(372, sum(end - start for start, end in (claim["range"] for claim in code)))
        self.assertEqual(128, sum(end - start for start, end in (claim["range"] for claim in literals)))
        self.assertTrue(all(claim["primary_class"] == self.CODE_CLASS and claim["mode"] == "thumb" for claim in code))
        self.assertTrue(all(claim["primary_class"] == self.LITERAL_CLASS for claim in literals))
        self.assertTrue(
            all(
                claim["role"] == "primary"
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["promotion_batch"] == self.BATCH
                and claim["independent_verifier_path"]
                == "tools/verify_rom_cfg_proven_roots_v12_bundle.py"
                and claim["independent_verifier_sha256"]
                == coverage_auditor.CFG_PROVEN_ROOTS_V12_BUNDLE_VERIFIER_SHA256
                for claim in claims
            )
        )
        segments = coverage_auditor.atomize_claims(6_291_456, [*self._baseline(), *claims])
        for hole_start, hole_end in self.HOLES:
            hole_segments = [
                segment
                for segment in segments
                if hole_start < segment["range"][1] and segment["range"][0] < hole_end
            ]
            self.assertEqual([[hole_start, hole_end]], [segment["range"] for segment in hole_segments])
            self.assertTrue(all(segment["primary_class"] == "unknown" for segment in hole_segments))

    def test_rejects_known_overlap_duplicate_batch_and_identity_drift(self):
        baseline = self._baseline()
        synthetic_known = {
            "id": "synthetic-v12-known-overlap",
            "range": [0x064478, 0x064479],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, synthetic_known])
        synthetic_batch = {
            "id": "synthetic-v12-duplicate-batch",
            "range": [0x064478, 0x0644C2],
            "role": "primary",
            "primary_class": "synthetic_duplicate_batch",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "pre-v12|already"):
            self._claims([*baseline, synthetic_batch])
        for constant in (
            "CFG_PROVEN_ROOTS_V12_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_V12_PAYLOAD_SHA256",
            "CFG_PROVEN_ROOTS_V12_VERIFIER_SHA256",
            "CFG_PROVEN_ROOTS_V12_BUNDLE_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()

    def test_rejects_verifier_failure_rom_tamper_and_range_drift(self):
        with mock.patch.object(
            coverage_auditor,
            "_run_cfg_proven_roots_v12_bundle_verifier",
            return_value={
                "schema": "rom-cfg-proven-roots-v12-bundle-verification-v1",
                "verified": False,
                "errors": ["forced verifier failure"],
            },
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification failed"):
                self._claims()
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x064478] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity changed"):
            coverage_auditor._cfg_proven_roots_v12_claims(ROOT, bytes(rom), self._baseline())
        drifted = [list(value) for value in self.CODE_RANGES]
        drifted[0] = [0x064478, 0x0644C4]
        with mock.patch.object(
            coverage_auditor, "CFG_PROVEN_ROOTS_V12_CODE_RANGES", drifted, create=True
        ), self.assertRaisesRegex(ValueError, "current unknown|target code range|promotion"):
            self._claims()

    def test_auditor_executes_the_anchored_bundle_bytes_via_stdin(self):
        frozen_source = b"raise AssertionError('subprocess mock should intercept')\n"
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                coverage_auditor.CFG_PROVEN_ROOTS_V12_BUNDLE_EXPECTED_REPORT
            ).encode("utf-8"),
            stderr=b"",
        )
        with mock.patch.object(
            coverage_auditor.subprocess,
            "run",
            return_value=completed,
        ) as run:
            report = coverage_auditor._run_cfg_proven_roots_v12_bundle_verifier(
                ROOT,
                frozen_source,
                ROOT / coverage_auditor.CFG_PROVEN_ROOTS_V12_BUNDLE_VERIFIER,
            )

        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V12_BUNDLE_EXPECTED_REPORT,
            report,
        )
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual([sys.executable, "-I", "-S", "-c"], command[:4])
        self.assertIn("sys.stdin.buffer.read()", command[4])
        self.assertEqual(frozen_source, kwargs["input"])
        self.assertNotIn("text", kwargs)
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])


class CfgProvenRootsV13CoverageTests(unittest.TestCase):
    BATCH = "cfg-proven-roots-v13"
    CODE_KIND = "cfg_proven_roots_v13_reachable_instruction_bytes"
    LITERAL_KIND = "cfg_proven_roots_v13_consumed_literal_bytes"
    CODE_CLASS = "armv4t_cfg_proven_roots_v13_reachable_thumb_code"
    LITERAL_CLASS = "armv4t_cfg_proven_roots_v13_consumed_literal_pool"
    CODE_RANGES = [
        [0x0651F8, 0x06523C],
        [0x06524C, 0x0652DE],
        [0x065308, 0x06536A],
    ]
    LITERAL_RANGES = [
        [0x06523C, 0x06524C],
        [0x0652E0, 0x065308],
        [0x06536C, 0x065384],
    ]
    HOLES = [[0x0652DE, 0x0652E0], [0x06536A, 0x06536C]]

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") not in {self.CODE_KIND, self.LITERAL_KIND}
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return coverage_auditor._cfg_proven_roots_v13_claims(
            ROOT,
            (ROOT / "rom/base.gba").read_bytes(),
            self._baseline() if baseline is None else baseline,
        )

    def test_auditor_binds_exact_accepted_artifact_and_verifier_receipt(self):
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v13"
        manifest_path = artifact / "manifest.json"
        payload_path = artifact / "rom-cfg-proven-roots-v13.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(321_520, coverage_auditor.CFG_PROVEN_ROOTS_V13_MANIFEST_SIZE)
        self.assertEqual(312_804, coverage_auditor.CFG_PROVEN_ROOTS_V13_PAYLOAD_SIZE)
        self.assertEqual(
            "589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133",
            coverage_auditor.CFG_PROVEN_ROOTS_V13_MANIFEST_SHA256,
        )
        self.assertEqual(
            "45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b",
            coverage_auditor.CFG_PROVEN_ROOTS_V13_PAYLOAD_SHA256,
        )
        self.assertEqual(
            "a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7",
            coverage_auditor.CFG_PROVEN_ROOTS_V13_VERIFIER_SHA256,
        )
        self.assertEqual(
            "0fe1b8c1d1aa1a191d8bc7e210db952551e4b54aceeed1c13aecd9db6c12c272",
            coverage_auditor.CFG_PROVEN_ROOTS_V13_BUNDLE_VERIFIER_SHA256,
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V13_MANIFEST_SHA256,
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V13_PAYLOAD_SHA256,
            hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        )
        self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
        self.assertEqual("rom-cfg-proven-roots-v13", manifest["artifact_schema"])
        self.assertEqual("accepted", manifest["artifact_status"])
        self.assertEqual(
            {
                "rom-cfg-proven-roots-v13.json": {
                    "size": coverage_auditor.CFG_PROVEN_ROOTS_V13_PAYLOAD_SIZE,
                    "sha256": coverage_auditor.CFG_PROVEN_ROOTS_V13_PAYLOAD_SHA256,
                }
            },
            manifest["files"],
        )
        self.assertEqual(0, manifest["verifier"]["exit_code"])
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V13_EXPECTED_REPORT,
            manifest["verifier"]["report"],
        )
        auditor_source = (ROOT / "tools/audit_rom_byte_coverage.py").read_text()
        self.assertNotIn(
            "from tools.verify_rom_cfg_proven_roots_v13_bundle import",
            auditor_source,
        )

    def test_promotes_exact_three_code_and_three_literal_ranges_but_not_holes(self):
        claims = self._claims()
        code = [claim for claim in claims if claim["claim_kind"] == self.CODE_KIND]
        literals = [
            claim for claim in claims if claim["claim_kind"] == self.LITERAL_KIND
        ]
        self.assertEqual(6, len(claims))
        self.assertEqual(self.CODE_RANGES, [claim["range"] for claim in code])
        self.assertEqual(self.LITERAL_RANGES, [claim["range"] for claim in literals])
        self.assertEqual(
            312,
            sum(end - start for start, end in (claim["range"] for claim in code)),
        )
        self.assertEqual(
            80,
            sum(end - start for start, end in (claim["range"] for claim in literals)),
        )
        self.assertTrue(
            all(
                claim["primary_class"] == self.CODE_CLASS
                and claim["mode"] == "thumb"
                for claim in code
            )
        )
        self.assertTrue(
            all(claim["primary_class"] == self.LITERAL_CLASS for claim in literals)
        )
        self.assertTrue(
            all(
                claim["role"] == "primary"
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["promotion_batch"] == self.BATCH
                and claim["independent_verifier_path"]
                == "tools/verify_rom_cfg_proven_roots_v13_bundle.py"
                and claim["independent_verifier_sha256"]
                == coverage_auditor.CFG_PROVEN_ROOTS_V13_BUNDLE_VERIFIER_SHA256
                for claim in claims
            )
        )
        segments = coverage_auditor.atomize_claims(
            6_291_456, [*self._baseline(), *claims]
        )
        for hole_start, hole_end in self.HOLES:
            hole_segments = [
                segment
                for segment in segments
                if hole_start < segment["range"][1]
                and segment["range"][0] < hole_end
            ]
            self.assertEqual(
                [[hole_start, hole_end]],
                [segment["range"] for segment in hole_segments],
            )
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in hole_segments)
            )

    def test_rejects_known_overlap_duplicate_batch_and_identity_drift(self):
        baseline = self._baseline()
        synthetic_known = {
            "id": "synthetic-v13-known-overlap",
            "range": [0x0651F8, 0x0651F9],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, synthetic_known])
        synthetic_batch = {
            "id": "synthetic-v13-duplicate-batch",
            "range": [0x0651F8, 0x06523C],
            "role": "primary",
            "primary_class": "synthetic_duplicate_batch",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "pre-v13|already"):
            self._claims([*baseline, synthetic_batch])
        for constant in (
            "CFG_PROVEN_ROOTS_V13_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_V13_PAYLOAD_SHA256",
            "CFG_PROVEN_ROOTS_V13_VERIFIER_SHA256",
            "CFG_PROVEN_ROOTS_V13_BUNDLE_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()

    def test_rejects_verifier_failure_rom_tamper_and_range_drift(self):
        with mock.patch.object(
            coverage_auditor,
            "_run_cfg_proven_roots_v13_bundle_verifier",
            return_value={
                "schema": "rom-cfg-proven-roots-v13-bundle-verification-v1",
                "verified": False,
                "errors": ["forced verifier failure"],
            },
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification failed"):
                self._claims()
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x0651F8] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity changed"):
            coverage_auditor._cfg_proven_roots_v13_claims(
                ROOT, bytes(rom), self._baseline()
            )
        drifted = [list(value) for value in self.CODE_RANGES]
        drifted[0] = [0x0651F8, 0x065240]
        with mock.patch.object(
            coverage_auditor, "CFG_PROVEN_ROOTS_V13_CODE_RANGES", drifted, create=True
        ), self.assertRaisesRegex(
            ValueError, "current unknown|target code range|promotion"
        ):
            self._claims()

    def test_auditor_executes_the_anchored_bundle_bytes_via_stdin(self):
        frozen_source = b"raise AssertionError('subprocess mock should intercept')\n"
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                coverage_auditor.CFG_PROVEN_ROOTS_V13_BUNDLE_EXPECTED_REPORT
            ).encode("utf-8"),
            stderr=b"",
        )
        with mock.patch.object(
            coverage_auditor.subprocess,
            "run",
            return_value=completed,
        ) as run:
            report = coverage_auditor._run_cfg_proven_roots_v13_bundle_verifier(
                ROOT,
                frozen_source,
                ROOT / coverage_auditor.CFG_PROVEN_ROOTS_V13_BUNDLE_VERIFIER,
            )

        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V13_BUNDLE_EXPECTED_REPORT,
            report,
        )
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual([sys.executable, "-I", "-S", "-c"], command[:4])
        self.assertIn("sys.stdin.buffer.read()", command[4])
        self.assertEqual(frozen_source, kwargs["input"])
        self.assertNotIn("text", kwargs)
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])


class ParserBoundZeroPaddingCoverageTests(unittest.TestCase):
    BATCH = "rom-parser-bound-zero-padding-v1"
    CLAIM_KIND = "parser_bound_zero_padding_range"

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") != self.CLAIM_KIND
        ]

    def test_promotes_exact_verified_current_unknown_ranges(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = coverage_auditor._parser_bound_zero_padding_claims(
            ROOT, rom, self._baseline()
        )
        self.assertEqual(142, len(claims))
        self.assertEqual(
            198,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(
            "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1",
            hashlib.sha256(
                json.dumps(
                    [claim["range"] for claim in claims], separators=(",", ":")
                ).encode("ascii")
            ).hexdigest(),
        )
        self.assertEqual(
            {
                "chapter_terminal_to_fixed_root_zero_padding": (85, 85),
                "m4a_wave_alignment_zero_padding": (57, 113),
            },
            {
                source_kind: (
                    sum(claim["source_kind"] == source_kind for claim in claims),
                    sum(
                        claim["range"][1] - claim["range"][0]
                        for claim in claims
                        if claim["source_kind"] == source_kind
                    ),
                )
                for source_kind in {
                    claim["source_kind"] for claim in claims
                }
            },
        )
        self.assertTrue(
            all(
                claim["claim_kind"] == self.CLAIM_KIND
                and claim["primary_class"] == claim["source_kind"]
                and claim["promotion_batch"] == self.BATCH
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["safe_allocatable_space_claimed"] is False
                and claim["natural_execution_reachability_claimed"] is False
                and claim["editing_or_relocation_safety_claimed"] is False
                and claim["bytes_sha256"]
                == hashlib.sha256(rom[slice(*claim["range"])]).hexdigest()
                and not any(rom[slice(*claim["range"])])
                for claim in claims
            )
        )

        artifact = json.loads(
            (
                ROOT
                / "artifacts/rom-parser-bound-zero-padding-v1/rom-parser-bound-zero-padding.json"
            ).read_text()
        )
        self.assertEqual(
            [record["range"] for record in artifact["classified_ranges"]],
            [claim["range"] for claim in claims],
        )
        self.assertTrue(
            all(
                claim["source_range_id"] == record["range_id"]
                and claim["packed_range"] == record["packed_range"]
                and claim["evidence_selector"] == f"/classified_ranges/{index}"
                for index, (claim, record) in enumerate(
                    zip(claims, artifact["classified_ranges"], strict=True)
                )
            )
        )
        claimed_ranges = {tuple(claim["range"]) for claim in claims}
        self.assertTrue(
            claimed_ranges.isdisjoint(
                tuple(record["range"])
                for record in [
                    *artifact["rejected_ranges"],
                    *artifact["contract_excluded_ranges"],
                ]
            )
        )

    def test_fails_closed_on_known_overlap_duplicate_batch_and_verifier_failure(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        synthetic_known = {
            "id": "synthetic-parser-padding-known-overlap",
            "range": [0x46E881, 0x46E882],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "fully current unknown"):
            coverage_auditor._parser_bound_zero_padding_claims(
                ROOT, rom, [*baseline, synthetic_known]
            )
        duplicate_batch = {
            "id": "synthetic-parser-padding-duplicate-batch",
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            coverage_auditor._parser_bound_zero_padding_claims(
                ROOT, rom, [*baseline, duplicate_batch]
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_parser_bound_zero_padding",
            return_value={
                "schema": "rom-parser-bound-zero-padding-verification-v1",
                "verified": False,
                "errors": ["forced failure"],
            },
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                coverage_auditor._parser_bound_zero_padding_claims(
                    ROOT, rom, baseline
                )

    def test_fails_closed_on_artifact_and_verifier_trust_boundary_changes(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        temp_parent = ROOT / "build/experiments/active"
        source_artifact = ROOT / coverage_auditor.PARSER_BOUND_ZERO_PADDING_ARTIFACT

        with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
            temp_root = Path(temp_dir)

            artifact_link = temp_root / "artifact-link"
            artifact_link.symlink_to(source_artifact, target_is_directory=True)
            with mock.patch.object(
                coverage_auditor,
                "PARSER_BOUND_ZERO_PADDING_ARTIFACT",
                artifact_link.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "artifact uses a symlink"):
                    coverage_auditor._parser_bound_zero_padding_claims(
                        ROOT, rom, baseline
                    )

            verifier_link = temp_root / "verifier-link.py"
            verifier_link.symlink_to(
                ROOT / coverage_auditor.PARSER_BOUND_ZERO_PADDING_VERIFIER
            )
            with mock.patch.object(
                coverage_auditor,
                "PARSER_BOUND_ZERO_PADDING_VERIFIER",
                verifier_link.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "verifier identity"):
                    coverage_auditor._parser_bound_zero_padding_claims(
                        ROOT, rom, baseline
                    )

            member_symlink_artifact = temp_root / "member-symlink-artifact"
            member_symlink_artifact.mkdir()
            for name in {
                "manifest.json",
                coverage_auditor.PARSER_BOUND_ZERO_PADDING_PAYLOAD_NAME,
            }:
                shutil.copy2(source_artifact / name, member_symlink_artifact / name)
            bundle_name = coverage_auditor.PARSER_BOUND_ZERO_PADDING_BUNDLE_NAME
            (member_symlink_artifact / bundle_name).symlink_to(
                source_artifact / bundle_name
            )
            with mock.patch.object(
                coverage_auditor,
                "PARSER_BOUND_ZERO_PADDING_ARTIFACT",
                member_symlink_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "file set changed"):
                    coverage_auditor._parser_bound_zero_padding_claims(
                        ROOT, rom, baseline
                    )

            tampered_artifact = temp_root / "tampered-artifact"
            shutil.copytree(source_artifact, tampered_artifact)
            payload_path = (
                tampered_artifact
                / coverage_auditor.PARSER_BOUND_ZERO_PADDING_PAYLOAD_NAME
            )
            payload_raw = payload_path.read_bytes()
            payload_path.write_bytes(bytes([payload_raw[0] ^ 1]) + payload_raw[1:])
            with mock.patch.object(
                coverage_auditor,
                "PARSER_BOUND_ZERO_PADDING_ARTIFACT",
                tampered_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "artifact identity"):
                    coverage_auditor._parser_bound_zero_padding_claims(
                        ROOT, rom, baseline
                    )

            self_reference_artifact = temp_root / "self-reference-artifact"
            shutil.copytree(source_artifact, self_reference_artifact)
            payload_path = (
                self_reference_artifact
                / coverage_auditor.PARSER_BOUND_ZERO_PADDING_PAYLOAD_NAME
            )
            payload_raw = payload_path.read_bytes() + b"rom-byte-coverage"
            payload_path.write_bytes(payload_raw)
            with (
                mock.patch.object(
                    coverage_auditor,
                    "PARSER_BOUND_ZERO_PADDING_ARTIFACT",
                    self_reference_artifact.relative_to(ROOT),
                ),
                mock.patch.object(
                    coverage_auditor,
                    "PARSER_BOUND_ZERO_PADDING_PAYLOAD_SIZE",
                    len(payload_raw),
                ),
                mock.patch.object(
                    coverage_auditor,
                    "PARSER_BOUND_ZERO_PADDING_PAYLOAD_SHA256",
                    hashlib.sha256(payload_raw).hexdigest(),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "self-references coverage"):
                    coverage_auditor._parser_bound_zero_padding_claims(
                        ROOT, rom, baseline
                    )


class DirectCpusetBoundPaletteCoverageTests(unittest.TestCase):
    """Additive coverage contract for six already verified raw palettes."""

    BATCH = "rom-direct-cpuset-bound-palette-coverage-v1"
    CLAIM_KIND = "direct_cpuset_bound_palette_source_range"
    EXPECTED_RANGES = [
        [0x348BE4, 0x348C04],
        [0x3496B0, 0x3496D0],
        [0x405FF0, 0x406010],
        [0x457EA8, 0x457EC8],
        [0x45830C, 0x45832C],
        [0x463FFC, 0x46401C],
    ]
    RANGE_DENOMINATOR_SHA256 = (
        "37ea9a17c34454a25866f790eb26b72d4b40b7a7a663b7f15366a6e3ad7fcf1f"
    )
    PACKED_BYTES_SHA256 = (
        "056a3625cc3a6735e56921aaec6ee37e646380bf31040cb6ad63fa8dbe757b70"
    )

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
        ]

    def test_promotes_exact_six_whole_current_unknown_palettes(self):
        rom = self._rom()
        baseline = self._baseline()
        payload = json.loads(
            (
                ROOT
                / "artifacts/rom-direct-cpuset-gpu-inventory-v1"
                / "rom-direct-cpuset-gpu-inventory.json"
            ).read_text(encoding="utf-8")
        )
        claims = coverage_auditor._direct_cpuset_bound_palette_claims(
            ROOT, rom, baseline
        )

        self.assertEqual(self.EXPECTED_RANGES, [claim["range"] for claim in claims])
        self.assertEqual(6, len(claims))
        self.assertEqual(192, sum(end - start for start, end in self.EXPECTED_RANGES))
        self.assertEqual(
            self.PACKED_BYTES_SHA256,
            hashlib.sha256(
                b"".join(rom[start:end] for start, end in self.EXPECTED_RANGES)
            ).hexdigest(),
        )
        baseline_segments = atomize_claims(len(rom), baseline)
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual(32, end - start)
            self.assertEqual("primary", claim["role"])
            self.assertEqual("palette_bgr555", claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(self.RANGE_DENOMINATOR_SHA256, claim["range_denominator_sha256"])
            self.assertEqual(16, claim["color_count"])
            self.assertTrue(claim["consumer_operations"])
            self.assertEqual(
                claim["consumer_operations"],
                [
                    payload["already_bound_operations"][
                        int(selector.removeprefix("/already_bound_operations/"))
                    ]
                    for selector in claim["evidence_selectors"]
                ],
            )
            self.assertTrue(
                all(
                    selector.startswith("/already_bound_operations/")
                    and selector.removeprefix("/already_bound_operations/").isdigit()
                    for selector in claim["evidence_selectors"]
                )
            )
            self.assertTrue(
                all(
                    operation["destination_domain"] == "PRAM"
                    and operation["copy_size"] >= 32
                    for operation in claim["consumer_operations"]
                )
            )
            self.assertFalse(claim["natural_runtime_reachability_claimed"])
            self.assertFalse(claim["editing_or_relocation_safety_claimed"])
            self.assertFalse(claim["allocatable_space_claimed"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in intersections)
            )

    def test_fails_closed_on_partial_overlap_duplicate_batch_and_verifier_failure(self):
        rom = self._rom()
        baseline = self._baseline()
        synthetic_known = {
            "id": "synthetic-cpuset-palette-overlap",
            "range": [self.EXPECTED_RANGES[0][0], self.EXPECTED_RANGES[0][0] + 1],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._direct_cpuset_bound_palette_claims(
                ROOT, rom, [*baseline, synthetic_known]
            )

        duplicate_batch = {
            "id": "synthetic-cpuset-palette-duplicate",
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            coverage_auditor._direct_cpuset_bound_palette_claims(
                ROOT, rom, [*baseline, duplicate_batch]
            )

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_direct_cpuset_gpu_inventory",
            return_value={
                "schema": "rom-direct-cpuset-gpu-inventory-verification-v1",
                "verified": False,
                "errors": ["forced failure"],
                "direct_call_count": 146,
                "new_source_count": 3,
            },
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                coverage_auditor._direct_cpuset_bound_palette_claims(
                    ROOT, rom, baseline
                )

    def test_rejects_parent_record_expansion_and_rom_tamper(self):
        rom = self._rom()
        claims = coverage_auditor._direct_cpuset_bound_palette_claims(
            ROOT, rom, self._baseline()
        )
        parent = next(claim for claim in claims if claim["range"][0] == 0x405FF0)
        self.assertEqual([0x405FF0, 0x406010], parent["range"])
        self.assertTrue(
            any(operation["copy_size"] == 256 for operation in parent["consumer_operations"])
        )

        tampered = bytearray(rom)
        tampered[self.EXPECTED_RANGES[0][0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            coverage_auditor._direct_cpuset_bound_palette_claims(
                ROOT, bytes(tampered), self._baseline()
            )

    def test_rejects_an_unlisted_seventh_eligible_source(self):
        rom = self._rom()
        baseline = self._baseline()
        payload_path = (
            ROOT
            / "artifacts/rom-direct-cpuset-gpu-inventory-v1"
            / "rom-direct-cpuset-gpu-inventory.json"
        )
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        injected = copy.deepcopy(payload)
        replacement = next(
            operation
            for operation in injected["already_bound_operations"]
            if operation["source_address"] == "0x0834941C"
        )
        replacement["source_address"] = "0x080003E0"
        expected_report = {
            "schema": "rom-direct-cpuset-gpu-inventory-verification-v1",
            "verified": True,
            "errors": [],
            "direct_call_count": 146,
            "new_source_count": 3,
        }
        with (
            mock.patch.object(
                coverage_auditor.json,
                "loads",
                return_value=injected,
            ),
            mock.patch(
                "tools.audit_rom_byte_coverage.verify_rom_direct_cpuset_gpu_inventory",
                return_value=expected_report,
            ),
        ):
            with self.assertRaisesRegex(ValueError, "source denominator"):
                coverage_auditor._direct_cpuset_bound_palette_claims(
                    ROOT, rom, baseline
                )

    def test_fails_closed_at_artifact_catalog_and_identity_trust_boundaries(self):
        rom = self._rom()
        baseline = self._baseline()
        temp_parent = ROOT / "build/experiments/active"
        source_artifact = ROOT / coverage_auditor.DIRECT_CPUSET_GPU_ARTIFACT

        with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
            temp_root = Path(temp_dir)
            member_symlink_artifact = temp_root / "member-symlink-artifact"
            member_symlink_artifact.mkdir()
            for name in {"manifest.json", "rom-direct-cpuset-gpu-inventory.json"}:
                shutil.copy2(source_artifact / name, member_symlink_artifact / name)
            (member_symlink_artifact / "new-raw-sources.bin").symlink_to(
                source_artifact / "new-raw-sources.bin"
            )
            with mock.patch.object(
                coverage_auditor,
                "DIRECT_CPUSET_GPU_ARTIFACT",
                member_symlink_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "file set changed"):
                    coverage_auditor._direct_cpuset_bound_palette_claims(
                        ROOT, rom, baseline
                    )

            catalog_link = temp_root / "catalog-link.json"
            catalog_link.symlink_to(ROOT / coverage_auditor.DIRECT_CPUSET_SOURCE_CATALOG)
            with mock.patch.object(
                coverage_auditor,
                "DIRECT_CPUSET_SOURCE_CATALOG",
                catalog_link.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "source catalog is unsafe"):
                    coverage_auditor._direct_cpuset_bound_palette_claims(
                        ROOT, rom, baseline
                    )

            self_reference_artifact = temp_root / "self-reference-artifact"
            shutil.copytree(source_artifact, self_reference_artifact)
            payload_path = (
                self_reference_artifact / "rom-direct-cpuset-gpu-inventory.json"
            )
            payload_path.write_bytes(payload_path.read_bytes() + b"rom-byte-coverage")
            with mock.patch.object(
                coverage_auditor,
                "DIRECT_CPUSET_GPU_ARTIFACT",
                self_reference_artifact.relative_to(ROOT),
            ):
                with self.assertRaisesRegex(ValueError, "self-references coverage"):
                    coverage_auditor._direct_cpuset_bound_palette_claims(
                        ROOT, rom, baseline
                    )

        with mock.patch.object(
            coverage_auditor,
            "DIRECT_CPUSET_GPU_VERIFIER_SHA256",
            "0" * 64,
        ):
            with self.assertRaisesRegex(ValueError, "evidence identity"):
                coverage_auditor._direct_cpuset_bound_palette_claims(
                    ROOT, rom, baseline
                )


class SpriteDefinitionResolvedWindowCoverageTests(unittest.TestCase):
    def test_promotes_only_verified_current_unknown_windows(self):
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        rom = (ROOT / "rom/base.gba").read_bytes()
        # 本包已晋升进账本，生产者自己的 current-unknown 门会拒绝拿最终账本
        # 重投影（"sprite-definition resolved-window promotion changed"）。
        # 必须用链时基线：账本去掉本包自己那 3 条 claim。
        baseline = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind") != "sprite_definition_resolved_window_bytes"
        ]
        claims = _sprite_definition_resolved_window_claims(
            ROOT, rom, baseline
        )
        self.assertEqual(3, len(claims))
        self.assertEqual(
            1_720,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertTrue(
            all(
                claim["promoted_from_primary_class"] == "unknown"
                and claim["range"][1] <= 0x12FC78
                for claim in claims
            )
        )


class BattleControllerCfgCoverageTests(unittest.TestCase):
    """Independent RED contract for the controller-CFG coverage helper.

    This class deliberately does NOT depend on
    :class:`RomByteCoverageAuditTests.setUpClass`.  It pins:

    1. The auditor's identity constants (payload/manifest/verifier SHA and
       payload size) to the freshly committed controller-CFG artifact.
    2. The integration behaviour of ``_battle_controller_cfg_claims`` when
       fed a frozen baseline that already excludes every
       ``battle_controller_cfg_reachable_instruction_bytes`` claim.
    3. The tamper fail-closed behaviour of the same helper for any byte
       inside the corrected controller range.

    The first two contracts are intentionally written so they will be RED
    against the current auditor, whose constants still bind to the pre-GREEN
    (pre-§9.1 #4/#5 worklist) controller-CFG payload/manifest SHA.  The
    third contract is satisfied whenever the helper raises (the SHA check
    fires first, before the tamper check, but the assertion only requires a
    ValueError).
    """

    EXPECTED_PAYLOAD_SHA256 = (
        "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"
    )
    EXPECTED_PAYLOAD_SIZE = 401_034
    EXPECTED_MANIFEST_SHA256 = (
        "282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63"
    )

    # Tamper byte: first byte of block-thumb-0733a0 (offset 0x733A0), which
    # sits inside the controller range [0x732B4, 0x7509C) and is part of the
    # first promoted claim battle-controller-cfg-thumb-0000-0733a0.
    CONTROLLER_TAMPER_OFFSET = 0x733A2

    @classmethod
    def _project_root(cls) -> Path:
        return ROOT

    @classmethod
    def _committed_verifier_sha256(cls) -> str:
        verifier_path = cls._project_root() / BATTLE_CONTROLLER_CFG_VERIFIER
        return hashlib.sha256(verifier_path.read_bytes()).hexdigest()

    def test_auditor_constants_bind_to_committed_artifact_identity(self):
        """Auditor constants must pin the freshly committed controller CFG.

        This is a static identity contract.  The auditor still binds the
        pre-GREEN payload/manifest SHA and size, so this test is expected
        to fail RED until the constants are updated alongside the new
        artifact.
        """
        verifier_sha = self._committed_verifier_sha256()

        self.assertEqual(
            self.EXPECTED_PAYLOAD_SHA256,
            BATTLE_CONTROLLER_CFG_PAYLOAD_SHA256,
            "auditor payload SHA must match the committed artifact",
        )
        self.assertEqual(
            self.EXPECTED_PAYLOAD_SIZE,
            BATTLE_CONTROLLER_CFG_PAYLOAD_SIZE,
            "auditor payload size must match the committed artifact",
        )
        self.assertEqual(
            self.EXPECTED_MANIFEST_SHA256,
            BATTLE_CONTROLLER_CFG_MANIFEST_SHA256,
            "auditor manifest SHA must match the committed artifact",
        )
        self.assertEqual(
            verifier_sha,
            BATTLE_CONTROLLER_CFG_VERIFIER_SHA256,
            (
                "auditor verifier SHA must match the freshly computed hash "
                "of tools/verify_rom_battle_controller_cfg.py"
            ),
        )

    def test_helper_promotes_49_claims_with_6172_bytes_from_frozen_baseline(
        self,
    ):
        """Integration contract for ``_battle_controller_cfg_claims``.

        Build a frozen baseline by removing every
        ``battle_controller_cfg_reachable_instruction_bytes`` claim from
        the committed coverage JSON, then call the helper and assert the
        exact promoted structure (49 claims, 6172 bytes, all promoted from
        unknown, no overlap with the eight excluded producer ranges).

        This test is expected to be RED against the current auditor, whose
        constants still bind to the pre-GREEN payload/manifest SHA, so the
        helper will refuse to run on the committed artifact.
        """
        coverage_path = self._project_root() / "sequel" / "rom-byte-coverage.json"
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        baseline = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "battle_controller_cfg_reachable_instruction_bytes"
        ]

        rom = (self._project_root() / "rom" / "base.gba").read_bytes()

        claims = _battle_controller_cfg_claims(
            self._project_root(), rom, baseline
        )

        self.assertEqual(
            BATTLE_CONTROLLER_CFG_PROMOTED_CODE_CLAIM_COUNT,
            len(claims),
            "helper must emit exactly 49 promoted claims",
        )
        promoted_bytes = sum(
            claim["range"][1] - claim["range"][0] for claim in claims
        )
        self.assertEqual(
            BATTLE_CONTROLLER_CFG_PROMOTED_CODE_BYTES,
            promoted_bytes,
            "helper must promote exactly 6172 bytes of unknown code",
        )
        for claim in claims:
            self.assertEqual(
                "unknown",
                claim["promoted_from_primary_class"],
                (
                    "every controller-CFG claim must be promoted from the "
                    "unknown primary class"
                ),
            )
            self.assertEqual(
                BATTLE_CONTROLLER_CFG_CONTROLLER_RANGE,
                tuple(claim["controller_range"]),
                "controller_range must match the committed controller range",
            )

        claim_ranges = [tuple(claim["range"]) for claim in claims]
        for excluded_start, excluded_end in BATTLE_CONTROLLER_CFG_EXCLUDED_PRODUCER_RANGES:
            for claim_start, claim_end in claim_ranges:
                self.assertFalse(
                    claim_start < excluded_end and claim_end > excluded_start,
                    (
                        f"claim [{hex(claim_start)}, {hex(claim_end)}) must "
                        f"not overlap excluded producer range "
                        f"[{hex(excluded_start)}, {hex(excluded_end)})"
                    ),
                )

    def test_helper_fails_closed_on_rom_tampering_inside_controller(self):
        """Tamper contract: helper must raise for any byte inside controller.

        Even though the auditor's pre-GREEN constants would already trigger
        a ValueError on the SHA check before reaching the tamper check, the
        contract under test is strictly: tampering any byte inside the
        controller range must not silently succeed.  Asserting a ValueError
        is sufficient for both the current (pre-GREEN) auditor and the
        post-GREEN auditor.
        """
        coverage_path = self._project_root() / "sequel" / "rom-byte-coverage.json"
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        baseline = [
            claim
            for claim in coverage["claims"]
            if claim.get("claim_kind")
            != "battle_controller_cfg_reachable_instruction_bytes"
        ]

        rom = bytearray((self._project_root() / "rom" / "base.gba").read_bytes())
        self.assertTrue(
            BATTLE_CONTROLLER_CFG_CONTROLLER_RANGE[0]
            <= self.CONTROLLER_TAMPER_OFFSET
            < BATTLE_CONTROLLER_CFG_CONTROLLER_RANGE[1],
            "tamper byte must lie inside the committed controller range",
        )
        rom[self.CONTROLLER_TAMPER_OFFSET] ^= 0x01

        with self.assertRaises(ValueError):
            _battle_controller_cfg_claims(
                self._project_root(), bytes(rom), baseline
            )


class BattleEffectSpriteAnimationSourceCoverageTests(unittest.TestCase):
    """Frozen source-range contract for the battle-effect sprite artifact."""

    @classmethod
    def _project_root(cls) -> Path:
        return ROOT

    @classmethod
    def _rom(cls) -> bytes:
        return (cls._project_root() / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (cls._project_root() / "sequel/rom-byte-coverage.json").read_text(
                encoding="utf-8"
            )
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != BATTLE_EFFECT_SPRITE_SOURCE_BATCH
        ]

    @staticmethod
    def _select(document: object, selector: str) -> object:
        selected = document
        for part in selector.removeprefix("/").split("/"):
            if isinstance(selected, dict):
                selected = selected[part]
            elif isinstance(selected, list):
                selected = selected[int(part)]
            else:
                raise AssertionError(f"unresolved selector {selector}")
        return selected

    def test_promotes_four_frozen_source_kinds_from_current_unknown(self):
        claims = _battle_effect_sprite_animation_source_claims(
            self._project_root(), self._rom(), self._baseline()
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_EXPECTED_CLAIM_COUNT, len(claims)
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_EXPECTED_BYTES,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_CLASS_COUNTS,
            {
                primary_class: sum(
                    claim["primary_class"] == primary_class for claim in claims
                )
                for primary_class in BATTLE_EFFECT_SPRITE_SOURCE_CLASS_COUNTS
            },
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_CLASS_BYTES,
            {
                primary_class: sum(
                    claim["range"][1] - claim["range"][0]
                    for claim in claims
                    if claim["primary_class"] == primary_class
                )
                for primary_class in BATTLE_EFFECT_SPRITE_SOURCE_CLASS_BYTES
            },
        )
        self.assertTrue(
            all(
                claim["claim_kind"] == BATTLE_EFFECT_SPRITE_SOURCE_CLAIM_KIND
                and claim["promotion_batch"] == BATTLE_EFFECT_SPRITE_SOURCE_BATCH
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["baseline_unknown_only"]
                and claim["role"] == "primary"
                for claim in claims
            )
        )

        manifest = json.loads(
            (
                self._project_root()
                / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        rom = self._rom()
        self.assertEqual(
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            hashlib.sha256(rom).hexdigest(),
        )
        self.assertEqual(
            BATTLE_EFFECT_SPRITE_SOURCE_CLAIM_DENOMINATOR_SHA256,
            hashlib.sha256(
                json.dumps(
                    [
                        {
                            key: claim[key]
                            for key in (
                                "id",
                                "range",
                                "primary_class",
                                "bytes_sha256",
                                "evidence_selector",
                            )
                        }
                        for claim in sorted(
                            claims,
                            key=lambda item: (item["range"], item["id"]),
                        )
                    ],
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("ascii")
            ).hexdigest(),
        )
        for claim in claims:
            record = self._select(manifest, claim["evidence_selector"])
            self.assertEqual(
                BATTLE_EFFECT_SPRITE_SOURCE_MANIFEST_SHA256,
                claim["evidence_sha256"],
            )
            self.assertEqual(
                BATTLE_EFFECT_SPRITE_SOURCE_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                BATTLE_EFFECT_SPRITE_SOURCE_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                BATTLE_EFFECT_SPRITE_SOURCE_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )
            start, end = claim["range"]
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(),
                claim["bytes_sha256"],
            )
            self.assertEqual(claim["range"], claim["source_range"])
            if claim["primary_class"] in {
                "battle_effect_sprite_component_records",
                "battle_effect_sprite_animation_timeline",
            }:
                self.assertEqual(record["raw_size"], end - start)
                self.assertEqual(record["raw_sha256"], claim["source_raw_sha256"])
                self.assertEqual(record["raw_sha256"], claim["bytes_sha256"])
                self.assertEqual(
                    "ffff0000",
                    rom[end - 4 : end].hex(),
                )
            else:
                self.assertEqual(
                    claim["table_entry_count"] * 4,
                    end - start,
                )
                expected_field = {
                    "battle_effect_sprite_definition_pointer_table": (
                        "definition_pointer_table"
                    ),
                    "battle_effect_sprite_animation_pointer_table": (
                        "animation_pointer_table"
                    ),
                }[claim["primary_class"]]
                self.assertTrue(
                    claim["evidence_selector"].endswith(f"/{expected_field}")
                )
                self.assertEqual(claim["source_pointer"], record)
            self.assertTrue(claim["evidence_selector"].startswith("/groups/"))

        self.assertEqual(
            len(claims),
            len({claim["evidence_selector"] for claim in claims}),
        )

        empty_frame_claim = next(
            claim
            for claim in claims
            if claim["evidence_selector"] == "/groups/17/frames/7"
        )
        self.assertEqual(4, empty_frame_claim["range"][1] - empty_frame_claim["range"][0])

    def test_existing_primary_overlap_fails_closed_without_reclaiming_bytes(self):
        baseline = self._baseline()
        artifact_manifest = json.loads(
            (
                self._project_root()
                / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        frame = artifact_manifest["groups"][0]["frames"][0]
        first_start = int(frame["component_list_pointer"], 16) - 0x08000000
        first = {"range": [first_start, first_start + frame["raw_size"]]}
        baseline.append(
            {
                "id": "injected-existing-primary",
                "range": first["range"],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sprite_animations",
            return_value=BATTLE_EFFECT_SPRITE_SOURCE_EXPECTED_REPORT,
        ):
            with self.assertRaisesRegex(ValueError, "current unknown"):
                _battle_effect_sprite_animation_source_claims(
                    self._project_root(), self._rom(), baseline
                )

    def test_rom_tampering_fails_closed(self):
        tampered = bytearray(self._rom())
        tampered[0x3409F0] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            _battle_effect_sprite_animation_source_claims(
                self._project_root(), bytes(tampered), self._baseline()
            )

    def test_independent_verifier_failure_fails_closed(self):
        failed = {
            "schema": "battle-effect-sprite-animations-verification-v1",
            "verified": False,
            "verified_groups": 0,
            "verified_frames": 0,
            "verified_components": 0,
            "verified_animations": 0,
            "errors": ["injected failure"],
        }
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sprite_animations",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _battle_effect_sprite_animation_source_claims(
                    self._project_root(), self._rom(), self._baseline()
                )


class ReferencedTextSlotPaddingCoverageTests(unittest.TestCase):
    """Coverage promotion contract for the 133 referenced post-NUL suffixes."""

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != REFERENCED_TEXT_SLOT_PADDING_BATCH
        ]

    def test_promotes_exact_three_group_denominator_from_current_unknown(self):
        baseline = self._baseline()
        baseline_segments = atomize_claims(len(self._rom()), baseline)
        claims = _referenced_text_slot_padding_claims(ROOT, self._rom(), baseline)
        self.assertEqual(133, len(claims))
        self.assertEqual(
            1_255,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(
            REFERENCED_TEXT_SLOT_PADDING_CLASS_COUNTS,
            {
                primary_class: sum(
                    claim["primary_class"] == primary_class for claim in claims
                )
                for primary_class in REFERENCED_TEXT_SLOT_PADDING_CLASS_COUNTS
            },
        )
        self.assertEqual(
            REFERENCED_TEXT_SLOT_PADDING_CLASS_BYTES,
            {
                primary_class: sum(
                    claim["range"][1] - claim["range"][0]
                    for claim in claims
                    if claim["primary_class"] == primary_class
                )
                for primary_class in REFERENCED_TEXT_SLOT_PADDING_CLASS_BYTES
            },
        )
        for claim in claims:
            start, end = claim["range"]
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertFalse(claim["safe_allocatable_space_claimed"])
            self.assertFalse(claim["runtime_reachability_claimed"])
            self.assertFalse(claim["text_semantics_claimed"])
            self.assertEqual(bytes(end - start), self._rom()[start:end])
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in intersections)
            )
            self.assertEqual(
                REFERENCED_TEXT_SLOT_PADDING_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                REFERENCED_TEXT_SLOT_PADDING_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                REFERENCED_TEXT_SLOT_PADDING_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )

    def test_existing_primary_overlap_fails_closed(self):
        payload = json.loads(
            (
                ROOT
                / "artifacts/rom-referenced-text-slot-padding-v1/referenced-text-slot-padding.json"
            ).read_text(encoding="utf-8")
        )
        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-padding-overlap",
                "range": payload["classified_ranges"][0]["range"],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            _referenced_text_slot_padding_claims(ROOT, self._rom(), baseline)

    def test_independent_verifier_failure_fails_closed(self):
        failed = dict(REFERENCED_TEXT_SLOT_PADDING_EXPECTED_REPORT)
        failed["verified"] = False
        failed["errors"] = ["injected failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_referenced_text_slot_padding",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _referenced_text_slot_padding_claims(
                    ROOT, self._rom(), self._baseline()
                )

    def test_rom_tampering_fails_closed(self):
        payload = json.loads(
            (
                ROOT
                / "artifacts/rom-referenced-text-slot-padding-v1/referenced-text-slot-padding.json"
            ).read_text(encoding="utf-8")
        )
        tampered = bytearray(self._rom())
        tampered[payload["classified_ranges"][0]["range"][0]] = 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            _referenced_text_slot_padding_claims(
                ROOT, bytes(tampered), self._baseline()
            )


class SelectorDirectSourceRecordCoverageTests(unittest.TestCase):
    """Coverage promotion contract for the fixed 46×20-byte source rows."""

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != SELECTOR_DIRECT_SOURCE_RECORDS_BATCH
        ]

    def test_promotes_exact_fixed_record_denominator_from_current_unknown(self):
        baseline = self._baseline()
        baseline_segments = atomize_claims(len(self._rom()), baseline)
        claims = _selector_direct_source_record_claims(ROOT, self._rom(), baseline)
        self.assertEqual(46, len(claims))
        self.assertEqual(
            920, sum(claim["range"][1] - claim["range"][0] for claim in claims)
        )
        self.assertEqual(list(range(46)), [claim["source_id"] for claim in claims])
        self.assertEqual(
            [[0x59F5F0 + index * 20, 0x59F5F0 + (index + 1) * 20] for index in range(46)],
            [claim["range"] for claim in claims],
        )
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual("selector_direct_source_record", claim["primary_class"])
            self.assertEqual("selector_direct_source_record_bytes", claim["claim_kind"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertFalse(claim["runtime_reachability_claimed"])
            self.assertFalse(claim["full_record_field_semantics_claimed"])
            self.assertFalse(claim["editing_or_writeback_safety_proven"])
            self.assertFalse(claim["allocatable_space_claimed"])
            self.assertEqual(
                hashlib.sha256(self._rom()[start:end]).hexdigest(),
                claim["bytes_sha256"],
            )
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in intersections)
            )
            self.assertEqual(
                SELECTOR_DIRECT_SOURCE_RECORDS_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                SELECTOR_DIRECT_SOURCE_RECORDS_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                SELECTOR_DIRECT_SOURCE_RECORDS_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )

    def test_existing_primary_overlap_fails_closed(self):
        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-source-row-overlap",
                "range": [0x59F5F0, 0x59F604],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            _selector_direct_source_record_claims(ROOT, self._rom(), baseline)

    def test_independent_verifier_failure_fails_closed(self):
        failed = dict(SELECTOR_DIRECT_SOURCE_RECORDS_EXPECTED_REPORT)
        failed["verified"] = False
        failed["errors"] = ["injected failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_selector_direct_source_records",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _selector_direct_source_record_claims(
                    ROOT, self._rom(), self._baseline()
                )


class SelectorCodeWindowCoverageTests(unittest.TestCase):
    """Coverage promotion contract for the ten fixed selector code windows."""

    EXPECTED_RANGES = [
        [0x0663A6, 0x0663B4],
        [0x0663EE, 0x0663F4],
        [0x066408, 0x06640C],
        [0x066420, 0x066424],
        [0x066438, 0x06643C],
        [0x0664EC, 0x0664F8],
        [0x066526, 0x066530],
        [0x0666CC, 0x0666F8],
        [0x08A6AC, 0x08A700],
        [0x08AFE0, 0x08B07C],
        [0x08B2C8, 0x08B2EA],
        [0x08B356, 0x08B580],
        [0x08B58C, 0x08B5C2],
        [0x08B5E6, 0x08B640],
        [0x08B64E, 0x08B65A],
        [0x08CD5A, 0x08CDF8],
        [0x097C96, 0x097C98],
        [0x09C4FC, 0x09C504],
        [0x09C526, 0x09C528],
    ]

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != SELECTOR_CODE_WINDOWS_BATCH
        ]

    def test_promotes_exact_current_unknown_projection(self):
        rom = self._rom()
        baseline = self._baseline()
        baseline_segments = atomize_claims(len(rom), baseline)
        claims = _selector_code_window_claims(ROOT, rom, baseline)
        self.assertEqual(19, len(claims))
        self.assertEqual(self.EXPECTED_RANGES, [claim["range"] for claim in claims])
        self.assertEqual(
            1_252, sum(end - start for start, end in self.EXPECTED_RANGES)
        )
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual("consumer_code_slice", claim["primary_class"])
            self.assertEqual("consumer_code_slice", claim["claim_kind"])
            self.assertEqual(SELECTOR_CODE_WINDOWS_BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertFalse(claim["instruction_only_claimed"])
            self.assertFalse(claim["runtime_reachability_claimed"])
            self.assertFalse(claim["safe_editing"])
            self.assertFalse(claim["allocatable"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(
                f"/promotion_ranges/{index}", claim["evidence_selector"]
            )
            self.assertEqual(
                SELECTOR_CODE_WINDOWS_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                SELECTOR_CODE_WINDOWS_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                SELECTOR_CODE_WINDOWS_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in intersections)
            )

    def test_existing_primary_overlap_fails_closed(self):
        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-selector-code-overlap",
                "range": self.EXPECTED_RANGES[0],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            _selector_code_window_claims(ROOT, self._rom(), baseline)

    def test_independent_verifier_failure_fails_closed(self):
        failed = dict(SELECTOR_CODE_WINDOWS_EXPECTED_REPORT)
        failed["verified"] = False
        failed["errors"] = ["injected failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_selector_code_windows",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _selector_code_window_claims(ROOT, self._rom(), self._baseline())

    def test_rom_tampering_fails_closed(self):
        tampered = bytearray(self._rom())
        tampered[self.EXPECTED_RANGES[0][0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            _selector_code_window_claims(ROOT, bytes(tampered), self._baseline())


class MenuPortraitPaletteCoverageTests(unittest.TestCase):
    """Coverage promotion contract for the 70 physical portrait palettes."""

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (
                ROOT
                / "artifacts/rom-menu-portrait-palette-inventory-v1"
                / "rom-menu-portrait-palette-inventory.json"
            ).read_text(encoding="utf-8")
        )

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != MENU_PORTRAIT_PALETTE_BATCH
        ]

    def test_promotes_exact_physical_current_unknown_denominator(self):
        rom = self._rom()
        payload = self._payload()
        baseline = self._baseline()
        baseline_segments = atomize_claims(len(rom), baseline)
        claims = _menu_portrait_palette_claims(ROOT, rom, baseline)
        expected_ranges = [record["range"] for record in payload["physical_palettes"]]

        self.assertEqual(70, len(claims))
        self.assertEqual(expected_ranges, [claim["range"] for claim in claims])
        self.assertEqual(8_960, sum(end - start for start, end in expected_ranges))
        self.assertEqual(
            [0, 67, 68, 69, 70],
            claims[0]["source_resource_ids"],
        )
        self.assertEqual(56, claims[0]["logical_alias_count"])
        self.assertTrue(all(len(claim["range"]) == 2 for claim in claims))
        self.assertTrue(all(claim["range"][1] - claim["range"][0] == 128 for claim in claims))
        self.assertEqual(
            70,
            len({tuple(claim["range"]) for claim in claims}),
        )
        self.assertGreater(
            len(claims),
            len({claim["bytes_sha256"] for claim in claims}),
            "physical ranges must not be deduplicated by equal content hash",
        )
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual("menu_portrait_palette_bgr555", claim["primary_class"])
            self.assertEqual(
                "menu_portrait_palette_source_range", claim["claim_kind"]
            )
            self.assertEqual(MENU_PORTRAIT_PALETTE_BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertFalse(claim["natural_runtime_reachability_claimed"])
            self.assertFalse(claim["runtime_pixel_equivalence_claimed"])
            self.assertFalse(claim["editing_safety_claimed"])
            self.assertFalse(claim["allocatable_space_claimed"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(
                f"/physical_palettes/{index}", claim["evidence_selector"]
            )
            self.assertEqual(
                MENU_PORTRAIT_PALETTE_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                MENU_PORTRAIT_PALETTE_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                MENU_PORTRAIT_PALETTE_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in intersections)
            )

    def test_existing_primary_overlap_fails_closed(self):
        baseline = self._baseline()
        first_start = self._payload()["physical_palettes"][0]["range"][0]
        baseline.append(
            {
                "id": "injected-menu-palette-one-byte-overlap",
                "range": [first_start, first_start + 1],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "fully current unknown"):
            _menu_portrait_palette_claims(ROOT, self._rom(), baseline)

    def test_independent_verifier_failure_fails_closed(self):
        failed = dict(MENU_PORTRAIT_PALETTE_EXPECTED_REPORT)
        failed["verified"] = False
        failed["errors"] = ["injected failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_menu_portrait_palette_inventory",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _menu_portrait_palette_claims(ROOT, self._rom(), self._baseline())

    def test_duplicate_batch_and_rom_tampering_fail_closed(self):
        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-menu-palette-batch",
                "range": [0, 1],
                "role": "secondary",
                "claim_kind": "test-only",
                "promotion_batch": MENU_PORTRAIT_PALETTE_BATCH,
            }
        )
        with self.assertRaisesRegex(ValueError, "already present"):
            _menu_portrait_palette_claims(ROOT, self._rom(), baseline)

        tampered = bytearray(self._rom())
        tampered[self._payload()["physical_palettes"][0]["range"][0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            _menu_portrait_palette_claims(
                ROOT, bytes(tampered), self._baseline()
            )


class SceneVisualSourceRangeCoverageTests(unittest.TestCase):
    """Coverage promotion contract for the frozen scene-visual source extents."""

    ARTIFACT = ROOT / "artifacts/rom-scene-visual-source-ranges-v1"

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (cls.ARTIFACT / "rom-scene-visual-source-ranges.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != SCENE_VISUAL_SOURCE_BATCH
        ]

    def test_promotes_exact_current_unknown_denominator_and_preserves_overlap(self):
        rom = self._rom()
        payload = self._payload()
        baseline = self._baseline()
        baseline_segments = atomize_claims(len(rom), baseline)
        records = payload["promotion_denominator"]["records"]
        claims = _scene_visual_source_range_claims(ROOT, rom, baseline)

        self.assertEqual(29, len(claims))
        self.assertEqual([record["range"] for record in records], [
            claim["range"] for claim in claims
        ])
        self.assertEqual(3_257, sum(
            claim["range"][1] - claim["range"][0] for claim in claims
        ))
        self.assertEqual(
            SCENE_VISUAL_SOURCE_CLASS_COUNTS,
            {
                primary_class: sum(
                    claim["primary_class"] == primary_class for claim in claims
                )
                for primary_class in SCENE_VISUAL_SOURCE_CLASS_COUNTS
            },
        )
        self.assertEqual(
            SCENE_VISUAL_SOURCE_CLASS_BYTES,
            {
                primary_class: sum(
                    claim["range"][1] - claim["range"][0]
                    for claim in claims
                    if claim["primary_class"] == primary_class
                )
                for primary_class in SCENE_VISUAL_SOURCE_CLASS_BYTES
            },
        )

        pack5 = next(
            claim for claim in claims if claim["source_id"] == "pack-05-definition"
        )
        self.assertEqual([0x407C0F, 0x407C50], pack5["range"])
        self.assertFalse(any(
            claim["range"][0] < 0x407C0F and 0x407BF0 < claim["range"][1]
            for claim in claims
        ))
        old_owner = next(
            claim for claim in baseline if claim["id"] == "unbound-lz77-35-407bec"
        )
        self.assertEqual([0x407BEC, 0x407C0F], old_owner["range"])
        self.assertEqual("lz77_syntax_unbound", old_owner["primary_class"])

        for index, (record, claim) in enumerate(zip(records, claims, strict=True)):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual("scene_visual_source_range", claim["claim_kind"])
            self.assertEqual(SCENE_VISUAL_SOURCE_BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(record["source_id"], claim["source_id"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(
                f"/promotion_denominator/records/{index}",
                claim["evidence_selector"],
            )
            self.assertEqual(
                SCENE_VISUAL_SOURCE_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                SCENE_VISUAL_SOURCE_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                SCENE_VISUAL_SOURCE_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )
            self.assertFalse(claim["natural_runtime_reachability_claimed"])
            self.assertFalse(claim["final_pixel_equivalence_claimed"])
            self.assertFalse(claim["editing_or_relocation_safety_claimed"])
            self.assertFalse(claim["allocatable_space_claimed"])
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(all(
                segment["primary_class"] == "unknown" for segment in intersections
            ))

    def test_existing_one_byte_primary_overlap_fails_closed(self):
        baseline = self._baseline()
        start = self._payload()["promotion_denominator"]["records"][0]["range"][0]
        baseline.append(
            {
                "id": "injected-scene-visual-one-byte-overlap",
                "range": [start, start + 1],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "fully current unknown"):
            _scene_visual_source_range_claims(ROOT, self._rom(), baseline)

    def test_independent_verifier_failure_fails_closed(self):
        failed = copy.deepcopy(SCENE_VISUAL_SOURCE_EXPECTED_REPORT)
        failed["verified"] = False
        failed["errors"] = ["injected failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_scene_visual_source_ranges",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _scene_visual_source_range_claims(
                    ROOT, self._rom(), self._baseline()
                )

    def test_manifest_identity_and_duplicate_batch_fail_closed(self):
        original_sha256_file = __import__(
            "tools.audit_rom_byte_coverage", fromlist=["_sha256_file"]
        )._sha256_file

        def drift_manifest(path: Path) -> str:
            if path.name == "manifest.json" and path.parent.name == SCENE_VISUAL_SOURCE_BATCH:
                return "0" * 64
            return original_sha256_file(path)

        with mock.patch(
            "tools.audit_rom_byte_coverage._sha256_file",
            side_effect=drift_manifest,
        ):
            with self.assertRaisesRegex(ValueError, "manifest hash"):
                _scene_visual_source_range_claims(
                    ROOT, self._rom(), self._baseline()
                )

        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-scene-visual-batch",
                "range": [0, 1],
                "role": "secondary",
                "promotion_batch": SCENE_VISUAL_SOURCE_BATCH,
            }
        )
        with self.assertRaisesRegex(ValueError, "already present"):
            _scene_visual_source_range_claims(ROOT, self._rom(), baseline)

    def test_rom_tampering_fails_closed(self):
        tampered = bytearray(self._rom())
        tampered[self._payload()["promotion_denominator"]["records"][0]["range"][0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            _scene_visual_source_range_claims(
                ROOT, bytes(tampered), self._baseline()
            )


class CutsceneObjSourceRangeCoverageTests(unittest.TestCase):
    """Coverage contract for the 28 fixed Cutscene OBJ source records."""

    ARTIFACT = ROOT / "artifacts/rom-cutscene-obj-source-ranges-v1"

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (cls.ARTIFACT / "rom-cutscene-obj-source-ranges.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != CUTSCENE_OBJ_SOURCE_BATCH
        ]

    def test_promotes_exact_four_kind_current_unknown_denominator(self):
        rom = self._rom()
        payload = self._payload()
        baseline = self._baseline()
        baseline_segments = atomize_claims(len(rom), baseline)
        claims = _cutscene_obj_source_range_claims(ROOT, rom, baseline)

        self.assertEqual(28, len(claims))
        self.assertEqual(
            [record["range"] for record in payload["records"]],
            [claim["range"] for claim in claims],
        )
        self.assertEqual(
            400,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_CLASS_COUNTS,
            {
                primary_class: sum(
                    claim["primary_class"] == primary_class for claim in claims
                )
                for primary_class in CUTSCENE_OBJ_SOURCE_CLASS_COUNTS
            },
        )
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_CLASS_BYTES,
            {
                primary_class: sum(
                    claim["range"][1] - claim["range"][0]
                    for claim in claims
                    if claim["primary_class"] == primary_class
                )
                for primary_class in CUTSCENE_OBJ_SOURCE_CLASS_BYTES
            },
        )
        self.assertEqual(
            CUTSCENE_OBJ_SOURCE_RANGE_DENOMINATOR_SHA256,
            hashlib.sha256(
                json.dumps(
                    [
                        {
                            key: claim[key]
                            for key in (
                                "id",
                                "range",
                                "primary_class",
                                "bytes_sha256",
                                "evidence_selector",
                            )
                        }
                        for claim in claims
                    ],
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("ascii")
            ).hexdigest(),
        )
        for index, (record, claim) in enumerate(
            zip(payload["records"], claims, strict=True)
        ):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual("cutscene_obj_source_range", claim["claim_kind"])
            self.assertEqual(CUTSCENE_OBJ_SOURCE_BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(record["kind"], claim["source_kind"])
            self.assertEqual(record["resource_id"], claim["resource_id"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(f"/records/{index}", claim["evidence_selector"])
            self.assertEqual(
                CUTSCENE_OBJ_SOURCE_MANIFEST_SHA256,
                claim["promotion_manifest_sha256"],
            )
            self.assertEqual(
                CUTSCENE_OBJ_SOURCE_VERIFIER.as_posix(),
                claim["independent_verifier_path"],
            )
            self.assertEqual(
                CUTSCENE_OBJ_SOURCE_VERIFIER_SHA256,
                claim["independent_verifier_sha256"],
            )
            self.assertFalse(claim["natural_runtime_reachability_claimed"])
            self.assertFalse(claim["final_pixel_equivalence_claimed"])
            self.assertFalse(claim["definition_unknown_field_semantics_claimed"])
            self.assertFalse(claim["graphics_or_palette_expansion_claimed"])
            self.assertFalse(claim["editing_or_relocation_safety_claimed"])
            self.assertFalse(claim["allocatable_space_claimed"])
            intersections = [
                segment
                for segment in baseline_segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            self.assertTrue(intersections)
            self.assertTrue(
                all(segment["primary_class"] == "unknown" for segment in intersections)
            )

    def test_committed_manifest_publishes_the_cutscene_obj_scope_boundary(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            any(
                "Cutscene OBJ source-range inventory" in limitation
                and "28 complete current-unknown ranges" in limitation
                and "400 bytes" in limitation
                and "unknown component field semantics" in limitation
                and "natural runtime reachability" in limitation
                and "allocatable space" in limitation
                for limitation in coverage["limitations"]
            )
        )

    def test_overlap_and_duplicate_batch_fail_closed(self):
        baseline = self._baseline()
        first_start = self._payload()["records"][0]["range"][0]
        baseline.append(
            {
                "id": "injected-cutscene-obj-overlap",
                "range": [first_start, first_start + 1],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "fully current unknown"):
            _cutscene_obj_source_range_claims(ROOT, self._rom(), baseline)

        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-cutscene-obj-batch",
                "range": [0, 1],
                "role": "secondary",
                "promotion_batch": CUTSCENE_OBJ_SOURCE_BATCH,
            }
        )
        with self.assertRaisesRegex(ValueError, "already present"):
            _cutscene_obj_source_range_claims(ROOT, self._rom(), baseline)

    def test_verifier_and_rom_tampering_fail_closed(self):
        failed = copy.deepcopy(CUTSCENE_OBJ_SOURCE_EXPECTED_REPORT)
        failed["verified"] = False
        failed["errors"] = ["injected failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_cutscene_obj_source_ranges",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                _cutscene_obj_source_range_claims(
                    ROOT, self._rom(), self._baseline()
                )

        tampered = bytearray(self._rom())
        tampered[self._payload()["records"][0]["range"][0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            _cutscene_obj_source_range_claims(
                ROOT, bytes(tampered), self._baseline()
            )


class BattlePresentationTileAssetsAlignmentGapCoverageTests(unittest.TestCase):
    """Frozen contract for the two-byte battle-presentation/tile-assets gap."""

    BATCH = "rom-battle-presentation-tile-assets-alignment-gap-coverage-v1"
    PRIMARY_CLASS = "battle_presentation_binding_to_tile_assets_4byte_alignment_gap"
    CLAIM_KIND = "battle_presentation_tile_assets_alignment_gap_bytes"
    CLAIM_ID = "battle-presentation-tile-assets-alignment-gap-5a320a"
    CANDIDATE_RANGE = [0x5A320A, 0x5A320C]
    CANDIDATE_GBA_RANGE = [0x085A320A, 0x085A320C]
    CANDIDATE_BYTES_SHA256 = (
        "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
    )
    RANGE_DENOMINATOR_SHA256 = (
        "7649610dfb23720aa7a052893bf3fec739e423ddc826720e9cfa8529bea1882c"
    )
    LEFT_TABLE_RANGE = [0x5A2EF4, 0x5A320A]
    LEFT_TABLE_SHA256 = (
        "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8"
    )
    LEFT_RECORD_COUNT = 79
    LEFT_RECORD_SIZE = 10
    LEFT_FINAL_RECORD_INDEX = 78
    LEFT_FINAL_RECORD_RANGE = [0x5A3200, 0x5A320A]
    LEFT_FINAL_RECORD_RAW_HEX = "02a2a300000000000000"
    LEFT_FINAL_RECORD_SHA256 = (
        "6ae83895ea1b77c98338369bb60f5068fb9b7b39fb6b20f0cf6bf0273cf6e0a3"
    )
    RIGHT_TABLE_RANGE = [0x5A320C, 0x5A4708]
    RIGHT_TABLE_SHA256 = (
        "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
    )
    RIGHT_RECORD_COUNT = 79
    RIGHT_RECORD_SIZE = 68
    RIGHT_FIRST_RECORD_RANGE = [0x5A320C, 0x5A3250]
    RIGHT_FIRST_RECORD_SHA256 = (
        "f6383ba097db640fb0f3364e990bfe94ebf28ac92516add592e5a7e1e1df2fe9"
    )
    RIGHT_FIRST_DESCRIPTOR_ID = 0
    RIGHT_FIRST_CONSUMER_ID = 1
    RIGHT_FIRST_STATUS = "partial"
    RIGHT_FIRST_RAW_WORDS = [
        "0x00020000",
        "0x00020048",
        "0x00000077",
        "0x08349EB4",
        "0x0834AFC8",
        "0x0834B228",
        "0x083497BC",
        "0x08349D10",
        "0x08349E74",
        "0x0A100410",
        "0x083658C4",
        "0x08367630",
        "0x08367960",
        "0x0A1E0418",
        "0x00000000",
        "0x0836774C",
        "0x00000000",
    ]
    RIGHT_BANK_PATH = "sequel/content/tile-assets/bank.json"
    RIGHT_BANK_SHA256 = (
        "9ef92f5c358f114a660eeea42ab5358f37435047d7bb91708c3a80274d5df218"
    )
    LEFT_ARTIFACT_PATH = "artifacts/battle-presentation-glyphs-v1"
    LEFT_MANIFEST_PATH = (
        "artifacts/battle-presentation-glyphs-v1/manifest.json"
    )
    LEFT_MANIFEST_SHA256 = (
        "ecc44fde0d886b75397d34181112f5b86dbb791b09e3b85797e9b4013f4e74a7"
    )
    LEFT_VERIFIER_PATH = "tools/verify_battle_presentation_rom_ranges.py"
    LEFT_VERIFIER_SHA256 = (
        "0c2b219f87bbdc19dc64aee97f2e131783978dc7c4dc70deb2c1764c9a9766fb"
    )
    LEFT_UPSTREAM_TEST_PATH = "tests/test_verify_battle_presentation_rom_ranges.py"
    LEFT_UPSTREAM_TEST_SHA256 = (
        "0337a0db38640b28af048a22043914ee2cdfce85bc5242bca819cf29d993adfb"
    )
    RIGHT_ARTIFACT_PATH = "artifacts/tile-assets-bg-v2"
    RIGHT_MANIFEST_PATH = "artifacts/tile-assets-bg-v2/manifest.json"
    RIGHT_MANIFEST_SHA256 = (
        "1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749"
    )
    RIGHT_VERIFIER_PATH = "tools/verify_tile_asset_bg_export.py"
    RIGHT_VERIFIER_SHA256 = (
        "4273c6d0cada4e7d018a805e5c96fca9654c19aabeff9a1a7b26e5aa8380d57c"
    )
    RIGHT_UPSTREAM_TEST_PATH = "tests/test_export_tile_asset_bg_layers.py"
    RIGHT_UPSTREAM_TEST_SHA256 = (
        "f5bc75c6dee2eb487ef26ed91ee3e4663e5cb5c3237d5e3887659822d5330448"
    )
    LEFT_VERIFY_REPORT = {
        "schema": "battle-presentation-rom-range-verification-v1",
        "verified": True,
        "message_count": 79,
        "message_bytes": 1148,
        "table_bytes": 1794,
        "palette_bytes": 32,
        "errors": [],
    }
    RIGHT_VERIFY_REPORT = {
        "schema": "tile-assets-bg-verification-v2",
        "rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
        "verified_descriptors": 79,
        "verified_complete_layers": 236,
        "verified_atlases": 108,
        "errors": [],
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
        ]

    @classmethod
    def _minimal_owner_baseline(cls) -> list[dict]:
        return [
            claim
            for claim in cls._baseline()
            if claim.get("id")
            in {"battle-presentation-bindings-table", "bank-tile-assets-000"}
        ]

    def _helper(self):
        return getattr(
            coverage_auditor,
            "_battle_presentation_tile_assets_alignment_gap_claims",
        )

    def test_promotes_exact_gap_and_preserves_fixed_count_endpoint_semantics(self):
        claims = self._helper()(ROOT, self._rom(), self._baseline())
        self.assertEqual(1, len(claims))
        claim = claims[0]

        self.assertEqual(self.CLAIM_ID, claim["id"])
        self.assertEqual(self.CANDIDATE_RANGE, claim["range"])
        self.assertEqual(self.CANDIDATE_GBA_RANGE, claim["gba_range"])
        self.assertEqual("primary", claim["role"])
        self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
        self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
        self.assertEqual(self.BATCH, claim["promotion_batch"])
        self.assertEqual("unknown", claim["promoted_from_primary_class"])
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["bytes_sha256"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["packed_bytes_sha256"])
        self.assertEqual(self.RANGE_DENOMINATOR_SHA256, claim["range_denominator_sha256"])
        self.assertEqual(2, claim["zero_byte_count"])
        self.assertTrue(claim["all_zero"])

        self.assertEqual(self.LEFT_TABLE_RANGE, claim["battle_presentation_binding_table_range"])
        self.assertEqual(self.LEFT_TABLE_SHA256, claim["battle_presentation_binding_table_sha256"])
        self.assertEqual(self.LEFT_RECORD_COUNT, claim["battle_presentation_binding_record_count"])
        self.assertEqual(self.LEFT_RECORD_SIZE, claim["battle_presentation_binding_record_size"])
        self.assertEqual(self.LEFT_FINAL_RECORD_INDEX, claim["battle_presentation_final_record_index"])
        self.assertEqual(self.LEFT_FINAL_RECORD_RANGE, claim["battle_presentation_final_record_range"])
        self.assertEqual(self.LEFT_FINAL_RECORD_RAW_HEX, claim["battle_presentation_final_record_raw_hex"])
        self.assertEqual(self.LEFT_FINAL_RECORD_SHA256, claim["battle_presentation_final_record_sha256"])
        self.assertEqual(2, claim["battle_presentation_final_record_glyph_count"])
        self.assertEqual([162, 163], claim["battle_presentation_final_record_glyph_ids"])
        self.assertFalse(claim["battle_presentation_final_record_is_terminator"])
        self.assertEqual("fixed_count_boundary", claim["battle_presentation_endpoint_semantics"])

        self.assertEqual(self.RIGHT_TABLE_RANGE, claim["tile_assets_table_range"])
        self.assertEqual(self.RIGHT_TABLE_SHA256, claim["tile_assets_table_sha256"])
        self.assertEqual(self.RIGHT_RECORD_COUNT, claim["tile_assets_record_count"])
        self.assertEqual(self.RIGHT_RECORD_SIZE, claim["tile_assets_record_size"])
        self.assertEqual(self.RIGHT_FIRST_RECORD_RANGE, claim["tile_assets_first_record_range"])
        self.assertEqual(self.RIGHT_FIRST_RECORD_SHA256, claim["tile_assets_first_record_sha256"])
        self.assertEqual(self.RIGHT_FIRST_DESCRIPTOR_ID, claim["tile_assets_first_descriptor_id"])
        self.assertEqual(self.RIGHT_FIRST_CONSUMER_ID, claim["tile_assets_first_consumer_id"])
        self.assertEqual(self.RIGHT_FIRST_STATUS, claim["tile_assets_first_descriptor_status"])
        self.assertEqual(self.RIGHT_FIRST_RAW_WORDS, claim["tile_assets_first_record_raw_words"])
        self.assertEqual(17, claim["tile_assets_first_record_u32_word_count"])

        self.assertEqual(0x5A320C, claim["alignment_target"])
        self.assertEqual("(0x5A320A + 3) & ~3 == 0x5A320C", claim["alignment_formula"])
        self.assertEqual("(start + 3) & ~3", claim["alignment_formula_expression"])
        self.assertEqual(2, claim["alignment_gap_bytes"])
        self.assertTrue(claim["alignment_gap_is_exact"])
        self.assertEqual("fixed_count_boundary", claim["previous_owner_endpoint_kind"])
        self.assertEqual(["/tables/bindings", "/messages/78/binding"], claim["previous_owner_evidence_selectors"])
        self.assertEqual(["/source_table", "/descriptors/0"], claim["next_owner_evidence_selectors"])

        for flag in (
            "reserved_space_claimed",
            "free_space_claimed",
            "padding_claimed",
            "natural_runtime_reachability_claimed",
            "global_unreachable_claimed",
            "editing_or_relocation_safety_claimed",
            "editable_claimed",
            "relocatable_claimed",
            "safe_allocatable_space_claimed",
            "adjacent_bytes_claimed",
            "additional_table_field_semantics_claimed",
            "all_consumers_claimed",
            "consumer_completeness_claimed",
        ):
            with self.subTest(flag=flag):
                self.assertFalse(claim[flag])
        self.assertEqual(
            [
                "Only the exact two current-unknown bytes needed to reach the next 4-byte boundary between the frozen 79-record battle-presentation binding table and the frozen 79-record tile-assets table are classified.",
                "The left endpoint is an exact fixed-count table boundary, not an explicit terminator record; padding, reserved/free space, reachability, editing, relocation, allocation, adjacent bytes, additional fields, and consumer completeness remain unclaimed.",
            ],
            claim["limitations"],
        )

    def test_verifies_canonical_evidence_selectors_hashes_and_reports(self):
        claims = self._helper()(ROOT, self._rom(), self._baseline())
        self.assertEqual(1, len(claims))
        claim = claims[0]
        self.assertEqual(self.LEFT_MANIFEST_PATH, claim["previous_owner_evidence_path"])
        self.assertEqual(self.LEFT_MANIFEST_SHA256, claim["previous_owner_evidence_sha256"])
        self.assertEqual(self.LEFT_VERIFIER_PATH, claim["previous_owner_verifier_path"])
        self.assertEqual(self.LEFT_VERIFIER_SHA256, claim["previous_owner_verifier_sha256"])
        self.assertEqual(self.LEFT_UPSTREAM_TEST_PATH, claim["previous_owner_upstream_test_path"])
        self.assertEqual(self.LEFT_UPSTREAM_TEST_SHA256, claim["previous_owner_upstream_test_sha256"])
        self.assertEqual(self.RIGHT_MANIFEST_PATH, claim["next_owner_evidence_path"])
        self.assertEqual(self.RIGHT_MANIFEST_SHA256, claim["next_owner_evidence_sha256"])
        self.assertEqual(self.RIGHT_VERIFIER_PATH, claim["next_owner_verifier_path"])
        self.assertEqual(self.RIGHT_VERIFIER_SHA256, claim["next_owner_verifier_sha256"])
        self.assertEqual(self.RIGHT_UPSTREAM_TEST_PATH, claim["next_owner_upstream_test_path"])
        self.assertEqual(self.RIGHT_UPSTREAM_TEST_SHA256, claim["next_owner_upstream_test_sha256"])
        self.assertEqual(self.RIGHT_BANK_PATH, claim["next_owner_bank_evidence_path"])
        self.assertEqual(self.RIGHT_BANK_SHA256, claim["next_owner_bank_evidence_sha256"])
        self.assertEqual("battle-presentation-bindings-table", claim["previous_owner_id"])
        self.assertEqual(self.LEFT_TABLE_RANGE, claim["previous_owner_range"])
        self.assertEqual("primary", claim["previous_owner_role"])
        self.assertEqual("battle_presentation_message_glyph_binding_table", claim["previous_owner_primary_class"])
        self.assertEqual("battle_presentation_table", claim["previous_owner_claim_kind"])
        self.assertEqual("bank-tile-assets-000", claim["next_owner_id"])
        self.assertEqual(self.RIGHT_TABLE_RANGE, claim["next_owner_range"])
        self.assertEqual("primary", claim["next_owner_role"])
        self.assertEqual("fixed_table", claim["next_owner_primary_class"])
        self.assertEqual("bank_record_bytes", claim["next_owner_claim_kind"])
        self.assertEqual(self.LEFT_VERIFY_REPORT, claim["previous_owner_verifier_report"])
        self.assertEqual(self.RIGHT_VERIFY_REPORT, claim["next_owner_verifier_report"])

    def test_fails_closed_on_overlap_duplicates_and_invalid_baseline_claims(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        for role, message in (("primary", "current unknown"), ("secondary", "secondary")):
            with self.subTest(role=role):
                injected = {
                    "id": f"injected-{role}-overlap",
                    "range": [0x5A320A, 0x5A320B],
                    "role": role,
                    "claim_kind": "injected_overlap",
                }
                if role == "primary":
                    injected["primary_class"] = "injected_known"
                with self.assertRaisesRegex(ValueError, message):
                    helper(ROOT, rom, [*baseline, injected])

        for injected in (
            {
                "id": "injected-duplicate-batch",
                "range": [0, 1],
                "role": "secondary",
                "claim_kind": "injected_duplicate",
                "promotion_batch": self.BATCH,
            },
            {
                "id": "injected-duplicate-kind",
                "range": [0, 1],
                "role": "secondary",
                "claim_kind": self.CLAIM_KIND,
                "promotion_batch": "injected-other-batch",
            },
        ):
            with self.assertRaisesRegex(ValueError, "already present"):
                helper(ROOT, rom, [*baseline, injected])

        duplicate_id = dict(baseline[0])
        with self.assertRaisesRegex(ValueError, "claim IDs are not unique"):
            helper(ROOT, rom, [*baseline, duplicate_id])
        output_id_conflict = {
            "id": self.CLAIM_ID,
            "range": [0, 1],
            "role": "secondary",
            "claim_kind": "injected_existing_output_claim_id",
            "promotion_batch": "injected-existing-output-claim-id",
        }
        with self.assertRaisesRegex(
            ValueError, "claim ID.*already present|duplicate claim ID"
        ):
            helper(ROOT, rom, [*baseline, output_id_conflict])
        invalid_role = dict(baseline[0])
        invalid_role["id"] = "invalid-role"
        invalid_role["role"] = "tertiary"
        with self.assertRaisesRegex(ValueError, "role changed"):
            helper(ROOT, rom, [invalid_role])
        invalid_range = dict(baseline[0])
        invalid_range["id"] = "invalid-range"
        invalid_range["range"] = [0x5A320A, 0x5A320A]
        with self.assertRaisesRegex(ValueError, "invalid range|outside"):
            helper(ROOT, rom, [invalid_range])

    def test_fails_closed_on_rom_candidate_table_and_row_drift(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        tampered = bytearray(self._rom())
        tampered[0x5A320A] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

        for constant, drifted, message in (
            ("BATTLE_PRESENTATION_TILE_ASSETS_GAP_RANGE", (0x5A3209, 0x5A320C), "candidate|alignment"),
            ("BATTLE_PRESENTATION_BINDING_TABLE_SHA256", "0" * 64, "table|contract"),
            ("BATTLE_PRESENTATION_FINAL_RECORD_SHA256", "0" * 64, "final record|contract"),
            ("TILE_ASSETS_TABLE_SHA256", "0" * 64, "table|contract"),
            ("TILE_ASSETS_FIRST_RECORD_SHA256", "0" * 64, "first record|contract"),
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, drifted):
                    with self.assertRaisesRegex(ValueError, message):
                        helper(ROOT, self._rom(), baseline)

    def test_fails_closed_on_hash_constant_owner_literal_and_verifier_drift(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        for constant in (
            "BATTLE_PRESENTATION_TILE_ASSETS_GAP_BATCH",
            "BATTLE_PRESENTATION_TILE_ASSETS_GAP_CLAIM_ID",
            "BATTLE_PRESENTATION_TILE_ASSETS_GAP_PRIMARY_CLASS",
            "BATTLE_PRESENTATION_TILE_ASSETS_GAP_CLAIM_KIND",
            "BATTLE_PRESENTATION_TILE_ASSETS_GAP_BYTES_SHA256",
            "BATTLE_PRESENTATION_TILE_ASSETS_GAP_RANGE_DENOMINATOR_SHA256",
            "BATTLE_PRESENTATION_GAP_LEFT_MANIFEST_SHA256",
            "BATTLE_PRESENTATION_GAP_LEFT_VERIFIER_SHA256",
            "BATTLE_PRESENTATION_GAP_LEFT_UPSTREAM_TEST_SHA256",
            "BATTLE_PRESENTATION_GAP_RIGHT_MANIFEST_SHA256",
            "BATTLE_PRESENTATION_GAP_RIGHT_VERIFIER_SHA256",
            "BATTLE_PRESENTATION_GAP_RIGHT_UPSTREAM_TEST_SHA256",
            "BATTLE_PRESENTATION_GAP_RIGHT_BANK_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaisesRegex(ValueError, "contract|identity|changed|candidate"):
                        helper(ROOT, self._rom(), baseline)

        identity_cases = (
            ("BATTLE_PRESENTATION_GAP_LEFT_OWNER_ID", "battle-presentation-bindings-table", "drifted-left-owner"),
            ("BATTLE_PRESENTATION_GAP_RIGHT_OWNER_ID", "bank-tile-assets-000", "drifted-right-owner"),
            ("BATTLE_PRESENTATION_GAP_LEFT_OWNER_RANGE", "battle-presentation-bindings-table", [0x5A2EF3, 0x5A320A]),
            ("BATTLE_PRESENTATION_GAP_RIGHT_OWNER_RANGE", "bank-tile-assets-000", [0x5A320C, 0x5A4707]),
            ("BATTLE_PRESENTATION_GAP_LEFT_OWNER_PRIMARY_CLASS", "battle_presentation_message_glyph_binding_table", "drifted-left-class"),
            ("BATTLE_PRESENTATION_GAP_RIGHT_OWNER_PRIMARY_CLASS", "fixed_table", "drifted-right-class"),
            ("BATTLE_PRESENTATION_GAP_LEFT_OWNER_CLAIM_KIND", "battle_presentation_table", "drifted-left-kind"),
            ("BATTLE_PRESENTATION_GAP_RIGHT_OWNER_CLAIM_KIND", "bank_record_bytes", "drifted-right-kind"),
        )
        for constant, owner_id, drifted in identity_cases:
            with self.subTest(constant=constant):
                field = "range" if constant.endswith("_RANGE") else (
                    "primary_class" if constant.endswith("PRIMARY_CLASS") else (
                        "claim_kind" if constant.endswith("CLAIM_KIND") else "id"
                    )
                )
                with mock.patch.object(coverage_auditor, constant, drifted):
                    with self.assertRaisesRegex(ValueError, "owner.*contract|owner.*identity"):
                        helper(ROOT, self._rom(), baseline)

        failed = {**self.LEFT_VERIFY_REPORT, "verified": False, "errors": ["forced failure"]}
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_presentation_rom_ranges",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, self._rom(), baseline)
        failed = {**self.RIGHT_VERIFY_REPORT, "errors": ["forced failure"]}
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_tile_asset_bg_export",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, self._rom(), baseline)

    def test_fails_closed_on_baseline_owner_evidence_and_denominator_drift(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        drift_cases = (
            ("battle-presentation-bindings-table", "evidence_path", "drifted/manifest.json"),
            ("battle-presentation-bindings-table", "evidence_sha256", "0" * 64),
            ("battle-presentation-bindings-table", "record_count", 78),
            ("battle-presentation-bindings-table", "record_size", 9),
            ("battle-presentation-bindings-table", "bytes_sha256", "0" * 64),
            ("bank-tile-assets-000", "evidence_path", "drifted/bank.json"),
            ("bank-tile-assets-000", "evidence_sha256", "0" * 64),
            ("bank-tile-assets-000", "records", 78),
            ("bank-tile-assets-000", "bytes_sha256", "0" * 64),
        )
        for owner_id, field, drifted in drift_cases:
            with self.subTest(owner_id=owner_id, field=field):
                changed = []
                for item in baseline:
                    clone = dict(item)
                    if clone.get("id") == owner_id:
                        clone[field] = drifted
                    changed.append(clone)
                with self.assertRaisesRegex(ValueError, "owner|denominator|evidence|identity"):
                    helper(ROOT, self._rom(), changed)

    def test_fails_closed_on_all_noncanonical_evidence_paths(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        path_specs = {
            "BATTLE_PRESENTATION_GAP_LEFT_ARTIFACT",
            "BATTLE_PRESENTATION_GAP_RIGHT_ARTIFACT",
            "BATTLE_PRESENTATION_GAP_LEFT_MANIFEST_PATH",
            "BATTLE_PRESENTATION_GAP_RIGHT_MANIFEST_PATH",
            "BATTLE_PRESENTATION_GAP_LEFT_VERIFIER",
            "BATTLE_PRESENTATION_GAP_RIGHT_VERIFIER",
            "BATTLE_PRESENTATION_GAP_LEFT_UPSTREAM_TEST",
            "BATTLE_PRESENTATION_GAP_RIGHT_UPSTREAM_TEST",
            "BATTLE_PRESENTATION_GAP_RIGHT_BANK_PATH",
        }
        path_values = {
            "BATTLE_PRESENTATION_GAP_LEFT_ARTIFACT": self.LEFT_ARTIFACT_PATH,
            "BATTLE_PRESENTATION_GAP_RIGHT_ARTIFACT": self.RIGHT_ARTIFACT_PATH,
            "BATTLE_PRESENTATION_GAP_LEFT_MANIFEST_PATH": self.LEFT_MANIFEST_PATH,
            "BATTLE_PRESENTATION_GAP_RIGHT_MANIFEST_PATH": self.RIGHT_MANIFEST_PATH,
            "BATTLE_PRESENTATION_GAP_LEFT_VERIFIER": self.LEFT_VERIFIER_PATH,
            "BATTLE_PRESENTATION_GAP_RIGHT_VERIFIER": self.RIGHT_VERIFIER_PATH,
            "BATTLE_PRESENTATION_GAP_LEFT_UPSTREAM_TEST": self.LEFT_UPSTREAM_TEST_PATH,
            "BATTLE_PRESENTATION_GAP_RIGHT_UPSTREAM_TEST": self.RIGHT_UPSTREAM_TEST_PATH,
            "BATTLE_PRESENTATION_GAP_RIGHT_BANK_PATH": self.RIGHT_BANK_PATH,
        }
        artifact_constants = {
            "BATTLE_PRESENTATION_GAP_LEFT_ARTIFACT",
            "BATTLE_PRESENTATION_GAP_RIGHT_ARTIFACT",
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as temp_dir:
            temp_root = Path(temp_dir)
            for constant in path_specs:
                with self.subTest(path=constant):
                    linked = temp_root / f"symlink-{constant}"
                    linked.symlink_to(
                        ROOT / path_values[constant],
                        target_is_directory=constant in artifact_constants,
                    )
                    with mock.patch.object(coverage_auditor, constant, linked):
                        with self.assertRaisesRegex(ValueError, "canonical|symlink|path contract|invalid"):
                            helper(ROOT, self._rom(), baseline)

            for constant in path_specs:
                with self.subTest(path=f"same-hash-{constant}"):
                    alias = temp_root / f"alias-{constant}"
                    if constant in artifact_constants:
                        shutil.copytree(ROOT / path_values[constant], alias)
                    else:
                        shutil.copy2(ROOT / path_values[constant], alias)
                    with mock.patch.object(coverage_auditor, constant, alias):
                        with self.assertRaisesRegex(ValueError, "canonical|path contract"):
                            helper(ROOT, self._rom(), baseline)

        with tempfile.TemporaryDirectory() as outside_dir:
            outside_root = Path(outside_dir)
            for constant in path_specs:
                with self.subTest(path=f"outside-{constant}"):
                    outside = outside_root / f"outside-{constant}"
                    if constant in artifact_constants:
                        shutil.copytree(ROOT / path_values[constant], outside)
                    else:
                        shutil.copy2(ROOT / path_values[constant], outside)
                    with mock.patch.object(coverage_auditor, constant, outside):
                        with self.assertRaisesRegex(ValueError, "canonical|outside|invalid"):
                            helper(ROOT, self._rom(), baseline)

            with mock.patch.object(coverage_auditor, "BATTLE_PRESENTATION_GAP_RIGHT_UPSTREAM_TEST", outside_root / "missing.py"):
                with self.assertRaisesRegex(ValueError, "canonical|path contract|invalid"):
                    helper(ROOT, self._rom(), baseline)

    def test_does_not_call_atomize_claims(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("atomize_claims must not be called"),
        ):
            claims = self._helper()(ROOT, self._rom(), self._minimal_owner_baseline())
        self.assertEqual([self.CANDIDATE_RANGE], [claim["range"] for claim in claims])


class RuntimeStateHandlerTableAlignmentGapCoverageTests(unittest.TestCase):
    """Frozen contract for the runtime-state/handler-pair table gap."""

    BATCH = "rom-runtime-state-handler-table-alignment-gap-coverage-v1"
    CLAIM_ID = "runtime-state-handler-table-alignment-gap-53e696"
    PRIMARY_CLASS = (
        "runtime_state_sequence_table_to_handler_pair_table_4byte_alignment_gap"
    )
    CLAIM_KIND = "runtime_state_handler_table_alignment_gap_bytes"
    CANDIDATE_RANGE = [0x53E696, 0x53E698]
    CANDIDATE_GBA_RANGE = [0x0853E696, 0x0853E698]
    CANDIDATE_BYTES_SHA256 = (
        "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
    )
    RANGE_DENOMINATOR_SHA256 = (
        "11a9249d8cf1654cfbfa44bf13fa9fafc94677f7f1b075b892319e5e524f275c"
    )

    LEFT_TABLE_RANGE = [0x53E596, 0x53E696]
    LEFT_TABLE_SHA256 = (
        "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b"
    )
    LEFT_TABLE_COUNT = 256
    LEFT_TABLE_SIZE = 1
    LEFT_CONSUMER_RANGE = [0x7F0FC, 0x7F110]
    LEFT_CONSUMER_SHA256 = (
        "7b16c1004bdbf81a55ecdcfc523166059ec2a94c81161063d695e1ca59f6cc56"
    )
    LEFT_OWNER_PARTITIONS = [
        {
            "id": "verified-reuse-battle-effect-runtime-state-sequences-53e596",
            "range": [0x53E596, 0x53E5A8],
            "primary_class": "battle_effect_runtime_state_sequence_table",
            "claim_kind": "verified_artifact_reuse_table",
            "bytes_sha256": "33cc41cb7cb0c2838787501880cfde5d7cc10612c640524b5cbae04ccc14c8bb",
        },
        {
            "id": "unbound-lz77-38-53e5a8",
            "range": [0x53E5A8, 0x53E5B3],
            "primary_class": "lz77_syntax_unbound",
            "claim_kind": "unbound_strict_lz77_syntax_range",
            "bytes_sha256": "a0260fdd0de7a5ebc31581e6edf83d33efb1159801cbf5a43c6309b61cd2c210",
        },
        {
            "id": "verified-reuse-battle-effect-runtime-state-sequences-53e5b3",
            "range": [0x53E5B3, 0x53E696],
            "primary_class": "battle_effect_runtime_state_sequence_table",
            "claim_kind": "verified_artifact_reuse_table",
            "bytes_sha256": "ca886661235293ba6fef3f6e29a938c414ced19858c17b2efd26db852f351a77",
        },
    ]
    LEFT_MANIFEST_PATH = "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
    LEFT_MANIFEST_SHA256 = (
        "ec8f41571bb132577ecb7bc57f946a85f219b4c05f3697c89b75be73385b0c73"
    )
    LEFT_VERIFIER_PATH = "tools/verify_battle_effect_sequence_bindings.py"
    LEFT_VERIFIER_SHA256 = (
        "5d0012a1f0a03c6068d0150df16074bdd16cb426325dbb4508db521fc6555a2b"
    )
    LEFT_UPSTREAM_TEST_PATH = "tests/test_export_battle_effect_sequence_bindings.py"
    LEFT_UPSTREAM_TEST_SHA256 = (
        "e453b7f99ebb2f3223c66d101d64634525d192946bcc664d52e5c80c84de7ab1"
    )

    LZ77_ARTIFACT_PATH = "artifacts/rom-unbound-lz77-inventory-v1"
    LZ77_INVENTORY_PATH = (
        "artifacts/rom-unbound-lz77-inventory-v1/inventory.json"
    )
    LZ77_INVENTORY_SHA256 = (
        "52674bcbe44ffe0b1e620602f630c332420b35bcb05676aa2447e9ea2de2b3f1"
    )
    LZ77_MANIFEST_PATH = "artifacts/rom-unbound-lz77-inventory-v1/manifest.json"
    LZ77_MANIFEST_SHA256 = (
        "74e5027cc2fe7993ab4b17983ebfc27ca9cd61a94e3ec7b04720fb8822c1299c"
    )
    LZ77_VERIFIER_PATH = "tools/verify_rom_unbound_lz77_inventory.py"
    LZ77_VERIFIER_SHA256 = (
        "0a309854c9262947feb127188a6a13984b8a8643489af386bf2397c3715c9091"
    )
    LZ77_UPSTREAM_TEST_PATH = "tests/test_rom_unbound_lz77_inventory.py"
    LZ77_UPSTREAM_TEST_SHA256 = (
        "eb5dfc7303d29e88e93f8363e2cda025158ce360c0ba1b009c8dc9f3916cf598"
    )
    LZ77_RECORD_RANGE = [0x53E5A8, 0x53E5B3]
    LZ77_RECORD_SHA256 = (
        "a0260fdd0de7a5ebc31581e6edf83d33efb1159801cbf5a43c6309b61cd2c210"
    )

    RIGHT_OWNER_ID = "bank-map-events-000"
    RIGHT_TABLE_RANGE = [0x53E698, 0x53EE98]
    RIGHT_TABLE_SHA256 = (
        "20e4727cf65dca82626ffc9637cb36561d5851971500b22a282c5a8c65c7c945"
    )
    RIGHT_RECORD_COUNT = 256
    RIGHT_RECORD_SIZE = 8
    RIGHT_FIRST_RECORD_RANGE = [0x53E698, 0x53E6A0]
    RIGHT_FIRST_RECORD_SHA256 = (
        "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc"
    )
    RIGHT_BANK_PATH = "sequel/content/map-events/bank.json"
    RIGHT_BANK_SHA256 = (
        "aaf2c3244502fbf062d8d43721f7e1f6ef83b244aa32cbf3aff4d5e709a99365"
    )
    RIGHT_VERIFIER_PATH = "tools/verify_disproved_bank_candidates.py"
    RIGHT_VERIFIER_SHA256 = (
        "fbdcafb5f173f92cb72ec94bc3d48fba7b6f6e9886b57e8ef61f4af6a1a3e49c"
    )
    RIGHT_UPSTREAM_TEST_PATH = "tests/test_verify_disproved_bank_candidates.py"
    RIGHT_UPSTREAM_TEST_SHA256 = (
        "11f11019370a94bbdfe222fa5bf89f4fca387b38652519e8a08605edc6586c42"
    )
    RIGHT_CONSUMER_RANGE = [0x7F934, 0x7F968]
    RIGHT_CONSUMER_SHA256 = (
        "a1dc1b497f2aebb8e2b865adbc7c7a9abb42f13e7f456130f648b619343cb4f9"
    )
    RIGHT_HISTORICAL_BANK_PATH = "sequel/content/battle-handlers/bank.json"
    RIGHT_HISTORICAL_BANK_SHA256 = (
        "1d3b1ed2da0b7581f09cc7fbf40db5169f7e6c3659bf47def544a9d6ef4886bd"
    )
    RIGHT_AUDIT_NOTE_PATH = "notes/dynamic-verification-audit.md"
    RIGHT_AUDIT_NOTE_SHA256 = (
        "14447c265114d067a7c7cd2cf618827f2a536130d3adf8062d323a1bf03c5f7b"
    )

    LEFT_VERIFY_REPORT = {
        "schema": "battle-effect-sequence-bindings-verification-v1",
        "verified": True,
        "errors": [],
        "verified_runtime_state_bindings": 256,
        "verified_active_action_bindings": 87,
        "verified_ninja_tool_bindings": 94,
        "verified_sequences": 22,
    }
    RIGHT_VERIFY_REPORT = {
        "schema": "disproved-bank-candidate-verification-v1",
        "verified": True,
        "errors": [],
        "bank": "battle-handlers",
        "rejected": True,
        "rejection_scope": "independent_physical_bank_candidate",
        "alternative_logical_consumers_exhaustively_excluded": False,
        "proof_kind": "canonical_table_alias",
        "candidate_range": [0x53E6D8, 0x53E710],
        "candidate_sha256": "aa94c4fc093dbe84a36a2c4db406fc7b26e7f71bba5d95763ee6a61b41a51528",
        "bank_sha256": "1d3b1ed2da0b7581f09cc7fbf40db5169f7e6c3659bf47def544a9d6ef4886bd",
        "evidence_sha256": {
            "notes/dynamic-verification-audit.md": "14447c265114d067a7c7cd2cf618827f2a536130d3adf8062d323a1bf03c5f7b",
            "sequel/content/map-events/bank.json": "aaf2c3244502fbf062d8d43721f7e1f6ef83b244aa32cbf3aff4d5e709a99365",
        },
        "details": {
            "candidate_base_pointer_offsets": [],
            "canonical_base_pointer_offsets": [0x7FA38, 0x7FD88],
            "consumer_code_range": [0x7F934, 0x7F968],
            "consumer_code_sha256": "a1dc1b497f2aebb8e2b865adbc7c7a9abb42f13e7f456130f648b619343cb4f9",
            "source_bank": "map-events",
            "source_record_range": [8, 15],
        },
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("id") != cls.CLAIM_ID
        ]

    @classmethod
    def _minimal_owner_baseline(cls) -> list[dict]:
        owner_ids = {partition["id"] for partition in cls.LEFT_OWNER_PARTITIONS}
        owner_ids.add(cls.RIGHT_OWNER_ID)
        return [claim for claim in cls._baseline() if claim.get("id") in owner_ids]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_runtime_state_handler_table_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "runtime-state handler alignment helper is absent")
        return helper

    def test_promotes_exact_gap_and_freezes_tables_and_nonclaims(self):
        claim = self._helper()(ROOT, self._rom(), self._baseline())[0]
        self.assertEqual(self.CLAIM_ID, claim["id"])
        self.assertEqual(self.CANDIDATE_RANGE, claim["range"])
        self.assertEqual(self.CANDIDATE_GBA_RANGE, claim["gba_range"])
        self.assertEqual("primary", claim["role"])
        self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
        self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
        self.assertEqual(self.BATCH, claim["promotion_batch"])
        self.assertEqual("unknown", claim["promoted_from_primary_class"])
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["bytes_sha256"])
        self.assertEqual(self.CANDIDATE_BYTES_SHA256, claim["packed_bytes_sha256"])
        self.assertEqual(self.RANGE_DENOMINATOR_SHA256, claim["range_denominator_sha256"])
        self.assertTrue(claim["all_zero"])
        self.assertEqual(2, claim["zero_byte_count"])

        self.assertEqual(self.LEFT_TABLE_RANGE, claim["runtime_state_sequence_table_range"])
        self.assertEqual(self.LEFT_TABLE_SHA256, claim["runtime_state_sequence_table_sha256"])
        self.assertEqual(self.LEFT_TABLE_COUNT, claim["runtime_state_sequence_table_entry_count"])
        self.assertEqual(self.LEFT_TABLE_SIZE, claim["runtime_state_sequence_table_entry_size"])
        self.assertEqual(self.LEFT_TABLE_RANGE[1], claim["runtime_state_sequence_table_endpoint"])
        self.assertEqual("fixed_count_u8_domain_boundary", claim["runtime_state_sequence_table_endpoint_semantics"])
        self.assertEqual(self.LEFT_CONSUMER_RANGE, claim["runtime_state_sequence_consumer_code_range"])
        self.assertEqual(self.LEFT_CONSUMER_SHA256, claim["runtime_state_sequence_consumer_code_sha256"])
        self.assertEqual(self.RIGHT_TABLE_RANGE, claim["handler_pair_table_range"])
        self.assertEqual(self.RIGHT_TABLE_SHA256, claim["handler_pair_table_sha256"])
        self.assertEqual(self.RIGHT_RECORD_COUNT, claim["handler_pair_table_record_count"])
        self.assertEqual(self.RIGHT_RECORD_SIZE, claim["handler_pair_table_record_size"])
        self.assertEqual(self.RIGHT_FIRST_RECORD_RANGE, claim["handler_pair_table_first_record_range"])
        self.assertEqual(self.RIGHT_FIRST_RECORD_SHA256, claim["handler_pair_table_first_record_sha256"])
        self.assertEqual(self.RIGHT_CONSUMER_RANGE, claim["handler_pair_table_consumer_code_range"])
        self.assertEqual(self.RIGHT_CONSUMER_SHA256, claim["handler_pair_table_consumer_code_sha256"])

        self.assertEqual(0x53E698, claim["alignment_target"])
        self.assertEqual("(0x53E696 + 3) & ~3 == 0x53E698", claim["alignment_formula"])
        self.assertEqual("(start + 3) & ~3", claim["alignment_formula_expression"])
        self.assertEqual(2, claim["alignment_gap_bytes"])
        self.assertTrue(claim["alignment_gap_is_exact"])
        self.assertFalse(claim["runtime_state_sequence_table_terminator_semantics_claimed"])

        for flag in (
            "padding_claimed",
            "reserved_space_claimed",
            "free_space_claimed",
            "natural_runtime_reachability_claimed",
            "global_unreachable_claimed",
            "editing_safety_claimed",
            "editing_or_relocation_safety_claimed",
            "editable_claimed",
            "relocatable_claimed",
            "safe_allocatable_space_claimed",
            "allocatable_space_claimed",
            "adjacent_bytes_claimed",
            "neighbor_expansion_claimed",
            "terminator_semantics_claimed",
            "cross_table_dataflow_claimed",
            "additional_table_field_semantics_claimed",
            "all_consumers_claimed",
            "consumer_completeness_claimed",
        ):
            with self.subTest(flag=flag):
                self.assertFalse(claim[flag])

    def test_preserves_all_three_left_partitions_and_lz77_record_38(self):
        claim = self._helper()(ROOT, self._rom(), self._baseline())[0]
        self.assertEqual(
            self.LEFT_OWNER_PARTITIONS, claim["runtime_state_sequence_table_owner_partitions"]
        )
        self.assertEqual(
            [partition["id"] for partition in self.LEFT_OWNER_PARTITIONS],
            claim["runtime_state_sequence_table_owner_ids"],
        )
        self.assertEqual(self.LZ77_RECORD_RANGE, claim["lz77_record_38_range"])
        self.assertEqual(self.LZ77_RECORD_SHA256, claim["lz77_record_38_sha256"])
        self.assertEqual(38, claim["lz77_record_38_index"])
        self.assertEqual(0, claim["lz77_record_38_aligned_pointer_reference_count"])
        self.assertFalse(claim["lz77_record_38_runtime_reachability_claimed"])
        self.assertEqual("/records/38", claim["lz77_record_38_evidence_selector"])
        self.assertNotIn("previous_owner_id", claim)

    def test_binds_canonical_evidence_and_exact_verifier_reports(self):
        claim = self._helper()(ROOT, self._rom(), self._baseline())[0]
        self.assertEqual(self.LEFT_MANIFEST_PATH, claim["left_manifest_path"])
        self.assertEqual(self.LEFT_MANIFEST_SHA256, claim["left_manifest_sha256"])
        self.assertEqual(self.LEFT_VERIFIER_PATH, claim["left_verifier_path"])
        self.assertEqual(self.LEFT_VERIFIER_SHA256, claim["left_verifier_sha256"])
        self.assertEqual(self.LEFT_UPSTREAM_TEST_PATH, claim["left_upstream_test_path"])
        self.assertEqual(self.LEFT_UPSTREAM_TEST_SHA256, claim["left_upstream_test_sha256"])
        self.assertEqual(self.LZ77_INVENTORY_PATH, claim["lz77_inventory_path"])
        self.assertEqual(self.LZ77_INVENTORY_SHA256, claim["lz77_inventory_sha256"])
        self.assertEqual(self.LZ77_MANIFEST_PATH, claim["lz77_manifest_path"])
        self.assertEqual(self.LZ77_MANIFEST_SHA256, claim["lz77_manifest_sha256"])
        self.assertEqual(self.LZ77_VERIFIER_PATH, claim["lz77_verifier_path"])
        self.assertEqual(self.LZ77_VERIFIER_SHA256, claim["lz77_verifier_sha256"])
        self.assertEqual(self.LZ77_UPSTREAM_TEST_PATH, claim["lz77_upstream_test_path"])
        self.assertEqual(self.LZ77_UPSTREAM_TEST_SHA256, claim["lz77_upstream_test_sha256"])
        self.assertEqual(self.RIGHT_BANK_PATH, claim["right_bank_path"])
        self.assertEqual(self.RIGHT_BANK_SHA256, claim["right_bank_sha256"])
        self.assertEqual(self.RIGHT_VERIFIER_PATH, claim["right_verifier_path"])
        self.assertEqual(self.RIGHT_VERIFIER_SHA256, claim["right_verifier_sha256"])
        self.assertEqual(self.RIGHT_UPSTREAM_TEST_PATH, claim["right_upstream_test_path"])
        self.assertEqual(self.RIGHT_UPSTREAM_TEST_SHA256, claim["right_upstream_test_sha256"])
        self.assertEqual(self.RIGHT_HISTORICAL_BANK_PATH, claim["right_historical_bank_path"])
        self.assertEqual(self.RIGHT_HISTORICAL_BANK_SHA256, claim["right_historical_bank_sha256"])
        self.assertEqual(self.RIGHT_AUDIT_NOTE_PATH, claim["right_audit_note_path"])
        self.assertEqual(self.RIGHT_AUDIT_NOTE_SHA256, claim["right_audit_note_sha256"])
        self.assertEqual(self.LEFT_VERIFY_REPORT, claim["left_verifier_report"])
        self.assertEqual(self.RIGHT_VERIFY_REPORT, claim["right_verifier_report"])
        self.assertEqual(self.RIGHT_OWNER_ID, claim["next_owner_id"])
        self.assertEqual(self.RIGHT_TABLE_RANGE, claim["next_owner_range"])
        self.assertEqual("primary", claim["next_owner_role"])
        self.assertEqual("fixed_table", claim["next_owner_primary_class"])
        self.assertEqual("bank_record_bytes", claim["next_owner_claim_kind"])

    def test_rejects_candidate_overlap_duplicates_and_invalid_baseline(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        for role, message in (("primary", "current unknown"), ("secondary", "secondary")):
            injected = {
                "id": f"injected-{role}-overlap",
                "range": [0x53E696, 0x53E697],
                "role": role,
                "claim_kind": "injected_overlap",
            }
            if role == "primary":
                injected["primary_class"] = "injected_known"
            with self.assertRaisesRegex(ValueError, message):
                helper(ROOT, rom, [*baseline, injected])

        for injected in (
            {
                "id": "injected-duplicate-batch",
                "range": [0, 1],
                "role": "secondary",
                "claim_kind": "injected",
                "promotion_batch": self.BATCH,
            },
            {
                "id": "injected-duplicate-kind",
                "range": [0, 1],
                "role": "secondary",
                "claim_kind": self.CLAIM_KIND,
                "promotion_batch": "injected",
            },
            {
                "id": self.CLAIM_ID,
                "range": [0, 1],
                "role": "secondary",
                "claim_kind": "injected",
                "promotion_batch": "injected",
            },
        ):
            with self.assertRaisesRegex(ValueError, "already present"):
                helper(ROOT, rom, [*baseline, injected])

        duplicate_id = dict(baseline[0])
        with self.assertRaisesRegex(ValueError, "claim IDs are not unique"):
            helper(ROOT, rom, [*baseline, duplicate_id])
        invalid_role = dict(baseline[0])
        invalid_role["id"] = "invalid-role"
        invalid_role["role"] = "tertiary"
        with self.assertRaisesRegex(ValueError, "role changed"):
            helper(ROOT, rom, [invalid_role])
        invalid_range = dict(baseline[0])
        invalid_range["id"] = "invalid-range"
        invalid_range["range"] = [0x53E696, 0x53E696]
        with self.assertRaisesRegex(ValueError, "invalid range|outside"):
            helper(ROOT, rom, [invalid_range])

    def test_rejects_left_partition_lz77_and_right_owner_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._minimal_owner_baseline()
        owner_fields = (
            (self.LEFT_OWNER_PARTITIONS[0]["id"], "range", [0x53E597, 0x53E5A8]),
            (self.LEFT_OWNER_PARTITIONS[1]["id"], "primary_class", "drifted"),
            (self.LEFT_OWNER_PARTITIONS[2]["id"], "claim_kind", "drifted"),
            (self.LEFT_OWNER_PARTITIONS[0]["id"], "bytes_sha256", "0" * 64),
            (self.LEFT_OWNER_PARTITIONS[2]["id"], "evidence_path", "copy.json"),
            (self.LZ77_RECORD_RANGE and self.LEFT_OWNER_PARTITIONS[1]["id"], "evidence_selector", "/records/37"),
            (self.RIGHT_OWNER_ID, "range", [0x53E698, 0x53EE97]),
            (self.RIGHT_OWNER_ID, "claim_kind", "drifted"),
            (self.RIGHT_OWNER_ID, "evidence_sha256", "0" * 64),
            (self.RIGHT_OWNER_ID, "records", 255),
        )
        for owner_id, field, drifted in owner_fields:
            with self.subTest(owner_id=owner_id, field=field):
                changed = []
                for item in baseline:
                    clone = dict(item)
                    if clone.get("id") == owner_id:
                        clone[field] = drifted
                    changed.append(clone)
                with self.assertRaisesRegex(ValueError, "owner|partition|evidence|denominator|identity"):
                    helper(ROOT, rom, changed)

    def test_rejects_rom_candidate_table_alignment_and_constant_drift(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        tampered = bytearray(self._rom())
        tampered[0x53E696] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

        constant_cases = (
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_BATCH", "drifted"),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_CLAIM_ID", "drifted"),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_PRIMARY_CLASS", "drifted"),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_CLAIM_KIND", "drifted"),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_RANGE", (0x53E695, 0x53E698)),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_GBA_RANGE", (0x0853E695, 0x0853E698)),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_BYTES_SHA256", "0" * 64),
            ("RUNTIME_STATE_HANDLER_TABLE_ALIGNMENT_GAP_RANGE_DENOMINATOR_SHA256", "0" * 64),
            ("RUNTIME_STATE_SEQUENCE_TABLE_RANGE", (0x53E596, 0x53E695)),
            ("RUNTIME_STATE_SEQUENCE_TABLE_SHA256", "0" * 64),
            ("RUNTIME_STATE_HANDLER_TABLE_RANGE", (0x53E698, 0x53EE97)),
            ("RUNTIME_STATE_HANDLER_TABLE_SHA256", "0" * 64),
            ("RUNTIME_STATE_HANDLER_TABLE_FIRST_RECORD_SHA256", "0" * 64),
        )
        for constant, drifted in constant_cases:
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, drifted):
                    with self.assertRaisesRegex(ValueError, "contract|candidate|alignment|table|denominator|identity"):
                        helper(ROOT, self._rom(), baseline)

    def test_rejects_full_rom_drift_even_if_shared_rom_hash_constant_moves(self):
        tampered = bytearray(self._rom())
        tampered[0x100] ^= 1
        moved_hash = hashlib.sha256(tampered).hexdigest()
        with mock.patch.object(coverage_auditor, "ROM_SHA256", moved_hash):
            with self.assertRaisesRegex(ValueError, "ROM identity|ROM hash|contract"):
                self._helper()(
                    ROOT,
                    bytes(tampered),
                    self._minimal_owner_baseline(),
                )

    def test_rejects_partition_constant_and_baseline_synchronized_drift(self):
        drifted_partitions = copy.deepcopy(
            coverage_auditor.RUNTIME_STATE_HANDLER_GAP_LEFT_OWNER_PARTITIONS
        )
        drifted_partitions = list(drifted_partitions)
        first = dict(drifted_partitions[0])
        first["range"] = (0x53E597, 0x53E5A8)
        first["bytes_sha256"] = hashlib.sha256(
            self._rom()[0x53E597:0x53E5A8]
        ).hexdigest()
        drifted_partitions[0] = first
        drifted_partitions = tuple(drifted_partitions)

        synchronized_baseline = []
        for claim in self._minimal_owner_baseline():
            clone = copy.deepcopy(claim)
            if clone.get("id") == first["id"]:
                clone["range"] = list(first["range"])
                clone["bytes_sha256"] = first["bytes_sha256"]
            synchronized_baseline.append(clone)
        with mock.patch.object(
            coverage_auditor,
            "RUNTIME_STATE_HANDLER_GAP_LEFT_OWNER_PARTITIONS",
            drifted_partitions,
        ):
            with self.assertRaisesRegex(
                ValueError, "partition.*contract|owner.*denominator|identity"
            ):
                self._helper()(ROOT, self._rom(), synchronized_baseline)

    def test_rejects_manifest_verifier_and_verifier_report_drift(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        hash_constants = (
            "RUNTIME_STATE_HANDLER_GAP_LEFT_MANIFEST_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_LEFT_VERIFIER_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_LEFT_UPSTREAM_TEST_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_LZ77_INVENTORY_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_LZ77_MANIFEST_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_LZ77_VERIFIER_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_LZ77_UPSTREAM_TEST_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_BANK_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_VERIFIER_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_UPSTREAM_TEST_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_HISTORICAL_BANK_SHA256",
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_AUDIT_NOTE_SHA256",
        )
        for constant in hash_constants:
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaisesRegex(ValueError, "contract|identity|changed|evidence"):
                        helper(ROOT, self._rom(), baseline)

        failed_left = dict(self.LEFT_VERIFY_REPORT)
        failed_left["verified"] = False
        failed_left["errors"] = ["forced failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_battle_effect_sequence_bindings",
            return_value=failed_left,
        ):
            with self.assertRaisesRegex(ValueError, "left independent verification"):
                helper(ROOT, self._rom(), baseline)

        failed_right = dict(self.RIGHT_VERIFY_REPORT)
        failed_right["errors"] = ["forced failure"]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_disproved_bank_candidate",
            return_value=failed_right,
        ):
            with self.assertRaisesRegex(ValueError, "right independent verification"):
                helper(ROOT, self._rom(), baseline)

        drifted_right = dict(self.RIGHT_VERIFY_REPORT)
        drifted_right["details"] = dict(self.RIGHT_VERIFY_REPORT["details"])
        drifted_right["details"]["source_record_range"] = [7, 15]
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_disproved_bank_candidate",
            return_value=drifted_right,
        ):
            with self.assertRaisesRegex(ValueError, "right independent verification"):
                helper(ROOT, self._rom(), baseline)

    def test_rejects_all_noncanonical_evidence_paths(self):
        helper = self._helper()
        baseline = self._minimal_owner_baseline()
        path_specs = {
            "RUNTIME_STATE_HANDLER_GAP_LEFT_ARTIFACT": self.LEFT_MANIFEST_PATH.rsplit("/", 1)[0],
            "RUNTIME_STATE_HANDLER_GAP_LEFT_MANIFEST_PATH": self.LEFT_MANIFEST_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LEFT_VERIFIER": self.LEFT_VERIFIER_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LEFT_UPSTREAM_TEST": self.LEFT_UPSTREAM_TEST_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LZ77_ARTIFACT": self.LZ77_ARTIFACT_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LZ77_INVENTORY_PATH": self.LZ77_INVENTORY_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LZ77_MANIFEST_PATH": self.LZ77_MANIFEST_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LZ77_VERIFIER": self.LZ77_VERIFIER_PATH,
            "RUNTIME_STATE_HANDLER_GAP_LZ77_UPSTREAM_TEST": self.LZ77_UPSTREAM_TEST_PATH,
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_BANK_PATH": self.RIGHT_BANK_PATH,
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_VERIFIER": self.RIGHT_VERIFIER_PATH,
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_UPSTREAM_TEST": self.RIGHT_UPSTREAM_TEST_PATH,
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_HISTORICAL_BANK_PATH": self.RIGHT_HISTORICAL_BANK_PATH,
            "RUNTIME_STATE_HANDLER_GAP_RIGHT_AUDIT_NOTE_PATH": self.RIGHT_AUDIT_NOTE_PATH,
        }
        artifact_constants = {
            "RUNTIME_STATE_HANDLER_GAP_LEFT_ARTIFACT",
            "RUNTIME_STATE_HANDLER_GAP_LZ77_ARTIFACT",
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as temp_dir:
            temp_root = Path(temp_dir)
            for constant, source in path_specs.items():
                with self.subTest(path=f"symlink-{constant}"):
                    linked = temp_root / f"symlink-{constant}"
                    linked.symlink_to(
                        ROOT / source,
                        target_is_directory=constant in artifact_constants,
                    )
                    with mock.patch.object(coverage_auditor, constant, linked):
                        with self.assertRaisesRegex(ValueError, "canonical|symlink|contract|invalid"):
                            helper(ROOT, self._rom(), baseline)

            for constant, source in path_specs.items():
                with self.subTest(path=f"same-hash-{constant}"):
                    alias = temp_root / f"alias-{constant}"
                    if constant in artifact_constants:
                        shutil.copytree(ROOT / source, alias)
                    else:
                        shutil.copy2(ROOT / source, alias)
                    with mock.patch.object(coverage_auditor, constant, alias):
                        with self.assertRaisesRegex(ValueError, "canonical|contract|path"):
                            helper(ROOT, self._rom(), baseline)

        with tempfile.TemporaryDirectory() as outside_dir:
            outside_root = Path(outside_dir)
            for constant, source in path_specs.items():
                with self.subTest(path=f"outside-{constant}"):
                    outside = outside_root / f"outside-{constant}"
                    if constant in artifact_constants:
                        shutil.copytree(ROOT / source, outside)
                    else:
                        shutil.copy2(ROOT / source, outside)
                    with mock.patch.object(coverage_auditor, constant, outside):
                        with self.assertRaisesRegex(ValueError, "canonical|outside|contract|invalid"):
                            helper(ROOT, self._rom(), baseline)

    def test_does_not_call_atomize_claims_or_build_manifest(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("atomize_claims must not be called"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("build_manifest must not be called"),
        ):
            claims = self._helper()(ROOT, self._rom(), self._minimal_owner_baseline())
        self.assertEqual([self.CANDIDATE_RANGE], [claim["range"] for claim in claims])


class CutsceneObjPaletteDefinitionAlignmentGapCoverageTests(unittest.TestCase):
    """Frozen coverage contract for four palette/definition alignment gaps."""

    BATCH = "rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1"
    PRIMARY_CLASS = "cutscene_obj_palette_to_definition_4byte_alignment_gap"
    CLAIM_KIND = "cutscene_obj_palette_definition_alignment_gap_bytes"
    RANGES = [
        [0x12DEFA, 0x12DEFC],
        [0x12E442, 0x12E444],
        [0x12E95E, 0x12E960],
        [0x12ED6E, 0x12ED70],
    ]
    CLAIM_IDS = [
        "cutscene-obj-palette-definition-alignment-gap-12defa",
        "cutscene-obj-palette-definition-alignment-gap-12e442",
        "cutscene-obj-palette-definition-alignment-gap-12e95e",
        "cutscene-obj-palette-definition-alignment-gap-12ed6e",
    ]
    RANGE_VECTOR_SHA256 = (
        "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6"
    )
    CLAIM_DENOMINATOR_SHA256 = (
        "dae7c87fa52a1e1e9f1a72279fc7839d8f26f07b126e80aca07450286abcc137"
    )
    GAP_SHA256 = (
        "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
    )
    PACKED_SHA256 = (
        "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc"
    )
    REPORT_SHA256 = (
        "c89ed50357f1497139aa81bc29e4b67c5947608c640fc572f0ff66ed01dd8f41"
    )
    VERIFIER_PATH = (
        "tools/verify_rom_cutscene_obj_palette_definition_alignment_gaps.py"
    )
    VERIFIER_SHA256 = (
        "b78a8726b65e6079be8f2a2d332b082d87386987831a2e7d4354997969548823"
    )
    TEST_PATH = (
        "tests/test_verify_rom_cutscene_obj_palette_definition_alignment_gaps.py"
    )
    TEST_SHA256 = (
        "6941aec328ec5f261249b021442eae1c396068c35070744b610edd2df9708f9b"
    )
    SOURCE_MANIFEST_PATH = "artifacts/rom-cutscene-obj-source-ranges-v1/manifest.json"
    SOURCE_MANIFEST_SHA256 = (
        "a0e97ec43858a145a7c26dc71c5b89dfe8c4d9a5d6074ccad88c4ae56e03afd5"
    )
    SOURCE_PAYLOAD_PATH = (
        "artifacts/rom-cutscene-obj-source-ranges-v1/rom-cutscene-obj-source-ranges.json"
    )
    SOURCE_PAYLOAD_SHA256 = (
        "6d25034640799621d9adcfb8b8f2a553757f6d9fb2988216b426d0777559a2dc"
    )
    SOURCE_VERIFIER_PATH = "tools/verify_rom_cutscene_obj_source_ranges.py"
    SOURCE_VERIFIER_SHA256 = (
        "a1075b8885378fe2c26c1c262126ad8098bb81c171a805cb3e08ed0d8217c446"
    )
    LZ77_INVENTORY_PATH = (
        "artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"
    )
    LZ77_INVENTORY_SHA256 = (
        "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
    )
    LEFT_OWNER_IDS = [
        "lz77-12dee4",
        "lz77-12e42c",
        "lz77-12e948",
        "lz77-12ed58",
    ]
    LEFT_RANGES = [
        [0x12DEE4, 0x12DEFA],
        [0x12E42C, 0x12E442],
        [0x12E948, 0x12E95E],
        [0x12ED58, 0x12ED6E],
    ]
    RIGHT_OWNER_IDS = [
        "cutscene-obj-source-00-12defc",
        "cutscene-obj-source-06-12e444",
        "cutscene-obj-source-12-12e960",
        "cutscene-obj-source-18-12ed70",
    ]
    RIGHT_RANGES = [
        [0x12DEFC, 0x12DF14],
        [0x12E444, 0x12E45C],
        [0x12E960, 0x12E978],
        [0x12ED70, 0x12ED88],
    ]
    RIGHT_SELECTORS = ["/records/0", "/records/6", "/records/12", "/records/18"]
    RIGHT_RECORD_SHA256 = [
        "eb8f1ba7cc2d225bf3a2adefd015873a9bf311e4d1b1e080328f3c9187852ed1",
        "eb8f1ba7cc2d225bf3a2adefd015873a9bf311e4d1b1e080328f3c9187852ed1",
        "eb8f1ba7cc2d225bf3a2adefd015873a9bf311e4d1b1e080328f3c9187852ed1",
        "a3f6935912109790d1ddaa4b1496984c0eba79325a6b250057dfe5bb2eeb05ce",
    ]
    NON_CLAIMS = {
        "padding_claimed",
        "reserved_space_claimed",
        "free_space_claimed",
        "runtime_consumes_padding_claimed",
        "compiler_authorship_claimed",
        "generic_lz_alignment_rule_claimed",
        "all_cutscene_gaps_exhaustive_claimed",
        "natural_runtime_reachability_claimed",
        "global_unreachable_claimed",
        "editing_safety_claimed",
        "editing_or_relocation_safety_claimed",
        "editable_claimed",
        "relocatable_claimed",
        "safe_allocatable_space_claimed",
        "allocatable_space_claimed",
        "adjacent_bytes_claimed",
        "neighbor_expansion_claimed",
        "definition_unknown_field_semantics_claimed",
        "graphics_or_palette_expansion_claimed",
        "final_pixel_equivalence_claimed",
        "all_consumers_claimed",
        "consumer_completeness_claimed",
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        excluded_ids = set(cls.CLAIM_IDS)
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("id") not in excluded_ids
        ]

    @classmethod
    def _owner_baseline(cls) -> list[dict]:
        owner_ids = set(cls.LEFT_OWNER_IDS + cls.RIGHT_OWNER_IDS)
        return [claim for claim in cls._baseline() if claim.get("id") in owner_ids]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_cutscene_obj_palette_definition_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "Cutscene OBJ alignment-gap helper is absent")
        return helper

    def test_promotes_exact_four_ranges_boundaries_evidence_and_nonclaims(self):
        claims = self._helper()(ROOT, self._rom(), self._baseline())
        self.assertEqual(4, len(claims))
        self.assertEqual(self.CLAIM_IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(8, sum(end - start for start, end in self.RANGES))

        denominator = hashlib.sha256(
            json.dumps(
                [
                    {
                        key: claim[key]
                        for key in (
                            "id",
                            "range",
                            "resource_id",
                            "primary_class",
                            "claim_kind",
                            "bytes_sha256",
                            "previous_owner_id",
                            "next_owner_id",
                            "evidence_selector",
                        )
                    }
                    for claim in claims
                ],
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
        ).hexdigest()
        self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, denominator)

        for index, claim in enumerate(claims):
            start, end = self.RANGES[index]
            self.assertEqual([0x08000000 + start, 0x08000000 + end], claim["gba_range"])
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(index, claim["resource_id"])
            self.assertEqual(index, claim["record_index"])
            self.assertEqual(self.GAP_SHA256, claim["bytes_sha256"])
            self.assertEqual([index * 2, index * 2 + 2], claim["packed_range"])
            self.assertEqual(self.PACKED_SHA256, claim["packed_bytes_sha256"])
            self.assertEqual(self.RANGE_VECTOR_SHA256, claim["range_vector_sha256"])
            self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, claim["claim_denominator_sha256"])
            self.assertTrue(claim["all_zero"])
            self.assertEqual(2, claim["zero_byte_count"])
            self.assertEqual(4, claim["alignment_bytes"])
            self.assertEqual(end, claim["alignment_target"])
            self.assertEqual("(start + 3) & ~3", claim["alignment_formula_expression"])
            self.assertEqual(2, claim["alignment_gap_bytes"])
            self.assertTrue(claim["alignment_gap_is_exact"])
            self.assertEqual(self.LEFT_RANGES[index], claim["palette_lz_range"])
            self.assertEqual(22, claim["palette_lz_compressed_size"])
            self.assertEqual(32, claim["palette_lz_declared_output_size"])
            self.assertEqual(start, claim["palette_lz_parser_endpoint"])
            self.assertEqual(
                "declared_output_fixed_count",
                claim["palette_lz_endpoint_semantics"],
            )
            self.assertEqual(self.RIGHT_RANGES[index], claim["definition_first_record_range"])
            self.assertEqual(self.RIGHT_RECORD_SHA256[index], claim["definition_first_record_sha256"])
            self.assertEqual(20, claim["definition_component_stride"])
            self.assertEqual("ffff0000", claim["definition_terminator_hex"])
            self.assertEqual(24, claim["definition_record_size"])
            self.assertEqual(self.LEFT_OWNER_IDS[index], claim["previous_owner_id"])
            self.assertEqual(self.RIGHT_OWNER_IDS[index], claim["next_owner_id"])
            self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
            self.assertEqual(self.VERIFIER_SHA256, claim["independent_verifier_sha256"])
            self.assertEqual(self.TEST_PATH, claim["upstream_test_path"])
            self.assertEqual(self.TEST_SHA256, claim["upstream_test_sha256"])
            self.assertEqual(self.REPORT_SHA256, claim["independent_verifier_report_sha256"])
            self.assertEqual(f"/resources/{index}", claim["evidence_selector"])
            for flag in self.NON_CLAIMS:
                with self.subTest(resource=index, flag=flag):
                    self.assertFalse(claim[flag])

    def test_binds_exact_left_and_right_owner_partitions(self):
        claims = self._helper()(ROOT, self._rom(), self._baseline())
        for index, claim in enumerate(claims):
            self.assertEqual(self.LEFT_RANGES[index], claim["previous_owner_range"])
            self.assertEqual("primary", claim["previous_owner_role"])
            self.assertEqual("lz77_resource", claim["previous_owner_primary_class"])
            self.assertEqual(
                "aligned_pointer_reachable_lz77", claim["previous_owner_claim_kind"]
            )
            self.assertEqual(1, claim["previous_owner_aligned_pointer_reference_count"])
            self.assertEqual(self.LZ77_INVENTORY_PATH, claim["previous_owner_evidence_path"])
            self.assertEqual(self.LZ77_INVENTORY_SHA256, claim["previous_owner_evidence_sha256"])
            self.assertEqual(self.RIGHT_RANGES[index], claim["next_owner_range"])
            self.assertEqual("primary", claim["next_owner_role"])
            self.assertEqual(
                "cutscene_obj_definition_records",
                claim["next_owner_primary_class"],
            )
            self.assertEqual("cutscene_obj_source_range", claim["next_owner_claim_kind"])
            self.assertEqual(self.RIGHT_SELECTORS[index], claim["next_owner_evidence_selector"])
            self.assertEqual(self.SOURCE_PAYLOAD_PATH, claim["next_owner_evidence_path"])
            self.assertEqual(self.SOURCE_PAYLOAD_SHA256, claim["next_owner_evidence_sha256"])
            self.assertEqual(self.SOURCE_MANIFEST_PATH, claim["next_owner_promotion_manifest_path"])
            self.assertEqual(
                self.SOURCE_MANIFEST_SHA256,
                claim["next_owner_promotion_manifest_sha256"],
            )
            self.assertEqual(
                self.SOURCE_VERIFIER_PATH, claim["next_owner_independent_verifier_path"]
            )
            self.assertEqual(
                self.SOURCE_VERIFIER_SHA256,
                claim["next_owner_independent_verifier_sha256"],
            )

    def test_primary_secondary_duplicate_and_invalid_baseline_fail_closed(self):
        helper = self._helper()
        for role in ("primary", "secondary"):
            with self.subTest(role=role):
                baseline = self._owner_baseline()
                injected = {"id": f"injected-{role}", "range": [self.RANGES[0][0], self.RANGES[0][0] + 1], "role": role}
                if role == "primary":
                    injected["primary_class"] = "injected"
                baseline.append(injected)
                with self.assertRaisesRegex(ValueError, "unknown|overlap"):
                    helper(ROOT, self._rom(), baseline)

        for field, value in (
            ("promotion_batch", self.BATCH),
            ("claim_kind", self.CLAIM_KIND),
            ("id", self.CLAIM_IDS[0]),
        ):
            with self.subTest(duplicate=field):
                baseline = self._owner_baseline()
                baseline.append(
                    {"id": f"duplicate-{field}", "range": [0, 1], "role": "secondary", field: value}
                )
                with self.assertRaisesRegex(ValueError, "already present"):
                    helper(ROOT, self._rom(), baseline)

        for mutation in ("duplicate-id", "bad-role", "bad-range"):
            with self.subTest(mutation=mutation):
                baseline = self._owner_baseline()
                if mutation == "duplicate-id":
                    baseline.append(copy.deepcopy(baseline[0]))
                elif mutation == "bad-role":
                    baseline[0]["role"] = "observer"
                else:
                    baseline[0]["range"] = [2, 1]
                with self.assertRaisesRegex(
                    ValueError, "baseline|unique|role|range|outside|domain"
                ):
                    helper(ROOT, self._rom(), baseline)

    def test_owner_identity_and_unexpected_source_overlap_fail_closed(self):
        helper = self._helper()
        for owner_id in self.LEFT_OWNER_IDS + self.RIGHT_OWNER_IDS:
            with self.subTest(owner=owner_id):
                baseline = self._owner_baseline()
                owner = next(claim for claim in baseline if claim["id"] == owner_id)
                owner["bytes_sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "owner.*identity"):
                    helper(ROOT, self._rom(), baseline)

        baseline = self._owner_baseline()
        baseline.append(
            {
                "id": "injected-source-secondary",
                "range": [self.LEFT_RANGES[0][0], self.LEFT_RANGES[0][0] + 1],
                "role": "secondary",
            }
        )
        with self.assertRaisesRegex(ValueError, "source ownership|overlap"):
            helper(ROOT, self._rom(), baseline)

    def test_verifier_report_file_identities_and_canonical_paths_fail_closed(self):
        helper = self._helper()
        baseline = self._owner_baseline()
        failed = {
            "schema": "rom-cutscene-obj-palette-definition-alignment-gaps-verification-v1",
            "verified": False,
            "errors": ["forced failure"],
        }
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_cutscene_obj_palette_definition_alignment_gaps",
            return_value=failed,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, self._rom(), baseline)

        path_specs = {
            "CUTSCENE_OBJ_ALIGNMENT_GAP_VERIFIER": self.VERIFIER_PATH,
            "CUTSCENE_OBJ_ALIGNMENT_GAP_TEST": self.TEST_PATH,
            "CUTSCENE_OBJ_ALIGNMENT_GAP_SOURCE_MANIFEST": self.SOURCE_MANIFEST_PATH,
            "CUTSCENE_OBJ_ALIGNMENT_GAP_SOURCE_PAYLOAD": self.SOURCE_PAYLOAD_PATH,
            "CUTSCENE_OBJ_ALIGNMENT_GAP_SOURCE_VERIFIER": self.SOURCE_VERIFIER_PATH,
            "CUTSCENE_OBJ_ALIGNMENT_GAP_LZ77_INVENTORY": self.LZ77_INVENTORY_PATH,
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw:
            temp = Path(raw)
            for constant, source in path_specs.items():
                with self.subTest(path=constant):
                    alias = temp / constant
                    shutil.copy2(ROOT / source, alias)
                    with mock.patch.object(coverage_auditor, constant, alias):
                        with self.assertRaisesRegex(ValueError, "canonical|path"):
                            helper(ROOT, self._rom(), baseline)

    def test_constant_and_rom_drift_fail_closed(self):
        helper = self._helper()
        baseline = self._owner_baseline()
        for constant, value in (
            ("CUTSCENE_OBJ_ALIGNMENT_GAP_BATCH", "drifted"),
            ("CUTSCENE_OBJ_ALIGNMENT_GAP_PRIMARY_CLASS", "drifted"),
            ("CUTSCENE_OBJ_ALIGNMENT_GAP_CLAIM_KIND", "drifted"),
            ("CUTSCENE_OBJ_ALIGNMENT_GAP_RANGES", ((0x12DEFB, 0x12DEFC),)),
            ("CUTSCENE_OBJ_ALIGNMENT_GAP_RANGE_VECTOR_SHA256", "0" * 64),
            ("CUTSCENE_OBJ_ALIGNMENT_GAP_CLAIM_DENOMINATOR_SHA256", "0" * 64),
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, value):
                    with self.assertRaisesRegex(ValueError, "contract changed"):
                        helper(ROOT, self._rom(), baseline)

        tampered = bytearray(self._rom())
        tampered[self.RANGES[0][0]] = 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_build_manifest_integration_has_exact_delta_and_no_segment_split(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        source_call = "claims += _cutscene_obj_source_range_claims(root, rom, claims)"
        gap_call = (
            "claims += _cutscene_obj_palette_definition_alignment_gap_claims(\n"
            "        root, rom, claims\n"
            "    )"
        )
        self.assertIn(source_call, source)
        self.assertIn(gap_call, source)
        self.assertLess(source.index(source_call), source.index(gap_call))
        for key in (
            "cutscene_obj_alignment_gap_promotion_batch",
            "cutscene_obj_alignment_gap_claim_kind",
            "cutscene_obj_alignment_gap_bytes",
            "cutscene_obj_alignment_gap_claim_count",
            "cutscene_obj_alignment_gap_claim_denominator_sha256",
            "cutscene_obj_alignment_gap_range_vector_sha256",
            "cutscene_obj_alignment_gap_packed_bytes_sha256",
            "cutscene_obj_alignment_gap_independent_verifier_report_sha256",
        ):
            with self.subTest(summary=key):
                self.assertIn(f'"{key}"', source)

        claims = self._baseline()
        claims += self._helper()(ROOT, self._rom(), claims)
        claims.sort(key=lambda claim: (claim["range"], claim["id"]))
        segments = atomize_claims(len(self._rom()), claims)
        classified = sum(
            end - start
            for segment in segments
            if segment["primary_class"] != "unknown"
            for start, end in [segment["range"]]
        )
        unknown = sum(
            end - start
            for segment in segments
            if segment["primary_class"] == "unknown"
            for start, end in [segment["range"]]
        )
        self.assertGreaterEqual(classified, 6_106_920)
        self.assertLessEqual(unknown, 184_536)
        self.assertGreaterEqual(len(claims), 14_165)
        self.assertGreaterEqual(len(segments), 16_257)
        for start, _ in self.RANGES:
            segment = next(
                segment
                for segment in segments
                if segment["range"][0] <= start < segment["range"][1]
            )
            self.assertEqual(self.PRIMARY_CLASS, segment["primary_class"])
            self.assertEqual([], segment["secondary_claim_ids"])

    def test_does_not_call_atomize_claims_or_build_manifest(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("atomize_claims must not be called"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("build_manifest must not be called"),
        ):
            claims = self._helper()(ROOT, self._rom(), self._owner_baseline())
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])


class PositionsAuxDispatchCoverageTests(unittest.TestCase):
    """Coverage contract for the 144 fixed positions auxiliary cell tables."""

    ARTIFACT = ROOT / "artifacts/rom-positions-aux-dispatch-v1"
    BATCH = "rom-positions-aux-dispatch-v1"
    PRIMARY_CLASS = "positions_aux_dispatch_cell_table"
    CLAIM_KIND = "positions_aux_dispatch_cell_table_bytes"
    RANGE_DENOMINATOR_SHA256 = (
        "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68"
    )
    PACKED_BYTES_SHA256 = (
        "ce2ce373f1699899739903532424f59e89184afa8cd37a527f0adc4ecc8c2c57"
    )
    VECTOR_SHA256 = (
        "29bee47cef98715a027f5df0ce76c03c03d11dcbd7a84b225e50524e6215d8cb"
    )

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (cls.ARTIFACT / "rom-positions-aux-dispatch.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
        ]

    @staticmethod
    def _helper():
        return coverage_auditor._positions_aux_dispatch_claims

    def test_promotes_exact_fixed_current_unknown_denominator(self):
        rom = self._rom()
        payload = self._payload()
        baseline = self._baseline()
        claims = self._helper()(ROOT, rom, baseline)

        self.assertEqual(144, len(claims))
        self.assertEqual(
            [table["range"] for table in payload["tables"]],
            [claim["range"] for claim in claims],
        )
        self.assertEqual(
            9_216,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(self.RANGE_DENOMINATOR_SHA256, payload["range_list_sha256"])
        self.assertEqual(self.PACKED_BYTES_SHA256, payload["packed_range_bytes_sha256"])
        self.assertEqual(
            self.VECTOR_SHA256, payload["per_range_sha256_vector_sha256"]
        )

        for index, (table, claim) in enumerate(
            zip(payload["tables"], claims, strict=True)
        ):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(index, claim["ordinal"])
            self.assertEqual(table["group"], claim["group"])
            self.assertEqual(table["variant"], claim["variant"])
            self.assertEqual(f"/tables/{index}", claim["evidence_selector"])
            self.assertEqual(table["sha256"], claim["bytes_sha256"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(
                [
                    "byte0_dispatch_selector",
                    "byte1_raw_handler_operand",
                    "byte2_raw_handler_operand",
                    "byte3_raw_handler_operand",
                ],
                claim["read_footprint"],
            )
            for key in (
                "runtime_group_bound_claimed",
                "runtime_variant_bound_claimed",
                "all_cells_naturally_reached_claimed",
                "tag_business_semantics_claimed",
                "byte1_common_semantics_claimed",
                "byte2_common_semantics_claimed",
                "byte3_common_semantics_claimed",
                "byte3_padding_claimed",
                "free_space_claimed",
                "editing_safety_claimed",
                "allocatable_space_claimed",
            ):
                self.assertFalse(claim[key])

    def test_overlap_duplicate_verifier_and_rom_drift_fail_closed(self):
        payload = self._payload()
        baseline = self._baseline()
        start = payload["tables"][0]["range"][0]
        baseline.append(
            {
                "id": "injected-positions-aux-overlap",
                "range": [start, start + 1],
                "role": "primary",
                "primary_class": "injected_semantic",
            }
        )
        with self.assertRaisesRegex(ValueError, "fully current unknown"):
            self._helper()(ROOT, self._rom(), baseline)

        baseline = self._baseline()
        baseline.append(
            {
                "id": "injected-positions-aux-batch",
                "range": [0, 1],
                "role": "secondary",
                "promotion_batch": self.BATCH,
            }
        )
        with self.assertRaisesRegex(ValueError, "already present"):
            self._helper()(ROOT, self._rom(), baseline)

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_positions_aux_dispatch",
            return_value={"verified": False, "errors": ["injected failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                self._helper()(ROOT, self._rom(), self._baseline())

        tampered = bytearray(self._rom())
        tampered[start] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            self._helper()(ROOT, bytes(tampered), self._baseline())

    def test_artifact_identity_and_helper_independence_fail_closed(self):
        for constant in (
            "POSITIONS_AUX_DISPATCH_MANIFEST_SHA256",
            "POSITIONS_AUX_DISPATCH_PAYLOAD_SHA256",
            "POSITIONS_AUX_DISPATCH_VERIFIER_SHA256",
            "POSITIONS_AUX_DISPATCH_RANGE_DENOMINATOR_SHA256",
            "POSITIONS_AUX_DISPATCH_PACKED_BYTES_SHA256",
            "POSITIONS_AUX_DISPATCH_VECTOR_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaises(ValueError):
                        self._helper()(ROOT, self._rom(), self._baseline())

        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            claims = self._helper()(ROOT, self._rom(), self._baseline())
        self.assertEqual(144, len(claims))

    def test_build_manifest_integration_has_exact_delta_and_scope_boundary(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _positions_aux_dispatch_claims(root, rom, claims)", source
        )
        for key in (
            "positions_aux_dispatch_promotion_batch",
            "positions_aux_dispatch_claim_kind",
            "positions_aux_dispatch_bytes",
            "positions_aux_dispatch_claim_count",
            "positions_aux_dispatch_range_denominator_sha256",
        ):
            self.assertIn(f'"{key}"', source)

        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(9_216, summary["positions_aux_dispatch_bytes"])
        self.assertEqual(144, summary["positions_aux_dispatch_claim_count"])
        self.assertTrue(
            any(
                "positions auxiliary dispatch" in limitation.lower()
                and "9,216 bytes" in limitation
                and "natural" in limitation
                and "editing" in limitation
                for limitation in manifest["limitations"]
            )
        )


class BattleSoundSelectorCoverageTests(unittest.TestCase):
    """Coverage contract for the fixed 256-byte battle sound selector."""

    ARTIFACT = ROOT / "artifacts/rom-battle-sound-selector-v1"
    BATCH = "rom-battle-sound-selector-v1"
    PRIMARY_CLASS = "battle_gameplay_sound_selector_table"
    CLAIM_KIND = "battle_gameplay_sound_selector_table_bytes"
    TABLE_RANGE = [0x53E496, 0x53E596]
    TABLE_SHA256 = (
        "2f77582ae5eea1711b079fc8ce67d36e95ec68bf0e2bd0a3d5780eb3d9819b5d"
    )
    DENOMINATOR_SHA256 = (
        "fc3c1c03d918f173b304633d84fcbd8ead4448f5185d30d687c2ef352a3fcd62"
    )
    NON_CLAIMS = {
        "all_indices_naturally_reached_claimed",
        "all_direct_paths_naturally_reached_claimed",
        "all_selector_consumers_exhausted_claimed",
        "computed_or_ram_consumers_exhausted_claimed",
        "zero_value_business_semantics_claimed",
        "nonzero_value_business_semantics_claimed",
        "index_to_gameplay_semantics_claimed",
        "play_routine_full_behavior_claimed",
        "sound_playback_success_claimed",
        "left_neighbor_structure_claimed",
        "right_neighbor_business_relation_claimed",
        "all_battle_audio_exhausted_claimed",
        "editing_safety_claimed",
        "writeback_safety_claimed",
        "relocation_safety_claimed",
        "free_space_claimed",
        "allocatable_space_claimed",
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (cls.ARTIFACT / "battle-sound-selector.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
        ]

    @staticmethod
    def _helper():
        return coverage_auditor._battle_sound_selector_claims

    def test_promotes_exact_current_unknown_table_and_preserves_non_claims(self):
        rom = self._rom()
        payload = self._payload()
        claims = self._helper()(ROOT, rom, self._baseline())

        self.assertEqual(1, len(claims))
        claim = claims[0]
        self.assertEqual(self.TABLE_RANGE, claim["range"])
        self.assertEqual("primary", claim["role"])
        self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
        self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
        self.assertEqual(self.BATCH, claim["promotion_batch"])
        self.assertEqual("unknown", claim["promoted_from_primary_class"])
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertEqual(256, claim["entry_count"])
        self.assertEqual(1, claim["entry_size"])
        self.assertEqual(5, claim["direct_literal_consumer_count"])
        self.assertEqual(self.TABLE_SHA256, claim["bytes_sha256"])
        self.assertEqual(
            self.DENOMINATOR_SHA256, claim["entry_denominator_sha256"]
        )
        self.assertEqual("/selector", claim["evidence_selector"])
        self.assertEqual(self.NON_CLAIMS, set(claim["non_claims"]))
        self.assertTrue(all(value is False for value in claim["non_claims"].values()))
        self.assertEqual(payload["non_claims"], claim["non_claims"])
        start, end = claim["range"]
        self.assertEqual(self.TABLE_SHA256, hashlib.sha256(rom[start:end]).hexdigest())

    def test_identity_overlap_duplicate_verifier_and_rom_drift_fail_closed(self):
        baseline = self._baseline()
        overlap = {
            "id": "injected-battle-sound-selector-overlap",
            "range": [self.TABLE_RANGE[0], self.TABLE_RANGE[0] + 1],
            "role": "primary",
            "primary_class": "injected_semantic",
        }
        with self.assertRaisesRegex(ValueError, "fully current unknown"):
            self._helper()(ROOT, self._rom(), [*baseline, overlap])

        duplicate = {
            "id": "injected-battle-sound-selector-batch",
            "range": [0, 1],
            "role": "secondary",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            self._helper()(ROOT, self._rom(), [*baseline, duplicate])

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_battle_sound_selector",
            return_value={"verified": False, "errors": ["injected failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                self._helper()(ROOT, self._rom(), baseline)

        for constant in (
            "BATTLE_SOUND_SELECTOR_MANIFEST_SHA256",
            "BATTLE_SOUND_SELECTOR_PAYLOAD_SHA256",
            "BATTLE_SOUND_SELECTOR_BINARY_SHA256",
            "BATTLE_SOUND_SELECTOR_VERIFIER_SHA256",
            "BATTLE_SOUND_SELECTOR_DENOMINATOR_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaises(ValueError):
                        self._helper()(ROOT, self._rom(), baseline)

        tampered = bytearray(self._rom())
        tampered[self.TABLE_RANGE[0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            self._helper()(ROOT, bytes(tampered), baseline)

    def test_helper_is_non_recursive_and_build_manifest_integration_is_exact(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            self.assertEqual(
                1, len(self._helper()(ROOT, self._rom(), self._baseline()))
            )

        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _battle_sound_selector_claims(root, rom, claims)", source
        )
        for key in (
            "battle_sound_selector_promotion_batch",
            "battle_sound_selector_claim_kind",
            "battle_sound_selector_bytes",
            "battle_sound_selector_claim_count",
            "battle_sound_selector_table_sha256",
            "battle_sound_selector_entry_denominator_sha256",
        ):
            self.assertIn(f'"{key}"', source)

        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["battle_sound_selector_promotion_batch"])
        self.assertEqual(self.CLAIM_KIND, summary["battle_sound_selector_claim_kind"])
        self.assertEqual(256, summary["battle_sound_selector_bytes"])
        self.assertEqual(1, summary["battle_sound_selector_claim_count"])
        self.assertEqual(self.TABLE_SHA256, summary["battle_sound_selector_table_sha256"])
        self.assertEqual(
            self.DENOMINATOR_SHA256,
            summary["battle_sound_selector_entry_denominator_sha256"],
        )

        def class_at(offset: int) -> str:
            return next(
                segment["primary_class"]
                for segment in manifest["segments"]
                if segment["range"][0] <= offset < segment["range"][1]
            )

        # 0x53E495 已被相邻族 rom-fixed-index-u8-tail-v1 认领
        # （claim range 0x53E492..0x53E496，与本表 0x53E496 相邻且不重叠），
        # 不再是 unknown。本用例的意图是「本表左边界不含本族的 claim」。
        self.assertNotEqual(self.PRIMARY_CLASS, class_at(0x53E495))
        self.assertEqual(self.PRIMARY_CLASS, class_at(0x53E496))
        self.assertEqual(self.PRIMARY_CLASS, class_at(0x53E595))
        self.assertEqual(
            "battle_effect_runtime_state_sequence_table", class_at(0x53E596)
        )
        self.assertTrue(
            any(
                "battle sound selector" in limitation.lower()
                and "256" in limitation
                and "natural" in limitation
                and "editing" in limitation
                for limitation in manifest["limitations"]
            )
        )


class BattleConditionRecordsCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen battle-condition record projection."""

    ARTIFACT = ROOT / "artifacts/rom-battle-condition-records-v1"
    BATCH = "rom-battle-condition-records-v1"
    CLAIM_KIND = "battle_condition_record_current_unknown_fragment"
    PREFIX_CLASS = "battle_condition_variant_prefix_raw_bytes"
    PREDICATE_CLASS = "battle_condition_predicate_record_bytes"
    TABLE_RANGE = [0x594758, 0x596CCC]
    TABLE_SHA256 = (
        "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4"
    )
    PROJECTED_UNKNOWN_RANGES = [
        [0x594758, 0x59475C],
        [0x59503C, 0x595040],
        [0x595920, 0x595924],
        [0x596204, 0x596CCC],
    ]
    PROJECTED_RANGE_SHA256 = (
        "1b639baa06f56a6273327a2df2dc0ad2595535af6a08b47c9d8038378836544a"
    )
    PROJECTED_BYTES_SHA256 = (
        "f63949e16d48a198983a61099bcf6f18d3b01980dea2a94bd9440ed8d9f49810"
    )
    PREFIX_RANGE_SHA256 = (
        "11275ecaa34b3e4d187efcb04aa59ae8911bfb0ba9d6a147df313cae376b941d"
    )
    PREFIX_BYTES_SHA256 = (
        "eae9d28d7679ffbf2ab2dc851a67b2e3e1c4c6f0dceb8ab805cd0f7218ce8d8b"
    )
    PREDICATE_RANGE_SHA256 = (
        "f61a404bc830e0f78916268876bb62238d3a2d55267df5af3beda39af0861dcc"
    )
    PREDICATE_BYTES_SHA256 = (
        "e31d7da27eca37808d6a5937025991c2cf59785d7633c81c7695c1dc8800d64b"
    )
    COMBINED_RANGE_SHA256 = (
        "72fff4ac415bd154e643b2205064c53822209fb9eb0fe90a8243284e8f32f77f"
    )

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (cls.ARTIFACT / "battle-condition-records.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
        ]

    @staticmethod
    def _helper():
        return coverage_auditor._battle_condition_record_claims

    @staticmethod
    def _range_sha(ranges: list[list[int]]) -> str:
        raw = (json.dumps(ranges, separators=(",", ":")) + "\n").encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def test_promotes_exact_unknown_projection_and_preserves_existing_owners(self):
        rom = self._rom()
        payload = self._payload()
        baseline = self._baseline()
        claims = self._helper()(ROOT, rom, baseline)

        self.assertEqual(84, len(claims))
        self.assertEqual(84, len({claim["id"] for claim in claims}))
        prefix = sorted(
            (claim for claim in claims if claim["primary_class"] == self.PREFIX_CLASS),
            key=lambda claim: claim["range"],
        )
        predicate = sorted(
            (
                claim
                for claim in claims
                if claim["primary_class"] == self.PREDICATE_CLASS
            ),
            key=lambda claim: claim["range"],
        )
        self.assertEqual(41, len(prefix))
        self.assertEqual(43, len(predicate))
        self.assertEqual(164, sum(c["range"][1] - c["range"][0] for c in prefix))
        self.assertEqual(
            2_608, sum(c["range"][1] - c["range"][0] for c in predicate)
        )

        prefix_ranges = [claim["range"] for claim in prefix]
        predicate_ranges = [claim["range"] for claim in predicate]
        combined_ranges = sorted(prefix_ranges + predicate_ranges)
        self.assertEqual(self.PREFIX_RANGE_SHA256, self._range_sha(prefix_ranges))
        self.assertEqual(
            self.PREDICATE_RANGE_SHA256, self._range_sha(predicate_ranges)
        )
        self.assertEqual(self.COMBINED_RANGE_SHA256, self._range_sha(combined_ranges))
        self.assertIn([0x594758, 0x59475C], prefix_ranges)
        for expected in (
            [0x59503C, 0x595040],
            [0x595920, 0x595924],
            [0x596204, 0x59622C],
            [0x596C8C, 0x596CCC],
        ):
            self.assertIn(expected, predicate_ranges)
        self.assertEqual(
            self.PREFIX_BYTES_SHA256,
            hashlib.sha256(
                b"".join(rom[start:end] for start, end in prefix_ranges)
            ).hexdigest(),
        )
        self.assertEqual(
            self.PREDICATE_BYTES_SHA256,
            hashlib.sha256(
                b"".join(rom[start:end] for start, end in predicate_ranges)
            ).hexdigest(),
        )
        self.assertEqual(
            self.PROJECTED_BYTES_SHA256,
            hashlib.sha256(
                b"".join(rom[start:end] for start, end in combined_ranges)
            ).hexdigest(),
        )

        merged = []
        for start, end in combined_ranges:
            if merged and merged[-1][1] == start:
                merged[-1][1] = end
            else:
                merged.append([start, end])
        self.assertEqual(self.PROJECTED_UNKNOWN_RANGES, merged)
        self.assertEqual(self.PROJECTED_RANGE_SHA256, self._range_sha(merged))

        primary_baseline = [
            claim for claim in baseline if claim.get("role") == "primary"
        ]
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertTrue(claim["preserves_existing_primary_owners"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(payload["non_claims"], claim["non_claims"])
            self.assertTrue(
                all(value is False for value in claim["non_claims"].values())
            )
            self.assertFalse(
                any(
                    other["range"][0] < end and start < other["range"][1]
                    for other in primary_baseline
                )
            )

    def test_identity_projection_duplicate_verifier_and_rom_drift_fail_closed(self):
        rom = self._rom()
        baseline = self._baseline()
        injected = {
            "id": "injected-battle-condition-owner",
            "range": [0x594758, 0x594759],
            "role": "primary",
            "primary_class": "injected_semantic",
        }
        with self.assertRaisesRegex(ValueError, "unknown projection"):
            self._helper()(ROOT, rom, [*baseline, injected])

        removed_owner = next(
            claim
            for claim in baseline
            if claim.get("role") == "primary"
            and claim["range"][0] <= 0x59475C < claim["range"][1]
        )
        with self.assertRaisesRegex(ValueError, "unknown projection"):
            self._helper()(
                ROOT,
                rom,
                [claim for claim in baseline if claim is not removed_owner],
            )

        duplicate = {
            "id": "injected-battle-condition-batch",
            "range": [0, 1],
            "role": "secondary",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "already present"):
            self._helper()(ROOT, rom, [*baseline, duplicate])

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_battle_condition_records",
            return_value={"verified": False, "errors": ["injected failure"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                self._helper()(ROOT, rom, baseline)

        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_battle_condition_records",
            return_value={"verified": True, "errors": [], "schema": "wrong"},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                self._helper()(ROOT, rom, baseline)

        for constant in (
            "BATTLE_CONDITION_RECORDS_MANIFEST_SHA256",
            "BATTLE_CONDITION_RECORDS_PAYLOAD_SHA256",
            "BATTLE_CONDITION_RECORDS_BINARY_SHA256",
            "BATTLE_CONDITION_RECORDS_EXPORTER_SHA256",
            "BATTLE_CONDITION_RECORDS_VERIFIER_SHA256",
            "BATTLE_CONDITION_RECORDS_TEST_SHA256",
            "BATTLE_CONDITION_PROJECTED_RANGE_SHA256",
            "BATTLE_CONDITION_PROJECTED_BYTES_SHA256",
            "BATTLE_CONDITION_PREFIX_FRAGMENT_RANGE_SHA256",
            "BATTLE_CONDITION_PREFIX_FRAGMENT_BYTES_SHA256",
            "BATTLE_CONDITION_PREDICATE_FRAGMENT_RANGE_SHA256",
            "BATTLE_CONDITION_PREDICATE_FRAGMENT_BYTES_SHA256",
            "BATTLE_CONDITION_COMBINED_FRAGMENT_RANGE_SHA256",
        ):
            with self.subTest(constant=constant):
                with mock.patch.object(coverage_auditor, constant, "0" * 64):
                    with self.assertRaises(ValueError):
                        self._helper()(ROOT, rom, baseline)

        for offset in (self.TABLE_RANGE[0], 0x596CCC):
            tampered = bytearray(rom)
            tampered[offset] ^= 1
            with self.subTest(rom_mutation=offset):
                with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
                    self._helper()(ROOT, bytes(tampered), baseline)

    def test_helper_is_non_recursive_and_build_manifest_integration_is_exact(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            self.assertEqual(
                84, len(self._helper()(ROOT, self._rom(), self._baseline()))
            )

        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _battle_condition_record_claims(root, rom, claims)", source
        )
        for key in (
            "battle_condition_records_promotion_batch",
            "battle_condition_records_table_sha256",
            "battle_condition_projected_unknown_bytes",
            "battle_condition_projected_unknown_claim_count",
            "battle_condition_prefix_fragment_bytes",
            "battle_condition_prefix_fragment_claim_count",
            "battle_condition_predicate_fragment_bytes",
            "battle_condition_predicate_fragment_claim_count",
        ):
            self.assertIn(f'"{key}"', source)

        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["battle_condition_records_promotion_batch"])
        self.assertEqual(self.TABLE_SHA256, summary["battle_condition_records_table_sha256"])
        self.assertEqual(2_772, summary["battle_condition_projected_unknown_bytes"])
        self.assertEqual(84, summary["battle_condition_projected_unknown_claim_count"])
        self.assertEqual(164, summary["battle_condition_prefix_fragment_bytes"])
        self.assertEqual(41, summary["battle_condition_prefix_fragment_claim_count"])
        self.assertEqual(2_608, summary["battle_condition_predicate_fragment_bytes"])
        self.assertEqual(43, summary["battle_condition_predicate_fragment_claim_count"])

        def class_at(offset: int) -> str:
            return next(
                segment["primary_class"]
                for segment in manifest["segments"]
                if segment["range"][0] <= offset < segment["range"][1]
            )

        self.assertEqual(self.PREFIX_CLASS, class_at(0x594758))
        self.assertEqual("fixed_table", class_at(0x59475C))
        self.assertEqual("positions_aux_dispatch_cell_table", class_at(0x594FFC))
        self.assertEqual(self.PREDICATE_CLASS, class_at(0x59503C))
        self.assertEqual("fixed_table", class_at(0x595040))
        self.assertEqual("positions_aux_dispatch_cell_table", class_at(0x5961C4))
        self.assertEqual(self.PREDICATE_CLASS, class_at(0x596204))
        self.assertEqual(self.PREDICATE_CLASS, class_at(0x596CCB))
        self.assertEqual("unknown", class_at(0x596CCC))
        self.assertEqual("unknown", class_at(0x596D5B))
        self.assertTrue(
            any(
                "battle condition" in limitation.lower()
                and "2,772" in limitation
                and "144" in limitation
                and "editing" in limitation
                for limitation in manifest["limitations"]
            )
        )


class LookupAndBootThumbHandoffCoverageTests(unittest.TestCase):
    """Coverage contracts for the two frozen 2026-08-27 artifacts."""

    LOOKUP_ARTIFACT = ROOT / "artifacts/rom-u8-indexed-u16-pair-lookup-v1"
    LOOKUP_BATCH = "rom-u8-indexed-u16-pair-lookup-v1"
    LOOKUP_KIND = "u8_indexed_u16_pair_lookup_bytes"
    LOOKUP_CLASS = "u8_indexed_u16_pair_lookup"
    LOOKUP_RANGE = [0x59F560, 0x59F5F0]
    LOOKUP_SHA256 = (
        "36799e6ed48b1bb9dfb3b6ed607e114ef6477174ce57f57ad352b8cab0441f60"
    )
    LOOKUP_MANIFEST_SHA256 = (
        "926c2df1b1154181b28dcb65369471f87cdb35c986ce9d0c15a942a3e6fef81a"
    )

    BOOT_ARTIFACT = ROOT / "artifacts/rom-boot-thumb-handoff-cfg-v1"
    BOOT_BATCH = "rom-boot-thumb-handoff-cfg-v1"
    BOOT_CODE_KIND = "boot_thumb_handoff_reachable_instruction_bytes"
    BOOT_LITERAL_KIND = "boot_thumb_handoff_consumed_literal_bytes"
    BOOT_CODE_CLASS = "armv4t_boot_thumb_handoff_reachable_code"
    BOOT_LITERAL_CLASS = "armv4t_boot_thumb_handoff_consumed_literal_pool"
    BOOT_MANIFEST_SHA256 = (
        "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
    )
    BOOT_RANGE_VECTOR_SHA256 = (
        "f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5"
    )

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch")
            not in {cls.LOOKUP_BATCH, cls.BOOT_BATCH}
        ]

    @classmethod
    def _lookup_payload(cls) -> dict:
        return json.loads(
            (
                cls.LOOKUP_ARTIFACT
                / "rom-u8-indexed-u16-pair-lookup.json"
            ).read_text(encoding="utf-8")
        )

    @classmethod
    def _boot_payload(cls) -> dict:
        return json.loads(
            (cls.BOOT_ARTIFACT / "rom-boot-thumb-handoff-cfg.json").read_text(
                encoding="utf-8"
            )
        )

    def test_lookup_promotes_one_exact_unknown_slice_and_preserves_overlap(self):
        rom = self._rom()
        baseline = self._baseline()
        payload = self._lookup_payload()
        claims = coverage_auditor._u8_indexed_u16_pair_lookup_claims(
            ROOT, rom, baseline
        )

        self.assertEqual(1, len(claims))
        claim = claims[0]
        self.assertEqual(self.LOOKUP_RANGE, claim["range"])
        self.assertEqual("primary", claim["role"])
        self.assertEqual(self.LOOKUP_CLASS, claim["primary_class"])
        self.assertEqual(self.LOOKUP_KIND, claim["claim_kind"])
        self.assertEqual(self.LOOKUP_BATCH, claim["promotion_batch"])
        self.assertEqual("unknown", claim["promoted_from_primary_class"])
        self.assertTrue(claim["baseline_unknown_only"])
        self.assertTrue(claim["preserves_existing_primary_owners"])
        self.assertEqual(self.LOOKUP_SHA256, claim["bytes_sha256"])
        self.assertEqual([0, 36], claim["logical_cell_range"])
        self.assertEqual(36, claim["logical_cell_count"])
        self.assertEqual(256, claim["logical_view_cell_count"])
        self.assertEqual(1_024, claim["logical_view_bytes"])
        self.assertEqual(880, claim["existing_owner_overlap_bytes"])
        self.assertEqual(payload["non_claims"], claim["non_claims"])
        self.assertTrue(all(value is False for value in claim["non_claims"].values()))

        cells = payload["logical_view"]["cells"][:36]
        self.assertEqual(
            self.LOOKUP_RANGE,
            [cells[0]["range"][0], cells[-1]["range"][1]],
        )
        self.assertEqual(
            rom[self.LOOKUP_RANGE[0] : self.LOOKUP_RANGE[1]],
            b"".join(bytes.fromhex(cell["raw_hex"]) for cell in cells),
        )
        overlap = payload["coverage_projection"]["existing_owner_overlap"]
        self.assertEqual([0x59F5F0, 0x59F960], overlap["range"])
        self.assertFalse(overlap["reclassifies_existing_owner"])
        self.assertFalse(
            any(
                other.get("role") == "primary"
                and other["range"][0] < self.LOOKUP_RANGE[1]
                and self.LOOKUP_RANGE[0] < other["range"][1]
                for other in baseline
            )
        )

    def test_lookup_and_boot_fail_closed_on_baseline_or_identity_drift(self):
        rom = self._rom()
        baseline = self._baseline()
        lookup_helper = coverage_auditor._u8_indexed_u16_pair_lookup_claims
        boot_helper = coverage_auditor._boot_thumb_handoff_cfg_claims

        with self.assertRaisesRegex(ValueError, "unknown projection"):
            lookup_helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-lookup-owner",
                        "range": [self.LOOKUP_RANGE[0], self.LOOKUP_RANGE[0] + 1],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            lookup_helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-lookup-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.LOOKUP_BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_u8_indexed_u16_pair_lookup",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                lookup_helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "U8_LOOKUP_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                lookup_helper(ROOT, rom, baseline)

        lookup_claims = lookup_helper(ROOT, rom, baseline)
        boot_baseline = [*baseline, *lookup_claims]
        first_boot_range = self._boot_payload()["promotion_ranges"][0]["range"]
        with self.assertRaisesRegex(ValueError, "unknown projection"):
            boot_helper(
                ROOT,
                rom,
                [
                    *boot_baseline,
                    {
                        "id": "injected-boot-owner",
                        "range": [first_boot_range[0], first_boot_range[0] + 1],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_boot_thumb_handoff_cfg",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                boot_helper(ROOT, rom, boot_baseline)
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_boot_thumb_handoff_cfg",
            return_value=None,
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                boot_helper(ROOT, rom, boot_baseline)
        with mock.patch.object(
            coverage_auditor, "BOOT_THUMB_HANDOFF_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                boot_helper(ROOT, rom, boot_baseline)

        tampered = bytearray(rom)
        tampered[self.LOOKUP_RANGE[0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM"):
            lookup_helper(ROOT, bytes(tampered), baseline)
        tampered_boot = bytearray(rom)
        tampered_boot[first_boot_range[0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM"):
            boot_helper(ROOT, bytes(tampered_boot), boot_baseline)

    def test_boot_promotes_exact_separate_code_and_literal_denominators(self):
        rom = self._rom()
        baseline = self._baseline()
        lookup_claims = coverage_auditor._u8_indexed_u16_pair_lookup_claims(
            ROOT, rom, baseline
        )
        boot_baseline = [*baseline, *lookup_claims]
        payload = self._boot_payload()
        claims = coverage_auditor._boot_thumb_handoff_cfg_claims(
            ROOT, rom, boot_baseline
        )

        self.assertEqual(49, len(claims))
        self.assertEqual(49, len({claim["id"] for claim in claims}))
        code = [claim for claim in claims if claim["claim_kind"] == self.BOOT_CODE_KIND]
        literals = [
            claim
            for claim in claims
            if claim["claim_kind"] == self.BOOT_LITERAL_KIND
        ]
        self.assertEqual(27, len(code))
        self.assertEqual(22, len(literals))
        self.assertEqual(1_226, sum(c["range"][1] - c["range"][0] for c in code))
        self.assertEqual(296, sum(c["range"][1] - c["range"][0] for c in literals))
        self.assertEqual(
            [row["range"] for row in payload["promotion_ranges"]],
            [claim["range"] for claim in claims],
        )
        self.assertEqual(
            self.BOOT_RANGE_VECTOR_SHA256,
            hashlib.sha256(
                json.dumps(
                    payload["union_ranges"], sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
        )
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BOOT_BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"])
            self.assertEqual(
                self.BOOT_CODE_CLASS
                if claim["claim_kind"] == self.BOOT_CODE_KIND
                else self.BOOT_LITERAL_CLASS,
                claim["primary_class"],
            )
            self.assertFalse(
                any(
                    other.get("role") == "primary"
                    and other["range"][0] < end
                    and start < other["range"][1]
                    for other in boot_baseline
                )
            )

    def test_helpers_are_non_recursive_and_build_manifest_integration_is_exact(self):
        rom = self._rom()
        baseline = self._baseline()
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            lookup = coverage_auditor._u8_indexed_u16_pair_lookup_claims(
                ROOT, rom, baseline
            )
            boot = coverage_auditor._boot_thumb_handoff_cfg_claims(
                ROOT, rom, [*baseline, *lookup]
            )
        self.assertEqual(1, len(lookup))
        self.assertEqual(49, len(boot))

        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        lookup_call = "claims += _u8_indexed_u16_pair_lookup_claims(root, rom, claims)"
        boot_call = "claims += _boot_thumb_handoff_cfg_claims(root, rom, claims)"
        self.assertIn(lookup_call, source)
        self.assertIn(boot_call, source)
        self.assertLess(source.index(lookup_call), source.index(boot_call))
        for key in (
            "u8_indexed_u16_pair_lookup_bytes",
            "u8_indexed_u16_pair_lookup_claim_count",
            "u8_indexed_u16_pair_lookup_existing_owner_overlap_bytes",
            "boot_thumb_handoff_code_bytes",
            "boot_thumb_handoff_code_claim_count",
            "boot_thumb_handoff_literal_bytes",
            "boot_thumb_handoff_literal_claim_count",
            "boot_thumb_handoff_union_bytes",
        ):
            self.assertIn(f'"{key}"', source)

        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(144, summary["u8_indexed_u16_pair_lookup_bytes"])
        self.assertEqual(1, summary["u8_indexed_u16_pair_lookup_claim_count"])
        self.assertEqual(
            880,
            summary["u8_indexed_u16_pair_lookup_existing_owner_overlap_bytes"],
        )
        self.assertEqual(1_226, summary["boot_thumb_handoff_code_bytes"])
        self.assertEqual(27, summary["boot_thumb_handoff_code_claim_count"])
        self.assertEqual(296, summary["boot_thumb_handoff_literal_bytes"])
        self.assertEqual(22, summary["boot_thumb_handoff_literal_claim_count"])
        self.assertEqual(1_522, summary["boot_thumb_handoff_union_bytes"])


class TaskSchedulerCoreCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen task-scheduler CFG artifact."""

    ARTIFACT = ROOT / "artifacts/rom-task-scheduler-core-v1"
    BATCH = "rom-task-scheduler-core-v1"
    CODE_KIND = "task_scheduler_core_reachable_instruction_bytes"
    LITERAL_KIND = "task_scheduler_core_consumed_literal_bytes"
    CODE_CLASS = "armv4t_task_scheduler_thumb_code"
    LITERAL_CLASS = "thumb_pc_relative_consumed_literal"
    MANIFEST_SHA256 = (
        "88ef48526ed1bd096a8ece9a58aa4f5770f207084634a125f04dc99561c7d58c"
    )
    RANGE_VECTOR_SHA256 = (
        "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f"
    )
    GAP_RANGES = [[0x061D62, 0x061D64], [0x061D7A, 0x061D7C], [0x061DEA, 0x061DEC]]
    OWNER_RANGES = [[0x061D7C, 0x061DEA], [0x061E00, 0x061E1C]]
    OWNER_IDS = ["cfg-thumb-0000-061d7c", "cfg-thumb-0001-061e00"]

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in {cls.CODE_KIND, cls.LITERAL_KIND}
        ]

    @classmethod
    def _payload(cls) -> dict:
        return json.loads(
            (cls.ARTIFACT / "rom-task-scheduler-core.json").read_text(
                encoding="utf-8"
            )
        )

    def test_promotes_exact_code_and_literal_denominators(self):
        rom = self._rom()
        baseline = self._baseline()
        payload = self._payload()
        manifest_raw = (self.ARTIFACT / "manifest.json").read_bytes()
        self.assertEqual(self.MANIFEST_SHA256, hashlib.sha256(manifest_raw).hexdigest())
        self.assertEqual(
            self.MANIFEST_SHA256,
            coverage_auditor.TASK_SCHEDULER_MANIFEST_SHA256,
        )
        claims = coverage_auditor._task_scheduler_core_claims(ROOT, rom, baseline)

        self.assertEqual(7, len(claims))
        self.assertEqual(7, len({claim["id"] for claim in claims}))
        code = [claim for claim in claims if claim["claim_kind"] == self.CODE_KIND]
        literals = [
            claim for claim in claims if claim["claim_kind"] == self.LITERAL_KIND
        ]
        self.assertEqual(4, len(code))
        self.assertEqual(3, len(literals))
        self.assertEqual(264, sum(c["range"][1] - c["range"][0] for c in code))
        self.assertEqual(44, sum(c["range"][1] - c["range"][0] for c in literals))
        self.assertEqual(
            [row["range"] for row in payload["promotion_ranges"]],
            [claim["range"] for claim in claims],
        )
        self.assertEqual(
            self.RANGE_VECTOR_SHA256,
            hashlib.sha256(
                (
                    json.dumps(
                        payload["promotion"]["union_ranges"],
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
            ).hexdigest(),
        )
        packed = b"".join(
            rom[start:end]
            for start, end in (
                row["range"] for row in payload["promotion_ranges"]
            )
        )
        self.assertEqual(
            (self.ARTIFACT / "rom-task-scheduler-core.bin").read_bytes(), packed
        )
        for row, claim in zip(payload["promotion_ranges"], claims, strict=True):
            start, end = claim["range"]
            self.assertEqual(row["id"], claim["id"])
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(row["id"], claim["artifact_range_id"])
            self.assertEqual(row["sha256"], claim["bytes_sha256"])
            self.assertEqual(
                self.CODE_CLASS if row["kind"] == "code" else self.LITERAL_CLASS,
                claim["primary_class"],
            )
            self.assertEqual(hashlib.sha256(rom[start:end]).hexdigest(), row["sha256"])
            self.assertEqual(
                f'/promotion_ranges/{payload["promotion_ranges"].index(row)}',
                claim["evidence_selector"],
            )
            self.assertFalse(
                any(
                    other.get("role") == "primary"
                    and other["range"][0] < end
                    and start < other["range"][1]
                    for other in baseline
                )
            )

    def test_preserves_owned_provenance_and_three_unknown_gaps(self):
        rom = self._rom()
        baseline = self._baseline()
        claims = coverage_auditor._task_scheduler_core_claims(ROOT, rom, baseline)

        owners = [
            claim
            for claim in baseline
            if claim.get("id") in set(self.OWNER_IDS)
        ]
        self.assertEqual(self.OWNER_IDS, [claim["id"] for claim in owners])
        self.assertEqual(self.OWNER_RANGES, [claim["range"] for claim in owners])
        self.assertEqual(
            ["armv4t_cfg_reachable_thumb_code"] * 2,
            [claim["primary_class"] for claim in owners],
        )
        self.assertEqual(138, sum(end - start for start, end in self.OWNER_RANGES))
        for start, end in [*self.GAP_RANGES, *self.OWNER_RANGES]:
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )
        self.assertEqual(6, sum(end - start for start, end in self.GAP_RANGES))

    def test_fails_closed_on_baseline_verifier_artifact_or_rom_drift(self):
        rom = self._rom()
        baseline = self._baseline()
        helper = coverage_auditor._task_scheduler_core_claims
        first = self._payload()["promotion_ranges"][0]["range"]

        with self.assertRaisesRegex(ValueError, "unknown projection"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-scheduler-owner",
                        "range": [first[0], first[0] + 1],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-scheduler-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_task_scheduler_core_bundle",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "TASK_SCHEDULER_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)

        tampered = bytearray(rom)
        tampered[first[0]] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM"):
            helper(ROOT, bytes(tampered), baseline)

    def test_uses_immutable_bundle_after_gap_promotion(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_task_scheduler_core",
            side_effect=AssertionError(
                "coverage helper must not call the live-coupled legacy verifier"
            ),
        ):
            claims = coverage_auditor._task_scheduler_core_claims(
                ROOT, self._rom(), self._baseline()
            )
        self.assertEqual(7, len(claims))

    def test_helper_is_non_recursive_and_manifest_integration_is_exact(self):
        rom = self._rom()
        baseline = self._baseline()
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            claims = coverage_auditor._task_scheduler_core_claims(
                ROOT, rom, baseline
            )
        self.assertEqual(7, len(claims))

        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        boot_call = "claims += _boot_thumb_handoff_cfg_claims(root, rom, claims)"
        scheduler_call = "claims += _task_scheduler_core_claims(root, rom, claims)"
        self.assertIn(boot_call, source)
        self.assertIn(scheduler_call, source)
        self.assertLess(source.index(boot_call), source.index(scheduler_call))
        for key in (
            "task_scheduler_core_code_bytes",
            "task_scheduler_core_code_claim_count",
            "task_scheduler_core_literal_bytes",
            "task_scheduler_core_literal_claim_count",
            "task_scheduler_core_promoted_bytes",
            "task_scheduler_core_promotion_claim_count",
            "task_scheduler_core_gap_bytes",
            "task_scheduler_core_owned_provenance_bytes",
        ):
            self.assertIn(f'"{key}"', source)

        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertIn(
            coverage_auditor.TASK_SCHEDULER_COVERAGE_LIMITATION,
            manifest["limitations"],
        )
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(264, summary["task_scheduler_core_code_bytes"])
        self.assertEqual(4, summary["task_scheduler_core_code_claim_count"])
        self.assertEqual(44, summary["task_scheduler_core_literal_bytes"])
        self.assertEqual(3, summary["task_scheduler_core_literal_claim_count"])
        self.assertEqual(308, summary["task_scheduler_core_promoted_bytes"])
        self.assertEqual(7, summary["task_scheduler_core_promotion_claim_count"])
        self.assertEqual(6, summary["task_scheduler_core_gap_bytes"])
        self.assertEqual(3, summary["task_scheduler_core_gap_range_count"])
        self.assertEqual(138, summary["task_scheduler_core_owned_provenance_bytes"])
        self.assertEqual(2, summary["task_scheduler_core_owned_provenance_range_count"])
        self.assertEqual(3, summary["task_scheduler_core_union_range_count"])
        self.assertEqual(
            self.RANGE_VECTOR_SHA256,
            summary["task_scheduler_core_union_range_vector_sha256"],
        )
        self.assertEqual(1, summary["task_scheduler_core_frontier_count"])
        self.assertEqual(12, summary["task_scheduler_core_return_count"])
        self.assertGreaterEqual(summary["cfg_reachable_thumb_code_bytes"], 144_178)
        self.assertGreaterEqual(summary["cfg_promoted_unknown_bytes"], 144_210)
        self.assertGreaterEqual(summary["cfg_primary_claim_count"], 3_785)


class DirectSoundPitchLookupCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen 344-byte DirectSound pitch packet."""

    ARTIFACT = ROOT / "artifacts/rom-directsound-pitch-lookup-v1"
    BATCH = "rom-directsound-pitch-lookup-v1"
    RANGES = [
        [0x099D7C, 0x099D8C],
        [0x09A998, 0x09A9F4],
        [0x09A9F4, 0x09A9FC],
        [0x4645C4, 0x464678],
        [0x464678, 0x4646A8],
    ]
    IDS = [
        "directsound-pitch-high32-interwork-099d7c",
        "directsound-pitch-consumer-09a998",
        "directsound-pitch-literals-09a9f4",
        "directsound-pitch-scale-table-4645c4",
        "directsound-pitch-frequency-table-464678",
    ]
    CLASSES = [
        "armv4t_directsound_pitch_high32_interwork_code",
        "armv4t_directsound_pitch_consumer_thumb_code",
        "directsound_pitch_table_pointer_literals",
        "directsound_pitch_scale_descriptor_table",
        "directsound_pitch_frequency_u32_table",
    ]
    KINDS = [
        "directsound_pitch_high32_interwork_instruction_bytes",
        "directsound_pitch_consumer_instruction_bytes",
        "directsound_pitch_consumed_literal_bytes",
        "directsound_pitch_scale_descriptor_bytes",
        "directsound_pitch_frequency_u32_bytes",
    ]

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in set(cls.KINDS)
        ]

    def test_directsound_claims_are_exactly_five_ranges(self):
        rom = self._rom()
        baseline = self._baseline()
        claims = coverage_auditor._directsound_pitch_lookup_claims(
            ROOT, rom, baseline
        )
        self.assertEqual(5, len(claims))
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual([None, "thumb", None, None, None], [c["mode"] for c in claims])
        self.assertEqual(5, len({claim["id"] for claim in claims}))
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(
                "artifacts/rom-directsound-pitch-lookup-v1/rom-directsound-pitch-lookup.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "artifacts/rom-directsound-pitch-lookup-v1/manifest.json",
                claim["promotion_manifest_path"],
            )
            self.assertEqual(
                "tools/verify_rom_directsound_pitch_lookup.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(
                any(
                    other.get("role") == "primary"
                    and other["range"][0] < end
                    and start < other["range"][1]
                    for other in baseline
                )
            )

    def test_directsound_loader_fails_closed_on_drift_or_overlap(self):
        rom = self._rom()
        baseline = self._baseline()
        helper = coverage_auditor._directsound_pitch_lookup_claims
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-directsound-owner",
                        "range": [0x099D7C, 0x099D7D],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "excluded bytes"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-mp2k-excluded-owner",
                        "range": self.EXCLUDED[0],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-directsound-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_directsound_pitch_lookup_bundle",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "DIRECTSOUND_PITCH_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x099D7C] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM"):
            helper(ROOT, bytes(tampered), baseline)

    def test_directsound_helper_is_non_recursive(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            claims = coverage_auditor._directsound_pitch_lookup_claims(
                ROOT, self._rom(), self._baseline()
            )
        self.assertEqual(5, len(claims))

    def test_build_manifest_projects_directsound_totals_and_segments(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        scheduler_call = "claims += _task_scheduler_core_claims(root, rom, claims)"
        directsound_call = "claims += _directsound_pitch_lookup_claims(root, rom, claims)"
        self.assertIn(scheduler_call, source)
        self.assertIn(directsound_call, source)
        self.assertLess(source.index(scheduler_call), source.index(directsound_call))
        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["directsound_pitch_lookup_promotion_batch"])
        self.assertEqual(344, summary["directsound_pitch_lookup_bytes"])
        self.assertEqual(5, summary["directsound_pitch_lookup_claim_count"])
        self.assertEqual(
            "ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd",
            summary["directsound_pitch_lookup_range_vector_sha256"],
        )
        self.assertEqual(
            "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850",
            summary["directsound_pitch_lookup_packed_bytes_sha256"],
        )
        self.assertEqual(
            dict(zip(self.CLASSES, [16, 92, 8, 180, 48], strict=True)),
            summary["directsound_pitch_lookup_class_bytes"],
        )
        self.assertEqual(
            {primary_class: 1 for primary_class in self.CLASSES},
            summary["directsound_pitch_lookup_class_claim_counts"],
        )
        self.assertEqual(2, summary["directsound_pitch_lookup_producer_count"])
        self.assertEqual(44, summary["directsound_pitch_lookup_consumer_instruction_count"])
        self.assertEqual(5, summary["directsound_pitch_lookup_consumer_block_count"])
        self.assertEqual(0, summary["directsound_pitch_lookup_consumer_frontier_count"])
        self.assertEqual(5, summary["directsound_pitch_lookup_helper_instruction_count"])
        self.assertEqual(2, summary["directsound_pitch_lookup_helper_block_count"])
        self.assertEqual(0, summary["directsound_pitch_lookup_helper_frontier_count"])
        self.assertEqual(180, summary["directsound_pitch_lookup_scale_descriptor_count"])
        self.assertEqual(12, summary["directsound_pitch_lookup_frequency_entry_count"])

        segments = {tuple(segment["range"]): segment for segment in manifest["segments"]}
        # 本包自己认领的 5 段：主 claim 之间不可重叠，后继批次切不开它们，
        # 所以仍然可以用精确区间键断言。
        own = {
            (0x099D7C, 0x099D8C): self.CLASSES[0],
            (0x09A998, 0x09A9F4): self.CLASSES[1],
            (0x09A9F4, 0x09A9FC): self.CLASSES[2],
            (0x4645C4, 0x464678): self.CLASSES[3],
            (0x464678, 0x4646A8): self.CLASSES[4],
        }
        for interval, primary_class in own.items():
            self.assertEqual(primary_class, segments[interval]["primary_class"])
        # 三段「应当仍为 unknown」的邻接区不能用冻结区间键断言：
        # 后继批次 rom-psg-frequency-lookup-v1（生产链里排在本包之后）
        # 合法认领了 [0x46475C,0x464798)，把 (0x4646A8,0x46480C) 切成了三段，
        # 区间键随之消失。改为逐字节派生：窗口连续铺满、段表与主 claim 表
        # 逐字节投影一致、且本包不得认领窗口内任何字节。
        for start, end in (
            (0x09A996, 0x09A998),
            (0x09A9FC, 0x09AA00),
            (0x4646A8, 0x46480C),
        ):
            tiles, owner = _ledger_window_tiles(manifest, start, end)
            self.assertEqual(start, tiles[0][0])
            self.assertEqual(end, tiles[-1][1])
            for begin, stop, primary_class in tiles:
                for offset in range(begin, stop):
                    owner_class, owner_batch = owner[offset]
                    self.assertEqual(owner_class, primary_class)
                    self.assertNotEqual(self.BATCH, owner_batch)
        self.assertIn(
            coverage_auditor.DIRECTSOUND_PITCH_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class PsgFrequencyLookupCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen 226-byte PSG/noise lookup packet."""

    ARTIFACT = ROOT / "artifacts/rom-psg-frequency-lookup-v1"
    BATCH = "rom-psg-frequency-lookup-v1"
    RANGES = [
        [0x09B494, 0x09B4C6],
        [0x09B4C8, 0x09B4CC],
        [0x09B4CC, 0x09B534],
        [0x09B534, 0x09B53C],
        [0x46475C, 0x464798],
    ]
    IDS = [
        "psg-frequency-code-a-09b494",
        "psg-frequency-noise-literal-09b4c8",
        "psg-frequency-code-b-09b4cc",
        "psg-frequency-nonnoise-literals-09b534",
        "psg-noise-register-table-46475c",
    ]
    CLASSES = [
        "armv4t_psg_frequency_lookup_thumb_code",
        "psg_frequency_lookup_consumed_pointer_literals",
        "armv4t_psg_frequency_lookup_thumb_code",
        "psg_frequency_lookup_consumed_pointer_literals",
        "psg_noise_register_descriptor_table",
    ]
    KINDS = [
        "psg_frequency_lookup_instruction_bytes",
        "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "psg_frequency_lookup_instruction_bytes",
        "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "psg_noise_register_descriptor_bytes",
    ]

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in set(cls.KINDS)
        ]

    def test_psg_frequency_claims_are_exactly_five_ranges(self):
        rom = self._rom()
        baseline = self._baseline()
        claims = coverage_auditor._psg_frequency_lookup_claims(
            ROOT, rom, baseline
        )
        self.assertEqual(5, len(claims))
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(
            ["thumb", None, "thumb", None, None],
            [claim["mode"] for claim in claims],
        )
        self.assertEqual(5, len({claim["id"] for claim in claims}))
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(
                "artifacts/rom-psg-frequency-lookup-v1/rom-psg-frequency-lookup.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "artifacts/rom-psg-frequency-lookup-v1/manifest.json",
                claim["promotion_manifest_path"],
            )
            self.assertEqual(
                "tools/verify_rom_psg_frequency_lookup.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(
                any(
                    other.get("role") == "primary"
                    and other["range"][0] < end
                    and start < other["range"][1]
                    for other in baseline
                )
            )

    def test_psg_frequency_loader_fails_closed_on_drift_or_overlap(self):
        rom = self._rom()
        baseline = self._baseline()
        helper = coverage_auditor._psg_frequency_lookup_claims
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-psg-owner",
                        "range": [0x09B494, 0x09B495],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-psg-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_psg_frequency_lookup_bundle",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "PSG_FREQUENCY_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x09B494] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM"):
            helper(ROOT, bytes(tampered), baseline)

    def test_psg_frequency_helper_is_non_recursive(self):
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize the full ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            claims = coverage_auditor._psg_frequency_lookup_claims(
                ROOT, self._rom(), self._baseline()
            )
        self.assertEqual(5, len(claims))

    def test_build_manifest_projects_psg_totals_and_segments(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        directsound_call = "claims += _directsound_pitch_lookup_claims(root, rom, claims)"
        psg_call = "claims += _psg_frequency_lookup_claims(root, rom, claims)"
        self.assertIn(directsound_call, source)
        self.assertIn(psg_call, source)
        self.assertLess(source.index(directsound_call), source.index(psg_call))
        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["psg_frequency_lookup_promotion_batch"])
        self.assertEqual(226, summary["psg_frequency_lookup_bytes"])
        self.assertEqual(5, summary["psg_frequency_lookup_claim_count"])
        self.assertEqual(
            "5247ee79350c15d6292e52a5e1ef58bd7b7555f50a70bc157e3e936b8ffa0080",
            summary["psg_frequency_lookup_range_vector_sha256"],
        )
        self.assertEqual(
            "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b",
            summary["psg_frequency_lookup_packed_bytes_sha256"],
        )
        self.assertEqual(
            "6683ef2206af27246bc97abb750a02023ea18909611b7dbda9e1987419e515eb",
            summary["psg_frequency_lookup_semantic_range_vector_sha256"],
        )
        self.assertEqual(
            {
                "armv4t_psg_frequency_lookup_thumb_code": 154,
                "psg_frequency_lookup_consumed_pointer_literals": 12,
                "psg_noise_register_descriptor_table": 60,
            },
            summary["psg_frequency_lookup_class_bytes"],
        )
        self.assertEqual(
            {
                "armv4t_psg_frequency_lookup_thumb_code": 2,
                "psg_frequency_lookup_consumed_pointer_literals": 2,
                "psg_noise_register_descriptor_table": 1,
            },
            summary["psg_frequency_lookup_class_claim_counts"],
        )
        self.assertEqual(0, summary["psg_frequency_lookup_direct_branch_producer_count"])
        self.assertEqual(1, summary["psg_frequency_lookup_thumb_pointer_occurrence_count"])
        self.assertEqual(77, summary["psg_frequency_lookup_consumer_instruction_count"])
        self.assertEqual(12, summary["psg_frequency_lookup_consumer_block_count"])
        self.assertEqual(0, summary["psg_frequency_lookup_consumer_frontier_count"])
        self.assertEqual(60, summary["psg_frequency_lookup_noise_table_entry_count"])
        self.assertEqual([0, 59], summary["psg_frequency_lookup_noise_index_domain"])
        self.assertEqual(2, summary["psg_frequency_lookup_unclassified_gap_bytes"])

        segments = {tuple(segment["range"]): segment for segment in manifest["segments"]}
        expected = {
            (0x09B494, 0x09B4C6): self.CLASSES[0],
            (0x09B4C6, 0x09B4C8): "artifact_bound_4byte_alignment_bytes",
            (0x09B4C8, 0x09B4CC): self.CLASSES[1],
            (0x09B4CC, 0x09B534): self.CLASSES[2],
            (0x09B534, 0x09B53C): self.CLASSES[3],
            (0x4646A8, 0x46475C): "unknown",
            (0x46475C, 0x464798): self.CLASSES[4],
            (0x464798, 0x46480C): "unknown",
        }
        for interval, primary_class in expected.items():
            self.assertEqual(primary_class, segments[interval]["primary_class"])
        self.assertIn(
            coverage_auditor.PSG_FREQUENCY_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class U8IndexedU8TripletLookupCoverageTests(unittest.TestCase):
    """Coverage contract for the exact 19-byte triplet lookup promotion."""

    ARTIFACT = ROOT / "artifacts/rom-u8-indexed-u8-triplet-lookup-v1"
    BATCH = "rom-u8-indexed-u8-triplet-lookup-v1"
    RANGES = [[0x075C0C, 0x075C10], [0x53DFB0, 0x53DFBF]]
    IDS = [
        "fixed-consumer-triplet-pointer-literal",
        "fixed-consumer-triplet-records",
    ]
    CLASSES = [
        "fixed_consumer_triplet_pointer_literal",
        "fixed_consumer_triplet_table",
    ]
    KINDS = [
        "fixed_consumer_triplet_pointer_literal_bytes",
        "fixed_consumer_triplet_record_bytes",
    ]

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in set(cls.KINDS)
        ]

    def test_triplet_claims_are_exactly_two_current_unknown_ranges(self):
        rom = self._rom()
        baseline = self._baseline()
        claims = coverage_auditor._u8_indexed_u8_triplet_lookup_claims(
            ROOT,
            rom,
            baseline,
        )
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(2, len({claim["id"] for claim in claims}))
        for claim in claims:
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(),
                claim["bytes_sha256"],
            )
            self.assertEqual(
                "artifacts/rom-u8-indexed-u8-triplet-lookup-v1/rom-u8-indexed-u8-triplet-lookup.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "tools/verify_rom_u8_indexed_u8_triplet_lookup.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(
                any(
                    other.get("role") == "primary"
                    and other["range"][0] < end
                    and start < other["range"][1]
                    for other in baseline
                )
            )

    def test_triplet_loader_fails_closed_on_drift_or_overlap(self):
        rom = self._rom()
        baseline = self._baseline()
        helper = coverage_auditor._u8_indexed_u8_triplet_lookup_claims
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-triplet-owner",
                        "range": [0x075C0C, 0x075C0D],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-triplet-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_u8_indexed_u8_triplet_lookup_bundle",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor,
            "U8_TRIPLET_MANIFEST_SHA256",
            "0" * 64,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)

    def test_triplet_loader_uses_immutable_bundle_after_gap_promotion(self):
        rom = self._rom()
        baseline = self._baseline()
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_u8_indexed_u8_triplet_lookup",
            side_effect=AssertionError("legacy live verifier must not run"),
        ):
            claims = coverage_auditor._u8_indexed_u8_triplet_lookup_claims(
                ROOT,
                rom,
                baseline,
            )
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])

    def test_build_manifest_projects_triplet_totals_and_exact_segments(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        psg_call = "claims += _psg_frequency_lookup_claims(root, rom, claims)"
        triplet_call = (
            "claims += _u8_indexed_u8_triplet_lookup_claims(root, rom, claims)"
        )
        self.assertIn(psg_call, source)
        self.assertIn(triplet_call, source)
        self.assertLess(source.index(psg_call), source.index(triplet_call))
        manifest = build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["u8_indexed_u8_triplet_lookup_promotion_batch"])
        self.assertEqual(19, summary["u8_indexed_u8_triplet_lookup_bytes"])
        self.assertEqual(2, summary["u8_indexed_u8_triplet_lookup_claim_count"])
        self.assertEqual(
            {
                "fixed_consumer_triplet_pointer_literal": 4,
                "fixed_consumer_triplet_table": 15,
            },
            summary["u8_indexed_u8_triplet_lookup_class_bytes"],
        )
        self.assertEqual(
            {
                "fixed_consumer_triplet_pointer_literal": 1,
                "fixed_consumer_triplet_table": 1,
            },
            summary["u8_indexed_u8_triplet_lookup_class_claim_counts"],
        )
        segments = {tuple(segment["range"]): segment for segment in manifest["segments"]}
        self.assertEqual(
            "fixed_consumer_triplet_pointer_literal",
            segments[(0x075C0C, 0x075C10)]["primary_class"],
        )
        self.assertEqual(
            "fixed_consumer_triplet_table",
            segments[(0x53DFB0, 0x53DFBF)]["primary_class"],
        )
        self.assertIn(
            coverage_auditor.U8_TRIPLET_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class CgbBoundedCfgCoverageTests(unittest.TestCase):
    """Coverage contracts for the two accepted bounded CGB audio CFGs."""

    GAP_BATCH = "rom-artifact-bound-alignment-gaps-v1"
    PACKETS = (
        {
            "label": "helper",
            "helper": "_cgb_helper_bounded_cfg_claims",
            "batch": "rom-cgb-helper-bounded-cfg-v1",
            "prefix": "cgb-helper",
            "manifest_sha256": (
                "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1"
            ),
            "payload_sha256": (
                "dccdca087744e57136b180dba1c3e4151c123efecec10d5d53f90894dc760960"
            ),
            "binary_sha256": (
                "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
            ),
            "range_vector_sha256": (
                "ea942377babe2613c9affe8711b6480f6e9e27e60da7aeb483112790de3b85b3"
            ),
            "code_bytes": 164,
            "literal_bytes": 16,
            "excluded": [[0x09B572, 0x09B574], [0x09B586, 0x09B588]],
            "rows": [
                ([0x09B53C, 0x09B560], "cgb_helper_bounded_thumb_code", "ac01b052dd7ab7f97e74b52e671f1e8bdc2c423caeebeee4c5618c905f29bca1"),
                ([0x09B560, 0x09B564], "cgb_helper_consumed_literal_bytes", "22f7252bc2b8f2444cb6c59642ab9d902a8cac23e4c27e48623e8513b28ddeee"),
                ([0x09B564, 0x09B568], "cgb_helper_bounded_thumb_code", "df358c07b036a56dcc30711ce42e97371d6e3f08f6a1e8027e0beb713f85c56d"),
                ([0x09B568, 0x09B56C], "cgb_helper_consumed_literal_bytes", "60e226a6318302bbe245079f99e6724c5cd2431c689d5ae9992b08bdcc592a04"),
                ([0x09B56C, 0x09B572], "cgb_helper_bounded_thumb_code", "30c6c9fcb611330459336092dfdf9059b742dabc6d5f773ae67f501c1caadc3f"),
                ([0x09B574, 0x09B578], "cgb_helper_consumed_literal_bytes", "d0455d972504810561aaa6b9cc70d69a9ad49abc84a3df38789afdd8eb9236eb"),
                ([0x09B578, 0x09B586], "cgb_helper_bounded_thumb_code", "6531a1df4bcdc95692713b4c346c135e75339afb73d35dd2934ff15e9f606d99"),
                ([0x09B588, 0x09B58C], "cgb_helper_consumed_literal_bytes", "bd56e77404afec2e1cb1d293f4b56e5188b6e7c5d7aaf39d58dbd1de177f28fd"),
                ([0x09B58C, 0x09B5F4], "cgb_helper_bounded_thumb_code", "584762a3caa5fe9d71f2afd7fe58f2e5a8d2ef8efb2c4d68df84a621b84c9b88"),
            ],
        },
        {
            "label": "cgbsound",
            "helper": "_cgbsound_bounded_cfg_claims",
            "batch": "rom-cgbsound-bounded-cfg-v1",
            "prefix": "cgbsound",
            "manifest_sha256": (
                "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e"
            ),
            "payload_sha256": (
                "362a3dc1b5819a57310482b7fbdd94bb2f79e9d439ea44713798140d1d79b18d"
            ),
            "binary_sha256": (
                "edebdbe6e5cf5f9cf04fdb93839846f7e37e6516914b77a7517413c88ee9a151"
            ),
            "range_vector_sha256": (
                "3386a673407d2191f9b9427725f95e3864b92009ea32de433d28c9665c618f57"
            ),
            "code_bytes": 1008,
            "literal_bytes": 76,
            "excluded": [
                [0x09B676, 0x09B678],
                [0x09B696, 0x09B698],
                [0x09B702, 0x09B704],
                [0x09B762, 0x09B764],
                [0x09B94A, 0x09B94C],
                [0x09B96E, 0x09B970],
                [0x09B9E2, 0x09B9E4],
            ],
            "rows": [
                ([0x09B5F4, 0x09B614], "cgbsound_bounded_thumb_code", "fd17960f5cf76e3c505f82a1e14e467b486b3b24564c9f7f79e6c6fe4845c1f3"),
                ([0x09B614, 0x09B618], "cgbsound_consumed_literal_bytes", "e47b04ebe71cb95aa7efebf2666040c297bdd758e5325d66acf08fd4cb9dc233"),
                ([0x09B618, 0x09B660], "cgbsound_bounded_thumb_code", "68c567148290640ca72fd9899e82e6ad53a6392bbff6943e28f5f5c7442520bd"),
                ([0x09B660, 0x09B66C], "cgbsound_consumed_literal_bytes", "9d59ea5cddbd1a0d6f4ecc839f5369d57d4b9420ff653253e34871df46464d68"),
                ([0x09B66C, 0x09B676], "cgbsound_bounded_thumb_code", "82c41b731bb51eda5c4f1e518bcbe5bd24383285b310eb3529dbd332baa97721"),
                ([0x09B678, 0x09B684], "cgbsound_consumed_literal_bytes", "164b6ec13f1c38fcd5d802c242991b31133912d7c9b7646a67b055dd9c37288f"),
                ([0x09B684, 0x09B696], "cgbsound_bounded_thumb_code", "310b0efa036d4193e5031df362d88f684111106908b74a13bc8d8d6051de3f55"),
                ([0x09B698, 0x09B6A4], "cgbsound_consumed_literal_bytes", "a0c75541973e91098dbe01f8d2a1a3c4e1e26a66d40f37239ef12477848d71f5"),
                ([0x09B6A4, 0x09B702], "cgbsound_bounded_thumb_code", "322c40d1faf3a126ba4d2cb7647fbb8d0d7fe271576b32b6d7eea2815dca20b5"),
                ([0x09B704, 0x09B710], "cgbsound_consumed_literal_bytes", "5ad3ec1a7bdfa9663a8d12dd5b15cd1013a51d0eb50fd7032783061eed5003ca"),
                ([0x09B710, 0x09B762], "cgbsound_bounded_thumb_code", "1dd6c73c8e2889f9ec54a4298431541e92669bc1042021901f6548b03d7c6606"),
                ([0x09B764, 0x09B768], "cgbsound_consumed_literal_bytes", "bfa1417d1dfb9abae35a079e4362dd0a8a3183f7d858197e967d25136e9b9717"),
                ([0x09B768, 0x09B94A], "cgbsound_bounded_thumb_code", "be11fa9cbce478459eaa53790d54b50be8af6b1f8ea979200e5d359a822a1dfb"),
                ([0x09B94C, 0x09B954], "cgbsound_consumed_literal_bytes", "4950d6ff3af2748c3139c4696c3e67ec47406f10330e83fce3f32a5f27a5f34a"),
                ([0x09B954, 0x09B96E], "cgbsound_bounded_thumb_code", "3103fe9dbc2aef74901cc58e862444d4d05c8a894eea55b459af150e0c107e3c"),
                ([0x09B970, 0x09B974], "cgbsound_consumed_literal_bytes", "718d44854b4098ea99f25e6518f1dc48ee6f60a046ad5163ce18bb59f49b67dd"),
                ([0x09B974, 0x09B9E2], "cgbsound_bounded_thumb_code", "3dc08cf18753e9d393ec6063adf2391007679a59d5c76b1b8e4a292323c3de3d"),
                ([0x09B9E4, 0x09B9EC], "cgbsound_consumed_literal_bytes", "1e2dbdfa88824243df8f52b267a7196eea98a7ca890c3877d74891272b0cbf1a"),
                ([0x09B9EC, 0x09BA3E], "cgbsound_bounded_thumb_code", "8629ba7d1a6f3952c309b67bc0c7456ba674745e25deab2128d15adebe3c1f6c"),
            ],
        },
    )

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        removed_batches = {cls.GAP_BATCH, *(packet["batch"] for packet in cls.PACKETS)}
        return [
            claim
            for claim in manifest["claims"]
            if claim.get("promotion_batch") not in removed_batches
        ]

    @staticmethod
    def _expected_id(packet: dict, interval: list[int], kind: str) -> str:
        row_kind = "code" if kind.endswith("thumb_code") else "literal"
        return f"{packet['prefix']}-{row_kind}-{interval[0]:06x}"

    def test_promotes_exact_rows_and_recomputes_denominators(self):
        rom = self._rom()
        baseline = self._baseline()
        produced: list[list[dict]] = []
        for packet in self.PACKETS:
            helper = getattr(coverage_auditor, packet["helper"], None)
            self.assertIsNotNone(helper, f"{packet['label']} coverage helper is absent")
            claims = helper(ROOT, rom, [*baseline, *[row for batch in produced for row in batch]])
            produced.append(claims)
            self.assertEqual(len(packet["rows"]), len(claims))
            self.assertEqual(
                [row[0] for row in packet["rows"]],
                [claim["range"] for claim in claims],
            )
            self.assertEqual(
                [self._expected_id(packet, interval, kind) for interval, kind, _ in packet["rows"]],
                [claim["id"] for claim in claims],
            )
            packed = b"".join(rom[start:end] for (start, end), _, _ in packet["rows"])
            vector = json.dumps(
                [interval for interval, _, _ in packet["rows"]],
                separators=(",", ":"),
            ).encode("ascii")
            self.assertEqual(packet["binary_sha256"], hashlib.sha256(packed).hexdigest())
            self.assertEqual(packet["range_vector_sha256"], hashlib.sha256(vector).hexdigest())
            for index, (claim, (interval, kind, sha256)) in enumerate(
                zip(claims, packet["rows"], strict=True)
            ):
                self.assertEqual("primary", claim["role"])
                self.assertEqual(kind, claim["primary_class"])
                self.assertEqual(kind, claim["claim_kind"])
                self.assertEqual(packet["batch"], claim["promotion_batch"])
                self.assertEqual("unknown", claim["promoted_from_primary_class"])
                self.assertTrue(claim["baseline_unknown_only"])
                self.assertEqual(sha256, claim["bytes_sha256"])
                self.assertEqual(
                    sha256,
                    hashlib.sha256(rom[slice(*interval)]).hexdigest(),
                )
                self.assertEqual(packet["manifest_sha256"], claim["promotion_manifest_sha256"])
                self.assertEqual(packet["payload_sha256"], claim["evidence_sha256"])
                self.assertEqual(f"/promotion_ranges/{index}", claim["evidence_selector"])

    def test_fails_closed_on_duplicate_overlap_verifier_identity_and_rom_drift(self):
        rom = self._rom()
        for packet in self.PACKETS:
            helper = getattr(coverage_auditor, packet["helper"], None)
            self.assertIsNotNone(helper, f"{packet['label']} coverage helper is absent")
            baseline = self._baseline()
            if packet["label"] == "cgbsound":
                baseline += coverage_auditor._cgb_helper_bounded_cfg_claims(
                    ROOT, rom, baseline
                )
            with self.assertRaisesRegex(ValueError, "already present"):
                helper(
                    ROOT,
                    rom,
                    [*baseline, {"id": "injected-batch", "range": [0, 1], "role": "secondary", "promotion_batch": packet["batch"]}],
                )
            start, end = packet["rows"][0][0]
            with self.assertRaisesRegex(ValueError, "unknown|overlap"):
                helper(
                    ROOT,
                    rom,
                    [*baseline, {"id": "injected-owner", "range": [start, end], "role": "primary", "primary_class": "injected"}],
                )
            excluded_start, excluded_end = packet["excluded"][0]
            with self.assertRaisesRegex(ValueError, "excluded|unknown|overlap"):
                helper(
                    ROOT,
                    rom,
                    [*baseline, {"id": "injected-excluded-owner", "range": [excluded_start, excluded_end], "role": "primary", "primary_class": "injected"}],
                )
            verifier_name = (
                "verify_rom_cgb_helper_bounded_cfg"
                if packet["label"] == "helper"
                else "verify_rom_cgbsound_bounded_cfg"
            )
            with mock.patch.object(
                coverage_auditor,
                verifier_name,
                return_value={"verified": False, "contract_ok": False},
                create=True,
            ):
                with self.assertRaisesRegex(ValueError, "independent verification"):
                    helper(ROOT, rom, baseline)
            constant = (
                "CGB_HELPER_BOUNDED_MANIFEST_SHA256"
                if packet["label"] == "helper"
                else "CGBSOUND_BOUNDED_MANIFEST_SHA256"
            )
            with mock.patch.object(coverage_auditor, constant, "0" * 64, create=True):
                with self.assertRaisesRegex(ValueError, "identity"):
                    helper(ROOT, rom, baseline)
            tampered = bytearray(rom)
            tampered[start] ^= 1
            with self.assertRaisesRegex(ValueError, "ROM"):
                helper(ROOT, bytes(tampered), baseline)

    def test_helpers_are_nonrecursive_and_integrated_after_dispatcher_before_gaps(self):
        rom = self._rom()
        baseline = self._baseline()
        with mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("bounded helpers must not atomize the ROM"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("bounded helpers must not recurse"),
        ):
            helper_claims = coverage_auditor._cgb_helper_bounded_cfg_claims(
                ROOT, rom, baseline
            )
            sound_claims = coverage_auditor._cgbsound_bounded_cfg_claims(
                ROOT, rom, [*baseline, *helper_claims]
            )
        self.assertEqual(9, len(helper_claims))
        self.assertEqual(19, len(sound_claims))

        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        calls = [
            "claims += _mp2k_dispatcher_claims(root, rom, claims)",
            "claims += _cgb_helper_bounded_cfg_claims(root, rom, claims)",
            "claims += _cgbsound_bounded_cfg_claims(root, rom, claims)",
            "claims += _artifact_bound_alignment_gap_claims(root, rom, claims)",
        ]
        for call in calls:
            self.assertEqual(1, source.count(call), call)
        self.assertEqual(sorted(source.index(call) for call in calls), [source.index(call) for call in calls])

    def test_build_manifest_exports_bounded_cfg_summary_and_limitations(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        for label in ("cgb_helper_bounded_cfg", "cgbsound_bounded_cfg"):
            for suffix in (
                "promotion_batch",
                "promoted_bytes",
                "promotion_claim_count",
                "code_bytes",
                "literal_bytes",
                "range_vector_sha256",
                "packed_bytes_sha256",
                "manifest_sha256",
                "payload_sha256",
                "independent_verifier_sha256",
            ):
                self.assertIn(f'"{label}_{suffix}"', source)
        self.assertIn("CGB_HELPER_BOUNDED_COVERAGE_LIMITATION", source)
        self.assertIn("CGBSOUND_BOUNDED_COVERAGE_LIMITATION", source)

    def test_committed_manifest_contains_both_exact_bounded_denominators(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        expected_totals = {
            "cgb_helper_bounded_cfg_promoted_bytes": 180,
            "cgb_helper_bounded_cfg_promotion_claim_count": 9,
            "cgb_helper_bounded_cfg_code_bytes": 164,
            "cgb_helper_bounded_cfg_literal_bytes": 16,
            "cgbsound_bounded_cfg_promoted_bytes": 1_084,
            "cgbsound_bounded_cfg_promotion_claim_count": 19,
            "cgbsound_bounded_cfg_code_bytes": 1_008,
            "cgbsound_bounded_cfg_literal_bytes": 76,
        }
        for key, value in expected_totals.items():
            self.assertEqual(value, summary[key])
        segments = {
            tuple(segment["range"]): segment
            for segment in manifest["segments"]
        }
        for packet in self.PACKETS:
            for interval, kind, _sha256 in packet["rows"]:
                self.assertEqual(kind, segments[tuple(interval)]["primary_class"])
        self.assertIn(
            coverage_auditor.CGB_HELPER_BOUNDED_COVERAGE_LIMITATION,
            manifest["limitations"],
        )
        self.assertIn(
            coverage_auditor.CGBSOUND_BOUNDED_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class ArtifactBoundAlignmentGapCoverageTests(unittest.TestCase):
    """Coverage contract for thirteen artifact-bound align4 byte ranges."""

    BATCH = "rom-artifact-bound-alignment-gaps-v1"
    PRIMARY_CLASS = "artifact_bound_4byte_alignment_bytes"
    CLAIM_KIND = "artifact_bound_alignment_gap_bytes"
    RANGES = [
        [0x061D62, 0x061D64],
        [0x061D7A, 0x061D7C],
        [0x061DEA, 0x061DEC],
        [0x09B4C6, 0x09B4C8],
        [0x09B572, 0x09B574],
        [0x09B586, 0x09B588],
        [0x09B676, 0x09B678],
        [0x09B696, 0x09B698],
        [0x09B702, 0x09B704],
        [0x09B762, 0x09B764],
        [0x09B94A, 0x09B94C],
        [0x09B96E, 0x09B970],
        [0x09B9E2, 0x09B9E4],
    ]
    IDS = [
        "artifact-bound-alignment-gap-061d62",
        "artifact-bound-alignment-gap-061d7a",
        "artifact-bound-alignment-gap-061dea",
        "artifact-bound-alignment-gap-09b4c6",
        "artifact-bound-alignment-gap-09b572",
        "artifact-bound-alignment-gap-09b586",
        "artifact-bound-alignment-gap-09b676",
        "artifact-bound-alignment-gap-09b696",
        "artifact-bound-alignment-gap-09b702",
        "artifact-bound-alignment-gap-09b762",
        "artifact-bound-alignment-gap-09b94a",
        "artifact-bound-alignment-gap-09b96e",
        "artifact-bound-alignment-gap-09b9e2",
    ]
    BOUNDARY_IDS = [
        "scheduler-return-to-literal-061d62",
        "scheduler-branch-to-function-061d7a",
        "scheduler-return-to-literal-061dea",
        "psg-branch-to-literal-09b4c6",
        "cgb-helper-branch-to-literal-09b572",
        "cgb-helper-return-to-literal-09b586",
        "cgbsound-branch-to-literal-09b676",
        "cgbsound-branch-to-literal-09b696",
        "cgbsound-branch-to-literal-09b702",
        "cgbsound-branch-to-literal-09b762",
        "cgbsound-branch-to-literal-09b94a",
        "cgbsound-branch-to-literal-09b96e",
        "cgbsound-branch-to-literal-09b9e2",
    ]
    LEFT_OWNER_IDS = [
        "scheduler-code-02-061d10",
        "scheduler-code-03-061d70",
        "cfg-thumb-0000-061d7c",
        "psg-frequency-code-a-09b494",
        "cgb-helper-code-09b56c",
        "cgb-helper-code-09b578",
        "cgbsound-code-09b66c",
        "cgbsound-code-09b684",
        "cgbsound-code-09b6a4",
        "cgbsound-code-09b710",
        "cgbsound-code-09b768",
        "cgbsound-code-09b954",
        "cgbsound-code-09b974",
    ]
    RIGHT_OWNER_IDS = [
        "scheduler-literal-01-061d64",
        "cfg-thumb-0000-061d7c",
        "scheduler-literal-02-061dec",
        "psg-frequency-noise-literal-09b4c8",
        "cgb-helper-literal-09b574",
        "cgb-helper-literal-09b588",
        "cgbsound-literal-09b678",
        "cgbsound-literal-09b698",
        "cgbsound-literal-09b704",
        "cgbsound-literal-09b764",
        "cgbsound-literal-09b94c",
        "cgbsound-literal-09b970",
        "cgbsound-literal-09b9e4",
    ]
    RIGHT_KINDS = [
        "consumed_literal_range",
        "owned_thumb_function",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
        "consumed_literal_range",
    ]
    RANGE_VECTOR_SHA256 = (
        "d6582d3ca46f1bacb82537740370874320c79592f3c9512747affd4db5285741"
    )
    BOUNDARY_VECTOR_SHA256 = (
        "7dd56d026c90f090f3b4fbceb055bbe3db35786e915e4ace4ae61a6b06230843"
    )
    CLAIM_DENOMINATOR_SHA256 = (
        "1962c626da011e7ac32287662593e55cea72d5d21b003a419e78085a087b8d46"
    )
    SOURCE_FILE_VECTOR_SHA256 = (
        "d14919e7abafeb1891e1336d0511b5ab0e44ef6091ee010ca842ca6c6fd3f92f"
    )
    GAP_SHA256 = (
        "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
    )
    PACKED_SHA256 = (
        "659d36ca563ba4622daabb36a71dafaf6060cdcbf89bb12e75426198496d272c"
    )
    VERIFIER_PATH = "tools/verify_rom_artifact_bound_alignment_gaps.py"
    VERIFIER_SHA256 = (
        "784970276d8974c1390a4f33a12950dd5a2d2faefb894d7b7cc3856f38198227"
    )
    TEST_PATH = "tests/test_verify_rom_artifact_bound_alignment_gaps.py"
    TEST_SHA256 = (
        "b26c5b841a7a10b077ad9cc4446715908d6a5cc574fbd7a7953d65fae2a824fd"
    )
    REPORT_SHA256 = (
        "58c8b2f9badfa2bb40edb570ddef879ab56412bdf4e477e9e16f074ebc121d28"
    )
    NON_CLAIMS = {
        "padding_semantics_claimed",
        "nop_instruction_claimed",
        "reserved_space_claimed",
        "free_space_claimed",
        "allocatable_space_claimed",
        "natural_runtime_reachability_claimed",
        "global_unreachability_claimed",
        "compiler_authorship_claimed",
        "editing_writeback_relocation_safe_claimed",
        "right_structure_semantics_extended_claimed",
        "all_alignment_gaps_exhaustive_claimed",
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        baseline = [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("id") not in set(cls.IDS)
            and claim.get("promotion_batch")
            not in {
                "rom-cgb-helper-bounded-cfg-v1",
                "rom-cgbsound-bounded-cfg-v1",
            }
        ]
        rom = cls._rom()
        helper_claims = coverage_auditor._cgb_helper_bounded_cfg_claims(
            ROOT, rom, baseline
        )
        sound_claims = coverage_auditor._cgbsound_bounded_cfg_claims(
            ROOT, rom, [*baseline, *helper_claims]
        )
        return [*baseline, *helper_claims, *sound_claims]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_artifact_bound_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "artifact-bound alignment helper is absent")
        return helper

    def test_promotes_exact_boundaries_and_preserves_nonclaims(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.BOUNDARY_IDS, [claim["boundary_id"] for claim in claims])
        self.assertEqual(self.LEFT_OWNER_IDS, [claim["previous_owner_id"] for claim in claims])
        self.assertEqual(self.RIGHT_OWNER_IDS, [claim["next_owner_id"] for claim in claims])
        self.assertEqual(self.RIGHT_KINDS, [claim["right_structure_kind"] for claim in claims])
        self.assertEqual(26, sum(end - start for start, end in self.RANGES))
        for index, claim in enumerate(claims):
            start, end = self.RANGES[index]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual([0x08000000 + start, 0x08000000 + end], claim["gba_range"])
            self.assertEqual(self.GAP_SHA256, claim["bytes_sha256"])
            self.assertEqual(self.PACKED_SHA256, claim["packed_bytes_sha256"])
            self.assertEqual(self.RANGE_VECTOR_SHA256, claim["range_vector_sha256"])
            self.assertEqual(self.BOUNDARY_VECTOR_SHA256, claim["boundary_vector_sha256"])
            self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, claim["claim_denominator_sha256"])
            self.assertEqual(self.SOURCE_FILE_VECTOR_SHA256, claim["source_file_vector_sha256"])
            self.assertEqual([index * 2, index * 2 + 2], claim["packed_range"])
            self.assertEqual(4, claim["alignment_bytes"])
            self.assertEqual(end, claim["alignment_target"])
            self.assertEqual("(left_end + 3) & ~3", claim["alignment_formula_expression"])
            self.assertEqual(2, claim["alignment_gap_bytes"])
            self.assertTrue(claim["alignment_gap_is_exact"])
            self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
            self.assertEqual(self.VERIFIER_SHA256, claim["independent_verifier_sha256"])
            self.assertEqual(self.TEST_PATH, claim["upstream_test_path"])
            self.assertEqual(self.TEST_SHA256, claim["upstream_test_sha256"])
            self.assertEqual(self.REPORT_SHA256, claim["independent_verifier_report_sha256"])
            self.assertEqual(self.GAP_SHA256, hashlib.sha256(rom[start:end]).hexdigest())
            for flag in self.NON_CLAIMS:
                with self.subTest(index=index, flag=flag):
                    self.assertIs(claim[flag], False)

    def test_fails_closed_on_overlap_duplicate_report_and_identity_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-alignment-owner",
                        "range": [self.RANGES[0][0], self.RANGES[0][0] + 1],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-alignment-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_artifact_bound_alignment_gaps",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor,
            "ARTIFACT_BOUND_ALIGNMENT_GAP_VERIFIER_SHA256",
            "0" * 64,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)

    def test_fails_closed_on_owner_range_kind_and_rom_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        owner = next(
            claim for claim in baseline if claim.get("id") == self.RIGHT_OWNER_IDS[1]
        )
        changed = copy.deepcopy(baseline)
        next(claim for claim in changed if claim.get("id") == owner["id"])[
            "primary_class"
        ] = "injected"
        with self.assertRaisesRegex(ValueError, "owner.*identity|boundary"):
            helper(ROOT, rom, changed)
        tampered = bytearray(rom)
        tampered[self.RANGES[0][0]] = 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_integration_call_summary_and_no_recursive_coverage_read(self):
        helper = self._helper()
        build_source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        dispatcher_call = "claims += _mp2k_dispatcher_claims(root, rom, claims)"
        helper_call = "claims += _cgb_helper_bounded_cfg_claims(root, rom, claims)"
        sound_call = "claims += _cgbsound_bounded_cfg_claims(root, rom, claims)"
        alignment_call = "claims += _artifact_bound_alignment_gap_claims(root, rom, claims)"
        for call in (dispatcher_call, helper_call, sound_call, alignment_call):
            self.assertEqual(1, build_source.count(call), call)
        self.assertLess(build_source.index(dispatcher_call), build_source.index(helper_call))
        self.assertLess(build_source.index(helper_call), build_source.index(sound_call))
        self.assertLess(build_source.index(sound_call), build_source.index(alignment_call))
        for key in (
            "artifact_bound_alignment_gap_promotion_batch",
            "artifact_bound_alignment_gap_bytes",
            "artifact_bound_alignment_gap_claim_count",
            "artifact_bound_alignment_gap_claim_denominator_sha256",
            "artifact_bound_alignment_gap_range_vector_sha256",
            "artifact_bound_alignment_gap_independent_verifier_report_sha256",
        ):
            self.assertIn(f'"{key}"', build_source)
        helper_source = __import__("inspect").getsource(helper)
        self.assertNotIn("build_manifest(", helper_source)
        self.assertNotIn("atomize_claims(", helper_source)
        self.assertNotIn("rom-byte-coverage.json", helper_source)

    def test_committed_manifest_has_exact_delta_segments_and_limitation(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["artifact_bound_alignment_gap_promotion_batch"])
        self.assertEqual(26, summary["artifact_bound_alignment_gap_bytes"])
        self.assertEqual(13, summary["artifact_bound_alignment_gap_claim_count"])
        segments = {tuple(segment["range"]): segment for segment in manifest["segments"]}
        for interval in map(tuple, self.RANGES):
            self.assertEqual(self.PRIMARY_CLASS, segments[interval]["primary_class"])
        self.assertIn(
            coverage_auditor.ARTIFACT_BOUND_ALIGNMENT_GAP_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class MPlayMainSchedulerCoverageTests(unittest.TestCase):
    """Coverage contract for the immutable 612-byte MPlayMain packet."""

    ARTIFACT = ROOT / "artifacts/rom-mplaymain-scheduler-v1"
    BATCH = "rom-mplaymain-scheduler-v1"
    RANGES = [[0x09A42C, 0x09A684], [0x09A688, 0x09A694]]
    IDS = ["mplaymain-code-00-09a42c", "mplaymain-literal-00-09a688"]
    CLASSES = [
        "armv4t_mplaymain_scheduler_thumb_code",
        "mplaymain_scheduler_consumed_literals",
    ]
    KINDS = [
        "mplaymain_scheduler_reachable_instruction_bytes",
        "mplaymain_scheduler_consumed_literal_bytes",
    ]

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in set(cls.KINDS)
        ]

    @staticmethod
    def _helper():
        return coverage_auditor._mplaymain_scheduler_claims

    def test_promotes_exact_code_and_literal_ranges(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(["thumb", None], [claim["mode"] for claim in claims])
        self.assertEqual(2, len({claim["id"] for claim in claims}))
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(self.IDS[index], claim["artifact_range_id"])
            self.assertEqual(
                f"/promotion_ranges/{index}", claim["evidence_selector"]
            )
            self.assertEqual(
                "artifacts/rom-mplaymain-scheduler-v1/rom-mplaymain-scheduler.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "tools/verify_rom_mplaymain_scheduler_bundle.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(claim["non_claims"]["natural_runtime_reachable"])
            self.assertFalse(claim["non_claims"]["callback_lifecycle_closed"])
            self.assertFalse(
                claim["non_claims"][
                    "global_ram_or_computed_producer_denominator_complete"
                ]
            )

    def test_preserves_owned_veneer_and_two_byte_unknown_gap(self):
        rom = self._rom()
        baseline = self._baseline()
        claims = self._helper()(ROOT, rom, baseline)
        owner = next(
            claim
            for claim in baseline
            if claim.get("id") == "cfg-thumb-0752-09a684"
        )
        self.assertEqual([0x09A684, 0x09A686], owner["range"])
        self.assertEqual(
            "armv4t_cfg_reachable_thumb_code",
            owner["primary_class"],
        )
        for interval in ([0x09A684, 0x09A686], [0x09A686, 0x09A688]):
            start, end = interval
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )

    def test_loader_fails_closed_on_overlap_duplicate_verifier_and_identity_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-mplaymain-owner",
                        "range": [0x09A42C, 0x09A42D],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-mplaymain-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_mplaymain_scheduler_bundle",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "MPLAYMAIN_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x09A42C] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_loader_uses_immutable_bundle_and_is_non_recursive(self):
        helper = self._helper()
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_mplaymain_scheduler_bundle",
            wraps=coverage_auditor.verify_rom_mplaymain_scheduler_bundle,
        ) as bundle, mock.patch(
            "tools.audit_rom_byte_coverage.atomize_claims",
            side_effect=AssertionError("helper must not atomize full coverage"),
        ), mock.patch(
            "tools.audit_rom_byte_coverage.build_manifest",
            side_effect=AssertionError("helper must not recurse into build_manifest"),
        ):
            claims = helper(ROOT, self._rom(), self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        bundle.assert_called_once()
        helper_source = __import__("inspect").getsource(helper)
        self.assertNotIn("verify_rom_mplaymain_scheduler(", helper_source)
        self.assertNotIn("rom-byte-coverage.json", helper_source)

    def test_build_manifest_integration_and_summary_fields_are_exact(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        historical_alignment_call = (
            "claims += _historical_artifact_bound_alignment_gap_claims(root, rom, claims)"
        )
        alignment_call = "claims += _artifact_bound_alignment_gap_claims(root, rom, claims)"
        mplaymain_call = "claims += _mplaymain_scheduler_claims(root, rom, claims)"
        helper_call = "claims += _cgb_helper_bounded_cfg_claims(root, rom, claims)"
        sound_call = "claims += _cgbsound_bounded_cfg_claims(root, rom, claims)"
        self.assertIn(historical_alignment_call, source)
        self.assertIn(alignment_call, source)
        self.assertIn(mplaymain_call, source)
        self.assertIn(helper_call, source)
        self.assertIn(sound_call, source)
        self.assertLess(source.index(historical_alignment_call), source.index(mplaymain_call))
        self.assertLess(source.index(mplaymain_call), source.index(helper_call))
        self.assertLess(source.index(helper_call), source.index(sound_call))
        self.assertLess(source.index(sound_call), source.index(alignment_call))
        for key in (
            "mplaymain_scheduler_promotion_batch",
            "mplaymain_scheduler_code_bytes",
            "mplaymain_scheduler_code_claim_count",
            "mplaymain_scheduler_literal_bytes",
            "mplaymain_scheduler_literal_claim_count",
            "mplaymain_scheduler_promoted_bytes",
            "mplaymain_scheduler_promotion_claim_count",
            "mplaymain_scheduler_owned_provenance_bytes",
            "mplaymain_scheduler_gap_bytes",
            "mplaymain_scheduler_union_range_vector_sha256",
            "mplaymain_scheduler_frontier_count",
        ):
            self.assertIn(f'"{key}"', source)

    def test_committed_manifest_has_exact_projected_totals_segments_and_limitation(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["mplaymain_scheduler_promotion_batch"])
        self.assertEqual(600, summary["mplaymain_scheduler_code_bytes"])
        self.assertEqual(12, summary["mplaymain_scheduler_literal_bytes"])
        self.assertEqual(612, summary["mplaymain_scheduler_promoted_bytes"])
        self.assertEqual(2, summary["mplaymain_scheduler_promotion_claim_count"])
        segments = {tuple(item["range"]): item for item in manifest["segments"]}
        # 段表必须连续铺满本包所在窗口，并与主 claim 表的逐字节投影一致。
        # 冻结区间键不可用：后继批次（cfg-v2 consumed literal 与
        # cfg-proven-roots-v15）会合法地把当初的 unknown 间隙再切开，
        # 区间键随之消失，但账本本身仍然正确。
        tiles, owner = _ledger_window_tiles(manifest, 0x09A3DC, 0x09A694)
        self.assertEqual(0x09A3DC, tiles[0][0])
        self.assertEqual(0x09A694, tiles[-1][1])
        for previous, current in zip(tiles, tiles[1:]):
            self.assertEqual(previous[1], current[0])
        for begin, stop, primary_class in tiles:
            for offset in range(begin, stop):
                self.assertEqual(owner[offset][0], primary_class)
        # 本包自己认领的两段必须原样在位，且窗口内其余字节不得挂在本包名下。
        self.assertEqual(
            self.CLASSES[0],
            segments[(0x09A42C, 0x09A684)]["primary_class"],
        )
        self.assertEqual(
            self.CLASSES[1],
            segments[(0x09A688, 0x09A694)]["primary_class"],
        )
        owned_ranges: list[list[int]] = []
        for offset in sorted(owner):
            if owner[offset][1] != self.BATCH:
                continue
            if owned_ranges and owned_ranges[-1][1] == offset:
                owned_ranges[-1][1] = offset + 1
            else:
                owned_ranges.append([offset, offset + 1])
        self.assertEqual(
            [[0x09A42C, 0x09A684], [0x09A688, 0x09A694]],
            owned_ranges,
        )
        self.assertIn(
            coverage_auditor.MPLAYMAIN_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class SoundMainRelocatedCfgCoverageTests(unittest.TestCase):
    """Coverage contract for the externally anchored 924-byte SoundMain packet."""

    ARTIFACT = ROOT / "artifacts/rom-soundmain-relocated-cfg-v1"
    BATCH = "rom-soundmain-relocated-cfg-v1"
    RANGES = [
        [0x099E10, 0x099E1A],
        [0x099E1C, 0x099EC2],
        [0x099EC4, 0x099EC8],
        [0x099EC8, 0x099FA6],
        [0x099FA8, 0x09A1AE],
        [0x09A1B0, 0x09A1B4],
    ]
    IDS = [
        "soundmain-code-00-099e10",
        "soundmain-code-01-099e1c",
        "soundmain-literal-00-099ec4",
        "soundmain-code-02-099ec8",
        "soundmain-code-03-099fa8",
        "soundmain-literal-01-09a1b0",
    ]
    CODE_CLASS = "armv4t_soundmain_relocated_mixed_isa_code"
    LITERAL_CLASS = "soundmain_relocated_consumed_literal_bytes"
    CODE_KIND = "soundmain_relocated_reachable_instruction_bytes"
    LITERAL_KIND = "soundmain_relocated_consumed_literal_bytes"
    CLASSES = [
        CODE_CLASS,
        CODE_CLASS,
        LITERAL_CLASS,
        CODE_CLASS,
        CODE_CLASS,
        LITERAL_CLASS,
    ]
    KINDS = [
        CODE_KIND,
        CODE_KIND,
        LITERAL_KIND,
        CODE_KIND,
        CODE_KIND,
        LITERAL_KIND,
    ]
    GAPS = [
        [0x099E1A, 0x099E1C],
        [0x099EC2, 0x099EC4],
        [0x099FA6, 0x099FA8],
    ]

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in {cls.CODE_KIND, cls.LITERAL_KIND}
            and claim.get("promotion_batch")
            != "rom-soundmain-relocated-alignment-gaps-v1"
            and claim.get("claim_kind")
            != "soundmain_relocated_alignment_gap_bytes"
        ]

    @staticmethod
    def _helper():
        return coverage_auditor._soundmain_relocated_cfg_claims

    def test_promotes_exact_six_code_and_literal_ranges(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(
            [
                "mixed_arm_thumb_relocated",
                "mixed_arm_thumb_relocated",
                None,
                "mixed_arm_thumb_relocated",
                "mixed_arm_thumb_relocated",
                None,
            ],
            [claim["mode"] for claim in claims],
        )
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"]
            )
            self.assertEqual(self.IDS[index], claim["artifact_range_id"])
            self.assertEqual(f"/promotion_ranges/{index}", claim["evidence_selector"])
            self.assertEqual(
                "artifacts/rom-soundmain-relocated-cfg-v1/rom-soundmain-relocated-cfg.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "tools/verify_rom_soundmain_relocated_cfg_bundle.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(claim["non_claims"]["natural_runtime_reachability_complete"])
            self.assertFalse(
                claim["non_claims"][
                    "computed_or_indirect_producer_denominator_complete"
                ]
            )

    def test_semantic_packet_preserves_three_deferred_gaps_and_return_veneer(self):
        baseline = self._baseline()
        claims = self._helper()(ROOT, self._rom(), baseline)
        owner = next(
            claim
            for claim in baseline
            if claim.get("id") == "boot-thumb-handoff-code-22-09a1ae"
        )
        self.assertEqual([0x09A1AE, 0x09A1B0], owner["range"])
        self.assertEqual(
            "armv4t_boot_thumb_handoff_reachable_code",
            owner["primary_class"],
        )
        for interval in [*self.GAPS, owner["range"]]:
            start, end = interval
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )

    def test_loader_fails_closed_on_overlap_batch_wrapper_and_identity_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-soundmain-owner",
                        "range": [0x099E10, 0x099E11],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-soundmain-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_soundmain_relocated_cfg_bundle",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "SOUNDMAIN_RELOCATED_MANIFEST_SHA256", "0" * 64
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x099E10] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_build_manifest_integration_and_summary_fields_are_exact(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        mplaymain_call = "claims += _mplaymain_scheduler_claims(root, rom, claims)"
        soundmain_call = "claims += _soundmain_relocated_cfg_claims(root, rom, claims)"
        self.assertIn(mplaymain_call, source)
        self.assertIn(soundmain_call, source)
        self.assertLess(source.index(mplaymain_call), source.index(soundmain_call))
        for key in (
            "soundmain_relocated_promotion_batch",
            "soundmain_relocated_code_bytes",
            "soundmain_relocated_code_claim_count",
            "soundmain_relocated_literal_bytes",
            "soundmain_relocated_literal_claim_count",
            "soundmain_relocated_promoted_bytes",
            "soundmain_relocated_promotion_claim_count",
            "soundmain_relocated_gap_bytes",
            "soundmain_relocated_union_range_vector_sha256",
            "soundmain_relocated_block_count",
        ):
            self.assertIn(f'"{key}"', source)

    def test_committed_manifest_has_projected_totals_segments_and_limitation(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["soundmain_relocated_promotion_batch"])
        self.assertEqual(916, summary["soundmain_relocated_code_bytes"])
        self.assertEqual(8, summary["soundmain_relocated_literal_bytes"])
        self.assertEqual(924, summary["soundmain_relocated_promoted_bytes"])
        self.assertEqual(6, summary["soundmain_relocated_promotion_claim_count"])
        segments = {tuple(item["range"]): item for item in manifest["segments"]}
        expected = {
            (0x099E10, 0x099E1A): self.CODE_CLASS,
            (0x099E1A, 0x099E1C): (
                "soundmain_relocated_artifact_bound_4byte_alignment_bytes"
            ),
            (0x099E1C, 0x099EC2): self.CODE_CLASS,
            (0x099EC2, 0x099EC4): (
                "soundmain_relocated_artifact_bound_4byte_alignment_bytes"
            ),
            (0x099EC4, 0x099EC8): self.LITERAL_CLASS,
            (0x099EC8, 0x099FA6): self.CODE_CLASS,
            (0x099FA6, 0x099FA8): (
                "soundmain_relocated_artifact_bound_4byte_alignment_bytes"
            ),
            (0x099FA8, 0x09A1AE): self.CODE_CLASS,
            (0x09A1AE, 0x09A1B0): "armv4t_boot_thumb_handoff_reachable_code",
            (0x09A1B0, 0x09A1B4): self.LITERAL_CLASS,
        }
        for interval, primary_class in expected.items():
            self.assertEqual(primary_class, segments[interval]["primary_class"])
        self.assertIn(
            coverage_auditor.SOUNDMAIN_RELOCATED_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class SoundMainRelocatedAlignmentGapCoverageTests(unittest.TestCase):
    """Coverage contract for three additive SoundMain align4 gap claims."""

    BATCH = "rom-soundmain-relocated-alignment-gaps-v1"
    PRIMARY_CLASS = "soundmain_relocated_artifact_bound_4byte_alignment_bytes"
    CLAIM_KIND = "soundmain_relocated_alignment_gap_bytes"
    RANGES = [
        [0x099E1A, 0x099E1C],
        [0x099EC2, 0x099EC4],
        [0x099FA6, 0x099FA8],
    ]
    IDS = [
        "soundmain-alignment-gap-00-099e1a",
        "soundmain-alignment-gap-01-099ec2",
        "soundmain-alignment-gap-02-099fa6",
    ]
    BOUNDARY_IDS = [
        "soundmain-thumb-to-arm-099e1a",
        "soundmain-branch-to-literal-099ec2",
        "soundmain-thumb-to-arm-099fa6",
    ]
    LEFT_OWNER_IDS = [
        "soundmain-code-00-099e10",
        "soundmain-code-01-099e1c",
        "soundmain-code-02-099ec8",
    ]
    RIGHT_OWNER_IDS = [
        "soundmain-code-01-099e1c",
        "soundmain-literal-00-099ec4",
        "soundmain-code-03-099fa8",
    ]
    RIGHT_KINDS = ["arm_block", "consumed_literal_range", "arm_block"]
    RIGHT_STRUCTURE_RANGES = [
        [0x099E1C, 0x099E2C],
        [0x099EC4, 0x099EC8],
        [0x099FA8, 0x099FC8],
    ]
    RANGE_VECTOR_SHA256 = (
        "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af"
    )
    BOUNDARY_VECTOR_SHA256 = (
        "2f21e70062013bff5f99a9191920f3a6b4ee8996fd1adb0d8cfe577f7d450dd4"
    )
    CLAIM_DENOMINATOR_SHA256 = (
        "ed6703a2245ca526dc40809dafbaa65328faec20f5aa493ab735ab70128cbd6c"
    )
    SOURCE_FILE_VECTOR_SHA256 = (
        "94d5aa4caa9f45d802f4cecde10d1f08ee4c5650a0c4f24bf40707f2ca1888a2"
    )
    PACKED_BYTES_SHA256 = (
        "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44"
    )
    VERIFIER_PATH = "tools/verify_rom_soundmain_relocated_alignment_gaps.py"
    VERIFIER_SHA256 = (
        "0ae3c5c6f2a4d2315cd3f5b10f422faa2babfafe220d8b12069f510a6badc00a"
    )
    TEST_PATH = "tests/test_verify_rom_soundmain_relocated_alignment_gaps.py"
    TEST_SHA256 = (
        "220e3e3ecdda28cf7675952e0823aba8baefcaea6663ec36333120353c8155d5"
    )
    REPORT_SHA256 = (
        "95b54d511b064b652c50b5b34519ae6bc887a41e60c0321aa56fc9cc4a059b5f"
    )

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("id") not in cls.IDS
        ]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_soundmain_relocated_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "SoundMain alignment-gap helper is absent")
        return helper

    def test_promotes_exact_three_ranges_with_frozen_boundary_provenance(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        for index, claim in enumerate(claims):
            start, end = self.RANGES[index]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(self.BOUNDARY_IDS[index], claim["boundary_id"])
            self.assertEqual(self.LEFT_OWNER_IDS[index], claim["previous_owner_id"])
            self.assertEqual(self.RIGHT_OWNER_IDS[index], claim["next_owner_id"])
            self.assertEqual(self.RIGHT_KINDS[index], claim["right_structure_kind"])
            self.assertEqual(
                self.RIGHT_STRUCTURE_RANGES[index],
                claim["right_structure_range"],
            )
            self.assertEqual([index * 2, index * 2 + 2], claim["packed_range"])
            self.assertEqual(
                hashlib.sha256(rom[start:end]).hexdigest(),
                claim["bytes_sha256"],
            )
            self.assertEqual(self.RANGE_VECTOR_SHA256, claim["range_vector_sha256"])
            self.assertEqual(
                self.BOUNDARY_VECTOR_SHA256,
                claim["boundary_vector_sha256"],
            )
            self.assertEqual(
                self.CLAIM_DENOMINATOR_SHA256,
                claim["claim_denominator_sha256"],
            )
            self.assertEqual(
                self.SOURCE_FILE_VECTOR_SHA256,
                claim["source_file_vector_sha256"],
            )
            self.assertEqual(self.PACKED_BYTES_SHA256, claim["packed_bytes_sha256"])
            self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
            self.assertEqual(self.VERIFIER_SHA256, claim["independent_verifier_sha256"])
            self.assertEqual(self.TEST_PATH, claim["upstream_test_path"])
            self.assertEqual(self.TEST_SHA256, claim["upstream_test_sha256"])
            self.assertEqual(
                self.REPORT_SHA256,
                claim["independent_verifier_report_sha256"],
            )
            self.assertTrue(all(value is False for value in claim["non_claims"].values()))

    def test_fails_closed_on_overlap_duplicate_verifier_and_identity_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-soundmain-gap-owner",
                        "range": [0x099E1A, 0x099E1B],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-soundmain-gap-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_soundmain_relocated_alignment_gaps",
            return_value={"verified": False, "errors": ["injected"]},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor,
            "SOUNDMAIN_RELOCATED_ALIGNMENT_GAP_VERIFIER_SHA256",
            "0" * 64,
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x099E1A] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_build_manifest_integrates_after_semantic_packet_with_summary_contract(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        semantic_call = "claims += _soundmain_relocated_cfg_claims(root, rom, claims)"
        gap_call = (
            "claims += _soundmain_relocated_alignment_gap_claims(root, rom, claims)"
        )
        self.assertIn(semantic_call, source)
        self.assertIn(gap_call, source)
        self.assertLess(source.index(semantic_call), source.index(gap_call))
        for key in (
            "soundmain_relocated_alignment_gap_promotion_batch",
            "soundmain_relocated_alignment_gap_bytes",
            "soundmain_relocated_alignment_gap_claim_count",
            "soundmain_relocated_alignment_gap_range_vector_sha256",
            "soundmain_relocated_alignment_gap_claim_denominator_sha256",
            "soundmain_relocated_alignment_gap_independent_verifier_report_sha256",
        ):
            self.assertIn(f'"{key}"', source)

    def test_committed_manifest_has_exact_totals_segments_and_limitation(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(
            self.BATCH,
            summary["soundmain_relocated_alignment_gap_promotion_batch"],
        )
        self.assertEqual(6, summary["soundmain_relocated_alignment_gap_bytes"])
        self.assertEqual(3, summary["soundmain_relocated_alignment_gap_claim_count"])
        segments = {tuple(item["range"]): item for item in manifest["segments"]}
        for interval in map(tuple, self.RANGES):
            self.assertEqual(self.PRIMARY_CLASS, segments[interval]["primary_class"])
        self.assertIn(
            coverage_auditor.SOUNDMAIN_RELOCATED_ALIGNMENT_GAP_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class M4aInitializerChainCoverageTests(unittest.TestCase):
    """Coverage contract for the accepted 518-byte m4a initializer chain."""

    BATCH = "rom-m4a-initializer-chain-v1"
    CODE_CLASS = "armv4t_m4a_initializer_chain_thumb_code"
    LITERAL_CLASS = "m4a_initializer_chain_consumed_literal_bytes"
    CODE_KIND = "m4a_initializer_chain_bounded_thumb_code"
    LITERAL_KIND = "m4a_initializer_chain_consumed_literal_bytes"
    RANGES = [
        [0x09AA3C, 0x09AA90],
        [0x09AA90, 0x09AAB4],
        [0x09ACF8, 0x09ADC0],
        [0x09ADC0, 0x09AE10],
        [0x09B17C, 0x09B1E6],
        [0x09B1E8, 0x09B1F4],
    ]
    IDS = [
        "m4a-sound-init-code-09aa3c",
        "m4a-sound-init-literals-09aa90",
        "psg-initializer-code-09acf8",
        "psg-initializer-literals-09adc0",
        "mplay-open-code-09b17c",
        "mplay-open-literals-09b1e8",
    ]
    CLASSES = [CODE_CLASS, LITERAL_CLASS, CODE_CLASS, LITERAL_CLASS, CODE_CLASS, LITERAL_CLASS]
    KINDS = [CODE_KIND, LITERAL_KIND, CODE_KIND, LITERAL_KIND, CODE_KIND, LITERAL_KIND]
    MODES = ["thumb", None, "thumb", None, "thumb", None]

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in {cls.CODE_KIND, cls.LITERAL_KIND}
            and claim.get("id") not in cls.IDS
        ]

    def _helper(self):
        helper = getattr(coverage_auditor, "_m4a_initializer_chain_claims", None)
        self.assertIsNotNone(helper, "m4a initializer-chain coverage helper is absent")
        return helper

    def test_promotes_exact_six_ranges_from_independently_verified_artifact(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(self.MODES, [claim["mode"] for claim in claims])
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"])
            self.assertEqual(self.IDS[index], claim["artifact_range_id"])
            self.assertEqual(f"/coverage_claims/{index}", claim["evidence_selector"])
            self.assertEqual(
                "artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "tools/verify_rom_m4a_initializer_chain.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(claim["non_claims"]["producer_bytes_promoted"])
            self.assertFalse(claim["non_claims"]["natural_runtime_reachability_complete"])

    def test_preserves_raw_producer_and_return_to_pool_gap_as_unknown(self):
        claims = self._helper()(ROOT, self._rom(), self._baseline())
        for interval in ([0x061E28, 0x061E2C], [0x09B1E6, 0x09B1E8]):
            start, end = interval
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )

    def test_loader_fails_closed_on_overlap_duplicate_verifier_and_identity_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-m4a-owner",
                        "range": [0x09AA3C, 0x09AA3D],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-m4a-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_m4a_initializer_chain",
            return_value={"verified": False, "contract_ok": False},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor, "M4A_INITIALIZER_MANIFEST_SHA256", "0" * 64,
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x09AA3C] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_build_manifest_and_committed_coverage_preserve_milestone_delta(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        gap_call = "claims += _soundmain_relocated_alignment_gap_claims(root, rom, claims)"
        initializer_call = "claims += _m4a_initializer_chain_claims(root, rom, claims)"
        self.assertIn(gap_call, source)
        self.assertIn(initializer_call, source)
        self.assertLess(source.index(gap_call), source.index(initializer_call))
        for key in (
            "m4a_initializer_chain_promotion_batch",
            "m4a_initializer_chain_code_bytes",
            "m4a_initializer_chain_literal_bytes",
            "m4a_initializer_chain_promoted_bytes",
            "m4a_initializer_chain_promotion_claim_count",
            "m4a_initializer_chain_union_range_vector_sha256",
            "m4a_initializer_chain_gap_bytes",
        ):
            self.assertIn(f'"{key}"', source)

        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_123_937)
        self.assertLessEqual(summary["unknown_bytes"], 167_519)
        self.assertGreaterEqual(summary["claim_count"], 14_499)
        self.assertGreaterEqual(summary["segment_count"], 16_608)
        self.assertEqual(self.BATCH, summary["m4a_initializer_chain_promotion_batch"])
        self.assertEqual(390, summary["m4a_initializer_chain_code_bytes"])
        self.assertEqual(128, summary["m4a_initializer_chain_literal_bytes"])
        self.assertEqual(518, summary["m4a_initializer_chain_promoted_bytes"])
        self.assertEqual(6, summary["m4a_initializer_chain_promotion_claim_count"])
        segments = {tuple(item["range"]): item for item in manifest["segments"]}
        for interval, primary_class in zip(self.RANGES, self.CLASSES, strict=True):
            self.assertEqual(primary_class, segments[tuple(interval)]["primary_class"])
        self.assertEqual("unknown", segments[(0x09B1E6, 0x09B1E8)]["primary_class"])
        self.assertIn(
            coverage_auditor.M4A_INITIALIZER_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class Mp2kNoteAllocatorCoverageTests(unittest.TestCase):
    """Coverage contract for the accepted 562-byte MP2K note allocator."""

    BATCH = "rom-mp2k-note-allocator-v1"
    RANGES = [
        [0x09A6D8, 0x09A708],
        [0x09A708, 0x09A8FE],
        [0x09A900, 0x09A908],
        [0x09AF24, 0x09AF28],
    ]
    IDS = [
        "mp2k-channel-gain-code-09a6d8",
        "mp2k-note-allocator-code-09a708",
        "mp2k-note-allocator-literals-09a900",
        "mp2k-note-entry-pointer-09af24",
    ]
    CLASSES = [
        "armv4t_mp2k_channel_gain_thumb_code",
        "armv4t_mp2k_note_allocator_thumb_code",
        "mp2k_note_allocator_consumed_literals",
        "mp2k_initializer_consumed_thumb_pointer",
    ]
    KINDS = [
        "mp2k_channel_gain_bounded_thumb_code",
        "mp2k_note_allocator_bounded_thumb_code",
        "mp2k_note_allocator_consumed_literals",
        "mp2k_note_entry_initializer_consumed_thumb_pointer",
    ]
    MODES = ["thumb", "thumb", None, None]
    EXCLUDED = [
        [0x09A6D2, 0x09A6D8],
        [0x09A8FE, 0x09A900],
        [0x09AEF4, 0x09AF24],
        [0x09AF28, 0x09AF34],
    ]
    # 生产链里 cfg-v2 consumed literals 排在 note allocator 之后
    # （build_manifest 里 _cfg_consumed_literal_batch_claims 在
    # _mp2k_note_allocator_claims 之后），它认领了本包排除邻居
    # [0x09A6D2, 0x09A6D8) 里的 4 个字节。拿最终账本当基线重放本包
    # 生产者会撞上自己的 current-unknown 门，所以必须用链时基线：
    # 把后继批次从基线里剔掉。
    LATER_BATCHES = ("rom-cfg-v2-consumed-literals-v1",)

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in set(cls.KINDS)
            and claim.get("id") not in cls.IDS
            and claim.get("promotion_batch") not in cls.LATER_BATCHES
        ]

    def _helper(self):
        helper = getattr(coverage_auditor, "_mp2k_note_allocator_claims", None)
        self.assertIsNotNone(helper, "MP2K note-allocator coverage helper is absent")
        return helper

    def test_promotes_exact_four_ranges_from_independently_verified_artifact(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(self.MODES, [claim["mode"] for claim in claims])
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"])
            self.assertEqual(self.IDS[index], claim["artifact_range_id"])
            self.assertEqual(f"/coverage_claims/{index}", claim["evidence_selector"])
            self.assertEqual(
                "artifacts/rom-mp2k-note-allocator-v1/rom-mp2k-note-allocator.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "tools/verify_rom_mp2k_note_allocator.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(claim["non_claims"]["natural_runtime_reachability"])
            self.assertFalse(claim["non_claims"]["global_ram_writer_denominator_complete"])

    def test_preserves_all_four_excluded_neighbors_as_unknown(self):
        claims = self._helper()(ROOT, self._rom(), self._baseline())
        for start, end in self.EXCLUDED:
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )

    def test_loader_fails_closed_on_overlap_duplicate_verifier_and_identity_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-mp2k-owner",
                        "range": [0x09A6D8, 0x09A6D9],
                        "role": "primary",
                        "primary_class": "injected",
                    },
                ],
            )
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-mp2k-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_mp2k_note_allocator",
            return_value={"verified": False, "contract_ok": False},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor,
            "MP2K_NOTE_ALLOCATOR_MANIFEST_SHA256",
            "0" * 64,
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x09A6D8] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_loader_rejects_non_object_json_with_a_contract_error(self):
        report = {
            "schema": "rom-mp2k-note-allocator-verification-v1",
            "verified": True,
            "contract_ok": True,
            "artifact_status": "accepted",
            "summary": coverage_auditor.MP2K_NOTE_ALLOCATOR_EXPECTED_SUMMARY,
            "bundle_sha256": (
                coverage_auditor.MP2K_NOTE_ALLOCATOR_BINARY_SHA256
            ),
            "payload_sha256": (
                coverage_auditor.MP2K_NOTE_ALLOCATOR_PAYLOAD_SHA256
            ),
            "manifest_sha256": (
                coverage_auditor.MP2K_NOTE_ALLOCATOR_MANIFEST_SHA256
            ),
            "coverage_baseline_sha256": (
                coverage_auditor.MP2K_NOTE_ALLOCATOR_BASELINE_SHA256
            ),
            "scope": coverage_auditor.MP2K_NOTE_ALLOCATOR_SCOPE,
            "limitations": list(
                coverage_auditor.MP2K_NOTE_ALLOCATOR_LIMITATIONS
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            non_object = Path(directory) / "non-object.json"
            non_object.write_text("[]\n", encoding="utf-8")
            with (
                mock.patch(
                    "tools.audit_rom_byte_coverage.verify_rom_mp2k_note_allocator",
                    return_value=report,
                ),
                mock.patch(
                    "tools.audit_rom_byte_coverage._checked_repository_file",
                    return_value=non_object,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "JSON containers"):
                    self._helper()(ROOT, self._rom(), self._baseline())

    def test_build_manifest_integrates_after_m4a_with_summary_contract(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        initializer_call = "claims += _m4a_initializer_chain_claims(root, rom, claims)"
        allocator_call = "claims += _mp2k_note_allocator_claims(root, rom, claims)"
        self.assertIn(initializer_call, source)
        self.assertIn(allocator_call, source)
        self.assertLess(source.index(initializer_call), source.index(allocator_call))
        for key in (
            "mp2k_note_allocator_promotion_batch",
            "mp2k_note_allocator_code_bytes",
            "mp2k_note_allocator_literal_bytes",
            "mp2k_note_allocator_pointer_bytes",
            "mp2k_note_allocator_promoted_bytes",
            "mp2k_note_allocator_promotion_claim_count",
            "mp2k_note_allocator_union_range_vector_sha256",
            "mp2k_note_allocator_excluded_bytes",
            "mp2k_note_allocator_accepted_value_count",
        ):
            self.assertIn(f'"{key}"', source)

    def test_committed_coverage_preserves_exact_milestone_delta(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_124_499)
        self.assertLessEqual(summary["unknown_bytes"], 166_957)
        self.assertGreaterEqual(summary["claim_count"], 14_503)
        self.assertGreaterEqual(summary["segment_count"], 16_614)
        self.assertEqual(self.BATCH, summary["mp2k_note_allocator_promotion_batch"])
        self.assertEqual(550, summary["mp2k_note_allocator_code_bytes"])
        self.assertEqual(8, summary["mp2k_note_allocator_literal_bytes"])
        self.assertEqual(4, summary["mp2k_note_allocator_pointer_bytes"])
        self.assertEqual(562, summary["mp2k_note_allocator_promoted_bytes"])
        self.assertEqual(4, summary["mp2k_note_allocator_promotion_claim_count"])
        segments = {tuple(item["range"]): item for item in manifest["segments"]}
        for interval, primary_class in zip(self.RANGES, self.CLASSES, strict=True):
            self.assertEqual(primary_class, segments[tuple(interval)]["primary_class"])
        # 排除邻居在链时必须保持 unknown；在最终账本里，其中 4 个字节已被
        # 后继批次（cfg-v2 consumed literals）认领，所以改为逐字节检查：
        # 仍为 unknown 或归别的批次，且绝不能挂在本包名下。
        for start, end in self.EXCLUDED:
            tiles, owner = _ledger_window_tiles(manifest, start, end)
            self.assertEqual(start, tiles[0][0])
            self.assertEqual(end, tiles[-1][1])
            for begin, stop, primary_class in tiles:
                for offset in range(begin, stop):
                    owner_class, owner_batch = owner[offset]
                    self.assertEqual(owner_class, primary_class)
                    self.assertNotEqual(self.BATCH, owner_batch)
                    if owner_class == "unknown":
                        self.assertIsNone(owner_batch)
        self.assertIn(
            coverage_auditor.MP2K_NOTE_ALLOCATOR_COVERAGE_LIMITATION,
            manifest["limitations"],
        )


class Mp2kDispatcherCoverageTests(unittest.TestCase):
    """Coverage contract for the accepted 102-byte MP2K dispatcher delta."""

    BATCH = "rom-mp2k-dispatcher-v1"
    RANGES = [
        [0x09BCB4, 0x09BCE2],
        [0x09BD24, 0x09BD30],
        [0x09BDC4, 0x09BDEC],
        [0x09BDFC, 0x09BE00],
    ]
    IDS = [
        "mp2k-dispatcher-code-09bcb4",
        "mp2k-dispatcher-table-tail-09bd24",
        "mp2k-dispatcher-code-09bdc4",
        "mp2k-dispatcher-literal-09bdfc",
    ]
    CLASSES = [
        "mp2k_dispatcher_bounded_thumb_code",
        "mp2k_dispatcher_table_tail_u32_entries",
        "mp2k_dispatcher_bounded_thumb_code",
        "mp2k_dispatcher_consumed_literal_bytes",
    ]
    KINDS = list(CLASSES)
    MODES = ["thumb", None, "thumb", None]
    EXCLUDED = [
        [0x09BCE2, 0x09BCE4],
        [0x09BDFA, 0x09BDFC],
    ]
    EXISTING_OWNERS = {
        "similar-table-candidate-027-range-050": [0x09BCE4, 0x09BCE8],
        "similar-table-candidate-027-range-051": [0x09BCE8, 0x09BD24],
        "cfg-thumb-0770-09bd30": [0x09BD30, 0x09BDC4],
        "cfg-thumb-0771-09bdec": [0x09BDEC, 0x09BDFA],
        "cfg-thumb-0772-09be00": [0x09BE00, 0x09BE0C],
    }

    @staticmethod
    def _rom() -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") not in set(cls.KINDS)
            and claim.get("id") not in cls.IDS
        ]

    def _helper(self):
        helper = getattr(coverage_auditor, "_mp2k_dispatcher_claims", None)
        self.assertIsNotNone(helper, "MP2K dispatcher coverage helper is absent")
        return helper

    def test_promotes_exact_four_ranges_from_independently_verified_artifact(self):
        rom = self._rom()
        claims = self._helper()(ROOT, rom, self._baseline())
        self.assertEqual(self.IDS, [claim["id"] for claim in claims])
        self.assertEqual(self.RANGES, [claim["range"] for claim in claims])
        self.assertEqual(self.CLASSES, [claim["primary_class"] for claim in claims])
        self.assertEqual(self.KINDS, [claim["claim_kind"] for claim in claims])
        self.assertEqual(self.MODES, [claim["mode"] for claim in claims])
        for index, claim in enumerate(claims):
            start, end = claim["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(hashlib.sha256(rom[start:end]).hexdigest(), claim["bytes_sha256"])
            self.assertEqual(index, claim["artifact_range_index"])
            self.assertEqual(f"/coverage_claims/{index}", claim["evidence_selector"])
            self.assertEqual(
                "artifacts/rom-mp2k-dispatcher-v1/rom-mp2k-dispatcher.json",
                claim["evidence_path"],
            )
            self.assertEqual(
                "tools/verify_rom_mp2k_dispatcher.py",
                claim["independent_verifier_path"],
            )
            self.assertFalse(claim["non_claims"]["natural_runtime_reachability"])
            self.assertFalse(
                claim["non_claims"]["global_caller_or_code_denominator_complete"]
            )

    def test_preserves_existing_owners_and_excluded_neighbors(self):
        baseline = self._baseline()
        by_id = {claim["id"]: claim for claim in baseline}
        for claim_id, interval in self.EXISTING_OWNERS.items():
            self.assertEqual(interval, by_id[claim_id]["range"])
        claims = self._helper()(ROOT, self._rom(), baseline)
        for start, end in self.EXCLUDED:
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )
        for interval in self.EXISTING_OWNERS.values():
            start, end = interval
            self.assertFalse(
                any(
                    claim["range"][0] < end and start < claim["range"][1]
                    for claim in claims
                )
            )

    def test_loader_fails_closed_on_overlap_and_excluded_neighbor_ownership(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        for interval, label in (
            ([0x09BCB4, 0x09BCB5], "promotion"),
            ([0x09BCE2, 0x09BCE3], "excluded"),
        ):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "unknown|overlap"):
                    helper(
                        ROOT,
                        rom,
                        [
                            *baseline,
                            {
                                "id": f"injected-{label}-owner",
                                "range": interval,
                                "role": "primary",
                                "primary_class": "injected",
                            },
                        ],
                    )

    def test_loader_fails_closed_on_duplicate_verifier_identity_and_rom_drift(self):
        helper = self._helper()
        rom = self._rom()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "already present"):
            helper(
                ROOT,
                rom,
                [
                    *baseline,
                    {
                        "id": "injected-dispatcher-batch",
                        "range": [0, 1],
                        "role": "secondary",
                        "promotion_batch": self.BATCH,
                    },
                ],
            )
        with mock.patch(
            "tools.audit_rom_byte_coverage.verify_rom_mp2k_dispatcher",
            return_value={"verified": False, "contract_ok": False},
        ):
            with self.assertRaisesRegex(ValueError, "independent verification"):
                helper(ROOT, rom, baseline)
        with mock.patch.object(
            coverage_auditor,
            "MP2K_DISPATCHER_MANIFEST_SHA256",
            "0" * 64,
            create=True,
        ):
            with self.assertRaisesRegex(ValueError, "identity"):
                helper(ROOT, rom, baseline)
        tampered = bytearray(rom)
        tampered[0x09BCB4] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            helper(ROOT, bytes(tampered), baseline)

    def test_build_manifest_integrates_after_allocator_with_summary_contract(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        allocator_call = "claims += _mp2k_note_allocator_claims(root, rom, claims)"
        dispatcher_call = "claims += _mp2k_dispatcher_claims(root, rom, claims)"
        self.assertIn(allocator_call, source)
        self.assertIn(dispatcher_call, source)
        self.assertLess(source.index(allocator_call), source.index(dispatcher_call))
        for key in (
            "mp2k_dispatcher_promotion_batch",
            "mp2k_dispatcher_code_bytes",
            "mp2k_dispatcher_table_tail_bytes",
            "mp2k_dispatcher_literal_bytes",
            "mp2k_dispatcher_promoted_bytes",
            "mp2k_dispatcher_promotion_claim_count",
            "mp2k_dispatcher_union_range_vector_sha256",
            "mp2k_dispatcher_excluded_bytes",
            "mp2k_dispatcher_accepted_value_count",
            "mp2k_dispatcher_existing_owner_provenance_bytes",
        ):
            self.assertIn(f'"{key}"', source)

    def test_committed_coverage_has_exact_post_state(self):
        manifest = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_126_383)
        self.assertLessEqual(summary["unknown_bytes"], 165_073)
        self.assertGreaterEqual(summary["claim_count"], 14_552)
        self.assertGreaterEqual(summary["segment_count"], 16_665)
        self.assertEqual(self.BATCH, summary["mp2k_dispatcher_promotion_batch"])
        self.assertEqual(86, summary["mp2k_dispatcher_code_bytes"])
        self.assertEqual(12, summary["mp2k_dispatcher_table_tail_bytes"])
        self.assertEqual(4, summary["mp2k_dispatcher_literal_bytes"])
        self.assertEqual(102, summary["mp2k_dispatcher_promoted_bytes"])
        self.assertEqual(4, summary["mp2k_dispatcher_promotion_claim_count"])
        self.assertEqual(4, summary["mp2k_dispatcher_excluded_bytes"])
        self.assertEqual(18, summary["mp2k_dispatcher_accepted_value_count"])
        self.assertEqual(238, summary["mp2k_dispatcher_existing_owner_provenance_bytes"])
        segments = {tuple(item["range"]): item for item in manifest["segments"]}
        for interval, primary_class in zip(self.RANGES, self.CLASSES, strict=True):
            self.assertEqual(primary_class, segments[tuple(interval)]["primary_class"])
        for interval in self.EXCLUDED:
            self.assertEqual("unknown", segments[tuple(interval)]["primary_class"])
        self.assertEqual(
            coverage_auditor.MP2K_DISPATCHER_COVERAGE_LIMITATION,
            manifest["limitations"][-1],
        )


class CfgProvenRootsV14CoverageTests(unittest.TestCase):
    BATCH = "cfg-proven-roots-v14"
    CODE_KIND = "cfg_proven_roots_v14_reachable_instruction_bytes"
    LITERAL_KIND = "cfg_proven_roots_v14_consumed_literal_bytes"
    CODE_CLASS = "armv4t_cfg_proven_roots_v14_reachable_thumb_code"
    LITERAL_CLASS = "armv4t_cfg_proven_roots_v14_consumed_literal"
    CODE_RANGES = [[0x0624C0, 0x062500], [0x062510, 0x062548]]
    LITERAL_RANGES = [[0x062500, 0x062510], [0x062548, 0x062560]]

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") not in {self.CODE_KIND, self.LITERAL_KIND}
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return coverage_auditor._cfg_proven_roots_v14_claims(
            ROOT,
            (ROOT / "rom/base.gba").read_bytes(),
            self._baseline() if baseline is None else baseline,
        )

    def test_promotes_exact_two_code_and_two_literal_ranges(self) -> None:
        claims = self._claims()
        code = [claim for claim in claims if claim["claim_kind"] == self.CODE_KIND]
        literals = [
            claim for claim in claims if claim["claim_kind"] == self.LITERAL_KIND
        ]
        self.assertEqual(4, len(claims))
        self.assertEqual(self.CODE_RANGES, [claim["range"] for claim in code])
        self.assertEqual(self.LITERAL_RANGES, [claim["range"] for claim in literals])
        self.assertEqual(120, sum(end - start for start, end in self.CODE_RANGES))
        self.assertEqual(40, sum(end - start for start, end in self.LITERAL_RANGES))
        self.assertTrue(
            all(
                claim["primary_class"] == self.CODE_CLASS
                and claim["mode"] == "thumb"
                for claim in code
            )
        )
        self.assertTrue(
            all(claim["primary_class"] == self.LITERAL_CLASS for claim in literals)
        )
        self.assertTrue(
            all(
                claim["role"] == "primary"
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["promotion_batch"] == self.BATCH
                and claim["independent_verifier_path"]
                == "tools/verify_rom_cfg_proven_roots_v14_bundle.py"
                for claim in claims
            )
        )
        segments = coverage_auditor.atomize_claims(
            6_291_456, [*self._baseline(), *claims]
        )
        promoted = [
            segment
            for segment in segments
            if 0x0624C0 <= segment["range"][0]
            and segment["range"][1] <= 0x062560
        ]
        self.assertEqual(
            [*self.CODE_RANGES[:1], *self.LITERAL_RANGES[:1], *self.CODE_RANGES[1:], *self.LITERAL_RANGES[1:]],
            [segment["range"] for segment in promoted],
        )

    def test_binds_accepted_artifact_legacy_and_bundle_identities(self) -> None:
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v14"
        manifest = artifact / "manifest.json"
        payload = artifact / "rom-cfg-proven-roots-v14.json"
        legacy = ROOT / "tools/verify_rom_cfg_proven_roots_v14.py"
        bundle = ROOT / "tools/verify_rom_cfg_proven_roots_v14_bundle.py"
        self.assertEqual(
            hashlib.sha256(manifest.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V14_MANIFEST_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(payload.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V14_PAYLOAD_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(legacy.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V14_VERIFIER_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(bundle.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V14_BUNDLE_VERIFIER_SHA256,
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V14_BUNDLE_EXPECTED_REPORT,
            coverage_auditor._run_cfg_proven_roots_v14_bundle_verifier(
                ROOT, bundle.read_bytes(), bundle
            ),
        )

    def test_rejects_known_overlap_duplicate_batch_and_identity_drift(self) -> None:
        baseline = self._baseline()
        known = {
            "id": "synthetic-v14-known-overlap",
            "range": [0x0624C0, 0x0624C1],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, known])
        duplicate = {
            "id": "synthetic-v14-duplicate-batch",
            "range": self.CODE_RANGES[0],
            "role": "primary",
            "primary_class": "synthetic_duplicate_batch",
            "claim_kind": "synthetic_duplicate_batch",
            "promotion_batch": self.BATCH,
        }
        with self.assertRaisesRegex(ValueError, "pre-v14|already"):
            self._claims([*baseline, duplicate])
        for constant in (
            "CFG_PROVEN_ROOTS_V14_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_V14_PAYLOAD_SHA256",
            "CFG_PROVEN_ROOTS_V14_VERIFIER_SHA256",
            "CFG_PROVEN_ROOTS_V14_BUNDLE_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()

    def test_current_manifest_retains_exact_v14_delta(self) -> None:
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _cfg_proven_roots_v14_claims(root, rom, claims)", source
        )
        for key in (
            "cfg_proven_roots_v14_extension_code_bytes",
            "cfg_proven_roots_v14_extension_code_claim_count",
            "cfg_proven_roots_v14_consumed_literal_bytes",
            "cfg_proven_roots_v14_consumed_literal_claim_count",
            "cfg_proven_roots_v14_promotion_bytes",
            "cfg_proven_roots_v14_promotion_claim_count",
        ):
            self.assertIn(f'"{key}"', source)
        manifest = coverage_auditor.build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_127_495)
        self.assertLessEqual(summary["unknown_bytes"], 163_961)
        self.assertGreaterEqual(summary["claim_count"], 14_624)
        self.assertGreaterEqual(summary["segment_count"], 16_693)
        self.assertEqual(120, summary["cfg_proven_roots_v14_extension_code_bytes"])
        self.assertEqual(2, summary["cfg_proven_roots_v14_extension_code_claim_count"])
        self.assertEqual(40, summary["cfg_proven_roots_v14_consumed_literal_bytes"])
        self.assertEqual(2, summary["cfg_proven_roots_v14_consumed_literal_claim_count"])
        self.assertEqual(160, summary["cfg_proven_roots_v14_promotion_bytes"])
        self.assertEqual(4, summary["cfg_proven_roots_v14_promotion_claim_count"])

    def test_global_cfg_totals_use_the_complete_bounded_code_kind_denominator(
        self,
    ) -> None:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        aggregate = coverage_auditor._cfg_code_aggregate(coverage["claims"])
        self.assertEqual(aggregate["cfg_reachable_arm_code_bytes"], 956)
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 165_572)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 166_560)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 3_969)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 45)
        for key, expected in aggregate.items():
            self.assertEqual(expected, coverage["summary"][key])

    def test_global_cfg_totals_fail_closed_on_future_code_and_producer_kinds(
        self,
    ) -> None:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        synthetic_future_kinds = (
            {
                "id": "synthetic-unregistered-bounded-thumb-code-kind",
                "range": [0x062560, 0x062562],
                "role": "primary",
                "primary_class": "synthetic_future_bounded_thumb_code",
                "claim_kind": "synthetic_future_bounded_thumb_code",
                "mode": "thumb",
            },
            {
                "id": "synthetic-unregistered-bounded-arm-code-kind",
                "range": [0x062560, 0x062564],
                "role": "primary",
                "primary_class": "synthetic_future_bounded_arm_code",
                "claim_kind": "synthetic_future_bounded_arm_code",
                "mode": "arm",
            },
            {
                "id": "synthetic-unregistered-direct-thumb-bl-producer",
                "range": [0x062560, 0x062564],
                "role": "primary",
                "primary_class": "thumb_bl_direct_call_producer",
                "claim_kind": "synthetic_future_direct_thumb_bl_producer",
                "mode": "thumb",
            },
        )
        for synthetic in synthetic_future_kinds:
            with self.subTest(claim_kind=synthetic["claim_kind"]):
                with self.assertRaisesRegex(
                    ValueError, "(?:code|producer) kind denominator changed"
                ):
                    coverage_auditor._cfg_code_aggregate(
                        [*coverage["claims"], synthetic]
                    )


class CfgProvenRootsV15CoverageTests(unittest.TestCase):
    BATCH = "cfg-proven-roots-v15"
    CODE_KIND = "cfg_proven_roots_v15_reachable_instruction_bytes"
    LITERAL_KIND = "cfg_proven_roots_v15_consumed_literal_bytes"
    CODE_CLASS = "armv4t_cfg_proven_roots_v15_reachable_thumb_code"
    LITERAL_CLASS = "armv4t_cfg_proven_roots_v15_consumed_literal"
    CODE_RANGES = [
        [0x0611F4, 0x06123A],
        [0x061250, 0x061276],
        [0x0618FC, 0x061920],
        [0x061924, 0x061936],
        [0x08B6F0, 0x08B79A],
        [0x09A3E0, 0x09A422],
    ]
    LITERAL_RANGES = [
        [0x06123C, 0x061250],
        [0x061278, 0x06128C],
        [0x061920, 0x061924],
        [0x09A424, 0x09A42C],
    ]
    HOLES = [
        [0x06123A, 0x06123C],
        [0x061276, 0x061278],
        [0x06128C, 0x0612BC],
        [0x061936, 0x061A80],
        [0x08B79A, 0x08B79C],
        [0x09A422, 0x09A424],
    ]
    REJECTED_RANGE = [0x09C0F4, 0x09C110]

    def _baseline(self) -> list[dict]:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != self.BATCH
            and claim.get("claim_kind") not in {self.CODE_KIND, self.LITERAL_KIND}
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return coverage_auditor._cfg_proven_roots_v15_claims(
            ROOT,
            (ROOT / "rom/base.gba").read_bytes(),
            self._baseline() if baseline is None else baseline,
        )

    def test_promotes_exact_semantic_ranges_and_preserves_holes_and_rejection(
        self,
    ) -> None:
        baseline = self._baseline()
        claims = self._claims(baseline)
        code = [claim for claim in claims if claim["claim_kind"] == self.CODE_KIND]
        literals = [
            claim for claim in claims if claim["claim_kind"] == self.LITERAL_KIND
        ]
        self.assertEqual(10, len(claims))
        self.assertEqual(self.CODE_RANGES, [claim["range"] for claim in code])
        self.assertEqual(
            self.LITERAL_RANGES, [claim["range"] for claim in literals]
        )
        self.assertEqual(398, sum(end - start for start, end in self.CODE_RANGES))
        self.assertEqual(
            52, sum(end - start for start, end in self.LITERAL_RANGES)
        )
        self.assertTrue(
            all(
                claim["role"] == "primary"
                and claim["promoted_from_primary_class"] == "unknown"
                and claim["promotion_batch"] == self.BATCH
                and claim["evidence_path"]
                == "artifacts/rom-cfg-proven-roots-v15/rom-cfg-proven-roots-v15.json"
                and claim["promotion_manifest_path"]
                == "artifacts/rom-cfg-proven-roots-v15/manifest.json"
                and claim["independent_verifier_path"]
                == "tools/verify_rom_cfg_proven_roots_v15_bundle.py"
                for claim in claims
            )
        )
        self.assertTrue(
            all(
                claim["primary_class"] == self.CODE_CLASS
                and claim["mode"] == "thumb"
                for claim in code
            )
        )
        self.assertTrue(
            all(claim["primary_class"] == self.LITERAL_CLASS for claim in literals)
        )
        selectors = {tuple(claim["range"]): claim["evidence_selector"] for claim in claims}
        self.assertEqual(
            {
                (0x0611F4, 0x06123A): "/targets/1/code_ranges/0",
                (0x06123C, 0x061250): "/targets/1/literal_projection/literal_only_ranges/0",
                (0x061250, 0x061276): "/targets/1/code_ranges/1",
                (0x061278, 0x06128C): "/targets/1/literal_projection/literal_only_ranges/1",
                (0x0618FC, 0x061920): "/targets/2/code_ranges/0",
                (0x061920, 0x061924): "/targets/2/literal_projection/literal_only_ranges/0",
                (0x061924, 0x061936): "/targets/2/code_ranges/1",
                (0x08B6F0, 0x08B79A): "/targets/3/code_ranges/0",
                (0x09A3E0, 0x09A422): "/targets/0/code_ranges/0",
                (0x09A424, 0x09A42C): "/targets/0/literal_projection/literal_only_ranges/0",
            },
            selectors,
        )
        segments = coverage_auditor.atomize_claims(
            6_291_456, [*baseline, *claims]
        )
        for start, end in [*self.HOLES, self.REJECTED_RANGE]:
            with self.subTest(range=[start, end]):
                # 空洞与被拒范围在链时必须保持 unknown；最终账本里 v16 批次
                # 已合法认领其中一部分（v15 空洞正是 v16 的目标区），所以
                # 改为逐字节检查：仍为 unknown 或归后继批次，且绝不能挂在
                # 本包（v15）名下。
                tiles, owner = _window_tiles([*baseline, *claims], segments, start, end)
                self.assertEqual(start, tiles[0][0])
                self.assertEqual(end, tiles[-1][1])
                for begin, stop, primary_class in tiles:
                    for offset in range(begin, stop):
                        owner_class, owner_batch = owner[offset]
                        self.assertEqual(owner_class, primary_class)
                        self.assertNotEqual(self.BATCH, owner_batch)
                self.assertFalse(
                    any(
                        claim["range"][0] < end and start < claim["range"][1]
                        for claim in claims
                    )
                )
        aggregate = coverage_auditor._cfg_code_aggregate([*baseline, *claims])
        self.assertEqual(aggregate["cfg_reachable_arm_code_bytes"], 956)
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 148_778)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 149_766)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 3_835)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 33)

    def test_binds_canonical_artifact_legacy_and_bundle_identities(self) -> None:
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v15"
        manifest = artifact / "manifest.json"
        payload = artifact / "rom-cfg-proven-roots-v15.json"
        legacy = ROOT / "tools/verify_rom_cfg_proven_roots_v15.py"
        bundle = ROOT / "tools/verify_rom_cfg_proven_roots_v15_bundle.py"
        self.assertEqual(
            hashlib.sha256(manifest.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V15_MANIFEST_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(payload.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V15_PAYLOAD_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(legacy.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V15_VERIFIER_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(bundle.read_bytes()).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V15_BUNDLE_VERIFIER_SHA256,
        )
        self.assertEqual(
            coverage_auditor.CFG_PROVEN_ROOTS_V15_BUNDLE_EXPECTED_REPORT,
            coverage_auditor._run_cfg_proven_roots_v15_bundle_verifier(
                ROOT, bundle.read_bytes(), bundle
            ),
        )

    def test_v15_isolated_bundle_subprocess_scrubs_runtime_path_overrides(
        self,
    ) -> None:
        completed = mock.Mock(
            returncode=0,
            stdout=b'{"verified": true}',
            stderr=b"",
        )
        overrides = {
            "PYTHONPATH": "/synthetic/pythonpath",
            "PYTHONHOME": "/synthetic/pythonhome",
            "LIBCAPSTONE_PATH": "/synthetic/libcapstone",
        }
        with mock.patch.dict(os.environ, overrides), mock.patch(
            "tools.audit_rom_byte_coverage.subprocess.run",
            return_value=completed,
        ) as run:
            report = coverage_auditor._run_cfg_proven_roots_v15_bundle_verifier(
                ROOT,
                b"synthetic wrapper source",
                ROOT / "tools/verify_rom_cfg_proven_roots_v15_bundle.py",
            )

        environment = run.call_args.kwargs["env"]
        for name in overrides:
            self.assertNotIn(name, environment)
        self.assertTrue(report["verified"])

    def test_rejects_known_overlap_duplicate_identity_and_report_drift(self) -> None:
        baseline = self._baseline()
        known = {
            "id": "synthetic-v15-known-overlap",
            "range": [0x0611F4, 0x0611F5],
            "role": "primary",
            "primary_class": "synthetic_current_known",
            "claim_kind": "synthetic_current_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, known])
        for duplicate in (
            {
                "id": "synthetic-v15-duplicate-batch",
                "range": self.CODE_RANGES[0],
                "role": "primary",
                "primary_class": "synthetic_duplicate_batch",
                "claim_kind": "synthetic_duplicate_batch",
                "promotion_batch": self.BATCH,
            },
            {
                "id": "synthetic-v15-duplicate-kind",
                "range": self.CODE_RANGES[0],
                "role": "primary",
                "primary_class": self.CODE_CLASS,
                "claim_kind": self.CODE_KIND,
            },
        ):
            with self.subTest(id=duplicate["id"]), self.assertRaisesRegex(
                ValueError, "pre-v15|already"
            ):
                self._claims([*baseline, duplicate])
        for constant in (
            "CFG_PROVEN_ROOTS_V15_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_V15_PAYLOAD_SHA256",
            "CFG_PROVEN_ROOTS_V15_VERIFIER_SHA256",
            "CFG_PROVEN_ROOTS_V15_BUNDLE_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()
        drifted = copy.deepcopy(
            coverage_auditor.CFG_PROVEN_ROOTS_V15_BUNDLE_EXPECTED_REPORT
        )
        drifted["verified"] = False
        with mock.patch.object(
            coverage_auditor,
            "CFG_PROVEN_ROOTS_V15_BUNDLE_EXPECTED_REPORT",
            drifted,
        ), self.assertRaisesRegex(ValueError, "independent verification"):
            self._claims()

    def test_build_manifest_exposes_exact_post_v15_delta(self) -> None:
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _cfg_proven_roots_v15_claims(root, rom, claims)", source
        )
        for key in (
            "cfg_proven_roots_v15_extension_code_bytes",
            "cfg_proven_roots_v15_extension_code_claim_count",
            "cfg_proven_roots_v15_consumed_literal_bytes",
            "cfg_proven_roots_v15_consumed_literal_claim_count",
            "cfg_proven_roots_v15_promotion_bytes",
            "cfg_proven_roots_v15_promotion_claim_count",
            "cfg_proven_roots_v15_preserved_unknown_hole_bytes",
            "cfg_proven_roots_v15_rejected_root_count",
        ):
            self.assertIn(f'"{key}"', source)
        manifest = coverage_auditor.build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_127_495)
        self.assertLessEqual(summary["unknown_bytes"], 163_961)
        self.assertGreaterEqual(summary["claim_count"], 14_624)
        self.assertGreaterEqual(summary["segment_count"], 16_693)
        self.assertEqual(398, summary["cfg_proven_roots_v15_extension_code_bytes"])
        self.assertEqual(
            6, summary["cfg_proven_roots_v15_extension_code_claim_count"]
        )
        self.assertEqual(
            52, summary["cfg_proven_roots_v15_consumed_literal_bytes"]
        )
        self.assertEqual(
            4, summary["cfg_proven_roots_v15_consumed_literal_claim_count"]
        )
        self.assertEqual(450, summary["cfg_proven_roots_v15_promotion_bytes"])
        self.assertEqual(10, summary["cfg_proven_roots_v15_promotion_claim_count"])
        self.assertEqual(
            386, summary["cfg_proven_roots_v15_preserved_unknown_hole_bytes"]
        )
        self.assertEqual(1, summary["cfg_proven_roots_v15_rejected_root_count"])
        self.assertGreaterEqual(summary["cfg_reachable_thumb_code_bytes"], 148_778)
        self.assertGreaterEqual(summary["cfg_promoted_unknown_bytes"], 149_766)
        self.assertGreaterEqual(summary["cfg_primary_claim_count"], 3_835)
        self.assertGreaterEqual(summary["cfg_code_claim_kind_count"], 33)
        self.assertEqual(
            _expected_cfg_registry_sha256(manifest["claims"]),
            summary["cfg_code_claim_kind_denominator_sha256"],
        )


class MenuPortraitLz77PaletteAlignmentGapCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen 52 LZ77-to-palette short gaps."""

    BATCH = "rom-menu-portrait-lz77-palette-alignment-gaps-v1"
    PRIMARY_CLASS = "menu_portrait_lz77_palette_alignment_bytes"
    CLAIM_KIND = "menu_portrait_lz77_palette_alignment_gap_bytes"
    RANGE_VECTOR_SHA256 = (
        "e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7"
    )
    BOUNDARY_VECTOR_SHA256 = (
        "13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb"
    )
    PACKED_BYTES_SHA256 = (
        "f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5"
    )
    CLAIM_DENOMINATOR_SHA256 = (
        "c49c9c26422412414154b96397c621761cdcf611e8d6ecb6fe52fd6302a70d18"
    )
    REPORT_SHA256 = (
        "e2d9a895e98c4359add5af092f26e74b0c2e6f03e8e758abefc81324302da7aa"
    )
    VERIFIER_PATH = "tools/verify_rom_menu_portrait_lz77_palette_alignment_gaps.py"
    VERIFIER_SHA256 = (
        "9bbf3532a5edde0cbf0f0d5924c037bb7df6873f6b02bd278f7215cd3b1af27d"
    )
    TEST_PATH = "tests/test_verify_rom_menu_portrait_lz77_palette_alignment_gaps.py"
    TEST_SHA256 = (
        "47d5a52c6d6e29f89d6b95e871f482cb0d152e2abb28633798122a6b60c040e7"
    )
    POINTER_MANIFEST_PATH = "artifacts/rom-pointer-lz77-inventory-v1/manifest.json"
    POINTER_MANIFEST_SHA256 = (
        "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33"
    )
    POINTER_PAYLOAD_PATH = (
        "artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"
    )
    POINTER_PAYLOAD_SHA256 = (
        "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
    )
    MENU_MANIFEST_PATH = "artifacts/rom-menu-portrait-palette-inventory-v1/manifest.json"
    MENU_MANIFEST_SHA256 = (
        "8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b"
    )
    MENU_PAYLOAD_PATH = (
        "artifacts/rom-menu-portrait-palette-inventory-v1/rom-menu-portrait-palette-inventory.json"
    )
    MENU_PAYLOAD_SHA256 = (
        "ac263fc071b6c6ad4b94b649df38560c180f2b2fd350212cc3875055146d908d"
    )
    MENU_VERIFIER_PATH = "tools/verify_rom_menu_portrait_palette_inventory.py"
    MENU_VERIFIER_SHA256 = (
        "63d60ffe786841d910b0655de31cbb4a3d52178b433fc1a40b24729f683cda46"
    )
    NON_CLAIMS = set(menu_gap_verifier.NON_CLAIMS)

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _report(cls) -> dict:
        report = menu_gap_verifier.verify_root(ROOT)
        if not report["verified"]:
            raise AssertionError(report["errors"])
        return report

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("primary_class") != cls.PRIMARY_CLASS
        ]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_menu_portrait_lz77_palette_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "menu portrait LZ77/palette gap helper is absent")
        return helper

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return self._helper()(ROOT, self._rom(), self._baseline() if baseline is None else baseline)

    def test_promotes_exact_ranges_owner_boundaries_evidence_and_nonclaims(self):
        report = self._report()
        baseline = self._baseline()
        claims = self._claims(baseline)
        self.assertEqual(52, len(claims))
        self.assertEqual(110, sum(claim["range"][1] - claim["range"][0] for claim in claims))
        self.assertEqual([row["id"] for row in report["rows"]], [claim["id"] for claim in claims])
        self.assertEqual([row["range"] for row in report["rows"]], [claim["range"] for claim in claims])

        denominator = hashlib.sha256(
            json.dumps(
                [
                    {
                        key: claim[key]
                        for key in (
                            "id", "range", "resource_id", "primary_class",
                            "claim_kind", "bytes_sha256", "previous_owner_id",
                            "next_owner_id", "evidence_selector",
                        )
                    }
                    for claim in claims
                ],
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
        ).hexdigest()
        self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, denominator)

        for index, (row, claim) in enumerate(zip(report["rows"], claims, strict=True)):
            start, end = row["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(row["resource_id"], claim["resource_id"])
            self.assertEqual(row["bytes_sha256"], claim["bytes_sha256"])
            self.assertEqual([0x08000000 + start, 0x08000000 + end], claim["gba_range"])
            self.assertEqual(self.RANGE_VECTOR_SHA256, claim["range_vector_sha256"])
            self.assertEqual(self.BOUNDARY_VECTOR_SHA256, claim["boundary_vector_sha256"])
            self.assertEqual(self.PACKED_BYTES_SHA256, claim["packed_bytes_sha256"])
            self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, claim["claim_denominator_sha256"])
            self.assertEqual([start, end], claim["range"])
            self.assertEqual(end, claim["alignment_target"])
            self.assertEqual("(start + 3) & ~3", claim["alignment_formula_expression"])
            self.assertEqual(end - start, claim["alignment_gap_bytes"])
            self.assertTrue(claim["alignment_gap_is_exact"])
            self.assertEqual(row["gfx_stream_range"], claim["previous_owner_range"])
            self.assertEqual("lz77_resource", claim["previous_owner_primary_class"])
            self.assertEqual(row["palette_range"], claim["next_owner_range"])
            self.assertEqual("menu_portrait_palette_bgr555", claim["next_owner_primary_class"])
            self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
            self.assertEqual(self.VERIFIER_SHA256, claim["independent_verifier_sha256"])
            self.assertEqual(self.REPORT_SHA256, claim["independent_verifier_report_sha256"])
            self.assertEqual(self.TEST_PATH, claim["upstream_test_path"])
            self.assertEqual(self.TEST_SHA256, claim["upstream_test_sha256"])
            self.assertEqual(f"/rows/{index}", claim["evidence_selector"])
            for flag in self.NON_CLAIMS:
                self.assertIs(claim[flag], False, (index, flag))

        segments = coverage_auditor.atomize_claims(len(self._rom()), [*baseline, *claims])
        classified = sum(
            end - start
            for segment in segments
            if segment["primary_class"] != "unknown"
            for start, end in [segment["range"]]
        )
        self.assertGreaterEqual(classified, 6_127_495)
        self.assertLessEqual(len(self._rom()) - classified, 163_961)
        self.assertGreaterEqual(len(baseline) + len(claims), 14_624)
        self.assertGreaterEqual(len(segments), 16_693)

    def test_rejects_overlap_owner_identity_source_identity_and_report_drift(self):
        report = self._report()
        baseline = self._baseline()
        first = report["rows"][0]
        overlap = {
            "id": "synthetic-menu-gap-overlap",
            "range": first["range"],
            "role": "primary",
            "primary_class": "synthetic_known",
            "claim_kind": "synthetic_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, overlap])

        duplicate = dict(overlap)
        duplicate["id"] = "synthetic-menu-gap-duplicate"
        duplicate["promotion_batch"] = self.BATCH
        with self.assertRaisesRegex(ValueError, "already|pre-menu"):
            self._claims([*baseline, duplicate])

        left = next(claim for claim in baseline if claim.get("range") == first["gfx_stream_range"])
        changed = copy.deepcopy(baseline)
        next(claim for claim in changed if claim.get("id") == left["id"])["primary_class"] = "drifted"
        with self.assertRaisesRegex(ValueError, "left owner"):
            self._claims(changed)

        right = next(claim for claim in baseline if claim.get("range") == first["palette_range"])
        changed = copy.deepcopy(baseline)
        next(claim for claim in changed if claim.get("id") == right["id"])["evidence_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "right owner"):
            self._claims(changed)

        for constant in (
            "MENU_PORTRAIT_LZ77_PALETTE_GAP_VERIFIER_SHA256",
            "MENU_PORTRAIT_LZ77_PALETTE_GAP_TEST_SHA256",
            "MENU_PORTRAIT_LZ77_PALETTE_GAP_POINTER_MANIFEST_SHA256",
            "MENU_PORTRAIT_LZ77_PALETTE_GAP_MENU_MANIFEST_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()

        drifted = copy.deepcopy(report)
        drifted["verified"] = False
        with mock.patch.object(
            coverage_auditor,
            "verify_rom_menu_portrait_lz77_palette_alignment_gaps",
            return_value=drifted,
            create=True,
        ), self.assertRaisesRegex(ValueError, "independent verification"):
            self._claims()

    def test_build_manifest_exposes_exact_post_gap_delta(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _menu_portrait_lz77_palette_alignment_gap_claims(root, rom, claims)",
            source,
        )
        for key in (
            "menu_portrait_lz77_palette_alignment_gap_bytes",
            "menu_portrait_lz77_palette_alignment_gap_claim_count",
            "menu_portrait_lz77_palette_alignment_gap_range_vector_sha256",
            "menu_portrait_lz77_palette_alignment_gap_claim_denominator_sha256",
            "menu_portrait_lz77_palette_alignment_gap_independent_verifier_report_sha256",
        ):
            self.assertIn(f'"{key}"', source)
        manifest = coverage_auditor.build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_127_495)
        self.assertLessEqual(summary["unknown_bytes"], 163_961)
        self.assertGreaterEqual(summary["claim_count"], 14_624)
        self.assertGreaterEqual(summary["segment_count"], 16_693)
        self.assertEqual(110, summary["menu_portrait_lz77_palette_alignment_gap_bytes"])
        self.assertEqual(52, summary["menu_portrait_lz77_palette_alignment_gap_claim_count"])
        self.assertEqual(
            self.CLAIM_DENOMINATOR_SHA256,
            summary["menu_portrait_lz77_palette_alignment_gap_claim_denominator_sha256"],
        )


class TileBgLz77PaletteAlignmentGapCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen 84 tile-BG LZ77/palette gaps."""

    BATCH = "rom-tile-bg-lz77-palette-alignment-gaps-v1"
    PRIMARY_CLASS = "tile_bg_lz77_palette_alignment_bytes"
    CLAIM_KIND = "tile_bg_lz77_palette_alignment_gap_bytes"
    RANGE_VECTOR_SHA256 = (
        "684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2"
    )
    BOUNDARY_VECTOR_SHA256 = (
        "b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448"
    )
    PACKED_BYTES_SHA256 = (
        "2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d"
    )
    CLAIM_DENOMINATOR_SHA256 = (
        "1a956208ab86931840693d8967455bea8612cf13ea03be7ee41d20feed80c244"
    )
    REPORT_SHA256 = (
        "4122e5404dc32e9f1f0429b06e8446d4025b01fb566eeaf1110d92cab0b9a4dc"
    )
    VERIFIER_PATH = "tools/verify_rom_tile_bg_lz77_palette_alignment_gaps.py"
    VERIFIER_SHA256 = (
        "cd4f61cb1226989c235dd710be7e37b039a6548eec6e5448b23bff97fccbc80b"
    )
    TEST_PATH = "tests/test_verify_rom_tile_bg_lz77_palette_alignment_gaps.py"
    TEST_SHA256 = (
        "781bcf76d984d2a6d210fd8c1ae2a7d4fc82e0d441115a29b7114ae775353660"
    )
    NON_CLAIMS = tuple(tile_bg_gap_verifier.NON_CLAIMS)
    NON_CLAIM_FLAGS = {
        name: f"{name}_claimed" for name in NON_CLAIMS
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _report(cls) -> dict:
        report = tile_bg_gap_verifier.verify_root(ROOT)
        if not report["verified"]:
            raise AssertionError(report["errors"])
        return report

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("primary_class") != cls.PRIMARY_CLASS
        ]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_tile_bg_lz77_palette_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "tile-BG LZ77/palette gap helper is absent")
        return helper

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return self._helper()(
            ROOT,
            self._rom(),
            self._baseline() if baseline is None else baseline,
        )

    def test_promotes_exact_ranges_owner_boundaries_evidence_and_nonclaims(self):
        report = self._report()
        baseline = self._baseline()
        claims = self._claims(baseline)
        self.assertEqual(84, len(claims))
        self.assertEqual(
            165,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(
            [row["id"] for row in report["rows"]],
            [claim["id"] for claim in claims],
        )
        self.assertEqual(
            [row["range"] for row in report["rows"]],
            [claim["range"] for claim in claims],
        )

        denominator = hashlib.sha256(
            json.dumps(
                [
                    {
                        key: claim[key]
                        for key in (
                            "id",
                            "range",
                            "primary_class",
                            "claim_kind",
                            "bytes_sha256",
                            "previous_owner_id",
                            "next_owner_id",
                            "evidence_selector",
                        )
                    }
                    for claim in claims
                ],
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
        ).hexdigest()
        self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, denominator)

        for index, (row, claim) in enumerate(
            zip(report["rows"], claims, strict=True)
        ):
            start, end = row["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(row["bytes_sha256"], claim["bytes_sha256"])
            self.assertEqual(
                [0x08000000 + start, 0x08000000 + end], claim["gba_range"]
            )
            self.assertEqual(self.RANGE_VECTOR_SHA256, claim["range_vector_sha256"])
            self.assertEqual(
                self.BOUNDARY_VECTOR_SHA256, claim["boundary_vector_sha256"]
            )
            self.assertEqual(self.PACKED_BYTES_SHA256, claim["packed_bytes_sha256"])
            self.assertEqual(
                self.CLAIM_DENOMINATOR_SHA256,
                claim["claim_denominator_sha256"],
            )
            self.assertEqual(end, claim["alignment_target"])
            self.assertEqual("(start + 3) & ~3", claim["alignment_formula_expression"])
            self.assertEqual(row["left"], claim["previous_owner_range"])
            self.assertEqual("lz77_resource", claim["previous_owner_primary_class"])
            self.assertEqual(row["right"], claim["next_owner_range"])
            self.assertEqual("palette_bgr555", claim["next_owner_primary_class"])
            self.assertEqual(
                "tile_bg_palette_source_range", claim["next_owner_claim_kind"]
            )
            self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
            self.assertEqual(
                self.VERIFIER_SHA256, claim["independent_verifier_sha256"]
            )
            self.assertEqual(
                self.REPORT_SHA256,
                claim["independent_verifier_report_sha256"],
            )
            self.assertEqual(self.TEST_PATH, claim["upstream_test_path"])
            self.assertEqual(self.TEST_SHA256, claim["upstream_test_sha256"])
            self.assertEqual(f"/rows/{index}", claim["evidence_selector"])
            self.assertEqual(list(self.NON_CLAIMS), claim["non_claims"])
            for flag in self.NON_CLAIM_FLAGS.values():
                self.assertIs(claim[flag], False, (index, flag))

        segments = coverage_auditor.atomize_claims(
            len(self._rom()), [*baseline, *claims]
        )
        classified = sum(
            end - start
            for segment in segments
            if segment["primary_class"] != "unknown"
            for start, end in [segment["range"]]
        )
        self.assertGreaterEqual(classified, 6_127_684)
        self.assertLessEqual(len(self._rom()) - classified, 163_772)
        self.assertGreaterEqual(len(baseline) + len(claims), 14_720)
        self.assertGreaterEqual(len(segments), 16_693)

    def test_rejects_overlap_owner_source_identity_and_report_drift(self):
        report = self._report()
        baseline = self._baseline()
        first = report["rows"][0]
        overlap = {
            "id": "synthetic-tile-bg-gap-overlap",
            "range": first["range"],
            "role": "primary",
            "primary_class": "synthetic_known",
            "claim_kind": "synthetic_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, overlap])

        duplicate = dict(overlap)
        duplicate["id"] = "synthetic-tile-bg-gap-duplicate"
        duplicate["promotion_batch"] = self.BATCH
        with self.assertRaisesRegex(ValueError, "already|pre-tile"):
            self._claims([*baseline, duplicate])

        left = next(
            claim for claim in baseline if claim.get("range") == first["left"]
        )
        changed = copy.deepcopy(baseline)
        next(
            claim for claim in changed if claim.get("id") == left["id"]
        )["primary_class"] = "drifted"
        with self.assertRaisesRegex(ValueError, "left owner"):
            self._claims(changed)

        right = next(
            claim for claim in baseline if claim.get("range") == first["right"]
        )
        changed = copy.deepcopy(baseline)
        next(
            claim for claim in changed if claim.get("id") == right["id"]
        )["evidence_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "right owner"):
            self._claims(changed)

        for constant in (
            "TILE_BG_LZ77_PALETTE_GAP_VERIFIER_SHA256",
            "TILE_BG_LZ77_PALETTE_GAP_TEST_SHA256",
            "TILE_BG_LZ77_PALETTE_GAP_POINTER_MANIFEST_SHA256",
            "TILE_BG_LZ77_PALETTE_GAP_TILE_MANIFEST_SHA256",
            "TILE_BG_LZ77_PALETTE_GAP_TILE_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()

        drifted = copy.deepcopy(report)
        drifted["verified"] = False
        with mock.patch.object(
            coverage_auditor,
            "verify_rom_tile_bg_lz77_palette_alignment_gaps",
            return_value=drifted,
            create=True,
        ), self.assertRaisesRegex(ValueError, "independent verification"):
            self._claims()

    def test_build_manifest_exposes_exact_post_gap_delta(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _tile_bg_lz77_palette_alignment_gap_claims(root, rom, claims)",
            source,
        )
        for key in (
            "tile_bg_lz77_palette_alignment_gap_bytes",
            "tile_bg_lz77_palette_alignment_gap_claim_count",
            "tile_bg_lz77_palette_alignment_gap_range_vector_sha256",
            "tile_bg_lz77_palette_alignment_gap_claim_denominator_sha256",
            "tile_bg_lz77_palette_alignment_gap_independent_verifier_report_sha256",
        ):
            self.assertIn(f'"{key}"', source)
        manifest = coverage_auditor.build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_127_684)
        self.assertLessEqual(summary["unknown_bytes"], 163_772)
        self.assertGreaterEqual(summary["claim_count"], 14_720)
        self.assertGreaterEqual(summary["segment_count"], 16_693)
        self.assertEqual(165, summary["tile_bg_lz77_palette_alignment_gap_bytes"])
        self.assertEqual(84, summary["tile_bg_lz77_palette_alignment_gap_claim_count"])
        self.assertEqual(
            self.CLAIM_DENOMINATOR_SHA256,
            summary["tile_bg_lz77_palette_alignment_gap_claim_denominator_sha256"],
        )


class BootThumbCodeLiteralAlignmentGapCoverageTests(unittest.TestCase):
    """Coverage contract for the frozen 12 boot code/literal gaps."""

    BATCH = "rom-boot-thumb-code-literal-alignment-gaps-v1"
    PRIMARY_CLASS = "boot_thumb_code_literal_alignment_bytes"
    CLAIM_KIND = "boot_thumb_code_literal_alignment_gap_bytes"
    RANGE_VECTOR_SHA256 = (
        "dec4177a9818ff7b3349a7c678f8e4a223f4a6e8ac254e2cd81bb4cf1362ce58"
    )
    BOUNDARY_VECTOR_SHA256 = (
        "2c1e60388f8fd7ef11118e7a61ac93fa7816aa6012e7f6e3478a45d4d080b54f"
    )
    PACKED_BYTES_SHA256 = (
        "9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0"
    )
    CLAIM_DENOMINATOR_SHA256 = (
        "1fadc38e6e829c3603f3d9213e98ed2dd33272aa729accdfd8db48b898c5a574"
    )
    REPORT_SHA256 = (
        "e486e518c7df41659b002c5d4ed7aedf58e41c68aa1883122b88caeba8347e62"
    )
    VERIFIER_PATH = "tools/verify_rom_boot_thumb_code_literal_alignment_gaps.py"
    VERIFIER_SHA256 = (
        "f3179bb3df6be2622272ebb87668cd29a3c1edf1333d282c0932e50078b64b30"
    )
    TEST_PATH = "tests/test_verify_rom_boot_thumb_code_literal_alignment_gaps.py"
    TEST_SHA256 = (
        "ceca040c11f2ad8361f157e521398d698a49f26bc74aa576f7a30e1e9c901545"
    )
    SOURCE_MANIFEST_PATH = "artifacts/rom-boot-thumb-handoff-cfg-v1/manifest.json"
    SOURCE_MANIFEST_SHA256 = (
        "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
    )
    SOURCE_PAYLOAD_PATH = (
        "artifacts/rom-boot-thumb-handoff-cfg-v1/rom-boot-thumb-handoff-cfg.json"
    )
    SOURCE_PAYLOAD_SHA256 = (
        "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"
    )
    SOURCE_VERIFIER_PATH = "tools/verify_rom_boot_thumb_handoff_cfg.py"
    SOURCE_VERIFIER_SHA256 = (
        "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39"
    )
    NON_CLAIMS = tuple(boot_code_literal_gap_verifier.NON_CLAIMS)

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _report(cls) -> dict:
        report = boot_code_literal_gap_verifier.verify_root(ROOT)
        if not report["verified"]:
            raise AssertionError(report["errors"])
        return report

    @classmethod
    def _baseline(cls) -> list[dict]:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        return [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != cls.BATCH
            and claim.get("claim_kind") != cls.CLAIM_KIND
            and claim.get("primary_class") != cls.PRIMARY_CLASS
        ]

    def _helper(self):
        helper = getattr(
            coverage_auditor,
            "_boot_thumb_code_literal_alignment_gap_claims",
            None,
        )
        self.assertIsNotNone(helper, "boot code/literal gap helper is absent")
        return helper

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        return self._helper()(
            ROOT,
            self._rom(),
            self._baseline() if baseline is None else baseline,
        )

    def test_promotes_exact_ranges_owner_boundaries_evidence_and_nonclaims(self):
        report = self._report()
        baseline = self._baseline()
        claims = self._claims(baseline)
        self.assertEqual(12, len(claims))
        self.assertEqual(
            24,
            sum(claim["range"][1] - claim["range"][0] for claim in claims),
        )
        self.assertEqual(
            [row["id"] for row in report["gaps"]],
            [claim["id"] for claim in claims],
        )
        self.assertEqual(
            [row["range"] for row in report["gaps"]],
            [claim["range"] for claim in claims],
        )
        denominator = hashlib.sha256(
            json.dumps(
                [
                    {
                        key: claim[key]
                        for key in (
                            "id",
                            "range",
                            "primary_class",
                            "claim_kind",
                            "bytes_sha256",
                            "previous_owner_id",
                            "next_owner_id",
                            "evidence_selector",
                        )
                    }
                    for claim in claims
                ],
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
        ).hexdigest()
        self.assertEqual(self.CLAIM_DENOMINATOR_SHA256, denominator)

        for index, (row, claim) in enumerate(
            zip(report["gaps"], claims, strict=True)
        ):
            start, end = row["range"]
            self.assertEqual("primary", claim["role"])
            self.assertEqual(self.PRIMARY_CLASS, claim["primary_class"])
            self.assertEqual(self.CLAIM_KIND, claim["claim_kind"])
            self.assertEqual(self.BATCH, claim["promotion_batch"])
            self.assertEqual("unknown", claim["promoted_from_primary_class"])
            self.assertTrue(claim["baseline_unknown_only"])
            self.assertEqual(row["sha256"], claim["bytes_sha256"])
            self.assertEqual(
                [0x08000000 + start, 0x08000000 + end], claim["gba_range"]
            )
            self.assertEqual(self.RANGE_VECTOR_SHA256, claim["range_vector_sha256"])
            self.assertEqual(
                self.BOUNDARY_VECTOR_SHA256, claim["boundary_vector_sha256"]
            )
            self.assertEqual(self.PACKED_BYTES_SHA256, claim["packed_bytes_sha256"])
            self.assertEqual(
                self.CLAIM_DENOMINATOR_SHA256,
                claim["claim_denominator_sha256"],
            )
            self.assertEqual(row["left"]["range"], claim["previous_owner_range"])
            self.assertEqual(
                "armv4t_boot_thumb_handoff_reachable_code",
                claim["previous_owner_primary_class"],
            )
            self.assertEqual(row["right"]["range"], claim["next_owner_range"])
            self.assertEqual(
                "armv4t_boot_thumb_handoff_consumed_literal_pool",
                claim["next_owner_primary_class"],
            )
            self.assertEqual(row["terminal"], claim["terminal"])
            self.assertEqual(self.VERIFIER_PATH, claim["independent_verifier_path"])
            self.assertEqual(
                self.VERIFIER_SHA256, claim["independent_verifier_sha256"]
            )
            self.assertEqual(
                self.REPORT_SHA256,
                claim["independent_verifier_report_sha256"],
            )
            self.assertEqual(self.TEST_PATH, claim["upstream_test_path"])
            self.assertEqual(self.TEST_SHA256, claim["upstream_test_sha256"])
            self.assertEqual(f"/gaps/{index}", claim["evidence_selector"])
            self.assertEqual(list(self.NON_CLAIMS), claim["non_claims"])
            for name in self.NON_CLAIMS:
                self.assertIs(claim[f"{name}_claimed"], False, (index, name))

        segments = coverage_auditor.atomize_claims(
            len(self._rom()), [*baseline, *claims]
        )
        classified = sum(
            end - start
            for segment in segments
            if segment["primary_class"] != "unknown"
            for start, end in [segment["range"]]
        )
        self.assertGreaterEqual(classified, 6_127_684)
        self.assertLessEqual(len(self._rom()) - classified, 163_772)
        self.assertGreaterEqual(len(baseline) + len(claims), 14_720)
        self.assertGreaterEqual(len(segments), 16_693)

    def test_rejects_overlap_owner_source_identity_and_report_drift(self):
        report = self._report()
        baseline = self._baseline()
        first = report["gaps"][0]
        overlap = {
            "id": "synthetic-boot-code-literal-gap-overlap",
            "range": first["range"],
            "role": "primary",
            "primary_class": "synthetic_known",
            "claim_kind": "synthetic_known",
        }
        with self.assertRaisesRegex(ValueError, "current unknown|overlap"):
            self._claims([*baseline, overlap])

        left = next(
            claim for claim in baseline if claim.get("range") == first["left"]["range"]
        )
        changed = copy.deepcopy(baseline)
        next(claim for claim in changed if claim.get("id") == left["id"])[
            "primary_class"
        ] = "drifted"
        with self.assertRaisesRegex(ValueError, "left owner"):
            self._claims(changed)

        right = next(
            claim for claim in baseline if claim.get("range") == first["right"]["range"]
        )
        changed = copy.deepcopy(baseline)
        next(claim for claim in changed if claim.get("id") == right["id"])[
            "evidence_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ValueError, "right owner"):
            self._claims(changed)

        for constant in (
            "BOOT_THUMB_CODE_LITERAL_GAP_VERIFIER_SHA256",
            "BOOT_THUMB_CODE_LITERAL_GAP_TEST_SHA256",
            "BOOT_THUMB_CODE_LITERAL_GAP_SOURCE_MANIFEST_SHA256",
            "BOOT_THUMB_CODE_LITERAL_GAP_SOURCE_PAYLOAD_SHA256",
            "BOOT_THUMB_CODE_LITERAL_GAP_SOURCE_VERIFIER_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(
                coverage_auditor, constant, "0" * 64, create=True
            ), self.assertRaises(ValueError):
                self._claims()

        drifted = copy.deepcopy(report)
        drifted["verified"] = False
        with mock.patch.object(
            coverage_auditor,
            "verify_rom_boot_thumb_code_literal_alignment_gaps",
            return_value=drifted,
            create=True,
        ), self.assertRaisesRegex(ValueError, "independent verification"):
            self._claims()

    def test_exact_range_secondary_evidence_does_not_replace_the_primary_owner(self):
        baseline = self._baseline()
        first = self._report()["gaps"][0]
        secondary = {
            "id": "synthetic-boot-gap-secondary-evidence",
            "range": first["left"]["range"],
            "role": "secondary",
            "claim_kind": "synthetic_consumer_window",
        }
        claims = self._claims([*baseline, secondary])
        self.assertEqual(12, len(claims))
        self.assertEqual(
            "boot-thumb-handoff-code-00-060fac",
            claims[0]["previous_owner_id"],
        )

    def test_build_manifest_promotes_frozen_boundary_owners_before_the_gaps(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        handoff_call = (
            "claims += _boot_thumb_handoff_cfg_claims(root, rom, claims)"
        )
        gap_call = (
            "claims += "
            "_boot_thumb_code_literal_alignment_gap_claims(root, rom, claims)"
        )
        self.assertIn(handoff_call, source)
        self.assertIn(gap_call, source)
        self.assertLess(
            source.index(handoff_call),
            source.index(gap_call),
            "the gap helper must receive the frozen handoff owners in its baseline",
        )

    def test_alignment_gap_is_explicitly_excluded_from_cfg_code_totals(self):
        baseline = self._baseline()
        gap_claims = self._claims(baseline)
        self.assertIn(
            self.CLAIM_KIND,
            coverage_auditor.CFG_CODE_KIND_REGISTRY["excluded_code_like"],
        )
        aggregate = coverage_auditor._cfg_code_aggregate(
            [*baseline, *gap_claims]
        )
        self.assertEqual(956, aggregate["cfg_reachable_arm_code_bytes"])
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 148_778)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 149_766)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 3_835)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 33)
        self.assertEqual(
            _expected_cfg_registry_sha256([*baseline, *gap_claims]),
            aggregate["cfg_code_claim_kind_denominator_sha256"],
        )

    def test_build_manifest_wiring_and_summary_keys_are_present(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn(
            "claims += _boot_thumb_code_literal_alignment_gap_claims(root, rom, claims)",
            source,
        )
        for key in (
            "boot_thumb_code_literal_alignment_gap_bytes",
            "boot_thumb_code_literal_alignment_gap_claim_count",
            "boot_thumb_code_literal_alignment_gap_range_vector_sha256",
            "boot_thumb_code_literal_alignment_gap_boundary_vector_sha256",
            "boot_thumb_code_literal_alignment_gap_claim_denominator_sha256",
            "boot_thumb_code_literal_alignment_gap_independent_verifier_report_sha256",
        ):
            self.assertIn(f'"{key}"', source)
        manifest = coverage_auditor.build_manifest(ROOT)
        summary = manifest["summary"]
        self.assertGreaterEqual(summary["classified_bytes"], 6_127_684)
        self.assertLessEqual(summary["unknown_bytes"], 163_772)
        self.assertGreaterEqual(summary["claim_count"], 14_720)
        self.assertGreaterEqual(summary["segment_count"], 16_693)
        self.assertEqual(24, summary["boot_thumb_code_literal_alignment_gap_bytes"])
        self.assertEqual(
            12, summary["boot_thumb_code_literal_alignment_gap_claim_count"]
        )
        self.assertEqual(
            self.CLAIM_DENOMINATOR_SHA256,
            summary[
                "boot_thumb_code_literal_alignment_gap_claim_denominator_sha256"
            ],
        )


class CfgConsumedLiteralBatchCoverageTests(unittest.TestCase):
    # 每批：(claim 数, 字节数, primary_class, claim_kind, non_claims 条数)
    # non_claims 条数是批次增量（每批自带的非声明清单长度不同），保持硬编码。
    EXPECTED = {
        "rom-cfg-v2-consumed-literals-v1": (653, 6796, "armv4t_cfg_v2_consumed_literal_word", "armv4t_cfg_v2_consumed_literal_word_bytes", 5),
        "rom-cfg-v6-consumed-literals-v1": (185, 2980, "armv4t_cfg_v6_consumed_literal_word", "armv4t_cfg_v6_consumed_literal_word_bytes", 5),
        "rom-cfg-v1-consumed-literals-v1": (108, 1396, "armv4t_cfg_v1_consumed_literal_word", "armv4t_cfg_v1_consumed_literal_word_bytes", 4),
        "rom-cfg-v3-consumed-literals-v1": (95, 1220, "armv4t_cfg_v3_consumed_literal_word", "armv4t_cfg_v3_consumed_literal_word_bytes", 5),
        "rom-cfg-proven-roots-batch-consumed-literals-v1": (116, 1256, "armv4t_cfg_proven_roots_batch_consumed_literal_word", "armv4t_cfg_proven_roots_batch_consumed_literal_word_bytes", 4),
        "rom-battle-controller-consumed-literals-v1": (46, 536, "armv4t_cfg_battle_controller_consumed_literal_word", "armv4t_cfg_battle_controller_consumed_literal_word_bytes", 5),
        "rom-cfg-v2-shadowed-consumed-literals-v1": (17, 308, "armv4t_cfg_v2_shadowed_consumed_literal_word", "armv4t_cfg_v2_shadowed_consumed_literal_word_bytes", 6),
    }

    @classmethod
    def _rom(cls) -> bytes:
        return (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def _baseline(cls) -> list[dict]:
        batches = set(cls.EXPECTED)
        return [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") not in batches
        ]

    def _claims(self, baseline: list[dict] | None = None) -> list[dict]:
        helper = getattr(coverage_auditor, "_cfg_consumed_literal_batch_claims", None)
        self.assertIsNotNone(helper, "CFG consumed-literal batch helper is absent")
        return helper(ROOT, self._rom(), self._baseline() if baseline is None else baseline)

    def test_exact_seven_packet_projection_and_evidence(self):
        baseline = self._baseline()
        claims = self._claims(baseline)
        self.assertEqual(1_220, len(claims))
        self.assertEqual(14_492, sum(c["range"][1] - c["range"][0] for c in claims))
        seen_ranges: set[tuple[int, int]] = set()
        for batch, (count, size, primary_class, claim_kind, non_claims) in self.EXPECTED.items():
            rows = [c for c in claims if c["promotion_batch"] == batch]
            self.assertEqual(count, len(rows), batch)
            self.assertEqual(size, sum(c["range"][1] - c["range"][0] for c in rows), batch)
            self.assertEqual({primary_class}, {c["primary_class"] for c in rows})
            self.assertEqual({claim_kind}, {c["claim_kind"] for c in rows})
            for row in rows:
                interval = tuple(row["range"])
                self.assertNotIn(interval, seen_ranges)
                seen_ranges.add(interval)
                self.assertEqual("primary", row["role"])
                self.assertEqual("unknown", row["promoted_from_primary_class"])
                self.assertTrue(row["baseline_unknown_only"])
                self.assertFalse(row["runtime_reachability_claimed"])
                self.assertFalse(row["loaded_value_semantics_claimed"])
                self.assertTrue(row["independent_verifier_path"].startswith("tools/verify_rom_"))
                self.assertEqual(64, len(row["independent_verifier_sha256"]))
                self.assertEqual(64, len(row["promotion_manifest_sha256"]))
                self.assertTrue(row["evidence_selector"].startswith("/promotion/range_records/"))
                self.assertEqual(non_claims, len(row["non_claims"]))
        segments = coverage_auditor.atomize_claims(len(self._rom()), [*baseline, *claims])
        classified = sum(b-a for s in segments if s["primary_class"] != "unknown" for a,b in [s["range"]])
        self.assertGreaterEqual(classified, 6_142_176)
        self.assertLessEqual(len(self._rom())-classified, 149_280)
        self.assertGreaterEqual(len(baseline)+len(claims), 15_940)
        self.assertGreaterEqual(len(segments), 17_344)

    def test_overlap_duplicate_batch_identity_and_verifier_drift_fail_closed(self):
        baseline = self._baseline()
        claims = self._claims(baseline)
        with self.assertRaisesRegex(ValueError, "current unknown|already present|overlap"):
            self._claims([*baseline, claims[0]])
        for constant in (
            "CFG_V2_CONSUMED_LITERAL_MANIFEST_SHA256",
            "CFG_V6_CONSUMED_LITERAL_PAYLOAD_SHA256",
            "CFG_V1_CONSUMED_LITERAL_VERIFIER_SHA256",
            "CFG_V1_CONSUMED_LITERAL_TEST_SHA256",
            "CFG_V3_CONSUMED_LITERAL_MANIFEST_SHA256",
            "CFG_PROVEN_ROOTS_BATCH_CONSUMED_LITERAL_PAYLOAD_SHA256",
            "BATTLE_CONTROLLER_CONSUMED_LITERAL_VERIFIER_SHA256",
            "CFG_V2_SHADOWED_CONSUMED_LITERAL_TEST_SHA256",
        ):
            with self.subTest(constant=constant), mock.patch.object(coverage_auditor, constant, "0"*64, create=True), self.assertRaises(ValueError):
                self._claims()
        with mock.patch.object(coverage_auditor, "verify_rom_cfg_v6_consumed_literals", return_value={"contract_ok": False}, create=True), self.assertRaisesRegex(ValueError, "verification"):
            self._claims()

    def test_build_manifest_wires_one_batch_after_all_source_owners(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _cfg_consumed_literal_batch_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(source.index(call), source.index("claims += _cfg_proven_roots_v15_claims(root, rom, claims)"))
        self.assertGreater(
            source.index(call),
            source.index("claims += _artifact_bound_alignment_gap_claims(root, rom, claims)"),
            "additive literal claims must not perturb intermediate unknown-hole contracts",
        )
        for key in ("cfg_consumed_literal_batch_bytes", "cfg_consumed_literal_batch_claim_count", "cfg_v2_consumed_literal_bytes", "cfg_v6_consumed_literal_bytes", "cfg_v1_consumed_literal_bytes", "cfg_v3_consumed_literal_bytes", "cfg_proven_roots_batch_consumed_literal_bytes", "battle_controller_consumed_literal_bytes", "cfg_v2_shadowed_consumed_literal_bytes"):
            self.assertIn(f'"{key}"', source)


class AcceptedConsumerCodeSlicePacketCoverageTests(unittest.TestCase):
    BATCHES = {
        "rom-profile-selector-code-slices-v1",
        "rom-chapter-selector-code-slice-v1",
        "rom-sprite-loader-tail-v1",
        "rom-battle-status-bar-caller-slice-v1",
    }

    def test_four_packet_batch_projects_exact_five_claims(self):
        helper = getattr(
            coverage_auditor, "_accepted_consumer_code_slice_packet_claims", None
        )
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") not in self.BATCHES
        ]
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(5, len(claims))
        self.assertEqual(2_120, sum(item["range"][1] - item["range"][0] for item in claims))
        self.assertEqual(
            [
                [0x07A34C, 0x07AA8C],
                [0x080B58, 0x080B7C],
                [0x08B19E, 0x08B1B6],
                [0x08D1A4, 0x08D230],
                [0x08F594, 0x08F5D4],
            ],
            sorted(item["range"] for item in claims),
        )
        self.assertEqual({"consumer_code_slice"}, {item["primary_class"] for item in claims})
        self.assertEqual(4, len({item["promotion_batch"] for item in claims}))
        self.assertEqual(
            {
                "battle-status-bar-generator-caller",
                "chapter-root-table-selector",
                "generic-sprite-loader-terminal-tail",
                "profile-line-wrapper",
                "profile-pointer-selector",
            },
            {item["id"] for item in claims},
        )

    def test_build_manifest_wires_batch_after_consumed_literals(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        earlier = "claims += _cfg_consumed_literal_batch_claims(root, rom, claims)"
        current = "claims += _accepted_consumer_code_slice_packet_claims(root, rom, claims)"
        self.assertIn(current, source)
        self.assertGreater(source.index(current), source.index(earlier))
        self.assertLess(source.index(current), source.index("claims.sort"))


class FastAuditFourPacketCoverageTests(unittest.TestCase):
    BATCHES = {
        "rom-event-handler-cfg-v1",
        "rom-sprite-component-source-v1",
        "rom-cfg-proven-roots-v16",
        "rom-cfg-proven-roots-v16-consumed-literals-v1",
    }

    def test_four_packet_projection_is_exact_and_disjoint(self):
        helper = getattr(coverage_auditor, "_fast_audit_four_packet_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") not in self.BATCHES
        ]
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(116, len(claims))
        self.assertEqual(7_140, sum(b - a for c in claims for a, b in [c["range"]]))
        self.assertEqual(self.BATCHES, {c["promotion_batch"] for c in claims})
        segments = coverage_auditor.atomize_claims(len(rom), [*baseline, *claims])
        classified = sum(b - a for s in segments if s["primary_class"] != "unknown" for a, b in [s["range"]])
        self.assertGreaterEqual(classified, 6_151_436)
        self.assertLessEqual(len(rom) - classified, 140_020)
        self.assertGreaterEqual(len(baseline) + len(claims), 16_061)
        self.assertTrue(all(c["promoted_from_primary_class"] == "unknown" for c in claims))

    def test_four_packet_batch_is_wired_last(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _fast_audit_four_packet_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(source.index(call), source.index("claims += _accepted_consumer_code_slice_packet_claims(root, rom, claims)"))

    def test_new_cfg_code_kinds_are_in_the_frozen_registry(self):
        kinds = set(coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn("event_handler_reachable_instruction_bytes", kinds)
        self.assertIn("cfg_proven_roots_v16_reachable_instruction_bytes", kinds)

    def test_batch_uses_one_immutable_baseline_replay_verifier(self):
        self.assertEqual(
            "tools/verify_rom_fast_audit_four_packet_coverage.py",
            coverage_auditor.FAST_AUDIT_REPLAY_VERIFIER.as_posix(),
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / coverage_auditor.FAST_AUDIT_REPLAY_VERIFIER).read_bytes()
            ).hexdigest(),
            coverage_auditor.FAST_AUDIT_REPLAY_VERIFIER_SHA256,
        )


class CfgProvenRootsV17CoverageTests(unittest.TestCase):
    def test_combined_packet_projects_exact_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_cfg_proven_roots_v17_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") != "rom-cfg-proven-roots-v17"
        ]
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(26, len(claims))
        self.assertEqual(2_400, sum(end - start for claim in claims for start, end in [claim["range"]]))
        self.assertEqual({"rom-cfg-proven-roots-v17"}, {claim["promotion_batch"] for claim in claims})
        segments = coverage_auditor.atomize_claims(len(rom), [*baseline, *claims])
        classified = sum(end - start for segment in segments if segment["primary_class"] != "unknown" for start, end in [segment["range"]])
        self.assertGreaterEqual(classified, 6_153_836)
        self.assertLessEqual(len(rom) - classified, 137_620)
        for gap in ([0x0919BE, 0x0919C0], [0x091B0A, 0x091B0C], [0x091C2E, 0x091C30], [0x091E5A, 0x091E5C], [0x091F2E, 0x091F30]):
            self.assertTrue(any(segment["range"] == gap and segment["primary_class"] == "unknown" for segment in segments))

    def test_combined_packet_is_wired_after_four_packet_replay(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _cfg_proven_roots_v17_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(source.index(call), source.index("claims += _fast_audit_four_packet_claims(root, rom, claims)"))


class CfgProvenRootsV18CoverageTests(unittest.TestCase):
    def test_target_local_packet_projects_exact_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_cfg_proven_roots_v18_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [claim for claim in json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())["claims"] if claim.get("promotion_batch") != "rom-cfg-proven-roots-v18"]
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(17, len(claims))
        self.assertEqual(1_482, sum(end - start for claim in claims for start, end in [claim["range"]]))
        segments = coverage_auditor.atomize_claims(len(rom), [*baseline, *claims])
        classified = sum(end - start for segment in segments if segment["primary_class"] != "unknown" for start, end in [segment["range"]])
        self.assertGreaterEqual(classified, 6_155_318)
        self.assertLessEqual(len(rom) - classified, 136_138)
        for gap in ([0x0910CE, 0x0910D0], [0x091236, 0x091238], [0x09133A, 0x09133C], [0x0914CA, 0x0914CC]):
            self.assertTrue(any(segment["range"] == gap and segment["primary_class"] == "unknown" for segment in segments))

    def test_packet_is_wired_after_v17_and_code_kind_registered(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _cfg_proven_roots_v18_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(source.index(call), source.index("claims += _cfg_proven_roots_v17_claims(root, rom, claims)"))
        self.assertIn("cfg_proven_roots_v18_reachable_instruction_bytes", coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])


class BootContinuationAndCfgV19AtomicCoverageTests(unittest.TestCase):
    def test_dependency_dag_projects_both_packets_atomically(self):
        continuation = getattr(coverage_auditor, "_boot_interwork_continuation_claims", None)
        target = getattr(coverage_auditor, "_cfg_proven_roots_v19_claims", None)
        self.assertIsNotNone(continuation)
        self.assertIsNotNone(target)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())["claims"]
            if claim.get("promotion_batch")
            not in {"rom-boot-interwork-continuation-v1", "rom-cfg-proven-roots-v19"}
        ]
        continuation_claims = continuation(ROOT, rom, baseline)
        target_claims = target(ROOT, rom, [*baseline, *continuation_claims])
        self.assertEqual(6, len(continuation_claims))
        self.assertEqual(94, sum(c["range"][1] - c["range"][0] for c in continuation_claims))
        self.assertEqual(14, len(target_claims))
        self.assertEqual(1_660, sum(c["range"][1] - c["range"][0] for c in target_claims))
        claims = [*baseline, *continuation_claims, *target_claims]
        segments = coverage_auditor.atomize_claims(len(rom), claims)
        classified = sum(end - start for row in segments if row["primary_class"] != "unknown" for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_157_072)
        self.assertLessEqual(len(rom) - classified, 134_384)
        for gap in ([0x0657CA,0x0657CC],[0x065906,0x065908],[0x06598A,0x06598C],[0x065BA2,0x065BA4],[0x065C26,0x065C28],[0x065D9A,0x065D9C]):
            self.assertTrue(any(row["range"] == gap and row["primary_class"] == "unknown" for row in segments))

    def test_dependency_order_is_last_and_code_kinds_are_registered(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        continuation = "claims += _boot_interwork_continuation_claims(root, rom, claims)"
        target = "claims += _cfg_proven_roots_v19_claims(root, rom, claims)"
        self.assertIn(continuation, source)
        self.assertIn(target, source)
        self.assertGreater(source.index(continuation), source.index("claims += _cfg_proven_roots_v18_claims(root, rom, claims)"))
        self.assertGreater(source.index(target), source.index(continuation))
        self.assertIn("boot_interwork_continuation_reachable_instruction_bytes", coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn("cfg_proven_roots_v19_reachable_instruction_bytes", coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])


class UnboundChapterScriptTailCoverageTests(unittest.TestCase):
    BATCH = "rom-chapter-script-unbound-tail-v1"

    def test_packet_projects_both_unknown_root_closures(self):
        helper = getattr(coverage_auditor, "_unbound_chapter_script_tail_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())["claims"]
            if claim.get("promotion_batch") != self.BATCH
        ]
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(3, len(claims))
        self.assertEqual(3_186, sum(c["range"][1] - c["range"][0] for c in claims))
        self.assertEqual(
            {
                "chapter_script_unbound_root_pointer_vector",
                "chapter_script_syntax_unbound",
            },
            {claim["primary_class"] for claim in claims},
        )
        self.assertTrue(all(claim["current_unknown_verified_by_auditor"] for claim in claims))
        self.assertTrue(all(claim["coverage_projection_gate"] == "current_unknown_before_projection" for claim in claims))
        self.assertTrue(all(claim["historical_baseline_observed_during_artifact_build"] is False for claim in claims))
        segments = coverage_auditor.atomize_claims(len(rom), [*baseline, *claims])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_160_258)
        self.assertLessEqual(len(rom) - classified, 131_198)
        for gap in ([0x05C5DC, 0x05C5DD], [0x05CD40, 0x05CD41]):
            self.assertTrue(
                any(
                    row["range"][0] <= gap[0]
                    and row["range"][1] >= gap[1]
                    and row["primary_class"] == "unknown"
                    for row in segments
                ),
                gap,
            )
        self.assertTrue(
            any(
                row["range"] == [0x05C5DD, 0x05C6D3]
                and row["primary_class"] == "chapter_script_record"
                for row in segments
            )
        )

    def test_packet_is_wired_after_v19_and_binds_independent_verifier(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _unbound_chapter_script_tail_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(source.index(call), source.index("claims += _cfg_proven_roots_v19_claims(root, rom, claims)"))
        verifier = ROOT / "tools/verify_rom_unbound_chapter_script_tail.py"
        self.assertEqual(
            hashlib.sha256(verifier.read_bytes()).hexdigest(),
            coverage_auditor.UNBOUND_CHAPTER_SCRIPT_TAIL_VERIFIER_SHA256,
        )

    def test_projection_rejects_ranges_that_are_not_current_unknown(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())["claims"]
            if claim.get("promotion_batch") != self.BATCH
        ]
        baseline.append(
            {
                "id": "synthetic-known-overlap",
                "range": [0x05BFDF, 0x05BFE0],
                "role": "primary",
                "primary_class": "synthetic_known",
                "claim_kind": "synthetic_known",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._unbound_chapter_script_tail_claims(ROOT, rom, baseline)


class ChapterScriptConsumerRootsCoverageTests(unittest.TestCase):
    BATCH = "rom-chapter-script-consumer-roots-v1"

    def test_packet_projects_only_the_two_consumer_bound_closures(self):
        helper = getattr(coverage_auditor, "_chapter_script_consumer_root_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())["claims"]
            if claim.get("promotion_batch") != self.BATCH
        ]
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(2, len(claims))
        self.assertEqual(16_175, sum(c["range"][1] - c["range"][0] for c in claims))
        self.assertEqual(
            {"chapter_script_syntax_consumer_bound"},
            {claim["primary_class"] for claim in claims},
        )
        self.assertTrue(all(claim["current_unknown_verified_by_auditor"] for claim in claims))
        self.assertTrue(all(claim["coverage_projection_gate"] == "current_unknown_before_projection" for claim in claims))
        self.assertTrue(all(claim["historical_baseline_observed_during_artifact_build"] is False for claim in claims))
        segments = coverage_auditor.atomize_claims(len(rom), [*baseline, *claims])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_176_433)
        self.assertLessEqual(len(rom) - classified, 115_023)
        for gap in ([0x05CD40, 0x05CD41], [0x060C70, 0x060C74]):
            self.assertTrue(
                any(
                    row["range"][0] <= gap[0]
                    and row["range"][1] >= gap[1]
                    and row["primary_class"] == "unknown"
                    for row in segments
                ),
                gap,
            )

    def test_packet_is_wired_after_unbound_tail_and_binds_final_verifier(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _chapter_script_consumer_root_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(
            source.index(call),
            source.index("claims += _unbound_chapter_script_tail_claims(root, rom, claims)"),
        )
        verifier = ROOT / "tools/verify_rom_chapter_script_consumer_roots.py"
        self.assertEqual(
            hashlib.sha256(verifier.read_bytes()).hexdigest(),
            coverage_auditor.CHAPTER_SCRIPT_CONSUMER_ROOTS_VERIFIER_SHA256,
        )

    def test_projection_rejects_a_closure_that_is_not_current_unknown(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = [
            claim
            for claim in json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())["claims"]
            if claim.get("promotion_batch") != self.BATCH
        ]
        baseline.append(
            {
                "id": "synthetic-known-overlap",
                "range": [0x05CD41, 0x05CD42],
                "role": "primary",
                "primary_class": "synthetic_known",
                "claim_kind": "synthetic_known",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._chapter_script_consumer_root_claims(ROOT, rom, baseline)


class BattleConditionResultTextCoverageTests(unittest.TestCase):
    BATCH = "rom-battle-condition-result-text-v1"

    def _baseline(self):
        return [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") != self.BATCH
        ]

    def test_packet_projects_only_renderer_consumed_records(self):
        helper = getattr(
            coverage_auditor,
            "_battle_condition_result_text_claims",
            None,
        )
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        claims = helper(ROOT, rom, self._baseline())
        self.assertEqual(219, len(claims))
        self.assertEqual(3_961, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(
            {"battle_condition_result_renderer_text"},
            {claim["primary_class"] for claim in claims},
        )
        segments = coverage_auditor.atomize_claims(
            len(rom), [*self._baseline(), *claims]
        )
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_180_394)
        self.assertLessEqual(len(rom) - classified, 111_062)
        for gap in ([0x7F2E, 0x7F36], [0x9974, 0x9980], [0x9980, 0x9986]):
            self.assertTrue(
                any(
                    row["range"][0] <= gap[0]
                    and row["range"][1] >= gap[1]
                    and row["primary_class"] == "unknown"
                    for row in segments
                ),
                gap,
            )

    def test_packet_is_wired_after_chapter_roots_and_binds_verifier(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _battle_condition_result_text_claims(root, rom, claims)"
        self.assertIn(call, source)
        self.assertGreater(
            source.index(call),
            source.index(
                "claims += _chapter_script_consumer_root_claims(root, rom, claims)"
            ),
        )
        verifier = ROOT / "tools/verify_rom_battle_condition_result_text.py"
        self.assertEqual(
            hashlib.sha256(verifier.read_bytes()).hexdigest(),
            coverage_auditor.BATTLE_CONDITION_RESULT_TEXT_VERIFIER_SHA256,
        )

    def test_projection_rejects_a_record_that_is_not_current_unknown(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        baseline.append(
            {
                "id": "synthetic-known-overlap",
                "range": [0x7F1D, 0x7F1E],
                "role": "primary",
                "primary_class": "synthetic_known",
                "claim_kind": "synthetic_known",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._battle_condition_result_text_claims(
                ROOT, rom, baseline
            )


class AlternateDialogueTableCoverageTests(unittest.TestCase):
    BATCH = "rom-alternate-dialogue-table-v1"

    def _baseline(self):
        return [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch")
            not in {self.BATCH, "rom-battle-condition-result-text-v1"}
        ]

    def test_packet_projects_table_text_and_parser_bound_zero_gaps(self):
        helper = getattr(coverage_auditor, "_alternate_dialogue_table_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        condition = coverage_auditor._battle_condition_result_text_claims(
            ROOT, rom, baseline
        )
        claims = helper(ROOT, rom, [*baseline, *condition])
        self.assertEqual(161, len(claims))
        self.assertEqual(3_200, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(
            {
                "alternate_dialogue_record_table",
                "dialogue_encoded_text",
                "dialogue_inter_record_zero_padding",
            },
            {claim["primary_class"] for claim in claims},
        )
        self.assertTrue(
            all(claim["current_unknown_verified_by_auditor"] for claim in claims)
        )
        segments = coverage_auditor.atomize_claims(
            len(rom), [*baseline, *condition, *claims]
        )
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_183_594)
        self.assertLessEqual(len(rom) - classified, 107_862)
        self.assertTrue(
            any(
                row["range"][0] <= 0x45832C
                and row["range"][1] >= 0x458794
                and row["primary_class"] == "unknown"
                for row in segments
            )
        )

    def test_packet_is_wired_after_condition_text_and_binds_verifier(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        condition = "claims += _battle_condition_result_text_claims(root, rom, claims)"
        alternate = "claims += _alternate_dialogue_table_claims(root, rom, claims)"
        self.assertIn(alternate, source)
        self.assertLess(source.index(condition), source.index(alternate))
        verifier = ROOT / "tools/verify_rom_alternate_dialogue_table.py"
        self.assertEqual(
            hashlib.sha256(verifier.read_bytes()).hexdigest(),
            coverage_auditor.ALTERNATE_DIALOGUE_TABLE_VERIFIER_SHA256,
        )

    def test_projection_rejects_overlap_or_missing_upstream_owner(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "upstream owner"):
            coverage_auditor._alternate_dialogue_table_claims(
                ROOT,
                rom,
                [
                    claim
                    for claim in baseline
                    if claim.get("id")
                    != "verified-reuse-wram-overview-entry-08f9e2"
                ],
            )
        baseline.append(
            {
                "id": "synthetic-known-overlap",
                "range": [0x459284, 0x459285],
                "role": "primary",
                "primary_class": "synthetic_known",
                "claim_kind": "synthetic_known",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._alternate_dialogue_table_claims(ROOT, rom, baseline)


class StoryStateCallbackCfgCoverageTests(unittest.TestCase):
    BATCH = "rom-story-state-callback-cfg-v1"

    def _baseline(self):
        queued = {
            self.BATCH,
            "rom-battle-condition-result-text-v1",
            "rom-alternate-dialogue-table-v1",
        }
        return [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") not in queued
        ]

    def test_packet_projects_code_and_consumed_literals_after_existing_queue(self):
        helper = getattr(coverage_auditor, "_story_state_callback_cfg_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        condition = coverage_auditor._battle_condition_result_text_claims(
            ROOT, rom, baseline
        )
        alternate = coverage_auditor._alternate_dialogue_table_claims(
            ROOT, rom, [*baseline, *condition]
        )
        claims = helper(ROOT, rom, [*baseline, *condition, *alternate])
        self.assertEqual(13, len(claims))
        self.assertEqual(702, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(
            {
                "armv4t_story_state_callback_reachable_thumb_code",
                "armv4t_story_state_callback_consumed_literal_word",
            },
            {claim["primary_class"] for claim in claims},
        )
        self.assertTrue(
            all(
                claim["mode"] == "thumb"
                for claim in claims
                if claim["claim_kind"]
                == "story_state_callback_reachable_instruction_bytes"
            )
        )
        segments = coverage_auditor.atomize_claims(
            len(rom), [*baseline, *condition, *alternate, *claims]
        )
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_184_296)
        self.assertLessEqual(len(rom) - classified, 107_160)
        for start, end in (
            (0x08F77A, 0x08F77C),
            (0x08F8EE, 0x08F8F0),
            (0x08F99A, 0x08F99C),
            (0x08FA32, 0x08FA34),
        ):
            self.assertTrue(
                any(
                    row["range"][0] <= start
                    and row["range"][1] >= end
                    and row["primary_class"] == "unknown"
                    for row in segments
                )
            )

    def test_packet_is_wired_after_alternate_and_binds_verifier(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        alternate = "claims += _alternate_dialogue_table_claims(root, rom, claims)"
        callback = "claims += _story_state_callback_cfg_claims(root, rom, claims)"
        self.assertIn(callback, source)
        self.assertLess(source.index(alternate), source.index(callback))
        verifier = ROOT / "tools/verify_rom_story_state_callback_cfg.py"
        self.assertEqual(
            hashlib.sha256(verifier.read_bytes()).hexdigest(),
            coverage_auditor.STORY_STATE_CALLBACK_CFG_VERIFIER_SHA256,
        )

    def test_projection_rejects_missing_upstream_owner_or_overlap(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        with self.assertRaisesRegex(ValueError, "upstream owner"):
            coverage_auditor._story_state_callback_cfg_claims(
                ROOT,
                rom,
                [
                    claim
                    for claim in baseline
                    if claim.get("id") != "boot-thumb-handoff-literal-01-06107c"
                ],
            )
        baseline.append(
            {
                "id": "synthetic-known-overlap",
                "range": [0x08F73C, 0x08F73D],
                "role": "primary",
                "primary_class": "synthetic_known",
                "claim_kind": "synthetic_known",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._story_state_callback_cfg_claims(ROOT, rom, baseline)


class StoryStateEntryC4ccCoverageTests(unittest.TestCase):
    BATCH = "rom-story-state-entry-c4cc-v1"

    def _baseline(self):
        queued = {
            self.BATCH,
            "rom-story-state-callback-cfg-v1",
            "rom-battle-condition-result-text-v1",
            "rom-alternate-dialogue-table-v1",
        }
        # 链时基线：生产链里 rom-text-bg-task-closure-v1 排在本包**之后**
        # （build_manifest: _story_state_entry_c4cc_claims 在 36089 行，
        # _text_bg_task_closure_claims 在 36092 行），所以它在链时看不到本包；
        # 本包在链时同样看不到 text-bg 认领的那 948 字节。
        # 拿最终账本当基线会把后继批次的字节算进来，于是
        # 「[0x08C5A8,0x08CBB4) 整窗仍为 unknown」这个**链时**不变式被打破
        # （实测：该窗口被 text-bg 切成 13 段，无单段覆盖整窗）。
        # 必须把后继批次从基线里剔掉。
        later = {
            "rom-text-bg-task-closure-v1",
        }
        return [
            claim
            for claim in json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text()
            )["claims"]
            if claim.get("promotion_batch") not in queued
            and claim.get("promotion_batch") not in later
        ]

    def _queued_claims(self, rom, baseline):
        condition = coverage_auditor._battle_condition_result_text_claims(
            ROOT, rom, baseline
        )
        alternate = coverage_auditor._alternate_dialogue_table_claims(
            ROOT, rom, [*baseline, *condition]
        )
        callback = coverage_auditor._story_state_callback_cfg_claims(
            ROOT, rom, [*baseline, *condition, *alternate]
        )
        return condition, alternate, callback

    def test_packet_projects_exact_target_local_code_and_literals(self):
        helper = getattr(coverage_auditor, "_story_state_entry_c4cc_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        condition, alternate, callback = self._queued_claims(rom, baseline)
        prior = [*baseline, *condition, *alternate, *callback]
        claims = helper(ROOT, rom, prior)
        self.assertEqual(2, len(claims))
        self.assertEqual(220, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(
            {
                "armv4t_story_state_entry_reachable_thumb_code",
                "armv4t_story_state_entry_consumed_literal_word",
            },
            {claim["primary_class"] for claim in claims},
        )
        self.assertEqual(
            ["thumb"],
            [
                claim["mode"]
                for claim in claims
                if claim["claim_kind"]
                == "story_state_entry_reachable_instruction_bytes"
            ],
        )
        segments = coverage_auditor.atomize_claims(len(rom), [*prior, *claims])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_184_516)
        self.assertLessEqual(len(rom) - classified, 106_940)
        aggregate = coverage_auditor._cfg_code_aggregate([*prior, *claims])
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 159_480)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 160_468)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 3_917)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 41)
        self.assertTrue(
            any(
                row["range"][0] <= 0x08C5A8
                and row["range"][1] >= 0x08CBB4
                and row["primary_class"] == "unknown"
                for row in segments
            )
        )

    def test_packet_is_wired_after_callback_and_binds_verifier(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        callback = "claims += _story_state_callback_cfg_claims(root, rom, claims)"
        entry = "claims += _story_state_entry_c4cc_claims(root, rom, claims)"
        self.assertIn(entry, source)
        self.assertLess(source.index(callback), source.index(entry))
        verifier = ROOT / "tools/verify_rom_story_state_entry_c4cc.py"
        self.assertEqual(
            hashlib.sha256(verifier.read_bytes()).hexdigest(),
            coverage_auditor.STORY_STATE_ENTRY_C4CC_VERIFIER_SHA256,
        )

    def test_projection_rejects_missing_callback_owner_or_overlap(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        baseline = self._baseline()
        condition, alternate, callback = self._queued_claims(rom, baseline)
        prior = [*baseline, *condition, *alternate, *callback]
        with self.assertRaisesRegex(ValueError, "upstream owner"):
            coverage_auditor._story_state_entry_c4cc_claims(
                ROOT,
                rom,
                [
                    claim
                    for claim in prior
                    if claim.get("id")
                    != "story-callback-reachable_thumb_code-08-08fa08"
                ],
            )
        prior.append(
            {
                "id": "synthetic-known-overlap",
                "range": [0x08C4CC, 0x08C4CD],
                "role": "primary",
                "primary_class": "synthetic_known",
                "claim_kind": "synthetic_known",
            }
        )
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._story_state_entry_c4cc_claims(ROOT, rom, prior)

    def test_cfg_aggregate_registers_both_new_instruction_kinds(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        additions = [
            {
                "id": "synthetic-story-callback-code",
                "range": [0, 678],
                "role": "primary",
                "primary_class": "armv4t_story_state_callback_reachable_thumb_code",
                "claim_kind": "story_state_callback_reachable_instruction_bytes",
                "mode": "thumb",
            },
            {
                "id": "synthetic-story-entry-code",
                "range": [0, 184],
                "role": "primary",
                "primary_class": "armv4t_story_state_entry_reachable_thumb_code",
                "claim_kind": "story_state_entry_reachable_instruction_bytes",
                "mode": "thumb",
            },
        ]
        aggregate = coverage_auditor._cfg_code_aggregate(
            [*coverage["claims"], *additions]
        )
        self.assertEqual(
            coverage["summary"]["cfg_reachable_thumb_code_bytes"] + 862,
            aggregate["cfg_reachable_thumb_code_bytes"],
        )
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 41)


class TextBgLoopContinuationQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection only; this packet must not force a full rebuild."""

    def test_projects_exact_two_claims_and_54_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_text_bg_loop_continuation_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        baseline = _reproject_chain_baseline(coverage, 1)
        claims = helper(ROOT, rom, baseline)
        self.assertEqual(2, len(claims))
        self.assertEqual(54, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(
            {
                "armv4t_text_bg_loop_continuation_reachable_thumb_code",
                "armv4t_text_bg_loop_continuation_consumed_literal_word",
            },
            {row["primary_class"] for row in claims},
        )
        self.assertEqual(["thumb"], [row["mode"] for row in claims if row["claim_kind"] == "text_bg_loop_continuation_reachable_instruction_bytes"])
        segments = coverage_auditor.atomize_claims(len(rom), [*baseline, *claims])
        classified = sum(end - start for row in segments if row["primary_class"] != "unknown" for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_184_570)
        self.assertLessEqual(len(rom) - classified, 106_886)

    def test_packet_wiring_and_verifier_identity_are_frozen(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        call = "claims += _text_bg_loop_continuation_claims(root, rom, claims)"
        self.assertIn(call, source)
        verifier_path = ROOT / "tools/verify_rom_text_bg_loop_continuation.py"
        self.assertEqual(
            hashlib.sha256(verifier_path.read_bytes()).hexdigest(),
            coverage_auditor.TEXT_BG_LOOP_CONTINUATION_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        without_boundary = [
            claim
            for claim in _reproject_chain_baseline(coverage, 1)
            if claim.get("id") != "verified-reuse-wram-selection-bg-setup-08acf2"
        ]
        with self.assertRaisesRegex(ValueError, "boundary owner"):
            coverage_auditor._text_bg_loop_continuation_claims(
                ROOT, rom, without_boundary
            )
        prior = [*_reproject_chain_baseline(coverage, 1), {"id": "synthetic-overlap", "range": [0x08ACC8, 0x08ACC9], "role": "primary", "primary_class": "synthetic", "claim_kind": "synthetic"}]
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._text_bg_loop_continuation_claims(ROOT, rom, prior)

    def test_cfg_aggregate_registers_new_code_kind_and_both_claims(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        baseline = _reproject_chain_baseline(coverage, 1)
        claims = coverage_auditor._text_bg_loop_continuation_claims(
            ROOT, rom, baseline
        )
        aggregate = coverage_auditor._cfg_code_aggregate(
            [*baseline, *claims]
        )
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 159_522)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 160_510)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 3_918)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 42)


class BootCopySourcesQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the fixed boot ROM copy-source packet."""

    def test_projects_one_claim_and_combined_674_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_boot_copy_source_claims", None)
        self.assertIsNotNone(helper)
        rom = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        baseline = _reproject_chain_baseline(coverage, 2)
        first = coverage_auditor._text_bg_loop_continuation_claims(
            ROOT, rom, baseline
        )
        claims = helper(ROOT, rom, [*baseline, *first])
        self.assertEqual(1, len(claims))
        self.assertEqual([0x4C8, 0x734], claims[0]["range"])
        self.assertEqual("boot_fixed_rom_copy_source_bytes", claims[0]["primary_class"])
        self.assertEqual("fixed_rom_copy_source_bytes", claims[0]["claim_kind"])

        def _classified(rows: list[dict]) -> int:
            return sum(
                end - start
                for row in rows
                if row["primary_class"] != "unknown"
                for start, end in [row["range"]]
            )

        before = _classified(
            coverage_auditor.atomize_claims(len(rom), baseline)
        )
        segments = coverage_auditor.atomize_claims(
            len(rom), [*baseline, *first, *claims]
        )
        classified = _classified(segments)
        # 批次增量（两族合计）：text-BG loop continuation 54 B + boot copy source 620 B
        self.assertEqual(674, classified - before)
        # 全局量：随账本推进单调变化
        self.assertGreaterEqual(classified, 6_185_190)
        self.assertLessEqual(len(rom) - classified, 106_266)

    def test_packet_wiring_and_frozen_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        self.assertIn("claims += _boot_copy_source_claims(root, rom, claims)", source)
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_boot_copy_sources.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.BOOT_COPY_SOURCES_VERIFIER_SHA256,
        )

    def test_projection_rejects_existing_primary_overlap(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        prior = [
            *_reproject_chain_baseline(coverage, 2),
            {"id": "synthetic-overlap", "range": [0x4C8, 0x4C9], "role": "primary",
             "primary_class": "synthetic", "claim_kind": "synthetic"},
        ]
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._boot_copy_source_claims(ROOT, rom, prior)


class TextBgTaskClosureQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the dependency-gated text-BG task closure."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text()
        )
        # text-BG loop continuation 与 boot copy source 都已在 canonical 账本里，
        # 必须先剔掉再按原链序重投影，本用例自己再投影 text-BG task closure。
        # text-BG task closure 本身也已在账本里，必须一并从基线里剔掉
        # （但不由这里重建），否则生产者自己的 current-unknown 门会拒绝
        # 本用例对自己的重投影。
        cls.PRIOR = _reproject_chain(
            cls.COVERAGE,
            cls.ROM,
            2,
            excluded=("rom-text-bg-task-closure-v1",),
        )

    def _prior(self):
        return json.loads(json.dumps(self.PRIOR))

    def test_projects_exact_34_claims_and_combined_3614_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_text_bg_task_closure_claims", None)
        self.assertIsNotNone(helper)
        rom = self.ROM
        prior = self._prior()
        claims = helper(ROOT, rom, prior)
        self.assertEqual(34, len(claims))
        self.assertEqual(2940, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(21, sum(row["claim_kind"] == "text_bg_task_closure_reachable_instruction_bytes" for row in claims))
        self.assertEqual(13, sum(row["claim_kind"] == "text_bg_task_closure_consumed_literal_word_bytes" for row in claims))
        segments = coverage_auditor.atomize_claims(len(rom), [*prior, *claims])
        classified = sum(end - start for row in segments if row["primary_class"] != "unknown" for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_188_130)
        self.assertLessEqual(len(rom) - classified, 103_326)

    def test_packet_is_wired_after_boot_and_verifier_identity_is_frozen(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        boot = "claims += _boot_copy_source_claims(root, rom, claims)"
        task = "claims += _text_bg_task_closure_claims(root, rom, claims)"
        self.assertIn(task, source)
        self.assertGreater(source.index(task), source.index(boot))
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/verify_rom_text_bg_task_closure.py").read_bytes()).hexdigest(),
            coverage_auditor.TEXT_BG_TASK_CLOSURE_VERIFIER_SHA256,
        )

    def test_projection_rejects_any_non_unknown_promotion_overlap(self):
        rom = self.ROM
        prior = self._prior()
        prior.append({"id": "synthetic-overlap", "range": [0x08A708, 0x08A709],
                      "role": "primary", "primary_class": "synthetic", "claim_kind": "synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._text_bg_task_closure_claims(ROOT, rom, prior)


class FixedRendererScriptRecordsQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the fourth fixed renderer-record packet."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        # 前三个链包都已在 canonical 账本里，先剔掉再按原链序重投影，
        # 本用例自己再投影 fixed renderer script records。
        # 第 4 个链包（fixed renderer script records）同样已在账本里，
        # 必须一并从基线里剔掉（但不由这里重建）。
        cls.PRIOR = _reproject_chain(
            cls.COVERAGE,
            cls.ROM,
            3,
            excluded=("rom-fixed-renderer-script-records-v1",),
        )

    def _prior(self):
        return json.loads(json.dumps(self.PRIOR))

    def test_projects_exact_30_records_and_four_packet_total(self):
        helper = getattr(coverage_auditor, "_fixed_renderer_script_record_claims", None)
        self.assertIsNotNone(helper)
        claims = helper(ROOT, self.ROM, self._prior())
        self.assertEqual(30, len(claims))
        self.assertEqual(1124, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertTrue(all(row["claim_kind"] == "fixed_cfg_consumer_renderer_command_script_bytes" for row in claims))
        segments = coverage_auditor.atomize_claims(len(self.ROM), [*self._prior(), *claims])
        classified = sum(end - start for row in segments if row["primary_class"] != "unknown" for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_189_254)
        self.assertLessEqual(len(self.ROM) - classified, 102_202)

    def test_wiring_after_task_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        task = "claims += _text_bg_task_closure_claims(root, rom, claims)"
        records = "claims += _fixed_renderer_script_record_claims(root, rom, claims)"
        self.assertIn(records, source)
        self.assertGreater(source.index(records), source.index(task))
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/verify_rom_fixed_renderer_script_records.py").read_bytes()).hexdigest(),
            coverage_auditor.FIXED_RENDERER_SCRIPT_RECORDS_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = self._prior()
        prior.append({"id":"synthetic-overlap","range":[0x0A65,0x0A66],"role":"primary",
                      "primary_class":"synthetic","claim_kind":"synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._fixed_renderer_script_record_claims(ROOT, self.ROM, prior)


FOUR_PACKET_TIER1_BATCHES = {
    "rom-boot-state-dispatcher-cfg-v1",
    "rom-fixed-animation-descriptor-groups-v1",
    "rom-battle-distance-dispatcher-cfg-v1",
    "rom-bounded-index-u16-pair-table-v1",
}


def _before_four_packet_tier2(coverage):
    return [
        row for row in coverage["claims"]
        if row.get("promotion_batch") not in FOUR_PACKET_TIER1_BATCHES
    ]


class BootStateDispatcherCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the bounded boot-state dispatcher packet."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = _before_four_packet_tier2(cls.COVERAGE)

    def test_projects_exact_45_claims_and_2532_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_boot_state_dispatcher_cfg_claims", None)
        self.assertIsNotNone(helper)
        claims = helper(ROOT, self.ROM, self.PRIOR)
        self.assertEqual(45, len(claims))
        self.assertEqual(2532, sum(row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(23, sum(row["claim_kind"] == "boot_state_target_reachable_instruction_bytes" for row in claims))
        self.assertEqual(21, sum(row["claim_kind"] == "boot_state_target_consumed_literal_word_bytes" for row in claims))
        self.assertEqual(1, sum(row["claim_kind"] == "boot_state_bounded_dispatcher_bytes" for row in claims))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *claims])
        classified = sum(end - start for row in segments if row["primary_class"] != "unknown" for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_191_786)
        self.assertLessEqual(len(self.ROM) - classified, 99_670)

    def test_wiring_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _fixed_renderer_script_record_claims(root, rom, claims)"
        packet = "claims += _boot_state_dispatcher_cfg_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/verify_rom_boot_state_dispatcher_cfg.py").read_bytes()).hexdigest(),
            coverage_auditor.BOOT_STATE_DISPATCHER_CFG_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({"id":"synthetic-overlap","range":[0x063ADC,0x063ADE],"role":"primary",
                      "primary_class":"synthetic","claim_kind":"synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._boot_state_dispatcher_cfg_claims(ROOT, self.ROM, prior)


class FixedAnimationDescriptorGroupsQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the fixed four-group descriptor packet."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        baseline = _before_four_packet_tier2(cls.COVERAGE)
        boot_state = coverage_auditor._boot_state_dispatcher_cfg_claims(
            ROOT, cls.ROM, baseline)
        cls.PRIOR = [*baseline, *boot_state]

    def test_projects_one_claim_and_combined_3668_unknown_bytes(self):
        helper = getattr(coverage_auditor, "_fixed_animation_descriptor_group_claims", None)
        self.assertIsNotNone(helper)
        claims = helper(ROOT, self.ROM, self.PRIOR)
        self.assertEqual(1, len(claims))
        self.assertEqual([0x12D574, 0x12D9E4], claims[0]["range"])
        self.assertEqual(1136, claims[0]["range"][1] - claims[0]["range"][0])
        self.assertEqual("fixed_consumer_animation_descriptor_group_bytes",
                         claims[0]["primary_class"])
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *claims])
        classified = sum(end - start for row in segments
                         if row["primary_class"] != "unknown"
                         for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_192_922)
        self.assertLessEqual(len(self.ROM) - classified, 98_534)

    def test_wiring_after_boot_state_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _boot_state_dispatcher_cfg_claims(root, rom, claims)"
        packet = "claims += _fixed_animation_descriptor_group_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256((ROOT / "tools/verify_rom_fixed_animation_descriptor_groups.py").read_bytes()).hexdigest(),
            coverage_auditor.FIXED_ANIMATION_DESCRIPTOR_GROUPS_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({"id":"synthetic-overlap","range":[0x12D574,0x12D575],
                      "role":"primary","primary_class":"synthetic",
                      "claim_kind":"synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._fixed_animation_descriptor_group_claims(
                ROOT, self.ROM, prior)


class BattleDistanceDispatcherCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the seven-way battle-distance dispatcher."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        baseline = _before_four_packet_tier2(cls.COVERAGE)
        boot_state = coverage_auditor._boot_state_dispatcher_cfg_claims(
            ROOT, cls.ROM, baseline)
        fixed_animation = coverage_auditor._fixed_animation_descriptor_group_claims(
            ROOT, cls.ROM, [*baseline, *boot_state])
        cls.PRIOR = [*baseline, *boot_state, *fixed_animation]

    def test_projects_14_claims_and_combined_4830_unknown_bytes(self):
        helper = getattr(coverage_auditor,
                         "_battle_distance_dispatcher_cfg_claims", None)
        self.assertIsNotNone(helper)
        claims = helper(ROOT, self.ROM, self.PRIOR)
        self.assertEqual(14, len(claims))
        self.assertEqual(1162, sum(row["range"][1] - row["range"][0]
                                   for row in claims))
        self.assertEqual(7, sum(row["claim_kind"] ==
                                "battle_distance_target_reachable_instruction_bytes"
                                for row in claims))
        self.assertEqual(6, sum(row["claim_kind"] ==
                                "battle_distance_target_consumed_literal_word_bytes"
                                for row in claims))
        self.assertEqual(1, sum(row["claim_kind"] ==
                                "battle_distance_bounded_dispatch_table_bytes"
                                for row in claims))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *claims])
        classified = sum(end - start for row in segments
                         if row["primary_class"] != "unknown"
                         for start, end in [row["range"]])
        self.assertGreaterEqual(classified, 6_194_084)
        self.assertLessEqual(len(self.ROM) - classified, 97_372)
        holes = [row for row in segments if row["range"] in
                 ([0x083F52, 0x083F54], [0x083FBE, 0x083FC0])]
        self.assertEqual(["unknown", "unknown"],
                         [row["primary_class"] for row in holes])

    def test_wiring_after_fixed_animation_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _fixed_animation_descriptor_group_claims(root, rom, claims)"
        packet = "claims += _battle_distance_dispatcher_cfg_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_battle_distance_dispatcher_cfg.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.BATTLE_DISTANCE_DISPATCHER_CFG_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({"id": "synthetic-overlap", "range": [0x083B5C, 0x083B5D],
                      "role": "primary", "primary_class": "synthetic",
                      "claim_kind": "synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._battle_distance_dispatcher_cfg_claims(
                ROOT, self.ROM, prior)


class BattleDistanceDispatcherCfgRegistryTests(unittest.TestCase):
    """Keep the Tier-1 code kind admissible to the Tier-2 CFG aggregate."""

    def test_reachable_code_kind_is_registered_as_thumb_only(self):
        self.assertIn(
            "battle_distance_target_reachable_instruction_bytes",
            coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"],
        )


class BoundedIndexU16PairTableQuickProjectionTests(unittest.TestCase):
    """Tier-1 checks for the bounded-index u16-pair packet itself."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        baseline = _before_four_packet_tier2(cls.COVERAGE)
        boot_state = coverage_auditor._boot_state_dispatcher_cfg_claims(
            ROOT, cls.ROM, baseline)
        fixed_animation = coverage_auditor._fixed_animation_descriptor_group_claims(
            ROOT, cls.ROM, [*baseline, *boot_state])
        battle_distance = coverage_auditor._battle_distance_dispatcher_cfg_claims(
            ROOT, cls.ROM, [*baseline, *boot_state, *fixed_animation])
        cls.PRIOR = [
            *baseline, *boot_state, *fixed_animation, *battle_distance
        ]

    def test_projects_one_claim_and_four_packet_total(self):
        helper = getattr(
            coverage_auditor, "_bounded_index_u16_pair_table_claims", None)
        self.assertIsNotNone(helper)
        claims = helper(ROOT, self.ROM, self.PRIOR)
        self.assertEqual(1, len(claims))
        self.assertEqual([0x53F2EE, 0x53F30E], claims[0]["range"])
        self.assertEqual("bounded_index_u16_pair_table_bytes",
                         claims[0]["primary_class"])
        self.assertEqual("bounded_index_u16_pair_table_bytes",
                         claims[0]["claim_kind"])
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *claims])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_194_116)
        self.assertLessEqual(len(self.ROM) - classified, 97_340)
        right_gap = next(
            row for row in segments
            if row["range"][0] <= 0x53F30E
            and row["range"][1] >= 0x53F310
        )
        self.assertEqual("unknown", right_gap["primary_class"])

    def test_wiring_after_battle_distance_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _battle_distance_dispatcher_cfg_claims(root, rom, claims)"
        packet = "claims += _bounded_index_u16_pair_table_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_bounded_index_u16_pair_table.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.BOUNDED_INDEX_U16_PAIR_TABLE_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({"id": "synthetic-overlap", "range": [0x53F2EE, 0x53F2EF],
                      "role": "primary", "primary_class": "synthetic",
                      "claim_kind": "synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._bounded_index_u16_pair_table_claims(
                ROOT, self.ROM, prior)


SCENE_SOURCE_TIER1_BATCHES = {
    "rom-v17-v18-helper-cfg-v1",
    "rom-fixed-pair-tables-v1",
    "rom-prebattle-menu-controller-cfg-v1",
    "rom-scene-source-closures-v1",
}


def _before_scene_source_tier2(coverage):
    return [
        row for row in coverage["claims"]
        if row.get("promotion_batch") not in SCENE_SOURCE_TIER1_BATCHES
    ]


class V17V18HelperCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the producer-bound V17/V18 helper CFG."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = _before_scene_source_tier2(cls.COVERAGE)
        cls.CLAIMS = coverage_auditor._v17_v18_helper_cfg_claims(
            ROOT, cls.ROM, cls.PRIOR)

    def test_projects_exact_claims_and_keeps_six_holes_unknown(self):
        helper = getattr(coverage_auditor, "_v17_v18_helper_cfg_claims", None)
        self.assertIsNotNone(helper)
        claims = self.CLAIMS
        self.assertEqual(14, len(claims))
        self.assertEqual(1254, sum(
            row["range"][1] - row["range"][0] for row in claims))
        self.assertEqual(9, sum(
            row["claim_kind"] == "v17_v18_helper_reachable_instruction_bytes"
            for row in claims))
        self.assertEqual(5, sum(
            row["claim_kind"] == "v17_v18_helper_consumed_literal_word_bytes"
            for row in claims))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *claims])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_195_370)
        self.assertLessEqual(len(self.ROM) - classified, 96_086)
        holes = ([0x090656, 0x090658], [0x0906DE, 0x0906E0],
                 [0x090756, 0x090758], [0x0908D2, 0x0908D4],
                 [0x090A0A, 0x090A0C], [0x090A8E, 0x090A90])
        for hole in holes:
            owner = next(row for row in segments
                         if row["range"][0] <= hole[0]
                         and hole[1] <= row["range"][1])
            self.assertEqual("unknown", owner["primary_class"], hole)

    def test_wiring_after_bounded_index_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _bounded_index_u16_pair_table_claims(root, rom, claims)"
        packet = "claims += _v17_v18_helper_cfg_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_v17_v18_helper_cfg.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.V17_V18_HELPER_CFG_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({"id": "synthetic-overlap",
                      "range": [0x090564, 0x090565],
                      "role": "primary", "primary_class": "synthetic",
                      "claim_kind": "synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._v17_v18_helper_cfg_claims(
                ROOT, self.ROM, prior)

    def test_code_kind_is_staged_without_polluting_canonical_registry(self):
        kind = "v17_v18_helper_reachable_instruction_bytes"
        self.assertNotIn(
            kind,
            coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"],
        )
        self.assertIn(
            kind,
            coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"],
        )

    def test_staged_cfg_kind_is_absent_safe_present_counted_and_mode_checked(self):
        stable = coverage_auditor._cfg_code_aggregate(self.PRIOR)
        self.assertGreaterEqual(stable["cfg_reachable_thumb_code_bytes"], 165_572)
        self.assertGreaterEqual(stable["cfg_promoted_unknown_bytes"], 166_560)
        self.assertGreaterEqual(stable["cfg_primary_claim_count"], 3_969)
        self.assertGreaterEqual(stable["cfg_code_claim_kind_count"], 45)
        projected = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.CLAIMS])
        self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 166_770)
        self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 167_758)
        self.assertGreaterEqual(projected["cfg_primary_claim_count"], 3_978)
        self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 46)
        self.assertNotEqual(
            stable["cfg_code_claim_kind_denominator_sha256"],
            projected["cfg_code_claim_kind_denominator_sha256"],
        )
        mutated = json.loads(json.dumps(self.CLAIMS))
        code = next(row for row in mutated if row["mode"] == "thumb")
        code["mode"] = None
        with self.assertRaisesRegex(ValueError, "Thumb mode"):
            coverage_auditor._cfg_code_aggregate([*self.PRIOR, *mutated])


class FixedPairTablesQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the two frozen fixed pair tables."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = _before_scene_source_tier2(cls.COVERAGE)
        cls.HELPER = coverage_auditor._v17_v18_helper_cfg_claims(
            ROOT, cls.ROM, cls.PRIOR)
        cls.CLAIMS = coverage_auditor._fixed_pair_table_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.HELPER])

    def test_projects_exact_two_claims_and_preserves_neighbor_gaps(self):
        self.assertEqual(2, len(self.CLAIMS))
        self.assertEqual(
            [[0x53E00A, 0x53E014], [0x53E014, 0x53E034]],
            [row["range"] for row in self.CLAIMS],
        )
        self.assertEqual(
            ["fixed_signed_u16_sequence", "masked_u16_pair_table"],
            [row["claim_kind"] for row in self.CLAIMS],
        )
        self.assertEqual(42, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *self.HELPER, *self.CLAIMS])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_195_412)
        self.assertLessEqual(len(self.ROM) - classified, 96_044)
        for offset in (0x53E009, 0x53E034):
            owner = next(row for row in segments
                         if row["range"][0] <= offset < row["range"][1])
            self.assertEqual("unknown", owner["primary_class"])

    def test_wiring_after_helper_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _v17_v18_helper_cfg_claims(root, rom, claims)"
        packet = "claims += _fixed_pair_table_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_fixed_pair_tables.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.FIXED_PAIR_TABLES_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps([*self.PRIOR, *self.HELPER]))
        prior.append({"id": "synthetic-overlap",
                      "range": [0x53E00A, 0x53E00B],
                      "role": "primary", "primary_class": "synthetic",
                      "claim_kind": "synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._fixed_pair_table_claims(ROOT, self.ROM, prior)

    def test_tier2_canonical_contains_the_completed_batch(self):
        self.assertGreaterEqual(self.COVERAGE["summary"]["classified_bytes"], 6_198_347)
        self.assertLessEqual(self.COVERAGE["summary"]["unknown_bytes"], 93_109)


class PrebattleMenuControllerCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the frozen pre-battle controller CFG."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = _before_scene_source_tier2(cls.COVERAGE)
        cls.HELPER = coverage_auditor._v17_v18_helper_cfg_claims(
            ROOT, cls.ROM, cls.PRIOR)
        cls.FIXED = coverage_auditor._fixed_pair_table_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.HELPER])
        cls.CLAIMS = coverage_auditor._prebattle_menu_controller_cfg_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.HELPER, *cls.FIXED])

    def test_projects_exact_52_claims_and_1920_unknown_bytes(self):
        self.assertEqual(52, len(self.CLAIMS))
        self.assertEqual(1_920, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        self.assertEqual(27, sum(
            row["claim_kind"]
            == "prebattle_menu_controller_reachable_instruction_bytes"
            for row in self.CLAIMS))
        self.assertEqual(24, sum(
            row["claim_kind"]
            == "prebattle_menu_controller_consumed_literal_word_bytes"
            for row in self.CLAIMS))
        self.assertEqual(1, sum(
            row["claim_kind"]
            == "prebattle_menu_controller_fixed_jump_table_bytes"
            for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM),
            [*self.PRIOR, *self.HELPER, *self.FIXED, *self.CLAIMS],
        )
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_197_332)
        self.assertLessEqual(len(self.ROM) - classified, 94_124)

    def test_wiring_after_fixed_pairs_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _fixed_pair_table_claims(root, rom, claims)"
        packet = "claims += _prebattle_menu_controller_cfg_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_prebattle_menu_controller_cfg.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.PREBATTLE_MENU_CONTROLLER_CFG_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps([*self.PRIOR, *self.HELPER, *self.FIXED]))
        prior.append({"id": "synthetic-overlap",
                      "range": [0x08F190, 0x08F191],
                      "role": "primary", "primary_class": "synthetic",
                      "claim_kind": "synthetic"})
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._prebattle_menu_controller_cfg_claims(
                ROOT, self.ROM, prior)

    def test_code_kind_is_staged_without_changing_canonical_registry(self):
        kind = "prebattle_menu_controller_reachable_instruction_bytes"
        self.assertNotIn(kind, coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn(kind, coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])

    def test_staged_code_is_counted_without_rewriting_the_canonical_denominator(self):
        projected = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.HELPER, *self.FIXED, *self.CLAIMS]
        )
        self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 168_334)
        self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 169_322)
        self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_005)
        self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 47)


class SceneSourceClosuresQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the independently verified scene-source packet."""

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = _before_scene_source_tier2(cls.COVERAGE)
        cls.HELPER = coverage_auditor._v17_v18_helper_cfg_claims(
            ROOT, cls.ROM, cls.PRIOR)
        cls.FIXED = coverage_auditor._fixed_pair_table_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.HELPER])
        cls.PREBATTLE = coverage_auditor._prebattle_menu_controller_cfg_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.HELPER, *cls.FIXED])
        cls.CLAIMS = coverage_auditor._scene_source_closure_claims(
            ROOT,
            cls.ROM,
            [*cls.PRIOR, *cls.HELPER, *cls.FIXED, *cls.PREBATTLE],
        )

    def test_projects_exact_73_claims_and_1015_unknown_bytes(self):
        self.assertEqual(73, len(self.CLAIMS))
        self.assertEqual(1_015, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        self.assertEqual(2, sum(
            row["claim_kind"] == "scene_obj_source_closure_bytes"
            for row in self.CLAIMS))
        self.assertEqual(71, sum(
            row["claim_kind"] == "parser_bound_scene_source_record_bytes"
            for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM),
            [*self.PRIOR, *self.HELPER, *self.FIXED,
             *self.PREBATTLE, *self.CLAIMS],
        )
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_198_347)
        self.assertLessEqual(len(self.ROM) - classified, 93_109)

    def test_wiring_after_prebattle_and_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _prebattle_menu_controller_cfg_claims(root, rom, claims)"
        packet = "claims += _scene_source_closure_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_scene_source_closures.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.SCENE_SOURCE_CLOSURES_VERIFIER_SHA256,
        )

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps([
            *self.PRIOR, *self.HELPER, *self.FIXED, *self.PREBATTLE,
        ]))
        prior.append({
            "id": "synthetic-overlap", "range": [0x46401C, 0x46401D],
            "role": "primary", "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._scene_source_closure_claims(
                ROOT, self.ROM, prior)


class StoryCallbackDependencyQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the producer-bound story callback dependencies."""

    BATCH = "rom-story-callback-dependency-closures-v1"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        cls.COVERAGE = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = [
            row for row in cls.COVERAGE["claims"]
            if row.get("promotion_batch") != cls.BATCH
        ]
        cls.CLAIMS = coverage_auditor._story_callback_dependency_claims(
            ROOT, cls.ROM, cls.PRIOR)

    def test_projects_exact_32_claims_and_1932_current_unknown_bytes(self):
        self.assertEqual(32, len(self.CLAIMS))
        self.assertEqual(1_932, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        self.assertEqual(18, sum(
            row["claim_kind"]
            == "story_callback_dependency_reachable_instruction_bytes"
            for row in self.CLAIMS))
        self.assertEqual(14, sum(
            row["claim_kind"]
            == "story_callback_dependency_consumed_literal_word_bytes"
            for row in self.CLAIMS))
        self.assertTrue(all(
            row["coverage_projection_gate"] == "current_unknown_before_projection"
            for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *self.CLAIMS])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_200_279)
        self.assertLessEqual(len(self.ROM) - classified, 91_177)
        for start, end in (
            (0x68C12, 0x68C14), (0x86326, 0x86328),
            (0x86B6E, 0x86B70), (0x86BFE, 0x86C00),
            (0x86C12, 0x86C14), (0x8F6F6, 0x8F6F8),
        ):
            owner = next(row for row in segments
                         if row["range"][0] <= start and end <= row["range"][1])
            self.assertEqual("unknown", owner["primary_class"], (start, end))

    def test_wiring_verifier_identity_and_staged_code_registry(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _scene_source_closure_claims(root, rom, claims)"
        packet = "claims += _story_callback_dependency_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_story_callback_dependency_closures.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.STORY_CALLBACK_DEPENDENCY_VERIFIER_SHA256,
        )
        kind = "story_callback_dependency_reachable_instruction_bytes"
        self.assertNotIn(kind, coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn(kind, coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])
        projected = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.CLAIMS])
        self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 169_990)
        self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 170_978)
        self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_023)
        self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 48)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({
            "id": "synthetic-overlap", "range": [0x68AF0, 0x68AF1],
            "role": "primary", "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._story_callback_dependency_claims(
                ROOT, self.ROM, prior)


class CfgProvenRootsV20QuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the story-overlay-gated v20 CFG packet."""

    STORY_BATCH = "rom-story-callback-dependency-closures-v1"
    BATCH = "rom-cfg-proven-roots-v20"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = [
            row for row in coverage["claims"]
            if row.get("promotion_batch")
            not in {cls.STORY_BATCH, cls.BATCH}
        ]
        cls.STORY_CLAIMS = (
            coverage_auditor._story_callback_dependency_claims(
                ROOT, cls.ROM, cls.PRIOR))
        cls.CLAIMS = coverage_auditor._cfg_proven_roots_v20_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.STORY_CLAIMS])

    def test_projects_exact_18_claims_and_1150_current_unknown_bytes(self):
        self.assertEqual(18, len(self.CLAIMS))
        self.assertEqual(1_150, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        self.assertEqual(11, sum(
            row["claim_kind"]
            == "cfg_proven_roots_v20_reachable_instruction_bytes"
            for row in self.CLAIMS))
        self.assertEqual(7, sum(
            row["claim_kind"]
            == "cfg_proven_roots_v20_consumed_literal_word_bytes"
            for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *self.STORY_CLAIMS, *self.CLAIMS])
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_201_429)
        self.assertLessEqual(len(self.ROM) - classified, 90_027)

    def test_wiring_verifier_identity_and_staged_cfg_aggregate(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        story = "claims += _story_callback_dependency_claims(root, rom, claims)"
        packet = "claims += _cfg_proven_roots_v20_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(story))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_cfg_proven_roots_v20.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.CFG_PROVEN_ROOTS_V20_VERIFIER_SHA256,
        )
        kind = "cfg_proven_roots_v20_reachable_instruction_bytes"
        self.assertNotIn(kind, coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn(
            kind, coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])
        projected = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.STORY_CLAIMS, *self.CLAIMS])
        self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 171_060)
        self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 172_048)
        self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_034)
        self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 49)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps([*self.PRIOR, *self.STORY_CLAIMS]))
        prior.append({
            "id": "synthetic-overlap", "range": [0x627B0, 0x627B1],
            "role": "primary", "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._cfg_proven_roots_v20_claims(
                ROOT, self.ROM, prior)


class StoryNextDependencyCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the next producer-bound story CFG packet."""

    STORY_BATCH = "rom-story-callback-dependency-closures-v1"
    V20_BATCH = "rom-cfg-proven-roots-v20"
    BATCH = "rom-story-next-dependency-cfg-v1"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = [
            row for row in coverage["claims"]
            if row.get("promotion_batch")
            not in {cls.STORY_BATCH, cls.V20_BATCH, cls.BATCH}
        ]
        cls.STORY_CLAIMS = (
            coverage_auditor._story_callback_dependency_claims(
                ROOT, cls.ROM, cls.PRIOR))
        cls.V20_CLAIMS = coverage_auditor._cfg_proven_roots_v20_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.STORY_CLAIMS])
        cls.CLAIMS = coverage_auditor._story_next_dependency_cfg_claims(
            ROOT,
            cls.ROM,
            [*cls.PRIOR, *cls.STORY_CLAIMS, *cls.V20_CLAIMS],
        )

    def test_projects_exact_19_claims_and_854_current_unknown_bytes(self):
        self.assertEqual(19, len(self.CLAIMS))
        self.assertEqual(854, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        self.assertEqual(10, sum(
            row["claim_kind"]
            == "story_next_dependency_cfg_reachable_instruction_bytes"
            for row in self.CLAIMS))
        self.assertEqual(9, sum(
            row["claim_kind"]
            == "story_next_dependency_cfg_consumed_literal_word_bytes"
            for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM),
            [*self.PRIOR, *self.STORY_CLAIMS, *self.V20_CLAIMS, *self.CLAIMS],
        )
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_202_283)
        self.assertLessEqual(len(self.ROM) - classified, 89_173)
        for start, end in (
            (0x8859A, 0x8859C), (0x8860E, 0x88610),
            (0x8864A, 0x8864C), (0x88F52, 0x88F54),
            (0x89036, 0x89038),
        ):
            owner = next(row for row in segments
                         if row["range"][0] <= start and end <= row["range"][1])
            self.assertEqual("unknown", owner["primary_class"], (start, end))

    def test_wiring_verifier_identity_and_staged_cfg_aggregate(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _cfg_proven_roots_v20_claims(root, rom, claims)"
        packet = "claims += _story_next_dependency_cfg_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_story_next_dependency_cfg.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.STORY_NEXT_DEPENDENCY_CFG_VERIFIER_SHA256,
        )
        kind = "story_next_dependency_cfg_reachable_instruction_bytes"
        self.assertNotIn(kind, coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn(
            kind, coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])
        projected = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.STORY_CLAIMS,
             *self.V20_CLAIMS, *self.CLAIMS])
        self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 171_830)
        self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 172_818)
        self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_044)
        self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 50)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(
            [*self.PRIOR, *self.STORY_CLAIMS, *self.V20_CLAIMS]))
        prior.append({
            "id": "synthetic-overlap", "range": [0x88444, 0x88445],
            "role": "primary", "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._story_next_dependency_cfg_claims(
                ROOT, self.ROM, prior)


class BootRegisterInitDependencyCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the producer-bound boot register-init CFG."""

    STORY_BATCH = "rom-story-callback-dependency-closures-v1"
    V20_BATCH = "rom-cfg-proven-roots-v20"
    STORY_NEXT_BATCH = "rom-story-next-dependency-cfg-v1"
    BATCH = "rom-boot-register-init-dependency-cfg-v1"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        cls.PRIOR = [
            row for row in coverage["claims"]
            if row.get("promotion_batch") not in {
                cls.STORY_BATCH,
                cls.V20_BATCH,
                cls.STORY_NEXT_BATCH,
                cls.BATCH,
            }
        ]
        cls.STORY_CLAIMS = (
            coverage_auditor._story_callback_dependency_claims(
                ROOT, cls.ROM, cls.PRIOR))
        cls.V20_CLAIMS = coverage_auditor._cfg_proven_roots_v20_claims(
            ROOT, cls.ROM, [*cls.PRIOR, *cls.STORY_CLAIMS])
        cls.STORY_NEXT_CLAIMS = (
            coverage_auditor._story_next_dependency_cfg_claims(
                ROOT,
                cls.ROM,
                [*cls.PRIOR, *cls.STORY_CLAIMS, *cls.V20_CLAIMS],
            ))
        cls.CLAIMS = coverage_auditor._boot_register_init_dependency_cfg_claims(
            ROOT,
            cls.ROM,
            [*cls.PRIOR, *cls.STORY_CLAIMS,
             *cls.V20_CLAIMS, *cls.STORY_NEXT_CLAIMS],
        )

    def test_projects_exact_eight_claims_and_446_current_unknown_bytes(self):
        self.assertEqual(8, len(self.CLAIMS))
        self.assertEqual(446, sum(
            row["range"][1] - row["range"][0] for row in self.CLAIMS))
        self.assertEqual(4, sum(
            row["claim_kind"]
            == "boot_register_init_dependency_cfg_reachable_instruction_bytes"
            for row in self.CLAIMS))
        self.assertEqual(4, sum(
            row["claim_kind"]
            == "boot_register_init_dependency_cfg_consumed_literal_word_bytes"
            for row in self.CLAIMS))
        combined = [
            *self.PRIOR,
            *self.STORY_CLAIMS,
            *self.V20_CLAIMS,
            *self.STORY_NEXT_CLAIMS,
            *self.CLAIMS,
        ]
        segments = coverage_auditor.atomize_claims(len(self.ROM), combined)
        classified = sum(
            end - start
            for row in segments
            if row["primary_class"] != "unknown"
            for start, end in [row["range"]]
        )
        self.assertGreaterEqual(classified, 6_202_729)
        self.assertLessEqual(len(self.ROM) - classified, 88_727)
        hole = next(row for row in segments
                    if row["range"][0] <= 0x06181E
                    and 0x061820 <= row["range"][1])
        self.assertEqual("unknown", hole["primary_class"])
        existing = [
            row for row in segments
            if row["range"][0] < 0x0620CC
            and row["range"][1] > 0x0620B4
        ]
        self.assertEqual(
            [
                (0x0620B4, 0x0620C6,
                 "armv4t_boot_thumb_handoff_reachable_code"),
                (0x0620C6, 0x0620C8,
                 "boot_thumb_code_literal_alignment_bytes"),
                (0x0620C8, 0x0620CC,
                 "armv4t_boot_thumb_handoff_consumed_literal_pool"),
            ],
            [(*row["range"], row["primary_class"]) for row in existing],
        )

    def test_wiring_verifier_identity_and_staged_cfg_aggregate(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = "claims += _story_next_dependency_cfg_claims(root, rom, claims)"
        packet = (
            "claims += _boot_register_init_dependency_cfg_claims"
            "(root, rom, claims)"
        )
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_boot_register_init_dependency_cfg.py")
                .read_bytes()
            ).hexdigest(),
            coverage_auditor.BOOT_REGISTER_INIT_DEPENDENCY_CFG_VERIFIER_SHA256,
        )
        kind = (
            "boot_register_init_dependency_cfg_reachable_instruction_bytes"
        )
        self.assertNotIn(kind, coverage_auditor.CFG_CODE_KIND_REGISTRY["thumb_only"])
        self.assertIn(
            kind, coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"])
        projected = coverage_auditor._cfg_code_aggregate([
            *self.PRIOR,
            *self.STORY_CLAIMS,
            *self.V20_CLAIMS,
            *self.STORY_NEXT_CLAIMS,
            *self.CLAIMS,
        ])
        self.assertGreaterEqual(projected["cfg_reachable_thumb_code_bytes"], 172_148)
        self.assertGreaterEqual(projected["cfg_promoted_unknown_bytes"], 173_136)
        self.assertGreaterEqual(projected["cfg_primary_claim_count"], 4_048)
        self.assertGreaterEqual(projected["cfg_code_claim_kind_count"], 51)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps([
            *self.PRIOR,
            *self.STORY_CLAIMS,
            *self.V20_CLAIMS,
            *self.STORY_NEXT_CLAIMS,
        ]))
        prior.append({
            "id": "synthetic-overlap", "range": [0x06178C, 0x06178D],
            "role": "primary", "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._boot_register_init_dependency_cfg_claims(
                ROOT, self.ROM, prior)


class Tier1CurrentUnknownGateTests(unittest.TestCase):
    def test_linear_interval_gate_matches_fail_closed_primary_semantics(self):
        claims = [
            {"id": "left", "range": [2, 8], "role": "primary",
             "primary_class": "classified"},
            {"id": "support", "range": [10, 20], "role": "secondary"},
            {"id": "right", "range": [24, 30], "role": "primary",
             "primary_class": "classified"},
        ]
        coverage_auditor._require_current_unknown_ranges(
            32, claims, [(8, 24)], label="synthetic")
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._require_current_unknown_ranges(
                32, claims, [(7, 9)], label="synthetic")
        with self.assertRaisesRegex(ValueError, "conflicting primary"):
            coverage_auditor._require_current_unknown_ranges(
                32,
                [*claims, {"id": "overlap", "range": [7, 9],
                           "role": "primary", "primary_class": "other"}],
                [(20, 21)],
                label="synthetic",
            )


def _post_story_precoverage_for_quick_tests():
    """Keep historical Tier-1 receipts replayable after all siblings promote."""
    from tools import rom_fixed_index_u8_tail_contract as contract

    raw = gzip.decompress((ROOT / contract.PRECOVERAGE_ARTIFACT /
                           contract.PRECOVERAGE_ARCHIVE_NAME).read_bytes())
    if hashlib.sha256(raw).hexdigest() != contract.COVERAGE_SHA256:
        raise AssertionError("post-story precoverage identity changed")
    return json.loads(raw)


class FixedIndexU8TailQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the four fixed-index u8 lookup bytes."""

    BATCH = "rom-fixed-index-u8-tail-v1"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        coverage = _post_story_precoverage_for_quick_tests()
        cls.PRIOR = [
            row for row in coverage["claims"]
            if row.get("promotion_batch") != cls.BATCH
        ]
        cls.CLAIMS = coverage_auditor._fixed_index_u8_tail_claims(
            ROOT, cls.ROM, cls.PRIOR)

    def test_projects_exact_one_claim_and_four_current_unknown_bytes(self):
        self.assertEqual(1, len(self.CLAIMS))
        claim = self.CLAIMS[0]
        self.assertEqual([0x53E492, 0x53E496], claim["range"])
        self.assertEqual("fixed_index_u8_lookup_tail", claim["primary_class"])
        self.assertEqual(
            "fixed_index_u8_lookup_tail_bytes", claim["claim_kind"])
        self.assertEqual(4, claim["range"][1] - claim["range"][0])
        self.assertTrue(claim["current_unknown_verified_by_auditor"])
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *self.CLAIMS])
        classified = sum(
            row["range"][1] - row["range"][0]
            for row in segments if row["primary_class"] != "unknown"
        )
        self.assertEqual((6_202_733, 88_723),
                         (classified, len(self.ROM) - classified))

    def test_wiring_and_independent_verifier_identity(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        previous = (
            "claims += _boot_register_init_dependency_cfg_claims"
            "(root, rom, claims)"
        )
        packet = "claims += _fixed_index_u8_tail_claims(root, rom, claims)"
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(previous))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_fixed_index_u8_tail.py").read_bytes()
            ).hexdigest(),
            coverage_auditor.FIXED_INDEX_U8_TAIL_VERIFIER_SHA256,
        )
        aggregate = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.CLAIMS])
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 172_148)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 173_136)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 4_048)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 51)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({
            "id": "synthetic-overlap", "range": [0x53E493, 0x53E494],
            "role": "primary", "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._fixed_index_u8_tail_claims(
                ROOT, self.ROM, prior)


class StorySelectorDependencyCfgQuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the 80-byte story-selector dependency CFG."""

    BATCH = "rom-story-selector-dependency-cfg-v1"
    KIND = "story_selector_dependency_cfg_reachable_instruction_bytes"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        coverage = _post_story_precoverage_for_quick_tests()
        canonical = [
            row for row in coverage["claims"]
            if row.get("promotion_batch") != cls.BATCH
        ]
        fixed = coverage_auditor._fixed_index_u8_tail_claims(
            ROOT, cls.ROM, canonical)
        cls.PRIOR = [*canonical, *fixed]
        cls.CLAIMS = coverage_auditor._story_selector_dependency_cfg_claims(
            ROOT, cls.ROM, cls.PRIOR)

    def test_projects_exact_one_claim_and_eighty_current_unknown_bytes(self):
        self.assertEqual(1, len(self.CLAIMS))
        claim = self.CLAIMS[0]
        self.assertEqual([0x08F544, 0x08F594], claim["range"])
        self.assertEqual(
            "armv4t_story_selector_dependency_cfg", claim["primary_class"])
        self.assertEqual(self.KIND, claim["claim_kind"])
        self.assertEqual(80, claim["range"][1] - claim["range"][0])
        self.assertTrue(claim["raw_cfg_denominator_verified"])
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *self.CLAIMS])
        classified = sum(
            row["range"][1] - row["range"][0]
            for row in segments if row["primary_class"] != "unknown"
        )
        self.assertEqual((6_202_813, 88_643),
                         (classified, len(self.ROM) - classified))

    def test_wiring_verifier_identity_and_staged_cfg_registry(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        fixed = "claims += _fixed_index_u8_tail_claims(root, rom, claims)"
        packet = (
            "claims += _story_selector_dependency_cfg_claims"
            "(root, rom, claims)"
        )
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(fixed))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_story_selector_dependency_cfg.py")
                .read_bytes()
            ).hexdigest(),
            coverage_auditor.STORY_SELECTOR_DEPENDENCY_CFG_VERIFIER_SHA256,
        )
        self.assertIn(
            self.KIND,
            coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"],
        )
        aggregate = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.CLAIMS])
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 172_228)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 173_216)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 4_049)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 52)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({
            "id": "synthetic-story-selector-overlap",
            "range": [0x08F580, 0x08F582],
            "role": "primary",
            "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._story_selector_dependency_cfg_claims(
                ROOT, self.ROM, prior)


class TaskCallback078E38QuickProjectionTests(unittest.TestCase):
    """Tier-1 projection for the bounded 0x078E38 task callback closure."""

    BATCH = "rom-task-callback-078e38-closure-v1"
    CODE_KIND = "task_callback_078e38_closure_reachable_instruction_bytes"
    LITERAL_KIND = "task_callback_078e38_closure_consumed_literal_word_bytes"

    @classmethod
    def setUpClass(cls):
        cls.ROM = (ROOT / "rom/base.gba").read_bytes()
        coverage = _post_story_precoverage_for_quick_tests()
        canonical = [
            row for row in coverage["claims"]
            if row.get("promotion_batch") != cls.BATCH
        ]
        fixed = coverage_auditor._fixed_index_u8_tail_claims(
            ROOT, cls.ROM, canonical)
        story_prior = [*canonical, *fixed]
        story = coverage_auditor._story_selector_dependency_cfg_claims(
            ROOT, cls.ROM, story_prior)
        cls.PRIOR = [*story_prior, *story]
        cls.CLAIMS = coverage_auditor._task_callback_078e38_closure_claims(
            ROOT, cls.ROM, cls.PRIOR)

    def test_projects_exact_sixteen_claims_and_778_current_unknown_bytes(self):
        self.assertEqual(16, len(self.CLAIMS))
        self.assertEqual(
            778,
            sum(row["range"][1] - row["range"][0] for row in self.CLAIMS),
        )
        self.assertEqual(
            {self.CODE_KIND, self.LITERAL_KIND},
            {row["claim_kind"] for row in self.CLAIMS},
        )
        self.assertEqual(8, sum(row["mode"] == "thumb" for row in self.CLAIMS))
        self.assertTrue(all(row["unresolved_frontier_preserved"]
                            for row in self.CLAIMS))
        segments = coverage_auditor.atomize_claims(
            len(self.ROM), [*self.PRIOR, *self.CLAIMS])
        classified = sum(
            row["range"][1] - row["range"][0]
            for row in segments if row["primary_class"] != "unknown"
        )
        self.assertEqual((6_203_591, 87_865),
                         (classified, len(self.ROM) - classified))

    def test_wiring_verifier_identity_and_staged_cfg_registry(self):
        source = __import__("inspect").getsource(coverage_auditor.build_manifest)
        story = (
            "claims += _story_selector_dependency_cfg_claims"
            "(root, rom, claims)"
        )
        packet = (
            "claims += _task_callback_078e38_closure_claims"
            "(root, rom, claims)"
        )
        self.assertIn(packet, source)
        self.assertGreater(source.index(packet), source.index(story))
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "tools/verify_rom_task_callback_078e38_closure.py")
                .read_bytes()
            ).hexdigest(),
            coverage_auditor.TASK_CALLBACK_078E38_VERIFIER_SHA256,
        )
        self.assertIn(
            self.CODE_KIND,
            coverage_auditor.CFG_STAGED_CODE_KIND_REGISTRY["thumb_only"],
        )
        aggregate = coverage_auditor._cfg_code_aggregate(
            [*self.PRIOR, *self.CLAIMS])
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 172_946)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 173_934)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 4_057)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 53)

    def test_projection_rejects_non_unknown_overlap(self):
        prior = json.loads(json.dumps(self.PRIOR))
        prior.append({
            "id": "synthetic-task-callback-overlap",
            "range": [0x078E40, 0x078E42],
            "role": "primary",
            "primary_class": "synthetic",
            "claim_kind": "synthetic",
        })
        with self.assertRaisesRegex(ValueError, "current unknown"):
            coverage_auditor._task_callback_078e38_closure_claims(
                ROOT, self.ROM, prior)


class SceneSourceFourPacketTier2CanonicalTests(unittest.TestCase):
    """The queued four-packet batch must be materialized, not extrapolated."""

    def test_canonical_contains_the_scene_source_four_packet_batch(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        self.assertGreaterEqual(coverage["summary"]["classified_bytes"], 6_198_347)
        self.assertLessEqual(coverage["summary"]["unknown_bytes"], 93_109)
        self.assertGreaterEqual(coverage["summary"]["claim_count"], 16_793)
        expected = {
            "rom-v17-v18-helper-cfg-v1": (14, 1_254),
            "rom-fixed-pair-tables-v1": (2, 42),
            "rom-prebattle-menu-controller-cfg-v1": (52, 1_920),
            "rom-scene-source-closures-v1": (73, 1_015),
        }
        rows = []
        for batch, denominator in expected.items():
            selected = [claim for claim in coverage["claims"]
                        if claim.get("promotion_batch") == batch]
            self.assertEqual(
                denominator,
                (len(selected), sum(claim["range"][1] - claim["range"][0]
                                    for claim in selected)),
                batch,
            )
            rows.extend(selected)
        rows.sort(key=lambda claim: claim["range"])
        self.assertTrue(all(left["range"][1] <= right["range"][0]
                            for left, right in zip(rows, rows[1:])))


class StoryDependencyFourPacketTier2CanonicalTests(unittest.TestCase):
    """The four queued dependency packets require a real canonical rebuild."""

    def test_canonical_contains_the_dependency_four_packet_batch(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        self.assertGreaterEqual(coverage["summary"]["classified_bytes"], 6_202_729)
        self.assertLessEqual(coverage["summary"]["unknown_bytes"], 88_727)
        self.assertGreaterEqual(coverage["summary"]["claim_count"], 16_870)
        expected = {
            "rom-story-callback-dependency-closures-v1": (32, 1_932),
            "rom-cfg-proven-roots-v20": (18, 1_150),
            "rom-story-next-dependency-cfg-v1": (19, 854),
            "rom-boot-register-init-dependency-cfg-v1": (8, 446),
        }
        rows = []
        for batch, denominator in expected.items():
            selected = [claim for claim in coverage["claims"]
                        if claim.get("promotion_batch") == batch]
            self.assertEqual(
                denominator,
                (len(selected), sum(claim["range"][1] - claim["range"][0]
                                    for claim in selected)),
                batch,
            )
            rows.extend(selected)
        rows.sort(key=lambda claim: claim["range"])
        self.assertTrue(all(left["range"][1] <= right["range"][0]
                            for left, right in zip(rows, rows[1:])))
        aggregate = coverage_auditor._cfg_code_aggregate(coverage["claims"])
        self.assertGreaterEqual(aggregate["cfg_reachable_thumb_code_bytes"], 172_148)
        self.assertGreaterEqual(aggregate["cfg_promoted_unknown_bytes"], 173_136)
        self.assertGreaterEqual(aggregate["cfg_primary_claim_count"], 4_048)
        self.assertGreaterEqual(aggregate["cfg_code_claim_kind_count"], 51)
        for start, end in (
            (0x06181E, 0x061820),
            (0x08859A, 0x08859C),
            (0x08860E, 0x088610),
            (0x08864A, 0x08864C),
            (0x088F52, 0x088F54),
            (0x089036, 0x089038),
        ):
            owner = next(
                row for row in coverage["segments"]
                if row["range"][0] <= start and end <= row["range"][1]
            )
            self.assertEqual("unknown", owner["primary_class"], (start, end))


class FourQueuedPacketTier2CanonicalTests(unittest.TestCase):
    """The real Tier-2 rebuild, not arithmetic-only packet projection."""

    def test_canonical_contains_the_disjoint_four_packet_batch(self):
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text())
        self.assertGreaterEqual(coverage["summary"]["classified_bytes"], 6_194_116)
        self.assertLessEqual(coverage["summary"]["unknown_bytes"], 97_340)
        self.assertGreaterEqual(coverage["summary"]["claim_count"], 16_652)
        self.assertGreaterEqual(coverage["summary"]["segment_count"], 18_332)
        expected = {
            "rom-boot-state-dispatcher-cfg-v1": (45, 2_532),
            "rom-fixed-animation-descriptor-groups-v1": (1, 1_136),
            "rom-battle-distance-dispatcher-cfg-v1": (14, 1_162),
            "rom-bounded-index-u16-pair-table-v1": (1, 32),
        }
        batch_claims = []
        for batch, denominator in expected.items():
            rows = [row for row in coverage["claims"]
                    if row.get("promotion_batch") == batch]
            self.assertEqual(
                denominator,
                (len(rows), sum(row["range"][1] - row["range"][0]
                                for row in rows)),
                batch,
            )
            batch_claims.extend(rows)
        batch_claims.sort(key=lambda row: row["range"])
        self.assertTrue(all(
            left["range"][1] <= right["range"][0]
            for left, right in zip(batch_claims, batch_claims[1:])
        ))
        right_gap = next(
            row for row in coverage["segments"]
            if row["range"][0] <= 0x53F30E
            and row["range"][1] >= 0x53F310
        )
        self.assertEqual("unknown", right_gap["primary_class"])

    def test_tier2_receipt_is_non_degraded_and_preserves_failed_first_run(self):
        run = ROOT / "build/experiments/active/four-packet-tier2-20260904"
        first = json.loads((run / "coverage-guard.json").read_text())
        accepted = json.loads((run / "coverage-r2-guard.json").read_text())
        self.assertEqual(("idle-timeout", 124, False),
                         (first["reason"], first["exit_code"], first["degraded"]))
        self.assertEqual(("completed", 0, False),
                         (accepted["reason"], accepted["exit_code"],
                          accepted["degraded"]))


if __name__ == "__main__":
    unittest.main()
