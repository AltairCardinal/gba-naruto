#!/usr/bin/env python3
"""Independently verify the parser-bound zero-padding experiment artifact."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from typing import Any


SCHEMA = "rom-parser-bound-zero-padding-v1"
VERIFY_SCHEMA = "rom-parser-bound-zero-padding-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-parser-bound-zero-padding.json"
BUNDLE_NAME = "parser-bound-zero-padding.bin"
RUN_RELATIVE = Path(
    "build/experiments/active/parser-bound-zero-padding/codex-r4-20260821"
)
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

TABLE_SPECS = (
    ("primary", 0x060C74, 56, "f6c872afd0b653ae2e0e04407bdbc059719eb823801d165e22a1d7e5c98aa099"),
    ("alternate", 0x060D54, 56, "767308a8e78947f7795c61965155d27925265327466c9df9d5d547b2f0368b5c"),
    ("runtime_state", 0x060E34, 47, "d0abb00332b73cd36637dbfcf5a7811622438f9c6382dc8c8ff45b00455d00ae"),
    ("positions_formation", 0x060EF0, 45, "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed"),
)
FIXED_LENGTHS = {
    0x02: 4, 0x03: 2, 0x04: 4, 0x08: 2, 0x09: 2, 0x0A: 2,
    0x0E: 3, 0x0F: 2, 0x10: 1, 0x11: 2, 0x12: 5, 0x14: 3,
    0x16: 2, 0x17: 4, 0x18: 4, 0x19: 4, 0x1A: 3, 0x1B: 3,
    0x1C: 3, 0x1D: 3, 0x1E: 2, 0x1F: 2, 0x21: 5, 0x22: 4,
    0x23: 3, 0x33: 2, 0x37: 3,
}
CONDITIONAL_LAYOUTS = {
    0x0B: (6, 2), 0x0C: (6, 2), 0x15: (8, 4), 0x34: (8, 4),
    0x35: (9, 5), 0x36: (8, 4), 0x38: (7, 3), 0x39: (6, 2),
}
EXPECTED_GROUPS = {
    "m4a_wave_alignment_zero_padding": {
        "structure_count": 62, "structure_bytes": 122,
        "structure_range_sha256": "d6d1ff7eb0a8a1951b7b41d2068ba6553ce2fa55a59d9fbd634b12fb8a504acc",
        "accepted_count": 57, "accepted_bytes": 113,
        "accepted_range_sha256": "419028d3e627c2a81f1a46182f417b59fb4d444e60875761c01ef496dc62a9e5",
        "accepted_packed_sha256": "951b1c95584b91fd8776e1d26b25d745ad5d508f6337686b9f7131d7c2f7096a",
        "structural_rejected_count": 5, "structural_rejected_bytes": 9,
        "structural_rejected_range_sha256": "ef0f19220f9e98fa22f5ae65633df50f5b0062950b6885df5a208a106694cae1",
        "structural_rejected_bytes_sha256": "3863ffe80e143fa7f2003da77bd2d5fd705da5f440f88efbd88a710e149bd147",
    },
    "chapter_terminal_to_fixed_root_zero_padding": {
        "structure_count": 89, "structure_bytes": 3764,
        "structure_range_sha256": "5dd8da7a37873fd409f9b2964dd7626f04ff3a6836f13c39b0f4183099dc9f98",
        "accepted_count": 85, "accepted_bytes": 85,
        "accepted_range_sha256": "a49ad4eb183548d973bded8f8f3b25beef69166eeb4b5ba10daf477174d49a56",
        "accepted_packed_sha256": "6a3a9301bb8dd782bb5c170bedfa73e9e7c60235e6e1840f14bd14b812127ef2",
        "all_gap_count": 91, "all_gap_bytes": 3769,
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
EXPECTED_M4A_REPORT = {
    "schema": "rom-m4a-byte-inventory-verification-v1", "verified": True,
    "claim_count": 842, "byte_count": 887018, "sound_id_count": 159,
    "active_sound_id_count": 80, "empty_sound_id_count": 79,
    "track_reference_count": 217, "track_stream_count": 217,
    "voicegroup_count": 23, "tone_record_count": 387, "wave_count": 79,
    "unclaimed_dense_window_bytes": 318, "errors": [],
}
EXPECTED_CHAPTER_REPORT = {
    "schema": "rom-chapter-script-inventory-verification-v1", "verified": True,
    "pointer_table_slot_count": 204, "non_null_script_slots": 200,
    "unique_script_roots": 188, "unique_instruction_nodes": 18994,
    "dynamic_opcode_06_nodes": 42, "observed_opcode_count": 43,
    "terminal_node_count": 590, "parse_failure_count": 0,
    "raw_node_bytes": 334060, "node_overlap_bytes": 0,
    "merged_range_count": 92, "merged_range_bytes": 334060,
    "internal_gap_count": 91, "internal_gap_bytes": 3769,
    "packed_script_bytes": 334060, "errors": [],
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
SOURCE_CONTRACTS = {
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


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _slice(rom: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError(f"invalid ROM range at {_addr(offset)}")
    return rom[offset : offset + size]


def _u8(rom: bytes, offset: int) -> int:
    return _slice(rom, offset, 1)[0]


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _slice(rom, offset, 4))[0]


def _pointer(rom: bytes, offset: int, label: str) -> int:
    address = _u32(rom, offset)
    target = address - ROM_BASE
    if address < ROM_BASE or not 0 <= target < len(rom):
        raise ValueError(f"{label} is not a ROM pointer")
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
    if opcode == 0:
        return opcode, 1, []
    if opcode in FIXED_LENGTHS:
        length = FIXED_LENGTHS[opcode]
        _slice(rom, offset, length)
        return opcode, length, [offset + length]
    if opcode == 1:
        end = _renderer_text_end(rom, offset + 1)
        return opcode, end - offset, [end]
    if opcode in (5, 0x20):
        end = _renderer_text_end(rom, offset + 2)
        return opcode, end - offset, [end]
    if opcode == 6:
        return opcode, 9, [_pointer(rom, offset + 1, "opcode 06 branch 0"), _pointer(rom, offset + 5, "opcode 06 branch 1")]
    if opcode == 7:
        return opcode, 5, [_pointer(rom, offset + 1, "opcode 07 target")]
    if opcode in CONDITIONAL_LAYOUTS:
        length, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, length, [_pointer(rom, offset + pointer_offset, "conditional target"), offset + length]
    if opcode == 0x0D:
        return opcode, 5, [_pointer(rom, offset + 1, "opcode 0D target"), offset + 5]
    if opcode == 0x13:
        first_end = _token_text_end(rom, offset + 4)
        if _u8(rom, offset + 2) == 0:
            return opcode, first_end - offset, [first_end]
        second_end = _token_text_end(rom, first_end + 1)
        return opcode, second_end - offset, [second_end]
    if opcode == 0x32:
        cursor = offset
        edges = []
        while _u8(rom, cursor) == 0x32:
            edges.append(_pointer(rom, cursor + 1, "opcode 32 target"))
            cursor += 5
        edges.append(cursor)
        return opcode, cursor - offset, edges
    raise ValueError(f"unsupported/reserved opcode 0x{opcode:02X} at {_addr(offset)}")


def _pointer_tables(rom: bytes) -> tuple[list[tuple[str, int, int]], dict[int, list[tuple[str, int]]]]:
    roots: list[tuple[str, int, int]] = []
    by_offset: dict[int, list[tuple[str, int]]] = {}
    for name, start, count, expected_sha in TABLE_SPECS:
        raw = _slice(rom, start, count * 4)
        if _sha(raw) != expected_sha or _u32(rom, start) != 0:
            raise ValueError(f"{name} pointer table identity changed")
        for scenario_id in range(1, count):
            root = _pointer(rom, start + scenario_id * 4, f"{name}[{scenario_id}]")
            roots.append((name, scenario_id, root))
            by_offset.setdefault(root, []).append((name, scenario_id))
    return roots, by_offset


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
                    raise ValueError("node instability")
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


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not an object")
    return value


def _load_canonical_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not an object")
    if raw != _json_bytes(value):
        raise ValueError(f"{path.name} is not canonical JSON")
    return value


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


def _run_source_verifier(root: Path, command: list[str], expected: dict[str, Any]) -> None:
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError(f"source verifier failed: {command}")
    report = json.loads(completed.stdout)
    if report != expected:
        raise ValueError(f"source verifier report differs: {command}")


def _source_identity_and_reports(root: Path, payload: dict[str, Any]) -> None:
    _read_bound(root, M4A_MANIFEST_RELATIVE, M4A_MANIFEST_SHA256, "M4A source manifest identity changed")
    _read_bound(root, CHAPTER_MANIFEST_RELATIVE, CHAPTER_MANIFEST_SHA256, "chapter source promotion manifest identity changed")
    _read_bound(root, CHAPTER_PAYLOAD_RELATIVE, CHAPTER_PAYLOAD_SHA256, "chapter source payload identity changed")
    _read_bound(root, CHAPTER_BUNDLE_RELATIVE, CHAPTER_BUNDLE_SHA256, "chapter source bundle identity changed")
    _read_bound(root, M4A_VERIFIER_RELATIVE, M4A_VERIFIER_SHA256, "M4A source verifier identity changed")
    _read_bound(root, CHAPTER_VERIFIER_RELATIVE, CHAPTER_VERIFIER_SHA256, "chapter source verifier identity changed")
    m4a_command = ["python3", M4A_VERIFIER_RELATIVE.as_posix(), "--root", ".", "--manifest", M4A_MANIFEST_RELATIVE.as_posix()]
    chapter_command = ["python3", CHAPTER_VERIFIER_RELATIVE.as_posix(), "--root", ".", "--artifact-dir", CHAPTER_DIR_RELATIVE.as_posix()]
    _run_source_verifier(root, m4a_command, EXPECTED_M4A_REPORT)
    _run_source_verifier(root, chapter_command, EXPECTED_CHAPTER_REPORT)
    expected_sources = {
        "m4a": {"schema": M4A_SCHEMA, "manifest": M4A_MANIFEST_RELATIVE.as_posix(), "manifest_sha256": M4A_MANIFEST_SHA256, "verifier": {"command": m4a_command, "exit_code": 0, "verifier_sha256": M4A_VERIFIER_SHA256, "report": EXPECTED_M4A_REPORT}},
        "chapter": {"schema": CHAPTER_SCHEMA, "manifest": CHAPTER_MANIFEST_RELATIVE.as_posix(), "manifest_sha256": CHAPTER_MANIFEST_SHA256, "payload": CHAPTER_PAYLOAD_RELATIVE.as_posix(), "payload_sha256": CHAPTER_PAYLOAD_SHA256, "bundle": CHAPTER_BUNDLE_RELATIVE.as_posix(), "bundle_sha256": CHAPTER_BUNDLE_SHA256, "verifier": {"command": chapter_command, "exit_code": 0, "verifier_sha256": CHAPTER_VERIFIER_SHA256, "report": EXPECTED_CHAPTER_REPORT}},
    }
    if payload.get("sources") != expected_sources:
        raise ValueError("payload source identity binding mismatch")


def _base_record(kind: str, range_id: int, start: int, end: int, raw: bytes) -> dict[str, Any]:
    return {
        "range_id": range_id,
        "source_kind": kind,
        "range": [start, end],
        "size": end - start,
        "bytes_sha256": _sha(raw),
        "all_zero": not any(raw),
        "safe_allocatable_space_claimed": False,
    }


def _m4a_expected(rom: bytes, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    claims = sorted((c for c in manifest.get("claims", []) if c.get("semantic_class") == "m4a_directsound_wave"), key=lambda c: (c["range"], c["id"]))
    if len(claims) != 79:
        raise ValueError("M4A wave count changed")
    accepted, rejected, structure = [], [], []
    accepted_bytes = bytearray()
    structural_rejected_bytes = bytearray()
    for left, right in zip(claims, claims[1:]):
        le = left["range"][1]
        rs = right["range"][0]
        if rs != ((le + 3) & ~3) or rs <= le:
            continue
        raw = _slice(rom, le, rs - le)
        record = _base_record("m4a_wave_alignment_zero_padding", len(structure), le, rs, raw)
        record.update({
            "source_selector": {"semantic_class": "m4a_directsound_wave", "adjacency": "range_sorted", "alignment": 4},
            "left_claim_id": left["id"], "right_claim_id": right["id"],
            "left_range": list(left["range"]), "right_range": list(right["range"]),
            "alignment": 4,
            "left_source": {"claim_id": left["id"], "range": list(left["range"])},
            "right_source": {"claim_id": right["id"], "range": list(right["range"])},
        })
        structure.append(record)
        if record["all_zero"]:
            accepted.append(record)
            accepted_bytes.extend(raw)
        else:
            record["rejection_reason"] = "nonzero_alignment_gap"
            record["bytes"] = list(raw)
            rejected.append(record)
            structural_rejected_bytes.extend(raw)
    summary = {
        "structure_count": len(structure), "structure_bytes": sum(r["size"] for r in structure),
        "structure_range_sha256": _json_sha([r["range"] for r in structure]),
        "accepted_count": len(accepted), "accepted_bytes": sum(r["size"] for r in accepted),
        "accepted_range_sha256": _json_sha([r["range"] for r in accepted]),
        "accepted_packed_sha256": _sha(bytes(accepted_bytes)),
        "structural_rejected_count": len(rejected), "structural_rejected_bytes": sum(r["size"] for r in rejected),
        "structural_rejected_range_sha256": _json_sha([r["range"] for r in rejected]),
        "structural_rejected_bytes_sha256": _sha(bytes(structural_rejected_bytes)), "accepted_all_zero": True,
    }
    expected = {**EXPECTED_GROUPS["m4a_wave_alignment_zero_padding"], "accepted_all_zero": True}
    if summary != expected:
        raise ValueError("M4A padding denominator changed")
    return accepted, rejected, summary


def _chapter_expected(rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    roots, roots_by_offset = _pointer_tables(rom)
    nodes, failures = _walk_scripts(rom, roots)
    if failures:
        raise ValueError("chapter grammar traversal failed")
    merged = _merge_ranges([(offset, offset + length) for offset, (_, length) in nodes.items()])
    if len(merged) != 92:
        raise ValueError("chapter range count changed")
    accepted, structural_rejected, contract_excluded, structure = [], [], [], []
    accepted_bytes = bytearray()
    for index, ((_, left_end), (right_start, _)) in enumerate(zip(merged, merged[1:])):
        left_nodes = [(offset, opcode, length) for offset, (opcode, length) in nodes.items() if offset + length == left_end]
        terminal_nodes = [node for node in left_nodes if node[1] == 0]
        right_roots = roots_by_offset.get(right_start, [])
        is_structure = bool(terminal_nodes and right_roots)
        raw = _slice(rom, left_end, right_start - left_end)
        if is_structure:
            structure.append(_base_record("chapter_terminal_to_fixed_root_zero_padding", len(structure), left_end, right_start, raw))
        root_table, root_scenario = right_roots[0] if right_roots else (None, None)
        record = _base_record("chapter_terminal_to_fixed_root_zero_padding", index, left_end, right_start, raw)
        record.update({
            "source_selector": {"pointer_tables": [name for name, _, _, _ in TABLE_SPECS], "terminal_opcode": "0x00", "fixed_root": True},
            "terminal_opcode": "0x00" if terminal_nodes else None,
            "terminal_opcode_value": 0 if terminal_nodes else None,
            "terminal_offset": terminal_nodes[-1][0] if terminal_nodes else None,
            "right_root": right_start if right_roots else None,
            "right_pointer_table": root_table,
            "right_scenario_id": root_scenario,
            "left_terminal_nodes": [node[0] for node in terminal_nodes],
            "right_root_slots": [{"pointer_table": table, "scenario_id": scenario_id, "root": right_start} for table, scenario_id in right_roots],
            "left_source": {"terminal_offsets": [node[0] for node in terminal_nodes], "terminal_opcode": "0x00" if terminal_nodes else None},
            "right_source": {"root": right_start if right_roots else None, "pointer_table": root_table, "scenario_id": root_scenario},
        })
        if is_structure and record["all_zero"]:
            accepted.append(record)
            accepted_bytes.extend(raw)
        else:
            record["rejection_reason"] = "nonzero_terminal_to_root_gap" if is_structure else "nonterminal_or_nonroot_gap"
            record["bytes"] = list(raw)
            if is_structure:
                structural_rejected.append(record)
            else:
                contract_excluded.append(record)
    all_gap_records = sorted(accepted + structural_rejected + contract_excluded, key=lambda record: tuple(record["range"]))
    summary = {
        "structure_count": len(structure), "structure_bytes": sum(r["size"] for r in structure),
        "structure_range_sha256": _json_sha([r["range"] for r in structure]),
        "accepted_count": len(accepted), "accepted_bytes": sum(r["size"] for r in accepted),
        "accepted_range_sha256": _json_sha([r["range"] for r in accepted]),
        "accepted_packed_sha256": _sha(bytes(accepted_bytes)),
        "all_gap_count": len(all_gap_records), "all_gap_bytes": sum(r["size"] for r in all_gap_records),
        "all_gap_range_sha256": _json_sha([r["range"] for r in all_gap_records]),
        "all_gap_bytes_sha256": _sha(b"".join(bytes(record["bytes"]) if "bytes" in record else rom[record["range"][0]:record["range"][1]] for record in all_gap_records)),
        "accepted_all_zero": True,
    }
    summary.update(
        {
            "structural_rejected_count": len(structural_rejected),
            "structural_rejected_bytes": sum(r["size"] for r in structural_rejected),
            "structural_rejected_range_sha256": _json_sha([r["range"] for r in structural_rejected]),
            "structural_rejected_bytes_sha256": _sha(b"".join(bytes(r["bytes"]) for r in structural_rejected)),
            "contract_excluded_count": len(contract_excluded),
            "contract_excluded_bytes": sum(r["size"] for r in contract_excluded),
            "contract_excluded_range_sha256": _json_sha([r["range"] for r in contract_excluded]),
            "contract_excluded_bytes_sha256": _sha(b"".join(bytes(r["bytes"]) for r in contract_excluded)),
        }
    )
    expected = {**EXPECTED_GROUPS["chapter_terminal_to_fixed_root_zero_padding"], "accepted_all_zero": True}
    if summary != expected:
        raise ValueError("chapter padding denominator changed")
    return accepted, structural_rejected, contract_excluded, summary


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha((root / "tools/export_rom_parser_bound_zero_padding.py").read_bytes()),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_parser_bound_zero_padding.py").read_bytes()),
    }


def _expected_payload(root: Path, payload: dict[str, Any], rom: bytes) -> tuple[dict[str, Any], bytes]:
    source_m4a = _load_json(_safe_file(root, M4A_MANIFEST_RELATIVE))
    m4a_accepted, m4a_rejected, m4a_summary = _m4a_expected(rom, source_m4a)
    chapter_accepted, chapter_structural_rejected, chapter_contract_excluded, chapter_summary = _chapter_expected(rom)
    accepted = m4a_accepted + chapter_accepted
    accepted.sort(key=lambda r: (tuple(r["range"]), r["source_kind"], r["range_id"]))
    rejected = m4a_rejected + chapter_structural_rejected
    rejected.sort(key=lambda r: (tuple(r["range"]), r["source_kind"], r["range_id"]))
    chapter_contract_excluded.sort(key=lambda r: (tuple(r["range"]), r["source_kind"], r["range_id"]))
    bundle = bytearray()
    for record in accepted:
        start, end = record["range"]
        record["packed_range"] = [len(bundle), len(bundle) + end - start]
        bundle.extend(rom[start:end])
    expected_summary = {
        "accepted_range_count": len(accepted), "accepted_byte_count": len(bundle),
        "accepted_range_sha256": _json_sha([r["range"] for r in accepted]),
        "accepted_bundle_sha256": _sha(bytes(bundle)),
        "rejected_range_count": len(rejected), "rejected_byte_count": sum(r["size"] for r in rejected),
        "contract_excluded_range_count": len(chapter_contract_excluded),
        "contract_excluded_byte_count": sum(r["size"] for r in chapter_contract_excluded),
        "source_kind_counts": {"m4a_wave_alignment_zero_padding": len(m4a_accepted), "chapter_terminal_to_fixed_root_zero_padding": len(chapter_accepted)},
        "source_kind_bytes": {"m4a_wave_alignment_zero_padding": sum(r["size"] for r in m4a_accepted), "chapter_terminal_to_fixed_root_zero_padding": sum(r["size"] for r in chapter_accepted)},
        "accepted_all_zero": True, "safe_allocatable_space_claimed": False,
    }
    expected = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "sources": payload.get("sources"),
        "source_contracts": SOURCE_CONTRACTS,
        "classified_ranges": accepted,
        "rejected_ranges": rejected,
        "contract_excluded_ranges": chapter_contract_excluded,
        "group_summaries": {"m4a_wave_alignment_zero_padding": m4a_summary, "chapter_terminal_to_fixed_root_zero_padding": chapter_summary},
        "summary": expected_summary,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bytes(bundle))}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return expected, bytes(bundle)


def _producer_command() -> list[str]:
    return [
        "python3",
        "tools/export_rom_parser_bound_zero_padding.py",
        "--root",
        ".",
        "--output-dir",
        (RUN_RELATIVE / "final").as_posix(),
    ]


def _accepted_verifier_command() -> list[str]:
    return [
        "python3",
        "tools/verify_rom_parser_bound_zero_padding.py",
        "--root",
        ".",
        "--artifact-dir",
        (RUN_RELATIVE / "final").as_posix(),
    ]


def _candidate_command_is_valid(root: Path, command: object) -> bool:
    if not isinstance(command, list) or len(command) != 6:
        return False
    if command[:5] != [
        "python3",
        "tools/verify_rom_parser_bound_zero_padding.py",
        "--root",
        ".",
        "--artifact-dir",
    ]:
        return False
    argument = command[5]
    if not isinstance(argument, str):
        return False
    candidate = Path(argument)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    expected_parent = (root / RUN_RELATIVE).absolute()
    actual = (root / candidate).absolute()
    return actual.parent == expected_parent and actual.name.startswith(".candidate-")


def _expected_manifest(
    root: Path,
    payload: dict[str, Any],
    files: dict[str, str],
    status: str,
    report: dict[str, Any],
    recorded_command: object,
) -> dict[str, Any]:
    if status == "candidate":
        if not _candidate_command_is_valid(root, recorded_command):
            raise ValueError("candidate verifier command mismatch")
        verifier_command = recorded_command
        exit_code = None
        recorded_report = None
    elif status == "accepted":
        verifier_command = _accepted_verifier_command()
        exit_code = 0
        recorded_report = report
    else:
        raise ValueError("promotion manifest status mismatch")
    implementation = payload["implementation"]
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "files": files,
        "scope": SCOPE,
        "producer": {
            "command": _producer_command(),
            "exporter_sha256": implementation["exporter_sha256"],
            "test_sha256": implementation["test_sha256"],
            "verifier_sha256": implementation["verifier_sha256"],
        },
        "verifier": {
            "command": verifier_command,
            "exit_code": exit_code,
            "verifier_sha256": implementation["verifier_sha256"],
            "report": recorded_report,
        },
    }


def _report(payload: dict[str, Any], bundle: bytes) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "errors": [],
        "accepted_range_count": payload["summary"]["accepted_range_count"],
        "accepted_byte_count": payload["summary"]["accepted_byte_count"],
        "accepted_range_sha256": payload["summary"]["accepted_range_sha256"],
        "accepted_bundle_sha256": _sha(bundle),
        "rejected_range_count": payload["summary"]["rejected_range_count"],
        "rejected_byte_count": payload["summary"]["rejected_byte_count"],
        "contract_excluded_range_count": payload["summary"]["contract_excluded_range_count"],
        "contract_excluded_byte_count": payload["summary"]["contract_excluded_byte_count"],
        "m4a_structure_count": payload["group_summaries"]["m4a_wave_alignment_zero_padding"]["structure_count"],
        "chapter_structure_count": payload["group_summaries"]["chapter_terminal_to_fixed_root_zero_padding"]["structure_count"],
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact directory is missing or symlink")
        if not cursor.exists():
            break
    return requested


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        requested = artifact_dir if artifact_dir.is_absolute() else root / artifact_dir
        requested = _reject_symlink_components(requested)
        try:
            relative = requested.relative_to(root)
        except ValueError:
            if requested.is_symlink():
                raise ValueError("artifact directory is missing or symlink")
        else:
            cursor = root
            for part in relative.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ValueError("artifact directory is missing or symlink")
        artifact = requested.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact directory is missing or symlink")
        members = list(artifact.iterdir())
        if ({path.name for path in members} != {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"} or any(path.is_symlink() or not path.is_file() for path in members)):
            raise ValueError("artifact file set mismatch")
        manifest = _load_canonical_json(artifact / "manifest.json")
        if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA:
            raise ValueError("promotion manifest schema mismatch")
        if manifest.get("artifact_status") not in {"candidate", "accepted"}:
            raise ValueError("promotion manifest status mismatch")
        expected_files = {PAYLOAD_NAME: _sha((artifact / PAYLOAD_NAME).read_bytes()), BUNDLE_NAME: _sha((artifact / BUNDLE_NAME).read_bytes())}
        if manifest.get("files") != expected_files:
            raise ValueError("promotion manifest file hash mismatch")
        payload = _load_canonical_json(artifact / PAYLOAD_NAME)
        if set(payload) != {"schema", "rom", "sources", "source_contracts", "classified_ranges", "rejected_ranges", "contract_excluded_ranges", "group_summaries", "summary", "files", "scope", "limitations", "implementation"}:
            raise ValueError("payload top-level schema mismatch")
        if payload.get("schema") != SCHEMA:
            raise ValueError("payload schema mismatch")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity mismatch")
        if payload.get("rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
            raise ValueError("payload ROM identity mismatch")
        _source_identity_and_reports(root, payload)
        expected_payload, expected_bundle = _expected_payload(root, payload, rom)
        if payload != expected_payload:
            raise ValueError("payload differs from independent parser-bound rebuild")
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        if bundle != expected_bundle:
            raise ValueError("bundle differs from ROM-bound accepted bytes")
        report = _report(payload, bundle)
        verifier = manifest.get("verifier")
        recorded_command = verifier.get("command") if isinstance(verifier, dict) else None
        expected_manifest = _expected_manifest(
            root,
            payload,
            expected_files,
            manifest.get("artifact_status"),
            report,
            recorded_command,
        )
        if manifest != expected_manifest:
            raise ValueError("promotion manifest differs from independent rebuild")
        return report
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, struct.error, subprocess.SubprocessError) as error:
        errors.append(str(error))
        return {"schema": VERIFY_SCHEMA, "verified": False, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=RUN_RELATIVE / "final")
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
