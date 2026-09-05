#!/usr/bin/env python3
"""Independently verify the frozen boot Thumb code-to-literal alignment gaps.

The accepted handoff artifact supplies the bounded code/literal inventory.  This
helper binds that artifact by identity, rechecks every range and literal word
against the raw ROM, and derives the positive code-to-literal neighbours.  It
does not read the preflight packet, its report, or the repository-wide coverage
file; the optional ``--contract`` argument is only an extra consistency check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


VERIFY_SCHEMA = "rom-boot-thumb-code-literal-alignment-gaps-verification-v1"
CONTRACT_SCHEMA = "rom-boot-thumb-code-literal-alignment-gaps-contract-v1"
PROMOTION_BATCH = "rom-boot-thumb-code-literal-alignment-gaps-v1"
PRIMARY_CLASS = "boot_thumb_code_literal_alignment_bytes"
CLAIM_KIND = "boot_thumb_code_literal_alignment_gap_bytes"
ALIGNMENT_FORMULA = "gap_start=left_end; gap_end=align4(left_end)=right_start"
ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
SOURCE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
# Kept as a separately patchable verification expectation for mutation tests.
ROM_SHA256 = SOURCE_ROM_SHA256

SOURCE_DIR = Path("artifacts/rom-boot-thumb-handoff-cfg-v1")
SOURCE_MANIFEST_PATH = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD_PATH = SOURCE_DIR / "rom-boot-thumb-handoff-cfg.json"
SOURCE_BINARY_PATH = SOURCE_DIR / "rom-boot-thumb-handoff-cfg.bin"
SOURCE_MANIFEST_SHA256 = "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
SOURCE_PAYLOAD_SHA256 = "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"

SOURCE_EXPORTER_PATH = Path("tools/export_rom_boot_thumb_handoff_cfg.py")
SOURCE_EXPORTER_SHA256 = "1ff330269b4ece58c9cd12d81932cc45decc9ccea49e61502af815e590def337"
SOURCE_VERIFIER_PATH = Path("tools/verify_rom_boot_thumb_handoff_cfg.py")
SOURCE_VERIFIER_SHA256 = "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39"
SOURCE_TEST_PATH = Path("tests/test_export_rom_boot_thumb_handoff_cfg.py")
SOURCE_TEST_SHA256 = "55e6bb77c9044afd53467846415367c1d39356debb9d6848431a2274beebb1cb"

EXPECTED_CONTRACT_SHA256 = "2298b1f03236d77eb14e0970612c54cbfa2ba10f92ba595fc1cb6426a61f338b"
EXPECTED_CODE_RANGE_COUNT = 27
EXPECTED_CODE_BYTES = 1_226
EXPECTED_LITERAL_RANGE_COUNT = 22
EXPECTED_LITERAL_BYTES = 296
EXPECTED_LITERAL_BINDING_COUNT = 77
EXPECTED_GAP_COUNT = 12
EXPECTED_GAP_BYTES = 24
EXPECTED_RANGE_VECTOR_SHA256 = "dec4177a9818ff7b3349a7c678f8e4a223f4a6e8ac254e2cd81bb4cf1362ce58"
EXPECTED_BOUNDARY_VECTOR_SHA256 = "2c1e60388f8fd7ef11118e7a61ac93fa7816aa6012e7f6e3478a45d4d080b54f"
EXPECTED_PACKED_BYTES_SHA256 = "9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0"
EXPECTED_ZERO_PAIR_SHA256 = "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
EXPECTED_FLOW_COUNTS = {
    "indirect_branch": 1,
    "return": 5,
    "unconditional_branch": 6,
}
SOURCE_CODE_SEMANTIC_CLASS = "armv4t_cfg_handoff_thumb_code"
SOURCE_LITERAL_SEMANTIC_CLASS = "thumb_pc_relative_literal"
EXPECTED_CODE_RANGE_VECTOR_SHA256 = "c1322a0cc9eeb8a252af3993b36fdd772d4f7e907629960ddd2080875f446564"
EXPECTED_LITERAL_RANGE_VECTOR_SHA256 = "2536966a4ab33e372e305a349c63faae8e15976c3e56cfc28b3fed72c878f39c"
EXPECTED_BINDING_VECTOR_SHA256 = "a41fd583ca65ccfc2084064d1809c9a04c7185f69c4adb6bba1129ad3af60917"

SOURCE_SUMMARY = {
    "block_count": 125,
    "budget_exhausted": False,
    "external_edge_count": 14,
    "external_target_count": 11,
    "frontier_count": 2,
    "instruction_bytes": EXPECTED_CODE_BYTES,
    "instruction_count": 583,
    "internal_edge_count": 164,
    "literal_bytes": EXPECTED_LITERAL_BYTES,
    "literal_ref_count": EXPECTED_LITERAL_BINDING_COUNT,
    "literal_word_count": 74,
    "raw_indirect_pc_count": 15,
    "return_count": 14,
}
SOURCE_PROMOTION = {
    "code_bytes": EXPECTED_CODE_BYTES,
    "code_range_count": EXPECTED_CODE_RANGE_COUNT,
    "current_known_overlap_bytes": 0,
    "future_coverage_claim_projection": {
        "code_claim_count": EXPECTED_CODE_RANGE_COUNT,
        "literal_claim_count": EXPECTED_LITERAL_RANGE_COUNT,
        "semantically_merged_union_claim_count": 0,
    },
    "literal_bytes": EXPECTED_LITERAL_BYTES,
    "literal_range_count": EXPECTED_LITERAL_RANGE_COUNT,
    "union_bytes": 1522,
    "union_bytes_sha256": "73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22",
    "union_range_count": 25,
    "union_range_vector_sha256": "f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5",
    "wide_envelope": [397228, 639128],
    "wide_envelope_is_claim": False,
}
SOURCE_SCOPE = {
    "allocatable_free_space_proven": False,
    "arm_startup_handoff_rebuilt_from_raw_rom": True,
    "callee_abi_or_semantics_proven": False,
    "code_and_literal_ranges_kept_separate": True,
    "current_unknown_only_promotion": True,
    "dynamic_callback_targets_resolved": False,
    "editing_relocation_writeback_safe": False,
    "envelope_gaps_classified": False,
    "existing_exact_entries_opaque": True,
    "global_caller_denominator_complete": False,
    "global_code_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "iwram_contents_or_loader_classified": False,
    "natural_execution_reachability_complete": False,
    "new_61624_entry_proven_without_scheduling": True,
    "owner_061624_full_range_is_code": False,
    "runtime_reachability_complete": False,
    "target_limited_thumb_cfg_complete": True,
}
SOURCE_IMPLEMENTATION = {
    "exporter": {"path": SOURCE_EXPORTER_PATH.as_posix(), "sha256": SOURCE_EXPORTER_SHA256},
    "test": {"path": SOURCE_TEST_PATH.as_posix(), "sha256": SOURCE_TEST_SHA256},
    "verifier": {"path": SOURCE_VERIFIER_PATH.as_posix(), "sha256": SOURCE_VERIFIER_SHA256},
}
SOURCE_FILES = {
    SOURCE_PAYLOAD_PATH.name: {"sha256": SOURCE_PAYLOAD_SHA256, "size": 746981},
    "rom-boot-thumb-handoff-cfg.bin": {
        "sha256": "73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22",
        "size": 1522,
    },
}

NON_CLAIMS = {
    "original_artifact_envelope_gaps_classified": False,
    "complete_boot_runtime": False,
    "natural_execution_reachability": False,
    "global_code_or_literal_denominator": False,
    "indirect_target_resolution": False,
    "padding": False,
    "reserved_space": False,
    "free_or_allocatable_space": False,
    "editing_or_relocation_safety": False,
}
LIMITATIONS = [
    "Only the twelve fixed positive code-to-consumed-literal neighbours are classified as align4 gap bytes.",
    "The gap bytes are not claimed to be instructions, padding, reserved space, free space, or allocatable space.",
    "The accepted source artifact's wide envelope gaps remain historical non-claims; this packet is additive.",
    "This verifier does not prove complete boot runtime, natural execution reachability, global code/literal coverage, or indirect target resolution.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _compact_sha(value: object) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _canonical_sha(value: object) -> str:
    return _sha((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _safe_root(root: Path | str) -> Path:
    requested = Path(root).expanduser()
    absolute = requested if requested.is_absolute() else Path.cwd() / requested
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("repository root uses a symlink")
    try:
        resolved = requested.resolve(strict=True)
    except OSError as error:
        raise ValueError("repository root is missing") from error
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    for marker in (Path("rom"), Path("artifacts"), Path("tools"), Path("tests")):
        candidate = resolved / marker
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("repository root is outside the expected project tree")
    return resolved


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository-relative input: {relative}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    try:
        resolved = cursor.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"repository input is missing: {relative}") from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes repository root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _read_bound(root: Path, relative: Path, expected_sha256: str, label: str) -> bytes:
    path = _safe_file(root, relative)
    raw = path.read_bytes()
    if _sha(raw) != expected_sha256:
        raise ValueError(f"{label} identity changed")
    return raw


def _read_json_bound(root: Path, relative: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    raw = _read_bound(root, relative, expected_sha256, label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not canonical JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _rom_slice(rom: bytes, start: int, end: int, label: str = "ROM range") -> bytes:
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or start >= end or end > len(rom):
        raise ValueError(f"{label} is outside the ROM")
    return rom[start:end]


def _validate_ranges(value: object, count: int, byte_count: int, label: str, *, alignment: int) -> list[list[int]]:
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"{label} denominator changed")
    result: list[list[int]] = []
    previous_end = -1
    total = 0
    for row in value:
        if (
            not isinstance(row, list)
            or len(row) != 2
            or not all(isinstance(part, int) for part in row)
            or row[0] < 0
            or row[0] >= row[1]
            or row[0] < previous_end
            or row[0] % alignment
            or row[1] % alignment
        ):
            raise ValueError(f"invalid {label} range")
        result.append([row[0], row[1]])
        total += row[1] - row[0]
        previous_end = row[1]
    if total != byte_count:
        raise ValueError(f"{label} byte denominator changed")
    return result


def _merge_ranges(ranges: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _validate_source(
    rom: bytes,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    payload_raw: bytes | None = None,
) -> tuple[
    list[list[int]],
    list[list[int]],
    dict[int, dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    expected_rom = {"path": ROM_PATH.as_posix(), "sha256": SOURCE_ROM_SHA256, "size": ROM_SIZE}
    manifest_files = manifest.get("files")
    expected_payload_file = {
        "sha256": SOURCE_PAYLOAD_SHA256,
        "size": len(payload_raw) if payload_raw is not None else SOURCE_FILES[SOURCE_PAYLOAD_PATH.name]["size"],
    }
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema") != "rom-boot-thumb-handoff-cfg-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("rom") != expected_rom
        or manifest.get("implementation") != SOURCE_IMPLEMENTATION
        or manifest.get("scope") != SOURCE_SCOPE
        or manifest.get("summary") != SOURCE_SUMMARY
        or manifest.get("promotion") != SOURCE_PROMOTION
        or not isinstance(manifest_files, dict)
        or manifest_files.get(SOURCE_PAYLOAD_PATH.name) != expected_payload_file
        or manifest_files.get("rom-boot-thumb-handoff-cfg.bin") != SOURCE_FILES["rom-boot-thumb-handoff-cfg.bin"]
    ):
        raise ValueError("accepted source manifest contract changed")
    if (
        payload.get("schema") != "rom-boot-thumb-handoff-cfg-v1"
        or payload.get("rom") != expected_rom
        or payload.get("summary") != SOURCE_SUMMARY
        or payload.get("promotion") != SOURCE_PROMOTION
        or payload.get("scope") != SOURCE_SCOPE
        or payload.get("implementation") != SOURCE_IMPLEMENTATION
    ):
        raise ValueError("accepted source payload contract changed")

    code = _validate_ranges(payload.get("code_ranges"), EXPECTED_CODE_RANGE_COUNT, EXPECTED_CODE_BYTES, "code", alignment=2)
    literal = _validate_ranges(payload.get("literal_ranges"), EXPECTED_LITERAL_RANGE_COUNT, EXPECTED_LITERAL_BYTES, "literal", alignment=4)
    if _compact_sha(code) != EXPECTED_CODE_RANGE_VECTOR_SHA256:
        raise ValueError("source code range vector changed")
    if _compact_sha(literal) != EXPECTED_LITERAL_RANGE_VECTOR_SHA256:
        raise ValueError("source literal range vector changed")
    if any(a < b and c < d and a < d and c < b for a, b in code for c, d in literal):
        raise ValueError("source code/literal ranges overlap")

    instructions = payload.get("instructions")
    if not isinstance(instructions, list) or len(instructions) != SOURCE_SUMMARY["instruction_count"]:
        raise ValueError("source instruction denominator changed")
    by_offset: dict[int, dict[str, Any]] = {}
    for item in instructions:
        if not isinstance(item, dict):
            raise ValueError("invalid source instruction")
        offset = item.get("file_offset")
        size = item.get("size")
        raw_hex = item.get("raw_hex")
        if (
            not isinstance(offset, int)
            or offset in by_offset
            or offset % 2
            or size not in (2, 4)
            or not isinstance(raw_hex, str)
            or len(raw_hex) != size * 2
            or item.get("accepted") is not True
            or item.get("mode") != "thumb"
            or not any(start <= offset and offset + size <= end for start, end in code)
        ):
            raise ValueError("invalid source instruction inventory")
        raw = _rom_slice(rom, offset, offset + size, "source instruction")
        if raw.hex() != raw_hex or item.get("bytes_sha256") != _sha(raw):
            terminal = any(offset + size == end for _, end in code)
            label = "source terminal branch/return instruction bytes" if terminal else "source instruction bytes"
            raise ValueError(f"{label} changed at 0x{offset:06X}")
        successors = item.get("successors")
        if not isinstance(successors, list):
            raise ValueError("source instruction successors changed")
        for successor in successors:
            if not isinstance(successor, dict) or not isinstance(successor.get("file_offset"), int) or successor.get("mode") != "thumb":
                raise ValueError("source instruction successor changed")
        by_offset[offset] = item
    for start, end in code:
        cursor = start
        while cursor < end:
            item = by_offset.get(cursor)
            if item is None:
                raise ValueError(f"source code range is not instruction-tiled at 0x{cursor:06X}")
            cursor += item["size"]
        if cursor != end:
            raise ValueError("source code range instruction boundary changed")
    if sum(1 for item in by_offset.values() if item.get("file_offset") is not None) != SOURCE_SUMMARY["instruction_count"]:
        raise ValueError("source instruction denominator changed")

    bindings = payload.get("literal_bindings")
    if not isinstance(bindings, list) or len(bindings) != EXPECTED_LITERAL_BINDING_COUNT:
        raise ValueError("literal binding denominator changed")
    binding_vector: list[list[object]] = []
    intervals: list[tuple[int, int]] = []
    for item in bindings:
        if not isinstance(item, dict):
            raise ValueError("invalid literal binding")
        literal_offset = item.get("literal_offset")
        instruction_offset = item.get("instruction_offset")
        load_offset = item.get("load_offset")
        raw_hex = item.get("raw_hex")
        if (
            not isinstance(literal_offset, int)
            or not isinstance(instruction_offset, int)
            or load_offset != instruction_offset
            or not isinstance(raw_hex, str)
            or len(raw_hex) != 8
            or instruction_offset not in by_offset
            or not any(start <= literal_offset and literal_offset + 4 <= end for start, end in literal)
        ):
            raise ValueError("invalid literal binding")
        raw = _rom_slice(rom, literal_offset, literal_offset + 4, "literal binding")
        if raw.hex() != raw_hex:
            raise ValueError("literal binding differs from raw ROM")
        intervals.append((literal_offset, literal_offset + 4))
        binding_vector.append([instruction_offset, literal_offset, raw_hex])
    if _compact_sha(binding_vector) != EXPECTED_BINDING_VECTOR_SHA256:
        raise ValueError("literal binding vector changed")
    if len(set(intervals)) != SOURCE_SUMMARY["literal_word_count"]:
        raise ValueError("literal word denominator changed")
    for start, end in literal:
        covered = sorted((a, b) for a, b in set(intervals) if start <= a and b <= end)
        cursor = start
        for a, b in covered:
            if a != cursor:
                raise ValueError("consumed-literal range is not fully bound")
            cursor = b
        if cursor != end:
            raise ValueError("consumed-literal range is not fully bound")

    coverage_claims = payload.get("coverage_claims")
    if not isinstance(coverage_claims, list) or len(coverage_claims) != (
        EXPECTED_CODE_RANGE_COUNT + EXPECTED_LITERAL_RANGE_COUNT
    ):
        raise ValueError("source coverage-claim denominator changed")
    source_claims: dict[tuple[str, int], dict[str, Any]] = {}
    for kind, ranges, semantic_class, id_kind in (
        ("code", code, SOURCE_CODE_SEMANTIC_CLASS, "code"),
        ("literal", literal, SOURCE_LITERAL_SEMANTIC_CLASS, "literal"),
    ):
        base = 0 if kind == "code" else EXPECTED_CODE_RANGE_COUNT
        for index, (start, end) in enumerate(ranges):
            raw = _rom_slice(rom, start, end, f"source {kind} claim")
            expected = {
                "baseline_unknown_only": True,
                "id": f"thumb-{id_kind}-{index:02d}-{start:06x}",
                "range": [start, end],
                "semantic_class": semantic_class,
                "sha256": _sha(raw),
                "size": end - start,
            }
            if coverage_claims[base + index] != expected:
                raise ValueError(f"source {kind} coverage claim changed")
            source_claims[(kind, index)] = expected
    return code, literal, by_offset, source_claims


def _incoming(instructions: dict[int, dict[str, Any]], target: int) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for offset, item in instructions.items():
        for successor in item.get("successors", []):
            if successor.get("file_offset") == target:
                result.append((offset, successor.get("kind", "")))
    return result


def _decode_terminal(rom: bytes, terminal_offset: int, left_end: int, right_start: int, instructions: dict[int, dict[str, Any]]) -> dict[str, Any]:
    if terminal_offset < 2 or terminal_offset + 2 > len(rom) or terminal_offset % 2 or terminal_offset + 2 != left_end:
        raise ValueError("invalid terminal instruction offset")
    opcode = int.from_bytes(rom[terminal_offset : terminal_offset + 2], "little")
    terminal: dict[str, Any] = {
        "offset": terminal_offset,
        "raw_hex": rom[terminal_offset : terminal_offset + 2].hex(),
        "opcode": opcode,
    }
    source = instructions.get(terminal_offset)
    if source is None or source.get("size") != 2:
        raise ValueError("source terminal instruction binding changed")
    if opcode & 0xF800 == 0xE000:
        immediate = opcode & 0x07FF
        if immediate & 0x0400:
            immediate -= 0x0800
        target = terminal_offset + 4 + (immediate << 1)
        if target < 0 or target >= len(rom) or target % 2:
            raise ValueError("unconditional branch target is invalid")
        if left_end <= target < right_start:
            raise ValueError("unconditional branch falls through the gap")
        terminal.update({"flow_kind": "unconditional_branch", "target": target})
        successors = source.get("successors")
        if successors != [{"file_offset": target, "kind": "branch_target", "mode": "thumb"}]:
            raise ValueError("unconditional branch target/fallthrough binding changed")
        if source.get("flow_kind") != "unconditional_branch" or source.get("raw_flow_kind") != "unconditional_branch":
            raise ValueError("source terminal flow binding changed")
        return terminal
    if opcode & 0xFF87 == 0x4700:
        register = (opcode >> 3) & 0x0F
        previous_offset = terminal_offset - 2
        previous = instructions.get(previous_offset)
        previous_raw = int.from_bytes(rom[previous_offset:terminal_offset], "little")
        terminal.update({"register": register, "previous_raw_hex": rom[previous_offset:terminal_offset].hex(), "target": None})
        exact_pop = previous_raw in (0xBC01, 0xBC02) and previous_raw == (0xBC00 | (1 << register))
        unique_fallthrough = _incoming(instructions, terminal_offset) == [(previous_offset, "fallthrough")]
        previous_linear = (
            previous is not None
            and previous.get("size") == 2
            and previous.get("flow_kind") == "linear"
            and previous.get("successors") == [{"file_offset": terminal_offset, "kind": "fallthrough", "mode": "thumb"}]
        )
        is_return = exact_pop and unique_fallthrough and previous_linear
        terminal["flow_kind"] = "return" if is_return else "indirect_branch"
        if source.get("flow_kind") != terminal["flow_kind"] or source.get("raw_flow_kind") != "indirect_branch":
            raise ValueError("source terminal return/indirect binding changed")
        if source.get("successors") != []:
            raise ValueError("terminal has an unexpected fallthrough")
        if is_return and not (previous is not None and previous.get("raw_hex") == rom[previous_offset:terminal_offset].hex()):
            raise ValueError("source return predecessor binding changed")
        return terminal
    raise ValueError(f"code range does not end in a supported no-fallthrough opcode: 0x{terminal_offset:06X}")


def _derive_rows(
    rom: bytes,
    code: list[list[int]],
    literal: list[list[int]],
    instructions: dict[int, dict[str, Any]],
    source_claims: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered = sorted(
        [(start, end, "code", index) for index, (start, end) in enumerate(code)]
        + [(start, end, "literal", index) for index, (start, end) in enumerate(literal)]
    )
    for left, right in zip(ordered, ordered[1:]):
        if left[1] > right[0]:
            raise ValueError("source code/literal ranges overlap")
    positive = [
        (left, right)
        for left, right in zip(ordered, ordered[1:])
        if left[2] == "code" and right[2] == "literal" and left[1] < right[0]
    ]
    if len(positive) != EXPECTED_GAP_COUNT:
        raise ValueError("positive code-to-literal neighbour denominator changed")
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(positive):
        left_start, left_end, _, left_index = left
        right_start, right_end, _, right_index = right
        aligned = (left_end + 3) & ~3
        if aligned != right_start or right_start - left_end != 2:
            raise ValueError("positive code-to-literal neighbour is not an align4 gap")
        raw = _rom_slice(rom, left_end, right_start, "alignment gap")
        if raw != b"\x00\x00" or _sha(raw) != EXPECTED_ZERO_PAIR_SHA256:
            raise ValueError("alignment gap is not the frozen two-byte zero range")
        terminal = _decode_terminal(rom, left_end - 2, left_end, right_start, instructions)
        left_claim = source_claims[("code", left_index)]
        right_claim = source_claims[("literal", right_index)]
        rows.append(
            {
                "id": f"boot-thumb-code-literal-gap-{index:02d}-{left_end:06x}",
                "range": [left_end, right_start],
                "size": 2,
                "sha256": _sha(raw),
                "raw_hex": raw.hex(),
                "alignment": {"unit": 4, "left_end": left_end, "align4_left_end": aligned, "right_start": right_start},
                "left": {
                    "kind": "reachable_thumb_code",
                    "source_index": left_index,
                    "source_artifact_claim_id": left_claim["id"],
                    "source_artifact_semantic_class": left_claim["semantic_class"],
                    "range": [left_start, left_end],
                },
                "right": {
                    "kind": "consumed_literal_pool",
                    "source_index": right_index,
                    "source_artifact_claim_id": right_claim["id"],
                    "source_artifact_semantic_class": right_claim["semantic_class"],
                    "range": [right_start, right_end],
                },
                "terminal": terminal,
            }
        )
    return rows


def _boundary_vector(rows: list[dict[str, Any]]) -> list[list[object]]:
    return [
        [
            *row["left"]["range"],
            *row["range"],
            *row["right"]["range"],
            row["terminal"]["offset"],
            row["terminal"]["raw_hex"],
            row["terminal"]["flow_kind"],
            row["terminal"].get("target"),
        ]
        for row in rows
    ]


def _validate_optional_contract(root: Path, relative: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    raw = _read_bound(root, relative, EXPECTED_CONTRACT_SHA256, "optional contract")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("optional contract is not canonical JSON") from error
    if not isinstance(contract, dict) or contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError("optional contract schema changed")
    candidate = contract.get("candidate")
    denominator = contract.get("source_denominator")
    if not isinstance(candidate, dict) or not isinstance(denominator, dict):
        raise ValueError("optional contract shape changed")
    checks = {
        "gap_count": summary["gap_count"],
        "gap_bytes": summary["gap_bytes"],
        "range_vector_sha256": summary["range_vector_sha256"],
        "boundary_vector_sha256": summary["boundary_vector_sha256"],
        "packed_bytes_sha256": summary["packed_bytes_sha256"],
        "flow_counts": summary["flow_counts"],
    }
    if any(candidate.get(key) != value for key, value in checks.items()):
        raise ValueError("optional contract candidate differs from raw derivation")
    expected_denominator = {
        "code_range_count": EXPECTED_CODE_RANGE_COUNT,
        "code_bytes": EXPECTED_CODE_BYTES,
        "consumed_literal_range_count": EXPECTED_LITERAL_RANGE_COUNT,
        "consumed_literal_bytes": EXPECTED_LITERAL_BYTES,
        "literal_binding_count": EXPECTED_LITERAL_BINDING_COUNT,
        "all_positive_code_to_literal_neighbours_selected": True,
    }
    if any(denominator.get(key) != value for key, value in expected_denominator.items()):
        raise ValueError("optional contract source denominator changed")
    contract_rows = candidate.get("rows")
    if not isinstance(contract_rows, list) or len(contract_rows) != len(rows):
        raise ValueError("optional contract row denominator changed")
    for actual, expected in zip(rows, contract_rows):
        if not isinstance(expected, dict):
            raise ValueError("optional contract row shape changed")
        for key in ("id", "range", "size", "sha256", "raw_hex", "alignment", "terminal"):
            if expected.get(key) != actual.get(key):
                raise ValueError("optional contract row differs from raw derivation")


def _report(rows: list[dict[str, Any]], *, rom_sha256: str, source_manifest_sha256: str, source_payload_sha256: str) -> dict[str, Any]:
    ranges = [row["range"] for row in rows]
    packed = b"".join(bytes.fromhex(row["raw_hex"]) for row in rows)
    boundary = _boundary_vector(rows)
    flow_counts = {kind: sum(row["terminal"]["flow_kind"] == kind for row in rows) for kind in sorted(EXPECTED_FLOW_COUNTS)}
    summary = {
        "code_range_count": EXPECTED_CODE_RANGE_COUNT,
        "code_bytes": EXPECTED_CODE_BYTES,
        "consumed_literal_range_count": EXPECTED_LITERAL_RANGE_COUNT,
        "consumed_literal_bytes": EXPECTED_LITERAL_BYTES,
        "literal_binding_count": EXPECTED_LITERAL_BINDING_COUNT,
        "gap_count": len(rows),
        "gap_bytes": len(packed),
        "size_counts": {"2": len(rows)},
        "flow_counts": flow_counts,
        "all_bytes_zero": packed == b"\x00" * len(packed),
        "range_vector_sha256": _compact_sha(ranges),
        "boundary_vector_sha256": _compact_sha(boundary),
        "packed_bytes_sha256": _sha(packed),
    }
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "promotion_batch": PROMOTION_BATCH,
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": rom_sha256},
        "source": {
            "manifest": {"path": SOURCE_MANIFEST_PATH.as_posix(), "sha256": source_manifest_sha256},
            "payload": {"path": SOURCE_PAYLOAD_PATH.as_posix(), "sha256": source_payload_sha256},
            "implementation": SOURCE_IMPLEMENTATION,
        },
        "source_denominator": {
            "target_limited_thumb_cfg_complete": True,
            "code_range_count": EXPECTED_CODE_RANGE_COUNT,
            "code_bytes": EXPECTED_CODE_BYTES,
            "consumed_literal_range_count": EXPECTED_LITERAL_RANGE_COUNT,
            "consumed_literal_bytes": EXPECTED_LITERAL_BYTES,
            "literal_binding_count": EXPECTED_LITERAL_BINDING_COUNT,
            "all_positive_code_to_literal_neighbours_selected": True,
        },
        "summary": summary,
        "candidate": {
            "gap_count": summary["gap_count"],
            "gap_bytes": summary["gap_bytes"],
            "size_counts": summary["size_counts"],
            "flow_counts": summary["flow_counts"],
            "range_vector_sha256": summary["range_vector_sha256"],
            "boundary_vector_sha256": summary["boundary_vector_sha256"],
            "packed_bytes_sha256": summary["packed_bytes_sha256"],
            "all_bytes_zero": summary["all_bytes_zero"],
            "alignment_formula": ALIGNMENT_FORMULA,
            "rows": rows,
        },
        "gaps": rows,
        "limitations": list(LIMITATIONS),
        "non_claims": dict(NON_CLAIMS),
        "source_artifact_historical_envelope_gaps_classified": False,
        "source_wide_envelope_is_claim": False,
        "new_packet_additive": True,
    }
    return report


def _failure(errors: list[str]) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": [error or "verification failed" for error in errors],
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "promotion_batch": PROMOTION_BATCH,
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "limitations": list(LIMITATIONS),
        "non_claims": dict(NON_CLAIMS),
        "source_artifact_historical_envelope_gaps_classified": False,
        "source_wide_envelope_is_claim": False,
        "new_packet_additive": True,
    }


def _verify_with_root(root: Path, rom: bytes, optional_contract: Path | None = None) -> dict[str, Any]:
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")
    manifest_raw = _read_bound(root, SOURCE_MANIFEST_PATH, SOURCE_MANIFEST_SHA256, "source manifest")
    payload_raw = _read_bound(root, SOURCE_PAYLOAD_PATH, SOURCE_PAYLOAD_SHA256, "source payload")
    _read_bound(
        root,
        SOURCE_BINARY_PATH,
        SOURCE_FILES[SOURCE_BINARY_PATH.name]["sha256"],
        "source binary artifact",
    )
    for path, sha256, label in (
        (SOURCE_EXPORTER_PATH, SOURCE_EXPORTER_SHA256, "source exporter"),
        (SOURCE_VERIFIER_PATH, SOURCE_VERIFIER_SHA256, "source verifier"),
        (SOURCE_TEST_PATH, SOURCE_TEST_SHA256, "source test"),
    ):
        _read_bound(root, path, sha256, label)
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        payload = json.loads(payload_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("accepted source JSON is invalid") from error
    if not isinstance(manifest, dict) or not isinstance(payload, dict):
        raise ValueError("accepted source JSON is not an object")
    code, literal, instructions, source_claims = _validate_source(
        rom, manifest, payload, payload_raw
    )
    rows = _derive_rows(rom, code, literal, instructions, source_claims)
    report = _report(rows, rom_sha256=_sha(rom), source_manifest_sha256=_sha(manifest_raw), source_payload_sha256=_sha(payload_raw))
    summary = report["summary"]
    if (
        len(rows) != EXPECTED_GAP_COUNT
        or len(b"".join(bytes.fromhex(row["raw_hex"]) for row in rows)) != EXPECTED_GAP_BYTES
        or summary["range_vector_sha256"] != EXPECTED_RANGE_VECTOR_SHA256
        or summary["boundary_vector_sha256"] != EXPECTED_BOUNDARY_VECTOR_SHA256
        or summary["packed_bytes_sha256"] != EXPECTED_PACKED_BYTES_SHA256
        or summary["flow_counts"] != EXPECTED_FLOW_COUNTS
    ):
        raise ValueError("frozen candidate contract changed")
    if optional_contract is not None:
        _validate_optional_contract(root, optional_contract, rows, summary)
    return report


def verify_root(root: Path | str, *, contract: Path | str | None = None) -> dict[str, Any]:
    """Safely verify ``rom/base.gba`` and its identity-bound source artifact."""

    try:
        resolved_root = _safe_root(root)
        rom_path = _safe_file(resolved_root, ROM_PATH)
        rom = rom_path.read_bytes()
        optional_contract = Path(contract) if contract is not None else None
        return _verify_with_root(resolved_root, rom, optional_contract)
    except (TypeError, ValueError, OSError, KeyError, IndexError) as error:
        return _failure([str(error)])


def verify_rom_bytes(rom: bytes, root: Path | str = ".") -> dict[str, Any]:
    """Verify supplied ROM bytes against the identity-bound source artifact."""

    try:
        resolved_root = _safe_root(root)
        return _verify_with_root(resolved_root, bytes(rom))
    except (TypeError, ValueError, OSError, KeyError, IndexError) as error:
        return _failure([str(error)])


def verify(root: Path | str, *, contract: Path | str | None = None) -> dict[str, Any]:
    return verify_root(root, contract=contract)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--contract", type=Path, default=None)
    args = parser.parse_args(argv)
    report = verify_root(args.root, contract=args.contract)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
