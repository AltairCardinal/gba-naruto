#!/usr/bin/env python3
"""Export the fixed eight-row bounded-index u16-pair table at 0x53F2EE."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCHEMA = "rom-bounded-index-u16-pair-table-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
OFFICIAL = Path("artifacts/rom-bounded-index-u16-pair-table-v1")
PAYLOAD_NAME = "rom-bounded-index-u16-pair-table.json"
MANIFEST_NAME = "manifest.json"
TABLE_RANGE = (0x53F2EE, 0x53F30E)
TABLE_SHA256 = "a123b14474752d4827e3e9b0e93d58b85ccc69fac06d6eae63470b7b77004246"
ROM_BASE = 0x08000000
CONSUMER_RANGE = (0x080AA8, 0x080B08)
CONSUMER_SHA256 = "491f8a9da26c00e76cbbb081c400da6335ff45154b5c3f32957ebddf1bbdaaa4"
BASE_LITERAL = 0x0853F2EE
BASE_LITERAL_OFFSET = 0x080B04
BASE_LITERAL_SHA256 = "ffc375d8d09677e26f66ce3c769666d93abdc7d54f5b7088d542c1b14006fd97"
EXPECTED_CONSUMER_HALFWORDS = {
    0x080AAC: 0x6B20, 0x080AAE: 0x2807, 0x080AB0: 0xD824,
    0x080AE0: 0x4B08, 0x080AE2: 0x6B20, 0x080AE4: 0x0082,
    0x080AE6: 0x18D1, 0x080AE8: 0x8809, 0x080AEA: 0x8121,
    0x080AEC: 0x3302, 0x080AEE: 0x18D2, 0x080AF0: 0x8811,
    0x080AF2: 0x8161, 0x080AF4: 0x3001, 0x080AF6: 0x6320,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _publish_exclusive(source: Path, destination: Path) -> None:
    source = source.absolute()
    destination = destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def _all_occurrences(raw: bytes, needle: bytes) -> list[int]:
    result = []
    cursor = 0
    while True:
        cursor = raw.find(needle, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _dominators(root: int, successors: dict[int, list[int]]) -> dict[int, set[int]]:
    nodes = set(successors)
    predecessors = {node: [] for node in nodes}
    for source, targets in successors.items():
        for target in targets:
            if target in predecessors:
                predecessors[target].append(source)
    result = {node: ({root} if node == root else set(nodes)) for node in nodes}
    changed = True
    while changed:
        changed = False
        for node in sorted(nodes - {root}):
            incoming = predecessors[node]
            value = {node} | (set.intersection(*(result[item] for item in incoming))
                              if incoming else set())
            if value != result[node]:
                result[node] = value
                changed = True
    return result


def _raw_consumer_contract(rom: bytes) -> dict[str, Any]:
    """Derive the guard and lookup dataflow from Thumb encodings."""
    root, return_bx = 0x080AA8, 0x080B00
    pending = [root]
    successors: dict[int, list[int]] = {}
    while pending:
        offset = min(pending)
        pending.remove(offset)
        if offset in successors:
            continue
        if not root <= offset <= return_bx:
            raise ValueError("consumer CFG escaped function bound")
        halfword = struct.unpack_from("<H", rom, offset)[0]
        if offset == return_bx:
            if halfword & 0xFF87 != 0x4700:
                raise ValueError("consumer return changed")
            targets: list[int] = []
        elif halfword & 0xF000 == 0xD000 and ((halfword >> 8) & 0xF) < 14:
            delta = (halfword & 0xFF) << 1
            if delta & 0x100:
                delta -= 0x200
            targets = [offset + 2, offset + 4 + delta]
        elif halfword & 0xF800 == 0xE000:
            delta = (halfword & 0x7FF) << 1
            if delta & 0x800:
                delta -= 0x1000
            targets = [offset + 4 + delta]
        else:
            targets = [offset + 2]
        successors[offset] = targets
        for target in targets:
            if target not in successors:
                pending.append(target)
    dominators = _dominators(root, successors)
    guard_load, guard_cmp, guard_branch = 0x080AAC, 0x080AAE, 0x080AB0
    first_load, second_load = 0x080AE8, 0x080AF0
    if not all(site in dominators for site in (first_load, second_load)):
        raise ValueError("consumer lookup sites left bounded CFG")
    for load_site in (first_load, second_load):
        if not {guard_load, guard_cmp, guard_branch}.issubset(dominators[load_site]):
            raise ValueError("consumer unsigned guard no longer dominates lookup")

    load_index = struct.unpack_from("<H", rom, guard_load)[0]
    reload_index = struct.unpack_from("<H", rom, 0x080AE2)[0]
    def decode_word_imm(instruction: int, opcode: int) -> tuple[int, int, int]:
        if instruction & 0xF800 != opcode:
            raise ValueError("consumer word-immediate dataflow changed")
        return ((instruction >> 6) & 0x1F) * 4, (instruction >> 3) & 7, instruction & 7
    if decode_word_imm(load_index, 0x6800) != (0x30, 4, 0):
        raise ValueError("consumer index guard load changed")
    if decode_word_imm(reload_index, 0x6800) != (0x30, 4, 0):
        raise ValueError("consumer index reload changed")
    index_writers = []
    for offset in successors:
        instruction = struct.unpack_from("<H", rom, offset)[0]
        if instruction & 0xF800 == 0x6000:
            immediate, base, source = decode_word_imm(instruction, 0x6000)
            if (immediate, base) == (0x30, 4):
                index_writers.append((offset, source))
    if index_writers != [(0x080AF6, 0)]:
        raise ValueError("consumer index writer denominator changed")

    compare = struct.unpack_from("<H", rom, guard_cmp)[0]
    if compare & 0xF800 != 0x2800 or (compare >> 8) & 7 != 0 or compare & 0xFF != 7:
        raise ValueError("consumer unsigned compare changed")
    branch = struct.unpack_from("<H", rom, guard_branch)[0]
    delta = (branch & 0xFF) << 1
    if delta & 0x100:
        delta -= 0x200
    if (branch >> 8) & 0xF != 8 or guard_branch + 4 + delta != 0x080AFC:
        raise ValueError("consumer unsigned guard changed")

    literal_load = struct.unpack_from("<H", rom, 0x080AE0)[0]
    literal_offset = ((0x080AE0 + 4) & ~3) + (literal_load & 0xFF) * 4
    if (literal_load & 0xF800, (literal_load >> 8) & 7,
            literal_offset) != (0x4800, 3, BASE_LITERAL_OFFSET):
        raise ValueError("consumer literal resolution changed")
    shift = struct.unpack_from("<H", rom, 0x080AE4)[0]
    if (shift & 0xF800, (shift >> 6) & 0x1F,
            (shift >> 3) & 7, shift & 7) != (0, 2, 0, 2):
        raise ValueError("consumer record stride changed")
    add_base = struct.unpack_from("<H", rom, 0x080AE6)[0]
    if add_base != 0x18D1:
        raise ValueError("consumer first address dataflow changed")
    first = struct.unpack_from("<H", rom, first_load)[0]
    if (first & 0xF800, (first >> 3) & 7, first & 7,
            (first >> 6) & 0x1F) != (0x8800, 1, 1, 0):
        raise ValueError("consumer first LDRH changed")
    plus_two = struct.unpack_from("<H", rom, 0x080AEC)[0]
    second_add = struct.unpack_from("<H", rom, 0x080AEE)[0]
    second = struct.unpack_from("<H", rom, second_load)[0]
    if plus_two != 0x3302 or second_add != 0x18D2:
        raise ValueError("consumer second address dataflow changed")
    if (second & 0xF800, (second >> 3) & 7, second & 7,
            (second >> 6) & 0x1F) != (0x8800, 2, 1, 0):
        raise ValueError("consumer second LDRH changed")
    return {"reachable_instruction_count": len(successors),
            "guard_dominates_halfword_loads": True,
            "index_field_writer_sites": [ROM_BASE + offset for offset, _ in index_writers],
            "raw_cfg_node_vector_sha256": _sha(_canonical(sorted(successors)))}


def _table(rom: bytes) -> dict[str, Any]:
    raw = rom[slice(*TABLE_RANGE)]
    if _sha(raw) != TABLE_SHA256:
        raise ValueError("table identity changed")
    records = []
    for index in range(8):
        start = TABLE_RANGE[0] + index * 4
        cell = rom[start:start + 4]
        first_u16, second_u16 = struct.unpack("<HH", cell)
        first_s16, second_s16 = struct.unpack("<hh", cell)
        records.append({"index": index, "range": [start, start + 4],
                        "raw_hex": cell.hex(), "bytes_sha256": _sha(cell),
                        "first_u16": first_u16, "second_u16": second_u16,
                        "first_s16": first_s16, "second_s16": second_s16})
    return {"range": list(TABLE_RANGE), "bytes_sha256": TABLE_SHA256,
            "record_count": 8, "record_size": 4, "records": records}


def _consumer(rom: bytes) -> dict[str, Any]:
    if _sha(rom[BASE_LITERAL_OFFSET:BASE_LITERAL_OFFSET + 4]) != BASE_LITERAL_SHA256:
        raise ValueError("literal identity changed")
    if _sha(rom[slice(*CONSUMER_RANGE)]) != CONSUMER_SHA256:
        raise ValueError("consumer identity changed")
    derived = _raw_consumer_contract(rom)
    for offset, expected in EXPECTED_CONSUMER_HALFWORDS.items():
        if struct.unpack_from("<H", rom, offset)[0] != expected:
            raise ValueError("consumer instruction contract changed")
    guard = struct.unpack_from("<H", rom, 0x080AB0)[0]
    displacement = (guard & 0xFF) << 1
    if displacement & 0x100:
        displacement -= 0x200
    if ((guard >> 8) & 0xF) != 8 or 0x080AB0 + 4 + displacement != 0x080AFC:
        raise ValueError("consumer unsigned guard changed")
    load = struct.unpack_from("<H", rom, 0x080AE0)[0]
    literal_offset = ((0x080AE0 + 4) & ~3) + (load & 0xFF) * 4
    if load & 0xF800 != 0x4800 or (load >> 8) & 7 != 3:
        raise ValueError("consumer literal load changed")
    if literal_offset != BASE_LITERAL_OFFSET:
        raise ValueError("consumer literal resolution changed")
    if struct.unpack_from("<I", rom, BASE_LITERAL_OFFSET)[0] != BASE_LITERAL:
        raise ValueError("literal table base changed")
    occurrences = _all_occurrences(rom, BASE_LITERAL.to_bytes(4, "little"))
    if occurrences != [BASE_LITERAL_OFFSET]:
        raise ValueError("literal occurrence denominator changed")
    return {"range": list(CONSUMER_RANGE), "bytes_sha256": CONSUMER_SHA256,
            "index_field_offset": 0x30, "unsigned_max_index": 7,
            "guard_load_site": ROM_BASE + 0x080AAC,
            "guard_compare_site": ROM_BASE + 0x080AAE,
            "guard_exit_branch_site": ROM_BASE + 0x080AB0,
            "guard_exit": ROM_BASE + 0x080AFC,
            "guard_relation": "unsigned_index<=7",
            "base_literal_load_site": ROM_BASE + 0x080AE0,
            "base_literal_occurrences": [ROM_BASE + offset for offset in occurrences],
            "base_literal_value": BASE_LITERAL, "record_stride": 4,
            "halfword_load_sites": [ROM_BASE + 0x080AE8, ROM_BASE + 0x080AF0],
            "destination_halfword_offsets": [0x08, 0x0A],
            "index_increment_site": ROM_BASE + 0x080AF4,
            "index_store_site": ROM_BASE + 0x080AF6, **derived}


def _build_from_rom(rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    table = _table(rom)
    consumer = _consumer(rom)
    claim = {"id": "bounded-index-u16-pair-table-53f2ee",
             "range": list(TABLE_RANGE),
             "claim_kind": "bounded_index_u16_pair_table",
             "bytes_sha256": TABLE_SHA256}
    return {"schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom),
                    "sha256": ROM_SHA256},
            "table": table, "consumer_contract": consumer,
            "promotion": {"promotion_batch": SCHEMA,
                          "promoted_from_primary_class": "unknown",
                          "claims": [claim], "claim_count": 1,
                          "promotion_bytes": 32},
            "scope": {"natural_runtime_all_indices": False,
                      "business_field_semantics": False,
                      "signedness_at_destination": False,
                      "adjacent_zero_gap": False,
                      "editing_or_relocation_safety": False}}


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(_safe_file(root, ROM_PATH).read_bytes())


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = output if output.is_absolute() else root / output
    for parent in [lexical, *lexical.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("output has symlink ancestor")
    output = lexical.resolve(strict=False)
    if not output.is_relative_to(root) or output.exists():
        raise FileExistsError("output exists or escapes root")
    payload_raw = _canonical(build_payload(root))
    exporter = Path("tools/export_rom_bounded_index_u16_pair_table.py")
    verifier = Path("tools/verify_rom_bounded_index_u16_pair_table.py")
    test = Path("tests/test_export_rom_bounded_index_u16_pair_table.py")
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
                "artifact_status": "accepted",
                "files": {PAYLOAD_NAME: {"size": len(payload_raw),
                                         "sha256": _sha(payload_raw)}},
                "summary": {"record_count": 8, "promotion_bytes": 32},
                "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                         "--output", output.relative_to(root).as_posix()]},
                "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                         "--artifact", output.relative_to(root).as_posix()]},
                "implementation": {
                    "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
                    "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
                    "test_sha256": _sha(_safe_file(root, test).read_bytes())}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,
                                     prefix=".bounded-index-pair-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_bounded_index_u16_pair_table import verify_artifact
        report = verify_artifact(root, stage, expected_artifact=output)
        if not report["verified"]:
            raise ValueError(report["errors"])
        _publish_exclusive(stage, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
