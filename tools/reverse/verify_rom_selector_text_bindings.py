#!/usr/bin/env python3
"""Independently verify selector-bound text prefixes and configuration records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _denominator_digest(value: Any) -> str:
    return _digest(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _bounded(data: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError("selector-text verifier slice escapes input")
    return data[start:end]


def _word16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _word32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _thumb_bl(data: bytes, offset: int) -> int:
    first = _word16(data, offset)
    second = _word16(data, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("selector-text verifier BL encoding changed")
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return offset + 4 + delta


def _literal_address(offset: int, instruction: int, register: int) -> int:
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        raise ValueError("selector-text verifier literal load changed")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _root_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _source_evidence(
    rom: bytes, start: int, end: int, expected: str, label: str
) -> dict[str, Any]:
    if _digest(_bounded(rom, start, end)) != expected:
        raise ValueError(f"selector-text {label} source changed")
    return {
        "range": [start, end],
        "gba_range": [_gba(start), _gba(end)],
        "sha256": expected,
    }


def _raw_bl_sites(rom: bytes, target: int) -> list[int]:
    result = []
    for offset in range(0, len(rom) - 3, 2):
        first = _word16(rom, offset)
        second = _word16(rom, offset + 2)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            if _thumb_bl(rom, offset) == target:
                result.append(offset)
    return result


def _independent_source_records(rom: bytes) -> list[dict[str, Any]]:
    raw_table = _bounded(rom, SOURCE_START, SOURCE_END)
    if _digest(raw_table) != SOURCE_SHA256:
        raise ValueError("selector-text direct source table changed")
    records = []
    vector = []
    for source_id in range(SOURCE_COUNT):
        start = SOURCE_START + source_id * SOURCE_RECORD_SIZE
        row = _bounded(rom, start, start + SOURCE_RECORD_SIZE)
        if row[0] != source_id:
            raise ValueError("selector-text direct source identity changed")
        records.append(
            {
                "source_id": source_id,
                "name_slot": row[1],
                "range": [start, start + SOURCE_RECORD_SIZE],
                "sha256": _digest(row),
            }
        )
        vector.append([source_id, start, row[0], row[1]])
    slots = [record["name_slot"] for record in records]
    if (
        tuple(slots) != EXPECTED_DIRECT_NAME_SLOTS
        or len(set(slots)) != SOURCE_COUNT
        or _denominator_digest(vector) != SOURCE_VECTOR_SHA256
        or _denominator_digest(slots) != DIRECT_NAME_SLOT_VECTOR_SHA256
        or _denominator_digest(sorted(slots)) != DIRECT_NAME_SLOT_SET_SHA256
    ):
        raise ValueError("selector-text direct source slot domain changed")
    return records


def _independent_direct_producer_contract(rom: bytes) -> dict[str, Any]:
    enumerator = _source_evidence(
        rom, *ENUMERATOR_RANGE, ENUMERATOR_SHA256, "direct enumerator"
    )
    lifecycle = _source_evidence(rom, *LIFECYCLE_RANGE, LIFECYCLE_SHA256, "lifecycle")
    menu = _source_evidence(rom, *MENU_RANGE, MENU_SHA256, "menu selector")
    records = _independent_source_records(rom)
    enum_tail = tuple(_word16(rom, offset) for offset in range(0x08A6EC, 0x08A6FA, 2))
    first_formula = tuple(_word16(rom, offset) for offset in range(0x08B2D8, 0x08B2E8, 2))
    second_formula = tuple(_word16(rom, offset) for offset in range(0x08B500, 0x08B512, 2))
    if (
        _literal_address(0x08A6B0, _word16(rom, 0x08A6B0), 6) != SOURCE_LITERAL
        or _word32(rom, SOURCE_LITERAL) != ROM_BASE + SOURCE_START
        or _word32(rom, PROFILE_TABLE_LITERAL) != 0x085A143C
        or _word16(rom, 0x08A6BC) != 0x7870
        or _thumb_bl(rom, 0x08A6BE) != 0x068EA4
        or enum_tail != (0x0249, 0x1850, 0x3614, 0x0C05, 0x1400, 0x282D, 0xDDE0)
        or _thumb_bl(rom, 0x08B5FE) != ENUMERATOR_RANGE[0]
        or _thumb_bl(rom, 0x08B640) != MENU_RANGE[0]
        or first_formula != (0x7879, 0x1840, 0x7801, 0x0088, 0x1840, 0x0080, 0x4959, 0x1840)
        or second_formula != (0x1CF8, 0x7879, 0x1840, 0x7801, 0x0088, 0x1840, 0x0080, 0x491B, 0x1840)
        or _word32(rom, 0x08B44C) != ROM_BASE + SOURCE_START
        or _word32(rom, 0x08B57C) != ROM_BASE + SOURCE_START
        or _thumb_bl(rom, 0x08B420) != DIRECT_CONSUMER_RANGE[0]
        or _thumb_bl(rom, 0x08B51A) != DIRECT_CONSUMER_RANGE[0]
    ):
        raise ValueError("selector-text direct producer semantics changed")
    sites = _raw_bl_sites(rom, DIRECT_CONSUMER_RANGE[0])
    if sites != [0x08B420, 0x08B51A]:
        raise ValueError("selector-text direct callsite denominator changed")
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
        "direct_consumer_callsites": sites,
    }


def _independent_consumer_contract(rom: bytes) -> dict[str, Any]:
    direct = _source_evidence(
        rom, *DIRECT_CONSUMER_RANGE, DIRECT_CONSUMER_SHA256, "direct consumer"
    )
    config = _source_evidence(
        rom, *CONFIG_CONSUMER_RANGE, CONFIG_CONSUMER_SHA256, "config consumer"
    )
    producer = _source_evidence(
        rom, *SELECTOR_PRODUCER_RANGE, SELECTOR_PRODUCER_SHA256, "selector producer"
    )
    mapper = _source_evidence(
        rom, *SELECTOR_MAPPER_RANGE, SELECTOR_MAPPER_SHA256, "selector mapper"
    )
    copy_parser = _source_evidence(
        rom, *COPY_PARSER_RANGE, COPY_PARSER_SHA256, "copy parser"
    )
    bridge = _source_evidence(
        rom, *RENDERER_BRIDGE_RANGE, RENDERER_BRIDGE_SHA256, "renderer bridge"
    )
    renderer = _source_evidence(
        rom, *RENDERER_PARSER_RANGE, RENDERER_PARSER_SHA256, "renderer parser"
    )
    direct_formula = tuple(_word16(rom, offset) for offset in range(0x08B02C, 0x08B03A, 2))
    config_formula = tuple(_word16(rom, offset) for offset in range(0x08CD86, 0x08CD92, 2))
    copy_loop = tuple(_word16(rom, offset) for offset in range(0x09C514, 0x09C526, 2))
    mapper_words = tuple(
        _word16(rom, SELECTOR_MAPPER_RANGE[0] + index * 2) for index in range(26)
    )
    expected_mapper = (
        0xB500, 0x0400, 0x1400, 0x2801, 0xDD11, 0x2808, 0xDD0D, 0x2817,
        0xDD0D, 0x281E, 0xDC01, 0x2002, 0xE00A, 0x2832, 0xDD07, 0x2833,
        0xD003, 0x2834, 0xD003, 0x2835, 0xD101, 0x2001, 0xE000, 0x2000,
        0xBC02, 0x4708,
    )
    if (
        direct_formula != (0x7871, 0x0088, 0x1840, 0x0080, 0x1A40, 0x4913, 0x1840)
        or _word32(rom, DIRECT_TABLE_LITERAL) != ROM_BASE + DIRECT_START
        or _thumb_bl(rom, 0x08B044) != RENDERER_BRIDGE_RANGE[0]
        or _word32(rom, POINTER_TABLE_LITERAL) != ROM_BASE + POINTER_START
        or _word32(rom, RUNTIME_STATE_LITERAL) != 0x020311D4
        or _word32(rom, PHYSICAL_TABLE_LITERAL) != ROM_BASE + PHYSICAL_START
        or config_formula != (0x7820, 0x00C1, 0x1809, 0x0049, 0x4828, 0x1809)
        or _thumb_bl(rom, 0x08CD94) != COPY_PARSER_RANGE[0]
        or copy_loop != (0x7810, 0x7018, 0x0600, 0x3201, 0x3301, 0x2800, 0xD1F8, 0x1C30, 0xBD70)
        or mapper_words != expected_mapper
        or _thumb_bl(rom, 0x097C7E) != SELECTOR_MAPPER_RANGE[0]
        or _word16(rom, 0x097C82) != 0x7520
        or _thumb_bl(rom, 0x06678A) != RENDERER_PARSER_RANGE[0]
    ):
        raise ValueError("selector-text consumer or parser semantics changed")
    return {
        "direct_text_consumer": {
            **direct,
            "index_load_offset": 0x08B02C,
            "record_stride": DIRECT_SLOT_SIZE,
            "table_literal_offset": DIRECT_TABLE_LITERAL,
            "table_address": _gba(DIRECT_START),
            "renderer_call_offset": 0x08B044,
            "renderer_bridge_target": _gba(RENDERER_BRIDGE_RANGE[0]),
        },
        "configured_text_consumer": {
            **config,
            "pointer_table_literal_offset": POINTER_TABLE_LITERAL,
            "runtime_selector_address": "0x020311E8",
            "physical_table_literal_offset": PHYSICAL_TABLE_LITERAL,
            "record_stride": PHYSICAL_SLOT_SIZE,
            "copy_call_offset": 0x08CD94,
            "copy_parser_target": _gba(COPY_PARSER_RANGE[0]),
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


def _independent_sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    raw = _bounded(rom, SJIS_TABLE, SJIS_TABLE_END)
    if _digest(raw) != SJIS_TABLE_SHA256:
        raise ValueError("selector-text character-range table changed")
    result = []
    for index in range(SJIS_RANGE_COUNT):
        row = _bounded(
            rom,
            SJIS_TABLE + index * SJIS_ENTRY_SIZE,
            SJIS_TABLE + index * SJIS_ENTRY_SIZE + 3,
        )
        lower = row[0] | row[1] << 8
        result.append((lower, lower + row[2]))
    return tuple(result)


def _independent_renderer_end(
    data: bytes,
    cursor: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> int:
    if not 0 <= cursor < limit <= len(data):
        raise ValueError("selector-text renderer bounds changed")
    while cursor < limit:
        value = data[cursor]
        if value == 0:
            return cursor + 1
        if value == 1:
            step = 2
        elif value == 2:
            step = 3
        elif 0x80 <= value <= 0x9F:
            step = 2
        elif value >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("selector-text renderer truncated pair")
            pair = value * 0x100 + data[cursor + 1]
            step = 2 if any(lower <= pair < upper for lower, upper in sjis_ranges) else 1
        else:
            step = 1
        if cursor + step > limit:
            raise ValueError("selector-text renderer truncated command")
        cursor += step
    raise ValueError("selector-text renderer lacks bounded NUL terminator")


def _independent_nul_end(data: bytes, start: int, limit: int) -> int:
    if not 0 <= start < limit <= len(data):
        raise ValueError("selector-text copy bounds changed")
    for cursor in range(start, limit):
        if data[cursor] == 0:
            return cursor + 1
    raise ValueError("selector-text copy record lacks bounded NUL terminator")


def _independent_record(
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
    raw = _bounded(rom, start, physical_end)
    if not start < end <= physical_end or rom[end - 1] != 0:
        raise ValueError("selector-text parser boundary changed")
    suffix = _bounded(rom, end, physical_end)
    if any(suffix):
        raise ValueError("selector-text observed suffix changed")
    record = {
        "record_id": record_id,
        "slot_id": slot_id,
        "physical_range": [start, physical_end],
        "physical_sha256": _digest(raw),
        "consumed_range": [start, end],
        "consumed_size": end - start,
        "consumed_sha256": _digest(_bounded(rom, start, end)),
        "terminator_offset": end - start - 1,
        "unclassified_suffix_range": [end, physical_end],
        "unclassified_suffix_size": physical_end - end,
        "unclassified_suffix_zero_filled": True,
    }
    if source_id is not None:
        record["source_id"] = source_id
    return record


def _independent_direct_text_records(
    rom: bytes, source_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ranges = _independent_sjis_ranges(rom)
    result = []
    for source in source_records:
        source_id = int(source["source_id"])
        slot = int(source["name_slot"])
        start = DIRECT_START + slot * DIRECT_SLOT_SIZE
        end = _independent_renderer_end(rom, start, start + DIRECT_SLOT_SIZE, ranges)
        result.append(
            _independent_record(
                rom,
                record_id=f"direct-source-{source_id:02d}-slot-{slot:02d}",
                source_id=source_id,
                slot_id=slot,
                start=start,
                slot_size=DIRECT_SLOT_SIZE,
                end=end,
            )
        )
    if _denominator_digest([record["consumed_range"] for record in result]) != DIRECT_RECORD_RANGE_SHA256:
        raise ValueError("selector-text direct range denominator changed")
    return result


def _independent_config_inventory(
    rom: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if _digest(_bounded(rom, PHYSICAL_START, PHYSICAL_END)) != PHYSICAL_SHA256:
        raise ValueError("selector-text physical table changed")
    if _digest(_bounded(rom, CONFIG_START, CONFIG_END)) != CONFIG_SHA256:
        raise ValueError("selector-text config lists changed")
    if _digest(_bounded(rom, POINTER_START, POINTER_END)) != POINTER_SHA256:
        raise ValueError("selector-text config pointers changed")
    pointers = [_word32(rom, POINTER_START + index * 4) for index in range(3)]
    starts = [pointer - ROM_BASE for pointer in pointers]
    if tuple(starts) != EXPECTED_LIST_STARTS:
        raise ValueError("selector-text list pointer denominator changed")
    all_records = []
    lists = []
    vector = []
    for list_index, start in enumerate(starts):
        limit = starts[list_index + 1] if list_index < 2 else CONFIG_END
        cursor = start
        records = []
        while cursor < limit:
            row = _bounded(rom, cursor, cursor + 4)
            if row == b"\xFF\x00\x00\x00":
                terminator = {"range": [cursor, cursor + 4], "sha256": _digest(row)}
                cursor += 4
                break
            if row[1] != 0 or not 0 < row[0] < PHYSICAL_SLOT_COUNT:
                raise ValueError("selector-text config record changed")
            record_index = len(records)
            record = {
                "record_id": f"config-{list_index}-{record_index:02d}",
                "list_index": list_index,
                "record_index": record_index,
                "range": [cursor, cursor + 4],
                "text_slot": row[0],
                "reserved_zero": row[1],
                "x": row[2],
                "y": row[3],
                "sha256": _digest(row),
            }
            records.append(record)
            all_records.append(record)
            vector.append([list_index, record_index, cursor, row[0], row[2], row[3]])
            cursor += 4
        else:
            raise ValueError("selector-text config list lacks terminator")
        if cursor != limit or len(records) != EXPECTED_RECORD_COUNTS[list_index]:
            raise ValueError("selector-text config list denominator changed")
        lists.append(
            {
                "list_index": list_index,
                "range": [start, limit],
                "record_count": len(records),
                "records": records,
                "terminator": terminator,
            }
        )
    if _denominator_digest(vector) != CONFIG_RECORD_DENOMINATOR_SHA256:
        raise ValueError("selector-text config vector changed")
    referenced = sorted(record["text_slot"] for record in all_records)
    if (
        tuple(referenced) != REFERENCED_IDS
        or len(set(referenced)) != len(referenced)
        or _denominator_digest(referenced) != REFERENCED_IDS_SHA256
    ):
        raise ValueError("selector-text referenced slots changed")
    text_records = []
    for slot in referenced:
        start = PHYSICAL_START + slot * PHYSICAL_SLOT_SIZE
        end = _independent_nul_end(rom, start, start + PHYSICAL_SLOT_SIZE)
        text_records.append(
            _independent_record(
                rom,
                record_id=f"configured-slot-{slot:02d}",
                slot_id=slot,
                start=start,
                slot_size=PHYSICAL_SLOT_SIZE,
                end=end,
            )
        )
    if _denominator_digest([record["consumed_range"] for record in text_records]) != CONFIGURED_RECORD_RANGE_SHA256:
        raise ValueError("selector-text configured range denominator changed")
    return (
        {
            "range": [CONFIG_START, CONFIG_END],
            "sha256": CONFIG_SHA256,
            "record_size": 4,
            "record_counts": list(EXPECTED_RECORD_COUNTS),
            "records": all_records,
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
                        "file_offset": starts[index],
                    }
                    for index, pointer in enumerate(pointers)
                ],
            },
        },
        text_records,
    )


def _independent_classified_ranges(
    rom: bytes,
    direct_records: list[dict[str, Any]],
    configured_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bytes]:
    specs = [
        (record["record_id"], "direct_renderer_text_prefix", record["consumed_range"])
        for record in direct_records
    ]
    specs += [
        (record["record_id"], "configured_copy_text_prefix", record["consumed_range"])
        for record in configured_records
    ]
    specs += [
        ("config-lists", "selector_configuration_lists", [CONFIG_START, CONFIG_END]),
        (
            "config-pointers",
            "selector_configuration_pointer_table",
            [POINTER_START, POINTER_END],
        ),
    ]
    specs.sort(key=lambda item: (item[2][0], item[2][1], item[0]))
    result = []
    packed = 0
    for range_id, kind, value in specs:
        start, end = value
        raw = _bounded(rom, start, end)
        result.append(
            {
                "range_id": range_id,
                "kind": kind,
                "range": value,
                "size": len(raw),
                "sha256": _digest(raw),
                "packed_range": [packed, packed + len(raw)],
            }
        )
        packed += len(raw)
    denominator = [item["range"] for item in result]
    if _denominator_digest(denominator) != CLASSIFIED_RANGE_SHA256:
        raise ValueError("selector-text classified denominator changed")
    if any(left[1] > right[0] for left, right in zip(denominator, denominator[1:])):
        raise ValueError("selector-text classified ranges overlap")
    bundle = b"".join(_bounded(rom, start, end) for start, end in denominator)
    if len(bundle) != 816 or _digest(bundle) != BUNDLE_SHA256:
        raise ValueError("selector-text bundle changed")
    return result, bundle


def _expected(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    producer = _independent_direct_producer_contract(rom)
    semantics = _independent_consumer_contract(rom)
    source_records = _independent_source_records(rom)
    if _digest(_bounded(rom, DIRECT_START, DIRECT_OBSERVED_END)) != DIRECT_OBSERVED_SHA256:
        raise ValueError("selector-text observed direct range changed")
    direct_records = _independent_direct_text_records(rom, source_records)
    config, configured_records = _independent_config_inventory(rom)
    ranges, bundle = _independent_classified_ranges(rom, direct_records, configured_records)
    implementation = {
        label: {"path": path, "sha256": _digest(_root_file(root, path).read_bytes())}
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
        "classified_range_count": len(ranges),
        "classified_bytes": len(bundle),
        "parse_failure_count": 0,
        "range_overlap_bytes": 0,
        "packed_bytes": len(bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError("selector-text summary changed")
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "direct_source_table": {
            "range": [SOURCE_START, SOURCE_END],
            "gba_range": [_gba(SOURCE_START), _gba(SOURCE_END)],
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
        "classified_ranges": ranges,
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


def _expected_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "files": {name: _digest(content) for name, content in sorted(files.items())},
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


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact file is missing or a symlink: {name}")
    resolved = path.resolve(strict=True)
    if artifact not in resolved.parents:
        raise ValueError(f"artifact file escapes directory: {name}")
    return resolved


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": [],
        "summary": {},
    }
    try:
        root = Path(root).resolve(strict=True)
        requested = Path(artifact_dir)
        if not requested.is_absolute():
            requested = root / requested
        if requested.is_symlink():
            raise ValueError("artifact directory must not be a symlink")
        artifact = requested.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact path is not a directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact contains symlink members")
        actual_files = {
            member.relative_to(artifact).as_posix() for member in members if member.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError("artifact file set changed")
        rom = _root_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256:
            raise ValueError("base ROM identity mismatch")
        expected_payload, expected_bundle = _expected(root, rom)
        expected_payload_bytes = _canonical(expected_payload)
        payload_bytes = _artifact_file(artifact, PAYLOAD_NAME).read_bytes()
        if payload_bytes != expected_payload_bytes:
            raise ValueError("artifact payload differs from independent reconstruction")
        bundle = _artifact_file(artifact, BUNDLE_NAME).read_bytes()
        if bundle != expected_bundle:
            raise ValueError("artifact bundle differs from independent reconstruction")
        files = {PAYLOAD_NAME: expected_payload_bytes, BUNDLE_NAME: expected_bundle}
        expected_manifest = _expected_manifest(expected_payload, files)
        manifest = json.loads(_artifact_file(artifact, "manifest.json").read_text(encoding="utf-8"))
        if manifest != expected_manifest:
            raise ValueError("artifact manifest differs from independent reconstruction")
        for name, digest in manifest["files"].items():
            if _digest(_artifact_file(artifact, name).read_bytes()) != digest:
                raise ValueError(f"artifact file hash mismatch: {name}")
        report["verified"] = True
        report["summary"] = expected_payload["summary"]
        report["rom_sha256"] = ROM_SHA256
        report["artifact_schema"] = SCHEMA
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
