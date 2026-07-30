#!/usr/bin/env python3
"""Independently verify the portrait-palette producer artifact."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
from typing import Any
import zlib


SCHEMA = "portrait-palette-producers-v1"
VERIFY_SCHEMA = "portrait-palette-producers-verification-v1"
PAYLOAD_NAME = "portrait-palette-producers.json"
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INPUT_STATE_SHA256 = "69c1d96d4077b67f1b7594f234191b6f6a0956db53a1f62b4bf4ca635df11805"
UPSTREAM_STATE = Path(
    "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-8.ss9"
)
UPSTREAM_STATE_SHA256 = "62adcd52b577f73ca1ffd6d2d4ec3b9fafa2a2b130ac644a6834e2a56a50d4d8"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GBA_STATE_SIZE = 0x61000
EXPECTED_RAW_SHA256 = {
    "control/audit.json": "1ad5c8dfc65e203586d3e4f189d0cec50b289cadf1403126667256a09bb1da85",
    "control/guard.json": "0341888deedcbe6ee1df81e86dd75dbf3d014faf38423ef4728eb91db6d42c78",
    "control/scratch.bin": "8c87fe73b486bbdf888660f7d15528d7c70e8b1cfbfcf0d5460b4037b6ce17e1",
    "control/startup.json": "abcd26ff4d7160a7c71497e9bd5039d98a2784de6d77f377e655a10cde04025d",
    "control/timeout.png": "ddda820a1d370d51afa603b746adc030c1ca5ca929b7c59045386b5e06110ac2",
    "control/timeout.ss9": "7f9798f7ee69b11d96d78962e40cdf911cfdf37d98943b23141fd18bb4884ec5",
    "control/trace.json": "c6ddff782c4b43a5f363b9bd96a4dba51cdc8b6f0a55342ea6f56b2f874f3d2b",
    "control/writes.json": "9bf17f599949d424e4e7135a3bb7b8050a3c7e51596a518d41ffc0ae1a47aaa2",
    "input/mode0-cursor.ss9": INPUT_STATE_SHA256,
    "positive/audit.json": "6cd235cb1df68721d7551c3ded4b196978174ce8302527eb6b88cb257c8191e9",
    "positive/guard.json": "3963011487d4309e4cad5dd4f63d4c9bdab278dcd547ea3724eebc8564e2bab6",
    "positive/hit.png": "d174a6a96b061763ef1d1d7613f02731efdcaaddf3b8675fc8843da3e789ed2f",
    "positive/hit.ss9": "87ab930f3f012f792d2abd4968676d034b44112b3c56ff2ed8c8c2dfe86cfc6f",
    "positive/portrait-state.bin": (
        "9e3da62abda6b92f66eae6ee87482efdba4a8e7f32bfbe59a31ded672462c7b7"
    ),
    "positive/scratch.bin": "4dc290d7b33dd76b5b123533b0c3959b86fee8ea95f7b4863385be109743d084",
    "positive/startup.json": "b087ec6a1c5478f4478faabf3ad4eaa19b37c20779c346eb721f497bf3aeb8bb",
    "positive/trace.json": "480b96993199c1a2b2dcafbf1f190cf15bd1d87ce05d0d0862a0342b6136baff",
    "positive/writes.json": "5f8fcd17ad0f57804f5c691782372692d9057a97941c0939e6ba0241cb00753d",
}
TRACE_FIELDS = (
    "name",
    "address",
    "frame",
    "pc",
    "lr",
    "r0",
    "r1",
    "r2",
    "r4",
    "r7",
    "scratch_first",
    "scratch_second",
)
EXPECTED_TRACE_CHAIN = [
    {
        "name": "chapter_opcode_17",
        "address": "0x08097966",
        "frame": 2,
        "pc": "0x08097968",
        "lr": "0x0809B273",
        "r0": "0x08097966",
        "r1": "0x080977F4",
        "r2": "0x000000FF",
        "r4": "0x00000002",
        "r7": "0x08032724",
        "scratch_first": 0,
        "scratch_second": 1024,
    },
    {
        "name": "portrait_transition_helper",
        "address": "0x08096B74",
        "frame": 2,
        "pc": "0x08096B76",
        "lr": "0x08097971",
        "r0": "0x00000000",
        "r1": "0x00000000",
        "r2": "0x00000001",
        "r4": "0x00000002",
        "r7": "0x08032724",
        "scratch_first": 0,
        "scratch_second": 1024,
    },
    {
        "name": "portrait_mode_dispatch",
        "address": "0x08096B9C",
        "frame": 2,
        "pc": "0x08096B9E",
        "lr": "0x08097971",
        "r0": "0x03005E50",
        "r1": "0x03005E50",
        "r2": "0x01000000",
        "r4": "0x03005930",
        "r7": "0x00000000",
        "scratch_first": 0,
        "scratch_second": 1024,
    },
    {
        "name": "palette_fill_mode_0",
        "address": "0x08096BD4",
        "frame": 2,
        "pc": "0x08096BD6",
        "lr": "0x08097971",
        "r0": "0x08096BD4",
        "r1": "0x08096BB0",
        "r2": "0x01000000",
        "r4": "0x03005930",
        "r7": "0x00000000",
        "scratch_first": 0,
        "scratch_second": 1024,
    },
    {
        "name": "palette_fill_cpuset_wrapper",
        "address": "0x0809C0E0",
        "frame": 2,
        "pc": "0x0809C0E2",
        "lr": "0x08096BE5",
        "r0": "0x030011E0",
        "r1": "0x02002882",
        "r2": "0x0100003F",
        "r4": "0x03005930",
        "r7": "0x00000000",
        "scratch_first": 0,
        "scratch_second": 1024,
    },
    {
        "name": "palette_fill_mode_0_complete",
        "address": "0x08096BE4",
        "frame": 2,
        "pc": "0x08096BE6",
        "lr": "0x08096BE5",
        "r0": "0x030011E0",
        "r1": "0x02002882",
        "r2": "0x0100003F",
        "r4": "0x03005930",
        "r7": "0x00000000",
        "scratch_first": 0,
        "scratch_second": 31,
    },
]

PRIMARY_TABLE = 0x08060C74
ALTERNATE_TABLE = 0x08060D54
CHAPTER_ENTRY_COUNT = 56
SJIS_RANGE_TABLE = 0x0853D644
SJIS_RANGE_COUNT = 31

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

JUMP_TABLE = [
    {"mode": 0, "target": "0x08096BD4"},
    {"mode": 1, "target": "0x08096BF8"},
    {"mode": 2, "target": "0x08096C22"},
    {"mode": 3, "target": "0x08096C56"},
    {"mode": 4, "target": "0x08096C9C"},
    {"mode": 5, "target": "0x08096C9C"},
    {"mode": 6, "target": "0x08096CA8"},
    {"mode": 7, "target": "0x08096CBC"},
    {"mode": 8, "target": "0x08096CCC"},
]
STATIC_SEMANTICS = {
    "source": "u16 stack constant 0x001F",
    "destination": "0x02002882",
    "cpuset_control": "0x0100003F",
    "operation": "fixed-source fill of 63 halfwords",
    "preserved_entry": "0x02002880..0x02002881",
    "next_state": "0x40",
    "tick_reset": 0,
}
QUEUE_SEMANTICS = {
    "source": "0x02002880",
    "destination": "0x05000200 + palette_bank * 32",
    "size_bytes": 128,
    "enqueue_callsite": "0x08096536",
    "enqueue_helper": "0x080635B8",
    "trigger": "state 0x40 and tick % 8 == 0",
}
DIM_TRANSFORM = {
    "helper": "0x08096D4C",
    "callsite": "0x08096E3A",
    "enqueue_callsite": "0x08096E44",
    "source_destination": "0x02002880 in place",
    "color_count": 64,
    "formula": "((color & 0x7BDE) >> 1) + ((color & 0x739C) >> 2)",
}
SCOPE = {
    "chapter_opcode_17_mode_denominator_complete": True,
    "mode_0_fill_static_complete": True,
    "mode_0_fill_runtime_complete": True,
    "mode_0_zero_input_control_complete": True,
    "dim_transform_static_complete": True,
    "dim_transform_runtime_complete": False,
    "all_scratch_02002880_producers_complete": False,
    "all_portrait_palette_runtime_paths_complete": False,
    "generic_palette_writeback_complete": False,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _offset(address: int, rom: bytes) -> int:
    value = address - ROM_BASE
    if not 0 <= value < len(rom):
        raise ValueError(f"address outside ROM: {_address(address)}")
    return value


def _bytes(rom: bytes, address: int, length: int) -> bytes:
    start = _offset(address, rom)
    data = rom[start : start + length]
    if len(data) != length:
        raise ValueError(f"truncated ROM at {_address(address)}")
    return data


def _u8(rom: bytes, address: int) -> int:
    return rom[_offset(address, rom)]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack("<H", _bytes(rom, address, 2))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack("<I", _bytes(rom, address, 4))[0]


def _require_pointer(rom: bytes, address: int) -> int:
    value = _u32(rom, address)
    _offset(value, rom)
    return value


def _sjis_pair_valid(rom: bytes, lead: int, trail: int) -> bool:
    code = (lead << 8) | trail
    for index in range(SJIS_RANGE_COUNT):
        raw = _bytes(rom, SJIS_RANGE_TABLE + index * 8, 3)
        lower = int.from_bytes(raw[:2], "little")
        if lower <= code < lower + raw[2]:
            return True
    return False


def _renderer_text_end(rom: bytes, address: int) -> int:
    cursor = address
    for _ in range(len(rom)):
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
        _bytes(rom, cursor, width)
        cursor += width
    raise ValueError("unterminated renderer text")


def _token_text_end(rom: bytes, address: int) -> int:
    cursor = address
    for _ in range(len(rom)):
        value = _u8(rom, cursor)
        if value == 0:
            return cursor + 1
        width = 2 if value == 1 or 0x80 <= value <= 0x9F else 3 if value == 2 else 1
        _bytes(rom, cursor, width)
        cursor += width
    raise ValueError("unterminated token text")


def _decode_node(rom: bytes, address: int) -> tuple[int, list[int]]:
    opcode = _u8(rom, address)
    if opcode == 0:
        return opcode, []
    if opcode in FIXED_LENGTHS:
        length = FIXED_LENGTHS[opcode]
        _bytes(rom, address, length)
        return opcode, [address + length]
    if opcode == 0x01:
        return opcode, [_renderer_text_end(rom, address + 1)]
    if opcode in (0x05, 0x20):
        return opcode, [_renderer_text_end(rom, address + 2)]
    if opcode == 0x06:
        return opcode, [_require_pointer(rom, address + 1), _require_pointer(rom, address + 5)]
    if opcode == 0x07:
        return opcode, [_require_pointer(rom, address + 1)]
    if opcode in CONDITIONAL_LAYOUTS:
        length, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, [_require_pointer(rom, address + pointer_offset), address + length]
    if opcode == 0x0D:
        return opcode, [_require_pointer(rom, address + 1), address + 5]
    if opcode == 0x13:
        first_end = _token_text_end(rom, address + 4)
        if _u8(rom, address + 2) == 0:
            return opcode, [first_end]
        return opcode, [_token_text_end(rom, first_end + 1)]
    if opcode == 0x32:
        cursor = address
        targets = []
        while _u8(rom, cursor) == 0x32:
            targets.append(_require_pointer(rom, cursor + 1))
            cursor += 5
        targets.append(cursor)
        return opcode, targets
    raise ValueError(f"unsupported opcode 0x{opcode:02X} at {_address(address)}")


def _chapter_denominator(rom: bytes) -> dict[str, Any]:
    roots = []
    for table, address in (("primary", PRIMARY_TABLE), ("alternate", ALTERNATE_TABLE)):
        if _u32(rom, address) != 0:
            raise ValueError(f"{table} sentinel is not null")
        for scenario_id in range(1, CHAPTER_ENTRY_COUNT):
            roots.append((table, scenario_id, _require_pointer(rom, address + scenario_id * 4)))
    global_nodes: dict[int, int] = {}
    hits: dict[int, set[tuple[str, int]]] = defaultdict(set)
    failures = []
    for table, scenario_id, root in roots:
        pending = [root]
        visited = set()
        try:
            while pending:
                address = pending.pop()
                if address in visited:
                    continue
                visited.add(address)
                opcode, edges = _decode_node(rom, address)
                previous = global_nodes.setdefault(address, opcode)
                if previous != opcode:
                    raise ValueError("opcode instability")
                if opcode == 0x17:
                    hits[address].add((table, scenario_id))
                pending.extend(edge for edge in edges if edge not in visited)
        except ValueError as error:
            failures.append(
                {
                    "table": table,
                    "scenario_id": scenario_id,
                    "root": _address(root),
                    "error": str(error),
                }
            )
    records = []
    for address, references in sorted(hits.items()):
        raw = _bytes(rom, address, 4)
        records.append(
            {
                "address": _address(address),
                "raw_hex": raw.hex(),
                "slot": raw[1],
                "mode": raw[2],
                "argument": raw[3],
                "roots": [
                    {"table": table, "scenario_id": scenario_id}
                    for table, scenario_id in sorted(references)
                ],
            }
        )
    counts = Counter(row["mode"] for row in records)
    return {
        "pointer_tables": {
            "primary": "0x08060C74",
            "alternate": "0x08060D54",
            "entry_count_each": 56,
            "entry_zero": "null sentinel",
        },
        "selection_rule": (
            "walk every reachable node from both 55-entry non-null chapter "
            "tables, following every statically enumerable control-flow edge"
        ),
        "record_layout": {
            "opcode": "0x17",
            "length": 4,
            "slot": "u8 +1",
            "mode": "u8 +2",
            "argument": "u8 +3",
            "handler": "0x08097966",
        },
        "summary": {
            "non_null_script_slots": len(roots),
            "unique_script_roots": len({root for _, _, root in roots}),
            "unique_instruction_nodes": len(global_nodes),
            "unique_opcode_17_records": len(records),
            "opcode_17_root_references": sum(len(row["roots"]) for row in records),
            "mode_counts": {str(mode): counts[mode] for mode in range(9)},
            "parse_failures": failures,
        },
        "records": records,
    }


def _slice(rom: bytes, start: int, end: int) -> dict[str, Any]:
    data = _bytes(rom, start, end - start)
    return {
        "start": _address(start),
        "end_exclusive": _address(end),
        "size": len(data),
        "sha256": _sha256(data),
    }


def _decode_bl(rom: bytes, address: int) -> int | None:
    first, second = _u16(rom, address), _u16(rom, address + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def _savestate_data(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("savestate is not PNG")
    cursor = len(PNG_SIGNATURE)
    payloads = []
    saw_iend = False
    while cursor < len(data):
        length = struct.unpack_from(">I", data, cursor)[0]
        tag = data[cursor + 4 : cursor + 8]
        payload = data[cursor + 8 : cursor + 8 + length]
        crc = struct.unpack_from(">I", data, cursor + 8 + length)[0]
        if zlib.crc32(tag + payload) & 0xFFFFFFFF != crc:
            raise ValueError("savestate PNG CRC mismatch")
        if tag == b"gbAs":
            payloads.append(payload)
        cursor += 12 + length
        if tag == b"IEND":
            saw_iend = True
            break
    if not saw_iend or cursor != len(data) or len(payloads) != 1:
        raise ValueError("invalid savestate PNG chunks")
    state = zlib.decompress(payloads[0])
    if len(state) != GBA_STATE_SIZE:
        raise ValueError("invalid savestate payload size")
    return state


def _read_state_memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x00400, 0x00400),
        (0x05000000, 0x00400, 0x00800),
        (0x07000000, 0x00400, 0x00C00),
        (0x06000000, 0x18000, 0x01000),
        (0x03000000, 0x08000, 0x19000),
        (0x02000000, 0x40000, 0x21000),
    )
    for base, length, state_offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[state_offset + relative : state_offset + relative + size]
    raise ValueError("unsupported savestate memory read")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_runtime(root: Path, artifact: Path, payload: dict[str, Any], errors: list[str]) -> None:
    try:
        raw = artifact / "raw"
        actual_raw_hashes = {
            relative: _sha256((raw / relative).read_bytes())
            for relative in sorted(EXPECTED_RAW_SHA256)
        }
        if actual_raw_hashes != EXPECTED_RAW_SHA256:
            errors.append("accepted raw capture hashes mismatch")
        fixture = raw / "input/mode0-cursor.ss9"
        if _sha256(fixture.read_bytes()) != INPUT_STATE_SHA256:
            errors.append("fixture hash mismatch")
        upstream = root / UPSTREAM_STATE
        if _sha256(upstream.read_bytes()) != UPSTREAM_STATE_SHA256:
            errors.append("upstream state hash mismatch")
        source_state = _savestate_data(upstream)
        fixture_state = _savestate_data(fixture)
        if _read_state_memory(source_state, 0x030011F0, 4) != bytes.fromhex("311f0308"):
            errors.append("upstream cursor mismatch")
        if _read_state_memory(fixture_state, 0x030011F0, 4) != bytes.fromhex("24270308"):
            errors.append("fixture cursor mismatch")
        diffs = [
            {"state_offset": index, "before": before, "after": after}
            for index, (before, after) in enumerate(zip(source_state, fixture_state))
            if before != after
        ]
        expected_diffs = [
            {"state_offset": 106992, "before": 49, "after": 36},
            {"state_offset": 106993, "before": 31, "after": 39},
        ]
        if diffs != expected_diffs:
            errors.append("fixture state diff mismatch")

        control = _load_json(raw / "control/audit.json")
        control_writes = _load_json(raw / "control/writes.json")["events"]
        control_trace = _load_json(raw / "control/trace.json")["events"]
        if not (
            control["rom_sha256"] == ROM_SHA256
            and control["input_state_sha256"] == INPUT_STATE_SHA256
            and control["inputs"] == []
            and control["success"] is False
            and control["outcome"] == "timeout"
            and control["frames"] == 240
            and control["write_event_count"] == 0
            and control_writes == []
            and control_trace == []
        ):
            errors.append("control runtime evidence mismatch")

        positive = _load_json(raw / "positive/audit.json")
        writes = _load_json(raw / "positive/writes.json")["events"]
        trace = _load_json(raw / "positive/trace.json")["events"]
        required_prefix = [
            "chapter_opcode_17",
            "portrait_transition_helper",
            "portrait_mode_dispatch",
            "palette_fill_mode_0",
            "palette_fill_cpuset_wrapper",
            "palette_fill_mode_0_complete",
        ]
        trace_chain = [
            {field: row[field] for field in TRACE_FIELDS}
            for row in trace[: len(EXPECTED_TRACE_CHAIN)]
        ]
        expected_addresses = [
            f"0x{address:08X}" for address in range(0x02002882, 0x02002900, 2)
        ]
        if not (
            positive["rom_sha256"] == ROM_SHA256
            and positive["input_state_sha256"] == INPUT_STATE_SHA256
            and positive["inputs"]
            == [{"key": "A", "down_frame": 2, "up_frame": 10, "hold_frames": 8}]
            and positive["success"] is True
            and positive["arguments_match"] is True
            and positive["callsite"] == "0x08096536"
            and positive["frame"] == 9
            and positive["lr"] == "0x0809653B"
            and positive["r0"] == "0x02002880"
            and positive["r1"] == "0x05000200"
            and positive["r2"] == "0x00000080"
            and positive["state"] == 64
            and positive["palette_bank"] == 0
            and positive["tick"] == 8
            and positive["write_event_count"] == 63
            and [row["address"] for row in writes] == expected_addresses
            and [(row["new_value"], row["width"]) for row in writes] == [(31, 2)] * 63
            and trace_chain == EXPECTED_TRACE_CHAIN
        ):
            errors.append("positive runtime evidence mismatch")
        scratch = (raw / "positive/scratch.bin").read_bytes()
        colors = struct.unpack("<64H", scratch) if len(scratch) == 128 else ()
        if colors != (0,) + (0x001F,) * 63:
            errors.append("positive scratch mismatch")
        state = (raw / "positive/portrait-state.bin").read_bytes()
        if len(state) != 16 or state[0] != 0x40 or int.from_bytes(state[8:10], "little") != 8:
            errors.append("positive portrait state mismatch")
        control_checkpoint = _savestate_data(raw / "control/timeout.ss9")
        positive_checkpoint = _savestate_data(raw / "positive/hit.ss9")
        control_scratch = (raw / "control/scratch.bin").read_bytes()
        positive_registers = struct.unpack_from("<16I", positive_checkpoint, 0x20)
        control_registers = struct.unpack_from("<16I", control_checkpoint, 0x20)
        if _read_state_memory(control_checkpoint, 0x02002880, 128) != control_scratch:
            errors.append("control checkpoint scratch mismatch")
        if _read_state_memory(positive_checkpoint, 0x02002880, 128) != scratch:
            errors.append("positive checkpoint scratch mismatch")
        if _read_state_memory(positive_checkpoint, 0x03005930, 16) != state:
            errors.append("positive checkpoint portrait state mismatch")
        if (positive_registers[15], positive_registers[14]) != (
            0x080635BA,
            0x0809653B,
        ):
            errors.append("positive checkpoint PC/LR mismatch")

        runtime = payload["mode_0_fill"]["runtime"]
        if runtime.get("raw_sha256") != dict(sorted(EXPECTED_RAW_SHA256.items())):
            errors.append("raw capture hash payload mismatch")
        if runtime["fixture"]["container_state_byte_diff"] != expected_diffs:
            errors.append("fixture payload mismatch")
        if runtime["control"]["audit"] != control:
            errors.append("control audit payload mismatch")
        if runtime["positive"]["audit"] != positive:
            errors.append("positive audit payload mismatch")
        if runtime["positive"]["required_trace_prefix"] != required_prefix:
            errors.append("trace prefix payload mismatch")
        histogram = {
            f"0x{value:04X}": count for value, count in sorted(Counter(colors).items())
        }
        if runtime["positive"]["scratch_halfword_histogram"] != histogram:
            errors.append("scratch histogram payload mismatch")
        if (
            runtime["control"].get("checkpoint_sha256")
            != EXPECTED_RAW_SHA256["control/timeout.ss9"]
            or runtime["control"].get("screenshot_sha256")
            != EXPECTED_RAW_SHA256["control/timeout.png"]
            or runtime["control"].get("terminal_pc") != _address(control_registers[15])
            or runtime["control"].get("terminal_lr") != _address(control_registers[14])
        ):
            errors.append("control terminal payload mismatch")
        if (
            runtime["positive"].get("checkpoint_sha256")
            != EXPECTED_RAW_SHA256["positive/hit.ss9"]
            or runtime["positive"].get("screenshot_sha256")
            != EXPECTED_RAW_SHA256["positive/hit.png"]
            or runtime["positive"].get("terminal_pc") != _address(positive_registers[15])
            or runtime["positive"].get("terminal_lr") != _address(positive_registers[14])
        ):
            errors.append("positive terminal payload mismatch")
        for kind in ("control", "positive"):
            guard = _load_json(raw / kind / "guard.json")
            summary = {
                key: guard[key]
                for key in (
                    "reason",
                    "exit_code",
                    "completion_trigger",
                    "protection_backend",
                    "degraded",
                    "peak_tree_rss_mib",
                )
            }
            if (
                summary["reason"] != "completed"
                or summary["exit_code"] != 0
                or summary["completion_trigger"] != "success-marker"
                or summary["degraded"] is not False
                or summary["peak_tree_rss_mib"] > 512
                or runtime[kind]["guard"] != summary
            ):
                errors.append(f"{kind} guard payload mismatch")
    except (KeyError, ValueError, OSError, struct.error, zlib.error) as error:
        errors.append(f"runtime verification failed: {error}")


def _expected_manifest(
    payload: dict[str, Any], files: dict[str, str]
) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": dict(sorted(files.items())),
        "scope": SCOPE,
        "source": {
            "rom_sha256": ROM_SHA256,
            "input_state_sha256": INPUT_STATE_SHA256,
            "upstream_checkpoint": {
                "path": UPSTREAM_STATE.as_posix(),
                "sha256": UPSTREAM_STATE_SHA256,
            },
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_portrait_palette_producers.py",
                "--root",
                ".",
                "--raw-root",
                f"artifacts/{SCHEMA}/raw",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_portrait_palette_producers.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "opcode_17_records": 161,
            },
        },
    }


def verify_artifact(root: Path | str, artifact: Path | str) -> dict[str, Any]:
    root = Path(root)
    artifact = Path(artifact)
    errors: list[str] = []
    try:
        manifest = _load_json(artifact / "manifest.json")
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_status") != "accepted"
        ):
            errors.append("manifest contract mismatch")
        files = {
            path.relative_to(artifact).as_posix(): _sha256(path.read_bytes())
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        expected_files = {PAYLOAD_NAME} | {
            f"raw/{relative}" for relative in EXPECTED_RAW_SHA256
        }
        if set(files) != expected_files:
            errors.append("artifact file set mismatch")
        if manifest.get("files") != dict(sorted(files.items())):
            errors.append("manifest file hashes mismatch")

        payload_path = artifact / PAYLOAD_NAME
        payload = _load_json(payload_path)
        if payload_path.read_bytes() != _json_bytes(payload):
            errors.append("payload JSON is not canonical")
        if payload.get("schema") != SCHEMA:
            errors.append("payload schema mismatch")

        rom = (root / "rom/base.gba").read_bytes()
        if _sha256(rom) != ROM_SHA256:
            errors.append("ROM hash mismatch")
        chapter = _chapter_denominator(rom)
        if payload.get("chapter_denominator") != chapter:
            errors.append("chapter denominator mismatch")
        if payload.get("transition_dispatch") != {
            "entry": "0x08096B74",
            "mode_dispatch": "0x08096B9C",
            "jump_table_address": "0x08096BB0",
            "jump_table": JUMP_TABLE,
        }:
            errors.append("transition dispatch mismatch")
        if [_u32(rom, 0x08096BB0 + mode * 4) for mode in range(9)] != [
            int(row["target"], 16) for row in JUMP_TABLE
        ]:
            errors.append("ROM jump table mismatch")
        if payload["mode_0_fill"].get("static_semantics") != STATIC_SEMANTICS:
            errors.append("mode-0 static semantics mismatch")
        if payload["mode_0_fill"].get("queue_semantics") != QUEUE_SEMANTICS:
            errors.append("mode-0 queue semantics mismatch")
        if payload.get("dim_transform") != DIM_TRANSFORM:
            errors.append("dim transform mismatch")
        if payload.get("scope") != SCOPE:
            errors.append("scope mismatch")
        if _u32(rom, 0x08096BF0) != 0x02002882 or _u32(rom, 0x08096BF4) != 0x0100003F:
            errors.append("mode-0 ROM literals mismatch")
        if (
            _decode_bl(rom, 0x08096BE0) != 0x0809C0E0
            or _decode_bl(rom, 0x08096536) != 0x080635B8
            or _decode_bl(rom, 0x08096E3A) != 0x08096D4C
            or _decode_bl(rom, 0x08096E44) != 0x080635B8
        ):
            errors.append("static call chain mismatch")
        expected_slices = {
            "opcode_17_handler": _slice(rom, 0x08097966, 0x08097974),
            "transition_dispatch": _slice(rom, 0x08096B74, 0x08096D00),
            "state_0x40_handler": _slice(rom, 0x0809651C, 0x08096542),
            "dim_transform_and_route": _slice(rom, 0x08096D4C, 0x08096E64),
        }
        if payload.get("static_evidence") != expected_slices:
            errors.append("static ROM evidence mismatch")
        for name, relative in {
            "exporter_sha256": "tools/export_portrait_palette_producers.py",
            "verifier_sha256": "tools/verify_portrait_palette_producers.py",
            "test_sha256": "tests/test_export_portrait_palette_producers.py",
            "probe_sha256": "tools/mgba_palette_producer_probe.lua",
            "probe_test_sha256": "tests/test_mgba_palette_producer_probe_script.py",
        }.items():
            if payload["implementation"].get(name) != _sha256((root / relative).read_bytes()):
                errors.append(f"implementation hash mismatch: {name}")
        _check_runtime(root, artifact, payload, errors)
        expected_manifest = _expected_manifest(payload, files)
        if manifest != expected_manifest:
            errors.append("promotion manifest mismatch")
    except (KeyError, ValueError, OSError, json.JSONDecodeError, struct.error) as error:
        errors.append(f"artifact verification failed: {error}")
        payload = {}
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "opcode_17_records": (
            payload.get("chapter_denominator", {})
            .get("summary", {})
            .get("unique_opcode_17_records")
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    result = verify_artifact(args.root, args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
