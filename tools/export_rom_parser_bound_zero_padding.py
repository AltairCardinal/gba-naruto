#!/usr/bin/env python3
"""Export the two strictly parser-bound zero-padding contracts.

The exporter deliberately owns only the isolated experiment run.  It never
promotes an artifact and it refuses every output path other than this run's
``final`` directory.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA = "rom-parser-bound-zero-padding-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RUN_RELATIVE = Path(
    "build/experiments/active/parser-bound-zero-padding/codex-r4-20260821"
)
PAYLOAD_NAME = "rom-parser-bound-zero-padding.json"
BUNDLE_NAME = "parser-bound-zero-padding.bin"

M4A_MANIFEST_RELATIVE = Path("artifacts/rom-m4a-byte-inventory-v1/manifest.json")
M4A_MANIFEST_SHA256 = "1c0205bc8dde65c887f18f9f55fccce5770d2ebf283bb1a4589fd6d392c40194"
M4A_SCHEMA = "rom-m4a-byte-inventory-v1"
M4A_VERIFIER_RELATIVE = Path("tools/verify_rom_m4a_byte_inventory.py")
M4A_VERIFIER_SHA256 = "61f0ae3ddf40916e738030655fa5e5c41242cd98db5adbf102ab60f749d4c511"

CHAPTER_DIR_RELATIVE = Path("artifacts/rom-chapter-script-inventory-v1")
CHAPTER_MANIFEST_RELATIVE = CHAPTER_DIR_RELATIVE / "manifest.json"
CHAPTER_PAYLOAD_RELATIVE = CHAPTER_DIR_RELATIVE / "chapter-script-inventory.json"
CHAPTER_BUNDLE_RELATIVE = CHAPTER_DIR_RELATIVE / "chapter-script-bytes.bin"
CHAPTER_MANIFEST_SHA256 = "ad77f775f927b89e4a499ddff82e077c38b2767cd86348b65053cb8ca4136f0e"
CHAPTER_PAYLOAD_SHA256 = "813cd10394e5fac239aefd6043437796b1a63f95d8d068d714871b8dd3edcabc"
CHAPTER_BUNDLE_SHA256 = "eba1393714485ab78d0dbde6cb1b9cf407e031ce8c2a86068038a3920d5f0699"
CHAPTER_SCHEMA = "rom-chapter-script-inventory-v1"
CHAPTER_VERIFIER_RELATIVE = Path("tools/verify_rom_chapter_script_inventory.py")
CHAPTER_VERIFIER_SHA256 = "b9bf0203bddd8ca85981bd7957d95171c11187a117447bc5a0e92e384777911c"

M4A_REPORT = {
    "schema": "rom-m4a-byte-inventory-verification-v1",
    "verified": True,
    "claim_count": 842,
    "byte_count": 887018,
    "sound_id_count": 159,
    "active_sound_id_count": 80,
    "empty_sound_id_count": 79,
    "track_reference_count": 217,
    "track_stream_count": 217,
    "voicegroup_count": 23,
    "tone_record_count": 387,
    "wave_count": 79,
    "unclaimed_dense_window_bytes": 318,
    "errors": [],
}
CHAPTER_REPORT = {
    "schema": "rom-chapter-script-inventory-verification-v1",
    "verified": True,
    "pointer_table_slot_count": 204,
    "non_null_script_slots": 200,
    "unique_script_roots": 188,
    "unique_instruction_nodes": 18994,
    "dynamic_opcode_06_nodes": 42,
    "observed_opcode_count": 43,
    "terminal_node_count": 590,
    "parse_failure_count": 0,
    "raw_node_bytes": 334060,
    "node_overlap_bytes": 0,
    "merged_range_count": 92,
    "merged_range_bytes": 334060,
    "internal_gap_count": 91,
    "internal_gap_bytes": 3769,
    "packed_script_bytes": 334060,
    "errors": [],
}

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

EXPECTED_GROUPS = {
    "m4a_wave_alignment_zero_padding": {
        "structure_count": 62,
        "structure_bytes": 122,
        "structure_range_sha256": "d6d1ff7eb0a8a1951b7b41d2068ba6553ce2fa55a59d9fbd634b12fb8a504acc",
        "accepted_count": 57,
        "accepted_bytes": 113,
        "accepted_range_sha256": "419028d3e627c2a81f1a46182f417b59fb4d444e60875761c01ef496dc62a9e5",
        "accepted_packed_sha256": "951b1c95584b91fd8776e1d26b25d745ad5d508f6337686b9f7131d7c2f7096a",
        "structural_rejected_count": 5,
        "structural_rejected_bytes": 9,
        "structural_rejected_range_sha256": "ef0f19220f9e98fa22f5ae65633df50f5b0062950b6885df5a208a106694cae1",
        "structural_rejected_bytes_sha256": "3863ffe80e143fa7f2003da77bd2d5fd705da5f440f88efbd88a710e149bd147",
    },
    "chapter_terminal_to_fixed_root_zero_padding": {
        "structure_count": 89,
        "structure_bytes": 3764,
        "structure_range_sha256": "5dd8da7a37873fd409f9b2964dd7626f04ff3a6836f13c39b0f4183099dc9f98",
        "accepted_count": 85,
        "accepted_bytes": 85,
        "accepted_range_sha256": "a49ad4eb183548d973bded8f8f3b25beef69166eeb4b5ba10daf477174d49a56",
        "accepted_packed_sha256": "6a3a9301bb8dd782bb5c170bedfa73e9e7c60235e6e1840f14bd14b812127ef2",
        "all_gap_count": 91,
        "all_gap_bytes": 3769,
        "all_gap_range_sha256": "a837e8ad9e59d3016bb527b3ca2a4bf3bebf828327328744847a38e106cb1d3b",
        "all_gap_bytes_sha256": "93b2b61f760b4e7d94f241e73e986b155ddd2926219d74d37834f75ec3f62d04",
        "structural_rejected_count": 4,
        "structural_rejected_bytes": 3679,
        "structural_rejected_range_sha256": "606cf93f1815780c140721bd42e19c8495735e4aad8c2db097b8043121b082c7",
        "structural_rejected_bytes_sha256": "bc16b3f0db513d90b092baee021e2ef834f995d27a2191e504f3d97da0bade56",
        "contract_excluded_count": 2,
        "contract_excluded_bytes": 5,
        "contract_excluded_range_sha256": "a921f64f02561dade5a990b79f2094c67420c970f33f36bb25e729aca8887e2f",
        "contract_excluded_bytes_sha256": "cb54af94086516aeda8d7ea81ee1335e14d2ca13e9df113319b0c42280fc91d2",
    },
}

SCOPE = {
    "natural_execution_reachability_complete": False,
    "arbitrary_zero_holes_complete": False,
    "free_space_complete": False,
    "edit_safety_complete": False,
    "rejected_gaps_classified": False,
    "all_m4a_unclaimed_classified": False,
    "all_chapter_gaps_classified": False,
    "parser_bound_source_contracts_complete": True,
}
LIMITATIONS = [
    "Only the frozen M4A wave adjacency and chapter parser terminal-to-fixed-root contracts are classified.",
    "A zero byte is accepted only inside one of those parser-bound source ranges; arbitrary zero holes and free space are unknown.",
    "The result does not claim natural execution reachability, edit safety, relocation safety, or allocatability.",
    "Rejected gaps, all other M4A unclaimed bytes, and all other chapter internal gaps remain outside the accepted claim.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_sha(value: object) -> str:
    return _sha(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


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
    for index in range(31):
        raw = _slice(rom, 0x53D644 + index * 8, 3)
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
        width = 2 if value in (1,) or 0x80 <= value <= 0x9F else 3 if value == 2 else 1
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
        return opcode, 9, [_pointer(rom, offset + 1, "opcode 0x06 branch 0"), _pointer(rom, offset + 5, "opcode 0x06 branch 1")]
    if opcode == 0x07:
        return opcode, 5, [_pointer(rom, offset + 1, "opcode 0x07 target")]
    if opcode in CONDITIONAL_LAYOUTS:
        length, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, length, [_pointer(rom, offset + pointer_offset, f"opcode 0x{opcode:02X} target"), offset + length]
    if opcode == 0x0D:
        return opcode, 5, [_pointer(rom, offset + 1, "opcode 0x0D call target"), offset + 5]
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
            roots.append((name, scenario_id, _pointer(rom, start + scenario_id * 4, f"{name}[{scenario_id}]")))
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


def _walk_scripts(rom: bytes, roots: list[tuple[str, int, int]]) -> tuple[dict[int, tuple[int, int]], list[dict[str, Any]]]:
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
            failures.append({"table": table, "scenario_id": scenario_id, "root": _addr(root), "error": str(error)})
    return nodes, failures


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    root = root.resolve(strict=True)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _read_bound(root: Path, relative: Path, expected_sha: str, message: str) -> bytes:
    raw = _safe_file(root, relative).read_bytes()
    if _sha(raw) != expected_sha:
        raise ValueError(message)
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _run_source_verifier(root: Path, command: list[str], expected: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError(f"source verifier failed: {command}: {completed.stderr.strip()}")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"source verifier did not emit JSON: {command}") from error
    if report != expected:
        raise ValueError(f"source verifier report changed: {command}: {report}")
    return report


def _source_contracts(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _read_bound(root, M4A_MANIFEST_RELATIVE, M4A_MANIFEST_SHA256, "M4A source manifest identity changed")
    _read_bound(root, CHAPTER_MANIFEST_RELATIVE, CHAPTER_MANIFEST_SHA256, "chapter source promotion manifest identity changed")
    _read_bound(root, CHAPTER_PAYLOAD_RELATIVE, CHAPTER_PAYLOAD_SHA256, "chapter source payload identity changed")
    _read_bound(root, CHAPTER_BUNDLE_RELATIVE, CHAPTER_BUNDLE_SHA256, "chapter source bundle identity changed")
    _read_bound(root, M4A_VERIFIER_RELATIVE, M4A_VERIFIER_SHA256, "M4A source verifier identity changed")
    _read_bound(root, CHAPTER_VERIFIER_RELATIVE, CHAPTER_VERIFIER_SHA256, "chapter source verifier identity changed")
    m4a_command = ["python3", M4A_VERIFIER_RELATIVE.as_posix(), "--root", ".", "--manifest", M4A_MANIFEST_RELATIVE.as_posix()]
    chapter_command = ["python3", CHAPTER_VERIFIER_RELATIVE.as_posix(), "--root", ".", "--artifact-dir", CHAPTER_DIR_RELATIVE.as_posix()]
    m4a_report = _run_source_verifier(root, m4a_command, M4A_REPORT)
    chapter_report = _run_source_verifier(root, chapter_command, CHAPTER_REPORT)
    sources = {
        "m4a": {
            "schema": M4A_SCHEMA,
            "manifest": M4A_MANIFEST_RELATIVE.as_posix(),
            "manifest_sha256": M4A_MANIFEST_SHA256,
            "verifier": {
                "command": m4a_command,
                "exit_code": 0,
                "verifier_sha256": M4A_VERIFIER_SHA256,
                "report": m4a_report,
            },
        },
        "chapter": {
            "schema": CHAPTER_SCHEMA,
            "manifest": CHAPTER_MANIFEST_RELATIVE.as_posix(),
            "manifest_sha256": CHAPTER_MANIFEST_SHA256,
            "payload": CHAPTER_PAYLOAD_RELATIVE.as_posix(),
            "payload_sha256": CHAPTER_PAYLOAD_SHA256,
            "bundle": CHAPTER_BUNDLE_RELATIVE.as_posix(),
            "bundle_sha256": CHAPTER_BUNDLE_SHA256,
            "verifier": {
                "command": chapter_command,
                "exit_code": 0,
                "verifier_sha256": CHAPTER_VERIFIER_SHA256,
                "report": chapter_report,
            },
        },
    }
    contracts = {
        "m4a_wave_alignment_zero_padding": {
            "source_schema": M4A_SCHEMA,
            "semantic_class": "m4a_directsound_wave",
            "adjacency": "range-sorted adjacent claims",
            "alignment": 4,
            "strict_gap": "right.start == align4(left.end) and right.start > left.end",
            "structure_count": 62,
            "structure_bytes": 122,
        },
        "chapter_terminal_to_fixed_root_zero_padding": {
            "source_schema": CHAPTER_SCHEMA,
            "pointer_tables": [name for name, _, _, _ in TABLE_SPECS],
            "structure": "left terminal opcode 0x00 ends at gap start and right boundary is a fixed-table root",
            "structure_count": 89,
            "structure_bytes": 3764,
            "rejected_preserved": True,
        },
    }
    return sources, contracts


def _record_base(kind: str, range_id: int, start: int, end: int, raw: bytes) -> dict[str, Any]:
    return {
        "range_id": range_id,
        "source_kind": kind,
        "range": [start, end],
        "size": end - start,
        "bytes_sha256": _sha(raw),
        "all_zero": not any(raw),
        "safe_allocatable_space_claimed": False,
    }


def _m4a_records(rom: bytes, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    claims = [claim for claim in manifest.get("claims", []) if claim.get("semantic_class") == "m4a_directsound_wave"]
    claims.sort(key=lambda claim: (claim["range"], claim["id"]))
    if len(claims) != 79:
        raise ValueError("M4A wave denominator changed")
    structure: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    accepted_bytes = bytearray()
    structural_rejected_bytes = bytearray()
    for left, right in zip(claims, claims[1:]):
        left_start, left_end = left["range"]
        right_start, right_end = right["range"]
        if right_start != ((left_end + 3) & ~3) or right_start <= left_end:
            continue
        raw = _slice(rom, left_end, right_start - left_end)
        record = _record_base("m4a_wave_alignment_zero_padding", len(structure), left_end, right_start, raw)
        record.update(
            {
                "source_selector": {
                    "semantic_class": "m4a_directsound_wave",
                    "adjacency": "range_sorted",
                    "alignment": 4,
                },
                "left_claim_id": left["id"],
                "right_claim_id": right["id"],
                "left_range": list(left["range"]),
                "right_range": list(right["range"]),
                "alignment": 4,
                "left_source": {"claim_id": left["id"], "range": list(left["range"])},
                "right_source": {"claim_id": right["id"], "range": list(right["range"])},
            }
        )
        structure.append(record)
        if record["all_zero"]:
            accepted.append(record)
            accepted_bytes.extend(raw)
        else:
            record["rejection_reason"] = "nonzero_alignment_gap"
            record["bytes"] = list(raw)
            rejected.append(record)
            structural_rejected_bytes.extend(raw)
    vector = [record["range"] for record in structure]
    accepted_vector = [record["range"] for record in accepted]
    rejected_vector = [record["range"] for record in rejected]
    summary = {
        **EXPECTED_GROUPS["m4a_wave_alignment_zero_padding"],
        "accepted_all_zero": True,
        "structure_range_sha256": _json_sha(vector),
        "accepted_range_sha256": _json_sha(accepted_vector),
        "structural_rejected_range_sha256": _json_sha(rejected_vector),
        "accepted_packed_sha256": _sha(bytes(accepted_bytes)),
        "structural_rejected_bytes_sha256": _sha(bytes(structural_rejected_bytes)),
    }
    if summary != EXPECTED_GROUPS["m4a_wave_alignment_zero_padding"] | {"accepted_all_zero": True}:
        raise ValueError(f"M4A padding denominator changed: {summary}")
    return accepted, rejected, summary


def _chapter_records(rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    pointer_tables, roots = _pointer_tables(rom)
    nodes, failures = _walk_scripts(rom, roots)
    if failures:
        raise ValueError(f"chapter parser failures: {failures}")
    merged = _merge_ranges([(offset, offset + length) for offset, (_, length) in nodes.items()])
    if len(merged) != 92:
        raise ValueError("chapter merged range denominator changed")
    roots_by_offset: dict[int, list[tuple[str, int]]] = {}
    for table, scenario_id, root in roots:
        roots_by_offset.setdefault(root, []).append((table, scenario_id))
    all_gaps: list[tuple[int, int, list[tuple[int, int, int]], list[tuple[str, int]]]] = []
    for (_, left_end), (right_start, _) in zip(merged, merged[1:]):
        left_nodes = [(offset, opcode, length) for offset, (opcode, length) in nodes.items() if offset + length == left_end]
        all_gaps.append((left_end, right_start, left_nodes, roots_by_offset.get(right_start, [])))
    accepted: list[dict[str, Any]] = []
    structural_rejected: list[dict[str, Any]] = []
    contract_excluded: list[dict[str, Any]] = []
    accepted_bytes = bytearray()
    structure: list[dict[str, Any]] = []
    for index, (start, end, left_nodes, right_roots) in enumerate(all_gaps):
        terminal_nodes = [node for node in left_nodes if node[1] == 0]
        is_structure = bool(terminal_nodes and right_roots)
        raw = _slice(rom, start, end - start)
        if is_structure:
            structure_record = _record_base("chapter_terminal_to_fixed_root_zero_padding", len(structure), start, end, raw)
            structure.append(structure_record)
        root_table, root_scenario = right_roots[0] if right_roots else (None, None)
        record = _record_base("chapter_terminal_to_fixed_root_zero_padding", index, start, end, raw)
        record.update(
            {
                "source_selector": {
                    "pointer_tables": [name for name, _, _, _ in TABLE_SPECS],
                    "terminal_opcode": "0x00",
                    "fixed_root": True,
                },
                "terminal_opcode": "0x00" if terminal_nodes else None,
                "terminal_opcode_value": 0 if terminal_nodes else None,
                "terminal_offset": terminal_nodes[-1][0] if terminal_nodes else None,
                "right_root": end if right_roots else None,
                "right_pointer_table": root_table,
                "right_scenario_id": root_scenario,
                "left_terminal_nodes": [node[0] for node in terminal_nodes],
                "right_root_slots": [
                    {"pointer_table": table, "scenario_id": scenario_id, "root": end}
                    for table, scenario_id in right_roots
                ],
                "left_source": {
                    "terminal_offsets": [node[0] for node in terminal_nodes],
                    "terminal_opcode": "0x00" if terminal_nodes else None,
                },
                "right_source": {
                    "root": end if right_roots else None,
                    "pointer_table": root_table,
                    "scenario_id": root_scenario,
                },
            }
        )
        if is_structure:
            if record["all_zero"]:
                accepted.append(record)
                accepted_bytes.extend(raw)
            else:
                record["rejection_reason"] = "nonzero_terminal_to_root_gap"
                record["bytes"] = list(raw)
                structural_rejected.append(record)
        else:
            record["rejection_reason"] = "nonterminal_or_nonroot_gap"
            record["bytes"] = list(raw)
            contract_excluded.append(record)
    structure_vector = [record["range"] for record in structure]
    accepted_vector = [record["range"] for record in accepted]
    all_gap_records = accepted + structural_rejected + contract_excluded
    all_gap_records.sort(key=lambda record: tuple(record["range"]))
    summary = {
        **EXPECTED_GROUPS["chapter_terminal_to_fixed_root_zero_padding"],
        "accepted_all_zero": True,
        "structure_range_sha256": _json_sha(structure_vector),
        "accepted_range_sha256": _json_sha(accepted_vector),
        "accepted_packed_sha256": _sha(bytes(accepted_bytes)),
        "all_gap_count": len(all_gap_records),
        "all_gap_bytes": sum(record["size"] for record in all_gap_records),
        "all_gap_range_sha256": _json_sha([record["range"] for record in all_gap_records]),
        "all_gap_bytes_sha256": _sha(b"".join(bytes(record["bytes"]) if "bytes" in record else rom[record["range"][0]:record["range"][1]] for record in all_gap_records)),
        "structural_rejected_range_sha256": _json_sha([record["range"] for record in structural_rejected]),
        "structural_rejected_bytes_sha256": _sha(b"".join(bytes(record["bytes"]) for record in structural_rejected)),
        "contract_excluded_range_sha256": _json_sha([record["range"] for record in contract_excluded]),
        "contract_excluded_bytes_sha256": _sha(b"".join(bytes(record["bytes"]) for record in contract_excluded)),
    }
    if summary != EXPECTED_GROUPS["chapter_terminal_to_fixed_root_zero_padding"] | {"accepted_all_zero": True}:
        raise ValueError(f"chapter padding denominator changed: {summary}")
    return accepted, structural_rejected, contract_excluded, summary, {"pointer_tables": pointer_tables, "roots": roots, "nodes": nodes, "merged": merged}


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha((root / "tools/verify_rom_parser_bound_zero_padding.py").read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_parser_bound_zero_padding.py").read_bytes()),
    }


def _reject_symlink_components(path: Path, message: str) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(message)
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    expected = root / RUN_RELATIVE / "final"
    candidate = output if output.is_absolute() else root / output
    candidate = _reject_symlink_components(candidate, "output path uses a symlink")
    if candidate.resolve(strict=False) != expected:
        raise ValueError("foreign output path; only this run final is allowed")
    if candidate.exists():
        expected_members = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
        members = list(candidate.iterdir()) if candidate.is_dir() else []
        if (
            not candidate.is_dir()
            or {member.name for member in members} != expected_members
            or any(member.is_symlink() or not member.is_file() for member in members)
        ):
            raise ValueError("output is not an empty replaceable directory")
    return candidate


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _build(root: Path) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    sources, contracts = _source_contracts(root)
    m4a_manifest = _load_json(_safe_file(root, M4A_MANIFEST_RELATIVE))
    if m4a_manifest.get("schema") != M4A_SCHEMA:
        raise ValueError("M4A source schema changed")
    m4a_accepted, m4a_rejected, m4a_summary = _m4a_records(rom, m4a_manifest)
    chapter_accepted, chapter_structural_rejected, chapter_contract_excluded, chapter_summary, chapter_context = _chapter_records(rom)
    accepted = m4a_accepted + chapter_accepted
    accepted.sort(key=lambda record: (tuple(record["range"]), record["source_kind"], record["range_id"]))
    rejected = m4a_rejected + chapter_structural_rejected
    rejected.sort(key=lambda record: (tuple(record["range"]), record["source_kind"], record["range_id"]))
    chapter_contract_excluded.sort(key=lambda record: (tuple(record["range"]), record["source_kind"], record["range_id"]))
    bundle = bytearray()
    for record in accepted:
        start, end = record["range"]
        record["packed_range"] = [len(bundle), len(bundle) + end - start]
        bundle.extend(rom[start:end])
    accepted_vector = [record["range"] for record in accepted]
    if _json_sha(accepted_vector) != "936959996300e6971bf0afa70ebe8fa116bb57c92a824b710daa91cd5b08a4c1":
        raise ValueError("combined accepted range denominator changed")
    if _sha(bytes(bundle)) != "a6eab4025a7c9c0877549f6e5d790f66af88ee7f2320e814954e638d8051f812":
        raise ValueError("combined accepted bundle changed")
    summary = {
        "accepted_range_count": len(accepted),
        "accepted_byte_count": len(bundle),
        "accepted_range_sha256": _json_sha(accepted_vector),
        "accepted_bundle_sha256": _sha(bytes(bundle)),
        "rejected_range_count": len(rejected),
        "rejected_byte_count": sum(record["size"] for record in rejected),
        "contract_excluded_range_count": len(chapter_contract_excluded),
        "contract_excluded_byte_count": sum(record["size"] for record in chapter_contract_excluded),
        "source_kind_counts": {
            "m4a_wave_alignment_zero_padding": len(m4a_accepted),
            "chapter_terminal_to_fixed_root_zero_padding": len(chapter_accepted),
        },
        "source_kind_bytes": {
            "m4a_wave_alignment_zero_padding": sum(record["size"] for record in m4a_accepted),
            "chapter_terminal_to_fixed_root_zero_padding": sum(record["size"] for record in chapter_accepted),
        },
        "accepted_all_zero": True,
        "safe_allocatable_space_claimed": False,
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "sources": sources,
        "source_contracts": contracts,
        "classified_ranges": accepted,
        "rejected_ranges": rejected,
        "contract_excluded_ranges": chapter_contract_excluded,
        "group_summaries": {
            "m4a_wave_alignment_zero_padding": m4a_summary,
            "chapter_terminal_to_fixed_root_zero_padding": chapter_summary,
        },
        "summary": summary,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bytes(bundle))}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, bytes(bundle), {"chapter_context": chapter_context}


def _verifier_command(root: Path, artifact: Path) -> list[str]:
    try:
        artifact_argument = artifact.absolute().relative_to(root).as_posix()
    except ValueError:
        artifact_argument = artifact.absolute().as_posix()
    return [
        "python3",
        "tools/verify_rom_parser_bound_zero_padding.py",
        "--root",
        ".",
        "--artifact-dir",
        artifact_argument,
    ]


def _manifest(
    root: Path,
    payload: dict[str, Any],
    files: dict[str, bytes],
    status: str,
    report: dict[str, Any] | None,
    verifier_command: list[str] | None = None,
) -> dict[str, Any]:
    final_rel = (RUN_RELATIVE / "final").as_posix()
    if status == "candidate":
        if verifier_command is None:
            raise ValueError("candidate verifier command is required")
        exit_code = None
        verifier_report = None
    elif status == "accepted":
        verifier_command = [
            "python3",
            "tools/verify_rom_parser_bound_zero_padding.py",
            "--root",
            ".",
            "--artifact-dir",
            final_rel,
        ]
        exit_code = 0
        verifier_report = report
    else:
        raise ValueError("unsupported artifact status")
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": ["python3", "tools/export_rom_parser_bound_zero_padding.py", "--root", ".", "--output-dir", final_rel],
            "exporter_sha256": payload["implementation"]["exporter_sha256"],
            "test_sha256": payload["implementation"]["test_sha256"],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
        },
        "verifier": {
            "command": verifier_command,
            "exit_code": exit_code,
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "report": verifier_report,
        },
    }


def _write_exact(directory: Path, payload_raw: bytes, bundle: bytes, manifest: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    expected = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or path.name not in expected:
            raise ValueError(f"output contains foreign file: {path}")
    (directory / PAYLOAD_NAME).write_bytes(payload_raw)
    (directory / BUNDLE_NAME).write_bytes(bundle)
    (directory / "manifest.json").write_bytes(_json_bytes(manifest))


def _verify_cli(root: Path, artifact: Path) -> tuple[list[str], dict[str, Any]]:
    command = _verifier_command(root, artifact)
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("independent verifier returned invalid JSON") from error
    if completed.returncode != 0 or report.get("verified") is not True:
        raise ValueError(f"independent verifier rejected artifact: exit={completed.returncode}, report={report}, stderr={completed.stderr.strip()}")
    return command, report


def _receipt(status: str, command: list[str], report: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return {
        "schema": "parser-bound-zero-padding-receipt-v1",
        "artifact_status": status,
        "command": command,
        "exit_code": 0,
        "report": report,
        "files": files,
    }


def _load_canonical_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"receipt is not an object: {path}")
    if raw != _json_bytes(value):
        raise ValueError(f"receipt is not canonical JSON: {path}")
    return value


def _safe_receipt_file(path: Path) -> Path:
    requested = _reject_symlink_components(
        path, "receipt path uses a symlink"
    )
    if requested.is_symlink() or not requested.is_file():
        raise ValueError(f"receipt is missing or not a regular file: {requested}")
    return requested


def _write_new_receipt(path: Path, raw: bytes) -> None:
    requested = _reject_symlink_components(
        path, "receipt path uses a symlink"
    )
    try:
        with requested.open("xb") as target:
            target.write(raw)
    except FileExistsError as error:
        raise ValueError(f"receipt already exists: {requested}") from error


def _validate_existing_run(root: Path, final: Path) -> dict[str, Any]:
    run = root / RUN_RELATIVE
    _reject_symlink_components(run, "receipt path uses a symlink")
    candidate = _reject_symlink_components(
        run / "candidate", "candidate path uses a symlink"
    )
    candidate_receipt_path = run / "candidate-receipt.json"
    accepted_receipt_path = run / "accepted-receipt.json"
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("candidate receipt artifact is missing")
    candidate_receipt_path = _safe_receipt_file(candidate_receipt_path)
    accepted_receipt_path = _safe_receipt_file(accepted_receipt_path)
    accepted_command, accepted_report = _verify_cli(root, final)
    _, candidate_report = _verify_cli(root, candidate)
    if candidate_report != accepted_report:
        raise ValueError("candidate receipt report differs from accepted report")
    final_manifest = _load_canonical_json(final / "manifest.json")
    candidate_manifest = _load_canonical_json(candidate / "manifest.json")
    files = final_manifest.get("files")
    if candidate_manifest.get("files") != files:
        raise ValueError("candidate receipt files differ from accepted files")
    expected_candidate = _receipt(
        "candidate",
        candidate_manifest.get("verifier", {}).get("command"),
        candidate_report,
        files,
    )
    expected_accepted = _receipt(
        "accepted", accepted_command, accepted_report, files
    )
    if _load_canonical_json(candidate_receipt_path) != expected_candidate:
        raise ValueError("candidate receipt mismatch")
    if _load_canonical_json(accepted_receipt_path) != expected_accepted:
        raise ValueError("accepted receipt mismatch")
    return _load_json(final / PAYLOAD_NAME)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    final = _validate_output(root, output)
    if final.exists():
        return _validate_existing_run(root, final)
    payload, bundle, _ = _build(root)
    payload_raw = _json_bytes(payload)
    files = {PAYLOAD_NAME: payload_raw, BUNDLE_NAME: bundle}
    run = root / RUN_RELATIVE
    candidate = run / "candidate"
    candidate_receipt_path = run / "candidate-receipt.json"
    accepted_receipt_path = run / "accepted-receipt.json"
    installed_final = False
    _reject_symlink_components(run, "receipt path uses a symlink")
    if (
        candidate.is_symlink()
        or candidate_receipt_path.is_symlink()
        or accepted_receipt_path.is_symlink()
    ):
        raise ValueError("candidate or receipt path uses a symlink")
    if (
        candidate.exists()
        or candidate_receipt_path.exists()
        or accepted_receipt_path.exists()
    ):
        raise ValueError("candidate or receipt already exists; refusing to overwrite receipt")
    run.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".candidate-", dir=run))
    try:
        candidate_command = _verifier_command(root, temporary)
        candidate_manifest = _manifest(
            root,
            payload,
            files,
            "candidate",
            None,
            candidate_command,
        )
        _write_exact(temporary, payload_raw, bundle, candidate_manifest)
        command, candidate_report = _verify_cli(root, temporary)
        if command != candidate_command:
            raise ValueError("candidate verifier command changed")
        os.replace(temporary, candidate)
        _write_new_receipt(
            candidate_receipt_path,
            _json_bytes(
                _receipt(
                    "candidate", command, candidate_report, candidate_manifest["files"]
                )
            ),
        )
        accepted_manifest = _manifest(root, payload, files, "accepted", candidate_report)
        accepted_tmp = Path(tempfile.mkdtemp(prefix=".accepted-", dir=run))
        try:
            _write_exact(accepted_tmp, payload_raw, bundle, accepted_manifest)
            final.parent.mkdir(parents=True, exist_ok=True)
            _reject_symlink_components(final, "output path uses a symlink")
            os.replace(accepted_tmp, final)
            installed_final = True
            accepted_command, accepted_report = _verify_cli(root, final)
            if accepted_report != candidate_report:
                raise ValueError("accepted verifier report differs from candidate report")
        finally:
            if accepted_tmp.exists():
                shutil.rmtree(accepted_tmp)
        _write_new_receipt(
            accepted_receipt_path,
            _json_bytes(
                _receipt(
                    "accepted",
                    accepted_command,
                    accepted_report,
                    accepted_manifest["files"],
                )
            ),
        )
        return payload
    except Exception:
        if installed_final and final.exists():
            shutil.rmtree(final)
        if candidate.exists():
            shutil.rmtree(candidate)
        candidate_receipt_path.unlink(missing_ok=True)
        accepted_receipt_path.unlink(missing_ok=True)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=RUN_RELATIVE / "final")
    args = parser.parse_args()
    export_artifact(args.root, args.output_dir)
    print(json.dumps({"schema": SCHEMA, "verified": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
