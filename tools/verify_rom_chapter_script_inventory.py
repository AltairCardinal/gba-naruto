#!/usr/bin/env python3
"""Independently verify the fixed-ROM chapter-script byte inventory."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-chapter-script-inventory-v1"
VERIFY_SCHEMA = "rom-chapter-script-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456

TABLE_CONTRACTS = (
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
TOTAL_TABLE_SLOTS = sum(entry_count for _, _, entry_count, _ in TABLE_CONTRACTS)

AUXILIARY_CONSUMER_CONTRACTS = (
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
SJIS_RANGE_TABLE_END = 0x53D73C
SJIS_RANGE_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

SPEAKER_BASE = 0x5A57C4
SPEAKER_STRIDE = 12
EXPECTED_SPEAKER_IDS = (
    *range(1, 32),
    35,
    36,
    37,
    41,
    *range(43, 55),
    56,
    61,
)
SPEAKER_DISPATCH_CONTRACTS = ((0x08, 0x097814), (0x0E, 0x09782C))
SPEAKER_HANDLER_OFFSET = 0x0979E8
SPEAKER_FORMULA_WINDOW = (0x097A0A, 0x097A38)
SPEAKER_FORMULA_HASH = "69b08531ec43f96019787e6b559f50cebe585200224f85a7137e564187d60226"
SPEAKER_LITERAL_OFFSET = 0x097A40
SPEAKER_RENDERER_OFFSET = 0x06626C
SPEAKER_RANGES_HASH = (
    "118e9d300bded69407cfe4fe7a8625654af6532ba5a4da3058ca8542fa5e1779"
)
SPEAKER_BYTES_HASH = (
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


def _take(rom: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError(f"invalid ROM range at {_addr(offset)}")
    return rom[offset : offset + size]


def _byte(rom: bytes, offset: int) -> int:
    return _take(rom, offset, 1)[0]


def _word(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _take(rom, offset, 4))[0]


def _rom_target(rom: bytes, offset: int, label: str) -> int:
    address = _word(rom, offset)
    target = address - ROM_BASE
    if address < ROM_BASE or not 0 <= target < len(rom):
        raise ValueError(f"{label} pointer escapes ROM: 0x{address:08X}")
    return target


def _valid_sjis_pair(rom: bytes, first: int, second: int) -> bool:
    code = first << 8 | second
    for index in range(SJIS_RANGE_COUNT):
        raw = _take(rom, SJIS_RANGE_TABLE + index * SJIS_RANGE_ENTRY_SIZE, 3)
        start = int.from_bytes(raw[:2], "little")
        if start <= code < start + raw[2]:
            return True
    return False


def _rendered_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _byte(rom, cursor)
        if value == 0:
            return cursor + 1
        if value == 1:
            width = 2
        elif value == 2:
            width = 3
        elif 0x80 <= value <= 0x9F:
            width = 2
        elif value >= 0xA0 and _valid_sjis_pair(rom, value, _byte(rom, cursor + 1)):
            width = 2
        else:
            width = 1
        _take(rom, cursor, width)
        cursor += width


def _token_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _byte(rom, cursor)
        if value == 0:
            return cursor + 1
        if value == 1 or 0x80 <= value <= 0x9F:
            width = 2
        elif value == 2:
            width = 3
        else:
            width = 1
        _take(rom, cursor, width)
        cursor += width


def _decode(rom: bytes, offset: int) -> tuple[int, int, list[int]]:
    opcode = _byte(rom, offset)
    if opcode == 0:
        return opcode, 1, []
    if opcode in FIXED_LENGTHS:
        size = FIXED_LENGTHS[opcode]
        _take(rom, offset, size)
        return opcode, size, [offset + size]
    if opcode == 1:
        end = _rendered_end(rom, offset + 1)
        return opcode, end - offset, [end]
    if opcode in (5, 0x20):
        end = _rendered_end(rom, offset + 2)
        return opcode, end - offset, [end]
    if opcode == 6:
        return opcode, 9, [
            _rom_target(rom, offset + 1, "opcode 06 first"),
            _rom_target(rom, offset + 5, "opcode 06 second"),
        ]
    if opcode == 7:
        return opcode, 5, [_rom_target(rom, offset + 1, "opcode 07")]
    if opcode in CONDITIONAL_LAYOUTS:
        size, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, size, [
            _rom_target(rom, offset + pointer_offset, f"opcode {opcode:02X}"),
            offset + size,
        ]
    if opcode == 0x0D:
        return opcode, 5, [
            _rom_target(rom, offset + 1, "opcode 0D"),
            offset + 5,
        ]
    if opcode == 0x13:
        first_end = _token_end(rom, offset + 4)
        if _byte(rom, offset + 2) == 0:
            return opcode, first_end - offset, [first_end]
        second_end = _token_end(rom, first_end + 1)
        return opcode, second_end - offset, [second_end]
    if opcode == 0x32:
        cursor = offset
        edges = []
        while _byte(rom, cursor) == 0x32:
            edges.append(_rom_target(rom, cursor + 1, "opcode 32 case"))
            cursor += 5
        edges.append(cursor)
        return opcode, cursor - offset, edges
    if 0x24 <= opcode <= 0x31:
        raise ValueError(f"reserved opcode 0x{opcode:02X} at {_addr(offset)}")
    raise ValueError(f"unsupported opcode 0x{opcode:02X} at {_addr(offset)}")


def _table_contract(rom: bytes) -> tuple[list[dict[str, Any]], list[tuple[str, int, int]]]:
    tables = []
    roots = []
    for name, start, entry_count, expected_hash in TABLE_CONTRACTS:
        table_size = entry_count * 4
        raw = _take(rom, start, table_size)
        if _sha(raw) != expected_hash or _word(rom, start) != 0:
            raise ValueError(f"{name} pointer table identity changed")
        for scenario_id in range(1, entry_count):
            roots.append(
                (name, scenario_id, _rom_target(rom, start + scenario_id * 4, name))
            )
        tables.append(
            {
                "name": name,
                "file_range": [start, start + table_size],
                "gba_range": [_addr(start), _addr(start + table_size)],
                "entry_count": entry_count,
                "null_sentinel_count": 1,
                "non_null_slot_count": entry_count - 1,
                "sha256": expected_hash,
            }
        )
    return tables, roots


def _walk_scripts(
    rom: bytes, roots: list[tuple[str, int, int]]
) -> tuple[dict[int, tuple[int, int]], list[str]]:
    nodes: dict[int, tuple[int, int]] = {}
    failures = []
    for table, scenario_id, root in roots:
        todo = [root]
        seen: set[int] = set()
        try:
            while todo:
                offset = todo.pop()
                if offset in seen:
                    continue
                seen.add(offset)
                opcode, size, edges = _decode(rom, offset)
                if offset in nodes and nodes[offset] != (opcode, size):
                    raise ValueError(f"unstable node at {_addr(offset)}")
                nodes[offset] = (opcode, size)
                todo.extend(edge for edge in edges if edge not in seen)
        except ValueError as error:
            failures.append(f"{table}[{scenario_id}] {_addr(root)}: {error}")
    return nodes, failures


def _coalesce(ranges: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _evidence_record(
    rom: bytes, start: int, end: int, expected_hash: str, label: str
) -> dict[str, Any]:
    if _sha(_take(rom, start, end - start)) != expected_hash:
        raise ValueError(f"{label} hash changed")
    return {
        "file_range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": expected_hash,
    }


def _decode_thumb_bl_target(rom: bytes, offset: int) -> int:
    high = int.from_bytes(_take(rom, offset, 2), "little")
    low = int.from_bytes(_take(rom, offset + 2, 2), "little")
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        raise ValueError(f"missing Thumb BL at {_addr(offset)}")
    delta = ((high & 0x07FF) << 12) | ((low & 0x07FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _auxiliary_evidence(rom: bytes) -> list[dict[str, Any]]:
    result = []
    for (
        name,
        function_start,
        function_end,
        function_hash,
        literal_offset,
        table_offset,
        lookup_start,
        lookup_end,
        lookup_hash,
        call_offset,
        typed_slots,
        index_evidence,
    ) in AUXILIARY_CONSUMER_CONTRACTS:
        if _sha(_take(rom, function_start, function_end - function_start)) != function_hash:
            raise ValueError(f"{name} consumer function hash changed")
        if _word(rom, literal_offset) != ROM_BASE + table_offset:
            raise ValueError(f"{name} table literal differs")
        if _sha(_take(rom, lookup_start, lookup_end - lookup_start)) != lookup_hash:
            raise ValueError(f"{name} lookup instruction hash changed")
        if _decode_thumb_bl_target(rom, call_offset) != INTERPRETER_RANGE[0]:
            raise ValueError(f"{name} consumer BL target differs")
        result.append(
            {
                "name": name,
                "function_range": [function_start, function_end],
                "function_sha256": function_hash,
                "table_literal_offset": literal_offset,
                "lookup_range": [lookup_start, lookup_end],
                "lookup_sha256": lookup_hash,
                "interpreter_call_offset": call_offset,
                "typed_script_slot_count": typed_slots,
                "runtime_index_evidence": index_evidence,
                "runtime_index_domain_complete": False,
            }
        )
    return result


def _expected_evidence(rom: bytes) -> dict[str, Any]:
    interpreter = _evidence_record(
        rom, *INTERPRETER_RANGE, INTERPRETER_SHA256, "interpreter"
    )
    start, end = DISPATCH_TABLE_RANGE
    if _sha(_take(rom, start, end - start)) != DISPATCH_TABLE_SHA256:
        raise ValueError("dispatch table hash changed")
    interpreter["dispatch_table_range"] = [start, end]
    interpreter["dispatch_table_sha256"] = DISPATCH_TABLE_SHA256
    return {
        "table_selector": _evidence_record(
            rom, *TABLE_SELECTOR_RANGE, TABLE_SELECTOR_SHA256, "table selector"
        ),
        "auxiliary_table_consumers": _auxiliary_evidence(rom),
        "interpreter": interpreter,
        "renderer_parser": _evidence_record(
            rom, *RENDERER_PARSER_RANGE, RENDERER_PARSER_SHA256, "renderer parser"
        ),
        "token_parser": _evidence_record(
            rom, *TOKEN_PARSER_RANGE, TOKEN_PARSER_SHA256, "token parser"
        ),
        "sjis_range_table": {
            **_evidence_record(
                rom,
                SJIS_RANGE_TABLE,
                SJIS_RANGE_TABLE_END,
                SJIS_RANGE_TABLE_SHA256,
                "SJIS table",
            ),
            "entry_count": SJIS_RANGE_COUNT,
            "entry_size": SJIS_RANGE_ENTRY_SIZE,
        },
    }


def _speaker_resource(
    rom: bytes, nodes: dict[int, tuple[int, int]]
) -> dict[str, Any]:
    dispatch = []
    for opcode, entry_offset in SPEAKER_DISPATCH_CONTRACTS:
        if _word(rom, entry_offset) != ROM_BASE + SPEAKER_HANDLER_OFFSET:
            raise ValueError(f"speaker opcode {opcode:02X} dispatch differs")
        dispatch.append(
            {
                "opcode": f"0x{opcode:02X}",
                "entry_offset": entry_offset,
                "handler_address": _addr(SPEAKER_HANDLER_OFFSET),
            }
        )
    formula_start, formula_end = SPEAKER_FORMULA_WINDOW
    if _sha(_take(rom, formula_start, formula_end - formula_start)) != SPEAKER_FORMULA_HASH:
        raise ValueError("speaker address formula differs")
    if _word(rom, SPEAKER_LITERAL_OFFSET) != ROM_BASE + SPEAKER_BASE:
        raise ValueError("speaker table base literal differs")
    if any(
        _decode_thumb_bl_target(rom, call_offset) != SPEAKER_RENDERER_OFFSET
        for call_offset in (0x097A18, 0x097A34)
    ):
        raise ValueError("speaker renderer calls differ")

    node_counts = Counter()
    operand_ids = []
    for offset, (opcode, _) in nodes.items():
        if opcode == 0x08:
            node_counts[opcode] += 1
            operand_ids.append(_byte(rom, offset + 1))
        elif opcode == 0x0E:
            node_counts[opcode] += 1
            operand_ids.extend((_byte(rom, offset + 1), _byte(rom, offset + 2)))
    label_ids = sorted(set(operand_ids))
    if tuple(label_ids) != EXPECTED_SPEAKER_IDS:
        raise ValueError("speaker referenced-ID set differs")

    records = []
    renderer_ranges = []
    renderer_bytes = bytearray()
    length_counts = Counter()
    padding_bytes = 0
    for label_id in label_ids:
        start = SPEAKER_BASE + label_id * SPEAKER_STRIDE
        slot_end = start + SPEAKER_STRIDE
        end = _rendered_end(rom, start)
        if end > slot_end:
            raise ValueError(f"speaker label {label_id} exceeds its record")
        raw = _take(rom, start, end - start)
        renderer_ranges.append([start, end])
        renderer_bytes.extend(raw)
        length_counts[len(raw)] += 1
        padding_bytes += slot_end - end
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
    ranges_hash = _sha(
        json.dumps(renderer_ranges, separators=(",", ":")).encode("ascii")
    )
    bytes_hash = _sha(bytes(renderer_bytes))
    summary = {
        "reference_node_counts": {"0x08": node_counts[0x08], "0x0E": node_counts[0x0E]},
        "operand_reference_count": len(operand_ids),
        "referenced_label_ids": label_ids,
        "structural_record_count": len(records),
        "structural_record_bytes": len(records) * SPEAKER_STRIDE,
        "renderer_consumed_record_count": len(records),
        "renderer_consumed_bytes": len(renderer_bytes),
        "post_nul_padding_bytes": padding_bytes,
        "renderer_length_distribution": {
            str(length): count for length, count in sorted(length_counts.items())
        },
        "semantic_range_denominator_sha256": ranges_hash,
        "semantic_bundle_sha256": bytes_hash,
    }
    if summary != {
        "reference_node_counts": {"0x08": 5_701, "0x0E": 7},
        "operand_reference_count": 5_715,
        "referenced_label_ids": list(EXPECTED_SPEAKER_IDS),
        "structural_record_count": 49,
        "structural_record_bytes": 588,
        "renderer_consumed_record_count": 49,
        "renderer_consumed_bytes": 251,
        "post_nul_padding_bytes": 337,
        "renderer_length_distribution": {"3": 9, "5": 28, "7": 12},
        "semantic_range_denominator_sha256": SPEAKER_RANGES_HASH,
        "semantic_bundle_sha256": SPEAKER_BYTES_HASH,
    }:
        raise ValueError(f"speaker semantic denominator differs: {summary}")
    return {
        "summary": summary,
        "consumer_evidence": {
            "dispatch_entries": dispatch,
            "handler_address": _addr(SPEAKER_HANDLER_OFFSET),
            "formula_range": [formula_start, formula_end],
            "formula_sha256": SPEAKER_FORMULA_HASH,
            "record_base_literal_offset": SPEAKER_LITERAL_OFFSET,
            "record_base_address": _addr(SPEAKER_BASE),
            "record_stride": SPEAKER_STRIDE,
            "renderer_address": _addr(SPEAKER_RENDERER_OFFSET),
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


def _expected_grammar() -> dict[str, Any]:
    return {
        "fixed_lengths": {
            f"0x{opcode:02X}": length for opcode, length in sorted(FIXED_LENGTHS.items())
        },
        "conditional_layouts": {
            f"0x{opcode:02X}": {"length": size, "pointer_offset": pointer_offset}
            for opcode, (size, pointer_offset) in sorted(CONDITIONAL_LAYOUTS.items())
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


def _derive(rom: bytes) -> tuple[dict[str, Any], bytes]:
    tables, roots = _table_contract(rom)
    nodes, failures = _walk_scripts(rom, roots)
    raw_ranges = [(offset, offset + size) for offset, (_, size) in nodes.items()]
    merged = _coalesce(raw_ranges)
    union_bytes = sum(end - start for start, end in merged)
    raw_bytes = sum(end - start for start, end in raw_ranges)
    range_hash = _sha(json.dumps(merged, separators=(",", ":")).encode("ascii"))
    if range_hash != RANGE_DENOMINATOR_SHA256:
        raise ValueError("range denominator differs from the fixed contract")
    counts = Counter(opcode for opcode, _ in nodes.values())
    byte_counts = Counter()
    for opcode, size in nodes.values():
        byte_counts[opcode] += size
    observed = {
        f"0x{opcode:02X}": {"nodes": counts[opcode], "bytes": byte_counts[opcode]}
        for opcode in sorted(counts)
    }
    summary = {
        "pointer_table_slot_count": TOTAL_TABLE_SLOTS,
        "non_null_script_slots": len(roots),
        "unique_script_roots": len({root for _, _, root in roots}),
        "unique_instruction_nodes": len(nodes),
        "dynamic_opcode_06_nodes": counts[0x06],
        "observed_opcode_count": len(counts),
        "terminal_node_count": counts[0x00],
        "parse_failure_count": len(failures),
        "raw_node_bytes": raw_bytes,
        "node_overlap_bytes": raw_bytes - union_bytes,
        "merged_range_count": len(merged),
        "merged_range_bytes": union_bytes,
        "internal_gap_count": max(0, len(merged) - 1),
        "internal_gap_bytes": sum(
            next_start - end
            for (_, end), (next_start, _) in zip(merged, merged[1:])
        ),
        "packed_script_bytes": union_bytes,
    }
    if summary != EXPECTED_SUMMARY or failures:
        raise ValueError(f"script traversal denominator changed: {summary}; {failures}")

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
        raise ValueError("packed script bundle differs from the fixed contract")
    return {
        "pointer_tables": tables,
        "consumer_evidence": _expected_evidence(rom),
        "grammar": _expected_grammar(),
        "observed_opcodes": observed,
        "referenced_resources": {
            "speaker_labels": _speaker_resource(rom, nodes),
        },
        "range_denominator_sha256": range_hash,
        "summary": summary,
        "ranges": ranges,
    }, bytes(bundle)


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_chapter_script_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_chapter_script_inventory.py").read_bytes()
        ),
    }


def _promotion_manifest(
    implementation: dict[str, str], payload_raw: bytes, bundle: bytes
) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            BUNDLE_NAME: _sha(bundle),
            PAYLOAD_NAME: _sha(payload_raw),
        },
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
            **implementation,
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
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                **EXPECTED_SUMMARY,
                "errors": [],
            },
        },
    }


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    summary = {key: 0 for key in EXPECTED_SUMMARY}
    try:
        root = root.resolve(strict=True)
        artifact = artifact.resolve(strict=True)
        if not artifact.is_dir() or artifact.is_symlink():
            raise ValueError("artifact is not a safe directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact contains a symbolic link")
        actual_files = {
            member.relative_to(artifact).as_posix()
            for member in members
            if member.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError(f"artifact file set mismatch: {sorted(actual_files)}")

        rom = (root / ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        expected, expected_bundle = _derive(rom)
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_raw)
        canonical = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        if payload_raw != canonical:
            raise ValueError("inventory JSON is not canonical")
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        if bundle != expected_bundle or _sha(bundle) != BUNDLE_SHA256:
            raise ValueError("packed script bundle differs from ROM")

        implementation = _implementation(root)
        expected_payload = {
            "schema": SCHEMA,
            "implementation": implementation,
            "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
            **expected,
            "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
            "scope": SCOPE,
            "limitations": LIMITATIONS,
        }
        if payload != expected_payload:
            raise ValueError("inventory claims differ from independent ROM traversal")
        summary = expected["summary"]

        manifest = json.loads((artifact / "manifest.json").read_bytes())
        if manifest != _promotion_manifest(implementation, payload_raw, bundle):
            raise ValueError("promotion manifest bindings changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        **summary,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
