#!/usr/bin/env python3
"""Independently verify a rom-task-scheduler-core-v1 candidate packet."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone
from capstone import CS_AC_WRITE, CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-task-scheduler-core-v1"
VERIFY_SCHEMA = "rom-task-scheduler-core-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
# Immutable baseline identity remains separate from the raw-input guard so
# layered mutation tests can reach the contract that owns a changed byte.
BASE_ROM_SHA256 = ROM_SHA256
COVERAGE_SHA256 = "9ed94f7cab667383c136b6fdb11132d077329f8f6a67b74871ce32f4038b3529"
COVERAGE_BASELINE_CLAIMS_SHA256 = (
    "0c71da2d7abf2e4305bceda0fbdb96a95d3beb616d1fc6946ce3c599d9877df0"
)
COVERAGE_PROMOTION_BATCH = SCHEMA
COVERAGE_CODE_KIND = "task_scheduler_core_reachable_instruction_bytes"
COVERAGE_LITERAL_KIND = "task_scheduler_core_consumed_literal_bytes"
COVERAGE_PREDECESSOR_MANIFEST_SHA256 = (
    "fd2fb66d2cf1a18976ce2a5cebdfa086cbec86eee318866d1e2d290289ae3cfe"
)
COVERAGE_PREDECESSOR_PAYLOAD_SHA256 = (
    "44bade693dfce91c579e6d03dc45d7146f52ee2bf111ad4efd251a800d88c1cc"
)
COVERAGE_PREDECESSOR_VERIFIER_SHA256 = (
    "0b5d1e0f1965efed70f8fe874a23dec4ef404950deff5f45698402e45f9fd724"
)
COVERAGE_BASELINE_PROMOTION_BATCHES = frozenset(
    {
        "battle-controller-cfg-v1",
        "battle-effect-sprite-animation-source-v1",
        "cfg-proven-roots-v1",
        "cfg-proven-roots-v10",
        "cfg-proven-roots-v11",
        "cfg-proven-roots-v2",
        "cfg-proven-roots-v3",
        "cfg-proven-roots-v4",
        "cfg-proven-roots-v5",
        "cfg-proven-roots-v6",
        "cfg-proven-roots-v7",
        "cfg-proven-roots-v8",
        "cfg-proven-roots-v9",
        "cfg-v3-one-generation",
        "referenced-text-slot-padding-v1",
        "rom-battle-condition-records-v1",
        "rom-battle-presentation-tile-assets-alignment-gap-coverage-v1",
        "rom-battle-sound-selector-v1",
        "rom-boot-interwork-padding-coverage-v1",
        "rom-boot-thumb-handoff-cfg-v1",
        "rom-cutscene-obj-palette-definition-alignment-gap-coverage-v1",
        "rom-cutscene-obj-source-ranges-v1",
        "rom-dialogue-font-sjis-empty-lookup-rows-coverage-v1",
        "rom-direct-cpuset-bound-palette-coverage-v1",
        "rom-menu-portrait-palette-inventory-v1",
        "rom-motion-spawn-sequence-descriptor-alignment-gap-coverage-v1",
        "rom-parser-bound-zero-padding-v1",
        "rom-positions-aux-dispatch-v1",
        "rom-runtime-state-handler-table-alignment-gap-coverage-v1",
        "rom-scene-visual-source-ranges-v1",
        "rom-selector-code-windows-v1",
        "rom-u8-indexed-u16-pair-lookup-v1",
        "selector-direct-source-records-v1",
        "verified-artifact-reuse-v1",
    }
)
COVERAGE_POST_PROMOTION_TOTALS = {
    "classified_bytes": 6_121_280,
    "unknown_bytes": 170_176,
    "claim_count": 14_466,
    "segment_count": 16_577,
}
COVERAGE_POST_SEGMENTS_SHA256 = (
    "84eb46911614c696216a1a4c865bfa9b2a2d1dc60a726990eec8c7a12b674276"
)
COVERAGE_POST_SUMMARY_SHA256 = (
    "b9e738098cb1fd761f6373aae5daaa0791818984ddc5dc36ce9272d38e11c31d"
)
COVERAGE_POST_STATIC_SHA256 = (
    "5d1361a1f9201097e2130f7aaa2f785a3a8e2bc65a6251374368a040f25a1c22"
)
COVERAGE_BASELINE_LIMITATIONS_SHA256 = (
    "18990a43c20e783f3df5b9801f1df61cfeb6668f6128b02fb1af9ab0ebcb80b3"
)
COVERAGE_STATIC_CORE_SHA256 = (
    "af4304b2ac0ce0558eceb97218a4ba6881878de9c6d2fa0e24098178654fb6ca"
)
COVERAGE_LIMITATION = "The task scheduler core artifact classifies exactly 264 bounded Thumb instruction bytes and 44 consumed literal bytes; 138 already-owned bytes remain provenance and three two-byte gaps remain unknown. Dynamic callback targets, callback lifecycle, natural runtime reachability, global caller/code/indirect denominators, scheduler business semantics, editing, relocation, and allocatable space remain unclaimed."
COVERAGE_SCHEDULER_SUMMARY = {
    "task_scheduler_core_promotion_batch": SCHEMA,
    "task_scheduler_core_code_claim_kind": COVERAGE_CODE_KIND,
    "task_scheduler_core_literal_claim_kind": COVERAGE_LITERAL_KIND,
    "task_scheduler_core_code_bytes": 264,
    "task_scheduler_core_code_claim_count": 4,
    "task_scheduler_core_literal_bytes": 44,
    "task_scheduler_core_literal_claim_count": 3,
    "task_scheduler_core_promoted_bytes": 308,
    "task_scheduler_core_promotion_claim_count": 7,
    "task_scheduler_core_gap_bytes": 6,
    "task_scheduler_core_gap_range_count": 3,
    "task_scheduler_core_owned_provenance_bytes": 138,
    "task_scheduler_core_owned_provenance_range_count": 2,
    "task_scheduler_core_union_range_count": 3,
    "task_scheduler_core_union_range_vector_sha256": (
        "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f"
    ),
    "task_scheduler_core_frontier_count": 1,
    "task_scheduler_core_return_count": 12,
}
PAYLOAD_NAME = "rom-task-scheduler-core.json"
BUNDLE_NAME = "rom-task-scheduler-core.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("artifacts/rom-task-scheduler-core-v1")
COVERAGE_RECEIPT_ARTIFACT = ARTIFACT_RELATIVE
CANDIDATE_FINAL_RELATIVE = Path(
    "build/experiments/active/rom-task-scheduler-core-sorted-coverage-compat/"
    "codex-r1-20260827/final"
)
FINAL_RELATIVE = CANDIDATE_FINAL_RELATIVE

BOOT_PAYLOAD_PATH = Path("artifacts/rom-boot-thumb-handoff-cfg-v1/rom-boot-thumb-handoff-cfg.json")
BOOT_MANIFEST_PATH = Path("artifacts/rom-boot-thumb-handoff-cfg-v1/manifest.json")
BOOT_VERIFIER_PATH = Path("tools/verify_rom_boot_thumb_handoff_cfg.py")
BOOT_PAYLOAD_SHA256 = "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"
BOOT_MANIFEST_SHA256 = "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
BOOT_VERIFIER_SHA256 = "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39"
BOOT_BINARY_PATH = Path("artifacts/rom-boot-thumb-handoff-cfg-v1/rom-boot-thumb-handoff-cfg.bin")
BOOT_BINARY_SHA256 = "73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22"
BOOT_ENTRY_SELECTOR = "/entry_proofs/0x08061624"
BOOT_ENTRY_OFFSET = 0x061624
BOOT_ENTRY_OWNER_RANGE = [0x061624, 0x061710]
BOOT_SOURCE_CALLSITE = 0x060FE0
BOOT_SCHEDULER_SOURCE = 0x0616C0
BOOT_SCHEDULER_TARGET = 0x061D10

CODE_RANGES = [[0x061C58, 0x061C80], [0x061C8C, 0x061D10], [0x061D10, 0x061D62], [0x061D70, 0x061D7A]]
LITERAL_RANGES = [[0x061C80, 0x061C8C], [0x061D64, 0x061D70], [0x061DEC, 0x061E00]]
UNCLASSIFIED_RANGES = [[0x061D62, 0x061D64], [0x061D7A, 0x061D7C], [0x061DEA, 0x061DEC]]
OWNED_PROVENANCE = [
    {"range": [0x061D7C, 0x061DEA], "claim_id": "cfg-thumb-0000-061d7c", "primary_class": "armv4t_cfg_reachable_thumb_code", "sha256": "a95b7b4ebd38bd2422bad8c1ac40a932dae4f2173577b466152c8e1f0410660d"},
    {"range": [0x061E00, 0x061E1C], "claim_id": "cfg-thumb-0001-061e00", "primary_class": "armv4t_cfg_reachable_thumb_code", "sha256": "6561d7b14adb45317767fa3ade10b54cc0b3d384274a0c77e504d999e95eb9b9"},
]
PROVENANCE_CLAIM_SNAPSHOTS = {
    "consumer_code_slice": {
        "bytes_sha256": "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff",
        "claim_kind": "consumer_code_slice",
        "evidence_path": "artifacts/battle-effect-sprite-animations-v1/manifest.json",
        "evidence_selector": "/consumer_code_slices",
        "evidence_sha256": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
        "id": "consumer-code-battle_effect_sprite_animations-061624",
        "independent_verifier_path": "tools/verify_battle_effect_sprite_animations.py",
        "independent_verifier_sha256": "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b",
        "limitations": ["The bounded slice may include embedded literal-pool bytes; it is not asserted to be instruction-only."],
        "primary_class": "consumer_code_slice",
        "range": [398884, 399120],
        "role": "primary",
        "source_records": [{"evidence_selector": "/consumer_code_slices", "name": "runtime_offset_table_initializer", "range": [398884, 399120], "sha256": "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff"}],
    },
    "function_pointer_table": {
        "bank": "function-pointers",
        "bytes_sha256": "2c5f6f1dccc3248181cc28f4198720edef87daa580a40deba7ca9cd94f7ee11a",
        "claim_kind": "bank_record_bytes",
        "evidence_path": "sequel/content/function-pointers/bank.json",
        "evidence_sha256": "88a227b94198761bf47c925c5ea6527ceabbd17d8601eea5c9986c97ee6304b2",
        "id": "bank-function-pointers-000",
        "primary_class": "fixed_table",
        "range": [5494260, 5494304],
        "records": 11,
        "role": "primary",
    },
    "opaque_targets": {
        "0x0809C114": {
            "bytes_sha256": "bac8ca6ee9f77b46c7ab5824c7c59d99fd0ca53ae998ea2872b78bb6a5189cc5",
            "claim_kind": "cfg_reachable_instruction_bytes",
            "evidence_path": "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json",
            "evidence_selector": "/blocks",
            "evidence_sha256": "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
            "fixed_root_count": 263,
            "global_code_map_claimed": False,
            "graph_denominator_sha256": "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3",
            "id": "cfg-thumb-0775-09c114",
            "independent_verifier_path": "tools/verify_rom_cfg_inventory.py",
            "independent_verifier_sha256": "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93",
            "limitations": ["Only bytes reached from the fixed 263-root denominator and still unknown in the pre-CFG coverage baseline are promoted.", "Indirect targets, global function discovery, and natural runtime reachability remain unproven."],
            "mode": "thumb",
            "primary_class": "armv4t_cfg_reachable_thumb_code",
            "promoted_from_primary_class": "unknown",
            "promotion_manifest_path": "artifacts/rom-cfg-inventory-v2/manifest.json",
            "promotion_manifest_sha256": "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
            "range": [639252, 639254],
            "role": "primary",
            "runtime_reachability_claimed": False,
            "source_block_count": 1,
            "source_blocks": [{"block_id": "block-thumb-09c114", "range": [639252, 639254]}],
        },
        "0x0809C574": {
            "bytes_sha256": "aa1170db7a37e96c7cd2677a368bc6541819794ef3984f1d91b8b27914201f6e",
            "claim_kind": "cfg_reachable_instruction_bytes",
            "evidence_path": "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json",
            "evidence_selector": "/blocks",
            "evidence_sha256": "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
            "fixed_root_count": 263,
            "global_code_map_claimed": False,
            "graph_denominator_sha256": "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3",
            "id": "cfg-thumb-0786-09c574",
            "independent_verifier_path": "tools/verify_rom_cfg_inventory.py",
            "independent_verifier_sha256": "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93",
            "limitations": ["Only bytes reached from the fixed 263-root denominator and still unknown in the pre-CFG coverage baseline are promoted.", "Indirect targets, global function discovery, and natural runtime reachability remain unproven."],
            "mode": "thumb",
            "primary_class": "armv4t_cfg_reachable_thumb_code",
            "promoted_from_primary_class": "unknown",
            "promotion_manifest_path": "artifacts/rom-cfg-inventory-v2/manifest.json",
            "promotion_manifest_sha256": "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
            "range": [640372, 640374],
            "role": "primary",
            "runtime_reachability_claimed": False,
            "source_block_count": 1,
            "source_blocks": [{"block_id": "block-thumb-09c574", "range": [640372, 640374]}],
        },
    },
}
BOOT_ENTRY_PROOF_EXPECTED = {
    "edge_resolution": "opaque_external_entry",
    "entry": {"decoded": "push {r4,r5,lr}", "file_offset": 398884, "gba_address": "0x08061624", "mode": "thumb", "raw_hex": "30b5", "sha256": "0179fa50db01a670ea0d378b606928ed6b7a1f590c3fe52fcfe05a1936a84414"},
    "owner_claim_id": "consumer-code-battle_effect_sprite_animations-061624",
    "owner_limitation": "owner boundary is not instruction-only; direct BL plus first-instruction decode proves only the exact entry",
    "owner_primary_class": "consumer_code_slice",
    "owner_range": [398884, 399120],
    "source_and_fallthrough": [397280, 397284],
    "source_call": {"decoded": "bl 0x08061624", "fallthrough_offset": 397284, "file_offset": 397280, "gba_address": "0x08060FE0", "raw_hex": "00f020fb", "sha256": "863c2fdd72169166dddf0538761736276d44edd62cad291bd254410f0d545ddf", "target_offset": 398884},
    "target_scheduled": False,
}
CODE_SHA256 = {
    (0x061C58, 0x061C80): "d6f97ceb5dbe1e4e8754e114f112dd7f53970dfae43bad0b033c9d6a691038b1",
    (0x061C8C, 0x061D10): "b9637acd9938285609cc74c04ee173a63968d582b54f827c987959d1ffb6ec59",
    (0x061D10, 0x061D62): "5d12c1a3a0baca5ccd5b4954d11584f758fcbec878ff80ff62fcbe029e44cabc",
    (0x061D70, 0x061D7A): "0f2ccaffa103a304988869555af6236f0866af5f4f60f26fbbe2704bcf82e7bc",
}
LITERAL_SHA256 = {
    (0x061C80, 0x061C8C): "78e1b8b72d09201c9bcf8cc8a9a0426a0a815415d0526eace7069e122be6eced",
    (0x061D64, 0x061D70): "b44c66f532b78332e719eed4e93fba84fdf5e09b552c1ef4abe0a51230e619c1",
    (0x061DEC, 0x061E00): "4fdd345be5715be0cc303f492e8a6b916ff3849b4916a45c16885ec64682890d",
}
COVERAGE_CODE_SHA256 = dict(CODE_SHA256)
COVERAGE_LITERAL_SHA256 = dict(LITERAL_SHA256)
UNCLASSIFIED_SHA256 = "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
TABLE_SENTINEL_RANGE = [0x053D5F0, 0x053D624]
TABLE_RANGE = [0x053D5F4, 0x053D620]
TABLE_SENTINEL_SHA256 = "849702f76bd1741ec61eff7b24ed01f2d428d05a38ada31010b1f7823ccc13ba"
TABLE_SHA256 = "2c5f6f1dccc3248181cc28f4198720edef87daa580a40deba7ca9cd94f7ee11a"
VENEER_RANGE = [0x09C110, 0x09C11C]
VENEER_SHA256 = "c8d1aed5a733599658000ec7d89114ae60194ea47863ccedba181604312a7f5e"
ROOTS = [0x061C58, 0x061C8C, 0x061C98, 0x061CA4, 0x061CB0, 0x061CBC, 0x061CC8, 0x061CD4, 0x061CE0, 0x061CEC, 0x061CF8, 0x061D04, 0x061D10, 0x061D70]
WRAPPER_OFFSETS = [0x061C8C + index * 0x0C for index in range(11)]
WRAPPER_CALLSITES = [0x061C90 + index * 0x0C for index in range(11)]
EXPECTED_RETURNS = [0x061C96 + index * 0x0C for index in range(11)] + [0x061D60]
EXTERNAL_EDGES = {(0x061C6C, 0x09C114): "opaque_indirect_callback", (0x061C74, 0x061E00): "opaque_existing_entry", (0x061C7A, 0x09C574): "opaque_existing_entry", (0x061D4E, 0x061D7C): "opaque_existing_entry", (0x061D74, 0x09C574): "opaque_existing_entry"}
LITERAL_BINDINGS = [
    (0x061C5C, 0x061C80, 0x03000CE8, "candidate_code"), (0x061C64, 0x061C84, 0x03000D00, "candidate_code"), (0x061C70, 0x061C88, 0x03000A84, "candidate_code"),
    (0x061D18, 0x061D64, 0x08061D71, "candidate_code"), (0x061D1C, 0x061D68, 0x03000A88, "candidate_code"), (0x061D52, 0x061D6C, 0x03000D18, "candidate_code"), (0x061D54, 0x061D68, 0x03000A88, "candidate_code"),
    (0x061D98, 0x061DEC, 0x03000A88, "owned_provenance_code"), (0x061DB2, 0x061DF0, 0x03000D1C, "owned_provenance_code"), (0x061DB8, 0x061DF4, 0x03000CE8, "owned_provenance_code"), (0x061DC2, 0x061DF8, 0x03000D00, "owned_provenance_code"), (0x061DD4, 0x061DFC, 0x0853D5F0, "owned_provenance_code"),
]
REGISTRATION_CALLS = [(0x06106C, 1, 0x06107C, 0x0808F73D), (0x061D4E, 0, 0x061D64, 0x08061D71), (0x06EAC4, 2, 0x06EAD4, 0x0806E959), (0x07AAE0, 4, 0x07AB28, 0x0807A34D), (0x08599A, 1, 0x0859B4, 0x0808F73D), (0x085A08, 5, 0x085A14, 0x0808584D), (0x08C1E0, 2, 0x08C1F8, 0x0808C175), (0x08F1CE, 2, 0x08F204, 0x0808EF2D)]
REGISTRATION_INNER_CALLS = [0x061D84, 0x07C61C]
CLEANUP_CALLS = [0x061C74, 0x06EADC, 0x07AC26, 0x07C74A, 0x0858A2, 0x0858A8, 0x0858AE, 0x0858B4, 0x0859A0, 0x085A32, 0x08C200, 0x08F49E]
EXPECTED_SUMMARY = {"instruction_count": 116, "instruction_bytes": 264, "block_count": 33, "internal_edge_count": 33, "external_edge_count": 5, "external_target_count": 4, "literal_ref_count": 12, "literal_word_count": 11, "literal_bytes": 44, "return_count": 12, "raw_indirect_pc_count": 12, "frontier_count": 1, "budget_exhausted": False, "code_bytes": 264, "promoted_bytes": 308, "unclassified_unknown_bytes": 6, "owned_provenance_bytes": 138}
SCOPE = {"bounded_armv4t_thumb_cfg_rebuilt": True, "raw_opcode_control_flow_double_checked": True, "current_unknown_only_promotion": True, "code_and_consumed_literal_ranges_separate": True, "existing_owned_provenance_not_reclaimed": True, "direct_targets_opaque": True, "dynamic_callback_targets_resolved": False, "callback_lifecycle_closed": False, "computed_callback_producer_denominator_complete": False, "state_writer_inheritance_denominator_complete": False, "natural_runtime_reachable": False, "natural_execution_reachability_complete": False, "global_caller_denominator_complete": False, "global_code_denominator_complete": False, "global_indirect_target_denominator_complete": False, "scheduler_semantics_proven": False, "candidate_59eae0_table_safe": False, "candidate_59eae0_record_count_proven": False, "unclassified_ranges_are_padding_or_free": False, "editing_relocation_writeback_safe": False, "allocatable_free_space_proven": False}
LIMITATIONS = ["This packet proves only a bounded static Thumb CFG for the four listed code ranges and the PC-relative words they consume.", "Existing owned scheduler registration and cleanup code is provenance only and is not re-owned by this packet.", "The 0x0809C114 veneer is an explicit opaque indirect-callback frontier at BX r1; dynamic callback targets remain unresolved.", "Direct targets outside the packet are opaque; the packet does not prove callback lifecycle closure, natural reachability, or global caller/code/indirect denominators.", "The three 2-byte unclassified current-unknown ranges remain unknown; they are not classified as padding, reserved bytes, or free space.", "The 0x59EAE0 candidate table, record count, editor/writeback, relocation, and allocatable-space safety are outside scope."]
_ENGINES: dict[str, Cs] = {}
_EDGE_ORDER = {"branch_target": 0, "call_target": 1, "fallthrough": 2}
_THUMB_NAMES = ("ARM_INS_ADC", "ARM_INS_ADD", "ARM_INS_ADR", "ARM_INS_AND", "ARM_INS_ASR", "ARM_INS_B", "ARM_INS_BIC", "ARM_INS_BL", "ARM_INS_BX", "ARM_INS_CMN", "ARM_INS_CMP", "ARM_INS_EOR", "ARM_INS_LDM", "ARM_INS_LDMIA", "ARM_INS_LDMIB", "ARM_INS_LDR", "ARM_INS_LDRB", "ARM_INS_LDRH", "ARM_INS_LDRSB", "ARM_INS_LDRSH", "ARM_INS_LSL", "ARM_INS_LSR", "ARM_INS_MLA", "ARM_INS_MOV", "ARM_INS_MOVS", "ARM_INS_MUL", "ARM_INS_MVN", "ARM_INS_NEG", "ARM_INS_NOP", "ARM_INS_ORR", "ARM_INS_POP", "ARM_INS_PUSH", "ARM_INS_ROR", "ARM_INS_RSB", "ARM_INS_SBC", "ARM_INS_STMIA", "ARM_INS_STR", "ARM_INS_STRB", "ARM_INS_STRH", "ARM_INS_SUB", "ARM_INS_SUBS", "ARM_INS_SVC", "ARM_INS_TST", "ARM_INS_UXTH", "ARM_INS_REV")
THUMB_INSTRUCTION_IDS = frozenset(getattr(arm_const, name) for name in _THUMB_NAMES if hasattr(arm_const, name))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _bounded(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or start >= end or end > len(rom):
        raise ValueError(f"ROM range outside input: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _safe_file(root: Path, relative: str | Path) -> Path:
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative input: {relative}")
    path = root / relative
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"input path uses a symlink: {path}")
    if not path.is_file():
        raise ValueError(f"input file is missing: {path}")
    return path


def _root(root: Path) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir() or resolved != PROJECT_ROOT.resolve(strict=True):
        raise ValueError("repository root does not match the loaded project root")
    return resolved


def _engine() -> Cs:
    if "thumb" not in _ENGINES:
        engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        engine.detail = True
        engine.skipdata = False
        _ENGINES["thumb"] = engine
    return _ENGINES["thumb"]


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _writes_pc(instruction: Any) -> bool:
    for operand in instruction.operands:
        if operand.type == arm_const.ARM_OP_REG and operand.reg == arm_const.ARM_REG_PC and operand.access & CS_AC_WRITE:
            return True
    try:
        _, writes = instruction.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _conditional(instruction: Any) -> bool:
    condition = getattr(instruction, "cc", arm_const.ARM_CC_AL)
    return condition not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)


def _valid_thumb(raw: bytes, instruction: Any) -> bool:
    if instruction.id not in THUMB_INSTRUCTION_IDS:
        return False
    if instruction.size == 2:
        return len(raw) >= 2
    if instruction.size != 4 or len(raw) < 4:
        return False
    first = int.from_bytes(raw[:2], "little")
    second = int.from_bytes(raw[2:4], "little")
    return instruction.id == arm_const.ARM_INS_BL and first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def _raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    if len(raw) not in (2, 4):
        return None
    first = int.from_bytes(raw[:2], "little")
    if len(raw) == 4:
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {"flow_kind": "call", "size": 4, "conditional": False, "target_file_offset": offset + 4 + _sign_extend(encoded, 23)}
    if first & 0xFF00 == 0xDF00:
        return {"flow_kind": "supervisor_call", "size": 2, "conditional": False, "swi_immediate": first & 0xFF}
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return {"flow_kind": "conditional_branch", "size": 2, "conditional": True, "target_file_offset": offset + 4 + _sign_extend((first & 0xFF) << 1, 9)}
    if first & 0xF800 == 0xE000:
        return {"flow_kind": "unconditional_branch", "size": 2, "conditional": False, "target_file_offset": offset + 4 + _sign_extend((first & 0x07FF) << 1, 12)}
    if first & 0xFF87 == 0x4700:
        register = (first >> 3) & 0xF
        return {"flow_kind": "return" if register == 14 else "indirect_branch", "size": 2, "conditional": False, "register": register}
    return None


def _edge(kind: str, offset: int) -> dict[str, Any]:
    return {"kind": kind, "mode": "thumb", "file_offset": offset}


def _decode_one(rom: bytes, offset: int) -> dict[str, Any]:
    base = {"accepted": False, "mode": "thumb", "file_offset": offset}
    if offset < 0 or offset + 2 > len(rom) or offset % 2:
        return {**base, "frontier_reason": "misaligned_or_outside_entry"}
    decoded = tuple(_engine().disasm(rom[offset : offset + 4], ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        return {**base, "frontier_reason": "decode_failure"}
    instruction = decoded[0]
    raw = rom[offset : offset + instruction.size]
    if len(raw) != instruction.size or not _valid_thumb(raw, instruction):
        return {**base, "frontier_reason": "decode_failure"}
    flow = _raw_flow(raw, offset)
    if instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL, arm_const.ARM_INS_BX, arm_const.ARM_INS_SVC) and flow is None:
        return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    if flow is not None:
        expected = {"unconditional_branch": arm_const.ARM_INS_B, "conditional_branch": arm_const.ARM_INS_B, "call": arm_const.ARM_INS_BL, "return": arm_const.ARM_INS_BX, "indirect_branch": arm_const.ARM_INS_BX, "supervisor_call": arm_const.ARM_INS_SVC}[flow["flow_kind"]]
        if instruction.id != expected or instruction.size != flow["size"]:
            return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    end = offset + instruction.size
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    raw_indirect_pc = False
    if flow is not None and flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        kind = "call_target" if flow["flow_kind"] == "call" else "branch_target"
        target = flow["target_file_offset"]
        if 0 <= target < len(rom) and target % 2 == 0:
            successors.append(_edge(kind, target))
        else:
            frontiers.append({"reason": "direct_target_outside_or_misaligned", "target": {"mode": "thumb", "file_offset": target}})
        if flow["flow_kind"] in {"call", "conditional_branch"}:
            successors.append(_edge("fallthrough", end))
        flow_kind = flow["flow_kind"]
    elif flow is not None and flow["flow_kind"] == "supervisor_call":
        frontiers.append({"reason": "bios_swi_external", "swi_immediate": flow["swi_immediate"]})
        successors.append(_edge("fallthrough", end))
        flow_kind = "supervisor_call"
    elif flow is not None and flow["flow_kind"] in {"return", "indirect_branch"}:
        flow_kind = flow["flow_kind"]
        if flow_kind == "indirect_branch":
            raw_indirect_pc = True
            frontiers.append({"reason": "indirect_pc_target", "register": flow["register"]})
    elif _writes_pc(instruction):
        flow_kind = "return" if instruction.id == arm_const.ARM_INS_POP else "indirect_branch"
        if flow_kind == "indirect_branch":
            raw_indirect_pc = True
            frontiers.append({"reason": "indirect_pc_target"})
    else:
        flow_kind = "linear"
        successors.append(_edge("fallthrough", end))
    successors.sort(key=lambda item: (_EDGE_ORDER[item["kind"]], item["file_offset"]))
    return {**base, "accepted": True, "mode": "thumb", "file_offset": offset, "gba_address": _gba(offset), "size": instruction.size, "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "mnemonic": instruction.mnemonic, "op_str": instruction.op_str, "conditional": flow["conditional"] if flow is not None else _conditional(instruction), "flow_kind": flow_kind, "raw_flow_kind": flow["flow_kind"] if flow is not None else None, "raw_indirect_pc": raw_indirect_pc, "successors": successors, "frontiers": frontiers}


def _close_returns(rom: bytes, nodes: dict[int, dict[str, Any]]) -> None:
    incoming: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["file_offset"] in nodes:
                incoming[edge["file_offset"]].append((source, edge["kind"]))
    for offset, node in nodes.items():
        previous = nodes.get(offset - 2)
        if node.get("raw_flow_kind") != "indirect_branch" or node.get("mnemonic") != "bx" or previous is None:
            continue
        if incoming.get(offset) != [(offset - 2, "fallthrough")] or previous.get("flow_kind") != "linear" or previous.get("successors") != [_edge("fallthrough", offset)]:
            continue
        if _u16(rom, previous["file_offset"]) == 0xBC01 and _u16(rom, offset) == 0x4700:
            node["flow_kind"] = "return"
            node["frontiers"] = []


def _coverage_promotion_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, ranges in (("code", CODE_RANGES), ("literal", LITERAL_RANGES)):
        for index, interval in enumerate(ranges):
            start, end = interval
            rows.append(
                {
                    "id": f"scheduler-{kind}-{index:02d}-{start:06x}",
                    "range": [start, end],
                    "role": "primary",
                    "primary_class": (
                        "armv4t_task_scheduler_thumb_code"
                        if kind == "code"
                        else "thumb_pc_relative_consumed_literal"
                    ),
                    "claim_kind": (
                        COVERAGE_CODE_KIND
                        if kind == "code"
                        else COVERAGE_LITERAL_KIND
                    ),
                    "promotion_batch": COVERAGE_PROMOTION_BATCH,
                    "promoted_from_primary_class": "unknown",
                    "baseline_unknown_only": True,
                    "bytes_sha256": (
                        COVERAGE_CODE_SHA256[(start, end)]
                        if kind == "code"
                        else COVERAGE_LITERAL_SHA256[(start, end)]
                    ),
                }
            )
    return rows


def _expected_coverage_promotion_claims(root: Path) -> list[dict[str, Any]]:
    artifact_rows: list[dict[str, Any]] = []
    for kind, ranges in (("code", CODE_RANGES), ("literal", LITERAL_RANGES)):
        for index, interval in enumerate(ranges):
            start, end = interval
            artifact_rows.append(
                {
                    "baseline_unknown_only": True,
                    "id": f"scheduler-{kind}-{index:02d}-{start:06x}",
                    "kind": kind,
                    "range": [start, end],
                    "semantic_class": (
                        "armv4t_task_scheduler_thumb_code"
                        if kind == "code"
                        else "thumb_pc_relative_consumed_literal"
                    ),
                    "sha256": (
                        COVERAGE_CODE_SHA256[(start, end)]
                        if kind == "code"
                        else COVERAGE_LITERAL_SHA256[(start, end)]
                    ),
                    "size": end - start,
                }
            )

    payload_path = _safe_file(
        root, COVERAGE_RECEIPT_ARTIFACT / PAYLOAD_NAME
    )
    manifest_path = _safe_file(
        root, COVERAGE_RECEIPT_ARTIFACT / MANIFEST_NAME
    )
    payload_raw = payload_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    try:
        payload = json.loads(payload_raw.decode("utf-8"))
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage promotion receipt JSON changed") from error
    current_verifier_sha = _sha(
        _safe_file(root, "tools/verify_rom_task_scheduler_core.py").read_bytes()
    )
    receipt_verifier = manifest.get("implementation", {}).get("verifier")
    verifier_sha = (
        receipt_verifier.get("sha256")
        if isinstance(receipt_verifier, dict)
        else None
    )
    if (
        payload_raw != _canonical(payload)
        or manifest_raw != _canonical(manifest)
        or payload.get("schema") != SCHEMA
        or payload.get("promotion_ranges") != artifact_rows
        or payload.get("scope") != SCOPE
        or payload.get("limitations") != LIMITATIONS
        or manifest.get("schema") != PROMOTION_SCHEMA
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("scope") != SCOPE
        or manifest.get("limitations") != LIMITATIONS
        or manifest.get("files", {}).get(PAYLOAD_NAME)
        != {"sha256": _sha(payload_raw), "size": len(payload_raw)}
        or not isinstance(receipt_verifier, dict)
        or receipt_verifier.get("path")
        != "tools/verify_rom_task_scheduler_core.py"
        or verifier_sha
        not in {current_verifier_sha, COVERAGE_PREDECESSOR_VERIFIER_SHA256}
        or (
            verifier_sha == COVERAGE_PREDECESSOR_VERIFIER_SHA256
            and (
                _sha(payload_raw) != COVERAGE_PREDECESSOR_PAYLOAD_SHA256
                or _sha(manifest_raw)
                != COVERAGE_PREDECESSOR_MANIFEST_SHA256
            )
        )
    ):
        raise ValueError("coverage promotion receipt changed")

    non_claims = {key: value for key, value in SCOPE.items() if value is False}
    expected: list[dict[str, Any]] = []
    for index, row in enumerate(artifact_rows):
        start, end = row["range"]
        expected.append(
            {
                "id": row["id"],
                "range": [start, end],
                "gba_range": [ROM_BASE + start, ROM_BASE + end],
                "role": "primary",
                "primary_class": row["semantic_class"],
                "claim_kind": (
                    COVERAGE_CODE_KIND
                    if row["kind"] == "code"
                    else COVERAGE_LITERAL_KIND
                ),
                "mode": "thumb" if row["kind"] == "code" else None,
                "promotion_batch": COVERAGE_PROMOTION_BATCH,
                "promoted_from_primary_class": "unknown",
                "baseline_unknown_only": True,
                "bytes_sha256": row["sha256"],
                "artifact_range_id": row["id"],
                "artifact_range_kind": row["kind"],
                "promotion_union_range_count": 3,
                "promotion_union_bytes": 308,
                "promotion_union_range_vector_sha256": (
                    "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f"
                ),
                "evidence_path": (
                    ARTIFACT_RELATIVE / PAYLOAD_NAME
                ).as_posix(),
                "evidence_sha256": _sha(payload_raw),
                "evidence_selector": f"/promotion_ranges/{index}",
                "promotion_manifest_path": (
                    ARTIFACT_RELATIVE / MANIFEST_NAME
                ).as_posix(),
                "promotion_manifest_sha256": _sha(manifest_raw),
                "independent_verifier_path": (
                    "tools/verify_rom_task_scheduler_core.py"
                ),
                "independent_verifier_sha256": verifier_sha,
                "non_claims": non_claims,
                "limitations": LIMITATIONS,
            }
        )
    return expected


def _coverage_state(
    root: Path,
) -> tuple[dict[str, Any], bytearray, dict[str, dict[str, Any]]]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage baseline JSON changed") from error
    base = {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": BASE_ROM_SHA256}
    if value.get("schema") != "rom-byte-coverage-v1" or value.get("base_rom") != base:
        raise ValueError("coverage baseline contract changed")
    segments, claims = value.get("segments"), value.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("coverage baseline segments or claims missing")
    if any(not isinstance(claim, dict) for claim in claims):
        raise ValueError("coverage claim contract changed")

    promotion_rows = _coverage_promotion_rows()
    promotion_ids = {row["id"] for row in promotion_rows}
    promotion_kinds = {COVERAGE_CODE_KIND, COVERAGE_LITERAL_KIND}

    def scheduler_claim(claim: dict[str, Any]) -> bool:
        return (
            claim.get("promotion_batch") == COVERAGE_PROMOTION_BATCH
            or claim.get("claim_kind") in promotion_kinds
            or claim.get("id") in promotion_ids
        )

    promoted = [
        claim for claim in claims if scheduler_claim(claim)
    ]
    baseline_claims = [
        claim
        for claim in claims
        if not scheduler_claim(claim)
        and (
            claim.get("promotion_batch") is None
            or claim.get("promotion_batch")
            in COVERAGE_BASELINE_PROMOTION_BATCHES
        )
    ]
    future_claims = [
        claim
        for claim in claims
        if not scheduler_claim(claim)
        and claim.get("promotion_batch") is not None
        and claim.get("promotion_batch")
        not in COVERAGE_BASELINE_PROMOTION_BATCHES
    ]
    if _sha(_canonical(baseline_claims)) != COVERAGE_BASELINE_CLAIMS_SHA256:
        raise ValueError("coverage pre-promotion claim denominator changed")

    post_promotion = _sha(raw) != COVERAGE_SHA256
    if not post_promotion:
        if promoted:
            raise ValueError("coverage baseline unexpectedly contains scheduler claims")
    else:
        expected_claims = _expected_coverage_promotion_claims(root)
        predecessor_claims = [
            {
                **claim,
                "evidence_sha256": COVERAGE_PREDECESSOR_PAYLOAD_SHA256,
                "promotion_manifest_sha256": (
                    COVERAGE_PREDECESSOR_MANIFEST_SHA256
                ),
                "independent_verifier_sha256": (
                    COVERAGE_PREDECESSOR_VERIFIER_SHA256
                ),
            }
            for claim in expected_claims
        ]
        promoted_by_id = {claim.get("id"): claim for claim in promoted}

        def matches_expected(candidate: list[dict[str, Any]]) -> bool:
            by_id = {claim["id"]: claim for claim in candidate}
            return (
                len(promoted) == len(candidate)
                and set(promoted_by_id) == set(by_id)
                and all(
                    promoted_by_id[identifier] == expected
                    for identifier, expected in by_id.items()
                )
            )

        if not any(
            matches_expected(candidate)
            for candidate in (expected_claims, predecessor_claims)
        ):
            raise ValueError("coverage scheduler promotion denominator changed")
        summary = value.get("summary")
        static = {
            key: item
            for key, item in value.items()
            if key not in {"claims", "segments", "summary"}
        }
        coverage_limitations = value.get("limitations")
        static_core = {
            key: item
            for key, item in value.items()
            if key not in {"claims", "segments", "summary", "limitations"}
        }
        if (
            set(value)
            != {
                "base_rom",
                "claims",
                "domain",
                "limitations",
                "policy",
                "schema",
                "segments",
                "semantic_classification_complete",
                "state_inventory_complete",
                "summary",
            }
            or not isinstance(coverage_limitations, list)
            or len(coverage_limitations) < 27
            or _sha(_canonical(coverage_limitations[:26]))
            != COVERAGE_BASELINE_LIMITATIONS_SHA256
            or coverage_limitations[26] != COVERAGE_LIMITATION
            or any(
                not isinstance(item, str) or not item
                for item in coverage_limitations[27:]
            )
            or _sha(_canonical(static_core)) != COVERAGE_STATIC_CORE_SHA256
        ):
            raise ValueError("coverage post-promotion static contract changed")
        exact_post_promotion = not future_claims
        if exact_post_promotion and (
            _sha(_canonical(segments)) != COVERAGE_POST_SEGMENTS_SHA256
            or not isinstance(summary, dict)
            or _sha(_canonical(summary)) != COVERAGE_POST_SUMMARY_SHA256
            or _sha(_canonical(static)) != COVERAGE_POST_STATIC_SHA256
        ):
            raise ValueError("coverage exact post-promotion projection changed")
        if not isinstance(summary, dict) or any(
            summary.get(key) != expected
            for key, expected in COVERAGE_SCHEDULER_SUMMARY.items()
        ):
            raise ValueError("coverage scheduler summary changed")
        if exact_post_promotion:
            if any(
                summary.get(key) != expected
                for key, expected in COVERAGE_POST_PROMOTION_TOTALS.items()
            ):
                raise ValueError("coverage post-promotion totals changed")
        elif (
            summary.get("claim_count") != len(claims)
            or summary.get("segment_count") != len(segments)
            or not isinstance(summary.get("classified_bytes"), int)
            or not isinstance(summary.get("unknown_bytes"), int)
            or summary["classified_bytes"] + summary["unknown_bytes"] != ROM_SIZE
            or summary["classified_bytes"] < 6_121_280
            or summary["unknown_bytes"] > 170_176
        ):
            raise ValueError("coverage later-promotion totals changed")

        identifiers = [claim.get("id") for claim in claims]
        if (
            any(not isinstance(identifier, str) or not identifier for identifier in identifiers)
            or len(set(identifiers)) != len(identifiers)
        ):
            raise ValueError("coverage later-promotion claim identities changed")
        claims_by_id = {claim["id"]: claim for claim in claims}
        references_by_id = {
            identifier: {"primary": [], "secondary": []}
            for identifier in claims_by_id
        }
        for segment in segments:
            segment_range = segment.get("range")
            primary_class = segment.get("primary_class")
            if (
                not isinstance(segment_range, list)
                or len(segment_range) != 2
                or not all(isinstance(value, int) for value in segment_range)
                or segment_range[0] < 0
                or segment_range[0] >= segment_range[1]
                or segment_range[1] > ROM_SIZE
                or not isinstance(primary_class, str)
                or not primary_class
            ):
                raise ValueError("coverage later-promotion segment contract changed")
            primary_references = segment.get("primary_claim_ids", [])
            if (
                not isinstance(primary_references, list)
                or (primary_class == "unknown" and primary_references)
                or (primary_class != "unknown" and len(primary_references) != 1)
            ):
                raise ValueError("coverage later-promotion primary owner changed")
            for key, role in (
                ("primary_claim_ids", "primary"),
                ("secondary_claim_ids", "secondary"),
            ):
                references = segment.get(key, [])
                if (
                    not isinstance(references, list)
                    or any(
                        not isinstance(identifier, str) or not identifier
                        for identifier in references
                    )
                    or len(set(references)) != len(references)
                ):
                    raise ValueError(
                        "coverage later-promotion segment references changed"
                    )
                for identifier in references:
                    claim = claims_by_id.get(identifier)
                    claim_range = claim.get("range") if claim is not None else None
                    if (
                        claim is None
                        or claim.get("role") != role
                        or not isinstance(claim_range, list)
                        or len(claim_range) != 2
                        or not all(isinstance(value, int) for value in claim_range)
                        or claim_range[0] > segment_range[0]
                        or segment_range[1] > claim_range[1]
                        or (
                            role == "primary"
                            and claim.get("primary_class") != primary_class
                        )
                    ):
                        raise ValueError(
                            "coverage later-promotion segment reference contract changed"
                        )
                    references_by_id[identifier][role].append(segment_range)
        for identifier, claim in claims_by_id.items():
            role = claim.get("role")
            claim_range = claim.get("range")
            if role not in {"primary", "secondary"}:
                raise ValueError("coverage later-promotion claim role changed")
            matching_ranges = references_by_id[identifier][role]
            other_role = "secondary" if role == "primary" else "primary"
            if (
                not isinstance(claim_range, list)
                or len(claim_range) != 2
                or not matching_ranges
                or matching_ranges[0][0] != claim_range[0]
                or matching_ranges[-1][1] != claim_range[1]
                or any(
                    left[1] != right[0]
                    for left, right in zip(
                        matching_ranges, matching_ranges[1:], strict=False
                    )
                )
                or references_by_id[identifier][other_role]
            ):
                raise ValueError(
                    "coverage later-promotion claim projection changed"
                )
        promotion_intervals = [row["range"] for row in promotion_rows]
        for claim in future_claims:
            interval = claim.get("range")
            role = claim.get("role")
            promotion_batch = claim.get("promotion_batch")
            if (
                not isinstance(promotion_batch, str)
                or not promotion_batch
                or promotion_batch == COVERAGE_PROMOTION_BATCH
                or promotion_batch in COVERAGE_BASELINE_PROMOTION_BATCHES
                or not isinstance(interval, list)
                or len(interval) != 2
                or not all(isinstance(value, int) for value in interval)
                or interval[0] < 0
                or interval[0] >= interval[1]
                or interval[1] > ROM_SIZE
                or role not in {"primary", "secondary"}
            ):
                raise ValueError("coverage later-promotion claim contract changed")
            start, end = interval
            overlaps_scheduler = any(
                start < promotion_end and promotion_start < end
                for promotion_start, promotion_end in promotion_intervals
            )
            if role == "primary" and overlaps_scheduler:
                raise ValueError("coverage later primary claim overlaps scheduler promotion")
            matching = [
                segment
                for segment in segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            matching_ranges = [segment["range"] for segment in matching]
            primary_reference_ranges = [
                segment["range"]
                for segment in segments
                if claim["id"] in segment.get("primary_claim_ids", [])
            ]
            secondary_reference_ranges = [
                segment["range"]
                for segment in segments
                if claim["id"] in segment.get("secondary_claim_ids", [])
            ]
            projection_changed = (
                not matching
                or matching[0]["range"][0] != start
                or matching[-1]["range"][1] != end
            )
            if role == "primary":
                primary_class = claim.get("primary_class")
                projection_changed = projection_changed or (
                    not isinstance(primary_class, str)
                    or not primary_class
                    or any(
                        segment.get("primary_class") != primary_class
                        or segment.get("primary_claim_ids") != [claim["id"]]
                        for segment in matching
                    )
                    or primary_reference_ranges != matching_ranges
                    or bool(secondary_reference_ranges)
                )
            else:
                projection_changed = (
                    projection_changed
                    or secondary_reference_ranges != matching_ranges
                    or bool(primary_reference_ranges)
                )
            if projection_changed:
                raise ValueError(
                    "coverage later-promotion claim is not atomized"
                )
        if claims != sorted(
            claims, key=lambda claim: (claim["range"], claim["id"])
        ):
            raise ValueError("coverage later-promotion claims are not canonical")

    unknown = bytearray(ROM_SIZE)
    cursor = classified = unknown_count = 0
    for segment in segments:
        interval = segment.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or not isinstance(interval[1], int) or interval[1] <= interval[0] or interval[1] > ROM_SIZE:
            raise ValueError("coverage baseline partition changed")
        start, end = interval
        if segment.get("primary_class") == "unknown":
            unknown[start:end] = b"\1" * (end - start)
            unknown_count += end - start
        else:
            classified += end - start
        cursor = end
    exact_post_promotion = post_promotion and not future_claims
    expected_totals = (
        (
            COVERAGE_POST_PROMOTION_TOTALS["classified_bytes"],
            COVERAGE_POST_PROMOTION_TOTALS["unknown_bytes"],
        )
        if exact_post_promotion
        else (
            value["summary"]["classified_bytes"],
            value["summary"]["unknown_bytes"],
        )
        if post_promotion
        else (6_120_972, 170_484)
    )
    if (
        cursor != ROM_SIZE
        or (classified, unknown_count) != expected_totals
        or value.get("summary", {}).get("classified_bytes") != classified
        or value.get("summary", {}).get("unknown_bytes") != unknown_count
        or len(segments)
        != (
            COVERAGE_POST_PROMOTION_TOTALS["segment_count"]
            if exact_post_promotion
            else value["summary"]["segment_count"]
            if post_promotion
            else 16_568
        )
    ):
        raise ValueError("coverage baseline count changed")

    if post_promotion:
        for expected in promotion_rows:
            start, end = expected["range"]
            matching = [
                segment
                for segment in segments
                if segment["range"][0] < end and start < segment["range"][1]
            ]
            if (
                not matching
                or matching[0]["range"][0] != start
                or matching[-1]["range"][1] != end
                or any(
                    segment.get("primary_class") != expected["primary_class"]
                    or segment.get("primary_claim_ids") != [expected["id"]]
                    for segment in matching
                )
            ):
                raise ValueError(
                    f"coverage scheduler segment projection changed: {expected['id']}"
                )
            unknown[start:end] = b"\1" * (end - start)

    expected_targets = [
        {
            "range": [0x061AE4, 0x061D7C],
            "primary_class": "unknown",
            "primary_claim_ids": [],
        },
        {
            "range": [0x061D7C, 0x061DEA],
            "primary_class": "armv4t_cfg_reachable_thumb_code",
            "primary_claim_ids": ["cfg-thumb-0000-061d7c"],
        },
        {
            "range": [0x061DEA, 0x061E00],
            "primary_class": "unknown",
            "primary_claim_ids": [],
        },
        {
            "range": [0x061E00, 0x061E1C],
            "primary_class": "armv4t_cfg_reachable_thumb_code",
            "primary_claim_ids": ["cfg-thumb-0001-061e00"],
        },
    ]
    claim_map = {
        item.get("id"): item
        for item in baseline_claims
        if isinstance(item, dict)
    }
    for item in OWNED_PROVENANCE:
        claim = claim_map.get(item["claim_id"])
        if not isinstance(claim, dict) or claim.get("range") != item["range"] or claim.get("primary_class") != item["primary_class"] or claim.get("role") != "primary" or claim.get("bytes_sha256") != item["sha256"]:
            raise ValueError(f"owned provenance claim changed: {item['claim_id']}")
    return (
        {
            "path": "sequel/rom-byte-coverage.json",
            "sha256": COVERAGE_SHA256,
            "schema": value["schema"],
            "base_rom": base,
            "classified_bytes": 6_120_972,
            "unknown_bytes": 170_484,
            "segment_count": 16_568,
            "claim_count": 14_459,
            "target_segments": expected_targets,
        },
        unknown,
        claim_map,
    )


def _load_coverage(root: Path) -> tuple[dict[str, Any], bytearray]:
    coverage, unknown, _ = _coverage_state(root)
    return coverage, unknown


def _provenance_inputs(root: Path, rom: bytes) -> dict[str, Any]:
    _, _, claim_map = _coverage_state(root)
    snapshots = PROVENANCE_CLAIM_SNAPSHOTS
    for expected in (snapshots["consumer_code_slice"], snapshots["function_pointer_table"], *snapshots["opaque_targets"].values()):
        if claim_map.get(expected["id"]) != expected:
            raise ValueError(f"provenance claim snapshot changed: {expected['id']}")
        if _sha(_bounded(rom, *expected["range"])) != expected["bytes_sha256"]:
            raise ValueError(f"provenance bytes identity changed: {expected['id']}")
        evidence = _safe_file(root, expected["evidence_path"])
        if _sha(evidence.read_bytes()) != expected["evidence_sha256"]:
            raise ValueError(f"provenance evidence changed: {expected['id']}")
        verifier_path = expected.get("independent_verifier_path")
        if verifier_path is not None and _sha(_safe_file(root, verifier_path).read_bytes()) != expected.get("independent_verifier_sha256"):
            raise ValueError(f"provenance verifier changed: {expected['id']}")
        promotion_path = expected.get("promotion_manifest_path")
        if promotion_path is not None and _sha(_safe_file(root, promotion_path).read_bytes()) != expected.get("promotion_manifest_sha256"):
            raise ValueError(f"provenance promotion receipt changed: {expected['id']}")
    consumer = snapshots["consumer_code_slice"]
    return {
        "coverage": {"path": "sequel/rom-byte-coverage.json", "sha256": COVERAGE_SHA256, "schema": "rom-byte-coverage-v1"},
        "consumer_code_slice": {**consumer, "instruction_only": False, "owner_instruction_only": False},
        "function_pointer_table": dict(snapshots["function_pointer_table"]),
        "opaque_targets": {key: dict(value) for key, value in snapshots["opaque_targets"].items()},
    }


def _rebuild_boot_entry_to_scheduler(rom: bytes) -> dict[str, Any]:
    pending = [BOOT_ENTRY_OFFSET]
    scheduled = {BOOT_ENTRY_OFFSET}
    nodes: dict[int, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    opaque_calls: list[dict[str, Any]] = []
    reached_source = False
    while pending:
        offset = heapq.heappop(pending)
        if offset == BOOT_SCHEDULER_SOURCE:
            reached_source = True
            continue
        if offset < BOOT_ENTRY_OFFSET or offset >= BOOT_SCHEDULER_SOURCE or offset not in range(*BOOT_ENTRY_OWNER_RANGE) or offset % 2:
            raise ValueError("entry proof worklist escaped owner before scheduler source")
        node = _decode_one(rom, offset)
        if not node.get("accepted") or offset + node["size"] > BOOT_SCHEDULER_SOURCE or not all(BOOT_ENTRY_OWNER_RANGE[0] <= value < BOOT_ENTRY_OWNER_RANGE[1] for value in range(offset, offset + node["size"])):
            raise ValueError(f"entry proof decode failure before scheduler source: 0x{offset:06X}")
        if node.get("frontiers"):
            raise ValueError(f"entry proof frontier before scheduler source: 0x{offset:06X}")
        raw = _bounded(rom, offset, offset + node["size"])
        raw_flow = _raw_flow(raw, offset)
        if raw_flow is None and node.get("raw_flow_kind") is not None:
            raise ValueError(f"entry proof raw/control-flow mismatch: 0x{offset:06X}")
        if raw_flow is not None and raw_flow.get("flow_kind") != node.get("raw_flow_kind"):
            raise ValueError(f"entry proof raw/control-flow mismatch: 0x{offset:06X}")
        nodes[offset] = node
        normalized: list[dict[str, Any]] = []
        for edge in node["successors"]:
            target = edge["file_offset"]
            if edge["kind"] == "call_target":
                opaque_calls.append({"source_offset": offset, "target_offset": target, "kind": edge["kind"], "resolution": "opaque_direct_call"})
                normalized.append({**edge, "resolution": "opaque_direct_call"})
                continue
            if target == BOOT_SCHEDULER_SOURCE:
                reached_source = True
                normalized.append({**edge, "resolution": "internal_stop"})
                edges.append({"source_offset": offset, "kind": edge["kind"], "target_offset": target, "resolution": "internal_stop"})
                continue
            if target < BOOT_ENTRY_OFFSET or target >= BOOT_SCHEDULER_SOURCE or target % 2:
                raise ValueError(f"entry proof frontier before scheduler source: 0x{target:06X}")
            normalized.append({**edge, "resolution": "internal"})
            edges.append({"source_offset": offset, "kind": edge["kind"], "target_offset": target, "resolution": "internal"})
            if target not in scheduled:
                scheduled.add(target)
                heapq.heappush(pending, target)
        node["proof_successors"] = normalized
    if not reached_source:
        raise ValueError("entry proof scheduler source is not reachable")
    covered = {value for offset, node in nodes.items() for value in range(offset, offset + node["size"])}
    if covered != set(range(BOOT_ENTRY_OFFSET, BOOT_SCHEDULER_SOURCE)):
        raise ValueError("entry proof decode frontier or gap before scheduler source")
    predecessor_edges = [edge for edge in edges if edge["target_offset"] == BOOT_SCHEDULER_SOURCE]
    expected_predecessor = {"source_offset": BOOT_SCHEDULER_SOURCE - 2, "kind": "fallthrough", "target_offset": BOOT_SCHEDULER_SOURCE, "resolution": "internal_stop"}
    if predecessor_edges != [expected_predecessor]:
        raise ValueError("entry proof scheduler source boundary changed")
    instructions = []
    for offset in sorted(nodes):
        node = nodes[offset]
        instructions.append({"file_offset": offset, "gba_address": _gba(offset), "size": node["size"], "raw_hex": node["raw_hex"], "sha256": node["bytes_sha256"], "mnemonic": node["mnemonic"], "op_str": node["op_str"], "flow_kind": node["flow_kind"], "raw_flow_kind": node["raw_flow_kind"], "conditional": node["conditional"], "successors": node["proof_successors"]})
    return {
        "mode": "thumb", "root_offset": BOOT_ENTRY_OFFSET, "owner_range": list(BOOT_ENTRY_OWNER_RANGE), "range": [BOOT_ENTRY_OFFSET, BOOT_SCHEDULER_SOURCE], "stop_offset": BOOT_SCHEDULER_SOURCE, "stop_reason": "reachable_instruction_boundary", "instruction_count": len(instructions), "instruction_bytes": sum(item["size"] for item in instructions), "edge_count": len(edges), "frontier_count": 0, "raw_opcode_control_flow_double_checked": True, "literal_pool_decoded": False, "literal_loads_not_decoded": True, "instructions": instructions, "edges": edges, "opaque_calls": opaque_calls, "frontiers": [], "source_predecessor": expected_predecessor,
    }


def _boot_receipt(root: Path, rom: bytes) -> dict[str, Any]:
    payload_path = _safe_file(root, BOOT_PAYLOAD_PATH)
    manifest_path = _safe_file(root, BOOT_MANIFEST_PATH)
    if _sha(payload_path.read_bytes()) != BOOT_PAYLOAD_SHA256 or _sha(manifest_path.read_bytes()) != BOOT_MANIFEST_SHA256:
        raise ValueError("boot entry proof artifact identity changed")
    binary_path = _safe_file(root, BOOT_BINARY_PATH)
    if _sha(binary_path.read_bytes()) != BOOT_BINARY_SHA256:
        raise ValueError("boot entry proof binary identity changed")
    try:
        boot_payload = json.loads(payload_path.read_text())
        boot_manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("boot entry proof artifact is not valid JSON") from error
    expected_files = {BOOT_PAYLOAD_PATH.name: {"size": payload_path.stat().st_size, "sha256": BOOT_PAYLOAD_SHA256}, BOOT_BINARY_PATH.name: {"size": binary_path.stat().st_size, "sha256": BOOT_BINARY_SHA256}}
    if boot_manifest.get("artifact_schema") != "rom-boot-thumb-handoff-cfg-v1" or boot_manifest.get("artifact_status") != "accepted" or boot_manifest.get("files") != expected_files:
        raise ValueError("boot entry proof manifest contract changed")
    if boot_manifest.get("implementation", {}).get("verifier") != {"path": BOOT_VERIFIER_PATH.as_posix(), "sha256": BOOT_VERIFIER_SHA256}:
        raise ValueError("boot entry proof verifier identity changed")
    official = boot_payload.get("entry_proofs", {}).get(BOOT_ENTRY_SELECTOR.rsplit("/", 1)[-1])
    if boot_payload.get("schema") != "rom-boot-thumb-handoff-cfg-v1" or official != BOOT_ENTRY_PROOF_EXPECTED:
        raise ValueError("boot entry proof selector changed")
    entry_raw = _bounded(rom, BOOT_ENTRY_OFFSET, BOOT_ENTRY_OFFSET + 2)
    if entry_raw.hex() != BOOT_ENTRY_PROOF_EXPECTED["entry"]["raw_hex"] or _sha(entry_raw) != BOOT_ENTRY_PROOF_EXPECTED["entry"]["sha256"]:
        raise ValueError("boot entry proof entry bytes changed")
    source_raw = _bounded(rom, BOOT_SOURCE_CALLSITE, BOOT_SOURCE_CALLSITE + 4)
    if source_raw.hex() != BOOT_ENTRY_PROOF_EXPECTED["source_call"]["raw_hex"] or _sha(source_raw) != BOOT_ENTRY_PROOF_EXPECTED["source_call"]["sha256"] or _bl_target(rom, BOOT_SOURCE_CALLSITE) != BOOT_ENTRY_OFFSET:
        raise ValueError("boot entry proof source BL changed")
    if _sha(_bounded(rom, *BOOT_ENTRY_OWNER_RANGE)) != PROVENANCE_CLAIM_SNAPSHOTS["consumer_code_slice"]["bytes_sha256"]:
        raise ValueError("boot entry proof owner bytes changed")
    rebuild = _rebuild_boot_entry_to_scheduler(rom)
    source_node = _decode_one(rom, BOOT_SCHEDULER_SOURCE)
    source_raw = _bounded(rom, BOOT_SCHEDULER_SOURCE, BOOT_SCHEDULER_SOURCE + 4)
    if not source_node.get("accepted") or source_node.get("raw_flow_kind") != "call" or _bl_target(rom, BOOT_SCHEDULER_SOURCE) != BOOT_SCHEDULER_TARGET or source_raw.hex() != "00f026fb":
        raise ValueError("scheduler source boundary or BL changed")
    source_to_scheduler = {"file_offset": BOOT_SCHEDULER_SOURCE, "gba_address": _gba(BOOT_SCHEDULER_SOURCE), "raw_hex": source_raw.hex(), "sha256": _sha(source_raw), "decoded": "bl 0x08061D10", "target_offset": BOOT_SCHEDULER_TARGET, "target_gba_address": _gba(BOOT_SCHEDULER_TARGET), "fallthrough_offset": BOOT_SCHEDULER_SOURCE + 4, "target_scheduled": False}
    official_copy = json.loads(json.dumps(BOOT_ENTRY_PROOF_EXPECTED))
    return {"artifact": {"schema": "rom-boot-thumb-handoff-cfg-v1", "payload_path": BOOT_PAYLOAD_PATH.as_posix(), "payload_sha256": BOOT_PAYLOAD_SHA256, "manifest_path": BOOT_MANIFEST_PATH.as_posix(), "manifest_sha256": BOOT_MANIFEST_SHA256, "verifier_path": BOOT_VERIFIER_PATH.as_posix(), "verifier_sha256": BOOT_VERIFIER_SHA256, "entry_selector": BOOT_ENTRY_SELECTOR}, "official_entry_proof": official_copy, "entry": {**official_copy["entry"], "range": [BOOT_ENTRY_OFFSET, BOOT_ENTRY_OFFSET + 2]}, "source_call": official_copy["source_call"], "source_and_fallthrough": official_copy["source_and_fallthrough"], "owner_claim_id": official_copy["owner_claim_id"], "owner_range": list(BOOT_ENTRY_OWNER_RANGE), "owner_primary_class": official_copy["owner_primary_class"], "owner_instruction_only": False, "owner_limitation": official_copy["owner_limitation"], "target_scheduled": False, "edge_resolution": official_copy["edge_resolution"], "rebuild": rebuild, "source_to_scheduler": source_to_scheduler}


def _read_rom(root: Path, rom: bytes | None = None) -> bytes:
    raw = _safe_file(root, ROM_PATH).read_bytes() if rom is None else rom
    if len(raw) != ROM_SIZE or _sha(raw) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    return raw


def _check_ranges(rom: bytes, unknown: bytearray) -> None:
    for start, end in CODE_RANGES:
        if _sha(_bounded(rom, start, end)) != CODE_SHA256[(start, end)] or not all(unknown[start:end]):
            raise ValueError(f"candidate code range changed: 0x{start:06X}")
    for start, end in LITERAL_RANGES:
        if _sha(_bounded(rom, start, end)) != LITERAL_SHA256[(start, end)] or not all(unknown[start:end]):
            raise ValueError(f"candidate literal range changed: 0x{start:06X}")
    for start, end in UNCLASSIFIED_RANGES:
        if _sha(_bounded(rom, start, end)) != UNCLASSIFIED_SHA256 or not all(unknown[start:end]):
            raise ValueError(f"unclassified range changed: 0x{start:06X}")
    for item in OWNED_PROVENANCE:
        start, end = item["range"]
        if _sha(_bounded(rom, start, end)) != item["sha256"] or any(unknown[start:end]):
            raise ValueError(f"owned provenance changed: 0x{start:06X}")


def _cfg(rom: bytes) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    code = {offset for start, end in CODE_RANGES for offset in range(start, end)}
    pending = list(ROOTS)
    heapq.heapify(pending)
    scheduled = set(ROOTS)
    nodes: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset not in code or offset % 2:
            raise ValueError("CFG escaped frozen code ranges")
        node = _decode_one(rom, offset)
        if not node.get("accepted") or not all(value in code for value in range(offset, offset + node["size"])):
            raise ValueError(f"CFG decode failed at 0x{offset:06X}")
        nodes[offset] = node
        for edge in node["successors"]:
            target = edge["file_offset"]
            if target in code:
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, target)
            else:
                resolution = EXTERNAL_EDGES.get((offset, target))
                if edge["kind"] != "call_target" or resolution is None:
                    raise ValueError("unexpected CFG target")
                external.append({"source_instruction_offset": offset, "source_gba_address": _gba(offset), "kind": edge["kind"], "mode": "thumb", "target_offset": target, "target_gba_address": _gba(target), "target_scheduled": False, "resolution": resolution})
    covered = {value for offset, node in nodes.items() for value in range(offset, offset + node["size"])}
    if covered != code or len(nodes) != 116 or sum(node["size"] for node in nodes.values()) != 264:
        raise ValueError("instruction denominator changed")
    _close_returns(rom, nodes)
    if [offset for offset, node in sorted(nodes.items()) if node["flow_kind"] == "return"] != EXPECTED_RETURNS:
        raise ValueError("return denominator changed")
    if sorted((item["source_instruction_offset"], item["target_offset"]) for item in external) != sorted(EXTERNAL_EDGES):
        raise ValueError("external edge denominator changed")
    if _sha(_bounded(rom, *VENEER_RANGE)) != VENEER_SHA256 or _u16(rom, 0x09C114) != 0x4708:
        raise ValueError("BX r1 callback veneer changed")
    return nodes, external


def _blocks(nodes: dict[int, dict[str, Any]], external: list[dict[str, Any]], rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["file_offset"] in nodes:
                predecessors[edge["file_offset"]].append((source, edge["kind"]))
    starts = set(ROOTS)
    for offset, incoming in predecessors.items():
        if offset in starts:
            continue
        if len(incoming) != 1:
            starts.add(offset)
            continue
        source, _ = incoming[0]
        predecessor = nodes[source]
        if len(predecessor["successors"]) != 1 or predecessor["flow_kind"] != "linear" or source + predecessor["size"] != offset:
            starts.add(offset)
    blocks: list[dict[str, Any]] = []
    by_offset: dict[int, str] = {}
    for start in sorted(starts):
        members: list[int] = []
        offset = start
        while offset in nodes and offset not in by_offset:
            members.append(offset)
            by_offset[offset] = f"block-thumb-{start:06x}"
            node = nodes[offset]
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            target = node["successors"][0]["file_offset"]
            if target in starts or target != offset + node["size"]:
                break
            offset = target
        if not members:
            continue
        end = members[-1] + nodes[members[-1]]["size"]
        last = nodes[members[-1]]
        blocks.append({"id": by_offset[start], "mode": "thumb", "range": [start, end], "gba_range": [_gba(start), _gba(end)], "instruction_count": len(members), "bytes_sha256": _sha(_bounded(rom, start, end)), "terminator": {"file_offset": members[-1], "size": last["size"], "raw_hex": last["raw_hex"], "mnemonic": last["mnemonic"], "op_str": last["op_str"], "flow_kind": last["flow_kind"], "conditional": last["conditional"]}, "successors": []})
    if len(by_offset) != len(nodes) or len(blocks) != 33:
        raise ValueError("CFG control-flow block denominator changed")
    ext_by_source: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for edge in external:
        ext_by_source[edge["source_instruction_offset"]].append(edge)
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for edge in nodes[source]["successors"]:
            target = edge["file_offset"]
            if target in nodes:
                record = {"source_block_id": block["id"], "source_instruction_offset": source, "kind": edge["kind"], "mode": "thumb", "target_offset": target, "target_gba_address": _gba(target), "target_block_id": by_offset[target], "target_scheduled": True, "resolution": "internal"}
            else:
                matches = [item for item in ext_by_source[source] if item["kind"] == edge["kind"] and item["target_offset"] == target]
                if len(matches) != 1:
                    raise ValueError("external edge binding changed")
                record = {**matches[0], "source_block_id": block["id"]}
            block["successors"].append(record)
            edges.append(record)
    if sum(edge["resolution"] == "internal" for edge in edges) != 33 or len(edges) != 38:
        raise ValueError("edge denominator changed")
    return blocks, edges


def _literals(rom: bytes, nodes: dict[int, dict[str, Any]], unknown: bytearray) -> list[dict[str, Any]]:
    expected = {(consumer, literal): value for consumer, literal, value, _ in LITERAL_BINDINGS}
    result: list[dict[str, Any]] = []
    for consumer, literal, value, consumer_kind in LITERAL_BINDINGS:
        if consumer_kind == "candidate_code" and consumer not in nodes:
            raise ValueError("candidate literal consumer missing")
        if consumer_kind == "owned_provenance_code" and not 0x061D7C <= consumer < 0x061DEA:
            raise ValueError("owned literal consumer escaped provenance")
        raw_instruction = _bounded(rom, consumer, consumer + 2)
        if _u16(rom, consumer) & 0xF800 != 0x4800:
            raise ValueError(f"literal consumer changed: 0x{consumer:06X}")
        decoded = tuple(_engine().disasm(rom[consumer : consumer + 4], ROM_BASE + consumer, count=1))
        if len(decoded) != 1 or decoded[0].mnemonic != "ldr" or decoded[0].size != 2:
            raise ValueError("literal consumer decode changed")
        target = ((consumer + 4) & ~3) + (_u16(rom, consumer) & 0xFF) * 4
        if target != literal or _u32(rom, literal) != value or not all(unknown[literal : literal + 4]):
            raise ValueError("literal value or binding changed")
        word = _bounded(rom, literal, literal + 4)
        result.append({"instruction_offset": consumer, "instruction_gba_address": _gba(consumer), "instruction_raw_hex": raw_instruction.hex(), "instruction_sha256": _sha(raw_instruction), "mnemonic": decoded[0].mnemonic, "op_str": decoded[0].op_str, "literal_offset": literal, "literal_gba_address": _gba(literal), "literal_raw_hex": word.hex(), "literal_sha256": _sha(word), "raw_value": f"0x{value:08X}", "value": f"0x{value:08X}", "consumer_kind": consumer_kind})
    for offset in nodes:
        if _u16(rom, offset) & 0xF800 == 0x4800:
            target = ((offset + 4) & ~3) + (_u16(rom, offset) & 0xFF) * 4
            if (offset, target) not in expected:
                raise ValueError("unexpected candidate literal load")
    result.sort(key=lambda item: (item["literal_offset"], item["instruction_offset"]))
    if len(result) != 12 or len({item["literal_offset"] for item in result}) != 11:
        raise ValueError("literal denominator changed")
    return result


def _bl_target(rom: bytes, offset: int) -> int | None:
    if offset % 2 or offset + 4 > len(rom):
        return None
    first, second = _u16(rom, offset), _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    return offset + 4 + _sign_extend(((first & 0x07FF) << 12) | ((second & 0x07FF) << 1), 23)


_BL_CACHE: dict[int, tuple[bytes, dict[int, list[int]]]] = {}


def _find_bl(rom: bytes, target: int) -> list[int]:
    cached = _BL_CACHE.get(id(rom))
    if cached is None or cached[0] is not rom:
        targets = defaultdict(list)
        for offset in range(0, len(rom) - 3, 2):
            first, second = struct.unpack_from("<HH", rom, offset)
            if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
                encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
                targets[offset + 4 + _sign_extend(encoded, 23)].append(offset)
        # Retain the input object with its scan so a later short-lived
        # mutation cannot reuse an id for a different byte stream.
        _BL_CACHE[id(rom)] = (rom, targets)
    else:
        targets = cached[1]
    return list(targets.get(target, []))


def _occurrences(rom: bytes, needle: bytes) -> list[int]:
    result: list[int] = []
    offset = rom.find(needle)
    while offset >= 0:
        result.append(offset)
        offset = rom.find(needle, offset + 1)
    return result


def _producer(rom: bytes) -> dict[str, Any]:
    entry_calls = _find_bl(rom, 0x061D10)
    if entry_calls != [0x0616C0] or _bounded(rom, 0x0616C0, 0x0616C4).hex() != "00f026fb":
        raise ValueError("scheduler entry producer denominator changed")
    pointer_occurrences = _occurrences(rom, (ROM_BASE + 0x061D10 + 1).to_bytes(4, "little"))
    if pointer_occurrences:
        raise ValueError("scheduler entry pointer producer denominator changed")
    if _sha(_bounded(rom, *TABLE_SENTINEL_RANGE)) != TABLE_SENTINEL_SHA256 or _sha(_bounded(rom, *TABLE_RANGE)) != TABLE_SHA256:
        raise ValueError("wrapper table identity changed")
    cells = []
    for index, wrapper in enumerate(WRAPPER_OFFSETS):
        cell = TABLE_RANGE[0] + index * 4
        pointer = ROM_BASE + wrapper + 1
        occurrences = _occurrences(rom, pointer.to_bytes(4, "little"))
        if occurrences != [cell]:
            raise ValueError("wrapper pointer occurrence denominator changed")
        cells.append({"index": index, "cell_offset": cell, "cell_raw_hex": _bounded(rom, cell, cell + 4).hex(), "pointer": f"0x{pointer:08X}", "pointer_occurrences": occurrences, "wrapper_offset": wrapper, "wrapper_gba_address": _gba(wrapper)})
    wrapper_calls = _find_bl(rom, 0x061C58)
    if wrapper_calls != WRAPPER_CALLSITES:
        raise ValueError("wrapper BL denominator changed")
    wrapper_call_records = [{"callsite": offset, "raw_hex": _bounded(rom, offset, offset + 4).hex(), "target_offset": 0x061C58, "target_gba_address": _gba(0x061C58)} for offset in wrapper_calls]
    registration_calls = [item[0] for item in REGISTRATION_CALLS]
    if _find_bl(rom, 0x061D7C) != registration_calls:
        raise ValueError("registration wrapper BL denominator changed")
    registrations = []
    for callsite, slot, literal, pointer in REGISTRATION_CALLS:
        if _u32(rom, literal) != pointer:
            raise ValueError("registration literal changed")
        registrations.append({"callsite": callsite, "raw_hex": _bounded(rom, callsite, callsite + 4).hex(), "target_offset": 0x061D7C, "target_gba_address": _gba(0x061D7C), "slot": slot, "literal_offset": literal, "literal_raw_hex": _bounded(rom, literal, literal + 4).hex(), "pointer": f"0x{pointer:08X}"})
    inner = _find_bl(rom, 0x061D8C)
    cleanup = _find_bl(rom, 0x061E00)
    if inner != REGISTRATION_INNER_CALLS or cleanup != CLEANUP_CALLS:
        raise ValueError("registration inner or cleanup denominator changed")
    return {"scheduler_entry": {"entry_offset": 0x061D10, "entry_gba_address": _gba(0x061D10), "direct_thumb_bl_callsites": entry_calls, "direct_thumb_bl_callsite_raw_hex": _bounded(rom, 0x0616C0, 0x0616C4).hex(), "direct_thumb_pointer_occurrences": pointer_occurrences}, "wrapper_table": {"sentinel_range": TABLE_SENTINEL_RANGE, "sentinel_sha256": TABLE_SENTINEL_SHA256, "range": TABLE_RANGE, "sha256": TABLE_SHA256, "entry_count": 11, "stride": 4, "cells": cells}, "wrapper_to_common": {"target_offset": 0x061C58, "target_gba_address": _gba(0x061C58), "callsites": wrapper_call_records}, "registration_wrapper": {"target_offset": 0x061D7C, "callsites": registrations}, "registration_inner": {"target_offset": 0x061D8C, "callsites": [{"callsite": value, "raw_hex": _bounded(rom, value, value + 4).hex()} for value in inner]}, "cleanup": {"target_offset": 0x061E00, "callsites": [{"callsite": value, "raw_hex": _bounded(rom, value, value + 4).hex()} for value in cleanup]}, "slot_zero_binding": {"literal_offset": 0x061D64, "literal_raw_hex": _bounded(rom, 0x061D64, 0x061D68).hex(), "pointer": "0x08061D71", "registration_callsite": 0x061D4E, "registration_target_offset": 0x061D7C, "registration_slot": 0}}


def _ranges(intervals: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    values = {"exporter": "tools/export_rom_task_scheduler_core.py", "verifier": "tools/verify_rom_task_scheduler_core.py", "test": "tests/test_export_rom_task_scheduler_core.py"}
    return {role: {"path": path, "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in values.items()}


def _expected(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    root = _root(root)
    rom = _read_rom(root, rom)
    coverage, unknown = _load_coverage(root)
    _check_ranges(rom, unknown)
    nodes, external = _cfg(rom)
    blocks, edges = _blocks(nodes, external, rom)
    literals = _literals(rom, nodes, unknown)
    producer = _producer(rom)
    provenance_inputs = _provenance_inputs(root, rom)
    entry_proof = _boot_receipt(root, rom)
    records: list[dict[str, Any]] = []
    layout: list[dict[str, Any]] = []
    parts: list[bytes] = []
    bundle_offset = 0
    for kind, ranges in (("code", CODE_RANGES), ("literal", LITERAL_RANGES)):
        for index, (start, end) in enumerate(ranges):
            raw = _bounded(rom, start, end)
            sha = CODE_SHA256[(start, end)] if kind == "code" else LITERAL_SHA256[(start, end)]
            record = {"id": f"scheduler-{kind}-{index:02d}-{start:06x}", "kind": kind, "range": [start, end], "size": end - start, "sha256": sha, "semantic_class": "armv4t_task_scheduler_thumb_code" if kind == "code" else "thumb_pc_relative_consumed_literal", "baseline_unknown_only": True}
            records.append(record)
            layout.append({"kind": kind, "range": [start, end], "source_offset": start, "bundle_offset": bundle_offset, "size": end - start, "sha256": sha})
            parts.append(raw)
            bundle_offset += end - start
    bundle = b"".join(parts)
    union = _ranges([tuple(item) for item in [*CODE_RANGES, *LITERAL_RANGES]])
    promotion = {"code_range_count": 4, "code_bytes": 264, "literal_range_count": 3, "literal_bytes": 44, "union_range_count": 3, "union_bytes": 308, "union_ranges": union, "union_range_vector_sha256": _sha(_canonical(union)), "union_bytes_sha256": _sha(bundle), "current_known_overlap_bytes": 0, "unclassified_unknown_ranges": UNCLASSIFIED_RANGES, "unclassified_unknown_bytes": 6, "owned_provenance_ranges": [item["range"] for item in OWNED_PROVENANCE], "owned_provenance_bytes": 138, "future_coverage_claim_projection": {"code_claim_count": 4, "literal_claim_count": 3, "unclassified_claim_count": 0, "owned_claim_count": 0}}
    frontiers = [{"instruction_offset": 0x061C6C, "instruction_gba_address": _gba(0x061C6C), "raw_hex": _bounded(rom, 0x061C6C, 0x061C70).hex(), "reason": "opaque_indirect_callback_veneer", "veneer_range": VENEER_RANGE, "veneer_instruction_offset": 0x09C114, "veneer_raw_hex": _bounded(rom, 0x09C114, 0x09C116).hex(), "veneer_operation": "bx r1", "target_mode": "thumb", "target_resolution": "computed_or_indirect_unresolved"}]
    raw_indirect = [{"instruction_offset": offset, "instruction_gba_address": _gba(offset), "raw_hex": node["raw_hex"], "raw_flow_kind": node["raw_flow_kind"], "flow_kind": node["flow_kind"], "resolved_as_exact_return": node["flow_kind"] == "return"} for offset, node in sorted(nodes.items()) if node.get("raw_indirect_pc")]
    summary = {**EXPECTED_SUMMARY, "external_target_count": len({edge["target_offset"] for edge in edges if edge["resolution"] != "internal"}), "internal_edge_count": sum(edge["resolution"] == "internal" for edge in edges), "external_edge_count": sum(edge["resolution"] != "internal" for edge in edges), "literal_ref_count": len(literals), "literal_word_count": len({item["literal_offset"] for item in literals}), "literal_bytes": len({item["literal_offset"] for item in literals}) * 4, "return_count": sum(node["flow_kind"] == "return" for node in nodes.values()), "raw_indirect_pc_count": len(raw_indirect), "frontier_count": len(frontiers)}
    if summary != EXPECTED_SUMMARY:
        raise ValueError("scheduler summary changed")
    payload = {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": BASE_ROM_SHA256}, "coverage_baseline": coverage, "provenance_inputs": provenance_inputs, "entry_proof": entry_proof, "roots": [{"mode": "thumb", "file_offset": offset, "gba_address": _gba(offset)} for offset in ROOTS], "candidate_windows": [[0x061C58, 0x061D7C], [0x061DEA, 0x061E1C]], "code_ranges": CODE_RANGES, "literal_ranges": LITERAL_RANGES, "unclassified_unknown_ranges": UNCLASSIFIED_RANGES, "owned_provenance_ranges": [item["range"] for item in OWNED_PROVENANCE], "range_hashes": {"code": [{"range": value, "sha256": CODE_SHA256[tuple(value)]} for value in CODE_RANGES], "literal": [{"range": value, "sha256": LITERAL_SHA256[tuple(value)]} for value in LITERAL_RANGES], "unclassified_unknown": [{"range": value, "sha256": UNCLASSIFIED_SHA256} for value in UNCLASSIFIED_RANGES], "owned_provenance": OWNED_PROVENANCE}, "existing_owned_provenance": OWNED_PROVENANCE, "instructions": [nodes[offset] for offset in sorted(nodes)], "blocks": blocks, "edges": edges, "external_edges": [edge for edge in edges if edge["resolution"] != "internal"], "literal_bindings": literals, "frontiers": frontiers, "raw_indirect_pc_sites": raw_indirect, "producer_denominator": producer, "promotion_ranges": records, "coverage_claims": records, "packed_layout": layout, "packed_binary": {"file": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle), "layout": layout}, "promotion": promotion, "summary": summary, "scope": SCOPE, "limitations": LIMITATIONS, "implementation": _implementation(root)}
    return payload, bundle


def build_expected_payload(root: Path, rom: bytes, *, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], bytes]:
    """Rebuild the contract from raw bytes without consulting the exporter."""
    expected = _expected(root, rom)
    if payload is not None and payload.get("coverage_baseline") != expected[0]["coverage_baseline"]:
        raise ValueError("coverage identity in supplied payload changed")
    return expected


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not JSON") from error
    if not isinstance(value, dict) or raw != _canonical(value):
        raise ValueError(f"{label} JSON bytes are not canonical")
    return value, raw


def _artifact_dir(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path contains a symlink component")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("artifact path is not a directory")
    members = list(resolved.iterdir())
    if any(item.is_symlink() or not item.is_file() for item in members) or {item.name for item in members} != {PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME}:
        raise ValueError("artifact contains foreign files")
    return resolved


def _stable_report(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "verified": True, "errors": [], "summary": payload["summary"], "promotion": payload["promotion"]}


def _commands() -> tuple[list[str], list[str]]:
    return (["python3", "-I", "-S", "tools/export_rom_task_scheduler_core.py", "--root", ".", "--output-dir", ARTIFACT_RELATIVE.as_posix()], ["python3", "-I", "-S", "tools/verify_rom_task_scheduler_core.py", "--root", ".", "--artifact-dir", ARTIFACT_RELATIVE.as_posix()])


def verify_artifact(root: Path, artifact: Path, *, allow_candidate: bool = False) -> dict[str, Any]:
    try:
        root = _root(root)
        directory = _artifact_dir(Path(artifact))
        manifest, manifest_raw = _load_json(directory / MANIFEST_NAME, "manifest")
        payload, payload_raw = _load_json(directory / PAYLOAD_NAME, "payload")
        bundle = (directory / BUNDLE_NAME).read_bytes()
        expected_payload, expected_bundle = _expected(root, _read_rom(root))
        if payload != expected_payload:
            key = next((key for key in expected_payload if payload.get(key) != expected_payload[key]), "payload-shape")
            raise ValueError(f"payload {key} changed")
        if bundle != expected_bundle:
            raise ValueError("packed promotion binary changed")
        expected_files = {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}, BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}}
        if manifest.get("files") != expected_files:
            raise ValueError("manifest file receipt changed")
        statuses = {"accepted", "candidate"} if allow_candidate else {"accepted"}
        if manifest.get("schema") != PROMOTION_SCHEMA or manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") not in statuses:
            raise ValueError("manifest schema or status changed")
        projection = ("rom", "coverage_baseline", "provenance_inputs", "entry_proof", "promotion", "summary", "implementation", "scope", "limitations")
        if any(manifest.get(key) != payload[key] for key in projection):
            raise ValueError("manifest projection changed")
        producer_command, verifier_command = _commands()
        if manifest.get("producer") != {"command": producer_command, "implementation": payload["implementation"]}:
            raise ValueError("producer receipt changed")
        status = manifest["artifact_status"]
        report = None if status == "candidate" else _stable_report(payload)
        verification = {"schema": VERIFY_SCHEMA, "command": verifier_command, "exit_code": None if report is None else 0, "report": report, "verifier_sha256": payload["implementation"]["verifier"]["sha256"]}
        if manifest.get("verifier") != verification or manifest.get("verification") != verification:
            raise ValueError("verifier receipt changed")
        return _stable_report(payload)
    except Exception as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", "--artifact", dest="artifact", type=Path, required=True)
    parser.add_argument("--allow-candidate", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact, allow_candidate=args.allow_candidate)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
