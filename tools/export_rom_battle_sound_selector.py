#!/usr/bin/env python3
"""Export the frozen physical battle sound selector table."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-battle-sound-selector-v1"
VERIFY_SCHEMA = "rom-battle-sound-selector-verification-v1"
JSON_NAME = "battle-sound-selector.json"
BIN_NAME = "battle-sound-selector.bin"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_START = 0x53E496
TABLE_END = 0x53E596
TABLE_RANGE = (TABLE_START, TABLE_END)
TABLE_SHA256 = "2f77582ae5eea1711b079fc8ce67d36e95ec68bf0e2bd0a3d5780eb3d9819b5d"
DENOMINATOR_SHA256 = "fc3c1c03d918f173b304633d84fcbd8ead4448f5185d30d687c2ef352a3fcd62"
POINTER_WORD = 0x0853E496
POINTER_WORD_RAW = bytes.fromhex("96e45308")
POINTER_ADDRESSES = [
    0x0807BC64,
    0x0807BDF8,
    0x0807C078,
    0x0807C33C,
    0x0807CCA4,
]
POINTER_VECTOR_SHA256 = "0aacec92ffcc42108b7fe437ff83872b3702697ab9662b51e86dffc73623392d"
PLAY_TARGET = 0x08061E6C

CONSUMER_CONTRACT = [
    {
        "window": (0x07BB70, 0x07BB88),
        "base": 0x07BB70,
        "base_halfword": 0x493C,
        "literal": 0x07BC64,
        "index": 0x07BB7E,
        "table": 0x07BB82,
        "call": 0x07BB84,
        "window_sha256": "894597c8cc38880ab91ed219991c5d137b73d2e1c271d8c0e943e34bbd2a8c46",
    },
    {
        "window": (0x07BD50, 0x07BD68),
        "base": 0x07BD50,
        "base_halfword": 0x4929,
        "literal": 0x07BDF8,
        "index": 0x07BD5E,
        "table": 0x07BD62,
        "call": 0x07BD64,
        "window_sha256": "1ae576f2d74d8c58e4762db95c12658c41aaa537caec94471099ed4bd89aaa89",
    },
    {
        "window": (0x07C046, 0x07C05E),
        "base": 0x07C046,
        "base_halfword": 0x490C,
        "literal": 0x07C078,
        "index": 0x07C054,
        "table": 0x07C058,
        "call": 0x07C05A,
        "window_sha256": "6c8a2264999769ed720357212d246cdc76e38cfd84f869cd6de300142fa424c4",
    },
    {
        "window": (0x07C1C6, 0x07C1E6),
        "base": 0x07C1C6,
        "base_halfword": 0x4B5D,
        "literal": 0x07C33C,
        "index": 0x07C1DC,
        "table": 0x07C1E0,
        "call": 0x07C1E2,
        "window_sha256": "501fc5c21279690eeecd2b8da076ba6c5b416d6a924cd706bec2f36d09ad18eb",
    },
    {
        "window": (0x07CC88, 0x07CC9C),
        "base": 0x07CC88,
        "base_halfword": 0x4906,
        "literal": 0x07CCA4,
        "index": 0x07CC92,
        "table": 0x07CC96,
        "call": 0x07CC98,
        "window_sha256": "9c6ff38335c7aaf8a8b0152fc1b88ddeab0f928876c34303d945b46d823d63e4",
    },
]

NON_CLAIM_FIELDS = (
    "all_indices_naturally_reached_claimed",
    "all_direct_paths_naturally_reached_claimed",
    "all_selector_consumers_exhausted_claimed",
    "computed_or_ram_consumers_exhausted_claimed",
    "zero_value_business_semantics_claimed",
    "nonzero_value_business_semantics_claimed",
    "index_to_gameplay_semantics_claimed",
    "play_routine_full_behavior_claimed",
    "sound_playback_success_claimed",
    "left_neighbor_structure_claimed",
    "right_neighbor_business_relation_claimed",
    "all_battle_audio_exhausted_claimed",
    "editing_safety_claimed",
    "writeback_safety_claimed",
    "relocation_safety_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _u16(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("Thumb halfword escapes the ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _u32(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError("literal word escapes the ROM")
    return int.from_bytes(rom[offset : offset + 4], "little")


def _validate_root(root: Path) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    return resolved


def _safe_input(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
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


def _implementation_identities(root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "exporter": Path("tools/export_rom_battle_sound_selector.py"),
        "verifier": Path("tools/verify_rom_battle_sound_selector.py"),
        "tests": Path("tests/test_export_rom_battle_sound_selector.py"),
    }
    result: dict[str, dict[str, str]] = {}
    for role, relative in paths.items():
        path = _safe_input(root, relative)
        result[role] = {"path": relative.as_posix(), "sha256": _sha(path.read_bytes())}
    return result


def _decode_ldr_literal(rom: bytes, offset: int, label: str) -> tuple[int, int, int]:
    instruction = _u16(rom, offset)
    if instruction & 0xF800 != 0x4800:
        raise ValueError(f"{label} is not a Thumb PC-relative LDR")
    register = (instruction >> 8) & 7
    address = ROM_BASE + offset
    literal_address = ((address + 4) & ~3) + (instruction & 0xFF) * 4
    literal_offset = literal_address - ROM_BASE
    value = _u32(rom, literal_offset)
    return register, literal_address, value


def _decode_ldrb(rom: bytes, offset: int, label: str) -> dict[str, int]:
    instruction = _u16(rom, offset)
    if instruction & 0xF800 != 0x7800:
        raise ValueError(f"{label} is not a Thumb LDRB")
    return {
        "halfword": instruction,
        "base_register": (instruction >> 3) & 7,
        "offset_register": (instruction >> 6) & 7,
        "target_register": instruction & 7,
        "width": 1,
    }


def _decode_bl(rom: bytes, offset: int, label: str) -> tuple[int, int, int]:
    first = _u16(rom, offset)
    second = _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"{label} is not a Thumb BL")
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm11 = second & 0x07FF
    i1 = j1 ^ 1 ^ sign
    i2 = j2 ^ 1 ^ sign
    immediate = (sign << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if sign:
        immediate -= 1 << 25
    call_address = ROM_BASE + offset
    target = call_address + 4 + immediate
    return first, second, target


def _scan_pointer_occurrences(rom: bytes) -> list[int]:
    occurrences = []
    for offset in range(0, len(rom) - len(POINTER_WORD_RAW) + 1):
        if rom[offset : offset + 4] == POINTER_WORD_RAW:
            occurrences.append(ROM_BASE + offset)
    return occurrences


def decode_consumer_contract(rom: bytes) -> dict[str, Any]:
    """Decode the complete direct-literal consumer denominator from raw ROM."""
    if len(rom) != ROM_SIZE:
        raise ValueError("consumer decoder requires the complete ROM")
    if len(rom[TABLE_START:TABLE_END]) != 256 or _sha(rom[TABLE_START:TABLE_END]) != TABLE_SHA256:
        raise ValueError("battle sound selector table identity changed")
    occurrences = _scan_pointer_occurrences(rom)
    if occurrences != POINTER_ADDRESSES:
        raise ValueError("direct selector pointer-literal denominator changed")
    raw_vector = b"".join(rom[address - ROM_BASE : address - ROM_BASE + 4] for address in occurrences)
    if _sha(raw_vector) != POINTER_VECTOR_SHA256:
        raise ValueError("direct selector pointer-literal vector changed")

    literal_xrefs: list[dict[str, Any]] = []
    consumer_paths: list[dict[str, Any]] = []
    for ordinal, contract in enumerate(CONSUMER_CONTRACT):
        register, literal_address, value = _decode_ldr_literal(
            rom, contract["base"], f"consumer {ordinal} base load"
        )
        if register != ((contract["base_halfword"] >> 8) & 7):
            raise ValueError(f"consumer {ordinal} base-load register changed")
        if _u16(rom, contract["base"]) != contract["base_halfword"]:
            raise ValueError(f"consumer {ordinal} base-load halfword changed")
        if literal_address != ROM_BASE + contract["literal"] or value != POINTER_WORD:
            raise ValueError(f"consumer {ordinal} literal word changed")
        index_load = _decode_ldrb(rom, contract["index"], f"consumer {ordinal} index load")
        table_load = _decode_ldrb(rom, contract["table"], f"consumer {ordinal} table load")
        first, second, target = _decode_bl(rom, contract["call"], f"consumer {ordinal} play call")
        if target != PLAY_TARGET:
            raise ValueError(f"consumer {ordinal} play target changed")
        window_start, window_end = contract["window"]
        window = rom[window_start:window_end]
        if len(window) != window_end - window_start or _sha(window) != contract["window_sha256"]:
            raise ValueError(f"consumer {ordinal} frozen window changed")
        literal_xrefs.append(
            {
                "ordinal": ordinal,
                "literal_word": POINTER_WORD,
                "raw_word_hex": POINTER_WORD_RAW.hex(),
                "base_load_address": ROM_BASE + contract["base"],
                "base_load_file_offset": contract["base"],
                "base_load_halfword": contract["base_halfword"],
                "resolved_literal_address": literal_address,
                "resolved_literal_file_offset": contract["literal"],
                "resolved_literal_word": value,
            }
        )
        consumer_paths.append(
            {
                "ordinal": ordinal,
                "base_load_address": ROM_BASE + contract["base"],
                "base_load_halfword": contract["base_halfword"],
                "literal_address": literal_address,
                "literal_word": value,
                "final_index_load_address": ROM_BASE + contract["index"],
                "final_index_load_halfword": index_load["halfword"],
                "final_index_load_width": index_load["width"],
                "table_load_address": ROM_BASE + contract["table"],
                "table_load_halfword": table_load["halfword"],
                "table_load_width": table_load["width"],
                "play_callsite": ROM_BASE + contract["call"],
                "play_call_halfwords": [first, second],
                "decoded_play_target": target,
                "window": {
                    "range": [window_start, window_end],
                    "gba_range": [ROM_BASE + window_start, ROM_BASE + window_end],
                    "size": window_end - window_start,
                    "sha256": contract["window_sha256"],
                },
            }
        )
    return {
        "literal_word": POINTER_WORD,
        "literal_word_raw_hex": POINTER_WORD_RAW.hex(),
        "literal_addresses": occurrences,
        "literal_vector_sha256": _sha(raw_vector),
        "literal_xrefs": literal_xrefs,
        "consumer_paths": consumer_paths,
    }


def _denominator_rows() -> list[dict[str, Any]]:
    return [
        {"index": index, "range": [TABLE_START + index, TABLE_START + index + 1]}
        for index in range(TABLE_END - TABLE_START)
    ]


def build_payload(root: Path) -> dict[str, Any]:
    root = _validate_root(root)
    rom_path = _safe_input(root, ROM_PATH)
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    table = rom[TABLE_START:TABLE_END]
    if len(table) != 256 or _sha(table) != TABLE_SHA256:
        raise ValueError("battle sound selector table identity changed")
    rows = _denominator_rows()
    if _sha(_canonical(rows)) != DENOMINATOR_SHA256:
        raise ValueError("battle sound selector entry denominator changed")
    counts = Counter(table)
    selector = {
        "range": [TABLE_START, TABLE_END],
        "gba_range": [ROM_BASE + TABLE_START, ROM_BASE + TABLE_END],
        "entry_count": 256,
        "entry_size": 1,
        "byte_sha256": _sha(table),
        "denominator_sha256": _sha(_canonical(rows)),
        "counts": {
            "zero": table.count(0),
            "nonzero": sum(value != 0 for value in table),
            "distinct": len(counts),
            "minimum": min(table),
            "maximum": max(table),
        },
        "frequency_map": {f"{value:02X}": counts[value] for value in sorted(counts)},
    }
    consumer = decode_consumer_contract(rom)
    entries = [
        {
            "index": index,
            "file_offset": TABLE_START + index,
            "gba_address": ROM_BASE + TABLE_START + index,
            "value": value,
        }
        for index, value in enumerate(table)
    ]
    non_claims = {field: False for field in NON_CLAIM_FIELDS}
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "selector": selector,
        "entries": entries,
        "literal_xrefs": consumer["literal_xrefs"],
        "consumer_paths": consumer["consumer_paths"],
        "literal_denominator": {
            "word": POINTER_WORD,
            "raw_word_hex": POINTER_WORD_RAW.hex(),
            "count": len(consumer["literal_addresses"]),
            "addresses": consumer["literal_addresses"],
            "vector_sha256": consumer["literal_vector_sha256"],
        },
        "right_boundary": {
            "table_end_exclusive": TABLE_END,
            "table_end_gba_address": ROM_BASE + TABLE_END,
            "no_overlap": True,
            "no_gap_claimed": True,
            "next_byte": {
                "file_offset": TABLE_END,
                "gba_address": ROM_BASE + TABLE_END,
                "class": "battle_effect_runtime_state_sequence_table",
                "claim": "verified-reuse-battle-effect-runtime-state-sequences-53e596",
            },
        },
        "scope": {
            "physical_selector_table_complete": True,
            "direct_literal_consumer_denominator_complete": True,
            "coverage_classification_performed": False,
            "non_claims": non_claims,
        },
        "non_claims": non_claims,
        "implementation": _implementation_identities(root),
    }


def _validate_output_path(root: Path, output_dir: Path) -> Path:
    requested = Path(output_dir).expanduser()
    if requested.is_symlink():
        raise ValueError("output directory uses a symlink")
    absolute = requested.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var")}: 
            raise ValueError("output directory path uses a symlink")
    resolved = absolute.resolve()
    if resolved == root:
        raise ValueError("output directory cannot be the repository root")
    if resolved in root.parents:
        raise ValueError("output directory cannot be an ancestor of repository root")
    if requested.exists() and not requested.is_dir():
        raise ValueError("output directory is not a directory")
    if requested.exists() and any(requested.iterdir()):
        raise ValueError("output directory is non-empty or contains foreign files")
    return absolute


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = _validate_root(root)
    output = _validate_output_path(root, output_dir)
    payload = build_payload(root)
    binary = (root / ROM_PATH).read_bytes()[TABLE_START:TABLE_END]
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SCHEMA}-", dir=parent))
    try:
        (temporary / JSON_NAME).write_bytes(_canonical(payload))
        (temporary / BIN_NAME).write_bytes(binary)
        os.replace(temporary, output)
    except Exception:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
        raise
    return {
        "schema": SCHEMA,
        "files": {
            JSON_NAME: _sha((output / JSON_NAME).read_bytes()),
            BIN_NAME: _sha((output / BIN_NAME).read_bytes()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--out-dir", "--output-dir", dest="out_dir", type=Path, required=True)
    args = parser.parse_args()
    result = export_artifact(args.root, args.out_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
