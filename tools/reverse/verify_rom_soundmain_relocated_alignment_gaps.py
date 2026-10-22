#!/usr/bin/env python3
"""Verify three frozen align4 gaps inside the accepted SoundMain source packet.

The accepted SoundMain artifact deliberately excluded these bytes from its
semantic promotion.  This verifier binds only the raw two-byte gaps, the
immediately preceding frozen Thumb terminal, the align4 equation, and the
immediately following frozen structure.  It does not change or reinterpret
the 924-byte semantic packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


VERIFY_SCHEMA = "rom-soundmain-relocated-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-soundmain-relocated-alignment-gaps-v1"
PRIMARY_CLASS = "soundmain_relocated_artifact_bound_4byte_alignment_bytes"
CLAIM_KIND = "soundmain_relocated_alignment_gap_bytes"

ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

ARTIFACT_DIR = Path("artifacts/rom-soundmain-relocated-cfg-v1")
MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"
PAYLOAD_PATH = ARTIFACT_DIR / "rom-soundmain-relocated-cfg.json"
BINARY_PATH = ARTIFACT_DIR / "rom-soundmain-relocated-cfg.bin"
BUNDLE_VERIFIER_PATH = Path("tools/verify_rom_soundmain_relocated_cfg_bundle.py")

MANIFEST_SHA256 = "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37"
MANIFEST_SIZE = 15_878
PAYLOAD_SHA256 = "63543ece1982ced20eb0818faf3b6f1848e72ba6dcdb68105fa8b2e3e07e477a"
PAYLOAD_SIZE = 352_934
BINARY_SHA256 = "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331"
BINARY_SIZE = 924
BUNDLE_VERIFIER_SHA256 = (
    "312104efd51f2d4cc262aeebe4e06563c71d2d50f54d3a2aa180cd13cfb34199"
)
BUNDLE_VERIFIER_SIZE = 10_678

RANGE_VECTOR = (
    (0x099E1A, 0x099E1C),
    (0x099EC2, 0x099EC4),
    (0x099FA6, 0x099FA8),
)
RANGE_VECTOR_SHA256 = (
    "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af"
)
PACKED_BYTES_SHA256 = (
    "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44"
)
ZERO_PAIR_SHA256 = (
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
)

BOUNDARY_VECTOR = (
    {
        "id": "soundmain-thumb-to-arm-099e1a",
        "left_block_id": "block-thumb-099e16",
        "left_range": [630_294, 630_298],
        "terminal_range": [630_296, 630_298],
        "terminal_raw_hex": "0847",
        "flow_kind": "mode_switch",
        "mnemonic": "bx",
        "op_str": "r1",
        "target_offset": 630_300,
        "gap_range": [630_298, 630_300],
        "right_kind": "arm_block",
        "right_id": "block-arm-099e1c",
        "right_range": [630_300, 630_316],
    },
    {
        "id": "soundmain-branch-to-literal-099ec2",
        "left_block_id": "block-thumb-099ec0",
        "left_range": [630_464, 630_466],
        "terminal_range": [630_464, 630_466],
        "terminal_raw_hex": "6be1",
        "flow_kind": "unconditional_branch",
        "mnemonic": "b",
        "op_str": "#0x3007b52",
        "target_offset": 631_194,
        "gap_range": [630_466, 630_468],
        "right_kind": "consumed_literal_range",
        "right_id": "soundmain-literal-00-099ec4",
        "right_range": [630_468, 630_472],
    },
    {
        "id": "soundmain-thumb-to-arm-099fa6",
        "left_block_id": "block-thumb-099f9c",
        "left_range": [630_684, 630_694],
        "terminal_range": [630_692, 630_694],
        "terminal_raw_hex": "0047",
        "flow_kind": "mode_switch",
        "mnemonic": "bx",
        "op_str": "r0",
        "target_offset": 630_696,
        "gap_range": [630_694, 630_696],
        "right_kind": "arm_block",
        "right_id": "block-arm-099fa8",
        "right_range": [630_696, 630_728],
    },
)
BOUNDARY_VECTOR_SHA256 = (
    "2f21e70062013bff5f99a9191920f3a6b4ee8996fd1adb0d8cfe577f7d450dd4"
)

CLAIM_DENOMINATOR_VECTOR = tuple(
    {
        "id": row["id"],
        "range": row["gap_range"],
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "left_block_id": row["left_block_id"],
        "right_id": row["right_id"],
    }
    for row in BOUNDARY_VECTOR
)
CLAIM_DENOMINATOR_SHA256 = (
    "ed6703a2245ca526dc40809dafbaa65328faec20f5aa493ab735ab70128cbd6c"
)

SOURCE_FILE_VECTOR = (
    {
        "path": MANIFEST_PATH.as_posix(),
        "sha256": MANIFEST_SHA256,
        "size": MANIFEST_SIZE,
    },
    {
        "path": PAYLOAD_PATH.as_posix(),
        "sha256": PAYLOAD_SHA256,
        "size": PAYLOAD_SIZE,
    },
    {
        "path": BINARY_PATH.as_posix(),
        "sha256": BINARY_SHA256,
        "size": BINARY_SIZE,
    },
    {
        "path": BUNDLE_VERIFIER_PATH.as_posix(),
        "sha256": BUNDLE_VERIFIER_SHA256,
        "size": BUNDLE_VERIFIER_SIZE,
    },
)
SOURCE_FILE_VECTOR_SHA256 = (
    "94d5aa4caa9f45d802f4cecde10d1f08ee4c5650a0c4f24bf40707f2ca1888a2"
)

EXPECTED_MANIFEST_KEYS = {
    "acceptance",
    "artifact_schema",
    "artifact_status",
    "copy_operation",
    "coverage_baseline",
    "files",
    "implementation",
    "limitations",
    "producer",
    "producer_denominator",
    "promotion",
    "rom",
    "schema",
    "scope",
    "source",
    "summary",
    "verification",
    "verifier",
}
EXPECTED_PAYLOAD_KEYS = {
    "cfg",
    "copy_operation",
    "coverage_baseline",
    "coverage_claims",
    "implementation",
    "limitations",
    "packed_binary",
    "packed_layout",
    "producer_denominator",
    "promotion",
    "promotion_ranges",
    "rom",
    "schema",
    "scope",
    "source",
    "summary",
}
EXPECTED_CFG_KEYS = {
    "alignment_gap_ranges",
    "block_edges",
    "blocks",
    "code_ranges",
    "external_edges",
    "identities",
    "instructions",
    "literal_bindings",
    "literal_ranges",
    "mode_switches",
    "owned_provenance_ranges",
    "root",
    "runtime_mapping",
    "summary",
}
EXPECTED_PROMOTION_RANGES = (
    (
        "soundmain-code-00-099e10",
        "code",
        [630_288, 630_298],
        "24afedc6cdbff9b7b4321f2e09ef10e899779307190eb09ceeaede96534e68ae",
    ),
    (
        "soundmain-code-01-099e1c",
        "code",
        [630_300, 630_466],
        "28ceffde8c9efededde19ed0651c4dd7fd191443f26a1c24ceaadf2361a5f620",
    ),
    (
        "soundmain-literal-00-099ec4",
        "literal",
        [630_468, 630_472],
        "2d04e57c5e80a3ae7f289b8ac025839a5b75d659b747ccd7e446f77e711a6663",
    ),
    (
        "soundmain-code-02-099ec8",
        "code",
        [630_472, 630_694],
        "c804dcedcd92c3a0ec788ecb255aa1637ecdc838b9f1029c08ccb5cfb9fdea5e",
    ),
    (
        "soundmain-code-03-099fa8",
        "code",
        [630_696, 631_214],
        "34a9c442a64856a9eb8636a5d249a146260af74fe828dbbd338fe263eea90427",
    ),
    (
        "soundmain-literal-01-09a1b0",
        "literal",
        [631_216, 631_220],
        "ee88b5a804fd87fa74b205951cfcc811ef5cdb452c4ad7f7cd1456fc90d71b90",
    ),
)
EXPECTED_TARGET_BLOCK_IDS = (
    "block-arm-099e1c",
    "block-thumb-09a19a",
    "block-arm-099fa8",
)
EXPECTED_LITERAL_RANGES = (
    (630_468, 630_472),
    (631_216, 631_220),
)
EXPECTED_LITERAL_BINDINGS = (
    {
        "instruction_mode": "thumb",
        "instruction_offset": 630_450,
        "instruction_runtime_address": "0x0300786A",
        "literal_offset": 630_468,
        "literal_runtime_address": "0x0300787C",
        "raw_hex": "06000004",
        "value": "0x04000006",
    },
    {
        "instruction_mode": "thumb",
        "instruction_offset": 631_196,
        "instruction_runtime_address": "0x03007B54",
        "literal_offset": 631_216,
        "literal_runtime_address": "0x03007B68",
        "raw_hex": "536d7368",
        "value": "0x68736D53",
    },
)

NON_CLAIM_KEYS = (
    "padding_semantics_claimed",
    "nop_instruction_claimed",
    "gap_instruction_semantics_claimed",
    "reserved_space_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
    "natural_runtime_reachability_claimed",
    "global_unreachability_claimed",
    "compiler_authorship_claimed",
    "editing_writeback_relocation_safe_claimed",
    "right_structure_semantics_extended_claimed",
    "all_alignment_gaps_exhaustive_claimed",
)
NON_CLAIMS = {key: False for key in NON_CLAIM_KEYS}
LIMITATIONS = (
    "Only the three listed two-byte ranges are classified as bytes required to reach each immediately following align4-bound frozen structure.",
    "The bytes are not claimed to be instructions, NOPs, padding, reserved space, free space, or allocatable space.",
    "The accepted 924-byte semantic packet remains unchanged, and no right-hand code or literal semantics are extended.",
    "Natural runtime reachability, global unreachability, compiler authorship, editing, writeback, relocation safety, and an exhaustive SoundMain gap denominator remain unclaimed.",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _safe_root(raw_root: Path) -> Path:
    candidate = Path(raw_root)
    if candidate.is_symlink():
        raise ValueError("repository root must not be a symlink")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    return resolved


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"source file must not be a symlink: {relative}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"source path escapes repository root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"source path is not a file: {relative}")
    return resolved


def _empty_report(errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": list(errors or []),
        "promotion_batch": PROMOTION_BATCH,
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "gap_count": 3,
        "byte_count": 6,
        "zero_byte_count": 0,
        "ranges": [list(pair) for pair in RANGE_VECTOR],
        "range_vector_sha256": RANGE_VECTOR_SHA256,
        "boundary_vector_sha256": BOUNDARY_VECTOR_SHA256,
        "claim_denominator_sha256": CLAIM_DENOMINATOR_SHA256,
        "source_file_vector_sha256": SOURCE_FILE_VECTOR_SHA256,
        "packed_bytes_sha256": None,
        "source_artifact_count": 1,
        "source_bundle_verified": False,
        "source_files": {},
        "gaps": [],
        "all_alignment_equations_hold": False,
        "all_boundaries_exact": False,
        "semantic_packet_modified": False,
        "non_claims": dict(NON_CLAIMS),
        "limitations": list(LIMITATIONS),
    }


def _add_error(errors: list[str], message: str) -> None:
    if message not in errors:
        errors.append(message)


def _validate_static_vectors(errors: list[str]) -> None:
    checks = (
        (_sha(_canonical([list(pair) for pair in RANGE_VECTOR])), RANGE_VECTOR_SHA256, "range vector"),
        (_sha(_canonical(list(BOUNDARY_VECTOR))), BOUNDARY_VECTOR_SHA256, "boundary vector"),
        (
            _sha(_canonical(list(CLAIM_DENOMINATOR_VECTOR))),
            CLAIM_DENOMINATOR_SHA256,
            "claim denominator",
        ),
        (
            _sha(_canonical(list(SOURCE_FILE_VECTOR))),
            SOURCE_FILE_VECTOR_SHA256,
            "source file vector",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            _add_error(errors, f"frozen {label} identity changed")


def _validate_bundle_report(
    bundle_report: Any, payload: dict[str, Any], errors: list[str]
) -> bool:
    if not isinstance(bundle_report, dict):
        _add_error(errors, "SoundMain bundle receipt is not an object")
        return False
    required_true = (
        "verified",
        "artifact_bundle_verified",
        "legacy_receipt_verified",
        "candidate_identity_verified",
    )
    for key in required_true:
        if bundle_report.get(key) is not True:
            _add_error(errors, f"SoundMain bundle receipt {key} changed")
    expected = {
        "schema": "rom-soundmain-relocated-cfg-bundle-verification-v1",
        "errors": [],
        "artifact_schema": "rom-soundmain-relocated-cfg-v1",
        "artifact_status": "accepted",
        "live_coverage_verified": False,
        "rom_sha256": ROM_SHA256,
        "promotion_bytes": 924,
        "promotion_claim_count": 6,
        "promotion_range_count": 6,
        "promotion_union_range_count": 5,
        "deferred_alignment_gap_bytes": 6,
        "promotion_packed_sha256": BINARY_SHA256,
        "accepted_manifest_sha256": MANIFEST_SHA256,
        "candidate_manifest_sha256": "16aedff95afaf1e24f49cd74c01ded1f46433a79b5b708145dfa9a582fd2fa28",
        "legacy_verifier_sha256": "321d5ca5b7d6f887a21ec93c1bb06640f6e1397248273068bb5a13d3d7167d82",
        "bundle_verifier_sha256": BUNDLE_VERIFIER_SHA256,
    }
    for key, value in expected.items():
        if bundle_report.get(key) != value:
            _add_error(errors, f"SoundMain bundle receipt {key} changed")
    if bundle_report.get("summary") != payload.get("summary"):
        _add_error(errors, "SoundMain bundle summary changed")
    if bundle_report.get("promotion") != payload.get("promotion"):
        _add_error(errors, "SoundMain bundle promotion changed")
    return not any("bundle" in error for error in errors)


def verify_inputs(
    rom: bytes,
    *,
    manifest: Any,
    payload: Any,
    binary: bytes,
    bundle_report: Any,
) -> dict[str, Any]:
    report = _empty_report()
    errors = report["errors"]
    _validate_static_vectors(errors)

    if not isinstance(rom, bytes):
        _add_error(errors, "ROM input is not bytes")
        return report
    if len(rom) != ROM_SIZE:
        _add_error(errors, "ROM size changed")
    if _sha(rom) != ROM_SHA256:
        _add_error(errors, "ROM identity changed")

    if not isinstance(manifest, dict):
        _add_error(errors, "accepted manifest is not an object")
        return report
    if set(manifest) != EXPECTED_MANIFEST_KEYS:
        _add_error(errors, "accepted manifest key denominator changed")
    if manifest.get("schema") != "git-artifact-promotion-v1":
        _add_error(errors, "accepted manifest schema changed")
    if manifest.get("artifact_schema") != "rom-soundmain-relocated-cfg-v1":
        _add_error(errors, "accepted artifact schema changed")
    if manifest.get("artifact_status") != "accepted":
        _add_error(errors, "accepted artifact status changed")
    try:
        manifest_raw = _canonical_json_bytes(manifest)
    except (TypeError, ValueError):
        _add_error(errors, "accepted manifest is not canonical JSON")
    else:
        if len(manifest_raw) != MANIFEST_SIZE or _sha(manifest_raw) != MANIFEST_SHA256:
            _add_error(errors, "accepted manifest canonical identity changed")

    if not isinstance(payload, dict):
        _add_error(errors, "accepted payload is not an object")
        return report
    if set(payload) != EXPECTED_PAYLOAD_KEYS:
        _add_error(errors, "accepted payload key denominator changed")
    if payload.get("schema") != "rom-soundmain-relocated-cfg-v1":
        _add_error(errors, "accepted payload schema changed")
    if payload.get("rom") != {
        "path": "rom/base.gba",
        "sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
        "size": ROM_SIZE,
    }:
        _add_error(errors, "accepted payload ROM identity changed")
    if manifest.get("summary") != payload.get("summary"):
        _add_error(errors, "manifest/payload summary binding changed")
    if manifest.get("promotion") != payload.get("promotion"):
        _add_error(errors, "manifest/payload promotion binding changed")
    try:
        payload_raw = _canonical_json_bytes(payload)
    except (TypeError, ValueError):
        _add_error(errors, "accepted payload is not canonical JSON")
    else:
        if len(payload_raw) != PAYLOAD_SIZE or _sha(payload_raw) != PAYLOAD_SHA256:
            _add_error(errors, "accepted payload canonical identity changed")

    promotion = payload.get("promotion")
    if not isinstance(promotion, dict):
        _add_error(errors, "SoundMain promotion is not an object")
        promotion = {}
    if promotion.get("deferred_alignment_gap_ranges") != [
        list(pair) for pair in RANGE_VECTOR
    ]:
        _add_error(errors, "SoundMain deferred gap denominator changed")
    if promotion.get("deferred_alignment_gap_bytes") != 6:
        _add_error(errors, "SoundMain deferred gap byte count changed")
    if promotion.get("alignment_gap_requires_accepted_immutable_artifact") is not True:
        _add_error(errors, "SoundMain post-acceptance gap gate changed")
    if promotion.get("semantic_bytes") != 924:
        _add_error(errors, "SoundMain semantic byte denominator changed")
    if promotion.get("semantic_claim_count") != 6:
        _add_error(errors, "SoundMain semantic claim denominator changed")
    if promotion.get("semantic_packed_sha256") != BINARY_SHA256:
        _add_error(errors, "SoundMain semantic packed identity changed")

    cfg = payload.get("cfg")
    if not isinstance(cfg, dict):
        _add_error(errors, "SoundMain CFG is not an object")
        cfg = {}
    if set(cfg) != EXPECTED_CFG_KEYS:
        _add_error(errors, "SoundMain CFG key denominator changed")
    if cfg.get("alignment_gap_ranges") != [list(pair) for pair in RANGE_VECTOR]:
        _add_error(errors, "SoundMain CFG gap denominator changed")
    if cfg.get("literal_ranges") != [list(pair) for pair in EXPECTED_LITERAL_RANGES]:
        _add_error(errors, "SoundMain CFG literal range denominator changed")
    if cfg.get("literal_bindings") != [dict(row) for row in EXPECTED_LITERAL_BINDINGS]:
        _add_error(errors, "SoundMain CFG literal binding denominator changed")

    promotion_ranges = payload.get("promotion_ranges")
    if not isinstance(promotion_ranges, list):
        _add_error(errors, "SoundMain promotion ranges are not a list")
        promotion_ranges = []
    actual_promotions: list[tuple[Any, Any, Any, Any]] = []
    seen_promotion_ids: set[str] = set()
    for row in promotion_ranges:
        if not isinstance(row, dict):
            _add_error(errors, "SoundMain promotion row is not an object")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or row_id in seen_promotion_ids:
            _add_error(errors, "SoundMain promotion IDs are not unique")
        else:
            seen_promotion_ids.add(row_id)
        actual_promotions.append(
            (row_id, row.get("kind"), row.get("range"), row.get("sha256"))
        )
    if tuple(actual_promotions) != EXPECTED_PROMOTION_RANGES:
        _add_error(errors, "SoundMain promotion range provenance changed")

    packed = bytearray()
    for row in promotion_ranges:
        if not isinstance(row, dict):
            continue
        interval = row.get("range")
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(isinstance(value, int) for value in interval)
        ):
            _add_error(errors, "SoundMain promotion interval changed")
            continue
        start, end = interval
        if not (0 <= start < end <= len(rom)):
            _add_error(errors, "SoundMain promotion interval is out of ROM")
            continue
        raw = rom[start:end]
        packed.extend(raw)
        if row.get("size") != end - start or row.get("sha256") != _sha(raw):
            _add_error(errors, "SoundMain promotion bytes changed")
    if not isinstance(binary, bytes):
        _add_error(errors, "SoundMain packed binary is not bytes")
        binary = b""
    if len(binary) != BINARY_SIZE or _sha(binary) != BINARY_SHA256:
        _add_error(errors, "SoundMain packed binary identity changed")
    if bytes(packed) != binary:
        _add_error(errors, "SoundMain packed binary no longer matches ROM ranges")

    blocks = cfg.get("blocks")
    if not isinstance(blocks, list):
        _add_error(errors, "SoundMain CFG blocks are not a list")
        blocks = []
    block_map: dict[str, dict[str, Any]] = {}
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("id"), str):
            _add_error(errors, "SoundMain CFG block identity changed")
            continue
        block_id = block["id"]
        if block_id in block_map:
            _add_error(errors, "SoundMain CFG block IDs are not unique")
        block_map[block_id] = block
    if len(blocks) != 73 or len(block_map) != 73:
        _add_error(errors, "SoundMain CFG block denominator changed")
    instructions = cfg.get("instructions")
    if not isinstance(instructions, list) or len(instructions) != 315:
        _add_error(errors, "SoundMain CFG instruction denominator changed")

    gaps: list[dict[str, Any]] = []
    boundary_errors_before = len(errors)
    for index, expected in enumerate(BOUNDARY_VECTOR):
        start, end = expected["gap_range"]
        left_start, left_end = expected["left_range"]
        terminal_start, terminal_end = expected["terminal_range"]
        right_start, right_end = expected["right_range"]
        left = block_map.get(expected["left_block_id"])
        if not isinstance(left, dict):
            _add_error(errors, f"missing left block {expected['left_block_id']}")
            left = {}
        if left.get("range") != expected["left_range"] or left.get("mode") != "thumb":
            _add_error(errors, f"left owner changed for {expected['id']}")
        left_raw = rom[left_start:left_end]
        if left.get("bytes_sha256") != _sha(left_raw):
            _add_error(errors, f"left owner bytes changed for {expected['id']}")
        terminator = left.get("terminator")
        expected_terminator = {
            "conditional": False,
            "flow_kind": expected["flow_kind"],
            "mnemonic": expected["mnemonic"],
            "mode": "thumb",
            "op_str": expected["op_str"],
            "source_offset": terminal_start,
        }
        if terminator != expected_terminator:
            _add_error(errors, f"left terminal changed for {expected['id']}")
        successors = left.get("successors")
        successor_ok = False
        if isinstance(successors, list) and len(successors) == 1:
            successor = successors[0]
            successor_ok = (
                isinstance(successor, dict)
                and successor.get("kind") == "branch_target"
                and successor.get("resolution") == "internal"
                and successor.get("source_block_id") == expected["left_block_id"]
                and successor.get("source_instruction_offset") == terminal_start
                and successor.get("source_mode") == "thumb"
                and successor.get("target_block_id") == EXPECTED_TARGET_BLOCK_IDS[index]
                and successor.get("target_offset") == expected["target_offset"]
            )
        if not successor_ok:
            _add_error(errors, f"left successor changed for {expected['id']}")

        terminal_raw = rom[terminal_start:terminal_end]
        gap_raw = rom[start:end]
        right_raw = rom[right_start:right_end]
        if terminal_raw.hex() != expected["terminal_raw_hex"]:
            _add_error(errors, f"raw terminal changed for {expected['id']}")
        if gap_raw != b"\x00\x00" or _sha(gap_raw) != ZERO_PAIR_SHA256:
            _add_error(errors, f"raw gap changed for {expected['id']}")

        if expected["right_kind"] == "arm_block":
            right = block_map.get(expected["right_id"])
            if (
                not isinstance(right, dict)
                or right.get("range") != expected["right_range"]
                or right.get("mode") != "arm"
                or right.get("bytes_sha256") != _sha(right_raw)
            ):
                _add_error(errors, f"right ARM block changed for {expected['id']}")
        else:
            right = next(
                (
                    row
                    for row in promotion_ranges
                    if isinstance(row, dict) and row.get("id") == expected["right_id"]
                ),
                None,
            )
            if (
                not isinstance(right, dict)
                or right.get("kind") != "literal"
                or right.get("range") != expected["right_range"]
                or right.get("sha256") != _sha(right_raw)
            ):
                _add_error(errors, f"right literal changed for {expected['id']}")

        gap_start_equals_left = start == left_end
        gap_end_equals_align4 = end == ((start + 3) & ~3)
        right_starts_at_gap_end = right_start == end
        if not (
            gap_start_equals_left
            and gap_end_equals_align4
            and right_starts_at_gap_end
        ):
            _add_error(errors, f"align4 boundary changed for {expected['id']}")
        gaps.append(
            {
                "id": expected["id"],
                "gap_range": [start, end],
                "gap_size": end - start,
                "gap_raw_hex": gap_raw.hex(),
                "gap_sha256": _sha(gap_raw),
                "left_block_id": expected["left_block_id"],
                "left_owner_range": [left_start, left_end],
                "left_owner_sha256": _sha(left_raw),
                "left_terminal": {
                    "range": [terminal_start, terminal_end],
                    "raw_hex": terminal_raw.hex(),
                    "sha256": _sha(terminal_raw),
                    "flow_kind": expected["flow_kind"],
                    "mnemonic": expected["mnemonic"],
                    "op_str": expected["op_str"],
                    "target_offset": expected["target_offset"],
                },
                "right_kind": expected["right_kind"],
                "right_id": expected["right_id"],
                "right_range": [right_start, right_end],
                "right_sha256": _sha(right_raw),
                "gap_start_equals_left_owner_end": gap_start_equals_left,
                "gap_end_equals_align4_left_end": gap_end_equals_align4,
                "right_start_equals_gap_end": right_starts_at_gap_end,
            }
        )

    boundaries_exact = len(errors) == boundary_errors_before
    bundle_ok = _validate_bundle_report(bundle_report, payload, errors)
    packed_gaps = b"".join(rom[start:end] for start, end in RANGE_VECTOR)
    report.update(
        {
            "zero_byte_count": sum(byte == 0 for byte in packed_gaps),
            "packed_bytes_sha256": _sha(packed_gaps),
            "source_bundle_verified": bundle_ok,
            "gaps": gaps,
            "all_alignment_equations_hold": all(
                row["gap_start_equals_left_owner_end"]
                and row["gap_end_equals_align4_left_end"]
                and row["right_start_equals_gap_end"]
                for row in gaps
            ),
            "all_boundaries_exact": boundaries_exact,
        }
    )
    if _sha(packed_gaps) != PACKED_BYTES_SHA256:
        _add_error(errors, "packed gap bytes changed")
    report["verified"] = not errors
    return report


def _run_bundle_verifier(
    root: Path, wrapper_source: bytes, wrapper_display_path: Path
) -> dict[str, Any]:
    bootstrap = (
        "import sys\n"
        "source = sys.stdin.buffer.read()\n"
        "display = sys.argv[1]\n"
        "sys.argv = [display, *sys.argv[2:]]\n"
        "namespace = {'__name__': '__main__', '__file__': display, "
        "'__package__': None}\n"
        "exec(compile(source, display, 'exec', dont_inherit=True, optimize=0), "
        "namespace, namespace)\n"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            bootstrap,
            str(wrapper_display_path),
            "--root",
            str(root),
            "--artifact-dir",
            ARTIFACT_DIR.as_posix(),
        ],
        cwd=root,
        input=wrapper_source,
        capture_output=True,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise ValueError(
            "SoundMain bundle verifier failed: "
            + (stderr.strip() or stdout.strip())
        )
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError("SoundMain bundle verifier returned invalid JSON") from error
    if not isinstance(report, dict):
        raise ValueError("SoundMain bundle verifier returned a non-object")
    return report


def verify_root(raw_root: Path) -> dict[str, Any]:
    report = _empty_report()
    try:
        root = _safe_root(raw_root)
        source_files: dict[str, dict[str, Any]] = {}
        loaded: dict[str, bytes] = {}
        for identity in SOURCE_FILE_VECTOR:
            relative = Path(identity["path"])
            path = _safe_file(root, relative)
            raw = path.read_bytes()
            loaded[relative.as_posix()] = raw
            actual = {"sha256": _sha(raw), "size": len(raw)}
            source_files[relative.name] = actual
            if actual != {
                "sha256": identity["sha256"],
                "size": identity["size"],
            }:
                raise ValueError(f"frozen source identity changed: {relative}")
        rom_path = _safe_file(root, ROM_PATH)
        rom = rom_path.read_bytes()
        manifest = json.loads(loaded[MANIFEST_PATH.as_posix()].decode("utf-8"))
        payload = json.loads(loaded[PAYLOAD_PATH.as_posix()].decode("utf-8"))
        binary = loaded[BINARY_PATH.as_posix()]
        wrapper = _safe_file(root, BUNDLE_VERIFIER_PATH)
        bundle_source = loaded[BUNDLE_VERIFIER_PATH.as_posix()]
        bundle_report = _run_bundle_verifier(root, bundle_source, wrapper)
        report = verify_inputs(
            rom,
            manifest=manifest,
            payload=payload,
            binary=binary,
            bundle_report=bundle_report,
        )
        report["source_files"] = source_files
        return report
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = verify_root(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
