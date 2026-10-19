#!/usr/bin/env python3
"""Pure producer for the five task-callback alignment gaps.

The public entry point takes already-read bytes.  It deliberately has no
repository file access or publication side effects; the parent task owns those
operations and the independent verifier.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable, Sequence


CONTRACT_SHA256 = "bc8d545f5bb9619935abc4fe52b4651967f3fe8d4dbd330cf2688fe74b18164a"
OUTPUT_SCHEMA = "rom-task-callback-078e38-alignment-gaps-v1"
SOURCE_SCHEMA = "rom-task-callback-078e38-closure-v1"
BASELINE_SCHEMA = "rom-byte-coverage-v1"
ROM_PATH = "rom/base.gba"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456
BOUNDARY_KIND = "artifact_bound_align4_bytes"
ID_PREFIX = "task-callback-078e38-align4"

EXPECTED_SUMMARY = {
    "gap_count": 5,
    "indirect_pc_target_count": 1,
    "promotion_bytes": 10,
    "unconditional_branch_count": 4,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _as_bytes(value: object, *, label: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    raise ValueError(f"{label} must be bytes")


def _parse_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _range_pair(value: object, *, label: str, limit: int, alignment: int) -> list[int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(_is_int(item) for item in value)
    ):
        raise ValueError(f"{label} must be a two-integer range")
    start, end = value
    if start < 0 or start >= end or end > limit:
        raise ValueError(f"{label} is outside the ROM")
    if start % alignment or end % alignment:
        raise ValueError(f"{label} has invalid alignment")
    return [start, end]


def _domain_ranges(
    value: object,
    *,
    label: str,
    limit: int,
    alignment: int,
) -> list[list[int]]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{label} must be a nonempty range list")
    result: list[list[int]] = []
    previous_end = -1
    for index, row in enumerate(value):
        pair = _range_pair(row, label=f"{label}[{index}]", limit=limit, alignment=alignment)
        if pair[0] < previous_end:
            raise ValueError(f"{label} ranges overlap or are out of order")
        result.append(pair)
        previous_end = pair[1]
    return result


def _check_cross_domain_ranges(
    code_ranges: Sequence[Sequence[int]], literal_ranges: Sequence[Sequence[int]]
) -> list[tuple[int, int, str]]:
    combined = [
        (start, end, "code") for start, end in code_ranges
    ] + [
        (start, end, "literal") for start, end in literal_ranges
    ]
    combined.sort(key=lambda row: (row[0], row[1], row[2]))
    previous: tuple[int, int, str] | None = None
    for current in combined:
        if previous is not None and current[0] < previous[1]:
            raise ValueError("code and literal ranges overlap")
        previous = current
    return combined


def _literal_binding_rows(
    rom: bytes,
    code_ranges: Sequence[Sequence[int]],
    literal_ranges: Sequence[Sequence[int]],
    value: object,
) -> list[list[object]]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("literal bindings must be a list")
    rows: list[list[object]] = []
    source_offsets: set[int] = set()
    target_offsets: list[int] = []

    def in_range(offset: int, size: int, ranges: Sequence[Sequence[int]]) -> bool:
        return any(start <= offset and offset + size <= end for start, end in ranges)

    for index, row in enumerate(value):
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError(f"literal binding {index} has invalid shape")
        source, target, raw_hex = row
        if not _is_int(source) or not _is_int(target) or not isinstance(raw_hex, str):
            raise ValueError(f"literal binding {index} has invalid fields")
        if source in source_offsets:
            raise ValueError("literal binding source is duplicated")
        if source < 0 or source + 2 > len(rom) or source % 2:
            raise ValueError(f"literal binding {index} source is outside the ROM")
        if not in_range(source, 2, code_ranges):
            raise ValueError(f"literal binding {index} source is outside code")
        if len(raw_hex) != 8:
            raise ValueError(f"literal binding {index} value is not four bytes")
        try:
            consumed = bytes.fromhex(raw_hex)
        except ValueError as error:
            raise ValueError(f"literal binding {index} value is not hexadecimal") from error
        if len(consumed) != 4:
            raise ValueError(f"literal binding {index} value is not four bytes")

        halfword = int.from_bytes(rom[source : source + 2], "little")
        if halfword & 0xF800 != 0x4800:
            raise ValueError(f"literal binding {index} source is not Thumb PC-relative LDR")
        aligned_pc = (source + 4) & ~3
        computed_target = aligned_pc + (halfword & 0xFF) * 4
        if target != computed_target:
            raise ValueError(f"literal binding {index} target does not match PC-relative LDR")
        if target < 0 or target + 4 > len(rom):
            raise ValueError(f"literal binding {index} target is outside the ROM")
        if not in_range(target, 4, literal_ranges):
            raise ValueError(f"literal binding {index} target is outside literals")
        actual = rom[target : target + 4]
        if actual != consumed:
            raise ValueError(f"literal binding {index} consumed value changed")

        source_offsets.add(source)
        target_offsets.append(target)
        rows.append([source, target, raw_hex.lower()])

    expected_words = {offset for start, end in literal_ranges for offset in range(start, end, 4)}
    if set(target_offsets) != expected_words:
        raise ValueError("literal word domain has incomplete verified binding coverage")
    return rows


def _decode_terminal(rom: bytes, left_end: int) -> dict[str, object]:
    if left_end < 2 or left_end > len(rom) or left_end % 2:
        raise ValueError("code range has no aligned final Thumb instruction")
    offset = left_end - 2
    halfword = int.from_bytes(rom[offset:left_end], "little")
    raw_hex = rom[offset:left_end].hex()
    if halfword & 0xF800 == 0xE000:
        immediate = halfword & 0x07FF
        if immediate & 0x0400:
            immediate -= 0x0800
        target = offset + 4 + (immediate << 1)
        if target < 0 or target + 2 > len(rom) or target % 2:
            raise ValueError("unconditional B target is outside the ROM")
        return {
            "kind": "unconditional_branch",
            "offset": offset,
            "raw_hex": raw_hex,
            "target": target,
        }
    if halfword & 0xFF87 == 0x4700:
        return {
            "kind": "indirect_pc_target",
            "offset": offset,
            "raw_hex": raw_hex,
            "register": (halfword >> 3) & 0x0F,
        }
    raise ValueError("code range does not end in an unconditional B or BX")


def _adjacent_boundaries(
    rom: bytes,
    code_ranges: Sequence[Sequence[int]],
    literal_ranges: Sequence[Sequence[int]],
    bindings: Sequence[Sequence[object]],
) -> list[dict[str, object]]:
    combined = _check_cross_domain_ranges(code_ranges, literal_ranges)
    boundaries: list[dict[str, object]] = []
    for index, (start, end, kind) in enumerate(combined[:-1]):
        next_start, next_end, next_kind = combined[index + 1]
        if kind != "code" or next_kind != "literal":
            continue
        if end == next_start:
            # A code/literal adjacency is a valid consumed-literal boundary,
            # but it has no positive bytes to promote.
            continue
        if end > next_start:
            raise ValueError("code-to-literal boundary overlaps")
        if ((end + 3) & ~3) != next_start:
            raise ValueError("code-to-literal boundary is not an align4 gap")
        gap = rom[end:next_start]
        if not gap or any(byte != 0 for byte in gap):
            raise ValueError("code-to-literal alignment gap is not zero")
        right_bindings = [
            list(row)
            for row in bindings
            if next_start <= int(row[1]) and int(row[1]) + 4 <= next_end
        ]
        if not right_bindings:
            raise ValueError("code-to-literal boundary has no consumed literal binding")
        right_bindings.sort(key=lambda row: (int(row[0]), int(row[1]), str(row[2])))
        boundaries.append(
            {
                "id": f"{ID_PREFIX}-{len(boundaries):02d}-{end:06x}",
                "kind": BOUNDARY_KIND,
                "range": [end, next_start],
                "bytes_sha256": _sha(gap),
                "left_code_range": [start, end],
                "right_literal_range": [next_start, next_end],
                "right_literal_bindings": right_bindings,
                "terminal": _decode_terminal(rom, end),
            }
        )
    excluded = [row["range"] for row in boundaries] + list(literal_ranges)
    for row in boundaries:
        terminal = row["terminal"]
        if terminal["kind"] == "unconditional_branch" and any(
            start <= terminal["target"] < end for start, end in excluded
        ):
            raise ValueError("terminal branch enters a gap or literal boundary")
    return boundaries


def derive_boundaries(
    rom: bytes | bytearray | memoryview,
    code_ranges: object,
    literal_ranges: object,
    literal_bindings: object,
) -> list[dict[str, object]]:
    """Derive all positive code-to-adjacent-literal align4 boundaries.

    This helper is intentionally independent of the frozen contract and
    baseline.  It validates the complete supplied domains so hidden relocated
    fixtures exercise the same derivation path as the production build.
    """

    rom_bytes = _as_bytes(rom, label="ROM")
    if not rom_bytes:
        raise ValueError("ROM must not be empty")
    code = _domain_ranges(code_ranges, label="code", limit=len(rom_bytes), alignment=2)
    literals = _domain_ranges(literal_ranges, label="literal", limit=len(rom_bytes), alignment=4)
    _check_cross_domain_ranges(code, literals)
    bindings = _literal_binding_rows(rom_bytes, code, literals, literal_bindings)
    return _adjacent_boundaries(rom_bytes, code, literals, bindings)


def _validate_baseline_segments(value: object, *, rom_size: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("baseline segments are missing")
    result: list[dict[str, Any]] = []
    cursor = 0
    for index, segment in enumerate(value):
        if not isinstance(segment, dict):
            raise ValueError(f"baseline segment {index} is not an object")
        pair = _range_pair(segment.get("range"), label=f"baseline segment {index}", limit=rom_size, alignment=1)
        if pair[0] != cursor:
            raise ValueError("baseline segments are not gapless")
        primary_class = segment.get("primary_class")
        primary_ids = segment.get("primary_claim_ids")
        secondary_ids = segment.get("secondary_claim_ids")
        if not isinstance(primary_class, str) or not isinstance(primary_ids, list) or not isinstance(secondary_ids, list):
            raise ValueError(f"baseline segment {index} owner schema changed")
        if primary_class == "unknown":
            if primary_ids or secondary_ids or not isinstance(segment.get("unknown_reason"), str):
                raise ValueError(f"baseline unknown segment {index} has owners")
        elif "unknown_reason" in segment:
            raise ValueError(f"baseline classified segment {index} has unknown reason")
        result.append(copy.deepcopy(segment))
        cursor = pair[1]
    if cursor != rom_size:
        raise ValueError("baseline segments do not cover the ROM")
    return result


def _segments_intersecting(
    segments: Sequence[dict[str, Any]], start: int, end: int
) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(segment)
        for segment in segments
        if segment["range"][0] < end and start < segment["range"][1]
    ]


def _gap_owners(
    segments: Sequence[dict[str, Any]], rom: bytes, start: int, end: int
) -> list[dict[str, Any]]:
    if rom[start:end] != b"\x00" * (end - start):
        raise ValueError("gap bytes are not zero")
    owners = _segments_intersecting(segments, start, end)
    if not owners:
        raise ValueError("gap has no baseline segment")
    for segment in owners:
        if (
            segment.get("primary_class") != "unknown"
            or segment.get("primary_claim_ids") != []
            or segment.get("secondary_claim_ids") != []
            or not isinstance(segment.get("unknown_reason"), str)
        ):
            raise ValueError("gap overlaps a known baseline owner")
    return owners


def project_baseline_owners(
    rom: bytes | bytearray | memoryview,
    code_ranges: object,
    literal_ranges: object,
    baseline_segments: object,
    gap_ranges: object,
) -> list[dict[str, object]]:
    """Project explicit gap ranges onto full baseline segment provenance.

    The returned segment objects are full copies.  A gap is accepted only when
    every intersecting baseline segment is an unknown segment with no owner.
    """

    rom_bytes = _as_bytes(rom, label="ROM")
    code = _domain_ranges(code_ranges, label="code", limit=len(rom_bytes), alignment=2)
    literals = _domain_ranges(literal_ranges, label="literal", limit=len(rom_bytes), alignment=4)
    _check_cross_domain_ranges(code, literals)
    if not isinstance(gap_ranges, (list, tuple)):
        raise ValueError("gap ranges must be a list")
    gaps = [_range_pair(row, label=f"gap[{index}]", limit=len(rom_bytes), alignment=1) for index, row in enumerate(gap_ranges)]
    segments = _validate_baseline_segments(baseline_segments, rom_size=len(rom_bytes))
    result: list[dict[str, object]] = []
    for start, end in gaps:
        result.append({"range": [start, end], "baseline_owners": {"gap": _gap_owners(segments, rom_bytes, start, end)}})
    return result


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema") != "rom-task-callback-five-gaps-public-contract-v1":
        raise ValueError("public contract schema changed")
    if contract.get("output_schema") != OUTPUT_SCHEMA:
        raise ValueError("output schema changed")
    if contract.get("rom") != {"path": ROM_PATH, "sha256": ROM_SHA256, "size": ROM_SIZE}:
        raise ValueError("ROM contract changed")
    if contract.get("expected_summary") != EXPECTED_SUMMARY:
        raise ValueError("expected summary changed")
    if not isinstance(contract.get("expected_boundaries"), list) or len(contract["expected_boundaries"]) != 5:
        raise ValueError("expected boundaries changed")
    if not isinstance(contract.get("source_inputs"), list):
        raise ValueError("source inputs are missing")
    source_payload = contract.get("source_payload")
    if not isinstance(source_payload, dict) or not isinstance(source_payload.get("sha256"), str) or not _is_int(source_payload.get("size")):
        raise ValueError("source payload identity is missing")
    baseline_archive = contract.get("baseline_archive")
    if not isinstance(baseline_archive, dict) or not isinstance(baseline_archive.get("sha256"), str) or not _is_int(baseline_archive.get("size")):
        raise ValueError("baseline archive identity is missing")
    if not isinstance(contract.get("baseline_raw_sha256"), str) or not _is_int(contract.get("baseline_raw_size")):
        raise ValueError("baseline raw identity is missing")
    denominators = contract.get("source_denominators")
    if not isinstance(denominators, dict):
        raise ValueError("source denominators are missing")
    for key in ("blocks", "code_ranges", "literal_ranges", "literal_bindings", "source_frontiers", "source_holes"):
        if not isinstance(denominators.get(key), list):
            raise ValueError(f"source denominator {key} is missing")
    if not isinstance(contract.get("scope"), dict):
        raise ValueError("scope is missing")


def _validate_source_payload(payload: dict[str, Any], contract: dict[str, Any]) -> tuple[list[list[int]], list[list[int]], list[list[object]]]:
    if payload.get("schema") != SOURCE_SCHEMA or payload.get("rom") != contract["rom"]:
        raise ValueError("source payload identity changed")
    closure = payload.get("closure")
    denominators = contract["source_denominators"]
    if not isinstance(closure, dict):
        raise ValueError("source closure is missing")
    for key in ("blocks", "code_ranges", "literal_ranges", "literal_bindings", "frontiers", "holes"):
        expected_key = {"frontiers": "source_frontiers", "holes": "source_holes"}.get(key, key)
        if closure.get(key) != denominators[expected_key]:
            raise ValueError(f"source closure {key} changed")
    for key in ("code_bytes", "literal_bytes", "instruction_count", "literal_reference_count", "structured_return_count"):
        if key in denominators and closure.get(key) != denominators[key]:
            raise ValueError(f"source closure {key} changed")
    code_ranges = _domain_ranges(closure["code_ranges"], label="code", limit=ROM_SIZE, alignment=2)
    literal_ranges = _domain_ranges(closure["literal_ranges"], label="literal", limit=ROM_SIZE, alignment=4)
    bindings = closure["literal_bindings"]
    if not isinstance(bindings, list):
        raise ValueError("source literal bindings are missing")
    return code_ranges, literal_ranges, [list(row) for row in bindings]


def _validate_baseline_payload(baseline: dict[str, Any], contract: dict[str, Any], rom_size: int) -> list[dict[str, Any]]:
    if baseline.get("schema") != BASELINE_SCHEMA or baseline.get("base_rom") != contract["rom"]:
        raise ValueError("baseline identity changed")
    if baseline.get("domain") != [0, rom_size]:
        raise ValueError("baseline domain changed")
    return _validate_baseline_segments(baseline.get("segments"), rom_size=rom_size)


def _attach_baseline_owners(
    rows: Sequence[dict[str, object]], segments: Sequence[dict[str, Any]], rom: bytes
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for row in rows:
        left_start, left_end = row["left_code_range"]  # type: ignore[misc]
        gap_start, gap_end = row["range"]  # type: ignore[misc]
        right_start, right_end = row["right_literal_range"]  # type: ignore[misc]
        owners = {
            "left": _segments_intersecting(segments, left_start, left_end),
            "gap": _gap_owners(segments, rom, gap_start, gap_end),
            "right": _segments_intersecting(segments, right_start, right_end),
        }
        if not owners["left"] or not owners["right"]:
            raise ValueError("boundary has incomplete baseline provenance")
        copied = copy.deepcopy(row)
        copied["baseline_owners"] = owners
        enriched.append(copied)
    return enriched


def build_payload(
    rom_bytes: bytes | bytearray | memoryview,
    source_payload_raw: bytes | bytearray | memoryview,
    baseline_raw: bytes | bytearray | memoryview,
    contract_raw: bytes | bytearray | memoryview,
) -> dict[str, Any]:
    """Build the contract-bound payload using only supplied raw bytes."""

    rom = _as_bytes(rom_bytes, label="ROM")
    source_raw = _as_bytes(source_payload_raw, label="source payload")
    baseline_bytes = _as_bytes(baseline_raw, label="baseline")
    contract_bytes = _as_bytes(contract_raw, label="contract")

    if _sha(contract_bytes) != CONTRACT_SHA256:
        raise ValueError("public contract identity changed")
    contract = _parse_json(contract_bytes, label="public contract")
    _validate_contract(contract)

    rom_identity = contract["rom"]
    if len(rom) != rom_identity["size"] or _sha(rom) != rom_identity["sha256"]:
        raise ValueError("ROM identity changed")
    source_identity = contract["source_payload"]
    if len(source_raw) != source_identity["size"] or _sha(source_raw) != source_identity["sha256"]:
        raise ValueError("source payload identity changed")
    if len(baseline_bytes) != contract["baseline_raw_size"] or _sha(baseline_bytes) != contract["baseline_raw_sha256"]:
        raise ValueError("baseline raw identity changed")

    source_payload = _parse_json(source_raw, label="source payload")
    baseline = _parse_json(baseline_bytes, label="baseline")
    code_ranges, literal_ranges, literal_bindings = _validate_source_payload(source_payload, contract)
    derived = derive_boundaries(rom, code_ranges, literal_ranges, literal_bindings)

    expected = contract["expected_boundaries"]
    if derived != expected:
        raise ValueError("derived boundaries do not match the public contract")
    segments = _validate_baseline_payload(baseline, contract, len(rom))
    boundaries = _attach_baseline_owners(derived, segments, rom)

    summary = {
        "gap_count": len(boundaries),
        "indirect_pc_target_count": sum(row["terminal"]["kind"] == "indirect_pc_target" for row in boundaries),  # type: ignore[index]
        "promotion_bytes": sum(row["range"][1] - row["range"][0] for row in boundaries),  # type: ignore[index]
        "unconditional_branch_count": sum(row["terminal"]["kind"] == "unconditional_branch" for row in boundaries),  # type: ignore[index]
    }
    if summary != contract["expected_summary"]:
        raise ValueError("derived summary does not match the public contract")

    claims = [
        {key: copy.deepcopy(row[key]) for key in ("id", "kind", "range", "bytes_sha256")}
        for row in boundaries
    ]
    promotion = {
        "claim_count": len(claims),
        "claims": claims,
        "promotion_bytes": summary["promotion_bytes"],
    }
    return {
        "schema": contract["output_schema"],
        "rom": copy.deepcopy(contract["rom"]),
        "source_inputs": copy.deepcopy(contract["source_inputs"]),
        "baseline": {
            "archive_observed_during_this_build": False,
            "archive_reference": copy.deepcopy(contract["baseline_archive"]),
            "raw_sha256": contract["baseline_raw_sha256"],
            "raw_size": contract["baseline_raw_size"],
        },
        "summary": summary,
        "boundaries": boundaries,
        "promotion": promotion,
        "scope": copy.deepcopy(contract["scope"]),
    }
