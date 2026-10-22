#!/usr/bin/env python3
"""Export the animation descriptor pool behind the seven base pairs at 0x45832C.

The accepted `0x12D574` animation-descriptor table uses a fixed 0x54 stride and a
four-byte 0x0000FFFF terminator.  This pool is a *different* table: its
descriptor stride is a variable `0x14 * entries + 2`, and every descriptor ends
with a two-byte 0xFFFF head.  Nothing about the old table's shape may be
assumed here.

The structure is derived from the ROM, not from a written-down table:

  * every four-byte-aligned word inside the claim that points back into the
    claim is a pointer slot;
  * adjacent pointer slots form a pointer table;
  * a table whose slots all point at a 0x0000FFFF-terminated eight-byte record
    is a group (sequence) table, every other table is a descriptor table;
  * from each descriptor-table slot the descriptor start is known, and the entry
    count is counted by stepping 0x14 until the two-byte 0xFFFF head;
  * descriptor tables and group tables pair up in address order into the seven
    base pairs the renderer allocator is handed.

The claim is the 640-byte region 0x45832C..0x4585AC.  The 488-byte tail
0x4585AC..0x458794 belongs to a different family (it starts with "LV" and holds
ASCII "0123"/"4567"/"89") and is explicitly excluded rather than silently
dropped.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA = "rom-animation-descriptor-pool-v2"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
OFFICIAL = Path("artifacts/rom-animation-descriptor-pool-v2")
PAYLOAD_NAME = "rom-animation-descriptor-pool-v2.json"
MANIFEST_NAME = "manifest.json"

CLAIM_RANGE = (0x45832C, 0x4585AC)
CLAIM_SHA256 = "9be0375fab3cd7f25c99d6cdcfedfd3727d5d787b56532ac72894c74f5ec511c"
CLAIM_BYTES = CLAIM_RANGE[1] - CLAIM_RANGE[0]

# The descriptor entry stride is *not* the fixed 0x54 stride of the accepted
# 0x12D574 table.  It is verified against the data: the greatest common divisor
# of every (terminator offset - descriptor start) must equal it exactly.
DESCRIPTOR_ENTRY_STRIDE = 0x14
DESCRIPTOR_TERMINATOR = 0xFFFF
DESCRIPTOR_TERMINATOR_WIDTH = 2

SEQUENCE_ITEM_SIZE = 8
SEQUENCE_TERMINATOR = 0x0000FFFF

DESCRIPTOR_COUNT = 8
DESCRIPTOR_ENTRY_COUNT = 24
DESCRIPTOR_BYTES = 496
SEQUENCE_COUNT = 8
SEQUENCE_BYTES = 64
POINTER_SLOT_COUNT = 16
POINTER_SLOT_BYTES = 64
POINTER_TABLE_COUNT = 14
BASE_PAIR_COUNT = 7
PADDING_SEGMENT_COUNT = 8
PADDING_BYTES = 16

# Upstream shared consumer segments.  Byte-identical to the accepted
# 0x12D574 contract, so they can be pinned whole.
ALLOCATOR_RANGE = (0x0626B4, 0x062766)
ALLOCATOR_SHA256 = "09cd85fb8fcdc85751019c67ef6b91d6d3d64c1fbeb0b0496e270234f846d804"
RENDERER_SELECT_RANGE = (0x062924, 0x062A0A)
RENDERER_SELECT_SHA256 = "23ead2fcc1537d16a632bf68dbccdb96a142af170410f862baaf4c1d750e0a18"
RENDERER_STEP_RANGE = (0x0631F6, 0x063208)
RENDERER_STEP_SHA256 = "79cb19c28c7f5a75ed323f99c837e131c0e11dd06c91f422e60ac9ff859e8f44"
RENDERER_ADVANCE_RANGE = (0x063238, 0x0632BA)
RENDERER_ADVANCE_SHA256 = "b6dc39ac66ecaac48e16f37406bab7e579362759e9e3570e9c6fa9e24ec0ab23"

# The two base-pair callers that were located and pinned.  Every other base
# pair is known only through its literal pair, so the caller denominator stays
# open.
CALLER_A_RANGE = (0x06F908, 0x06F920)
CALLER_A_SHA256 = "9316d77b9803a7651036902beb53e5de737e064505f560ff9987ee09256134e1"
CALLER_A_POOL_RANGE = (0x06F958, 0x06F960)
CALLER_A_POOL_SHA256 = "4dfab96f5dbd463a6b305159ed1bb143e71b34df58f6be23b462d09e4ae600e4"
CALLER_A_LOAD_SITES = (0x06F90C, 0x06F90E)
CALLER_A_LOAD_HALFWORDS = (0x4812, 0x4913)
CALLER_A_CALL_SITE = 0x06F914
CALLER_A_CALL_HALFWORD = 0xF7F2

CALLER_B_RANGE = (0x071040, 0x071060)
CALLER_B_SHA256 = "643d8b3c834c44f6c667f3a83dca3e3897b44f45f2a381f174d74bf1ab18c9da"
CALLER_B_POOL_RANGE = (0x0710D8, 0x0710E0)
CALLER_B_POOL_SHA256 = "f57f4ff0bfd5bf3dd7383f0f24ce930fe6184f68b82e5b00ad90717ec82e82a2"
CALLER_B_LOAD_SITES = (0x071044, 0x071046)
CALLER_B_LOAD_HALFWORDS = (0x4824, 0x4925)
CALLER_B_CALL_SITE = 0x071060
CALLER_B_CALL_HALFWORD = 0xF7F1

ALLOCATOR_CALL_TARGET = 0x0626B4

# The four literals whose full-ROM occurrence denominator was recomputed by
# hand and is therefore pinned byte for byte.
PINNED_LITERAL_OCCURRENCES = {
    0x0845854C: [0x06F958, 0x078068, 0x0789EC, 0x093C40, 0x094DD0, 0x094E7C],
    0x08458558: [0x06F95C, 0x07806C, 0x0789F0, 0x093C44, 0x094DD4, 0x094E80],
    0x08458510: [0x0710D8, 0x08AEF8, 0x08BD64, 0x0909B0, 0x092654, 0x094DC0],
    0x0845851C: [0x0710DC, 0x08AEFC, 0x08BD68, 0x0909B4, 0x092658, 0x094DC4],
}

# The heterogeneous tail: excluded from the claim, kept as evidence.
TAIL_RANGE = (0x4585AC, 0x458794)
TAIL_SHA256 = "11d1938dc0a00025ed1e953ba3e7e69892467f757a1de07fbc162cdc5b6c0f69"
FULL_SEGMENT_RANGE = (0x45832C, 0x458794)
FULL_SEGMENT_SHA256 = "bb920ef38b327c35495afe51e710741b88d64f783f4bf35c7b3c0c84fd39909c"

LOADER_SCAN_LIMIT = 0x400
REGISTER_NAMES = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7")

PRIMARY_CLASS = "fixed_consumer_animation_descriptor_group_bytes"
CLAIM_KIND = "fixed_consumer_animation_descriptor_group_bytes"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _publish_exclusive(source: Path, destination: Path) -> None:
    """Atomically publish one directory without replacing any destination."""
    source = source.absolute()
    destination = destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004  # RENAME_EXCL
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001  # RENAME_NOREPLACE
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


def _pin(rom: bytes, span: tuple[int, int], digest: str, label: str) -> None:
    if _sha(rom[span[0]:span[1]]) != digest:
        raise ValueError(f"{label} identity changed")


def _all_occurrences(raw: bytes, needle: bytes) -> list[int]:
    result: list[int] = []
    cursor = 0
    while True:
        cursor = raw.find(needle, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _half(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", rom, offset)[0]


def _word(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def _pointer_slots(rom: bytes) -> list[dict[str, int]]:
    """Every aligned word in the claim that points back into the claim."""
    slots: list[dict[str, int]] = []
    for offset in range(CLAIM_RANGE[0], CLAIM_RANGE[1] - 3, 4):
        value = _word(rom, offset)
        if ROM_BASE <= value < ROM_BASE + ROM_SIZE:
            target = value - ROM_BASE
            if CLAIM_RANGE[0] <= target < CLAIM_RANGE[1]:
                slots.append({"slot_offset": offset, "target": target})
    if not slots:
        raise ValueError("claim has no pointer slots")
    return slots


def _pointer_tables(slots: list[dict[str, int]]) -> list[list[dict[str, int]]]:
    """Adjacent pointer slots form one pointer table."""
    tables: list[list[dict[str, int]]] = []
    for slot in slots:
        if tables and tables[-1][-1]["slot_offset"] + 4 == slot["slot_offset"]:
            tables[-1].append(slot)
        else:
            tables.append([slot])
    return tables


def _walk_descriptor(rom: bytes, start: int) -> tuple[int, int]:
    """Count descriptor entries by stepping 0x14 until the 0xFFFF head."""
    count = 0
    offset = start
    while True:
        if offset + 2 > CLAIM_RANGE[1]:
            raise ValueError("descriptor terminator missing")
        if _half(rom, offset) == DESCRIPTOR_TERMINATOR:
            return count, offset
        count += 1
        offset += DESCRIPTOR_ENTRY_STRIDE


def _parse_descriptors(rom: bytes, starts: list[int]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    strides: list[int] = []
    for index, start in enumerate(starts):
        count, terminator = _walk_descriptor(rom, start)
        if count < 1:
            raise ValueError("descriptor has no entries")
        end = terminator + DESCRIPTOR_TERMINATOR_WIDTH
        strides.append(terminator - start)
        items.append({
            "descriptor_index": index,
            "range": [start, end],
            "entry_count": count,
            "entry_stride": DESCRIPTOR_ENTRY_STRIDE,
            "entry_heads": [_half(rom, start + step * DESCRIPTOR_ENTRY_STRIDE)
                            for step in range(count)],
            "terminator_offset": terminator,
            "bytes_sha256": _sha(rom[start:end]),
        })
    # The stride is confirmed against the data, not assumed.
    if math.gcd(*strides) != DESCRIPTOR_ENTRY_STRIDE:
        raise ValueError("descriptor entry stride changed")
    if len(items) != DESCRIPTOR_COUNT:
        raise ValueError("descriptor denominator changed")
    if sum(item["entry_count"] for item in items) != DESCRIPTOR_ENTRY_COUNT:
        raise ValueError("descriptor entry denominator changed")
    heads = sorted({head for item in items for head in item["entry_heads"]})
    flags = sorted({_half(rom, item["range"][0] + step * DESCRIPTOR_ENTRY_STRIDE + 2)
                    for item in items for step in range(item["entry_count"])})
    return {
        "descriptor_count": len(items),
        "entry_count": sum(item["entry_count"] for item in items),
        "entry_stride": DESCRIPTOR_ENTRY_STRIDE,
        "terminator_value": DESCRIPTOR_TERMINATOR,
        "terminator_width": DESCRIPTOR_TERMINATOR_WIDTH,
        "terminator_position": "head",
        "descriptor_bytes": sum(item["range"][1] - item["range"][0] for item in items),
        "entry_head_domain": {"min": heads[0], "max": heads[-1], "distinct": heads},
        "flag_halfword_domain": {"distinct": flags},
        "items": items,
    }


def _parse_sequences(rom: bytes, starts: list[int]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        if start + SEQUENCE_ITEM_SIZE > CLAIM_RANGE[1]:
            raise ValueError("sequence crosses the claim end")
        record, duration = struct.unpack_from("<HH", rom, start)
        terminator = _word(rom, start + 4)
        if terminator != SEQUENCE_TERMINATOR:
            raise ValueError("sequence terminator changed")
        items.append({
            "sequence_index": index,
            "range": [start, start + SEQUENCE_ITEM_SIZE],
            "record_index": record,
            "duration": duration,
            "terminator": terminator,
            "bytes_sha256": _sha(rom[start:start + SEQUENCE_ITEM_SIZE]),
        })
    if len(items) != SEQUENCE_COUNT:
        raise ValueError("sequence denominator changed")
    return {
        "sequence_count": len(items),
        "sequence_bytes": sum(item["range"][1] - item["range"][0] for item in items),
        "item_size": SEQUENCE_ITEM_SIZE,
        "terminator_value": SEQUENCE_TERMINATOR,
        "terminator_width": 4,
        "record_index_domain": sorted({item["record_index"] for item in items}),
        "duration_domain": sorted({item["duration"] for item in items}),
        "items": items,
    }


def _padding(rom: bytes, covered: set[int]) -> list[dict[str, Any]]:
    """Everything the claim holds that is not a descriptor, sequence or slot."""
    items: list[dict[str, Any]] = []
    cursor = CLAIM_RANGE[0]
    while cursor < CLAIM_RANGE[1]:
        if cursor in covered:
            cursor += 1
            continue
        start = cursor
        while cursor < CLAIM_RANGE[1] and cursor not in covered:
            cursor += 1
        raw = rom[start:cursor]
        if raw != b"\x00" * len(raw):
            raise ValueError("unattributed claim bytes are not zero padding")
        items.append({"range": [start, cursor], "bytes": len(raw),
                      "bytes_sha256": _sha(raw)})
    if len(items) != PADDING_SEGMENT_COUNT:
        raise ValueError("padding denominator changed")
    if sum(item["bytes"] for item in items) != PADDING_BYTES:
        raise ValueError("padding byte denominator changed")
    return items


def _structure(rom: bytes) -> dict[str, Any]:
    slots = _pointer_slots(rom)
    if len(slots) != POINTER_SLOT_COUNT:
        raise ValueError("pointer slot denominator changed")
    tables = _pointer_tables(slots)
    if len(tables) != POINTER_TABLE_COUNT:
        raise ValueError("pointer table denominator changed")

    descriptor_tables: list[dict[str, Any]] = []
    group_tables: list[dict[str, Any]] = []
    for table in tables:
        targets = [slot["target"] for slot in table]
        is_group = all(_word(rom, target + 4) == SEQUENCE_TERMINATOR
                       for target in targets)
        if is_group and any(_word(rom, target + 4) != SEQUENCE_TERMINATOR
                            for target in targets):
            raise ValueError("pointer table mixes descriptor and group targets")
        entry = {
            "range": [table[0]["slot_offset"],
                      table[-1]["slot_offset"] + 4],
            "slot_count": len(table),
            "slots": [{"slot_offset": slot["slot_offset"], "target": slot["target"]}
                      for slot in table],
        }
        (group_tables if is_group else descriptor_tables).append(entry)
    if len(descriptor_tables) != BASE_PAIR_COUNT or len(group_tables) != BASE_PAIR_COUNT:
        raise ValueError("pointer table kind denominator changed")

    descriptor_starts = [slot["target"] for table in descriptor_tables
                         for slot in table["slots"]]
    sequence_starts = [slot["target"] for table in group_tables
                       for slot in table["slots"]]
    if len(set(descriptor_starts)) != len(descriptor_starts):
        raise ValueError("descriptor table slots repeat a target")
    if len(set(sequence_starts)) != len(sequence_starts):
        raise ValueError("group table slots repeat a target")

    descriptors = _parse_descriptors(rom, descriptor_starts)
    sequences = _parse_sequences(rom, sequence_starts)

    covered: set[int] = set()
    for item in descriptors["items"]:
        covered.update(range(item["range"][0], item["range"][1]))
    for item in sequences["items"]:
        covered.update(range(item["range"][0], item["range"][1]))
    for table in descriptor_tables + group_tables:
        covered.update(range(table["range"][0], table["range"][1]))
    padding = _padding(rom, covered)
    if len(covered) + sum(item["bytes"] for item in padding) != CLAIM_BYTES:
        raise ValueError("claim coverage is not exact")

    base_pairs = []
    for index, (descriptor_table, group_table) in enumerate(zip(descriptor_tables,
                                                                group_tables)):
        base_pairs.append({
            "pair_index": index,
            "descriptor_table_index": index,
            "group_table_index": index,
            "descriptor_table_address": descriptor_table["range"][0],
            "group_table_address": group_table["range"][0],
            "descriptor_table_slots": descriptor_table["slot_count"],
            "group_table_slots": group_table["slot_count"],
            "descriptor_targets": [slot["target"] for slot in descriptor_table["slots"]],
            "group_targets": [slot["target"] for slot in group_table["slots"]],
            "r0_literal": ROM_BASE + descriptor_table["range"][0],
            "r1_literal": ROM_BASE + group_table["range"][0],
        })

    tables_payload = []
    for index, table in enumerate(descriptor_tables + group_tables):
        tables_payload.append({
            "table_index": index,
            "kind": "descriptor_table" if index < len(descriptor_tables) else "group_table",
            "range": table["range"],
            "slot_count": table["slot_count"],
            "slots": table["slots"],
        })

    return {
        "descriptors": descriptors,
        "sequences": sequences,
        "pointer_slots": {
            "slot_count": len(slots),
            "pointer_slot_bytes": len(slots) * 4,
            "table_count": len(tables_payload),
            "tables": tables_payload,
        },
        "base_pairs": {
            "pair_count": len(base_pairs),
            "items": base_pairs,
        },
        "padding": {
            "segment_count": len(padding),
            "padding_bytes": sum(item["bytes"] for item in padding),
            "items": padding,
        },
        "byte_attribution": {
            "total_bytes": CLAIM_BYTES,
            "descriptor_bytes": descriptors["descriptor_bytes"],
            "sequence_bytes": sequences["sequence_bytes"],
            "pointer_slot_bytes": len(slots) * 4,
            "padding_bytes": sum(item["bytes"] for item in padding),
            "unattributed_bytes": 0,
        },
    }


def _loader_for(rom: bytes, site: int) -> tuple[int | None, int | None]:
    """Nearest preceding Thumb LDR-literal instruction that resolves to `site`."""
    for back in range(0, LOADER_SCAN_LIMIT, 2):
        address = site - back
        if address < 2:
            break
        half = _half(rom, address)
        if half & 0xF800 != 0x4800:
            continue
        pool = ((address + 4) & ~3) + (half & 0xFF) * 4
        if pool == site:
            return (half >> 8) & 7, address
    return None, None


def _literal_binding(rom: bytes, pairs: list[dict[str, Any]]) -> dict[str, Any]:
    descriptor: dict[str, Any] = {}
    group: dict[str, Any] = {}
    r0_occurrences = 0
    r1_occurrences = 0
    pool_count = 0
    for pair in pairs:
        for key, bucket, wanted in (("r0_literal", descriptor, 0),
                                    ("r1_literal", group, 1)):
            literal = pair[key]
            sites = _all_occurrences(rom, struct.pack("<I", literal))
            loaders = []
            for site in sites:
                register, address = _loader_for(rom, site)
                if register != wanted:
                    raise ValueError("literal loader register changed")
                loaders.append({"site": site, "loader": address})
            bucket[f"0x{literal:08X}"] = {
                "register": REGISTER_NAMES[wanted],
                "occurrence_denominator": len(sites),
                "sites": sites,
                "loaders": loaders,
            }
            if wanted == 0:
                r0_occurrences += len(sites)
                # Each r0 literal anchors one literal pool that also holds the
                # matching r1 literal, so this counts the pools of the pair.
                pool_count += len(sites)
            else:
                r1_occurrences += len(sites)
    return {
        "scan_limit_bytes": LOADER_SCAN_LIMIT,
        "rule": "nearest preceding Thumb LDR-literal instruction resolving to the literal site",
        "descriptor_table_literals": descriptor,
        "group_table_literals": group,
        "literal_occurrence_count": r0_occurrences + r1_occurrences,
        "r0_literal_occurrence_count": r0_occurrences,
        "r1_literal_occurrence_count": r1_occurrences,
        "base_pair_pool_count": pool_count,
    }


def _consumer_contract(rom: bytes, pairs: list[dict[str, Any]]) -> dict[str, Any]:
    _pin(rom, ALLOCATOR_RANGE, ALLOCATOR_SHA256, "allocator")
    _pin(rom, RENDERER_SELECT_RANGE, RENDERER_SELECT_SHA256, "renderer select")
    _pin(rom, RENDERER_STEP_RANGE, RENDERER_STEP_SHA256, "renderer step")
    _pin(rom, RENDERER_ADVANCE_RANGE, RENDERER_ADVANCE_SHA256, "renderer advance")

    def _check_halfwords(load_sites: tuple[int, int], load_halfwords: tuple[int, int],
                         call_site: int, call_halfword: int) -> None:
        for site, expected_half in zip(load_sites, load_halfwords):
            half = _half(rom, site)
            if half != expected_half:
                raise ValueError("caller literal load halfword changed")
            if half & 0xF800 != 0x4800:
                raise ValueError("caller literal load is not a literal load")
        if _half(rom, call_site) != call_halfword:
            raise ValueError("caller call halfword changed")
        if call_halfword & 0xF800 != 0xF000:
            raise ValueError("caller call is not a long branch")

    _check_halfwords(CALLER_A_LOAD_SITES, CALLER_A_LOAD_HALFWORDS,
                     CALLER_A_CALL_SITE, CALLER_A_CALL_HALFWORD)
    _check_halfwords(CALLER_B_LOAD_SITES, CALLER_B_LOAD_HALFWORDS,
                     CALLER_B_CALL_SITE, CALLER_B_CALL_HALFWORD)

    _pin(rom, CALLER_A_RANGE, CALLER_A_SHA256, "caller a")
    _pin(rom, CALLER_A_POOL_RANGE, CALLER_A_POOL_SHA256, "caller a literal pool")
    _pin(rom, CALLER_B_RANGE, CALLER_B_SHA256, "caller b")
    _pin(rom, CALLER_B_POOL_RANGE, CALLER_B_POOL_SHA256, "caller b literal pool")

    for value, expected in PINNED_LITERAL_OCCURRENCES.items():
        if _all_occurrences(rom, struct.pack("<I", value)) != expected:
            raise ValueError("consumer literal denominator changed")

    def _describe(caller: str, code_range: tuple[int, int], pool_range: tuple[int, int],
                  load_sites: tuple[int, int], load_halfwords: tuple[int, int],
                  call_site: int, call_halfword: int) -> dict[str, Any]:
        pool_sites = []
        for site, expected_half in zip(load_sites, load_halfwords):
            half = _half(rom, site)
            pool = ((site + 4) & ~3) + (half & 0xFF) * 4
            if not pool_range[0] <= pool < pool_range[1]:
                raise ValueError("caller literal pool alignment changed")
            pool_sites.append(pool)
        values = [_word(rom, site) for site in pool_sites]
        pair = next((item for item in pairs
                     if item["r0_literal"] == values[0]
                     and item["r1_literal"] == values[1]), None)
        if pair is None:
            raise ValueError("caller base pair is not part of the pool")
        return {
            "caller_id": f"animation-descriptor-base-caller-{caller}",
            "code_range": list(code_range),
            "code_sha256": _sha(rom[code_range[0]:code_range[1]]),
            "literal_pool_range": list(pool_range),
            "literal_pool_sha256": _sha(rom[pool_range[0]:pool_range[1]]),
            "literal_load_sites": list(load_sites),
            "literal_load_halfwords": list(load_halfwords),
            "literal_pool_sites": pool_sites,
            "literal_values": values,
            "base_pair_index": pair["pair_index"],
            "call_site": call_site,
            "call_halfword": call_halfword,
            "call_target": ALLOCATOR_CALL_TARGET,
        }

    callers = [
        _describe("a", CALLER_A_RANGE, CALLER_A_POOL_RANGE, CALLER_A_LOAD_SITES,
                  CALLER_A_LOAD_HALFWORDS, CALLER_A_CALL_SITE,
                  CALLER_A_CALL_HALFWORD),
        _describe("b", CALLER_B_RANGE, CALLER_B_POOL_RANGE, CALLER_B_LOAD_SITES,
                  CALLER_B_LOAD_HALFWORDS, CALLER_B_CALL_SITE,
                  CALLER_B_CALL_HALFWORD),
    ]

    binding = _literal_binding(rom, pairs)
    return {
        "identity_ranges": [
            {"label": "allocator", "range": list(ALLOCATOR_RANGE),
             "bytes_sha256": ALLOCATOR_SHA256},
            {"label": "renderer_select", "range": list(RENDERER_SELECT_RANGE),
             "bytes_sha256": RENDERER_SELECT_SHA256},
            {"label": "renderer_step", "range": list(RENDERER_STEP_RANGE),
             "bytes_sha256": RENDERER_STEP_SHA256},
            {"label": "renderer_advance", "range": list(RENDERER_ADVANCE_RANGE),
             "bytes_sha256": RENDERER_ADVANCE_SHA256},
        ],
        "allocator_object_fields": {"group_index": 0x14, "record_slot": 0x16,
                                    "descriptor_table": 0x1C, "group_table": 0x20},
        "allocator_call_target": ALLOCATOR_CALL_TARGET,
        "located_callers": callers,
        "located_caller_count": len(callers),
        "pinned_literal_occurrence_denominator": {
            f"0x{value:08X}": offsets
            for value, offsets in PINNED_LITERAL_OCCURRENCES.items()},
        "literal_loader_binding": binding,
        "caller_site_denominator": {
            "base_pair_count": len(pairs),
            "base_pair_pools": binding["base_pair_pool_count"],
            "attributed_callers": len(callers),
            "attributed_pools": len(callers),
            "unattributed_pools": binding["base_pair_pool_count"] - len(callers),
            "closed": False,
        },
    }


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")

    # The structure is derived first, so that a damaged descriptor, terminator
    # or pointer slot is reported as such instead of as a generic hash change.
    structure = _structure(rom)

    if _sha(rom[CLAIM_RANGE[0]:CLAIM_RANGE[1]]) != CLAIM_SHA256:
        raise ValueError("claim identity changed")
    if _sha(rom[FULL_SEGMENT_RANGE[0]:FULL_SEGMENT_RANGE[1]]) != FULL_SEGMENT_SHA256:
        raise ValueError("full segment identity changed")
    if _sha(rom[TAIL_RANGE[0]:TAIL_RANGE[1]]) != TAIL_SHA256:
        raise ValueError("excluded tail identity changed")

    consumer = _consumer_contract(rom, structure["base_pairs"]["items"])

    claim = {
        "id": "animation-descriptor-pool-45832c",
        "range": list(CLAIM_RANGE),
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "bytes_sha256": CLAIM_SHA256,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "claim": {"range": list(CLAIM_RANGE), "bytes": CLAIM_BYTES,
                  "bytes_sha256": CLAIM_SHA256,
                  "primary_class": PRIMARY_CLASS, "claim_kind": CLAIM_KIND},
        "descriptors": structure["descriptors"],
        "sequences": structure["sequences"],
        "pointer_slots": structure["pointer_slots"],
        "base_pairs": structure["base_pairs"],
        "padding": structure["padding"],
        "byte_attribution": structure["byte_attribution"],
        "consumer_contract": consumer,
        "excluded_regions": [{
            "range": list(TAIL_RANGE),
            "bytes": TAIL_RANGE[1] - TAIL_RANGE[0],
            "bytes_sha256": TAIL_SHA256,
            "reason": "heterogeneous family: the tail opens with the ASCII marker "
                      "'LV' and carries the ASCII digit runs '0123', '4567' and "
                      "'89', so it is not part of the animation descriptor pool",
            "family_attributed": False,
            "inside_claim": False,
        }],
        "promotion": {
            "promotion_batch": SCHEMA,
            "promoted_from_primary_class": "unknown",
            "claims": [claim],
            "claim_count": 1,
            "promotion_bytes": CLAIM_BYTES,
        },
        "scope": {
            "natural_runtime_reachability": False,
            "caller_denominator_closed": False,
            "flags_domain_closed": False,
            "callback_domain_closed": False,
            "heterogeneous_tail_family_closed": False,
            "all_callers_share_this_input": False,
            "descriptor_editing_safety": False,
            "opaque_renderer_side_effects": False,
            "index_domain_closed": False,
        },
        "scope_notes": {
            "caller_denominator_closed":
                "seven base pairs are known and every literal site binds r0 to "
                "the descriptor table and r1 to the group table, but only two "
                "of the literal sites are attributed to a pinned caller, so the "
                "caller denominator is not closed",
            "flags_domain_closed":
                "the second halfword of every descriptor entry head is 0x0000 "
                "for all 24 entries; no writer and no flag meaning is bound "
                "here, so the flag domain is not closed",
            "callback_domain_closed":
                "descriptor entry heads and sequence record indices select "
                "records in a table that this package does not identify, so the "
                "callback domain is not closed",
            "heterogeneous_tail_family_closed":
                "the 488-byte tail 0x4585AC..0x458794 is excluded from the "
                "claim, but the family it belongs to is still unknown",
            "natural_runtime_reachability":
                "no claim is made that the pool is reached during normal play",
        },
    }


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


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
    exporter = Path("tools/export_rom_animation_descriptor_pool_v2.py")
    verifier = Path("tools/verify_rom_animation_descriptor_pool_v2.py")
    test = Path("tests/test_export_rom_animation_descriptor_pool_v2.py")
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
        "summary": {
            "descriptor_count": DESCRIPTOR_COUNT,
            "descriptor_entry_count": DESCRIPTOR_ENTRY_COUNT,
            "sequence_count": SEQUENCE_COUNT,
            "base_pair_count": BASE_PAIR_COUNT,
            "promotion_bytes": CLAIM_BYTES,
        },
        "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                 "--output", output.relative_to(root).as_posix()]},
        "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                  "--artifact", output.relative_to(root).as_posix()]},
        "implementation": {
            "exporter_sha256": _sha(_safe_file(root, exporter).read_bytes()),
            "verifier_sha256": _sha(_safe_file(root, verifier).read_bytes()),
            "test_sha256": _sha(_safe_file(root, test).read_bytes()),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,
                                     prefix=".animation-descriptor-pool-v2-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_animation_descriptor_pool_v2 import verify_artifact
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
