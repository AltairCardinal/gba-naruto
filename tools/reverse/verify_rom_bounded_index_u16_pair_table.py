#!/usr/bin/env python3
"""Independently verify the fixed bounded-index u16-pair table packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools._vendor.capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs


SCHEMA = "rom-bounded-index-u16-pair-table-v1"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
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
            raise ValueError("unsafe input path")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError("unsafe input path")
    return result


def _safe_artifact(root: Path, artifact: Path) -> Path:
    base = root.resolve(strict=True)
    lexical = artifact if artifact.is_absolute() else base / artifact
    try:
        relative = lexical.relative_to(base)
    except ValueError as error:
        raise ValueError("artifact escapes root") from error
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact symlink ancestor")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_dir():
        raise ValueError("artifact escapes root")
    return resolved


def _occurrences(raw: bytes, needle: bytes) -> list[int]:
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
    while True:
        changed = False
        for node in sorted(nodes - {root}):
            incoming = predecessors[node]
            value = {node} | (set.intersection(*(result[item] for item in incoming))
                              if incoming else set())
            if value != result[node]:
                result[node] = value
                changed = True
        if not changed:
            return result


def _semantic_consumer_contract(rom: bytes) -> dict[str, Any]:
    """Rebuild the consumer CFG and dataflow with Capstone semantics."""
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    root, return_bx = 0x080AA8, 0x080B00
    pending = [root]
    instructions: dict[int, tuple[str, str, int]] = {}
    successors: dict[int, list[int]] = {}
    while pending:
        offset = min(pending)
        pending.remove(offset)
        if offset in instructions:
            continue
        if not root <= offset <= return_bx:
            raise ValueError("consumer Capstone CFG escaped function bound")
        decoded = list(engine.disasm(rom[offset:offset + 4], ROM_BASE + offset, count=1))
        if len(decoded) != 1:
            raise ValueError("consumer Capstone decode failed")
        instruction = decoded[0]
        instructions[offset] = (instruction.mnemonic, instruction.op_str,
                                instruction.size)
        if offset == return_bx:
            if (instruction.mnemonic, instruction.op_str) != ("bx", "r0"):
                raise ValueError("consumer Capstone return changed")
            targets: list[int] = []
        elif instruction.mnemonic == "b":
            targets = [int(instruction.op_str.removeprefix("#"), 16) - ROM_BASE]
        elif instruction.mnemonic.startswith("b") and instruction.mnemonic != "bl":
            targets = [offset + instruction.size,
                       int(instruction.op_str.removeprefix("#"), 16) - ROM_BASE]
        else:
            targets = [offset + instruction.size]
        successors[offset] = targets
        for target in targets:
            if target not in instructions:
                pending.append(target)
    expected = {
        0x080AAC: ("ldr", "r0, [r4, #0x30]"),
        0x080AAE: ("cmp", "r0, #7"),
        0x080AB0: ("bhi", "#0x8080afc"),
        0x080AE0: ("ldr", "r3, [pc, #0x20]"),
        0x080AE2: ("ldr", "r0, [r4, #0x30]"),
        0x080AE4: ("lsls", "r2, r0, #2"),
        0x080AE6: ("adds", "r1, r2, r3"),
        0x080AE8: ("ldrh", "r1, [r1]"),
        0x080AEA: ("strh", "r1, [r4, #8]"),
        0x080AEC: ("adds", "r3, #2"),
        0x080AEE: ("adds", "r2, r2, r3"),
        0x080AF0: ("ldrh", "r1, [r2]"),
        0x080AF2: ("strh", "r1, [r4, #0xa]"),
        0x080AF4: ("adds", "r0, #1"),
        0x080AF6: ("str", "r0, [r4, #0x30]"),
    }
    for offset, semantic in expected.items():
        observed = instructions.get(offset)
        if observed is None or observed[:2] != semantic:
            raise ValueError(f"consumer Capstone dataflow changed at 0x{offset:06X}")
    dominators = _dominators(root, successors)
    for load_site in (0x080AE8, 0x080AF0):
        if not {0x080AAC, 0x080AAE, 0x080AB0}.issubset(dominators[load_site]):
            raise ValueError("consumer Capstone guard no longer dominates lookup")
    if successors[0x080AB0] != [0x080AB2, 0x080AFC]:
        raise ValueError("consumer Capstone BHI target changed")
    writers = [offset for offset, (mnemonic, operands, _) in instructions.items()
               if (mnemonic, operands) == ("str", "r0, [r4, #0x30]")]
    if writers != [0x080AF6]:
        raise ValueError("consumer Capstone index writer denominator changed")
    literal_gba = ((ROM_BASE + 0x080AE0 + 4) & ~3) + 0x20
    if literal_gba != ROM_BASE + BASE_LITERAL_OFFSET:
        raise ValueError("consumer Capstone literal resolution changed")
    if int.from_bytes(rom[BASE_LITERAL_OFFSET:BASE_LITERAL_OFFSET + 4], "little") != BASE_LITERAL:
        raise ValueError("consumer Capstone literal value changed")
    return {"reachable_instruction_count": len(instructions),
            "guard_dominates_halfword_loads": True,
            "index_field_writer_sites": [ROM_BASE + offset for offset in writers],
            "raw_cfg_node_vector_sha256": _sha(_canonical(sorted(instructions)))}


def _rebuild(rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    table_raw = rom[slice(*TABLE_RANGE)]
    if _sha(table_raw) != TABLE_SHA256:
        raise ValueError("table identity changed")
    records = []
    for index, start in enumerate(range(TABLE_RANGE[0], TABLE_RANGE[1], 4)):
        cell = rom[start:start + 4]
        first_u16 = int.from_bytes(cell[:2], "little", signed=False)
        second_u16 = int.from_bytes(cell[2:], "little", signed=False)
        first_s16 = int.from_bytes(cell[:2], "little", signed=True)
        second_s16 = int.from_bytes(cell[2:], "little", signed=True)
        records.append({"index": index, "range": [start, start + 4],
                        "raw_hex": cell.hex(), "bytes_sha256": _sha(cell),
                        "first_u16": first_u16, "second_u16": second_u16,
                        "first_s16": first_s16, "second_s16": second_s16})
    if len(records) != 8:
        raise ValueError("table record denominator changed")
    derived = _semantic_consumer_contract(rom)
    literal_raw = rom[BASE_LITERAL_OFFSET:BASE_LITERAL_OFFSET + 4]
    if _sha(literal_raw) != BASE_LITERAL_SHA256:
        raise ValueError("literal identity changed")
    if _sha(rom[slice(*CONSUMER_RANGE)]) != CONSUMER_SHA256:
        raise ValueError("consumer identity changed")
    if int.from_bytes(literal_raw, "little") != BASE_LITERAL:
        raise ValueError("literal table base changed")
    occurrences = _occurrences(rom, BASE_LITERAL.to_bytes(4, "little"))
    if occurrences != [BASE_LITERAL_OFFSET]:
        raise ValueError("literal occurrence denominator changed")
    table = {"range": list(TABLE_RANGE), "bytes_sha256": TABLE_SHA256,
             "record_count": 8, "record_size": 4, "records": records}
    consumer = {"range": list(CONSUMER_RANGE), "bytes_sha256": CONSUMER_SHA256,
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
    return {"table": table, "consumer_contract": consumer}


def _expected(rom: bytes) -> dict[str, Any]:
    rebuilt = _rebuild(rom)
    claim = {"id": "bounded-index-u16-pair-table-53f2ee",
             "range": list(TABLE_RANGE),
             "claim_kind": "bounded_index_u16_pair_table",
             "bytes_sha256": TABLE_SHA256}
    return {"schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom),
                    "sha256": ROM_SHA256}, **rebuilt,
            "promotion": {"promotion_batch": SCHEMA,
                          "promoted_from_primary_class": "unknown",
                          "claims": [claim], "claim_count": 1,
                          "promotion_bytes": 32},
            "scope": {"natural_runtime_all_indices": False,
                      "business_field_semantics": False,
                      "signedness_at_destination": False,
                      "adjacent_zero_gap": False,
                      "editing_or_relocation_safety": False}}


def verify_artifact(root: Path, artifact: Path,
                    *, expected_artifact: Path | None = None) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        directory = _safe_artifact(root, artifact)
        members = list(directory.iterdir())
        if {path.name for path in members} != {PAYLOAD_NAME, MANIFEST_NAME}:
            raise ValueError("artifact file denominator changed")
        if any(path.is_symlink() or not path.is_file() for path in members):
            raise ValueError("artifact member type changed")
        payload_raw = (directory / PAYLOAD_NAME).read_bytes()
        manifest_raw = (directory / MANIFEST_NAME).read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest):
            raise ValueError("artifact JSON not canonical")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        if payload != _expected(rom):
            raise ValueError("payload contract changed")
        receipt = expected_artifact if expected_artifact is not None else directory
        receipt = receipt if receipt.is_absolute() else root / receipt
        relative = receipt.resolve(strict=False).relative_to(root).as_posix()
        exporter = Path("tools/export_rom_bounded_index_u16_pair_table.py")
        verifier = Path("tools/verify_rom_bounded_index_u16_pair_table.py")
        test = Path("tests/test_export_rom_bounded_index_u16_pair_table.py")
        expected_manifest = {
            "schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "files": {PAYLOAD_NAME: {"size": len(payload_raw),
                                     "sha256": _sha(payload_raw)}},
            "summary": {"record_count": 8, "promotion_bytes": 32},
            "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                     "--output", relative]},
            "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                     "--artifact", relative]},
            "implementation": {
                "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
                "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
                "test_sha256": _sha(_safe_file(root, test).read_bytes())}}
        if manifest != expected_manifest:
            raise ValueError("manifest contract changed")
        return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True,
                "errors": [], "promotion_bytes": 32, "record_count": 8}
    except Exception as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "contract_ok": False,
                "errors": [str(error)], "promotion_bytes": 0,
                "record_count": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
