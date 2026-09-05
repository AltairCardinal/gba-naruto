#!/usr/bin/env python3
"""Independently verify the nine fixed consumer renderer text tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-fixed-consumer-text-inventory-v1"
VERIFY_SCHEMA = "rom-fixed-consumer-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

PARSER_RANGE = (0x06626C, 0x066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
BRIDGE_RANGE = (0x066758, 0x066790)
BRIDGE_SHA256 = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
BRIDGE_CALL = 0x06678A
SJIS_LOOKUP_RANGE = (0x065E80, 0x065EB6)
SJIS_LOOKUP_SHA256 = "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e"
SJIS_TABLE = 0x53D644
SJIS_RANGE_COUNT = 31
SJIS_ENTRY_SIZE = 8
SJIS_TABLE_END = SJIS_TABLE + SJIS_RANGE_COUNT * SJIS_ENTRY_SIZE
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "fixed-consumer-text-inventory.json"
BUNDLE_NAME = "fixed-consumer-text-bytes.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
RECORD_RANGE_DENOMINATOR_SHA256 = (
    "fa0faadae92918131418cf5ce089503550bbd87edc85e5dfa354b6fbe9f3d551"
)
CLASSIFIED_RANGE_DENOMINATOR_SHA256 = (
    "6edb4c9593886acdce149cc1a9e5defbba5289105abd1f6bae026fa126de20c3"
)
BUNDLE_SHA256 = "e71eefd9ee1d98333fdd0cd72c6b67ce6335a6874bf5f92c072177807ca1168a"

EXPECTED_SUMMARY = {
    "pointer_table_count": 11,
    "pointer_slot_count": 750,
    "null_pointer_slot_count": 11,
    "pointer_table_bytes": 3_000,
    "unique_target_count": 735,
    "renderer_record_count": 735,
    "renderer_consumed_bytes": 11_177,
    "classified_range_count": 746,
    "classified_bytes": 14_177,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 14_177,
}
SCOPE = {
    "nine_fixed_pointer_table_ranges_complete": True,
    "fixed_pointer_slot_denominator_complete": True,
    "null_pointer_slots_explicit": True,
    "pointer_table_byte_union_complete": True,
    "consumer_typed_target_set_complete": True,
    "renderer_consumed_byte_union_complete": True,
    "runtime_index_bounds_proven": False,
    "natural_gameplay_index_coverage_complete": False,
    "inter_record_padding_classified": False,
    "unicode_decoding_complete": False,
}
LIMITATIONS = [
    "Only the nine explicitly frozen table ranges, their 575 slots, and the 570 unique renderer-consumed targets are classified.",
    "Static consumers prove table-to-parser provenance but do not prove that every runtime index is bounded by the physical table length.",
    "Inter-record gaps, zero padding, and the mixed residual range at 0x005A65EC remain unknown.",
    "The mixed 24-slot UI resource table at 0x005A7FCC is excluded because no producer proves that its text-only 18-slot prefix is the complete runtime domain.",
    "Natural gameplay execution of every slot and Unicode decoding are outside this artifact's denominator.",
]


def _contract(
    table_id: str,
    semantic_type: str,
    start: int,
    entry_count: int,
    table_sha256: str,
    after_word_hex: str,
    unique_target_count: int,
    renderer_consumed_bytes: int,
    range_sha256: str,
    content_sha256: str,
    null_slot_count: int = 0,
    boundary_kind: str = "non_pointer_after_word",
) -> dict[str, Any]:
    return locals()


TABLE_CONTRACTS = (
    _contract(
        "ui_summary_name_9",
        "ui_summary_renderer_name_pointer_table",
        0x5A65C8,
        9,
        "5180da939a292991fdb3995bfad4179f9768f6d716b70db49f4367c970dea368",
        "8faa99b3",
        9,
        383,
        "424e8f14c6cab760d69168d9e205d1289317f73cf8080bdeba0203787f33dcfb",
        "b6012af7de277b10738695f60258ded193282f4cdd7e5b55e18f995683d359c5",
    ),
    _contract(
        "low_detail_action_name_87",
        "low_detail_action_renderer_name_pointer_table",
        0x5A6D04,
        87,
        "a9bd263418cf363d7ff4280490576c650a236b6ffe01497a01a79b2edc24e091",
        "8bca9154",
        86,
        728,
        "6ee106c30fad6407a520e2006bb3ec9419ebb743bec08a8b9eece2645f0cd26e",
        "eeade5513e54c33b25b1f9de705d38fb0e320a0401484715750cba8c437b8457",
    ),
    _contract(
        "passive_auxiliary_text_45",
        "passive_auxiliary_renderer_text_pointer_table",
        0x5A7060,
        45,
        "1231c8f3ac946f9138d1becab3a330aed1421bedc698c746471e7b4157206b71",
        "8bca9154",
        44,
        364,
        "1190e1e0a03e16a10f3ad82ec91b96acaee7ff3521dba5092ea99684f329113b",
        "3a7be0417d8e9fb14e23f32a01491f62a0251374048de7166ba8ed7ce835cb8b",
    ),
    _contract(
        "passive_detail_name_45",
        "passive_detail_renderer_name_pointer_table",
        0x5A73E0,
        45,
        "3bb9d9c1e7d4d2d58c12a1167d3598c48fa693384d9746639e70a06a75d1e829",
        "95ab9ca0",
        44,
        364,
        "7a3fbf4bff2d122a1a26c6a314a7e470b7a7cfc67b73cde96f6f0ed3faf09f69",
        "6c3f548f7f13e949bd1c3484b54bf5dfd6e636a24adba9ef65645973cbe27d1b",
    ),
    _contract(
        "ninja_tool_detail_name_94",
        "ninja_tool_detail_renderer_name_pointer_table",
        0x5A7C50,
        94,
        "403cb842a3018e1da6fcbd8cbca9bb55f554cc17065499c76c7214088f932d65",
        "96f79a58",
        93,
        917,
        "aa20fef1b3e297687af9bfd04698f9df842411cf63446486571f6f174499c02f",
        "a2782fb41080d1b3c936a8d804dbcfd3c6ec30c985c4f043ab2e9ff5c3dac441",
    ),
    _contract(
        "unit_name_63",
        "unit_name_renderer_text_pointer_table",
        0x599280,
        63,
        "68e8c6fc03c6a321ef701611aea372dd88e22aa16bd795706ec6e8ddb6946a1d",
        "171f0008",
        63,
        447,
        "429697081a829342e4f21f087ba7a4239de62c3cf8d2f88a36d024d60b360122",
        "9a34123e3856d26a2447a41f8423ce74983f937eab02243b94c9b5f5e0c3f2f9",
        boundary_kind="adjacent_fixed_table_start",
    ),
    _contract(
        "active_action_name_87",
        "active_action_name_renderer_text_pointer_table",
        0x59937C,
        87,
        "72c9247c5660a892890fb85da8606d9d47a3d15e01d06aee53dff7f5189145ac",
        "00000000",
        87,
        731,
        "6f2b9605fcb39ce8a5e8f2bb6a7fda08eb0a6195ad5ab73fee4bf46c02919da6",
        "1b15b93d292de6af6c84ed3a7c5c0851c84d06cde6b8d21e4bd8387971848ad5",
    ),
    _contract(
        "message_command_text_100",
        "message_command_renderer_text_pointer_table",
        0x599634,
        100,
        "cedf35c21b949aeacd8accf29a96856ed1595d3434f2b46bd2c893049fc6410f",
        "aa330008",
        99,
        1_065,
        "77e2cd0c4f35d75a0dea2005c511895a053471dd893b1121b4d1e8ca8f834c35",
        "000f6e4ee266144bc3cc44393471695336b171cd805f9d0467eda2c0e7019a50",
        null_slot_count=1,
        boundary_kind="consumer_index_upper_bound",
    ),
    _contract(
        "passive_description_45",
        "passive_description_renderer_text_pointer_table",
        0x5AAEDC,
        45,
        "1c1d5f7bad33686bc3c0f51c2f057bb7778d8dccedfc65104720376dc5eb200f",
        "92599a9a",
        45,
        1_781,
        "66fe87633a19b6218bd66ecb2aae1028c4f47d50711121f5dec34be5a86d51bc",
        "edebb994d020aca3e8fd4144b6455f94fbae044f9abf1cbb5b66b62a63934456",
    ),
    _contract(
        "active_action_description_87",
        "active_action_description_renderer_text_pointer_table",
        0x5994D8, 87,
        "55eb1e146e7f3f77672fe9508571e3393280821e001f80493b61b4cb8c2207d0",
        "88220008", 77, 1_837,
        "54d3f68236a7c5da25a83bcc8bae9e0723c27e60e85bfc7a9ecd69a27910fe40",
        "b8f71706da9b99d0a93e4452a6dc8d3cc88760555f8b177986c806f8cd3ff6fd",
        null_slot_count=10, boundary_kind="adjacent_fixed_table_start",
    ),
    _contract(
        "ninja_tool_description_suffix_88",
        "ninja_tool_description_renderer_text_pointer_table_suffix",
        0x5997C4, 88,
        "f27b28abedfe7a437f4843ba6c824e4c761655892d0bc4978a5f757e6e4fbb8e",
        "00000000", 88, 2_560,
        "930bb99cad1cf5ff7d0ed1a9dc2a3a0840ac206a893884f2a0979f47d100e5eb",
        "58dba410813b6428516a362158381bd96efffe99770aa26a4ba994841d0a01cf",
    ),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _range_hash(ranges: list[list[int]]) -> str:
    return _sha(json.dumps(ranges, separators=(",", ":")).encode("ascii"))


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = path.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink():
        raise ValueError(f"artifact member must not be a symlink: {name}")
    resolved = path.resolve(strict=True)
    if artifact != resolved and artifact not in resolved.parents:
        raise ValueError(f"artifact member escapes directory: {name}")
    if not resolved.is_file():
        raise ValueError(f"artifact member is not a file: {name}")
    return resolved


def _take(data: bytes, start: int, size: int) -> bytes:
    if start < 0 or size <= 0 or start + size > len(data):
        raise ValueError(f"invalid bounded range at 0x{start:06X}")
    return data[start : start + size]


def _word(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _take(rom, offset, 4))[0]


def _half(rom: bytes, offset: int) -> int:
    return int.from_bytes(_take(rom, offset, 2), "little")


def _assert_contract(
    rom: bytes, offset: int, expected: tuple[int, ...], label: str
) -> None:
    actual = tuple(_half(rom, offset + index * 2) for index in range(len(expected)))
    if actual != expected:
        raise ValueError(f"fixed consumer contract differs: {label}")


def _literal_target(offset: int, instruction: int, register: int) -> int:
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        raise ValueError("fixed consumer literal contract differs")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _thumb_call(rom: bytes, offset: int) -> int:
    first = _half(rom, offset)
    second = _half(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"fixed consumer call contract differs at 0x{offset:06X}")
    delta = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _evidence(
    rom: bytes, bounds: tuple[int, int], digest: str, label: str
) -> dict[str, Any]:
    start, end = bounds
    if _sha(_take(rom, start, end - start)) != digest:
        raise ValueError(f"fixed consumer evidence differs: {label}")
    return {
        "range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": digest,
    }


def _decode_consumer_contract(rom: bytes) -> dict[str, Any]:
    consumers: dict[str, dict[str, Any]] = {}

    ui = (0x4911, 0x00A8, 0x1840, 0x6801, 0x1C20, 0xF7ED, 0xFF14)
    _assert_contract(rom, 0x078436, ui, "ui-summary")
    if (
        _literal_target(0x078436, ui[0], 1) != 0x07847C
        or _word(rom, 0x07847C) != ROM_BASE + 0x5A65C8
        or _thumb_call(rom, 0x078440) != PARSER_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: ui-summary data flow")
    consumers["ui_summary_name_9"] = {
        "instruction_ranges": [[0x078436, 0x078444]],
        "table_literal_offset": 0x07847C,
        "index_source": "r5_u8_domain_from_ui_state",
        "index_scale": 4,
        "pointer_load_offset": 0x07843C,
        "parser_call_offset": 0x078440,
        "parser_call_target": _addr(PARSER_RANGE[0]),
    }

    action = (
        0x4912,
        0x7828,
        0x0080,
        0x1840,
        0x6800,
        0x9B1C,
        0x9C18,
        0x4323,
        0x17DB,
        0x2602,
        0x4033,
        0x9200,
        0x2100,
        0x2202,
        0xF7F5,
        0xFAE1,
    )
    _assert_contract(rom, 0x071176, action, "action-name")
    if (
        _literal_target(0x071176, action[0], 1) != 0x0711C0
        or _word(rom, 0x0711C0) != ROM_BASE + 0x5A6D04
        or _thumb_call(rom, 0x071192) != BRIDGE_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: action-name data flow")
    consumers["low_detail_action_name_87"] = {
        "instruction_ranges": [[0x071176, 0x071196]],
        "table_literal_offset": 0x0711C0,
        "index_source": "record_u8_bit7_clear_branch",
        "index_scale": 4,
        "pointer_load_offset": 0x07117E,
        "bridge_call_offset": 0x071192,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    auxiliary = (
        0x4A10,
        0x490C,
        0x00A4,
        0x20BC,
        0x4370,
        0x1824,
        0x1864,
        0x3454,
        0x7820,
        0x0080,
        0x1880,
        0x6800,
        0x9700,
        0x2101,
        0x2202,
        0x230B,
        0xF7E4,
        0xFF4B,
    )
    _assert_contract(rom, 0x08189E, auxiliary, "passive-auxiliary")
    if (
        _literal_target(0x08189E, auxiliary[0], 2) != 0x0818E0
        or _word(rom, 0x0818E0) != ROM_BASE + 0x5A7060
        or _thumb_call(rom, 0x0818BE) != BRIDGE_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: passive-auxiliary data flow")
    consumers["passive_auxiliary_text_45"] = {
        "instruction_ranges": [[0x08189E, 0x0818C2]],
        "table_literal_offset": 0x0818E0,
        "index_source": "materialized_record_plus_0x54_u8",
        "index_scale": 4,
        "pointer_load_offset": 0x0818B4,
        "bridge_call_offset": 0x0818BE,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    passive_lookup = (
        0x4909,
        0x7990,
        0x0080,
        0x1840,
        0x6801,
        0x79D0,
        0x0080,
        0x4448,
        0x3051,
        0x7805,
        0xE012,
    )
    passive_render = (
        0x78F2,
        0x3201,
        0x0612,
        0x0E12,
        0x2000,
        0x9000,
        0x1C08,
        0x2100,
        0x2300,
        0xF7ED,
        0xFF7A,
    )
    _assert_contract(rom, 0x078812, passive_lookup, "passive-detail lookup")
    _assert_contract(rom, 0x07884E, passive_render, "passive-detail render")
    if (
        _literal_target(0x078812, passive_lookup[0], 1) != 0x078838
        or _word(rom, 0x078838) != ROM_BASE + 0x5A73E0
        or _thumb_call(rom, 0x078860) != BRIDGE_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: passive-detail data flow")
    consumers["passive_detail_name_45"] = {
        "instruction_ranges": [[0x078812, 0x078828], [0x07884E, 0x078864]],
        "table_literal_offset": 0x078838,
        "index_source": "battle_record_plus_6_u8_when_type_is_4",
        "index_scale": 4,
        "pointer_load_offset": 0x07881A,
        "bridge_call_offset": 0x078860,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    skill = (
        0x4932,
        0x7828,
        0x2481,
        0x4264,
        0x4020,
        0x0080,
        0x1840,
        0x6800,
        0x9B1C,
        0x9918,
        0x430B,
        0x17DB,
        0x2202,
        0x4013,
        0x2100,
        0x9100,
        0xF7F5,
        0xFAB6,
    )
    _assert_contract(rom, 0x0711C8, skill, "ninja-tool")
    if (
        _literal_target(0x0711C8, skill[0], 1) != 0x071294
        or _word(rom, 0x071294) != ROM_BASE + 0x5A7C50
        or _thumb_call(rom, 0x0711E8) != BRIDGE_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: ninja-tool data flow")
    consumers["ninja_tool_detail_name_94"] = {
        "instruction_ranges": [[0x0711C8, 0x0711EC]],
        "table_literal_offset": 0x071294,
        "index_source": "record_u8_masked_to_7_bits",
        "static_index_domain": [0, 127],
        "physical_table_entry_count": 94,
        "index_scale": 4,
        "pointer_load_offset": 0x0711D6,
        "bridge_call_offset": 0x0711E8,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    unit = (
        0x490D,
        0x480D,
        0x6840,
        0x30BC,
        0x7800,
        0x0080,
        0x1840,
        0x6800,
        0x2100,
        0x9100,
        0x2203,
        0x2301,
        0xF7F5,
        0xFC05,
    )
    _assert_contract(rom, 0x070F32, unit, "unit-name")
    if (
        _literal_target(0x070F32, unit[0], 1) != 0x070F68
        or _word(rom, 0x070F68) != ROM_BASE + 0x599280
        or _thumb_call(rom, 0x070F4A) != BRIDGE_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: unit-name data flow")
    consumers["unit_name_63"] = {
        "instruction_ranges": [[0x070F32, 0x070F4E]],
        "table_literal_offset": 0x070F68,
        "index_source": "unit_state_plus_0xbc_u8",
        "index_scale": 4,
        "pointer_load_offset": 0x070F40,
        "bridge_call_offset": 0x070F4A,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    active_head = (0x4901, 0x0090, 0xE007)
    active_tail = (
        0x1840,
        0x6800,
        0x2100,
        0x9100,
        0x2201,
        0x2301,
        0xF7ED,
        0xF82D,
    )
    _assert_contract(rom, 0x0796D8, active_head, "active-action-name lookup")
    _assert_contract(rom, 0x0796EE, active_tail, "active-action-name renderer")
    if (
        _literal_target(0x0796D8, active_head[0], 1) != 0x0796E0
        or _word(rom, 0x0796E0) != ROM_BASE + 0x59937C
        or _thumb_call(rom, 0x0796FA) != BRIDGE_RANGE[0]
    ):
        raise ValueError(
            "fixed consumer contract differs: active-action-name data flow"
        )
    consumers["active_action_name_87"] = {
        "instruction_ranges": [[0x0796D8, 0x0796DE], [0x0796EE, 0x0796FE]],
        "table_literal_offset": 0x0796E0,
        "index_source": "message_command_u8_low_branch",
        "index_scale": 4,
        "pointer_load_offset": 0x0796F0,
        "bridge_call_offset": 0x0796FA,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    message_gate = (
        0xB500,
        0xB081,
        0x0600,
        0x0E02,
        0x2AE3,
        0xD847,
        0x2080,
        0x4010,
        0x0600,
        0x0E01,
        0x2900,
        0xD131,
    )
    message_lookup = (
        0x4906,
        0x2081,
        0x4240,
        0x4010,
        0x0080,
        0x1840,
        0x6800,
        0x2100,
        0x9100,
        0x2201,
        0x2301,
        0xF7ED,
        0xF82D,
    )
    _assert_contract(rom, 0x079668, message_gate, "message-command upper bound")
    _assert_contract(rom, 0x0796E4, message_lookup, "message-command lookup")
    if (
        _literal_target(0x0796E4, message_lookup[0], 1) != 0x079700
        or _word(rom, 0x079700) != ROM_BASE + 0x599634
        or _thumb_call(rom, 0x0796FA) != BRIDGE_RANGE[0]
    ):
        raise ValueError("fixed consumer contract differs: message-command data flow")
    consumers["message_command_text_100"] = {
        "instruction_ranges": [[0x079668, 0x079680], [0x0796E4, 0x0796FE]],
        "table_literal_offset": 0x079700,
        "index_source": "message_command_u8_high_branch_masked_to_7_bits",
        "command_domain": [0x80, 0xE3],
        "static_index_domain": [0, 99],
        "index_scale": 4,
        "pointer_load_offset": 0x0796F0,
        "null_slot_indices": [94],
        "bridge_call_offset": 0x0796FA,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    active_description = (
        0x490B, 0x7828, 0x0080, 0x1840, 0x6800,
        0x9600, 0x2100, 0x2202, 0x2300, 0xF7F5, 0xFAD6,
    )
    _assert_contract(
        rom, 0x071196, active_description, "active-action-description"
    )
    if (
        _literal_target(0x071196, active_description[0], 1) != 0x0711C4
        or _word(rom, 0x0711C4) != ROM_BASE + 0x5994D8
        or _thumb_call(rom, 0x0711A8) != BRIDGE_RANGE[0]
    ):
        raise ValueError(
            "fixed consumer contract differs: active-action-description data flow"
        )
    consumers["active_action_description_87"] = {
        "instruction_ranges": [[0x071196, 0x0711AC]],
        "table_literal_offset": 0x0711C4,
        "index_source": "record_u8_bit7_clear_branch",
        "physical_table_entry_count": 87,
        "index_scale": 4,
        "pointer_load_offset": 0x07119C,
        "null_slot_indices": [0, 10, 11, 13, 17, 18, 20, 39, 40, 52],
        "bridge_call_offset": 0x0711A8,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    tool_description = (
        0x492A, 0x7828, 0x4020, 0x0080, 0x1840, 0x6800,
        0x2302, 0x9300, 0x2100, 0x2202, 0x2300, 0xF7F5, 0xFAA9,
    )
    _assert_contract(rom, 0x0711EC, tool_description, "ninja-tool-description")
    if (
        _literal_target(0x0711EC, tool_description[0], 1) != 0x071298
        or _word(rom, 0x071298) != ROM_BASE + 0x5997AC
        or _thumb_call(rom, 0x071202) != BRIDGE_RANGE[0]
    ):
        raise ValueError(
            "fixed consumer contract differs: ninja-tool-description data flow"
        )
    consumers["ninja_tool_description_suffix_88"] = {
        "instruction_ranges": [[0x0711EC, 0x071206]],
        "logical_table_start": 0x5997AC,
        "physical_primary_suffix_start": 0x5997C4,
        "overlapping_prefix_slot_indices": [0, 1, 2, 3, 4, 5],
        "table_literal_offset": 0x071298,
        "index_source": "record_u8_masked_to_7_bits",
        "logical_slot_domain": [0, 93],
        "primary_suffix_slot_domain": [6, 93],
        "index_scale": 4,
        "pointer_load_offset": 0x0711F6,
        "bridge_call_offset": 0x071202,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    description_index = (0x4808, 0x7991, 0x0089, 0x1808, 0x6803)
    description_lookup = (0x4806, 0x1808, 0x6807)
    description_render = (0x1C38, 0x2100, 0x1C22, 0x2300, 0xF7D3, 0xFFBA)
    _assert_contract(rom, 0x0926EC, description_index, "passive-description index")
    _assert_contract(rom, 0x092718, description_lookup, "passive-description lookup")
    _assert_contract(rom, 0x0927D8, description_render, "passive-description renderer")
    if (
        _literal_target(0x092718, description_lookup[0], 0) != 0x092734
        or _word(rom, 0x092734) != ROM_BASE + 0x5AAEDC
        or _thumb_call(rom, 0x0927E0) != BRIDGE_RANGE[0]
    ):
        raise ValueError(
            "fixed consumer contract differs: passive-description data flow"
        )
    consumers["passive_description_45"] = {
        "instruction_ranges": [
            [0x0926EC, 0x0926F6],
            [0x092718, 0x09271E],
            [0x0927D8, 0x0927E4],
        ],
        "table_literal_offset": 0x092734,
        "index_source": "type_4_record_plus_6_u8",
        "index_scale": 4,
        "pointer_load_offset": 0x09271C,
        "pointer_register": "r7",
        "bridge_source_forward_offset": 0x0927D8,
        "bridge_call_offset": 0x0927E0,
        "bridge_call_target": _addr(BRIDGE_RANGE[0]),
    }

    _assert_contract(rom, 0x066760, (0x4681,), "bridge source capture")
    _assert_contract(rom, 0x066788, (0x4649,), "bridge source forwarding")
    if _thumb_call(rom, BRIDGE_CALL) != PARSER_RANGE[0]:
        raise ValueError("fixed consumer contract differs: bridge-to-parser")

    _assert_contract(
        rom,
        0x065E88,
        (0x4C05, 0x00D0, 0x1901, 0x8808, 0x4298, 0xD807, 0x7889, 0x1840, 0x4298, 0xDD03),
        "SJIS range lookup",
    )
    _assert_contract(
        rom,
        0x065EA4,
        (0x1C50, 0x0600, 0x0E02, 0x2A1E, 0xD9ED, 0x20FF),
        "SJIS range count",
    )
    if (
        _literal_target(0x065E88, _half(rom, 0x065E88), 4) != 0x065EA0
        or _word(rom, 0x065EA0) != ROM_BASE + SJIS_TABLE
    ):
        raise ValueError("fixed consumer contract differs: SJIS table flow")
    _assert_contract(
        rom,
        0x066284,
        (
            0x291F,
            0xD829,
            0x7810,
            0x2802,
            0xD00E,
            0x2802,
            0xDC02,
            0x2801,
            0xD005,
            0xE10A,
            0x2803,
            0xD00F,
            0x280A,
            0xD012,
            0xE105,
            0x7850,
            0x74B0,
            0x9807,
            0x3002,
            0xE236,
            0x7850,
            0x81B0,
            0x9907,
            0x7888,
            0x81F0,
            0x3103,
            0x9107,
        ),
        "renderer control widths",
    )
    _assert_contract(
        rom,
        0x0662DC,
        (0x2800, 0xDA69, 0x299F, 0xD909, 0x7811, 0x0209, 0x7850, 0x4308, 0xF7FF, 0xFDC8, 0x0600, 0x0E00, 0x28FF, 0xD05D),
        "renderer high-byte branch",
    )
    if _thumb_call(rom, 0x0662EC) != SJIS_LOOKUP_RANGE[0]:
        raise ValueError("fixed consumer contract differs: renderer SJIS call")
    _assert_contract(rom, 0x06639C, (0x9807, 0x3002, 0x9007), "pair advance")
    _assert_contract(rom, 0x0664A4, (0x9807, 0x3001, 0x9007), "single advance")
    _assert_contract(
        rom,
        0x06671C,
        (0x9A07, 0x7810, 0x2800, 0xD000, 0xE5AB),
        "NUL termination",
    )

    return {
        "table_consumers": consumers,
        "renderer_path": {
            "bridge": _addr(BRIDGE_RANGE[0]),
            "bridge_source_capture_offset": 0x066760,
            "bridge_source_forward_offset": 0x066788,
            "parser_call_offset": BRIDGE_CALL,
            "parser": _addr(PARSER_RANGE[0]),
        },
        "renderer_grammar": {
            "terminator": 0,
            "control_01_width": 2,
            "control_02_width": 3,
            "high_80_9f_width": 2,
            "valid_sjis_pair_width": 2,
            "otherwise_width": 1,
            "sjis_lookup": _addr(SJIS_LOOKUP_RANGE[0]),
            "sjis_range_table": _addr(SJIS_TABLE),
            "sjis_range_count": SJIS_RANGE_COUNT,
            "sjis_entry_size": SJIS_ENTRY_SIZE,
        },
    }


def _independent_sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    result = []
    for index in range(SJIS_RANGE_COUNT):
        row = _take(rom, SJIS_TABLE + index * SJIS_ENTRY_SIZE, 3)
        lower = int.from_bytes(row[:2], "little")
        result.append((lower, lower + row[2]))
    return tuple(result)


def _independent_renderer_end(
    data: bytes,
    start: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> int:
    if start < 0 or start >= limit or limit > len(data):
        raise ValueError("renderer record has an invalid bounded range")
    cursor = start
    while cursor < limit:
        opcode = data[cursor]
        if opcode == 0:
            return cursor + 1
        if opcode == 1:
            step = 2
        elif opcode == 2:
            step = 3
        elif 0x80 <= opcode <= 0x9F:
            step = 2
        elif opcode >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("renderer record has a truncated high-byte pair")
            codepoint = opcode * 256 + data[cursor + 1]
            step = 2 if any(lo <= codepoint < hi for lo, hi in sjis_ranges) else 1
        else:
            step = 1
        if cursor + step > limit:
            raise ValueError("renderer record has a truncated control or pair")
        cursor += step
    raise ValueError("renderer record lacks a bounded terminator")


def _expected_payload(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    semantics = _decode_consumer_contract(rom)
    sjis = _independent_sjis_ranges(rom)
    table_records: list[dict[str, Any]] = []
    record_sources: dict[int, list[dict[str, Any]]] = {}
    record_ends: dict[int, int] = {}

    for contract in TABLE_CONTRACTS:
        start = contract["start"]
        end = start + contract["entry_count"] * 4
        raw = _take(rom, start, end - start)
        if _sha(raw) != contract["table_sha256"]:
            raise ValueError(f"fixed table differs: {contract['table_id']}")
        if _take(rom, end, 4).hex() != contract["after_word_hex"]:
            raise ValueError(f"fixed table boundary differs: {contract['table_id']}")
        after_word = _word(rom, end)
        boundary_kind = contract["boundary_kind"]
        if boundary_kind == "non_pointer_after_word" and (
            ROM_BASE <= after_word < ROM_BASE + len(rom)
        ):
            raise ValueError(f"fixed table boundary remains pointer-like: {contract['table_id']}")
        if boundary_kind == "adjacent_fixed_table_start" and not any(
            other["start"] == end for other in TABLE_CONTRACTS
        ):
            raise ValueError(f"fixed adjacent table boundary differs: {contract['table_id']}")
        if boundary_kind == "consumer_index_upper_bound" and semantics[
            "table_consumers"
        ][contract["table_id"]].get("static_index_domain") != [
            0,
            contract["entry_count"] - 1,
        ]:
            raise ValueError(f"fixed consumer-bounded table differs: {contract['table_id']}")
        if boundary_kind not in {
            "non_pointer_after_word",
            "adjacent_fixed_table_start",
            "consumer_index_upper_bound",
        }:
            raise ValueError(f"unsupported fixed table boundary: {contract['table_id']}")

        slots: dict[int, list[int]] = {}
        null_slot_indices = []
        for slot in range(contract["entry_count"]):
            pointer = _word(rom, start + slot * 4)
            if pointer == 0:
                null_slot_indices.append(slot)
                continue
            target = pointer - ROM_BASE
            if not 0 <= target < len(rom):
                raise ValueError(f"fixed table pointer escapes ROM: {contract['table_id']}[{slot}]")
            slots.setdefault(target, []).append(slot)
        if len(null_slot_indices) != contract["null_slot_count"]:
            raise ValueError(f"fixed null-slot denominator differs: {contract['table_id']}")
        targets = sorted(slots)
        if any(target >= start for target in targets):
            raise ValueError(f"fixed table target ordering differs: {contract['table_id']}")
        target_ranges = []
        target_content = bytearray()
        for index, target in enumerate(targets):
            limit = targets[index + 1] if index + 1 < len(targets) else start
            end_of_record = _independent_renderer_end(rom, target, limit, sjis)
            target_ranges.append([target, end_of_record])
            target_content.extend(rom[target:end_of_record])
            if target in record_ends:
                raise ValueError("fixed target appears in multiple table denominators")
            record_ends[target] = end_of_record
            record_sources[target] = [
                {"table_id": contract["table_id"], "slot_indices": slots[target]}
            ]
        if (
            len(targets) != contract["unique_target_count"]
            or len(target_content) != contract["renderer_consumed_bytes"]
            or _range_hash(target_ranges) != contract["range_sha256"]
            or _sha(bytes(target_content)) != contract["content_sha256"]
        ):
            raise ValueError(f"fixed target denominator differs: {contract['table_id']}")
        table_records.append(
            {
                "table_id": contract["table_id"],
                "semantic_type": contract["semantic_type"],
                "range": [start, end],
                "gba_range": [_addr(start), _addr(end)],
                "entry_count": contract["entry_count"],
                "entry_size": 4,
                "null_slot_count": len(null_slot_indices),
                "null_slot_indices": null_slot_indices,
                "unique_target_count": len(targets),
                "renderer_consumed_bytes": len(target_content),
                "sha256": contract["table_sha256"],
                "after_table_word_hex": contract["after_word_hex"],
                "boundary_kind": boundary_kind,
                "target_range_denominator_sha256": contract["range_sha256"],
                "target_content_sha256": contract["content_sha256"],
            }
        )

    records = []
    record_ranges = []
    for index, target in enumerate(sorted(record_ends)):
        end = record_ends[target]
        raw = rom[target:end]
        record_id = f"fixed-consumer-text-{index:03d}"
        records.append(
            {
                "record_id": record_id,
                "sources": record_sources[target],
                "range": [target, end],
                "gba_range": [_addr(target), _addr(end)],
                "size": len(raw),
                "sha256": _sha(raw),
            }
        )
        record_ranges.append([target, end])
    if _range_hash(record_ranges) != RECORD_RANGE_DENOMINATOR_SHA256:
        raise ValueError("fixed global record denominator differs")

    classified = [
        {
            "range_id": f"pointer-table-{table['table_id']}",
            "kind": "pointer_table",
            "semantic_type": table["semantic_type"],
            "table_id": table["table_id"],
            "range": table["range"],
            "size": table["range"][1] - table["range"][0],
            "sha256": table["sha256"],
        }
        for table in table_records
    ] + [
        {
            "range_id": record["record_id"],
            "kind": "renderer_text_record",
            "source_table_ids": [source["table_id"] for source in record["sources"]],
            "range": record["range"],
            "size": record["size"],
            "sha256": record["sha256"],
        }
        for record in records
    ]
    classified.sort(key=lambda item: (item["range"][0], item["range"][1], item["kind"]))
    previous_end = -1
    bundle = bytearray()
    packed: dict[str, list[int]] = {}
    for item in classified:
        start, end = item["range"]
        if start < previous_end:
            raise ValueError("fixed classified ranges overlap")
        previous_end = end
        packed_start = len(bundle)
        bundle.extend(rom[start:end])
        item["packed_range"] = [packed_start, len(bundle)]
        packed[item["range_id"]] = item["packed_range"]
    for record in records:
        record["packed_range"] = packed[record["record_id"]]
    if _range_hash([item["range"] for item in classified]) != CLASSIFIED_RANGE_DENOMINATOR_SHA256:
        raise ValueError("fixed classified denominator differs")
    if _sha(bytes(bundle)) != BUNDLE_SHA256:
        raise ValueError("fixed packed bytes differ")

    summary = {
        "pointer_table_count": len(table_records),
        "pointer_slot_count": sum(item["entry_count"] for item in table_records),
        "null_pointer_slot_count": sum(
            item["null_slot_count"] for item in table_records
        ),
        "pointer_table_bytes": sum(item["range"][1] - item["range"][0] for item in table_records),
        "unique_target_count": len(records),
        "renderer_record_count": len(records),
        "renderer_consumed_bytes": sum(item["size"] for item in records),
        "classified_range_count": len(classified),
        "classified_bytes": len(bundle),
        "range_overlap_bytes": 0,
        "parse_failure_count": 0,
        "packed_bytes": len(bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"fixed summary differs: {summary}")
    implementation = {
        "exporter": {
            "path": "tools/export_rom_fixed_consumer_text_inventory.py",
            "sha256": _sha(_safe_file(root, "tools/export_rom_fixed_consumer_text_inventory.py").read_bytes()),
        },
        "verifier": {
            "path": "tools/verify_rom_fixed_consumer_text_inventory.py",
            "sha256": _sha(_safe_file(root, "tools/verify_rom_fixed_consumer_text_inventory.py").read_bytes()),
        },
        "test": {
            "path": "tests/test_export_rom_fixed_consumer_text_inventory.py",
            "sha256": _sha(_safe_file(root, "tests/test_export_rom_fixed_consumer_text_inventory.py").read_bytes()),
        },
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "pointer_tables": table_records,
        "consumer_evidence": {
            "decoded_semantics": semantics,
            "renderer_bridge": _evidence(rom, BRIDGE_RANGE, BRIDGE_SHA256, "renderer bridge"),
            "renderer_parser": _evidence(rom, PARSER_RANGE, PARSER_SHA256, "renderer parser"),
            "sjis_lookup": _evidence(rom, SJIS_LOOKUP_RANGE, SJIS_LOOKUP_SHA256, "SJIS lookup"),
            "sjis_range_table": {
                **_evidence(rom, (SJIS_TABLE, SJIS_TABLE_END), SJIS_TABLE_SHA256, "SJIS table"),
                "entry_count": SJIS_RANGE_COUNT,
                "entry_size": SJIS_ENTRY_SIZE,
            },
        },
        "records": records,
        "classified_ranges": classified,
        "record_range_denominator_sha256": RECORD_RANGE_DENOMINATOR_SHA256,
        "classified_range_denominator_sha256": CLASSIFIED_RANGE_DENOMINATOR_SHA256,
        "summary": summary,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": implementation,
    }
    return payload, bytes(bundle)


def _expected_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
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
                "tools/verify_rom_fixed_consumer_text_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
        },
    }


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        requested = _reject_symlink_components(Path(artifact_dir))
        artifact = requested.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact path is not a directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact tree contains a symlink")
        actual = {member.relative_to(artifact).as_posix() for member in members if member.is_file()}
        if actual != EXPECTED_FILES:
            raise ValueError("artifact file denominator differs")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity differs")
        expected_payload, expected_bundle = _expected_payload(root, rom)
        payload_bytes = _canonical(expected_payload)
        files = {PAYLOAD_NAME: payload_bytes, BUNDLE_NAME: expected_bundle}
        expected_manifest = _expected_manifest(expected_payload, files)
        manifest = json.loads(
            _artifact_file(artifact, "manifest.json").read_text(encoding="utf-8")
        )
        if manifest != expected_manifest:
            raise ValueError("artifact manifest differs from independent reconstruction")
        for name, digest in manifest["files"].items():
            if _sha(_artifact_file(artifact, name).read_bytes()) != digest:
                raise ValueError(f"artifact member hash differs: {name}")
        payload = json.loads(
            _artifact_file(artifact, PAYLOAD_NAME).read_text(encoding="utf-8")
        )
        if payload != expected_payload:
            raise ValueError("artifact payload differs from independent reconstruction")
        if _artifact_file(artifact, BUNDLE_NAME).read_bytes() != expected_bundle:
            raise ValueError("artifact packed bytes differ from ROM")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
    }
    if not errors:
        report.update(EXPECTED_SUMMARY)
        report["rom_sha256"] = ROM_SHA256
        report["record_range_denominator_sha256"] = RECORD_RANGE_DENOMINATOR_SHA256
        report["classified_range_denominator_sha256"] = CLASSIFIED_RANGE_DENOMINATOR_SHA256
        report["bundle_sha256"] = BUNDLE_SHA256
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
