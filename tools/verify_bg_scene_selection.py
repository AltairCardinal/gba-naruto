#!/usr/bin/env python3
"""Independently verify the complete BG scene-selection catalog."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "bg-scene-selection-v1"
VALID_ENTRY_IDS = tuple(range(1, 8)) + tuple(range(9, 14))

BG_LOADER = 0x08088348
BG_LOADER_END = 0x0808842A
BG_LOADER_SHA256 = "1d581ddbdfb89f17de5b5e52fd1b34d9952fcaddf8e4f24f1f86982facf6db27"
DIRECT_LOADER_CALLS = (0x0807AAA6, 0x0808F522, 0x08091716, 0x080930D6)
BATTLE_HEADERS = 0x0853D910
BATTLE_COUNT = 47
BATTLE_HEADER_SIZE = 0x20
BATTLE_HEADERS_SHA256 = "977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c"

PRIMARY_TABLE = 0x08060C74
ALTERNATE_TABLE = 0x08060D54
CHAPTER_ENTRY_COUNT = 56
PRIMARY_TABLE_SHA256 = "f6c872afd0b653ae2e0e04407bdbc059719eb823801d165e22a1d7e5c98aa099"
ALTERNATE_TABLE_SHA256 = "767308a8e78947f7795c61965155d27925265327466c9df9d5d547b2f0368b5c"
DISPATCH_TABLE = 0x080977F4
DISPATCH_COUNT = 0x3A
DISPATCH_TABLE_SHA256 = "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"
OPCODE_1E_HANDLER = 0x08097CE4
OPCODE_1E_HANDLER_END = 0x08097CF8
OPCODE_1E_HANDLER_SHA256 = "bffbff149e2ecf3deb9309a48123cffe724652121f6d4699720dc23b1d8f25dc"

SELECTION_WRAPPER = 0x0808F4D4
SELECTION_WRAPPER_END = 0x0808F544
SELECTION_WRAPPER_SHA256 = "5a5e08c007d48247ab0f8cce8c1e6c9b86c0a43c4fd8fd19d364790ac0dc71dd"
SELECTION_WRAPPER_CALLS = (
    0x0808A596, 0x0808A648, 0x0808F588, 0x08097038, 0x08097CEC,
)
SJIS_RANGE_TABLE = 0x0853D644
SJIS_RANGE_COUNT = 31
UPSTREAM_DIRECTORY = "artifacts/bg-resource-canvases-v1"
UPSTREAM_MANIFEST_SHA256 = "27096c9129823cc7d4f98aeb1fde304419a1c6abfadaf1cff6e13b80bf2fa99e"

FIXED_LENGTHS = {
    0x02: 4, 0x03: 2, 0x04: 4, 0x08: 2, 0x09: 2, 0x0A: 2,
    0x0E: 3, 0x0F: 2, 0x10: 1, 0x11: 2, 0x12: 5, 0x14: 3,
    0x16: 2, 0x17: 4, 0x18: 4, 0x19: 4, 0x1A: 3, 0x1B: 3,
    0x1C: 3, 0x1D: 3, 0x1E: 2, 0x1F: 2, 0x21: 5, 0x22: 4,
    0x23: 3, 0x33: 2, 0x37: 3,
}
CONDITIONAL_LAYOUTS = {
    0x0B: (6, 2), 0x0C: (6, 2), 0x15: (8, 4),
    0x34: (8, 4), 0x35: (9, 5), 0x36: (8, 4),
    0x38: (7, 3), 0x39: (6, 2),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _slice(rom: bytes, address: int, length: int) -> bytes:
    offset = address - ROM_BASE
    if offset < 0 or offset + length > len(rom):
        raise ValueError(f"ROM range is invalid at {_address(address)}")
    return rom[offset:offset + length]


def _u8(rom: bytes, address: int) -> int:
    return _slice(rom, address, 1)[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack("<I", _slice(rom, address, 4))[0]


def _pointer(rom: bytes, address: int) -> int:
    value = _u32(rom, address)
    _slice(rom, value, 1)
    return value


def _sjis_pair(rom: bytes, lead: int, trail: int) -> bool:
    code = lead << 8 | trail
    for index in range(SJIS_RANGE_COUNT):
        raw = _slice(rom, SJIS_RANGE_TABLE + index * 8, 3)
        lower = int.from_bytes(raw[:2], "little")
        if lower <= code < lower + raw[2]:
            return True
    return False


def _renderer_end(rom: bytes, address: int) -> int:
    cursor = address
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
        elif value >= 0xA0 and _sjis_pair(rom, value, _u8(rom, cursor + 1)):
            width = 2
        else:
            width = 1
        _slice(rom, cursor, width)
        cursor += width


def _token_end(rom: bytes, address: int) -> int:
    cursor = address
    while True:
        value = _u8(rom, cursor)
        if value == 0:
            return cursor + 1
        width = 2 if value == 1 or 0x80 <= value <= 0x9F else 3 if value == 2 else 1
        _slice(rom, cursor, width)
        cursor += width


def _node(rom: bytes, address: int) -> tuple[int, list[int]]:
    opcode = _u8(rom, address)
    if opcode == 0:
        return opcode, []
    if opcode in FIXED_LENGTHS:
        length = FIXED_LENGTHS[opcode]
        _slice(rom, address, length)
        return opcode, [address + length]
    if opcode == 1:
        return opcode, [_renderer_end(rom, address + 1)]
    if opcode in (5, 0x20):
        return opcode, [_renderer_end(rom, address + 2)]
    if opcode == 6:
        return opcode, [_pointer(rom, address + 1), _pointer(rom, address + 5)]
    if opcode == 7:
        return opcode, [_pointer(rom, address + 1)]
    if opcode in CONDITIONAL_LAYOUTS:
        length, pointer_offset = CONDITIONAL_LAYOUTS[opcode]
        return opcode, [_pointer(rom, address + pointer_offset), address + length]
    if opcode == 0x0D:
        return opcode, [_pointer(rom, address + 1), address + 5]
    if opcode == 0x13:
        first_end = _token_end(rom, address + 4)
        if _u8(rom, address + 2) == 0:
            return opcode, [first_end]
        return opcode, [_token_end(rom, first_end + 1)]
    if opcode == 0x32:
        cursor = address
        edges: list[int] = []
        while _u8(rom, cursor) == 0x32:
            edges.append(_pointer(rom, cursor + 1))
            cursor += 5
        edges.append(cursor)
        return opcode, edges
    if 0x24 <= opcode <= 0x31:
        raise ValueError(f"reserved opcode 0x{opcode:02X} at {_address(address)}")
    raise ValueError(f"unknown opcode 0x{opcode:02X} at {_address(address)}")


def _roots(rom: bytes) -> list[tuple[str, int, int]]:
    result = []
    for name, table in (("primary", PRIMARY_TABLE), ("alternate", ALTERNATE_TABLE)):
        if _u32(rom, table) != 0:
            raise ValueError(f"{name} sentinel is not null")
        for scenario_id in range(1, CHAPTER_ENTRY_COUNT):
            result.append((name, scenario_id, _pointer(rom, table + scenario_id * 4)))
    return result


def _chapter_catalog(rom: bytes) -> dict[str, Any]:
    roots = _roots(rom)
    nodes: dict[int, int] = {}
    opcode_06: set[int] = set()
    hits: dict[int, set[tuple[str, int]]] = defaultdict(set)
    failures: list[dict[str, Any]] = []
    for table, scenario_id, root in roots:
        pending = [root]
        seen: set[int] = set()
        try:
            while pending:
                address = pending.pop()
                if address in seen:
                    continue
                seen.add(address)
                opcode, edges = _node(rom, address)
                if address in nodes and nodes[address] != opcode:
                    raise ValueError(f"unstable opcode at {_address(address)}")
                nodes[address] = opcode
                if opcode == 6:
                    opcode_06.add(address)
                if opcode == 0x1E:
                    hits[address].add((table, scenario_id))
                pending.extend(edge for edge in edges if edge not in seen)
        except ValueError as error:
            failures.append(
                {
                    "table": table,
                    "scenario_id": scenario_id,
                    "root": _address(root),
                    "error": str(error),
                }
            )
    selections = []
    for address in sorted(hits):
        input_id = _u8(rom, address + 1)
        if input_id <= 49:
            selector = BATTLE_HEADERS + input_id * BATTLE_HEADER_SIZE + 0x1C
            entry_id = _u8(rom, selector)
            rule = "battle_header"
        else:
            selector = None
            entry_id = input_id - 41
            rule = "special_input_minus_41"
        selections.append(
            {
                "address": _address(address),
                "raw_hex": _slice(rom, address, 2).hex(),
                "input_id": input_id,
                "selection_rule": rule,
                "selector_address": None if selector is None else _address(selector),
                "entry_id": entry_id,
                "input_domain_valid": 0 <= input_id <= 54 and entry_id in VALID_ENTRY_IDS,
                "canvas": f"entry-{entry_id:02d}/canvas.png",
                "roots": [
                    {"table": table, "scenario_id": scenario_id}
                    for table, scenario_id in sorted(hits[address])
                ],
            }
        )
    return {
        "schema": "bg-chapter-opcode-1e-selections-v1",
        "pointer_tables": {
            "primary": _address(PRIMARY_TABLE),
            "alternate": _address(ALTERNATE_TABLE),
            "entry_count_each": CHAPTER_ENTRY_COUNT,
            "entry_zero": "null sentinel",
        },
        "interpreter": {
            "entry": "0x080977B8",
            "dispatch_table": _address(DISPATCH_TABLE),
            "opcode": "0x1E",
            "handler": _address(OPCODE_1E_HANDLER),
            "record_length": 2,
            "operand": "u8 at +1 passed to 0x0808F4D4",
        },
        "dynamic_opcode_06_contract": {
            "record_length": 9,
            "enumerated_indices": [0, 1],
            "runtime_index_address": "0x0200A880",
            "runtime_bounds_check": False,
            "caveat": "indices above 1 violate the ROM corpus invariant and can read past the two-pointer record",
        },
        "summary": {
            "non_null_script_slots": len(roots),
            "unique_script_roots": len({root for _, _, root in roots}),
            "unique_instruction_nodes": len(nodes),
            "dynamic_opcode_06_nodes": len(opcode_06),
            "unique_opcode_1e_records": len(selections),
            "parse_failures": failures,
        },
        "selections": selections,
    }


def _bl_calls(rom: bytes, target: int) -> list[int]:
    result = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        displacement = (first & 0x7FF) << 12 | (second & 0x7FF) << 1
        if displacement & 0x400000:
            displacement -= 0x800000
        callsite = ROM_BASE + offset
        if callsite + 4 + displacement == target:
            result.append(callsite)
    return result


def _callers_catalog(rom: bytes) -> dict[str, Any]:
    direct = _bl_calls(rom, BG_LOADER)
    wrapper = _bl_calls(rom, SELECTION_WRAPPER)
    if direct != list(DIRECT_LOADER_CALLS) or wrapper != list(SELECTION_WRAPPER_CALLS):
        raise ValueError("BG loader or wrapper callsites changed")
    unsafe_entry_ids = {
        str(input_id): _u8(
            rom, BATTLE_HEADERS + input_id * BATTLE_HEADER_SIZE + 0x1C
        )
        for input_id in range(BATTLE_COUNT, 50)
    }
    return {
        "schema": "bg-loader-callers-v1",
        "loader": _address(BG_LOADER),
        "selection_wrapper": _address(SELECTION_WRAPPER),
        "direct_loader_calls": [
            {
                "callsite": _address(callsite),
                "selection": (
                    "battle_header" if callsite == 0x0807AAA6
                    else "selection_wrapper_result" if callsite == 0x0808F522
                    else "fixed_entry_9" if callsite == 0x08091716
                    else "fixed_entry_1"
                ),
            }
            for callsite in direct
        ],
        "selection_wrapper_calls": [
            {"callsite": _address(callsite), "input": description}
            for callsite, description in (
                (0x0808A596, "function argument forwarded by battle presentation runner"),
                (0x0808A648, "function argument forwarded by indirect presentation entry"),
                (0x0808F588, "function argument forwarded by chapter flow entry"),
                (0x08097038, "reload state byte +0x17 from the last selection"),
                (0x08097CEC, "chapter opcode 0x1E operand byte"),
            )
        ],
        "input_mapping": {
            "0_to_46": "u8[0x0853D910 + input_id * 0x20 + 0x1C]",
            "47_to_49": "unsafe read past the 47-entry battle header table",
            "50_to_54": "entry_id = input_id - 41",
            "above_54": "unsafe entry_id 14+; loader has no bounds check",
        },
        "safe_input_ranges": [[0, 46], [50, 54]],
        "unsafe_input_ids": [47, 48, 49],
        "unsafe_entry_ids": unsafe_entry_ids,
        "valid_entry_ids": list(VALID_ENTRY_IDS),
        "valid_but_not_static_observed_entry_ids": [11, 13],
        "loader_bounds_check": False,
    }


def _upstream_canvases(root: Path) -> list[dict[str, Any]]:
    directory = root / UPSTREAM_DIRECTORY
    raw = (directory / "manifest.json").read_bytes()
    if _sha256(raw) != UPSTREAM_MANIFEST_SHA256:
        raise ValueError("upstream canvas manifest SHA-256 mismatch")
    manifest = json.loads(raw)
    if manifest.get("schema") != "bg-resource-canvases-v1":
        raise ValueError("upstream canvas schema mismatch")
    result = []
    for entry in manifest["entries"]:
        canvas = entry["canvas"]
        if _sha256((directory / canvas["png"]).read_bytes()) != canvas["png_sha256"]:
            raise ValueError(f"upstream canvas {entry['entry_id']} SHA-256 mismatch")
        result.append(
            {
                "entry_id": entry["entry_id"],
                "pixel_mode": entry["pixel_mode"],
                "canvas": canvas["png"],
                "canvas_sha256": canvas["png_sha256"],
            }
        )
    if tuple(row["entry_id"] for row in result) != VALID_ENTRY_IDS:
        raise ValueError("upstream canvas ID set mismatch")
    return result


def _battle_catalog(rom: bytes, canvases: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["entry_id"]: row for row in canvases}
    entries = []
    for battle_id in range(BATTLE_COUNT):
        selector = BATTLE_HEADERS + battle_id * BATTLE_HEADER_SIZE + 0x1C
        entry_id = _u8(rom, selector)
        canvas = by_id[entry_id]
        entries.append(
            {
                "battle_id": battle_id,
                "header_address": _address(BATTLE_HEADERS + battle_id * BATTLE_HEADER_SIZE),
                "selector_address": _address(selector),
                "entry_id": entry_id,
                "canvas": canvas["canvas"],
                "canvas_sha256": canvas["canvas_sha256"],
            }
        )
    return {
        "schema": "bg-battle-header-selections-v1",
        "formula": "u8[0x0853D910 + battle_id * 0x20 + 0x1C]",
        "entries": entries,
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def _expected(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    ranges = (
        (BATTLE_HEADERS, BATTLE_COUNT * BATTLE_HEADER_SIZE, BATTLE_HEADERS_SHA256),
        (PRIMARY_TABLE, CHAPTER_ENTRY_COUNT * 4, PRIMARY_TABLE_SHA256),
        (ALTERNATE_TABLE, CHAPTER_ENTRY_COUNT * 4, ALTERNATE_TABLE_SHA256),
        (DISPATCH_TABLE, DISPATCH_COUNT * 4, DISPATCH_TABLE_SHA256),
        (OPCODE_1E_HANDLER, OPCODE_1E_HANDLER_END - OPCODE_1E_HANDLER, OPCODE_1E_HANDLER_SHA256),
        (SELECTION_WRAPPER, SELECTION_WRAPPER_END - SELECTION_WRAPPER, SELECTION_WRAPPER_SHA256),
        (BG_LOADER, BG_LOADER_END - BG_LOADER, BG_LOADER_SHA256),
    )
    for address, size, digest in ranges:
        if _sha256(_slice(rom, address, size)) != digest:
            raise ValueError(f"evidence SHA-256 mismatch at {_address(address)}")
    dispatch = struct.unpack(
        f"<{DISPATCH_COUNT}I", _slice(rom, DISPATCH_TABLE, DISPATCH_COUNT * 4)
    )
    if dispatch[0x1E] != OPCODE_1E_HANDLER:
        raise ValueError("opcode 0x1E dispatch mismatch")

    canvases = _upstream_canvases(root)
    battles = _battle_catalog(rom, canvases)
    chapter = _chapter_catalog(rom)
    callers = _callers_catalog(rom)
    if chapter["summary"] != {
        "non_null_script_slots": 110,
        "unique_script_roots": 98,
        "unique_instruction_nodes": 14199,
        "dynamic_opcode_06_nodes": 42,
        "unique_opcode_1e_records": 6,
        "parse_failures": [],
    }:
        raise ValueError(f"chapter traversal coverage mismatch: {chapter['summary']}")
    observed = sorted(
        {row["entry_id"] for row in battles["entries"]}
        | {row["entry_id"] for row in chapter["selections"]}
        | {1, 9}
    )
    catalogs = {
        "battle-headers.json": battles,
        "chapter-opcode-1e.json": chapter,
        "loader-callers.json": callers,
    }
    manifest = {
        "schema": SCHEMA,
        "rom": {"file": "rom/base.gba", "sha256": ROM_SHA256},
        "upstream": {
            "directory": UPSTREAM_DIRECTORY,
            "schema": "bg-resource-canvases-v1",
            "manifest_sha256": UPSTREAM_MANIFEST_SHA256,
        },
        "evidence": {
            "battle_headers": {
                "gba_start": _address(BATTLE_HEADERS),
                "gba_end": _address(BATTLE_HEADERS + BATTLE_COUNT * BATTLE_HEADER_SIZE),
                "entry_count": BATTLE_COUNT,
                "entry_size": BATTLE_HEADER_SIZE,
                "selector_offset": 0x1C,
                "sha256": BATTLE_HEADERS_SHA256,
            },
            "chapter_pointer_tables": {
                "primary": _address(PRIMARY_TABLE),
                "primary_sha256": PRIMARY_TABLE_SHA256,
                "alternate": _address(ALTERNATE_TABLE),
                "alternate_sha256": ALTERNATE_TABLE_SHA256,
                "entry_count_each": CHAPTER_ENTRY_COUNT,
            },
            "interpreter_dispatch": {
                "gba_start": _address(DISPATCH_TABLE),
                "entry_count": DISPATCH_COUNT,
                "sha256": DISPATCH_TABLE_SHA256,
            },
            "opcode_1e_handler": {
                "gba_start": _address(OPCODE_1E_HANDLER),
                "gba_end": _address(OPCODE_1E_HANDLER_END),
                "sha256": OPCODE_1E_HANDLER_SHA256,
            },
            "selection_wrapper": {
                "gba_start": _address(SELECTION_WRAPPER),
                "gba_end": _address(SELECTION_WRAPPER_END),
                "sha256": SELECTION_WRAPPER_SHA256,
            },
            "loader": {
                "gba_start": _address(BG_LOADER),
                "gba_end": _address(BG_LOADER_END),
                "sha256": BG_LOADER_SHA256,
            },
        },
        "catalogs": {
            name: {"file": name, "sha256": _sha256(_json_bytes(value))}
            for name, value in catalogs.items()
        },
        "canvases": canvases,
        "summary": {
            "battle_header_count": BATTLE_COUNT,
            "chapter_opcode_1e_record_count": len(chapter["selections"]),
            "valid_entry_count": len(VALID_ENTRY_IDS),
            "statically_observed_entry_count": len(observed),
            "statically_observed_entry_ids": observed,
            "valid_but_unobserved_entry_ids": sorted(set(VALID_ENTRY_IDS) - set(observed)),
        },
        "scope": {
            "battle_header_selection_complete": True,
            "chapter_opcode_1e_selection_complete": True,
            "direct_loader_callers_complete": True,
            "selection_wrapper_callers_complete": True,
            "runtime_entry_selection_mechanisms_complete": True,
            "unsafe_wrapper_input_gap_documented": True,
            "natural_language_scene_names_complete": False,
            "scrolling_and_layer_composition_complete": False,
        },
    }
    return manifest, catalogs


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    expected_files = {
        "manifest.json",
        "battle-headers.json",
        "chapter-opcode-1e.json",
        "loader-callers.json",
    }
    actual_files = {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    } if artifact_dir.is_dir() else set()
    if actual_files != expected_files:
        errors.append(
            f"file set mismatch: expected {sorted(expected_files)}, got {sorted(actual_files)}"
        )
    try:
        expected_manifest, expected_catalogs = _expected(root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"source verification failed: {error}")
        return {
            "verified": False,
            "errors": errors,
            "battle_headers": 0,
            "chapter_opcode_1e_records": 0,
        }
    actual: dict[str, Any] = {}
    for name in expected_files:
        try:
            actual[name] = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            errors.append(f"{name}: {error}")
    if actual.get("manifest.json") != expected_manifest:
        errors.append("manifest.json does not match the independent ROM reconstruction")
    for name, expected in expected_catalogs.items():
        if actual.get(name) != expected:
            errors.append(f"{name} does not match the independent ROM reconstruction")
        path = artifact_dir / name
        if path.is_file():
            expected_hash = expected_manifest["catalogs"][name]["sha256"]
            if _sha256(path.read_bytes()) != expected_hash:
                errors.append(f"{name} SHA-256 mismatch")
    return {
        "verified": not errors,
        "errors": errors,
        "battle_headers": len(expected_catalogs["battle-headers.json"]["entries"]),
        "chapter_opcode_1e_records": len(
            expected_catalogs["chapter-opcode-1e.json"]["selections"]
        ),
        "battle_header_distribution": dict(
            sorted(
                Counter(
                    row["entry_id"]
                    for row in expected_catalogs["battle-headers.json"]["entries"]
                ).items()
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "artifacts" / SCHEMA,
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
