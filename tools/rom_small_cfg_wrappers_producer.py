#!/usr/bin/env python3
"""Pure producer for the three direct Thumb wrapper closures.

All input is supplied as bytes or values.  This module deliberately performs
no repository I/O, imports no upstream scanner/verifier, and publishes no
artifact; the parent task owns those responsibilities.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Sequence


CONTRACT_SHA256 = "065dae442f4f1276b6b41b42f5d5e56d550a043dea5a5a73090ab9fa886174ac"
CONTRACT_SCHEMA = "rom-three-direct-wrapper-public-contract-v1"
OUTPUT_SCHEMA = "rom-three-direct-wrapper-cfg-v1"
BASELINE_SCHEMA = "rom-byte-coverage-v1"
ROM_PATH = "rom/base.gba"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456
ROM_BASE = 0x08000000

PRODUCER_RAW_KEYS = ("kind", "source", "target", "raw_hex", "size")
PRODUCER_CLAIM_KEYS = (
    "claim_kind",
    "evidence_path",
    "evidence_selector",
    "evidence_sha256",
    "id",
    "independent_verifier_path",
    "independent_verifier_sha256",
    "mode",
    "primary_class",
    "promotion_manifest_path",
    "promotion_manifest_sha256",
    "range",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bytes(value: object, *, label: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    raise ValueError(f"{label} must be bytes")


def _json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _pair(
    value: object,
    *,
    label: str,
    limit: int,
    alignment: int,
    minimum_size: int = 1,
) -> list[int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or not all(_is_int(item) for item in value)
    ):
        raise ValueError(f"{label} must be a two-integer range")
    start, end = value
    if start < 0 or end <= start or end > limit or end - start < minimum_size:
        raise ValueError(f"{label} is outside the ROM")
    if start % alignment or end % alignment:
        raise ValueError(f"{label} has invalid alignment")
    return [start, end]


def _ranges(
    value: object,
    *,
    label: str,
    limit: int,
    alignment: int,
    allow_empty: bool = False,
    minimum_size: int = 1,
) -> list[list[int]]:
    if not isinstance(value, (list, tuple)) or (not value and not allow_empty):
        raise ValueError(f"{label} must be a nonempty range list")
    result: list[list[int]] = []
    previous_end = -1
    for index, row in enumerate(value):
        pair = _pair(
            row,
            label=f"{label}[{index}]",
            limit=limit,
            alignment=alignment,
            minimum_size=minimum_size,
        )
        if pair[0] < previous_end:
            raise ValueError(f"{label} ranges overlap or are out of order")
        result.append(pair)
        previous_end = pair[1]
    return result


def _disjoint_domains(
    named_ranges: Sequence[tuple[str, Sequence[Sequence[int]]]]
) -> list[tuple[int, int, str]]:
    combined = [
        (start, end, name)
        for name, ranges in named_ranges
        for start, end in ranges
    ]
    combined.sort(key=lambda row: (row[0], row[1], row[2]))
    previous: tuple[int, int, str] | None = None
    for current in combined:
        if previous is not None and current[0] < previous[1]:
            raise ValueError("code, literal, and hole ranges overlap")
        previous = current
    return combined


def _contains(ranges: Sequence[Sequence[int]], offset: int, size: int = 1) -> bool:
    return any(start <= offset and offset + size <= end for start, end in ranges)


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _decode_b_target(offset: int, halfword: int) -> int | None:
    if halfword & 0xF800 != 0xE000:
        return None
    return offset + 4 + _sign_extend((halfword & 0x07FF) << 1, 12)


def _decode_bcond_target(offset: int, halfword: int) -> int | None:
    if halfword & 0xF000 != 0xD000 or ((halfword >> 8) & 0x0F) >= 0x0E:
        return None
    return offset + 4 + _sign_extend((halfword & 0x00FF) << 1, 9)


def _decode_bl_target(offset: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def scan_producers(
    rom: bytes | bytearray | memoryview,
    targets: object,
) -> list[dict[str, object]]:
    """Scan every aligned Thumb halfword for target-limited direct branches."""

    rom_bytes = _bytes(rom, label="ROM")
    if not isinstance(targets, (list, tuple)):
        raise ValueError("producer targets must be a list")
    target_order: list[int] = []
    seen: set[int] = set()
    for target in targets:
        if not _is_int(target) or target < 0 or target >= len(rom_bytes) or target % 2:
            raise ValueError("producer target is invalid")
        if target in seen:
            raise ValueError("producer target is duplicated")
        seen.add(target)
        target_order.append(target)

    matches: dict[int, list[dict[str, object]]] = {target: [] for target in target_order}
    # The range includes len(rom)-2, which is the final two-byte halfword.
    for offset in range(0, max(0, len(rom_bytes) - 1), 2):
        first = int.from_bytes(rom_bytes[offset : offset + 2], "little")
        kind: str | None = None
        size = 2
        target: int | None = None
        if first & 0xF800 == 0xF000:
            if offset + 4 <= len(rom_bytes):
                second = int.from_bytes(rom_bytes[offset + 2 : offset + 4], "little")
                target = _decode_bl_target(offset, first, second)
                if target is not None:
                    kind = "thumb_bl"
                    size = 4
        if kind is None:
            target = _decode_bcond_target(offset, first)
            if target is not None:
                kind = "thumb_bcond"
        if kind is None:
            target = _decode_b_target(offset, first)
            if target is not None:
                kind = "thumb_b"
        if kind is not None and target in matches:
            matches[target].append(
                {
                    "kind": kind,
                    "source": offset,
                    "target": target,
                    "raw_hex": rom_bytes[offset : offset + size].hex(),
                    "size": size,
                }
            )
    return [row for target in target_order for row in sorted(matches[target], key=lambda row: int(row["source"]))]


def _decode_instruction(
    rom: bytes,
    offset: int,
    code_end: int,
) -> tuple[int, str, int | None, int | None]:
    if offset < 0 or offset % 2 or offset + 2 > code_end or offset + 2 > len(rom):
        raise ValueError("instruction is outside a complete code range")
    first = int.from_bytes(rom[offset : offset + 2], "little")

    if first & 0xF800 == 0xF000:
        if offset + 4 > code_end or offset + 4 > len(rom):
            raise ValueError("Thumb BL is truncated")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        target = _decode_bl_target(offset, first, second)
        if target is None:
            raise ValueError("unsupported Thumb high halfword")
        return 4, "call", target, None

    if first & 0xF000 == 0xD000:
        if ((first >> 8) & 0x0F) >= 0x0E:
            raise ValueError("undefined condition or SWI is outside the supported closure")
        target = _decode_bcond_target(offset, first)
        assert target is not None
        return 2, "conditional_branch", target, None

    target = _decode_b_target(offset, first)
    if target is not None:
        return 2, "unconditional_branch", target, None

    if first & 0xFF87 == 0x4700:
        return 2, "indirect_branch", None, (first >> 3) & 0x0F
    if first & 0xFF87 == 0x4780:
        raise ValueError("register BLX is an unresolved PC write")
    if first & 0xFF00 == 0xDF00:
        raise ValueError("SWI is outside the supported closure")
    if first & 0xFF00 == 0xBE00:
        raise ValueError("BKPT is outside the supported Thumb-1 closure")

    # High-register ADD/MOV can write PC.  CMP is a non-writing high-register
    # operation and remains a regular linear node.
    if first & 0xFC00 == 0x4400:
        operation = (first >> 8) & 0x03
        destination = (first & 0x07) | (((first >> 7) & 0x01) << 3)
        if operation in (0, 2) and destination == 15:
            raise ValueError("high-register PC write is outside the closure")
        if operation == 3:
            raise ValueError("unsupported high-register PC transfer")
        return 2, "linear", None, None

    # POP {pc} is an implicit PC write.  POP without PC is a normal linear
    # instruction; no return meaning is inferred from POP or BX.
    if first & 0xFE00 == 0xBC00:
        if first & 0x0100 or not first & 0x00FF:
            raise ValueError("POP {pc} is an unresolved PC write")
        return 2, "linear", None, None

    # Only the positively decoded Thumb-1 families needed by this packet are
    # linear. Unknown encodings must not inherit an implicit fallthrough.
    if (first < 0x2000 or first & 0xF800 in (0x3000, 0x4800, 0x6800)
            or first & 0xFE00 == 0xB400 and first & 0x01FF):
        return 2, "linear", None, None
    raise ValueError("unsupported instruction in frozen Thumb-1 closure")


def _literal_binding(
    rom: bytes,
    offset: int,
    literal_ranges: Sequence[Sequence[int]],
) -> list[object] | None:
    halfword = int.from_bytes(rom[offset : offset + 2], "little")
    if halfword & 0xF800 != 0x4800:
        return None
    target = ((offset + 4) & ~3) + (halfword & 0x00FF) * 4
    if not _contains(literal_ranges, target, 4):
        raise ValueError("literal LDR target is outside the declared literal domain")
    return [offset, target, rom[target : target + 4].hex()]


def _validate_closure_inputs(
    rom: bytes,
    roots: object,
    code_ranges: object,
    literal_ranges: object,
    opaque_entries: object,
    holes: object,
) -> tuple[list[int], list[list[int]], list[list[int]], list[int], list[list[int]]]:
    code = _ranges(code_ranges, label="code", limit=len(rom), alignment=2)
    literals = _ranges(
        literal_ranges,
        label="literal",
        limit=len(rom),
        alignment=4,
        allow_empty=True,
        minimum_size=4,
    )
    for start, end in literals:
        if (end - start) % 4:
            raise ValueError("literal range is not a whole-word domain")
    hole_ranges = _ranges(holes, label="hole", limit=len(rom), alignment=2, allow_empty=True)
    _disjoint_domains((("code", code), ("literal", literals), ("hole", hole_ranges)))

    if not isinstance(roots, (list, tuple)) or not roots:
        raise ValueError("roots must be a nonempty list")
    root_values: list[int] = []
    root_seen: set[int] = set()
    for root in roots:
        if not _is_int(root) or root < 0 or root + 2 > len(rom) or root % 2:
            raise ValueError("root is invalid")
        if root in root_seen:
            raise ValueError("root is duplicated")
        if not _contains(code, root, 2):
            raise ValueError("root is outside the code domain")
        root_seen.add(root)
        root_values.append(root)

    if not isinstance(opaque_entries, (list, tuple)):
        raise ValueError("opaque entries must be a list")
    opaque_values: list[int] = []
    opaque_seen: set[int] = set()
    for entry in opaque_entries:
        if not _is_int(entry) or entry < 0 or entry + 2 > len(rom) or entry % 2:
            raise ValueError("opaque entry is invalid")
        if entry in opaque_seen:
            raise ValueError("opaque entry is duplicated")
        if _contains(code, entry) or _contains(literals, entry) or _contains(hole_ranges, entry):
            raise ValueError("opaque entry overlaps a supplied domain")
        opaque_seen.add(entry)
        opaque_values.append(entry)
    return root_values, code, literals, opaque_values, hole_ranges


def _ensure_code_target(
    target: int | None,
    *,
    rom_size: int,
    code_ranges: Sequence[Sequence[int]],
    nodes: dict[int, dict[str, object]],
    pending: list[int],
    queued: set[int],
) -> None:
    if target is None or not _is_int(target) or target < 0 or target + 2 > rom_size or target % 2:
        raise ValueError("branch target is outside the ROM")
    if not _contains(code_ranges, target, 2):
        raise ValueError("branch target is outside the supplied code domain")
    for node in nodes.values():
        start = int(node["offset"])
        end = start + int(node["size"])
        if start < target < end:
            raise ValueError("branch enters the middle of an instruction")
    if target not in nodes and target not in queued:
        pending.append(target)
        queued.add(target)


def _validate_node_coverage(
    code_ranges: Sequence[Sequence[int]],
    nodes: Sequence[dict[str, object]],
) -> None:
    by_offset = {int(node["offset"]): node for node in nodes}
    for start, end in code_ranges:
        cursor = start
        while cursor < end:
            node = by_offset.get(cursor)
            if node is None:
                raise ValueError("a supplied code byte is unreachable")
            node_end = cursor + int(node["size"])
            if node_end > end:
                raise ValueError("instruction crosses a code range boundary")
            cursor = node_end
        if cursor != end:
            raise ValueError("code coverage does not close")


def _derive_blocks(
    code_ranges: Sequence[Sequence[int]],
    roots: Sequence[int],
    nodes: Sequence[dict[str, object]],
) -> list[list[int]]:
    by_offset = {int(node["offset"]): node for node in nodes}
    block_starts = set(roots)
    for node in nodes:
        flow = node["flow"]
        for edge in node["edges"]:  # type: ignore[union-attr]
            if edge["kind"] == "branch_target":
                block_starts.add(int(edge["target"]))
            elif edge["kind"] == "call_target" and edge["scope"] == "internal":
                block_starts.add(int(edge["target"]))
            elif edge["kind"] == "fallthrough" and flow in {"call", "conditional_branch"}:
                block_starts.add(int(edge["target"]))

    blocks: list[list[int]] = []
    for range_start, range_end in code_ranges:
        offsets = sorted(offset for offset in by_offset if range_start <= offset < range_end)
        starts = sorted({range_start, *(offset for offset in offsets if offset in block_starts)})
        if not offsets or offsets[0] != range_start:
            raise ValueError("code range does not start with a decoded node")
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else range_end
            cursor = start
            while cursor < end:
                node = by_offset.get(cursor)
                if node is None:
                    raise ValueError("basic block contains an undecoded byte")
                node_end = cursor + int(node["size"])
                if node_end > end:
                    raise ValueError("basic block splits an instruction")
                if node["flow"] in {"conditional_branch", "unconditional_branch", "indirect_branch"} and node_end != end:
                    raise ValueError("basic block crosses a terminal instruction")
                if node["flow"] == "call" and node_end != end:
                    raise ValueError("basic block does not split after a call")
                cursor = node_end
            if cursor != end:
                raise ValueError("basic block does not close")
            blocks.append([start, end])
    return blocks


def derive_closure(
    rom: bytes | bytearray | memoryview,
    roots: object,
    code_ranges: object,
    literal_ranges: object,
    opaque_entries: object,
    holes: object,
) -> dict[str, object]:
    """Derive a finite Thumb closure from supplied domains and roots."""

    rom_bytes = _bytes(rom, label="ROM")
    if not rom_bytes:
        raise ValueError("ROM must not be empty")
    root_values, code, literals, opaque, hole_ranges = _validate_closure_inputs(
        rom_bytes, roots, code_ranges, literal_ranges, opaque_entries, holes
    )

    pending = list(root_values)
    queued = set(pending)
    nodes: dict[int, dict[str, object]] = {}
    frontiers: list[dict[str, object]] = []
    literal_bindings: list[list[object]] = []

    while pending:
        offset = pending.pop(0)
        queued.discard(offset)
        if offset in nodes:
            continue
        if not _contains(code, offset, 2):
            raise ValueError("worklist target is outside code")
        for node in nodes.values():
            start = int(node["offset"])
            end = start + int(node["size"])
            if start < offset < end:
                raise ValueError("worklist target enters an instruction middle")

        code_end = next(end for start, end in code if start <= offset < end)
        size, flow, target, register = _decode_instruction(rom_bytes, offset, code_end)
        end = offset + size
        if end > code_end:
            raise ValueError("instruction crosses code range boundary")
        for node in nodes.values():
            other_start = int(node["offset"])
            other_end = other_start + int(node["size"])
            if offset < other_end and other_start < end:
                raise ValueError("instruction ranges overlap")

        edges: list[dict[str, object]] = []
        if flow == "call":
            assert target is not None
            if target in opaque:
                edges.append({"kind": "call_target", "scope": "opaque", "target": target})
            else:
                _ensure_code_target(
                    target,
                    rom_size=len(rom_bytes),
                    code_ranges=code,
                    nodes=nodes,
                    pending=pending,
                    queued=queued,
                )
                edges.append({"kind": "call_target", "scope": "internal", "target": target})
            fallthrough = end
            _ensure_code_target(
                fallthrough,
                rom_size=len(rom_bytes),
                code_ranges=code,
                nodes=nodes,
                pending=pending,
                queued=queued,
            )
            edges.append({"kind": "fallthrough", "scope": "internal", "target": fallthrough})
        elif flow == "conditional_branch":
            _ensure_code_target(
                target,
                rom_size=len(rom_bytes),
                code_ranges=code,
                nodes=nodes,
                pending=pending,
                queued=queued,
            )
            edges.append({"kind": "branch_target", "scope": "internal", "target": target})
            fallthrough = end
            _ensure_code_target(
                fallthrough,
                rom_size=len(rom_bytes),
                code_ranges=code,
                nodes=nodes,
                pending=pending,
                queued=queued,
            )
            edges.append({"kind": "fallthrough", "scope": "internal", "target": fallthrough})
        elif flow == "unconditional_branch":
            _ensure_code_target(
                target,
                rom_size=len(rom_bytes),
                code_ranges=code,
                nodes=nodes,
                pending=pending,
                queued=queued,
            )
            edges.append({"kind": "branch_target", "scope": "internal", "target": target})
        elif flow == "indirect_branch":
            assert register is not None
            frontiers.append({"reason": "indirect_pc_target", "register": register, "source": offset})
        else:
            fallthrough = end
            _ensure_code_target(
                fallthrough,
                rom_size=len(rom_bytes),
                code_ranges=code,
                nodes=nodes,
                pending=pending,
                queued=queued,
            )
            edges.append({"kind": "fallthrough", "scope": "internal", "target": fallthrough})

        binding = _literal_binding(rom_bytes, offset, literals)
        if binding is not None:
            literal_bindings.append(binding)
        nodes[offset] = {
            "edges": edges,
            "flow": flow,
            "offset": offset,
            "raw_hex": rom_bytes[offset:end].hex(),
            "size": size,
        }

    ordered_nodes = [nodes[offset] for offset in sorted(nodes)]
    _validate_node_coverage(code, ordered_nodes)

    # Every declared literal word must have at least one actual PC-relative
    # LDR consumer.  Duplicate consumers are valid and remain in source order.
    literal_targets = {int(row[1]) for row in literal_bindings}
    for start, end in literals:
        for target in range(start, end, 4):
            if target not in literal_targets:
                raise ValueError("declared literal word has no LDR consumer")
    literal_bindings.sort(key=lambda row: (int(row[0]), int(row[1])))
    frontiers.sort(key=lambda row: int(row["source"]))
    blocks = _derive_blocks(code, root_values, ordered_nodes)
    producer_count = len(scan_producers(rom_bytes, root_values))
    promotion_ranges = [*code, *literals]
    summary = {
        "basic_block_count": len(blocks),
        "claim_count": len(promotion_ranges),
        "code_bytes": sum(end - start for start, end in code),
        "frontier_count": len(frontiers),
        "instruction_count": len(ordered_nodes),
        "literal_bytes": sum(end - start for start, end in literals),
        "opaque_call_count": sum(
            edge["kind"] == "call_target" and edge["scope"] == "opaque"
            for node in ordered_nodes
            for edge in node["edges"]  # type: ignore[union-attr]
        ),
        "producer_count": producer_count,
        "promotion_bytes": sum(end - start for start, end in promotion_ranges),
        "root_count": len(root_values),
        "structured_return_count": 0,
    }
    return {
        "nodes": ordered_nodes,
        "blocks": blocks,
        "code_ranges": copy.deepcopy(code),
        "literal_ranges": copy.deepcopy(literals),
        "literal_bindings": literal_bindings,
        "frontiers": frontiers,
        "holes": copy.deepcopy(hole_ranges),
        "summary": summary,
    }


def _validate_baseline_segments(value: object, *, rom_size: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("baseline segments are missing")
    result: list[dict[str, Any]] = []
    cursor = 0
    for index, segment in enumerate(value):
        if not isinstance(segment, dict):
            raise ValueError(f"baseline segment {index} is not an object")
        pair = _pair(segment.get("range"), label=f"baseline segment {index}", limit=rom_size, alignment=1)
        if pair[0] != cursor:
            raise ValueError("baseline segments are not gapless")
        primary_class = segment.get("primary_class")
        primary_ids = segment.get("primary_claim_ids")
        secondary_ids = segment.get("secondary_claim_ids")
        if not isinstance(primary_class, str) or not isinstance(primary_ids, list) or not isinstance(secondary_ids, list):
            raise ValueError("baseline segment owner schema changed")
        if primary_class == "unknown":
            if primary_ids or secondary_ids or not isinstance(segment.get("unknown_reason"), str):
                raise ValueError("unknown baseline segment carries owners")
        elif "unknown_reason" in segment:
            raise ValueError("classified baseline segment carries unknown reason")
        result.append(copy.deepcopy(segment))
        cursor = pair[1]
    if cursor != rom_size:
        raise ValueError("baseline does not cover the ROM")
    return result


def _owners_for_range(
    segments: Sequence[dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    start: int,
    end: int,
    *,
    require_unknown: bool,
) -> list[dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    for segment in segments:
        segment_start, segment_end = segment["range"]
        if segment_start >= end or segment_end <= start:
            continue
        if require_unknown and (
            segment.get("primary_class") != "unknown"
            or segment.get("primary_claim_ids") != []
            or segment.get("secondary_claim_ids") != []
            or not isinstance(segment.get("unknown_reason"), str)
        ):
            raise ValueError("promotion range overlaps a known baseline owner")
        owners.append(copy.deepcopy(segment))
    if not owners:
        raise ValueError("range has no baseline owner segment")
    return owners


def _producer_owners(
    segments: Sequence[dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    for segment in segments:
        segment_start, segment_end = segment["range"]
        if segment_start >= end or segment_end <= start:
            continue
        claim_rows: list[dict[str, Any]] = []
        for claim_id in segment["primary_claim_ids"]:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                raise ValueError(f"baseline claim is missing: {claim_id}")
            if any(key not in claim for key in PRODUCER_CLAIM_KEYS):
                raise ValueError("baseline producer claim schema changed")
            claim_rows.append({key: copy.deepcopy(claim[key]) for key in PRODUCER_CLAIM_KEYS})
        owners.append(
            {
                "claims": claim_rows,
                "intersection": [max(start, segment_start), min(end, segment_end)],
                "segment": copy.deepcopy(segment),
            }
        )
    if not owners:
        raise ValueError("producer has no baseline owner")
    return owners


def _scan_pointer_occurrences(rom: bytes, roots: Sequence[int]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for root in roots:
        pointer = ROM_BASE + root + 1
        needle = pointer.to_bytes(4, "little")
        hits: list[int] = []
        cursor = 0
        while True:
            found = rom.find(needle, cursor)
            if found < 0:
                break
            hits.append(found)
            cursor = found + 1
        result[f"0x{pointer:x}"] = hits
    return result


def _validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError("public contract schema changed")
    if contract.get("output_schema") != OUTPUT_SCHEMA:
        raise ValueError("output schema changed")
    if contract.get("rom") != {"path": ROM_PATH, "sha256": ROM_SHA256, "size": ROM_SIZE}:
        raise ValueError("ROM contract changed")
    for key in (
        "baseline_archive",
        "baseline_raw_sha256",
        "baseline_raw_size",
        "code_ranges",
        "expected_blocks",
        "expected_frontiers",
        "expected_literal_bindings",
        "expected_nodes",
        "expected_producers",
        "expected_summary",
        "holes",
        "literal_ranges",
        "opaque_entries",
        "root_pointer_occurrences",
        "roots",
        "scope",
        "upstream_inputs",
    ):
        if key not in contract:
            raise ValueError(f"contract field is missing: {key}")
    if not _is_int(contract["baseline_raw_size"]) or not isinstance(contract["baseline_raw_sha256"], str):
        raise ValueError("baseline raw identity changed")
    if not isinstance(contract["expected_producers"], list) or not isinstance(contract["expected_nodes"], list):
        raise ValueError("contract expected vectors are malformed")


def _promotion_rows(
    rom: bytes,
    segments: Sequence[dict[str, Any]],
    claims_by_id: dict[str, dict[str, Any]],
    code_ranges: Sequence[Sequence[int]],
    literal_ranges: Sequence[Sequence[int]],
) -> list[dict[str, object]]:
    ranges = [
        (start, end, "reachable_thumb_code") for start, end in code_ranges
    ] + [
        (start, end, "consumed_literal_words") for start, end in literal_ranges
    ]
    ranges.sort(key=lambda row: (row[0], row[1], row[2]))
    rows: list[dict[str, object]] = []
    for index, (start, end, kind) in enumerate(ranges):
        owners = _owners_for_range(segments, claims_by_id, start, end, require_unknown=True)
        rows.append(
            {
                "id": f"three-direct-wrapper-{kind}-{index:02d}-{start:06x}",
                "kind": kind,
                "range": [start, end],
                "bytes_sha256": _sha(rom[start:end]),
                "baseline_owners": owners,
            }
        )
    return rows


def build_payload(
    rom: bytes | bytearray | memoryview,
    baseline_raw: bytes | bytearray | memoryview,
    contract_raw: bytes | bytearray | memoryview,
) -> dict[str, object]:
    """Build the frozen output from supplied raw bytes only."""

    rom_bytes = _bytes(rom, label="ROM")
    baseline_bytes = _bytes(baseline_raw, label="baseline")
    contract_bytes = _bytes(contract_raw, label="contract")
    if _sha(contract_bytes) != CONTRACT_SHA256:
        raise ValueError("public contract identity changed")
    contract = _json(contract_bytes, label="public contract")
    _validate_contract(contract)

    rom_identity = contract["rom"]
    if len(rom_bytes) != rom_identity["size"] or _sha(rom_bytes) != rom_identity["sha256"]:
        raise ValueError("ROM identity changed")
    if len(baseline_bytes) != contract["baseline_raw_size"] or _sha(baseline_bytes) != contract["baseline_raw_sha256"]:
        raise ValueError("baseline raw identity changed")

    baseline = _json(baseline_bytes, label="baseline")
    if baseline.get("schema") != BASELINE_SCHEMA or baseline.get("base_rom") != contract["rom"] or baseline.get("domain") != [0, len(rom_bytes)]:
        raise ValueError("baseline identity changed")
    segments = _validate_baseline_segments(baseline.get("segments"), rom_size=len(rom_bytes))
    claims = baseline.get("claims")
    if not isinstance(claims, list):
        raise ValueError("baseline claims are missing")
    claims_by_id: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("id"), str) or claim["id"] in claims_by_id:
            raise ValueError("baseline claims are malformed")
        claims_by_id[claim["id"]] = claim

    roots = contract["roots"]
    closure = derive_closure(
        rom_bytes,
        roots,
        contract["code_ranges"],
        contract["literal_ranges"],
        contract["opaque_entries"],
        contract["holes"],
    )
    if (
        closure["nodes"] != contract["expected_nodes"]
        or closure["blocks"] != contract["expected_blocks"]
        or closure["frontiers"] != contract["expected_frontiers"]
        or closure["literal_bindings"] != contract["expected_literal_bindings"]
        or closure["summary"] != contract["expected_summary"]
    ):
        raise ValueError("derived closure does not match the public contract")

    producer_raw = scan_producers(rom_bytes, roots)
    expected_producers = contract["expected_producers"]
    expected_raw = [{key: row[key] for key in PRODUCER_RAW_KEYS} for row in expected_producers]
    if producer_raw != expected_raw:
        raise ValueError("raw producer scan does not match the public contract")
    producers: list[dict[str, object]] = []
    for raw_row, expected_row in zip(producer_raw, expected_producers):
        owners = _producer_owners(
            segments,
            claims_by_id,
            int(raw_row["source"]),
            int(raw_row["source"]) + int(raw_row["size"]),
        )
        if owners != expected_row.get("owners"):
            raise ValueError("producer baseline provenance changed")
        producers.append({**copy.deepcopy(raw_row), "owners": owners})

    pointer_occurrences = _scan_pointer_occurrences(rom_bytes, roots)
    if pointer_occurrences != contract["root_pointer_occurrences"]:
        raise ValueError("root pointer occurrence denominator changed")

    promotion_claims = _promotion_rows(
        rom_bytes,
        segments,
        claims_by_id,
        contract["code_ranges"],
        contract["literal_ranges"],
    )
    promotion = {
        "claim_count": len(promotion_claims),
        "promotion_bytes": sum(row["range"][1] - row["range"][0] for row in promotion_claims),  # type: ignore[index]
        "claims": promotion_claims,
    }
    if promotion["claim_count"] != contract["expected_summary"]["claim_count"] or promotion["promotion_bytes"] != contract["expected_summary"]["promotion_bytes"]:
        raise ValueError("promotion summary changed")

    return {
        "schema": contract["output_schema"],
        "rom": copy.deepcopy(contract["rom"]),
        "upstream_inputs": copy.deepcopy(contract["upstream_inputs"]),
        "baseline": {
            "raw_sha256": contract["baseline_raw_sha256"],
            "raw_size": contract["baseline_raw_size"],
            "archive_reference": copy.deepcopy(contract["baseline_archive"]),
            "archive_observed_during_this_build": False,
        },
        "roots": copy.deepcopy(roots),
        "producers": producers,
        "root_pointer_occurrences": pointer_occurrences,
        "closure": closure,
        "promotion": promotion,
        "scope": copy.deepcopy(contract["scope"]),
    }
