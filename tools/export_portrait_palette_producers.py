#!/usr/bin/env python3
"""Export the chapter portrait-palette transition denominator and runtime proof."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid

try:
    from tools.export_bg_scene_selection import (
        _bytes,
        _chapter_roots,
        _decode_node,
        _u8,
    )
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from export_bg_scene_selection import _bytes, _chapter_roots, _decode_node, _u8
    from inspect_mgba_savestate import load_gba_state


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
MGBA_SOURCE_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
MGBA_BINARY_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"

RAW_FILES = (
    "input/mode0-cursor.ss9",
    "control/audit.json",
    "control/startup.json",
    "control/writes.json",
    "control/trace.json",
    "control/scratch.bin",
    "control/timeout.ss9",
    "control/timeout.png",
    "control/guard.json",
    "positive/audit.json",
    "positive/startup.json",
    "positive/writes.json",
    "positive/trace.json",
    "positive/scratch.bin",
    "positive/portrait-state.bin",
    "positive/hit.ss9",
    "positive/hit.png",
    "positive/guard.json",
)
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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def _slice(rom: bytes, start: int, end: int) -> dict[str, Any]:
    data = rom[start - ROM_BASE : end - ROM_BASE]
    if len(data) != end - start:
        raise ValueError(f"truncated ROM slice {_address(start)}..{_address(end)}")
    return {
        "start": _address(start),
        "end_exclusive": _address(end),
        "size": len(data),
        "sha256": _sha256(data),
    }


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, address - ROM_BASE)[0]


def _decode_bl(rom: bytes, address: int) -> int | None:
    first = _u16(rom, address)
    second = _u16(rom, address + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return address + 4 + displacement


def _chapter_denominator(rom: bytes) -> dict[str, Any]:
    roots = _chapter_roots(rom)
    global_nodes: dict[int, int] = {}
    hit_roots: dict[int, set[tuple[str, int]]] = defaultdict(set)
    failures: list[dict[str, Any]] = []
    for table, scenario_id, root in roots:
        pending = [root]
        visited: set[int] = set()
        try:
            while pending:
                address = pending.pop()
                if address in visited:
                    continue
                visited.add(address)
                opcode, edges, _ = _decode_node(rom, address)
                previous = global_nodes.setdefault(address, opcode)
                if previous != opcode:
                    raise ValueError(f"opcode instability at {_address(address)}")
                if opcode == 0x17:
                    hit_roots[address].add((table, scenario_id))
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
    for address, references in sorted(hit_roots.items()):
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
    mode_counts = Counter(row["mode"] for row in records)
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
            "mode_counts": {str(mode): mode_counts[mode] for mode in range(9)},
            "parse_failures": failures,
        },
        "records": records,
    }


def _validate_static_code(rom: bytes) -> dict[str, Any]:
    actual_targets = [_u32(rom, 0x08096BB0 + mode * 4) for mode in range(9)]
    _require(
        actual_targets,
        [int(row["target"], 16) for row in JUMP_TABLE],
        "portrait transition jump table",
    )
    for address, expected in (
        (0x08096BD4, 0x4669),
        (0x08096BD6, 0x201F),
        (0x08096BD8, 0x8008),
        (0x08096BDA, 0x4905),
        (0x08096BDC, 0x4A05),
        (0x08096BDE, 0x4668),
        (0x08096BE0, 0xF005),
        (0x08096BE2, 0xFA7E),
        (0x08096BE4, 0x2100),
        (0x08096BE6, 0x2040),
        (0x08096BE8, 0x7020),
        (0x08096BEA, 0x8121),
    ):
        _require(_u16(rom, address), expected, f"instruction at {_address(address)}")
    _require(_u32(rom, 0x08096BF0), 0x02002882, "mode-0 fill destination")
    _require(_u32(rom, 0x08096BF4), 0x0100003F, "mode-0 CpuSet control")
    _require(_decode_bl(rom, 0x08096BE0), 0x0809C0E0, "mode-0 CpuSet wrapper")
    _require(_decode_bl(rom, 0x08096536), 0x080635B8, "mode-0 enqueue")
    _require(_u32(rom, 0x0809653C), 0x02002880, "mode-0 scratch source")
    _require(_decode_bl(rom, 0x08096E3A), 0x08096D4C, "dim transform")
    _require(_decode_bl(rom, 0x08096E44), 0x080635B8, "dim enqueue")
    return {
        "opcode_17_handler": _slice(rom, 0x08097966, 0x08097974),
        "transition_dispatch": _slice(rom, 0x08096B74, 0x08096D00),
        "state_0x40_handler": _slice(rom, 0x0809651C, 0x08096542),
        "dim_transform_and_route": _slice(rom, 0x08096D4C, 0x08096E64),
    }


def _guard_summary(raw_root: Path, kind: str) -> dict[str, Any]:
    guard = _load_json(raw_root / kind / "guard.json")
    _require(guard.get("reason"), "completed", f"{kind} guard reason")
    _require(guard.get("exit_code"), 0, f"{kind} guard exit")
    _require(
        guard.get("completion_trigger"), "success-marker", f"{kind} completion trigger"
    )
    _require(guard.get("degraded"), False, f"{kind} degraded")
    peak = guard.get("peak_tree_rss_mib")
    if not isinstance(peak, (int, float)) or peak > 512:
        raise ValueError(f"{kind} guard peak RSS is invalid: {peak!r}")
    return {
        "reason": guard["reason"],
        "exit_code": guard["exit_code"],
        "completion_trigger": guard["completion_trigger"],
        "protection_backend": guard["protection_backend"],
        "degraded": guard["degraded"],
        "peak_tree_rss_mib": peak,
    }


def _validate_runtime(root: Path, raw_root: Path) -> dict[str, Any]:
    input_path = raw_root / "input/mode0-cursor.ss9"
    _require(_sha256(input_path.read_bytes()), INPUT_STATE_SHA256, "input state hash")
    upstream = root / UPSTREAM_STATE
    _require(_sha256(upstream.read_bytes()), UPSTREAM_STATE_SHA256, "upstream state hash")
    original_state = load_gba_state(upstream)
    fixture_state = load_gba_state(input_path)
    original_cursor = original_state.read_memory(0x030011F0, 4)
    fixture_cursor = fixture_state.read_memory(0x030011F0, 4)
    _require(original_cursor, bytes.fromhex("311f0308"), "upstream cursor")
    _require(fixture_cursor, bytes.fromhex("24270308"), "fixture cursor")
    changed = []
    original_payload = original_state.data
    fixture_payload = fixture_state.data
    for index, (before, after) in enumerate(zip(original_payload, fixture_payload)):
        if before != after:
            changed.append({"state_offset": index, "before": before, "after": after})
    _require(
        changed,
        [
            {"state_offset": 106992, "before": 49, "after": 36},
            {"state_offset": 106993, "before": 31, "after": 39},
        ],
        "fixture byte diff",
    )

    control_audit = _load_json(raw_root / "control/audit.json")
    control_writes = _load_json(raw_root / "control/writes.json")["events"]
    control_trace = _load_json(raw_root / "control/trace.json")["events"]
    _require(control_audit["rom_sha256"], ROM_SHA256, "control ROM hash")
    _require(control_audit["input_state_sha256"], INPUT_STATE_SHA256, "control state hash")
    _require(control_audit["inputs"], [], "control inputs")
    _require(control_audit["success"], False, "control success")
    _require(control_audit["outcome"], "timeout", "control outcome")
    _require(control_audit["frames"], 240, "control frames")
    _require(control_audit["write_event_count"], 0, "control write count")
    _require(control_writes, [], "control writes")
    _require(control_trace, [], "control trace")

    positive_audit = _load_json(raw_root / "positive/audit.json")
    positive_writes = _load_json(raw_root / "positive/writes.json")["events"]
    positive_trace = _load_json(raw_root / "positive/trace.json")["events"]
    _require(positive_audit["rom_sha256"], ROM_SHA256, "positive ROM hash")
    _require(positive_audit["input_state_sha256"], INPUT_STATE_SHA256, "positive state hash")
    _require(
        positive_audit["inputs"],
        [{"key": "A", "down_frame": 2, "up_frame": 10, "hold_frames": 8}],
        "positive inputs",
    )
    for field, expected in {
        "success": True,
        "arguments_match": True,
        "callsite": "0x08096536",
        "frame": 9,
        "lr": "0x0809653B",
        "r0": "0x02002880",
        "r1": "0x05000200",
        "r2": "0x00000080",
        "state": 64,
        "palette_bank": 0,
        "tick": 8,
        "write_event_count": 63,
    }.items():
        _require(positive_audit[field], expected, f"positive audit {field}")
    expected_addresses = [f"0x{address:08X}" for address in range(0x02002882, 0x02002900, 2)]
    _require(
        [row["address"] for row in positive_writes],
        expected_addresses,
        "positive write addresses",
    )
    _require(
        [(row["new_value"], row["width"]) for row in positive_writes],
        [(31, 2)] * 63,
        "positive write values",
    )
    required_trace_prefix = [
        "chapter_opcode_17",
        "portrait_transition_helper",
        "portrait_mode_dispatch",
        "palette_fill_mode_0",
        "palette_fill_cpuset_wrapper",
        "palette_fill_mode_0_complete",
    ]
    _require(
        [
            {field: row[field] for field in TRACE_FIELDS}
            for row in positive_trace[: len(EXPECTED_TRACE_CHAIN)]
        ],
        EXPECTED_TRACE_CHAIN,
        "positive trace chain",
    )
    scratch = (raw_root / "positive/scratch.bin").read_bytes()
    _require(len(scratch), 128, "positive scratch size")
    colors = struct.unpack("<64H", scratch)
    _require(colors, (0,) + (0x001F,) * 63, "positive scratch colors")
    state = (raw_root / "positive/portrait-state.bin").read_bytes()
    _require(len(state), 16, "positive portrait state size")
    _require(state[0], 0x40, "positive portrait state")
    _require(int.from_bytes(state[8:10], "little"), 8, "positive portrait tick")
    control_checkpoint = load_gba_state(raw_root / "control/timeout.ss9")
    positive_checkpoint = load_gba_state(raw_root / "positive/hit.ss9")
    control_scratch = (raw_root / "control/scratch.bin").read_bytes()
    _require(
        control_checkpoint.read_memory(0x02002880, 128),
        control_scratch,
        "control checkpoint scratch",
    )
    _require(
        positive_checkpoint.read_memory(0x02002880, 128),
        scratch,
        "positive checkpoint scratch",
    )
    _require(
        positive_checkpoint.read_memory(0x03005930, 16),
        state,
        "positive checkpoint portrait state",
    )
    _require(
        (positive_checkpoint.registers[15], positive_checkpoint.registers[14]),
        (0x080635BA, 0x0809653B),
        "positive checkpoint PC/LR",
    )

    return {
        "raw_sha256": dict(sorted(EXPECTED_RAW_SHA256.items())),
        "fixture": {
            "path": "raw/input/mode0-cursor.ss9",
            "sha256": INPUT_STATE_SHA256,
            "derived_from": UPSTREAM_STATE.as_posix(),
            "derived_from_sha256": UPSTREAM_STATE_SHA256,
            "memory_patch": {
                "address": "0x030011F0",
                "before_hex": original_cursor.hex(),
                "after_hex": fixture_cursor.hex(),
                "target_script_node": "0x08032724",
            },
            "container_state_byte_diff": changed,
        },
        "control": {
            "audit": control_audit,
            "guard": _guard_summary(raw_root, "control"),
            "writes_sha256": _sha256((raw_root / "control/writes.json").read_bytes()),
            "trace_sha256": _sha256((raw_root / "control/trace.json").read_bytes()),
            "checkpoint": "raw/control/timeout.ss9",
            "checkpoint_sha256": EXPECTED_RAW_SHA256["control/timeout.ss9"],
            "screenshot": "raw/control/timeout.png",
            "screenshot_sha256": EXPECTED_RAW_SHA256["control/timeout.png"],
            "terminal_pc": _address(control_checkpoint.registers[15]),
            "terminal_lr": _address(control_checkpoint.registers[14]),
        },
        "positive": {
            "audit": positive_audit,
            "guard": _guard_summary(raw_root, "positive"),
            "required_trace_prefix": required_trace_prefix,
            "scratch_halfword_histogram": {
                f"0x{value:04X}": count for value, count in sorted(Counter(colors).items())
            },
            "writes_sha256": _sha256((raw_root / "positive/writes.json").read_bytes()),
            "trace_sha256": _sha256((raw_root / "positive/trace.json").read_bytes()),
            "checkpoint": "raw/positive/hit.ss9",
            "checkpoint_sha256": EXPECTED_RAW_SHA256["positive/hit.ss9"],
            "screenshot": "raw/positive/hit.png",
            "screenshot_sha256": EXPECTED_RAW_SHA256["positive/hit.png"],
            "terminal_pc": _address(positive_checkpoint.registers[15]),
            "terminal_lr": _address(positive_checkpoint.registers[14]),
        },
    }


def _implementation(root: Path) -> dict[str, str]:
    paths = {
        "exporter_sha256": root / "tools/export_portrait_palette_producers.py",
        "verifier_sha256": root / "tools/verify_portrait_palette_producers.py",
        "test_sha256": root / "tests/test_export_portrait_palette_producers.py",
        "probe_sha256": root / "tools/mgba_palette_producer_probe.lua",
        "probe_test_sha256": root / "tests/test_mgba_palette_producer_probe_script.py",
    }
    return {name: _sha256(path.read_bytes()) for name, path in paths.items()}


def _payload(root: Path, raw_root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    _require(_sha256(rom), ROM_SHA256, "ROM hash")
    static_slices = _validate_static_code(rom)
    chapter = _chapter_denominator(rom)
    expected_summary = {
        "non_null_script_slots": 110,
        "unique_script_roots": 98,
        "unique_instruction_nodes": 14199,
        "unique_opcode_17_records": 161,
        "opcode_17_root_references": 193,
        "mode_counts": {
            "0": 48,
            "1": 2,
            "2": 29,
            "3": 31,
            "4": 11,
            "5": 18,
            "6": 4,
            "7": 5,
            "8": 13,
        },
        "parse_failures": [],
    }
    _require(chapter["summary"], expected_summary, "chapter denominator")
    runtime = _validate_runtime(root, raw_root)
    return {
        "schema": SCHEMA,
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "emulator": {
            "name": "mGBA",
            "source_commit": MGBA_SOURCE_COMMIT,
            "binary_sha256": MGBA_BINARY_SHA256,
            "architecture": "x86_64",
        },
        "chapter_denominator": chapter,
        "transition_dispatch": {
            "entry": "0x08096B74",
            "mode_dispatch": "0x08096B9C",
            "jump_table_address": "0x08096BB0",
            "jump_table": JUMP_TABLE,
        },
        "mode_0_fill": {
            "static_semantics": STATIC_SEMANTICS,
            "queue_semantics": QUEUE_SEMANTICS,
            "runtime": runtime,
        },
        "dim_transform": DIM_TRANSFORM,
        "static_evidence": static_slices,
        "scope": SCOPE,
        "implementation": _implementation(root),
    }


def _validate_raw_files(raw_root: Path) -> None:
    actual = {
        path.relative_to(raw_root).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    expected = set(RAW_FILES)
    if actual != expected:
        raise ValueError(
            f"raw capture file set mismatch: missing={sorted(expected - actual)}, "
            f"foreign={sorted(actual - expected)}"
        )
    actual_hashes = {
        relative: _sha256((raw_root / relative).read_bytes())
        for relative in sorted(expected)
    }
    if actual_hashes != EXPECTED_RAW_SHA256:
        mismatches = [
            relative
            for relative in sorted(expected)
            if actual_hashes[relative] != EXPECTED_RAW_SHA256[relative]
        ]
        raise ValueError(f"raw capture hash mismatch: {mismatches}")


def _manifest(payload: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
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


def export_artifact(
    root: Path | str,
    raw_root: Path | str,
    output_dir: Path | str | None,
) -> dict[str, Any]:
    root = Path(root)
    raw_root = Path(raw_root)
    _validate_raw_files(raw_root)
    payload = _payload(root, raw_root)
    if output_dir is None:
        return payload

    output_dir = Path(output_dir)
    if output_dir.exists():
        allowed = {"raw", PAYLOAD_NAME, "manifest.json"}
        foreign = {path.name for path in output_dir.iterdir()} - allowed
        if foreign:
            raise ValueError(f"foreign output entries: {sorted(foreign)}")

    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=parent))
    try:
        target_raw = temporary / "raw"
        for relative in RAW_FILES:
            target = target_raw / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(raw_root / relative, target)
        (temporary / PAYLOAD_NAME).write_bytes(_json_bytes(payload))
        files = {
            path.relative_to(temporary).as_posix(): _sha256(path.read_bytes())
            for path in temporary.rglob("*")
            if path.is_file()
        }
        manifest = _manifest(payload, files)
        (temporary / "manifest.json").write_bytes(_json_bytes(manifest))
        if output_dir.exists():
            backup = output_dir.with_name(f".{output_dir.name}.backup-{uuid.uuid4().hex}")
            output_dir.rename(backup)
            try:
                temporary.rename(output_dir)
            except BaseException:
                backup.rename(output_dir)
                raise
            shutil.rmtree(backup)
        else:
            temporary.rename(output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = export_artifact(args.root, args.raw_root, args.output_dir)
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "opcode_17_records": result["chapter_denominator"]["summary"][
                    "unique_opcode_17_records"
                ],
                "runtime_success": result["mode_0_fill"]["runtime"]["positive"][
                    "audit"
                ]["success"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
