#!/usr/bin/env python3
"""Export the exact fixed-ROM byte union reachable by the chapter interpreter."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-chapter-script-inventory-v1"
VERIFY_SCHEMA = "rom-chapter-script-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456

TABLE_SPECS = (
    (
        "primary",
        0x060C74,
        56,
        "f6c872afd0b653ae2e0e04407bdbc059719eb823801d165e22a1d7e5c98aa099",
    ),
    (
        "alternate",
        0x060D54,
        56,
        "767308a8e78947f7795c61965155d27925265327466c9df9d5d547b2f0368b5c",
    ),
    (
        "runtime_state",
        0x060E34,
        47,
        "d0abb00332b73cd36637dbfcf5a7811622438f9c6382dc8c8ff45b00455d00ae",
    ),
    (
        "positions_formation",
        0x060EF0,
        45,
        "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed",
    ),
)
TOTAL_TABLE_SLOTS = sum(entry_count for _, _, entry_count, _ in TABLE_SPECS)

AUXILIARY_CONSUMER_SPECS = (
    (
        "runtime_state",
        0x08A534,
        0x08A588,
        "2eebdb3fecb96d74024180c6c3ff764d9ed0af2a25860a985f714cc9da8d57ad",
        0x08A578,
        0x060E34,
        0x08A55C,
        0x08A564,
        "200db68d2ac056a78c92cfc0632cb954c1b93e3fbb2d4dce158df31ca9ad2ef0",
        0x08A566,
        46,
        "47-entry structural domain 0..46; runtime maximum is not statically bounded",
    ),
    (
        "positions_formation",
        0x08A588,
        0x08A630,
        "316b38ca78b84f67eb88df86531dbdc5e179b031067692acbdcd6372d0d195e0",
        0x08A5E4,
        0x060EF0,
        0x08A5CE,
        0x08A5D6,
        "d352f62a2053c30c684ca055c5c5d77a34d05f6192f0c5b7b1f6b84a09d118b1",
        0x08A5FC,
        44,
        "positions headers enumerate indices {0,6,8,10,11,12,14}",
    ),
)

TABLE_SELECTOR_RANGE = (0x08F594, 0x08F5D4)
TABLE_SELECTOR_SHA256 = "0c586c11a8c452e4096d4cf444bb5c75628d099020ff8e5642f99634ea022efd"
INTERPRETER_RANGE = (0x0977B8, 0x097E34)
INTERPRETER_SHA256 = "1e0c0550c08d7bbdd3395085112ccc864caffbd10db9d840a86294454f6cd249"
DISPATCH_TABLE_RANGE = (0x0977F4, 0x0978DC)
DISPATCH_TABLE_SHA256 = "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"
RENDERER_PARSER_RANGE = (0x06626C, 0x066736)
RENDERER_PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
TOKEN_PARSER_RANGE = (0x0960F0, 0x096138)
TOKEN_PARSER_SHA256 = "665cf2bbb49966bdfe69a7c55ed0ef5af763c8b12f1681ee47f0538e1c0426b9"
SJIS_RANGE_TABLE = 0x53D644
SJIS_RANGE_COUNT = 31
SJIS_RANGE_ENTRY_SIZE = 8
SJIS_RANGE_TABLE_END = SJIS_RANGE_TABLE + SJIS_RANGE_COUNT * SJIS_RANGE_ENTRY_SIZE
SJIS_RANGE_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

SPEAKER_LABEL_BASE = 0x5A57C4
SPEAKER_LABEL_STRIDE = 12
SPEAKER_LABEL_IDS = (
    *range(1, 32),
    35,
    36,
    37,
    41,
    *range(43, 55),
    56,
    61,
)
SPEAKER_DISPATCH_ENTRIES = ((0x08, 0x097814), (0x0E, 0x09782C))
SPEAKER_HANDLER = 0x0979E8
SPEAKER_FORMULA_RANGE = (0x097A0A, 0x097A38)
SPEAKER_FORMULA_SHA256 = "69b08531ec43f96019787e6b559f50cebe585200224f85a7137e564187d60226"
SPEAKER_BASE_LITERAL = 0x097A40
SPEAKER_RENDERER = 0x06626C
SPEAKER_RANGE_DENOMINATOR_SHA256 = (
    "118e9d300bded69407cfe4fe7a8625654af6532ba5a4da3058ca8542fa5e1779"
)
SPEAKER_BUNDLE_SHA256 = (
    "07c5281f03633aea88c4b70a4a0f755da92707aa2ab6e1a205a20252f8e78831"
)

PAYLOAD_NAME = "chapter-script-inventory.json"
BUNDLE_NAME = "chapter-script-bytes.bin"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
BUNDLE_SHA256 = "eba1393714485ab78d0dbde6cb1b9cf407e031ce8c2a86068038a3920d5f0699"
RANGE_DENOMINATOR_SHA256 = "351b76c28ab7ead1a1ea086523fb55f2178f2449076fe01a2460efa51ae9d2d2"

FIXED_LENGTHS = {
    0x02: 4,
    0x03: 2,
    0x04: 4,
    0x08: 2,
    0x09: 2,
    0x0A: 2,
    0x0E: 3,
    0x0F: 2,
    0x10: 1,
    0x11: 2,
    0x12: 5,
    0x14: 3,
    0x16: 2,
    0x17: 4,
    0x18: 4,
    0x19: 4,
    0x1A: 3,
    0x1B: 3,
    0x1C: 3,
    0x1D: 3,
    0x1E: 2,
    0x1F: 2,
    0x21: 5,
    0x22: 4,
    0x23: 3,
    0x33: 2,
    0x37: 3,
}
CONDITIONAL_LAYOUTS = {
    0x0B: (6, 2),
    0x0C: (6, 2),
    0x15: (8, 4),
    0x34: (8, 4),
    0x35: (9, 5),
    0x36: (8, 4),
    0x38: (7, 3),
    0x39: (6, 2),
}
EXPECTED_SUMMARY = {
    "pointer_table_slot_count": 204,
    "non_null_script_slots": 200,
    "unique_script_roots": 188,
    "unique_instruction_nodes": 18_994,
    "dynamic_opcode_06_nodes": 42,
    "observed_opcode_count": 43,
    "terminal_node_count": 590,
    "parse_failure_count": 0,
    "raw_node_bytes": 334_060,
    "node_overlap_bytes": 0,
    "merged_range_count": 92,
    "merged_range_bytes": 334_060,
    "internal_gap_count": 91,
    "internal_gap_bytes": 3_769,
    "packed_script_bytes": 334_060,
}
SCOPE = {
    "fixed_pointer_table_denominator_complete": True,
    "static_control_flow_closure_complete": True,
    "interpreter_consumed_byte_union_complete": True,
    "natural_gameplay_root_reachability_complete": False,
    "natural_language_decoding_complete": False,
}
LIMITATIONS = [
    "Only records statically reachable from the 200 non-null slots in the four fixed-ROM interpreter pointer tables are classified; internal gaps and bytes outside the reachable union remain unknown.",
    "Merged ranges contain bytecode records and their interpreter-consumed inline text or pointer operands; they are not asserted to be natural-language decoded text.",
    "Opcode 0x06 has no runtime bounds check; the fixed-ROM corpus proves only its two in-record pointer branches.",
    "All non-null auxiliary slots are structurally typed by direct table-lookup-to-interpreter consumers; this does not assert every auxiliary index or chapter root is reached during natural gameplay.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _slice(rom: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError(f"ROM range is invalid at {_addr(offset)}")
    return rom[offset : offset + size]


def _u8(rom: bytes, offset: int) -> int:
    return _slice(rom, offset, 1)[0]


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _slice(rom, offset, 4))[0]


def _pointer(rom: bytes, offset: int, label: str) -> int:
    address = _u32(rom, offset)
    target = address - ROM_BASE
    if address < ROM_BASE or not 0 <= target < len(rom):
        raise ValueError(f"{label} is not a ROM pointer: 0x{address:08X}")
    return target


def _sjis_pair_valid(rom: bytes, lead: int, trail: int) -> bool:
    code = lead << 8 | trail
    for index in range(SJIS_RANGE_COUNT):
        raw = _slice(rom, SJIS_RANGE_TABLE + index * SJIS_RANGE_ENTRY_SIZE, 3)
        lower = int.from_bytes(raw[:2], "little")
        if lower <= code < lower + raw[2]:
            return True
    return False


def _renderer_text_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _u8(rom, cursor)
        if value == 0:
            return cursor + 1
        if value == 1:
            width = 2
        elif value == 2:
            width = 3
        elif 0x80 <= value <= 0x9F:
            width = 2
        elif value >= 0xA0 and _sjis_pair_valid(rom, value, _u8(rom, cursor + 1)):
            width = 2
        else:
            width = 1
        _slice(rom, cursor, width)
        cursor += width


def _token_text_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _u8(rom, cursor)
        if value == 0:
            return cursor + 1
        width = 2 if value == 1 or 0x80 <= value <= 0x9F else 3 if value == 2 else 1
        _slice(rom, cursor, width)
        cursor += width


def _decode_node(rom: bytes, offset: int) -> tuple[int, int, list[int]]:
    opcode = _u8(rom, offset)
    if opcode == 0x00:
        return opcode, 1, []
    if opcode in FIXED_LENGTHS:
        length = FIXED_LENGTHS[opcode]
        _slice(rom, offset, length)
        return opcode, length, [offset + length]
    if opcode == 0x01:
        end = _renderer_text_end(rom, offset + 1)
        return opcode, end - offset, [end]
    if opcode in (0x05, 0x20):
        end = _renderer_text_end(rom, offset + 2)
        return opcode, end - offset, [end]
    if opcode == 0x06:
        return opcode, 9, [
            _pointer(rom, offset + 1, "opcode 0x06 branch 0"),
            _pointer(rom, offset + 5, "opcode 0x06 branch 1"),
        ]
    if opcode == 0x07:
        return opcode, 5, [_pointer(rom, offset + 1, "opcode 0x07 target")]
    if opcode in CONDITIONAL_LAYOUTS:
        length, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, length, [
            _pointer(rom, offset + pointer_offset, f"opcode 0x{opcode:02X} target"),
            offset + length,
        ]
    if opcode == 0x0D:
        return opcode, 5, [
            _pointer(rom, offset + 1, "opcode 0x0D call target"),
            offset + 5,
        ]
    if opcode == 0x13:
        first_end = _token_text_end(rom, offset + 4)
        if _u8(rom, offset + 2) == 0:
            return opcode, first_end - offset, [first_end]
        second_end = _token_text_end(rom, first_end + 1)
        return opcode, second_end - offset, [second_end]
    if opcode == 0x32:
        cursor = offset
        edges: list[int] = []
        while _u8(rom, cursor) == 0x32:
            edges.append(_pointer(rom, cursor + 1, "opcode 0x32 case target"))
            cursor += 5
        edges.append(cursor)
        return opcode, cursor - offset, edges
    if 0x24 <= opcode <= 0x31:
        raise ValueError(f"reserved opcode 0x{opcode:02X} at {_addr(offset)}")
    raise ValueError(f"unsupported opcode 0x{opcode:02X} at {_addr(offset)}")


def _pointer_tables(rom: bytes) -> tuple[list[dict[str, Any]], list[tuple[str, int, int]]]:
    records = []
    roots = []
    for name, start, entry_count, expected_sha in TABLE_SPECS:
        table_size = entry_count * 4
        raw = _slice(rom, start, table_size)
        if _sha(raw) != expected_sha or _u32(rom, start) != 0:
            raise ValueError(f"{name} chapter pointer table changed")
        for scenario_id in range(1, entry_count):
            roots.append(
                (name, scenario_id, _pointer(rom, start + scenario_id * 4, f"{name}[{scenario_id}]"))
            )
        records.append(
            {
                "name": name,
                "file_range": [start, start + table_size],
                "gba_range": [_addr(start), _addr(start + table_size)],
                "entry_count": entry_count,
                "null_sentinel_count": 1,
                "non_null_slot_count": entry_count - 1,
                "sha256": expected_sha,
            }
        )
    return records, roots


def _walk_scripts(
    rom: bytes, roots: list[tuple[str, int, int]]
) -> tuple[dict[int, tuple[int, int]], list[dict[str, Any]]]:
    nodes: dict[int, tuple[int, int]] = {}
    failures: list[dict[str, Any]] = []
    for table, scenario_id, root in roots:
        pending = [root]
        visited: set[int] = set()
        try:
            while pending:
                offset = pending.pop()
                if offset in visited:
                    continue
                visited.add(offset)
                opcode, length, edges = _decode_node(rom, offset)
                previous = nodes.setdefault(offset, (opcode, length))
                if previous != (opcode, length):
                    raise ValueError(f"node instability at {_addr(offset)}")
                pending.extend(edge for edge in edges if edge not in visited)
        except ValueError as error:
            failures.append(
                {
                    "table": table,
                    "scenario_id": scenario_id,
                    "root": _addr(root),
                    "error": str(error),
                }
            )
    return nodes, failures


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _checked_evidence_slice(
    rom: bytes, start: int, end: int, expected_sha: str, label: str
) -> dict[str, Any]:
    if _sha(_slice(rom, start, end - start)) != expected_sha:
        raise ValueError(f"{label} bytes changed")
    return {
        "file_range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": expected_sha,
    }


def _thumb_bl_target(rom: bytes, offset: int) -> int:
    first = int.from_bytes(_slice(rom, offset, 2), "little")
    second = int.from_bytes(_slice(rom, offset + 2, 2), "little")
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"expected Thumb BL at {_addr(offset)}")
    displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return offset + 4 + displacement


def _auxiliary_consumer_evidence(rom: bytes) -> list[dict[str, Any]]:
    records = []
    for (
        name,
        function_start,
        function_end,
        function_sha256,
        literal_offset,
        table_offset,
        lookup_start,
        lookup_end,
        lookup_sha256,
        call_offset,
        typed_slots,
        index_evidence,
    ) in AUXILIARY_CONSUMER_SPECS:
        if _sha(_slice(rom, function_start, function_end - function_start)) != function_sha256:
            raise ValueError(f"{name} consumer function changed")
        if _u32(rom, literal_offset) != ROM_BASE + table_offset:
            raise ValueError(f"{name} table literal changed")
        if _sha(_slice(rom, lookup_start, lookup_end - lookup_start)) != lookup_sha256:
            raise ValueError(f"{name} indexed lookup changed")
        if _thumb_bl_target(rom, call_offset) != INTERPRETER_RANGE[0]:
            raise ValueError(f"{name} no longer calls the chapter interpreter")
        records.append(
            {
                "name": name,
                "function_range": [function_start, function_end],
                "function_sha256": function_sha256,
                "table_literal_offset": literal_offset,
                "lookup_range": [lookup_start, lookup_end],
                "lookup_sha256": lookup_sha256,
                "interpreter_call_offset": call_offset,
                "typed_script_slot_count": typed_slots,
                "runtime_index_evidence": index_evidence,
                "runtime_index_domain_complete": False,
            }
        )
    return records


def _consumer_evidence(rom: bytes) -> dict[str, Any]:
    selector = _checked_evidence_slice(
        rom, *TABLE_SELECTOR_RANGE, TABLE_SELECTOR_SHA256, "table selector"
    )
    interpreter = _checked_evidence_slice(
        rom, *INTERPRETER_RANGE, INTERPRETER_SHA256, "chapter interpreter"
    )
    dispatch_start, dispatch_end = DISPATCH_TABLE_RANGE
    if _sha(_slice(rom, dispatch_start, dispatch_end - dispatch_start)) != DISPATCH_TABLE_SHA256:
        raise ValueError("chapter dispatch table changed")
    interpreter["dispatch_table_range"] = [dispatch_start, dispatch_end]
    interpreter["dispatch_table_sha256"] = DISPATCH_TABLE_SHA256
    return {
        "table_selector": selector,
        "auxiliary_table_consumers": _auxiliary_consumer_evidence(rom),
        "interpreter": interpreter,
        "renderer_parser": _checked_evidence_slice(
            rom, *RENDERER_PARSER_RANGE, RENDERER_PARSER_SHA256, "renderer parser"
        ),
        "token_parser": _checked_evidence_slice(
            rom, *TOKEN_PARSER_RANGE, TOKEN_PARSER_SHA256, "token parser"
        ),
        "sjis_range_table": {
            **_checked_evidence_slice(
                rom,
                SJIS_RANGE_TABLE,
                SJIS_RANGE_TABLE_END,
                SJIS_RANGE_TABLE_SHA256,
                "SJIS range table",
            ),
            "entry_count": SJIS_RANGE_COUNT,
            "entry_size": SJIS_RANGE_ENTRY_SIZE,
        },
    }


def _speaker_label_resource(
    rom: bytes, nodes: dict[int, tuple[int, int]]
) -> dict[str, Any]:
    dispatch_entries = []
    for opcode, entry_offset in SPEAKER_DISPATCH_ENTRIES:
        if _u32(rom, entry_offset) != ROM_BASE + SPEAKER_HANDLER:
            raise ValueError(f"speaker dispatch slot 0x{opcode:02X} changed")
        dispatch_entries.append(
            {
                "opcode": f"0x{opcode:02X}",
                "entry_offset": entry_offset,
                "handler_address": _addr(SPEAKER_HANDLER),
            }
        )
    formula_start, formula_end = SPEAKER_FORMULA_RANGE
    if _sha(_slice(rom, formula_start, formula_end - formula_start)) != SPEAKER_FORMULA_SHA256:
        raise ValueError("speaker label formula changed")
    if _u32(rom, SPEAKER_BASE_LITERAL) != ROM_BASE + SPEAKER_LABEL_BASE:
        raise ValueError("speaker label base literal changed")
    for call_offset in (0x097A18, 0x097A34):
        if _thumb_bl_target(rom, call_offset) != SPEAKER_RENDERER:
            raise ValueError("speaker label renderer call changed")

    reference_node_counts = Counter()
    referenced_ids: list[int] = []
    for offset, (opcode, _) in nodes.items():
        if opcode == 0x08:
            reference_node_counts[opcode] += 1
            referenced_ids.append(_u8(rom, offset + 1))
        elif opcode == 0x0E:
            reference_node_counts[opcode] += 1
            referenced_ids.extend((_u8(rom, offset + 1), _u8(rom, offset + 2)))
    unique_ids = sorted(set(referenced_ids))
    if tuple(unique_ids) != SPEAKER_LABEL_IDS:
        raise ValueError("speaker label ID denominator changed")

    records = []
    semantic_ranges = []
    semantic_bundle = bytearray()
    length_distribution = Counter()
    structural_bytes = 0
    post_nul_padding = 0
    for label_id in unique_ids:
        start = SPEAKER_LABEL_BASE + label_id * SPEAKER_LABEL_STRIDE
        slot_end = start + SPEAKER_LABEL_STRIDE
        end = _renderer_text_end(rom, start)
        if end > slot_end:
            raise ValueError(f"speaker label {label_id} terminator escapes its slot")
        raw = _slice(rom, start, end - start)
        semantic_ranges.append([start, end])
        semantic_bundle.extend(raw)
        length_distribution[len(raw)] += 1
        structural_bytes += SPEAKER_LABEL_STRIDE
        post_nul_padding += slot_end - end
        records.append(
            {
                "label_id": label_id,
                "slot_range": [start, slot_end],
                "renderer_range": [start, end],
                "gba_renderer_range": [_addr(start), _addr(end)],
                "size": len(raw),
                "bytes_sha256": _sha(raw),
            }
        )
    range_hash = _sha(
        json.dumps(semantic_ranges, separators=(",", ":")).encode("ascii")
    )
    bundle_hash = _sha(bytes(semantic_bundle))
    summary = {
        "reference_node_counts": {
            "0x08": reference_node_counts[0x08],
            "0x0E": reference_node_counts[0x0E],
        },
        "operand_reference_count": len(referenced_ids),
        "referenced_label_ids": unique_ids,
        "structural_record_count": len(records),
        "structural_record_bytes": structural_bytes,
        "renderer_consumed_record_count": len(records),
        "renderer_consumed_bytes": len(semantic_bundle),
        "post_nul_padding_bytes": post_nul_padding,
        "renderer_length_distribution": {
            str(length): count for length, count in sorted(length_distribution.items())
        },
        "semantic_range_denominator_sha256": range_hash,
        "semantic_bundle_sha256": bundle_hash,
    }
    expected_summary = {
        "reference_node_counts": {"0x08": 5_701, "0x0E": 7},
        "operand_reference_count": 5_715,
        "referenced_label_ids": list(SPEAKER_LABEL_IDS),
        "structural_record_count": 49,
        "structural_record_bytes": 588,
        "renderer_consumed_record_count": 49,
        "renderer_consumed_bytes": 251,
        "post_nul_padding_bytes": 337,
        "renderer_length_distribution": {"3": 9, "5": 28, "7": 12},
        "semantic_range_denominator_sha256": SPEAKER_RANGE_DENOMINATOR_SHA256,
        "semantic_bundle_sha256": SPEAKER_BUNDLE_SHA256,
    }
    if summary != expected_summary:
        raise ValueError(f"speaker label semantic denominator changed: {summary}")
    return {
        "summary": summary,
        "consumer_evidence": {
            "dispatch_entries": dispatch_entries,
            "handler_address": _addr(SPEAKER_HANDLER),
            "formula_range": [formula_start, formula_end],
            "formula_sha256": SPEAKER_FORMULA_SHA256,
            "record_base_literal_offset": SPEAKER_BASE_LITERAL,
            "record_base_address": _addr(SPEAKER_LABEL_BASE),
            "record_stride": SPEAKER_LABEL_STRIDE,
            "renderer_address": _addr(SPEAKER_RENDERER),
        },
        "records": records,
        "scope": {
            "fixed_interpreter_reference_denominator_complete": True,
            "renderer_consumed_byte_union_complete": True,
            "post_nul_padding_semantically_classified": False,
            "natural_gameplay_reference_coverage_complete": False,
        },
        "limitations": [
            "Only bytes through each referenced slot's first renderer-valid NUL are classified; 337 post-NUL slot bytes remain padding with no stronger semantic claim.",
            "Static references from the four fixed script tables do not prove every label reference executes during natural gameplay.",
        ],
    }


def _grammar() -> dict[str, Any]:
    return {
        "fixed_lengths": {
            f"0x{opcode:02X}": length for opcode, length in sorted(FIXED_LENGTHS.items())
        },
        "conditional_layouts": {
            f"0x{opcode:02X}": {"length": length, "pointer_offset": pointer_offset}
            for opcode, (length, pointer_offset) in sorted(CONDITIONAL_LAYOUTS.items())
        },
        "variable_records": {
            "0x00": "terminal byte",
            "0x01": "opcode followed by renderer text through NUL",
            "0x05/0x20": "two-byte header followed by renderer text through NUL",
            "0x06": "opcode followed by two ROM pointers",
            "0x07": "opcode followed by one ROM pointer",
            "0x0D": "call pointer plus fallthrough",
            "0x13": "four-byte header and one or two token strings",
            "0x32": "one or more opcode-plus-pointer cases",
        },
        "reserved_opcodes": "0x24..0x31",
    }


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = root.resolve(strict=True)
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    pointer_tables, roots = _pointer_tables(rom)
    nodes, failures = _walk_scripts(rom, roots)
    raw_ranges = [(offset, offset + length) for offset, (_, length) in nodes.items()]
    merged = _merge_ranges(raw_ranges)
    merged_bytes = sum(end - start for start, end in merged)
    raw_node_bytes = sum(end - start for start, end in raw_ranges)
    gap_bytes = sum(
        next_start - end
        for (_, end), (next_start, _) in zip(merged, merged[1:])
    )
    range_denominator = _sha(
        json.dumps(merged, separators=(",", ":")).encode("ascii")
    )
    if range_denominator != RANGE_DENOMINATOR_SHA256:
        raise ValueError("chapter script range denominator changed")

    opcode_nodes = Counter(opcode for opcode, _ in nodes.values())
    opcode_bytes = Counter()
    for opcode, length in nodes.values():
        opcode_bytes[opcode] += length
    observed_opcodes = {
        f"0x{opcode:02X}": {
            "nodes": opcode_nodes[opcode],
            "bytes": opcode_bytes[opcode],
        }
        for opcode in sorted(opcode_nodes)
    }
    summary = {
        "pointer_table_slot_count": TOTAL_TABLE_SLOTS,
        "non_null_script_slots": len(roots),
        "unique_script_roots": len({root for _, _, root in roots}),
        "unique_instruction_nodes": len(nodes),
        "dynamic_opcode_06_nodes": opcode_nodes[0x06],
        "observed_opcode_count": len(opcode_nodes),
        "terminal_node_count": opcode_nodes[0x00],
        "parse_failure_count": len(failures),
        "raw_node_bytes": raw_node_bytes,
        "node_overlap_bytes": raw_node_bytes - merged_bytes,
        "merged_range_count": len(merged),
        "merged_range_bytes": merged_bytes,
        "internal_gap_count": max(0, len(merged) - 1),
        "internal_gap_bytes": gap_bytes,
        "packed_script_bytes": merged_bytes,
    }
    if summary != EXPECTED_SUMMARY or failures:
        raise ValueError(f"chapter script denominator changed: {summary}; failures={failures}")

    bundle = bytearray()
    ranges = []
    for range_id, (start, end) in enumerate(merged):
        packed_start = len(bundle)
        raw = rom[start:end]
        bundle.extend(raw)
        ranges.append(
            {
                "range_id": range_id,
                "range": [start, end],
                "gba_range": [_addr(start), _addr(end)],
                "packed_range": [packed_start, len(bundle)],
                "size": end - start,
                "bytes_sha256": _sha(raw),
            }
        )
    if _sha(bytes(bundle)) != BUNDLE_SHA256:
        raise ValueError("chapter script bundle changed")

    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_chapter_script_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_chapter_script_inventory.py").read_bytes()
        ),
    }
    payload = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "pointer_tables": pointer_tables,
        "consumer_evidence": _consumer_evidence(rom),
        "grammar": _grammar(),
        "observed_opcodes": observed_opcodes,
        "referenced_resources": {
            "speaker_labels": _speaker_label_resource(rom, nodes),
        },
        "range_denominator_sha256": range_denominator,
        "summary": summary,
        "ranges": ranges,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bytes(bundle))}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
    }
    payload_raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    return payload, {PAYLOAD_NAME: payload_raw, BUNDLE_NAME: bytes(bundle)}


def _promotion_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_chapter_script_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_chapter_script_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                **EXPECTED_SUMMARY,
                "errors": [],
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    target = output.expanduser().resolve()
    root = root.resolve()
    if output.is_symlink() or target == root or target in root.parents:
        raise ValueError("output directory is unsafe")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    members = list(target.rglob("*"))
    actual = {
        member.relative_to(target).as_posix() for member in members if member.is_file()
    }
    if (
        any(member.is_symlink() for member in members)
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != EXPECTED_FILES
    ):
        raise ValueError("refusing to replace foreign output")
    for name, expected in manifest.get("files", {}).items():
        if _sha((target / name).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace(output: Path, files: dict[str, bytes], manifest: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    backup = None
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            if not output.exists():
                backup.rename(output)
            else:
                shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    target = _validate_output(root, output)
    payload, files = _build(root)
    _replace(target, files, _promotion_manifest(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
