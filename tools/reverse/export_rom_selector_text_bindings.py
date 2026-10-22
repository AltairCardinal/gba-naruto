#!/usr/bin/env python3
"""Export selector-bound text prefixes and their fixed configuration records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-selector-text-bindings-v1"
VERIFY_SCHEMA = "rom-selector-text-bindings-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SOURCE_START = 0x59F5F0
SOURCE_COUNT = 46
SOURCE_RECORD_SIZE = 20
SOURCE_END = SOURCE_START + SOURCE_COUNT * SOURCE_RECORD_SIZE
SOURCE_SHA256 = "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56"
SOURCE_VECTOR_SHA256 = "065fca6237d166557a03cf30ddd309f695b825f5c850356a3c736e396d9478db"
EXPECTED_DIRECT_NAME_SLOTS = (
    1, 2, 3, 7, 44, 43, 4, 5, 6, 45, 8, 9, 10, 46, 11, 12, 13, 47,
    48, 30, 51, 52, 14, 15, 16, 17, 18, 19, 22, 23, 24, 29, 61, 20,
    21, 31, 49, 56, 50, 25, 26, 27, 28, 53, 54, 62,
)
DIRECT_NAME_SLOT_VECTOR_SHA256 = (
    "d429cca720c928593b80289794395d0c6d266268af5da567bbe76a22c5b65ba2"
)
DIRECT_NAME_SLOT_SET_SHA256 = (
    "42aaddfc56e36df6be859279c4a64aff4ae006e416895817c200d733eeae64a2"
)

DIRECT_START = 0x5A5AB8
DIRECT_OBSERVED_SLOT_COUNT = 63
DIRECT_SLOT_SIZE = 19
DIRECT_OBSERVED_END = DIRECT_START + DIRECT_OBSERVED_SLOT_COUNT * DIRECT_SLOT_SIZE
DIRECT_OBSERVED_SHA256 = (
    "ea1dec8f7fad13d1f6471a6271ecea853cd3a2603a9b99c6f1b8fabc3d830d06"
)
DIRECT_RECORD_RANGE_SHA256 = (
    "ac015ae6d87532061d5ac37ad763ee8b4eba1c535b5e158333c696a38a00f0e3"
)

PHYSICAL_START = 0x5A5F65
PHYSICAL_SLOT_COUNT = 55
PHYSICAL_SLOT_SIZE = 18
PHYSICAL_END = PHYSICAL_START + PHYSICAL_SLOT_COUNT * PHYSICAL_SLOT_SIZE
PHYSICAL_SHA256 = "aceb556f738c98c7132a219c87ffaedc0cefa9fc66ce56914449dc68ba86e712"
CONFIG_START = 0x5A6344
CONFIG_END = 0x5A63E8
CONFIG_SHA256 = "95b7408a9b6718155c07d5651b6bb6a311f9c5cdfa2dfe9d98ec1e6149a7a288"
POINTER_START = 0x5A63E8
POINTER_END = 0x5A63F4
POINTER_SHA256 = "a09fb292239bd99919eff5bd747e1019dc47e8166dfc3174f7ad8e50e73b2d17"
EXPECTED_LIST_STARTS = (0x5A6344, 0x5A639C, 0x5A63C0)
EXPECTED_RECORD_COUNTS = (21, 8, 9)
REFERENCED_IDS = tuple(range(1, 32)) + (39, 46, 50, 51, 52, 53, 54)
REFERENCED_IDS_SHA256 = "261964630e2bbe7b30d5a9a46e2b02cf5460abbce8d8fc0fea2589250e318728"
CONFIG_RECORD_DENOMINATOR_SHA256 = (
    "56b0208308400f94b6bf1d72379bba32a0fc196711b01d4114f5b1565948aaa3"
)
CONFIGURED_RECORD_RANGE_SHA256 = (
    "8efeb3f86df9cca48e37700a97d6afbd4693e64a7c350ea66394dde4427fe749"
)
CLASSIFIED_RANGE_SHA256 = (
    "796450b0f16cdb73e068c165536f32ed449f2bd23e803a8321983ff7f64232b6"
)
BUNDLE_SHA256 = "1bc1df2046811a0399226edc53895b3c3359779d9407a6555dc0e7810d11e869"

ENUMERATOR_RANGE = (0x08A6AC, 0x08A700)
ENUMERATOR_SHA256 = "68e8b80905466def5f6c4cae6fb6977336c129e7560577a77f6acac7222ca665"
SOURCE_LITERAL = 0x08A700
PROFILE_TABLE_LITERAL = 0x08A704
LIFECYCLE_RANGE = (0x08B58C, 0x08B65A)
LIFECYCLE_SHA256 = "3b6050a3df82957c8804b86a06eb6c5b5efb8a7eca3da082dc999f74b78c7637"
MENU_RANGE = (0x08B2C8, 0x08B580)
MENU_SHA256 = "fe12c74a937dae0e60f0ba1e566788cd4dc842596d168632c9c45809f88dd07e"
DIRECT_CONSUMER_RANGE = (0x08AFE0, 0x08B07C)
DIRECT_CONSUMER_SHA256 = (
    "9ec877cbef2c9aa100a825509cd41be605e3d20ff0304279572d7986c1865ac4"
)
DIRECT_TABLE_LITERAL = 0x08B084

CONFIG_CONSUMER_RANGE = (0x08CD5A, 0x08CDF8)
CONFIG_CONSUMER_SHA256 = (
    "f36813ab1237d74d65213b8ee0f696f9506f5cd85c4ab4691cddd6fd5d9da73a"
)
POINTER_TABLE_LITERAL = 0x08CE28
RUNTIME_STATE_LITERAL = 0x08CE2C
PHYSICAL_TABLE_LITERAL = 0x08CE30
SELECTOR_PRODUCER_RANGE = (0x097C6C, 0x097C98)
SELECTOR_PRODUCER_SHA256 = (
    "7ee4104e63d0210a67f6fba866585df11a5f8018e3660d5f378d7958ac6ec57d"
)
SELECTOR_MAPPER_RANGE = (0x08CC80, 0x08CCB4)
SELECTOR_MAPPER_SHA256 = (
    "b496c1d67e0c22493935c1e458ca8da74e6f692543b9a879add659b9be967f3f"
)
COPY_PARSER_RANGE = (0x09C4DC, 0x09C528)
COPY_PARSER_SHA256 = (
    "e6fec731464677978f23752f6d0e920ba2ad91f2ff09baf18d0f65383d6508c5"
)
RENDERER_BRIDGE_RANGE = (0x066758, 0x066790)
RENDERER_BRIDGE_SHA256 = (
    "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
)
RENDERER_PARSER_RANGE = (0x06626C, 0x066736)
RENDERER_PARSER_SHA256 = (
    "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
)
SJIS_TABLE = 0x53D644
SJIS_RANGE_COUNT = 31
SJIS_ENTRY_SIZE = 8
SJIS_TABLE_END = SJIS_TABLE + SJIS_RANGE_COUNT * SJIS_ENTRY_SIZE
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "selector-text-bindings.json"
BUNDLE_NAME = "selector-text-bytes.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
EXPECTED_SUMMARY = {
    "direct_source_record_count": 46,
    "direct_source_record_bytes": 920,
    "direct_text_candidate_slot_count": 46,
    "direct_text_consumed_bytes": 324,
    "direct_text_unclassified_suffix_bytes": 550,
    "configured_physical_slot_count": 55,
    "configured_referenced_slot_count": 38,
    "configured_text_consumed_bytes": 316,
    "configured_text_unclassified_suffix_bytes": 368,
    "configured_unreferenced_slot_bytes": 306,
    "config_list_count": 3,
    "config_record_count": 38,
    "config_terminator_count": 3,
    "config_bytes": 164,
    "config_pointer_slot_count": 3,
    "config_pointer_bytes": 12,
    "classified_range_count": 86,
    "classified_bytes": 816,
    "parse_failure_count": 0,
    "range_overlap_bytes": 0,
    "packed_bytes": 816,
}
SCOPE = {
    "fixed_46_source_record_denominator_complete": True,
    "direct_name_slot_domain_complete_for_proven_menu_chain": True,
    "direct_63_slot_physical_denominator_complete": False,
    "only_parser_consumed_direct_prefixes_classified": True,
    "fixed_55_slot_configured_physical_table_observed": True,
    "only_configuration_referenced_prefixes_classified": True,
    "three_way_configuration_denominator_complete": True,
    "nul_suffixes_classified": False,
    "natural_gameplay_all_records_proven": False,
    "unicode_decoding_complete": False,
    "editing_safety_proven": False,
}
LIMITATIONS = [
    "The 46 direct records are the exact name-slot domain produced by the fixed 46-row menu source table; two other consumers of the same physical base remain unbounded, so a complete 63-slot table is not claimed.",
    "Only bytes through each parser-consumed NUL are classified; 918 observed zero suffix bytes, 17 unreferenced configured slots, and the byte at 0x5A6343 remain unknown.",
    "The three configuration lists and their pointer table are complete for the selector output domain 0..2; natural execution of every row, Unicode decoding, and safe writeback remain unclaimed.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _vector_hash(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _take(data: bytes, start: int, size: int) -> bytes:
    end = start + size
    if start < 0 or end < start or end > len(data):
        raise ValueError("selector-text bounded slice escapes input")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_take(data, offset, 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_take(data, offset, 4), "little")


def _decode_bl(data: bytes, offset: int) -> int:
    high = _u16(data, offset)
    low = _u16(data, offset + 2)
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        raise ValueError("selector-text BL encoding changed")
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _thumb_literal_offset(offset: int, instruction: int, register: int) -> int:
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        raise ValueError("selector-text literal-load instruction changed")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _safe_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _evidence(
    rom: bytes, start: int, end: int, digest: str, label: str
) -> dict[str, Any]:
    if _sha(_take(rom, start, end - start)) != digest:
        raise ValueError(f"selector-text {label} evidence changed")
    return {
        "range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": digest,
    }


def _bl_sites_to(rom: bytes, target: int) -> list[int]:
    sites = []
    for offset in range(0, len(rom) - 3, 2):
        high = _u16(rom, offset)
        low = _u16(rom, offset + 2)
        if high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800:
            if _decode_bl(rom, offset) == target:
                sites.append(offset)
    return sites


def _source_records(rom: bytes) -> list[dict[str, Any]]:
    if _sha(_take(rom, SOURCE_START, SOURCE_END - SOURCE_START)) != SOURCE_SHA256:
        raise ValueError("selector-text direct source table changed")
    records = []
    vector = []
    for source_id in range(SOURCE_COUNT):
        start = SOURCE_START + source_id * SOURCE_RECORD_SIZE
        raw = _take(rom, start, SOURCE_RECORD_SIZE)
        if raw[0] != source_id:
            raise ValueError("selector-text direct source row identity changed")
        record = {
            "source_id": source_id,
            "name_slot": raw[1],
            "range": [start, start + SOURCE_RECORD_SIZE],
            "sha256": _sha(raw),
        }
        records.append(record)
        vector.append([source_id, start, raw[0], raw[1]])
    name_slots = [record["name_slot"] for record in records]
    if (
        tuple(name_slots) != EXPECTED_DIRECT_NAME_SLOTS
        or len(set(name_slots)) != SOURCE_COUNT
        or _vector_hash(vector) != SOURCE_VECTOR_SHA256
        or _vector_hash(name_slots) != DIRECT_NAME_SLOT_VECTOR_SHA256
        or _vector_hash(sorted(name_slots)) != DIRECT_NAME_SLOT_SET_SHA256
    ):
        raise ValueError("selector-text direct source name-slot domain changed")
    return records


def _decode_direct_producer_contract(rom: bytes) -> dict[str, Any]:
    enumerator = _evidence(
        rom, *ENUMERATOR_RANGE, ENUMERATOR_SHA256, "direct source enumerator"
    )
    lifecycle = _evidence(rom, *LIFECYCLE_RANGE, LIFECYCLE_SHA256, "menu lifecycle")
    menu = _evidence(rom, *MENU_RANGE, MENU_SHA256, "menu source selector")
    records = _source_records(rom)
    enum_tail = tuple(_u16(rom, offset) for offset in range(0x08A6EC, 0x08A6FA, 2))
    first_formula = tuple(_u16(rom, offset) for offset in range(0x08B2D8, 0x08B2E8, 2))
    second_formula = tuple(_u16(rom, offset) for offset in range(0x08B500, 0x08B512, 2))
    if (
        _thumb_literal_offset(0x08A6B0, _u16(rom, 0x08A6B0), 6) != SOURCE_LITERAL
        or _u32(rom, SOURCE_LITERAL) != ROM_BASE + SOURCE_START
        or _u32(rom, PROFILE_TABLE_LITERAL) != 0x085A143C
        or _u16(rom, 0x08A6BC) != 0x7870
        or _decode_bl(rom, 0x08A6BE) != 0x068EA4
        or enum_tail != (0x0249, 0x1850, 0x3614, 0x0C05, 0x1400, 0x282D, 0xDDE0)
        or _decode_bl(rom, 0x08B5FE) != ENUMERATOR_RANGE[0]
        or _decode_bl(rom, 0x08B640) != MENU_RANGE[0]
        or first_formula != (0x7879, 0x1840, 0x7801, 0x0088, 0x1840, 0x0080, 0x4959, 0x1840)
        or second_formula != (0x1CF8, 0x7879, 0x1840, 0x7801, 0x0088, 0x1840, 0x0080, 0x491B, 0x1840)
        or _u32(rom, 0x08B44C) != ROM_BASE + SOURCE_START
        or _u32(rom, 0x08B57C) != ROM_BASE + SOURCE_START
        or _decode_bl(rom, 0x08B420) != DIRECT_CONSUMER_RANGE[0]
        or _decode_bl(rom, 0x08B51A) != DIRECT_CONSUMER_RANGE[0]
    ):
        raise ValueError("selector-text direct producer data flow changed")
    callsites = _bl_sites_to(rom, DIRECT_CONSUMER_RANGE[0])
    if callsites != [0x08B420, 0x08B51A]:
        raise ValueError("selector-text direct consumer callsite denominator changed")
    return {
        "enumerator": enumerator,
        "lifecycle": lifecycle,
        "menu_selector": menu,
        "source_table_range": [SOURCE_START, SOURCE_END],
        "source_record_count": len(records),
        "source_record_size": SOURCE_RECORD_SIZE,
        "name_slot_domain": sorted(record["name_slot"] for record in records),
        "enumerator_loop_upper_inclusive": 45,
        "enumerator_call_offset": 0x08B5FE,
        "menu_call_offset": 0x08B640,
        "direct_consumer_callsites": callsites,
    }


def _decode_consumer_contract(rom: bytes) -> dict[str, Any]:
    direct = _evidence(
        rom, *DIRECT_CONSUMER_RANGE, DIRECT_CONSUMER_SHA256, "direct consumer"
    )
    config = _evidence(
        rom, *CONFIG_CONSUMER_RANGE, CONFIG_CONSUMER_SHA256, "config consumer"
    )
    producer = _evidence(
        rom, *SELECTOR_PRODUCER_RANGE, SELECTOR_PRODUCER_SHA256, "selector producer"
    )
    mapper = _evidence(
        rom, *SELECTOR_MAPPER_RANGE, SELECTOR_MAPPER_SHA256, "selector mapper"
    )
    copy_parser = _evidence(rom, *COPY_PARSER_RANGE, COPY_PARSER_SHA256, "copy parser")
    bridge = _evidence(
        rom, *RENDERER_BRIDGE_RANGE, RENDERER_BRIDGE_SHA256, "renderer bridge"
    )
    renderer = _evidence(
        rom, *RENDERER_PARSER_RANGE, RENDERER_PARSER_SHA256, "renderer parser"
    )
    direct_formula = tuple(_u16(rom, offset) for offset in range(0x08B02C, 0x08B03A, 2))
    config_formula = tuple(_u16(rom, offset) for offset in range(0x08CD86, 0x08CD92, 2))
    copy_loop = tuple(_u16(rom, offset) for offset in range(0x09C514, 0x09C526, 2))
    mapper_halfwords = tuple(
        _u16(rom, SELECTOR_MAPPER_RANGE[0] + index * 2) for index in range(26)
    )
    expected_mapper = (
        0xB500, 0x0400, 0x1400, 0x2801, 0xDD11, 0x2808, 0xDD0D, 0x2817,
        0xDD0D, 0x281E, 0xDC01, 0x2002, 0xE00A, 0x2832, 0xDD07, 0x2833,
        0xD003, 0x2834, 0xD003, 0x2835, 0xD101, 0x2001, 0xE000, 0x2000,
        0xBC02, 0x4708,
    )
    if (
        direct_formula != (0x7871, 0x0088, 0x1840, 0x0080, 0x1A40, 0x4913, 0x1840)
        or _u32(rom, DIRECT_TABLE_LITERAL) != ROM_BASE + DIRECT_START
        or _decode_bl(rom, 0x08B044) != RENDERER_BRIDGE_RANGE[0]
        or _u32(rom, POINTER_TABLE_LITERAL) != ROM_BASE + POINTER_START
        or _u32(rom, RUNTIME_STATE_LITERAL) != 0x020311D4
        or _u32(rom, PHYSICAL_TABLE_LITERAL) != ROM_BASE + PHYSICAL_START
        or config_formula != (0x7820, 0x00C1, 0x1809, 0x0049, 0x4828, 0x1809)
        or _decode_bl(rom, 0x08CD94) != COPY_PARSER_RANGE[0]
        or copy_loop != (0x7810, 0x7018, 0x0600, 0x3201, 0x3301, 0x2800, 0xD1F8, 0x1C30, 0xBD70)
        or mapper_halfwords != expected_mapper
        or _decode_bl(rom, 0x097C7E) != SELECTOR_MAPPER_RANGE[0]
        or _u16(rom, 0x097C82) != 0x7520
        or _decode_bl(rom, 0x06678A) != RENDERER_PARSER_RANGE[0]
    ):
        raise ValueError("selector-text consumer or parser data flow changed")
    return {
        "direct_text_consumer": {
            **direct,
            "index_load_offset": 0x08B02C,
            "record_stride": DIRECT_SLOT_SIZE,
            "table_literal_offset": DIRECT_TABLE_LITERAL,
            "table_address": _addr(DIRECT_START),
            "renderer_call_offset": 0x08B044,
            "renderer_bridge_target": _addr(RENDERER_BRIDGE_RANGE[0]),
        },
        "configured_text_consumer": {
            **config,
            "pointer_table_literal_offset": POINTER_TABLE_LITERAL,
            "runtime_selector_address": "0x020311E8",
            "physical_table_literal_offset": PHYSICAL_TABLE_LITERAL,
            "record_stride": PHYSICAL_SLOT_SIZE,
            "copy_call_offset": 0x08CD94,
            "copy_parser_target": _addr(COPY_PARSER_RANGE[0]),
        },
        "three_way_selector": {
            "producer": producer,
            "mapper": mapper,
            "mapper_call_offset": 0x097C7E,
            "output_store_offset": 0x097C82,
            "output_domain": [0, 1, 2],
        },
        "copy_parser": copy_parser,
        "renderer_bridge": bridge,
        "renderer_parser": renderer,
    }


def _sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    raw = _take(rom, SJIS_TABLE, SJIS_TABLE_END - SJIS_TABLE)
    if _sha(raw) != SJIS_TABLE_SHA256:
        raise ValueError("selector-text renderer character-range table changed")
    result = []
    for index in range(SJIS_RANGE_COUNT):
        row = _take(rom, SJIS_TABLE + index * SJIS_ENTRY_SIZE, 3)
        lower = int.from_bytes(row[:2], "little")
        result.append((lower, lower + row[2]))
    return tuple(result)


def _renderer_end(
    data: bytes,
    start: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> int:
    if not 0 <= start < limit <= len(data):
        raise ValueError("selector-text renderer record has invalid bounds")
    cursor = start
    while cursor < limit:
        value = data[cursor]
        if value == 0:
            return cursor + 1
        if value == 1:
            advance = 2
        elif value == 2:
            advance = 3
        elif 0x80 <= value <= 0x9F:
            advance = 2
        elif value >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("selector-text renderer record has truncated pair")
            pair = value * 0x100 + data[cursor + 1]
            advance = 2 if any(lower <= pair < upper for lower, upper in sjis_ranges) else 1
        else:
            advance = 1
        if cursor + advance > limit:
            raise ValueError("selector-text renderer record has truncated command")
        cursor += advance
    raise ValueError("selector-text renderer record lacks bounded NUL terminator")


def _nul_end(data: bytes, start: int, limit: int) -> int:
    if not 0 <= start < limit <= len(data):
        raise ValueError("selector-text copy record has invalid bounds")
    try:
        return data.index(0, start, limit) + 1
    except ValueError as error:
        raise ValueError("selector-text copy record lacks bounded NUL terminator") from error


def _text_record(
    rom: bytes,
    *,
    record_id: str,
    slot_id: int,
    start: int,
    slot_size: int,
    end: int,
    source_id: int | None = None,
) -> dict[str, Any]:
    physical_end = start + slot_size
    raw = _take(rom, start, slot_size)
    if not start < end <= physical_end or rom[end - 1] != 0:
        raise ValueError("selector-text parser boundary changed")
    suffix = rom[end:physical_end]
    if any(suffix):
        raise ValueError("selector-text observed NUL suffix changed")
    result = {
        "record_id": record_id,
        "slot_id": slot_id,
        "physical_range": [start, physical_end],
        "physical_sha256": _sha(raw),
        "consumed_range": [start, end],
        "consumed_size": end - start,
        "consumed_sha256": _sha(rom[start:end]),
        "terminator_offset": end - start - 1,
        "unclassified_suffix_range": [end, physical_end],
        "unclassified_suffix_size": physical_end - end,
        "unclassified_suffix_zero_filled": True,
    }
    if source_id is not None:
        result["source_id"] = source_id
    return result


def _direct_text_records(
    rom: bytes, source_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    sjis = _sjis_ranges(rom)
    result = []
    for source in source_records:
        slot = int(source["name_slot"])
        start = DIRECT_START + slot * DIRECT_SLOT_SIZE
        end = _renderer_end(rom, start, start + DIRECT_SLOT_SIZE, sjis)
        result.append(
            _text_record(
                rom,
                record_id=f"direct-source-{source['source_id']:02d}-slot-{slot:02d}",
                source_id=int(source["source_id"]),
                slot_id=slot,
                start=start,
                slot_size=DIRECT_SLOT_SIZE,
                end=end,
            )
        )
    if _vector_hash([record["consumed_range"] for record in result]) != DIRECT_RECORD_RANGE_SHA256:
        raise ValueError("selector-text direct consumed-range denominator changed")
    return result


def _config_inventory(rom: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if _sha(_take(rom, PHYSICAL_START, PHYSICAL_END - PHYSICAL_START)) != PHYSICAL_SHA256:
        raise ValueError("selector-text configured physical table changed")
    if _sha(_take(rom, CONFIG_START, CONFIG_END - CONFIG_START)) != CONFIG_SHA256:
        raise ValueError("selector-text configuration lists changed")
    if _sha(_take(rom, POINTER_START, POINTER_END - POINTER_START)) != POINTER_SHA256:
        raise ValueError("selector-text configuration pointer table changed")
    pointers = [_u32(rom, POINTER_START + index * 4) for index in range(3)]
    pointer_offsets = [pointer - ROM_BASE for pointer in pointers]
    if tuple(pointer_offsets) != EXPECTED_LIST_STARTS:
        raise ValueError("selector-text configuration pointers changed")
    config_records: list[dict[str, Any]] = []
    lists = []
    vector = []
    for list_index, start in enumerate(pointer_offsets):
        limit = pointer_offsets[list_index + 1] if list_index < 2 else CONFIG_END
        cursor = start
        records = []
        while cursor < limit:
            raw = _take(rom, cursor, 4)
            if raw == b"\xFF\x00\x00\x00":
                terminator = {"range": [cursor, cursor + 4], "sha256": _sha(raw)}
                cursor += 4
                break
            if raw[1] != 0 or raw[0] == 0 or raw[0] >= PHYSICAL_SLOT_COUNT:
                raise ValueError("selector-text configuration row changed")
            row_index = len(records)
            record = {
                "record_id": f"config-{list_index}-{row_index:02d}",
                "list_index": list_index,
                "record_index": row_index,
                "range": [cursor, cursor + 4],
                "text_slot": raw[0],
                "reserved_zero": raw[1],
                "x": raw[2],
                "y": raw[3],
                "sha256": _sha(raw),
            }
            records.append(record)
            config_records.append(record)
            vector.append([list_index, row_index, cursor, raw[0], raw[2], raw[3]])
            cursor += 4
        else:
            raise ValueError("selector-text configuration list lacks terminator")
        if cursor != limit or len(records) != EXPECTED_RECORD_COUNTS[list_index]:
            raise ValueError("selector-text configuration denominator changed")
        lists.append(
            {
                "list_index": list_index,
                "range": [start, limit],
                "record_count": len(records),
                "records": records,
                "terminator": terminator,
            }
        )
    if _vector_hash(vector) != CONFIG_RECORD_DENOMINATOR_SHA256:
        raise ValueError("selector-text configuration record vector changed")
    referenced_ids = sorted(record["text_slot"] for record in config_records)
    if (
        tuple(referenced_ids) != REFERENCED_IDS
        or len(set(referenced_ids)) != len(referenced_ids)
        or _vector_hash(referenced_ids) != REFERENCED_IDS_SHA256
    ):
        raise ValueError("selector-text referenced text-slot denominator changed")
    text_records = []
    for slot in referenced_ids:
        start = PHYSICAL_START + slot * PHYSICAL_SLOT_SIZE
        end = _nul_end(rom, start, start + PHYSICAL_SLOT_SIZE)
        text_records.append(
            _text_record(
                rom,
                record_id=f"configured-slot-{slot:02d}",
                slot_id=slot,
                start=start,
                slot_size=PHYSICAL_SLOT_SIZE,
                end=end,
            )
        )
    if _vector_hash([record["consumed_range"] for record in text_records]) != CONFIGURED_RECORD_RANGE_SHA256:
        raise ValueError("selector-text configured consumed-range denominator changed")
    config = {
        "range": [CONFIG_START, CONFIG_END],
        "sha256": CONFIG_SHA256,
        "record_size": 4,
        "record_counts": list(EXPECTED_RECORD_COUNTS),
        "records": config_records,
        "lists": lists,
        "pointer_table": {
            "range": [POINTER_START, POINTER_END],
            "entry_count": 3,
            "entry_size": 4,
            "sha256": POINTER_SHA256,
            "entries": [
                {
                    "list_index": index,
                    "raw_pointer": f"0x{pointer:08X}",
                    "file_offset": pointer_offsets[index],
                }
                for index, pointer in enumerate(pointers)
            ],
        },
    }
    return config, text_records


def _classified_ranges(
    rom: bytes,
    direct_records: list[dict[str, Any]],
    configured_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bytes]:
    specs = [
        (record["record_id"], "direct_renderer_text_prefix", record["consumed_range"])
        for record in direct_records
    ]
    specs.extend(
        (record["record_id"], "configured_copy_text_prefix", record["consumed_range"])
        for record in configured_records
    )
    specs.extend(
        [
            ("config-lists", "selector_configuration_lists", [CONFIG_START, CONFIG_END]),
            (
                "config-pointers",
                "selector_configuration_pointer_table",
                [POINTER_START, POINTER_END],
            ),
        ]
    )
    specs.sort(key=lambda item: (item[2][0], item[2][1], item[0]))
    ranges = []
    packed_cursor = 0
    for range_id, kind, value in specs:
        start, end = value
        raw = _take(rom, start, end - start)
        next_cursor = packed_cursor + len(raw)
        ranges.append(
            {
                "range_id": range_id,
                "kind": kind,
                "range": value,
                "size": len(raw),
                "sha256": _sha(raw),
                "packed_range": [packed_cursor, next_cursor],
            }
        )
        packed_cursor = next_cursor
    denominator = [item["range"] for item in ranges]
    if _vector_hash(denominator) != CLASSIFIED_RANGE_SHA256:
        raise ValueError("selector-text classified-range denominator changed")
    if any(left[1] > right[0] for left, right in zip(denominator, denominator[1:])):
        raise ValueError("selector-text classified ranges overlap")
    bundle = b"".join(_take(rom, start, end - start) for start, end in denominator)
    if len(bundle) != 816 or _sha(bundle) != BUNDLE_SHA256:
        raise ValueError("selector-text packed bytes changed")
    return ranges, bundle


def _derive(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    producer = _decode_direct_producer_contract(rom)
    semantics = _decode_consumer_contract(rom)
    source_records = _source_records(rom)
    if _sha(_take(rom, DIRECT_START, DIRECT_OBSERVED_END - DIRECT_START)) != DIRECT_OBSERVED_SHA256:
        raise ValueError("selector-text observed direct physical range changed")
    direct_records = _direct_text_records(rom, source_records)
    config, configured_records = _config_inventory(rom)
    classified_ranges, bundle = _classified_ranges(rom, direct_records, configured_records)
    implementation = {
        label: {"path": path, "sha256": _sha(_safe_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_selector_text_bindings.py",
            "verifier": "tools/verify_rom_selector_text_bindings.py",
            "test": "tests/test_export_rom_selector_text_bindings.py",
        }.items()
    }
    summary = {
        "direct_source_record_count": len(source_records),
        "direct_source_record_bytes": SOURCE_END - SOURCE_START,
        "direct_text_candidate_slot_count": len(direct_records),
        "direct_text_consumed_bytes": sum(record["consumed_size"] for record in direct_records),
        "direct_text_unclassified_suffix_bytes": sum(record["unclassified_suffix_size"] for record in direct_records),
        "configured_physical_slot_count": PHYSICAL_SLOT_COUNT,
        "configured_referenced_slot_count": len(configured_records),
        "configured_text_consumed_bytes": sum(record["consumed_size"] for record in configured_records),
        "configured_text_unclassified_suffix_bytes": sum(record["unclassified_suffix_size"] for record in configured_records),
        "configured_unreferenced_slot_bytes": (PHYSICAL_SLOT_COUNT - len(configured_records)) * PHYSICAL_SLOT_SIZE,
        "config_list_count": len(config["lists"]),
        "config_record_count": len(config["records"]),
        "config_terminator_count": len(config["lists"]),
        "config_bytes": CONFIG_END - CONFIG_START,
        "config_pointer_slot_count": len(config["pointer_table"]["entries"]),
        "config_pointer_bytes": POINTER_END - POINTER_START,
        "classified_range_count": len(classified_ranges),
        "classified_bytes": len(bundle),
        "parse_failure_count": 0,
        "range_overlap_bytes": 0,
        "packed_bytes": len(bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError("selector-text summary denominator changed")
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "direct_source_table": {
            "range": [SOURCE_START, SOURCE_END],
            "gba_range": [_addr(SOURCE_START), _addr(SOURCE_END)],
            "record_count": SOURCE_COUNT,
            "record_size": SOURCE_RECORD_SIZE,
            "sha256": SOURCE_SHA256,
            "record_vector_sha256": SOURCE_VECTOR_SHA256,
            "records": source_records,
        },
        "direct_text_candidates": {
            "semantic_type": "fixed_source_enumerated_renderer_text_prefixes",
            "physical_range_observed": [DIRECT_START, DIRECT_OBSERVED_END],
            "physical_slot_count_observed": DIRECT_OBSERVED_SLOT_COUNT,
            "physical_slot_size": DIRECT_SLOT_SIZE,
            "physical_sha256": DIRECT_OBSERVED_SHA256,
            "physical_denominator_complete": False,
            "candidate_slot_ids": [record["name_slot"] for record in source_records],
            "candidate_slot_domain": sorted(record["name_slot"] for record in source_records),
            "records": direct_records,
            "nul_suffixes_classified": False,
        },
        "configured_text_table": {
            "semantic_type": "configuration_referenced_copy_text_prefixes",
            "physical_range": [PHYSICAL_START, PHYSICAL_END],
            "physical_slot_size": PHYSICAL_SLOT_SIZE,
            "physical_slot_count": PHYSICAL_SLOT_COUNT,
            "physical_sha256": PHYSICAL_SHA256,
            "referenced_slot_ids": list(REFERENCED_IDS),
            "referenced_records": configured_records,
            "unreferenced_slots_classified": False,
            "nul_suffixes_classified": False,
        },
        "config_lists": config,
        "classified_ranges": classified_ranges,
        "direct_record_range_denominator_sha256": DIRECT_RECORD_RANGE_SHA256,
        "configured_record_range_denominator_sha256": CONFIGURED_RECORD_RANGE_SHA256,
        "config_record_denominator_sha256": CONFIG_RECORD_DENOMINATOR_SHA256,
        "classified_range_denominator_sha256": CLASSIFIED_RANGE_SHA256,
        "consumer_evidence": {
            "direct_producer": producer,
            "decoded_semantics": semantics,
        },
        "summary": summary,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": implementation,
    }
    return payload, bundle


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "files": {name: _sha(content) for name, content in sorted(files.items())},
        "producer": payload["implementation"],
        "scope": SCOPE,
        "verification": {
            "schema": VERIFY_SCHEMA,
            "command": [
                "python3",
                "tools/verify_rom_selector_text_bindings.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
        },
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root:
        raise ValueError("artifact output must not be the repository root")
    if target in root.parents:
        raise ValueError("artifact output must not be an ancestor of the repository root")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("foreign artifact output is not a directory")
    manifest_path = target / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("foreign artifact output directory")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("foreign artifact output directory") from error
    members = list(target.rglob("*"))
    actual = {member.relative_to(target).as_posix() for member in members if member.is_file()}
    if (
        manifest.get("artifact_schema") != SCHEMA
        or actual != EXPECTED_FILES
        or any(member.is_symlink() for member in members)
    ):
        raise ValueError("foreign artifact output directory")
    try:
        from tools.verify_rom_selector_text_bindings import verify_artifact
    except ModuleNotFoundError:
        from verify_rom_selector_text_bindings import verify_artifact
    report = verify_artifact(root, target)
    if report.get("verified") is not True:
        raise ValueError(
            f"existing artifact failed independent verification: {report.get('errors', [])}"
        )
    return target


def _replace_output(target: Path, files: dict[str, bytes]) -> None:
    _reject_symlink_components(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        _reject_symlink_components(target)
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        _reject_symlink_components(target.parent)
        os.replace(temporary, target)
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        if backup is not None and backup.exists():
            if target.exists():
                shutil.rmtree(target)
            os.replace(backup, target)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output))
    payload, bundle = _derive(root)
    files = {PAYLOAD_NAME: _canonical(payload), BUNDLE_NAME: bundle}
    files["manifest.json"] = _canonical(_manifest(payload, files))
    _replace_output(target, files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else args.root / args.output_dir
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
