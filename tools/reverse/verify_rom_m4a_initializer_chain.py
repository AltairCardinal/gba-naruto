#!/usr/bin/env python3
"""Independently verify a rom-m4a-initializer-chain candidate.

This module intentionally repeats the small raw Thumb decoder and all frozen
denominators.  It does not import the exporter and does not trust exporter
objects or in-memory analysis results.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-m4a-initializer-chain-v1"
VERIFY_SCHEMA = "rom-m4a-initializer-chain-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SHA256 = BASE_ROM_SHA256
COVERAGE_SHA256 = "31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563"
COVERAGE_SUMMARY = {
    "classified_bytes": 6_123_419,
    "unknown_bytes": 168_037,
    "claim_count": 14_493,
    "segment_count": 16_600,
}
PROJECTED_COVERAGE_SUMMARY = {
    "classified_bytes": 6_123_937,
    "unknown_bytes": 167_519,
    "claim_count": 14_499,
    "segment_count": 16_608,
}
PRE_COVERAGE_ARTIFACT = Path(
    "artifacts/rom-m4a-initializer-chain-precoverage-v1"
)
PRE_COVERAGE_ARTIFACT_SCHEMA = "rom-byte-coverage-prepromotion-baseline-v1"
PRE_COVERAGE_MANIFEST_NAME = "manifest.json"
PRE_COVERAGE_ARCHIVE_NAME = "rom-byte-coverage.json.gz"
PRE_COVERAGE_MANIFEST_SIZE = 2_242
PRE_COVERAGE_MANIFEST_SHA256 = (
    "6d345594ab9278f5a098189328621af635ec17839f6ee7c5250b08bd7ed81baa"
)
PRE_COVERAGE_ARCHIVE_SIZE = 1_297_017
PRE_COVERAGE_ARCHIVE_SHA256 = (
    "9249601f241fd767ca9aa6ce583061c88686f9040ef93d6f9dab335e3cddbbac"
)
PRE_COVERAGE_RAW_SIZE = 23_097_532

PROMOTION_RANGES = [
    [0x09AA3C, 0x09AA90], [0x09AA90, 0x09AAB4],
    [0x09ACF8, 0x09ADC0], [0x09ADC0, 0x09AE10],
    [0x09B17C, 0x09B1E6], [0x09B1E8, 0x09B1F4],
]
PROMOTION_RANGE_SHA256 = [
    "c782ff96fc49708def45c12c5ba3c4170449390bf0ea4aa389561e09f359013b",
    "7f208987daf90cface78da36557a0773839b56b2bf1fe174358f1a56cfebbc6f",
    "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a",
    "5b0dd3fbbfc9f8c964f9c0f806548ccd9b72059ee6b67188c9432ac2342652b0",
    "b89251f7ae5e7e69702a82f4777b07d2a5ed1747b3aa8cfb8ea90bbfe0c7c733",
    "93fd80ddfc01693c7d0a9011380fb8fc6fe9c830809470f90cdacb2979bf0c46",
]
PACKED_SHA256 = "f5c0a94ac06bf6750edc038e0db95fc5d4e96c321129e57a11abd461aa678ea7"
RANGE_VECTOR_SHA256 = "8bcba07694e7375d59dddeb3cb12eeb4903e61147c91723482d61d06a47dbd72"
PROMOTION_UNION_RANGES = [[0x09AA3C, 0x09AAB4], [0x09ACF8, 0x09AE10], [0x09B17C, 0x09B1E6], [0x09B1E8, 0x09B1F4]]
GAP_RANGE = [0x09B1E6, 0x09B1E8]
GAP_SHA256 = "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
CODE_RANGES = [PROMOTION_RANGES[0], PROMOTION_RANGES[2], PROMOTION_RANGES[4]]
LITERAL_RANGES = [PROMOTION_RANGES[1], PROMOTION_RANGES[3], PROMOTION_RANGES[5]]
ROOTS = [
    {"id": "m4aSoundInit", "file_offset": 0x09AA3C, "code_range": PROMOTION_RANGES[0]},
    {"id": "PSG initializer", "file_offset": 0x09ACF8, "code_range": PROMOTION_RANGES[2]},
    {"id": "MPlayOpen", "file_offset": 0x09B17C, "code_range": PROMOTION_RANGES[4]},
]
ROOT_BY_OFFSET = {item["file_offset"]: item for item in ROOTS}
RETURN_OFFSETS = {0x09AA3C: 0x09AA8E, 0x09ACF8: 0x09ADBE, 0x09B17C: 0x09B1E4}
EXPECTED_BLOCK_RANGES = {
    0x09AA3C: [[0x09AA3C, 0x09AA4E], [0x09AA4E, 0x09AA54], [0x09AA54, 0x09AA5A], [0x09AA5A, 0x09AA60], [0x09AA60, 0x09AA6A], [0x09AA6A, 0x09AA6E], [0x09AA6E, 0x09AA7A], [0x09AA7A, 0x09AA8A], [0x09AA8A, 0x09AA90]],
    0x09ACF8: [[0x09ACF8, 0x09AD3A], [0x09AD3A, 0x09AD8A], [0x09AD8A, 0x09ADB8], [0x09ADB8, 0x09ADC0]],
    0x09B17C: [[0x09B17C, 0x09B18A], [0x09B18A, 0x09B18E], [0x09B18E, 0x09B190], [0x09B190, 0x09B19C], [0x09B19C, 0x09B1A6], [0x09B1A6, 0x09B1B4], [0x09B1B4, 0x09B1B6], [0x09B1B6, 0x09B1C4], [0x09B1C4, 0x09B1CA], [0x09B1CA, 0x09B1D4], [0x09B1D4, 0x09B1E0], [0x09B1E0, 0x09B1E6]],
}
ALLOWED_CALLS = {
    0x09AA3C: {0x09AA4A: (0x09C0E0, "opaque_call"), 0x09AA50: (0x09AE3C, "opaque_call"), 0x09AA56: (0x09ACF8, "included_root"), 0x09AA5C: (0x09AFD8, "opaque_call"), 0x09AA76: (0x09B17C, "included_root")},
    0x09ACF8: {0x09AD86: (0x09C0E0, "opaque_call")},
    0x09B17C: {0x09B1A2: (0x09AE28, "opaque_call")},
}
LITERAL_EXPECTATIONS = [
    (0x09AA3E, 0x09AA90, 0x08099E11), (0x09AA46, 0x09AA94, 0x030077C8), (0x09AA48, 0x09AA98, 0x04000100), (0x09AA4E, 0x09AA9C, 0x03006570), (0x09AA54, 0x09AAA0, 0x030075B0), (0x09AA5A, 0x09AAA4, 0x0095FA00), (0x09AA60, 0x09AAA8, 0x00000004), (0x09AA6A, 0x09AAAC, 0x08465B40), (0x09AA7E, 0x09AAB0, 0x03007770),
    (0x09ACFE, 0x09ADC0, 0x04000084), (0x09AD04, 0x09ADC4, 0x04000080), (0x09AD0A, 0x09ADC8, 0x04000063), (0x09AD2E, 0x09ADCC, 0x03007FF0), (0x09AD34, 0x09ADD0, 0x68736D53), (0x09AD3E, 0x09ADD4, 0x03007520), (0x09AD40, 0x09ADD8, 0x0809BCB5), (0x09AD44, 0x09ADDC, 0x0809A971), (0x09AD48, 0x09ADE0, 0x0809A985), (0x09AD4C, 0x09ADE4, 0x0809BE0D), (0x09AD50, 0x09ADE8, 0x0809A909), (0x09AD54, 0x09ADEC, 0x0809AF35), (0x09AD58, 0x09ADF0, 0x0809A695), (0x09AD60, 0x09ADF4, 0x0809B319), (0x09AD66, 0x09ADF8, 0x0809B3E1), (0x09AD6C, 0x09ADFC, 0x0809B5F5), (0x09AD70, 0x09AE00, 0x0809B53D), (0x09AD74, 0x09AE04, 0x0809B495), (0x09AD78, 0x09AE08, 0x00000000), (0x09AD80, 0x09AE0C, 0x05000040),
    (0x09B190, 0x09B1E8, 0x03007FF0), (0x09B196, 0x09B1EC, 0x68736D53), (0x09B1D6, 0x09B1F0, 0x0809A42D), (0x09B1DA, 0x09B1EC, 0x68736D53),
]
UPSTREAM_PATHS = {
    "soundmain": {"manifest": Path("artifacts/rom-soundmain-relocated-cfg-v1/manifest.json"), "payload": Path("artifacts/rom-soundmain-relocated-cfg-v1/rom-soundmain-relocated-cfg.json"), "verifier": Path("tools/verify_rom_soundmain_relocated_cfg.py")},
    "psg": {"manifest": Path("artifacts/rom-psg-frequency-lookup-v1/manifest.json"), "payload": Path("artifacts/rom-psg-frequency-lookup-v1/rom-psg-frequency-lookup.json"), "verifier": Path("tools/verify_rom_psg_frequency_lookup.py")},
    "mplaymain": {"manifest": Path("artifacts/rom-mplaymain-scheduler-v1/manifest.json"), "payload": Path("artifacts/rom-mplaymain-scheduler-v1/rom-mplaymain-scheduler.json"), "verifier": Path("tools/verify_rom_mplaymain_scheduler.py")},
}
UPSTREAM_RECEIPTS = {
    "soundmain": {"manifest_sha256": "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37", "payload_sha256": "63543ece1982ced20eb0818faf3b6f1848e72ba6dcdb68105fa8b2e3e07e477a", "verifier_sha256": "321d5ca5b7d6f887a21ec93c1bb06640f6e1397248273068bb5a13d3d7167d82"},
    "psg": {"manifest_sha256": "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f", "payload_sha256": "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733", "verifier_sha256": "c87ab33b067a35a0105e21967dc0caad5fe91368942f34baf91218d69258f616"},
    "mplaymain": {"manifest_sha256": "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d", "payload_sha256": "31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78", "verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a"},
}
EXPECTED_UPSTREAM_RECEIPTS = json.loads(json.dumps(UPSTREAM_RECEIPTS))
PAYLOAD_NAME = "rom-m4a-initializer-chain.json"
BUNDLE_NAME = "rom-m4a-initializer-chain.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("artifacts/rom-m4a-initializer-chain-v1")
SCOPE = {
    "source_instruction_membership_complete": False, "producer_source_instruction_membership_proven": False, "producer_bytes_promoted": False, "dynamic_callback_values_proven": False, "global_ram_or_computed_producer_denominator_complete": False, "global_caller_denominator_complete": False, "global_code_denominator_complete": False, "global_indirect_producer_denominator_complete": False, "natural_runtime_reachability_complete": False, "literal_pointer_target_semantics_claimed": False, "audio_behavior_proven": False, "editing_relocation_writeback_safe": False, "allocatable_free_space_proven": False,
}
LIMITATIONS = [
    "This candidate classifies exactly 390 bounded Thumb instruction bytes and 128 consumed literal bytes in three target-limited initializer roots.",
    "The three direct Thumb BL producer matches are raw provenance only; source instruction membership and producer bytes remain unpromoted.",
    "Dynamic callback/RAM values, natural runtime reachability, global caller/code/indirect/computed producer denominators, and literal target semantics remain unproven.",
    "The two bytes at 0x09B1E6..0x09B1E8 remain current unknown and are not padding, NOP, reserved, free, or allocatable space.",
    "Audio behavior, editing, writeback, relocation, and allocatable free-space safety are outside scope.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _bounded(rom: bytes, start: int, end: int, label: str = "ROM") -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range escapes ROM")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2, "Thumb halfword"), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4, "ROM word"), "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _validate_root(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve(strict=True)
    if not value.is_dir():
        raise ValueError("repository root is not a directory")
    return value


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    path = (root / relative).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not path.is_file():
        raise ValueError(f"required file missing: {relative}")
    return path


def _validate_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")


def _bl_target(rom: bytes, offset: int) -> int | None:
    if offset & 1 or offset < 0 or offset + 4 > len(rom):
        return None
    first, second = _u16(rom, offset), _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    return offset + 4 + _sign_extend(((first & 0x7FF) << 12) | ((second & 0x7FF) << 1), 23)


def _branch(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset & 1 or offset < 0 or offset + 2 > len(rom):
        return None
    halfword = _u16(rom, offset)
    condition = (halfword >> 8) & 0xF
    if halfword & 0xF000 == 0xD000 and condition <= 0xD:
        return "thumb_b_conditional", offset + 4 + _sign_extend((halfword & 0xFF) << 1, 9)
    if halfword & 0xF800 == 0xE000:
        return "thumb_b", offset + 4 + _sign_extend((halfword & 0x7FF) << 1, 12)
    return None


def _arm_branch(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset & 3 or offset < 0 or offset + 4 > len(rom):
        return None
    word = _u32(rom, offset)
    if word & 0x0E000000 != 0x0A000000:
        return None
    return ("arm_bl" if word & (1 << 24) else "arm_b", offset + 8 + _sign_extend((word & 0xFFFFFF) << 2, 26))


def _pointer_occurrences(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    rows: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return rows
        rows.append(cursor)
        cursor += 1


def _raw_producers(rom: bytes) -> dict[int, dict[str, list[int]]]:
    targets = [item["file_offset"] for item in ROOTS]
    result = {target: {"thumb_bl": [], "thumb_b": [], "thumb_b_conditional": [], "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": []} for target in targets}
    for offset in range(0, len(rom) - 3, 2):
        target = _bl_target(rom, offset)
        if target in result:
            result[target]["thumb_bl"].append(offset)
    for offset in range(0, len(rom) - 1, 2):
        row = _branch(rom, offset)
        if row is not None and row[1] in result:
            result[row[1]][row[0]].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        row = _arm_branch(rom, offset)
        if row is not None and row[1] in result:
            result[row[1]][row[0]].append(offset)
    for target in targets:
        result[target]["bytewise_u32_entry"] = _pointer_occurrences(rom, ROM_BASE + target)
        result[target]["bytewise_u32_thumb_pointer"] = _pointer_occurrences(rom, ROM_BASE + target + 1)
        for values in result[target].values():
            values.sort()
    expected = {0x09AA3C: [0x061E28], 0x09ACF8: [0x09AA56], 0x09B17C: [0x09AA76]}
    for target in targets:
        if result[target]["thumb_bl"] != expected[target] or any(result[target][name] for name in result[target] if name != "thumb_bl"):
            raise ValueError("target producer form denominator changed")
    vector = [{"target_file_offset": target, "forms": result[target]} for target in targets]
    return {
        "scan": {"mode": "raw-rom", "alignment_bytes": 2, "range": [0, ROM_SIZE]},
        "thumb_bl": [0x061E28, 0x09AA56, 0x09AA76],
        "root_forms": {f"0x{target:06X}": result[target] for target in targets},
        "producer_form_vector": vector,
        "producer_form_vector_sha256": _sha(_canonical(vector)),
        "all_non_thumb_bl_forms_empty": True,
        "producer_source_instruction_membership_proven": False,
        "producer_bytes_promoted": False,
        "target_limited_raw_producer_denominator_complete": True,
        "computed_or_indirect_producer_denominator_complete": False,
    }


def _load_coverage(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    return analyze_coverage_baseline(json.loads(raw.decode("utf-8")))


def _load_coverage_from_artifact(
    root: Path, artifact: Path | str
) -> tuple[dict[str, Any], dict[str, Any]]:
    requested = Path(artifact).expanduser()
    if requested.is_absolute():
        try:
            relative = requested.resolve(strict=True).relative_to(root)
        except ValueError as error:
            raise ValueError("coverage baseline artifact escapes repository root") from error
    else:
        relative = requested
    if relative != PRE_COVERAGE_ARTIFACT:
        raise ValueError("coverage baseline artifact identity changed")

    manifest_raw = _safe_file(
        root, relative / PRE_COVERAGE_MANIFEST_NAME
    ).read_bytes()
    archive_raw = _safe_file(
        root, relative / PRE_COVERAGE_ARCHIVE_NAME
    ).read_bytes()
    if (
        len(manifest_raw) != PRE_COVERAGE_MANIFEST_SIZE
        or _sha(manifest_raw) != PRE_COVERAGE_MANIFEST_SHA256
    ):
        raise ValueError("coverage baseline artifact manifest identity changed")
    if (
        len(archive_raw) != PRE_COVERAGE_ARCHIVE_SIZE
        or _sha(archive_raw) != PRE_COVERAGE_ARCHIVE_SHA256
    ):
        raise ValueError("coverage baseline artifact archive identity changed")
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        raw = gzip.decompress(archive_raw)
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as error:
        raise ValueError("coverage baseline artifact is invalid") from error
    if _canonical(manifest) != manifest_raw:
        raise ValueError("coverage baseline artifact manifest is not canonical JSON")
    if _canonical(coverage) != raw:
        raise ValueError("coverage baseline artifact raw JSON is not canonical")
    if (
        manifest.get("schema") != PRE_COVERAGE_ARTIFACT_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("coverage", {}).get("raw")
        != {
            "canonical_json": True,
            "schema": "rom-byte-coverage-v1",
            "sha256": COVERAGE_SHA256,
            "size": PRE_COVERAGE_RAW_SIZE,
            "summary": dict(COVERAGE_SUMMARY),
        }
        or manifest.get("coverage", {}).get("archive")
        != {
            "compression": "gzip",
            "file": PRE_COVERAGE_ARCHIVE_NAME,
            "sha256": PRE_COVERAGE_ARCHIVE_SHA256,
            "size": PRE_COVERAGE_ARCHIVE_SIZE,
        }
        or manifest.get("recovery", {}).get("kind")
        != "byte-identical-inverse-promotion-projection"
    ):
        raise ValueError("coverage baseline artifact contract changed")
    if len(raw) != PRE_COVERAGE_RAW_SIZE or _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline artifact raw identity changed")
    baseline = analyze_coverage_baseline(coverage)
    source = {
        "kind": "immutable-gzip-artifact",
        "artifact": relative.as_posix(),
        "manifest_sha256": PRE_COVERAGE_MANIFEST_SHA256,
        "archive_file": PRE_COVERAGE_ARCHIVE_NAME,
        "archive_size": PRE_COVERAGE_ARCHIVE_SIZE,
        "archive_sha256": PRE_COVERAGE_ARCHIVE_SHA256,
        "raw_size": PRE_COVERAGE_RAW_SIZE,
        "raw_sha256": COVERAGE_SHA256,
        "recovery_kind": "byte-identical-inverse-promotion-projection",
    }
    return baseline, source


def _frozen_coverage_receipt() -> dict[str, Any]:
    """Rebuild the accepted artifact's immutable pre-promotion receipt.

    Candidate construction and direct candidate verification still consult the
    live coverage file.  Once accepted, verification must remain portable when
    that file advances to the projected post-promotion state.
    """

    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": "rom-byte-coverage-v1",
        "sha256": COVERAGE_SHA256,
        "summary": dict(COVERAGE_SUMMARY),
        "promotion_bytes": 518,
        "unknown_promotion_bytes": 518,
        "primary_overlap_bytes": 0,
        "all_promotion_bytes_unknown": True,
        "target_segments": [
            {
                "range": list(interval),
                "primary_class": "unknown",
                "primary_claim_ids": [],
            }
            for interval in PROMOTION_RANGES
        ],
    }


def analyze_coverage_baseline(coverage: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(coverage, dict) or coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict) or {key: summary.get(key) for key in COVERAGE_SUMMARY} != COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list):
        raise ValueError("coverage baseline segments missing")
    normalized = []
    for segment in segments:
        raw_range = segment.get("range") if isinstance(segment, dict) else None
        if not isinstance(raw_range, list) or len(raw_range) != 2 or not all(isinstance(value, int) for value in raw_range):
            raise ValueError("coverage baseline contains an invalid segment range")
        normalized.append((raw_range[0], raw_range[1], segment))
    normalized.sort()
    target_segments: list[dict[str, Any]] = []
    unknown_bytes = 0
    overlap_bytes = 0
    for target_start, target_end in PROMOTION_RANGES:
        cursor = target_start
        for start, end, segment in normalized:
            if end <= target_start:
                continue
            if start >= target_end:
                break
            left, right = max(cursor, start), min(target_end, end)
            if left != cursor or right <= left:
                raise ValueError("coverage baseline has a partial owner or gap inside promotion range")
            unknown = segment.get("primary_class") == "unknown" and segment.get("primary_claim_ids") in (None, [])
            if unknown:
                unknown_bytes += right - left
            else:
                overlap_bytes += right - left
            target_segments.append({"range": [left, right], "primary_class": "unknown" if unknown else segment.get("primary_class"), "primary_claim_ids": [] if unknown else segment.get("primary_claim_ids")})
            cursor = right
        if cursor != target_end:
            raise ValueError("coverage baseline does not cover a promotion range")
    if unknown_bytes != 518 or overlap_bytes:
        raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
    return {"path": COVERAGE_PATH.as_posix(), "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "summary": dict(COVERAGE_SUMMARY), "promotion_bytes": 518, "unknown_promotion_bytes": unknown_bytes, "primary_overlap_bytes": overlap_bytes, "all_promotion_bytes_unknown": True, "target_segments": target_segments}


def _validate_upstreams(root: Path) -> None:
    if UPSTREAM_RECEIPTS != EXPECTED_UPSTREAM_RECEIPTS:
        raise ValueError("upstream receipt contract changed")
    for name, paths in UPSTREAM_PATHS.items():
        for role, relative in paths.items():
            raw = _safe_file(root, relative).read_bytes()
            expected = EXPECTED_UPSTREAM_RECEIPTS[name][f"{role}_sha256"]
            if _sha(raw) != expected:
                raise ValueError(f"upstream {name} {role} receipt changed")
            if role == "manifest" and json.loads(raw.decode("utf-8")).get("artifact_status") != "accepted":
                raise ValueError(f"upstream {name} artifact is not accepted")


def _engine() -> Cs:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    return engine


def _decode(engine: Cs, rom: bytes, offset: int, end: int) -> Any:
    if offset & 1 or offset < 0 or offset >= end:
        raise ValueError(f"CFG decode offset invalid at 0x{offset:06X}")
    rows = list(engine.disasm(_bounded(rom, offset, min(offset + 4, end), "instruction"), ROM_BASE + offset, count=1))
    if len(rows) != 1 or rows[0].address != ROM_BASE + offset or rows[0].size not in (2, 4) or offset + rows[0].size > end:
        raise ValueError(f"Thumb CFG decode failed at 0x{offset:06X}")
    return rows[0]


def _target(instruction: Any) -> int:
    if len(instruction.operands) != 1 or instruction.operands[0].type != arm_const.ARM_OP_IMM:
        raise ValueError("direct branch operand changed")
    return instruction.operands[0].imm - ROM_BASE


def _walk(rom: bytes, root_offset: int, engine: Cs) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    start, end = ROOT_BY_OFFSET[root_offset]["code_range"]
    pending = [start]
    seen: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in seen:
            continue
        instruction = _decode(engine, rom, offset, end)
        next_offset = offset + instruction.size
        if instruction.id == arm_const.ARM_INS_B:
            target = _target(instruction)
            conditional = instruction.cc != arm_const.ARM_CC_AL
            successors = [("branch_target", target)]
            if conditional:
                successors.append(("fallthrough", next_offset))
            flow_kind = "conditional_branch" if conditional else "unconditional_branch"
        elif instruction.id == arm_const.ARM_INS_BL:
            target = _target(instruction)
            expected = ALLOWED_CALLS[root_offset].get(offset)
            if expected is None or expected[0] != target:
                raise ValueError(f"direct call denominator changed at 0x{offset:06X}")
            successors = [("call_target", target), ("fallthrough", next_offset)]
            external.append({"source_instruction_offset": offset, "source_mode": "thumb", "kind": "call_target", "target_offset": target, "target_mode": "thumb", "resolution": expected[1], "target_root": ROOT_BY_OFFSET[target]["id"] if expected[1] == "included_root" else None})
            flow_kind = "call"
            conditional = False
        elif instruction.id == arm_const.ARM_INS_BX:
            if offset != RETURN_OFFSETS[root_offset] or instruction.op_str != "r0":
                raise ValueError(f"return/indirect branch changed at 0x{offset:06X}")
            successors = []
            flow_kind = "return"
            conditional = False
        else:
            if next_offset >= end:
                raise ValueError(f"CFG falls out of frozen range at 0x{offset:06X}")
            successors = [("fallthrough", next_offset)]
            flow_kind = "linear"
            conditional = False
        for kind, target in successors:
            if kind == "call_target":
                continue
            if not start <= target < end or target & 1:
                raise ValueError(f"CFG branch escaped frozen range from 0x{offset:06X}")
            heapq.heappush(pending, target)
        raw = _bounded(rom, offset, next_offset, "instruction")
        seen[offset] = {"root": ROOT_BY_OFFSET[root_offset]["id"], "offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}", "mode": "thumb", "size": instruction.size, "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "mnemonic": instruction.mnemonic, "op_str": instruction.op_str, "flow_kind": flow_kind, "conditional": conditional, "successors": [{"kind": kind, "target_offset": target, "target_mode": "thumb"} for kind, target in successors]}
    byte_owner: dict[int, int] = {}
    for offset, node in seen.items():
        for position in range(offset, offset + node["size"]):
            if position in byte_owner and byte_owner[position] != offset:
                raise ValueError("CFG target lands in an instruction middle")
            byte_owner[position] = offset
    if set(byte_owner) != set(range(start, end)):
        raise ValueError("CFG code range is not closed")
    return seen, external


def _blocks(rom: bytes, root_offset: int, nodes: dict[int, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for successor in node["successors"]:
            target = successor["target_offset"]
            if successor["kind"] != "call_target" and target in predecessors:
                predecessors[target].append((source, successor["kind"]))
    leaders = {root_offset}
    for offset, incoming in predecessors.items():
        if offset == root_offset:
            continue
        if len(incoming) != 1:
            leaders.add(offset)
            continue
        source, kind = incoming[0]
        predecessor = nodes[source]
        if len(predecessor["successors"]) != 1 or kind != "fallthrough" or predecessor["flow_kind"] != "linear" or source + predecessor["size"] != offset:
            leaders.add(offset)
    ids: dict[int, str] = {}
    blocks: list[dict[str, Any]] = []
    for block_start in sorted(leaders):
        if block_start in ids:
            continue
        members: list[int] = []
        cursor = block_start
        while cursor in nodes and cursor not in ids:
            members.append(cursor)
            ids[cursor] = f"{ROOT_BY_OFFSET[root_offset]['id']}-block-{block_start:06x}"
            node = nodes[cursor]
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            successor = node["successors"][0]
            if successor["kind"] != "fallthrough" or successor["target_offset"] in leaders or successor["target_offset"] != cursor + node["size"]:
                break
            cursor = successor["target_offset"]
        end = members[-1] + nodes[members[-1]]["size"]
        blocks.append({"id": ids[block_start], "root": ROOT_BY_OFFSET[root_offset]["id"], "mode": "thumb", "range": [block_start, end], "runtime_range": [ROM_BASE + block_start, ROM_BASE + end], "instruction_count": len(members), "bytes_sha256": _sha(_bounded(rom, block_start, end, "block")), "terminator": nodes[members[-1]], "successors": []})
    if [block["range"] for block in blocks] != EXPECTED_BLOCK_RANGES[root_offset]:
        raise ValueError("CFG block denominator changed")
    edges: list[dict[str, Any]] = []
    for block in blocks:
        for successor in block["terminator"]["successors"]:
            if successor["kind"] == "call_target":
                continue
            target = successor["target_offset"]
            if target not in ids:
                raise ValueError("CFG block edge escaped")
            edge = {"source_block_id": block["id"], "source_instruction_offset": block["terminator"]["offset"], "source_mode": "thumb", "kind": successor["kind"], "target_offset": target, "target_mode": "thumb", "target_block_id": ids[target], "resolution": "internal"}
            block["successors"].append(edge)
            edges.append(edge)
    return blocks, edges


def _cfg(rom: bytes) -> dict[str, Any]:
    engine = _engine()
    instructions: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    external: list[dict[str, Any]] = []
    for root in ROOTS:
        nodes, calls = _walk(rom, root["file_offset"], engine)
        root_blocks, root_edges = _blocks(rom, root["file_offset"], nodes)
        instructions.extend(nodes[offset] for offset in sorted(nodes))
        blocks.extend(root_blocks)
        edges.extend(root_edges)
        external.extend(calls)
    instructions.sort(key=lambda row: row["offset"])
    blocks.sort(key=lambda row: row["range"][0])
    edges.sort(key=lambda row: (row["source_instruction_offset"], row["kind"], row["target_offset"]))
    external.sort(key=lambda row: row["source_instruction_offset"])
    if len(instructions) != 188 or sum(row["size"] for row in instructions) != 390 or len(blocks) != 25 or len(edges) != 31 or len(external) != 7:
        raise ValueError("CFG denominator changed")
    if sum(row["flow_kind"] == "return" for row in instructions) != 3:
        raise ValueError("structured return denominator changed")
    vector = [[row["offset"], row["size"], row["mnemonic"], row["op_str"]] for row in instructions]
    edge_vector = [[row["source_instruction_offset"], row["kind"], row["target_offset"]] for row in edges]
    roots = [{"id": row["id"], "file_offset": row["file_offset"], "gba_address": f"0x{ROM_BASE + row['file_offset']:08X}", "mode": "thumb", "code_range": list(row["code_range"])} for row in ROOTS]
    summary = {"instruction_count": len(instructions), "instruction_bytes": sum(row["size"] for row in instructions), "code_bytes": 390, "block_count": len(blocks), "internal_edge_count": len(edges), "internal_block_edge_count": len(edges), "external_edge_count": len(external), "direct_call_count": len(external), "structured_return_count": 3, "frontier_count": 0, "unresolved_frontier_count": 0}
    return {"roots": roots, "code_ranges": [list(row) for row in CODE_RANGES], "instructions": instructions, "blocks": blocks, "block_edges": edges, "external_edges": external, "semantic_instruction_vector": vector, "semantic_instruction_vector_sha256": _sha(_canonical(vector)), "edge_vector_sha256": _sha(_canonical(edge_vector)), "summary": summary}


def _literals(rom: bytes, instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actual: list[tuple[int, int, int]] = []
    for node in instructions:
        if node["size"] != 2 or node["mnemonic"] != "ldr":
            continue
        halfword = _u16(rom, node["offset"])
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((node["offset"] + 4) & ~3) + (halfword & 0xFF) * 4
        actual.append((node["offset"], literal, _u32(rom, literal)))
    if actual != LITERAL_EXPECTATIONS:
        raise ValueError("literal binding denominator changed")
    rows = []
    covered: set[int] = set()
    for load_offset, literal_offset, value in actual:
        pool = next((rng for rng in LITERAL_RANGES if rng[0] <= literal_offset < rng[1]), None)
        if pool is None or literal_offset + 4 > pool[1]:
            raise ValueError("LDR literal escapes frozen pool")
        raw = _bounded(rom, literal_offset, literal_offset + 4, "literal word")
        covered.update(range(literal_offset, literal_offset + 4))
        rows.append({"instruction_offset": load_offset, "instruction_mode": "thumb", "load_raw_hex": _bounded(rom, load_offset, load_offset + 2, "LDR").hex(), "literal_offset": literal_offset, "literal_range": [literal_offset, literal_offset + 4], "value": f"0x{value:08X}", "raw_hex": raw.hex()})
    for start, end in LITERAL_RANGES:
        if not set(range(start, end)).issubset(covered):
            raise ValueError("literal pool hole or unconsumed byte")
    return rows


def _promotion_rows(rom: bytes) -> list[dict[str, Any]]:
    specs = [("m4a-sound-init-code-09aa3c", "bounded_thumb_code", "thumb"), ("m4a-sound-init-literals-09aa90", "consumed_literals", None), ("psg-initializer-code-09acf8", "bounded_thumb_code", "thumb"), ("psg-initializer-literals-09adc0", "consumed_literals", None), ("mplay-open-code-09b17c", "bounded_thumb_code", "thumb"), ("mplay-open-literals-09b1e8", "consumed_literals", None)]
    rows = []
    for index, (row_id, kind, mode) in enumerate(specs):
        start, end = PROMOTION_RANGES[index]
        raw = _bounded(rom, start, end, "promotion")
        if _sha(raw) != PROMOTION_RANGE_SHA256[index]:
            raise ValueError(f"promotion range bytes changed: {row_id}")
        rows.append({"id": row_id, "kind": kind, "range": [start, end], "size": end - start, "sha256": PROMOTION_RANGE_SHA256[index], "mode": mode, "semantic_class": "armv4t_m4a_initializer_chain_thumb_code" if mode else "m4a_initializer_chain_consumed_literal_bytes", "claim_kind": "m4a_initializer_chain_bounded_thumb_code" if mode else "m4a_initializer_chain_consumed_literal_bytes"})
    return rows


def _expected_payload(
    root: Path,
    rom: bytes,
    *,
    use_live_coverage: bool = True,
    coverage_baseline_artifact: Path | str | None = None,
) -> tuple[dict[str, Any], bytes]:
    _validate_rom(rom)
    _validate_upstreams(root)
    if coverage_baseline_artifact is not None:
        coverage, coverage_source = _load_coverage_from_artifact(
            root, coverage_baseline_artifact
        )
    else:
        coverage = (
            _load_coverage(root)
            if use_live_coverage
            else _frozen_coverage_receipt()
        )
        coverage_source = None
    rows = _promotion_rows(rom)
    if _sha(_bounded(rom, *GAP_RANGE, "gap")) != GAP_SHA256 or _bounded(rom, *GAP_RANGE) != b"\x00\x00":
        raise ValueError("MPlayOpen return-to-pool gap changed")
    cfg = _cfg(rom)
    literals = _literals(rom, cfg["instructions"])
    producer = _raw_producers(rom)
    bundle = b"".join(_bounded(rom, start, end, "promotion") for start, end in PROMOTION_RANGES)
    if _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion packed bytes changed")
    if _sha(_compact(PROMOTION_UNION_RANGES)) != RANGE_VECTOR_SHA256:
        raise ValueError("promotion range vector receipt changed")
    post = {"classified_bytes": coverage["summary"]["classified_bytes"] + 518, "unknown_bytes": coverage["summary"]["unknown_bytes"] - 518, "claim_count": coverage["summary"]["claim_count"] + 6, "segment_count": coverage["summary"]["segment_count"] + 8}
    if post != PROJECTED_COVERAGE_SUMMARY:
        raise ValueError("coverage post projection changed")
    literal_vector = [[row["instruction_offset"], row["literal_offset"], row["value"]] for row in literals]
    claims = [{**row, "role": "primary", "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown", "non_claims": dict(SCOPE), "limitations": list(LIMITATIONS)} for row in rows]
    payload = {
        "schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": BASE_ROM_SHA256}, "coverage_baseline": coverage, "coverage_projection": {"pre": dict(coverage["summary"]), "post": post, "classified_delta": 518, "unknown_delta": -518, "claim_delta": 6, "segment_delta": 8}, "upstream_receipts": json.loads(json.dumps(UPSTREAM_RECEIPTS)), "roots": cfg["roots"], "cfg": cfg, "code_ranges": [list(row) for row in CODE_RANGES], "literal_ranges": [list(row) for row in LITERAL_RANGES], "unclassified_unknown_ranges": [list(GAP_RANGE)], "promotion_ranges": rows, "coverage_claims": claims, "literal_bindings": literals, "literal_binding_vector": literal_vector, "literal_binding_vector_sha256": _sha(_canonical(literal_vector)), "producer_denominator": producer, "gap_exclusion": {"ranges": [list(GAP_RANGE)], "bytes": 2, "sha256": GAP_SHA256, "promotion_excluded": True, "semantic_label": "unknown"}, "promotion": {"ranges": [list(row) for row in PROMOTION_RANGES], "union_ranges": [list(row) for row in PROMOTION_UNION_RANGES], "union_range_count": len(PROMOTION_UNION_RANGES), "union_bytes": 518, "range_count": 6, "byte_count": 518, "range_sha256": list(PROMOTION_RANGE_SHA256), "range_vector_sha256": RANGE_VECTOR_SHA256, "packed_bytes_sha256": PACKED_SHA256, "code_bytes": 390, "literal_bytes": 128}, "packed_layout": [{"range": list(row["range"]), "kind": row["kind"], "bundle_offset": sum(item["size"] for item in rows[:index]), "size": row["size"], "sha256": row["sha256"]} for index, row in enumerate(rows)], "packed_binary": {"file": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle)}, "scope": dict(SCOPE), "limitations": list(LIMITATIONS), "summary": {**cfg["summary"], "literal_ref_count": len(literals), "literal_word_count": len({row["literal_offset"] for row in literals}), "literal_bytes": 128, "promoted_bytes": len(bundle), "promotion_claim_count": len(claims), "promotion_range_count": len(rows), "producer_count": len(producer["thumb_bl"]), "gap_exclusion_bytes": 2},
    }
    if coverage_source is not None:
        payload["coverage_baseline_source"] = coverage_source
    return payload, bundle


def independent_rebuild(root: Path | str, rom: bytes) -> dict[str, Any]:
    repository = _validate_root(root)
    payload, bundle = _expected_payload(repository, bytes(rom))
    return {"schema": VERIFY_SCHEMA, "contract_ok": True, "verified": True, "summary": payload["summary"], "producer_denominator": payload["producer_denominator"], "literal_bindings": payload["literal_bindings"], "bundle_sha256": _sha(bundle), "bundle_size": len(bundle), "payload": payload}


def _artifact_path(root: Path, artifact_dir: Path | str) -> Path:
    requested = Path(artifact_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    absolute = Path(os.path.abspath(requested))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"artifact path uses a symlink: {cursor}")
    requested = requested.resolve(strict=True)
    try:
        requested.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact must stay inside repository root") from error
    if not requested.is_dir():
        raise ValueError("artifact is not a directory")
    return requested


def _implementation(root: Path) -> dict[str, dict[str, Any]]:
    paths = {"exporter": Path("tools/export_rom_m4a_initializer_chain.py"), "verifier": Path("tools/verify_rom_m4a_initializer_chain.py"), "exporter_test": Path("tests/test_export_rom_m4a_initializer_chain.py"), "verifier_test": Path("tests/test_verify_rom_m4a_initializer_chain.py")}
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _semantic_contract(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "semantic_instruction_vector_sha256": payload["cfg"]["semantic_instruction_vector_sha256"],
        "edge_vector_sha256": payload["cfg"]["edge_vector_sha256"],
        "literal_binding_vector_sha256": payload["literal_binding_vector_sha256"],
        "producer_form_vector_sha256": payload["producer_denominator"]["producer_form_vector_sha256"],
        "range_vector_sha256": payload["promotion"]["range_vector_sha256"],
        "packed_bytes_sha256": payload["promotion"]["packed_bytes_sha256"],
    }


def _load_artifact(
    root: Path, artifact_dir: Path | str
) -> tuple[Path, dict[str, Any], bytes, dict[str, Any], dict[str, bytes]]:
    artifact = _artifact_path(root, artifact_dir)
    expected_names = {MANIFEST_NAME, PAYLOAD_NAME, BUNDLE_NAME}
    entries = list(artifact.iterdir())
    entry_names = {entry.name for entry in entries}
    if entry_names not in (expected_names, expected_names | {"candidate"}):
        raise ValueError("artifact file set changed")
    for entry in entries:
        if entry.is_symlink():
            raise ValueError("artifact file set changed")
        if entry.name == "candidate":
            if not entry.is_dir():
                raise ValueError("artifact file set changed")
        elif not entry.is_file():
            raise ValueError("artifact file set changed")
    files = {name: (artifact / name).read_bytes() for name in expected_names}
    try:
        manifest = json.loads(files[MANIFEST_NAME].decode("utf-8"))
        payload = json.loads(files[PAYLOAD_NAME].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("artifact JSON is invalid") from error
    if _canonical(manifest) != files[MANIFEST_NAME] or _canonical(payload) != files[PAYLOAD_NAME]:
        raise ValueError("artifact JSON is not canonical")
    return artifact, payload, files[BUNDLE_NAME], manifest, files


def _validated_artifact_reference(root: Path, value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} artifact path changed")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != value:
        raise ValueError(f"{label} artifact path changed")
    resolved = (root / relative).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} artifact path changed") from error
    return value


def _verify_artifact(
    root: Path | str,
    artifact_dir: Path | str,
    *,
    allow_candidate: bool = False,
    use_frozen_coverage: bool = False,
    coverage_baseline_artifact: Path | str | None = None,
) -> dict[str, Any]:
    repository = _validate_root(root)
    artifact, payload, bundle, manifest, files = _load_artifact(repository, artifact_dir)
    status = manifest.get("artifact_status")
    if status == "candidate" and not allow_candidate:
        raise ValueError("candidate artifact requires explicit opt-in")
    if status not in ({"candidate", "accepted"} if allow_candidate else {"accepted"}):
        raise ValueError("artifact status changed")
    payload_coverage_source = payload.get("coverage_baseline_source")
    if status == "accepted" and coverage_baseline_artifact is not None:
        raise ValueError(
            "accepted artifact does not accept an external coverage baseline"
        )
    if status == "accepted" and payload_coverage_source is not None:
        if not isinstance(payload_coverage_source, dict):
            raise ValueError("coverage baseline source changed")
        effective_coverage_artifact: Path | str | None = payload_coverage_source.get(
            "artifact"
        )
    else:
        effective_coverage_artifact = coverage_baseline_artifact
    embedded_candidate = artifact / "candidate"
    if status == "candidate" and embedded_candidate.exists():
        raise ValueError("candidate artifact contains an unexpected embedded candidate")
    if status == "accepted" and not embedded_candidate.is_dir():
        raise ValueError("accepted artifact is missing its embedded candidate")
    base_manifest_keys = {
        "schema", "artifact_schema", "artifact_status", "rom",
        "coverage_baseline", "coverage_projection", "upstream_receipts",
        "promotion", "promotion_ranges", "semantic_contract",
        "producer_denominator", "gap_exclusion", "scope", "limitations",
        "files", "implementation", "producer", "verification", "summary",
    }
    if payload_coverage_source is not None:
        base_manifest_keys.add("coverage_baseline_source")
    expected_manifest_keys = base_manifest_keys if status == "candidate" else base_manifest_keys | {"acceptance", "verifier"}
    if set(manifest) != expected_manifest_keys:
        raise ValueError("manifest schema changed")
    if manifest.get("schema") != PROMOTION_SCHEMA or manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("manifest schema changed")
    if manifest.get("files") != {
        PAYLOAD_NAME: {"size": len(files[PAYLOAD_NAME]), "sha256": _sha(files[PAYLOAD_NAME])},
        BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)},
    }:
        raise ValueError("manifest file receipts changed")
    expected, expected_bundle = _expected_payload(
        repository,
        _safe_file(repository, ROM_PATH).read_bytes(),
        use_live_coverage=(
            status == "candidate"
            and not use_frozen_coverage
            and effective_coverage_artifact is None
        ),
        coverage_baseline_artifact=effective_coverage_artifact,
    )
    if bundle != expected_bundle:
        raise ValueError("packed binary differs from raw-ROM reconstruction")
    expected_payload = {**expected, "implementation": _implementation(repository)}
    if payload != expected_payload:
        raise ValueError("payload contract changed")
    mirrored = {
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "coverage_projection": payload["coverage_projection"],
        "upstream_receipts": payload["upstream_receipts"],
        "promotion": payload["promotion"],
        "promotion_ranges": payload["promotion_ranges"],
        "semantic_contract": _semantic_contract(payload),
        "producer_denominator": payload["producer_denominator"],
        "gap_exclusion": payload["gap_exclusion"],
        "scope": payload["scope"],
        "limitations": payload["limitations"],
        "implementation": payload["implementation"],
        "summary": payload["summary"],
    }
    if payload_coverage_source is not None:
        mirrored["coverage_baseline_source"] = payload_coverage_source
    if any(manifest.get(key) != value for key, value in mirrored.items()):
        raise ValueError("manifest mirrored contract changed")

    artifact_relative = artifact.relative_to(repository).as_posix()
    acceptance_command: list[str] | None = None
    if status == "candidate":
        producer_output = artifact_relative
    else:
        acceptance = manifest.get("acceptance")
        if not isinstance(acceptance, dict):
            raise ValueError("accepted artifact acceptance receipt changed")
        candidate_artifact = _validated_artifact_reference(
            repository, acceptance.get("candidate_artifact"), "candidate"
        )
        expected_candidate_artifact = embedded_candidate.relative_to(repository).as_posix()
        if candidate_artifact != expected_candidate_artifact:
            raise ValueError("accepted artifact candidate path changed")
        source_candidate_artifact = _validated_artifact_reference(
            repository, acceptance.get("source_candidate_artifact"), "source candidate"
        )
        source_candidate_identity = acceptance.get("source_candidate_identity")
        if (
            not isinstance(source_candidate_identity, dict)
            or set(source_candidate_identity) != {
                "artifact_status", "manifest_sha256", "payload_sha256", "bundle_sha256"
            }
            or source_candidate_identity.get("artifact_status") != "candidate"
            or any(
                not isinstance(source_candidate_identity.get(key), str)
                or len(source_candidate_identity[key]) != 64
                or any(character not in "0123456789abcdef" for character in source_candidate_identity[key])
                for key in ("manifest_sha256", "payload_sha256", "bundle_sha256")
            )
        ):
            raise ValueError("accepted artifact source candidate identity changed")
        output_artifact = _validated_artifact_reference(
            repository, acceptance.get("output_artifact"), "output"
        )
        if output_artifact != artifact_relative:
            raise ValueError("accepted artifact output path changed")
        candidate_directory = _artifact_path(repository, candidate_artifact)
        if candidate_directory == artifact:
            raise ValueError("accepted artifact cannot cite itself as its candidate")
        candidate_report = _verify_artifact(
            repository,
            candidate_directory,
            allow_candidate=True,
            use_frozen_coverage=(effective_coverage_artifact is None),
            coverage_baseline_artifact=effective_coverage_artifact,
        )
        if candidate_report.get("artifact_status") != "candidate":
            raise ValueError("accepted artifact must cite a verified candidate")
        _, _, candidate_bundle, _, candidate_files = _load_artifact(
            repository, candidate_directory
        )
        acceptance_command = [
            "python3", "tools/verify_rom_m4a_initializer_chain.py",
            source_candidate_artifact,
        ]
        if effective_coverage_artifact is not None:
            acceptance_command += [
                "--coverage-baseline-artifact",
                Path(effective_coverage_artifact).as_posix(),
            ]
        acceptance_command += ["--accept-to", output_artifact]
        candidate_identity = {
            "artifact_status": "candidate",
            "manifest_sha256": _sha(candidate_files[MANIFEST_NAME]),
            "payload_sha256": _sha(candidate_files[PAYLOAD_NAME]),
            "bundle_sha256": _sha(candidate_bundle),
        }
        if (
            candidate_files[PAYLOAD_NAME] != files[PAYLOAD_NAME]
            or candidate_bundle != bundle
        ):
            raise ValueError("accepted artifact differs from cited candidate")
        expected_acceptance = {
            "kind": "independent-candidate-acceptance",
            "candidate_artifact": candidate_artifact,
            "source_candidate_artifact": source_candidate_artifact,
            "source_candidate_identity": source_candidate_identity,
            "output_artifact": output_artifact,
            "command": acceptance_command,
            "candidate_identity": candidate_identity,
        }
        if acceptance != expected_acceptance:
            raise ValueError("accepted artifact acceptance receipt changed")
        producer_output = candidate_artifact

    producer_command = [
        "python3",
        "tools/export_rom_m4a_initializer_chain.py",
    ]
    if effective_coverage_artifact is not None:
        producer_command += [
            "--coverage-baseline-artifact",
            Path(effective_coverage_artifact).as_posix(),
        ]
    producer_command += ["--output", producer_output]
    expected_producer = {
        "kind": "artifact-candidate-construction",
        "output_artifact": producer_output,
        "command": producer_command,
    }
    if manifest.get("producer") != expected_producer:
        raise ValueError("manifest producer command changed")
    if status == "candidate":
        if manifest.get("verification") != {"status": "pending", "report": None}:
            raise ValueError("candidate verification metadata changed")
    else:
        verifier_receipt = {
            "path": "tools/verify_rom_m4a_initializer_chain.py",
            "sha256": _implementation(repository)["verifier"]["sha256"],
            "command": acceptance_command,
        }
        if manifest.get("verifier") != verifier_receipt:
            raise ValueError("accepted verifier receipt changed")
        if manifest.get("verification") != {
            "status": "verified",
            "contract_ok": True,
            "schema": VERIFY_SCHEMA,
            "summary": expected["summary"],
        }:
            raise ValueError("accepted verification receipt changed")
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "contract_ok": True,
        "artifact_status": status,
        "artifact": str(artifact),
        "summary": expected["summary"],
        "bundle_sha256": _sha(bundle),
        "payload_sha256": _sha(files[PAYLOAD_NAME]),
        "manifest_sha256": _sha(files[MANIFEST_NAME]),
        "coverage_baseline_sha256": COVERAGE_SHA256,
    }


def verify_artifact(
    root: Path | str,
    artifact_dir: Path | str,
    *,
    allow_candidate: bool = False,
    coverage_baseline_artifact: Path | str | None = None,
) -> dict[str, Any]:
    """Verify a candidate or accepted artifact from explicit evidence inputs."""

    return _verify_artifact(
        root,
        artifact_dir,
        allow_candidate=allow_candidate,
        use_frozen_coverage=False,
        coverage_baseline_artifact=coverage_baseline_artifact,
    )


def _validate_output(root: Path, output: Path | str) -> Path:
    value = Path(output).expanduser()
    if not value.is_absolute():
        value = root / value
    absolute = Path(os.path.abspath(value))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"output path uses a symlink: {cursor}")
    value = value.resolve(strict=False)
    try:
        value.relative_to(root)
    except ValueError as error:
        raise ValueError("output must stay inside repository root") from error
    if value == root:
        raise ValueError("output must not be repository root")
    if value.exists():
        if value.is_symlink() or not value.is_dir():
            raise ValueError("output must be a new directory")
        if any(value.iterdir()):
            raise ValueError("output directory must be empty")
    return value


def accept_candidate(
    root: Path | str,
    candidate: Path | str,
    output: Path | str = ARTIFACT_RELATIVE,
    *,
    coverage_baseline_artifact: Path | str | None = None,
) -> dict[str, Any]:
    repository = _validate_root(root)
    canonical_coverage_artifact: Path | None = None
    if coverage_baseline_artifact is not None:
        _, coverage_source = _load_coverage_from_artifact(
            repository, coverage_baseline_artifact
        )
        canonical_coverage_artifact = Path(coverage_source["artifact"])
    report = verify_artifact(
        repository,
        candidate,
        allow_candidate=True,
        coverage_baseline_artifact=canonical_coverage_artifact,
    )
    if report["artifact_status"] != "candidate":
        raise ValueError("only a candidate artifact can be accepted")
    candidate_directory, _, bundle, manifest, files = _load_artifact(repository, candidate)
    target = _validate_output(repository, output)
    source_candidate_artifact = candidate_directory.relative_to(repository).as_posix()
    output_artifact = target.relative_to(repository).as_posix()
    candidate_artifact = (target / "candidate").relative_to(repository).as_posix()
    acceptance_command = [
        "python3", "tools/verify_rom_m4a_initializer_chain.py",
        source_candidate_artifact,
    ]
    if canonical_coverage_artifact is not None:
        acceptance_command += [
            "--coverage-baseline-artifact",
            canonical_coverage_artifact.as_posix(),
        ]
    acceptance_command += ["--accept-to", output_artifact]
    source_candidate_identity = {
        "artifact_status": "candidate",
        "manifest_sha256": _sha(files[MANIFEST_NAME]),
        "payload_sha256": _sha(files[PAYLOAD_NAME]),
        "bundle_sha256": _sha(bundle),
    }
    embedded_candidate = dict(manifest)
    embedded_producer_command = [
        "python3",
        "tools/export_rom_m4a_initializer_chain.py",
    ]
    if canonical_coverage_artifact is not None:
        embedded_producer_command += [
            "--coverage-baseline-artifact",
            canonical_coverage_artifact.as_posix(),
        ]
    embedded_producer_command += ["--output", candidate_artifact]
    embedded_candidate["producer"] = {
        "kind": "artifact-candidate-construction",
        "output_artifact": candidate_artifact,
        "command": embedded_producer_command,
    }
    embedded_candidate_raw = _canonical(embedded_candidate)
    candidate_identity = {
        "artifact_status": "candidate",
        "manifest_sha256": _sha(embedded_candidate_raw),
        "payload_sha256": _sha(files[PAYLOAD_NAME]),
        "bundle_sha256": _sha(bundle),
    }
    accepted = dict(embedded_candidate)
    accepted["artifact_status"] = "accepted"
    accepted["acceptance"] = {
        "kind": "independent-candidate-acceptance",
        "candidate_artifact": candidate_artifact,
        "source_candidate_artifact": source_candidate_artifact,
        "source_candidate_identity": source_candidate_identity,
        "output_artifact": output_artifact,
        "command": acceptance_command,
        "candidate_identity": candidate_identity,
    }
    accepted["verifier"] = {
        "path": "tools/verify_rom_m4a_initializer_chain.py",
        "sha256": _implementation(repository)["verifier"]["sha256"],
        "command": acceptance_command,
    }
    accepted["verification"] = {
        "status": "verified",
        "contract_ok": True,
        "schema": VERIFY_SCHEMA,
        "summary": report["summary"],
    }
    accepted_raw = _canonical(accepted)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    published = False
    try:
        (staging / PAYLOAD_NAME).write_bytes(files[PAYLOAD_NAME])
        (staging / BUNDLE_NAME).write_bytes(bundle)
        (staging / MANIFEST_NAME).write_bytes(accepted_raw)
        embedded_directory = staging / "candidate"
        embedded_directory.mkdir()
        (embedded_directory / PAYLOAD_NAME).write_bytes(files[PAYLOAD_NAME])
        (embedded_directory / BUNDLE_NAME).write_bytes(bundle)
        (embedded_directory / MANIFEST_NAME).write_bytes(embedded_candidate_raw)
        if target.exists():
            target.rmdir()
        os.replace(staging, target)
        published = True
        accepted_report = verify_artifact(repository, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if published:
            shutil.rmtree(target, ignore_errors=True)
        raise
    return {**accepted_report, "artifact_status": "accepted"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, nargs="?", default=ARTIFACT_RELATIVE)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--allow-candidate", action="store_true")
    parser.add_argument("--coverage-baseline-artifact", type=Path)
    parser.add_argument("--accept-to", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.accept_to is not None:
            if args.allow_candidate:
                raise ValueError("--allow-candidate cannot be combined with --accept-to")
            report = accept_candidate(
                args.root,
                args.artifact,
                args.accept_to,
                coverage_baseline_artifact=args.coverage_baseline_artifact,
            )
        else:
            if args.coverage_baseline_artifact is not None and not args.allow_candidate:
                raise ValueError(
                    "--coverage-baseline-artifact requires --allow-candidate or --accept-to"
                )
            report = verify_artifact(
                args.root,
                args.artifact,
                allow_candidate=args.allow_candidate,
                coverage_baseline_artifact=args.coverage_baseline_artifact,
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"schema": VERIFY_SCHEMA, "verified": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
