#!/usr/bin/env python3
"""Independently verify the animation descriptor pool at 0x45832C.

This verifier never imports the exporter.  It re-derives the pointer slots, the
pointer tables, the descriptor entry counts, the sequences, the base pairs and
the consumer contract straight from the ROM bytes and requires the published
payload to be byte-identical to that reconstruction.

The descriptor shape differs from the accepted 0x12D574 table: the entry stride
is 0x14 and the descriptor terminator is a two-byte 0xFFFF head, never a
four-byte 0x0000FFFF word and never a fixed 0x54 stride.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA = "rom-animation-descriptor-pool-v2"
VERIFY_SCHEMA = f"{SCHEMA}-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
PAYLOAD_NAME = "rom-animation-descriptor-pool-v2.json"
MANIFEST_NAME = "manifest.json"

CLAIM = (0x45832C, 0x4585AC)
CLAIM_DIGEST = "9be0375fab3cd7f25c99d6cdcfedfd3727d5d787b56532ac72894c74f5ec511c"
FULL = (0x45832C, 0x458794)
FULL_DIGEST = "bb920ef38b327c35495afe51e710741b88d64f783f4bf35c7b3c0c84fd39909c"
TAIL = (0x4585AC, 0x458794)
TAIL_DIGEST = "11d1938dc0a00025ed1e953ba3e7e69892467f757a1de07fbc162cdc5b6c0f69"

STRIDE = 0x14
TERMINATOR = 0xFFFF
SEQUENCE_SIZE = 8
SEQUENCE_END = 0x0000FFFF

DESCRIPTOR_TOTAL = 8
ENTRY_TOTAL = 24
SEQUENCE_TOTAL = 8
SLOT_TOTAL = 16
TABLE_TOTAL = 14
PAIR_TOTAL = 7
PAD_TOTAL = 8
PAD_BYTES = 16

ALLOCATOR = (0x0626B4, 0x062766)
ALLOCATOR_DIGEST = "09cd85fb8fcdc85751019c67ef6b91d6d3d64c1fbeb0b0496e270234f846d804"
SELECT = (0x062924, 0x062A0A)
SELECT_DIGEST = "23ead2fcc1537d16a632bf68dbccdb96a142af170410f862baaf4c1d750e0a18"
STEP = (0x0631F6, 0x063208)
STEP_DIGEST = "79cb19c28c7f5a75ed323f99c837e131c0e11dd06c91f422e60ac9ff859e8f44"
ADVANCE = (0x063238, 0x0632BA)
ADVANCE_DIGEST = "b6dc39ac66ecaac48e16f37406bab7e579362759e9e3570e9c6fa9e24ec0ab23"

CALLER_A = (0x06F908, 0x06F920)
CALLER_A_DIGEST = "9316d77b9803a7651036902beb53e5de737e064505f560ff9987ee09256134e1"
POOL_A = (0x06F958, 0x06F960)
POOL_A_DIGEST = "4dfab96f5dbd463a6b305159ed1bb143e71b34df58f6be23b462d09e4ae600e4"
LOAD_A = (0x06F90C, 0x06F90E)
HALF_A = (0x4812, 0x4913)
CALL_A = 0x06F914
CALL_HALF_A = 0xF7F2

CALLER_B = (0x071040, 0x071060)
CALLER_B_DIGEST = "643d8b3c834c44f6c667f3a83dca3e3897b44f45f2a381f174d74bf1ab18c9da"
POOL_B = (0x0710D8, 0x0710E0)
POOL_B_DIGEST = "f57f4ff0bfd5bf3dd7383f0f24ce930fe6184f68b82e5b00ad90717ec82e82a2"
LOAD_B = (0x071044, 0x071046)
HALF_B = (0x4824, 0x4925)
CALL_B = 0x071060
CALL_HALF_B = 0xF7F1

ALLOCATOR_TARGET = 0x0626B4

PINNED = {
    0x0845854C: [0x06F958, 0x078068, 0x0789EC, 0x093C40, 0x094DD0, 0x094E7C],
    0x08458558: [0x06F95C, 0x07806C, 0x0789F0, 0x093C44, 0x094DD4, 0x094E80],
    0x08458510: [0x0710D8, 0x08AEF8, 0x08BD64, 0x0909B0, 0x092654, 0x094DC0],
    0x0845851C: [0x0710DC, 0x08AEFC, 0x08BD68, 0x0909B4, 0x092658, 0x094DC4],
}

SCAN_LIMIT = 0x400
REGISTERS = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7")

PRIMARY_CLASS = "fixed_consumer_animation_descriptor_group_bytes"
CLAIM_KIND = "fixed_consumer_animation_descriptor_group_bytes"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _read(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", rom, offset)[0]


def _dword(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def _find_all(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    found: list[int] = []
    cursor = rom.find(needle)
    while cursor >= 0:
        found.append(cursor)
        cursor = rom.find(needle, cursor + 1)
    return found


def _slots(rom: bytes) -> list[tuple[int, int]]:
    """Aligned in-claim words that point back into the claim."""
    result: list[tuple[int, int]] = []
    offset = CLAIM[0]
    while offset + 4 <= CLAIM[1]:
        word = _dword(rom, offset)
        if ROM_BASE <= word < ROM_BASE + ROM_SIZE:
            target = word - ROM_BASE
            if CLAIM[0] <= target < CLAIM[1]:
                result.append((offset, target))
        offset += 4
    if not result:
        raise ValueError("claim has no pointer slots")
    return result


def _runs(slots: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Consecutive pointer slots form one table."""
    tables: list[list[tuple[int, int]]] = []
    for slot in slots:
        if tables and tables[-1][-1][0] + 4 == slot[0]:
            tables[-1].append(slot)
        else:
            tables.append([slot])
    return tables


def _entries(rom: bytes, start: int) -> tuple[int, int]:
    """Step 0x14 from the descriptor start until the two-byte 0xFFFF head."""
    count = 0
    cursor = start
    while True:
        if cursor + 2 > CLAIM[1]:
            raise ValueError("descriptor terminator missing")
        if _read(rom, cursor) == TERMINATOR:
            return count, cursor
        count += 1
        cursor += STRIDE


def _loader(rom: bytes, site: int) -> tuple[int | None, int | None]:
    """Nearest preceding Thumb literal load that resolves to `site`."""
    for back in range(0, SCAN_LIMIT, 2):
        address = site - back
        if address < 2:
            break
        half = _read(rom, address)
        if (half & 0xF800) != 0x4800:
            continue
        if ((address + 4) & ~3) + (half & 0xFF) * 4 == site:
            return (half >> 8) & 7, address
    return None, None


def _rebuild(rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256):
        raise ValueError("ROM identity changed")

    # The structure is derived first, so that a damaged descriptor, terminator
    # or pointer slot is reported as such instead of as a generic hash change.
    slots = _slots(rom)
    if len(slots) != SLOT_TOTAL:
        raise ValueError("pointer slot denominator changed")
    tables = _runs(slots)
    if len(tables) != TABLE_TOTAL:
        raise ValueError("pointer table denominator changed")

    descriptor_tables: list[dict[str, Any]] = []
    group_tables: list[dict[str, Any]] = []
    for table in tables:
        targets = [target for _, target in table]
        marks = [_dword(rom, target + 4) == SEQUENCE_END for target in targets]
        if any(marks) and not all(marks):
            raise ValueError("pointer table mixes descriptor and group targets")
        body = {
            "range": [table[0][0], table[-1][0] + 4],
            "slot_count": len(table),
            "slots": [{"slot_offset": offset, "target": target}
                      for offset, target in table],
        }
        if all(marks):
            group_tables.append(body)
        else:
            descriptor_tables.append(body)
    if len(descriptor_tables) != PAIR_TOTAL or len(group_tables) != PAIR_TOTAL:
        raise ValueError("pointer table kind denominator changed")

    descriptor_starts = [slot["target"] for table in descriptor_tables
                         for slot in table["slots"]]
    sequence_starts = [slot["target"] for table in group_tables
                       for slot in table["slots"]]
    if len(set(descriptor_starts)) != len(descriptor_starts):
        raise ValueError("descriptor table slots repeat a target")
    if len(set(sequence_starts)) != len(sequence_starts):
        raise ValueError("group table slots repeat a target")

    descriptor_items: list[dict[str, Any]] = []
    gaps: list[int] = []
    for index, start in enumerate(descriptor_starts):
        count, terminator = _entries(rom, start)
        if count < 1:
            raise ValueError("descriptor has no entries")
        gaps.append(terminator - start)
        descriptor_items.append({
            "descriptor_index": index,
            "range": [start, terminator + 2],
            "entry_count": count,
            "entry_stride": STRIDE,
            "entry_heads": [_read(rom, start + step * STRIDE) for step in range(count)],
            "terminator_offset": terminator,
            "bytes_sha256": _digest(rom[start:terminator + 2]),
        })
    if math.gcd(*gaps) != STRIDE:
        raise ValueError("descriptor entry stride changed")
    if len(descriptor_items) != DESCRIPTOR_TOTAL:
        raise ValueError("descriptor denominator changed")
    entry_total = sum(item["entry_count"] for item in descriptor_items)
    if entry_total != ENTRY_TOTAL:
        raise ValueError("descriptor entry denominator changed")
    all_heads = [head for item in descriptor_items for head in item["entry_heads"]]
    unique_heads = sorted(set(all_heads))
    flags = sorted({_read(rom, item["range"][0] + step * STRIDE + 2)
                    for item in descriptor_items for step in range(item["entry_count"])})
    descriptors = {
        "descriptor_count": len(descriptor_items),
        "entry_count": entry_total,
        "entry_stride": STRIDE,
        "terminator_value": TERMINATOR,
        "terminator_width": 2,
        "terminator_position": "head",
        "descriptor_bytes": sum(item["range"][1] - item["range"][0]
                                for item in descriptor_items),
        "entry_head_domain": {"min": unique_heads[0], "max": unique_heads[-1],
                              "distinct": unique_heads},
        "flag_halfword_domain": {"distinct": flags},
        "items": descriptor_items,
    }

    sequence_items: list[dict[str, Any]] = []
    for index, start in enumerate(sequence_starts):
        if start + SEQUENCE_SIZE > CLAIM[1]:
            raise ValueError("sequence crosses the claim end")
        record, duration = struct.unpack_from("<HH", rom, start)
        terminator = _dword(rom, start + 4)
        if terminator != SEQUENCE_END:
            raise ValueError("sequence terminator changed")
        sequence_items.append({
            "sequence_index": index,
            "range": [start, start + SEQUENCE_SIZE],
            "record_index": record,
            "duration": duration,
            "terminator": terminator,
            "bytes_sha256": _digest(rom[start:start + SEQUENCE_SIZE]),
        })
    if len(sequence_items) != SEQUENCE_TOTAL:
        raise ValueError("sequence denominator changed")
    sequences = {
        "sequence_count": len(sequence_items),
        "sequence_bytes": sum(item["range"][1] - item["range"][0]
                              for item in sequence_items),
        "item_size": SEQUENCE_SIZE,
        "terminator_value": SEQUENCE_END,
        "terminator_width": 4,
        "record_index_domain": sorted({item["record_index"] for item in sequence_items}),
        "duration_domain": sorted({item["duration"] for item in sequence_items}),
        "items": sequence_items,
    }

    covered: set[int] = set()
    for item in descriptor_items:
        covered.update(range(item["range"][0], item["range"][1]))
    for item in sequence_items:
        covered.update(range(item["range"][0], item["range"][1]))
    for table in descriptor_tables + group_tables:
        covered.update(range(table["range"][0], table["range"][1]))
    pad_items: list[dict[str, Any]] = []
    cursor = CLAIM[0]
    while cursor < CLAIM[1]:
        if cursor in covered:
            cursor += 1
            continue
        start = cursor
        while cursor < CLAIM[1] and cursor not in covered:
            cursor += 1
        raw = rom[start:cursor]
        if raw != bytes(len(raw)):
            raise ValueError("unattributed claim bytes are not zero padding")
        pad_items.append({"range": [start, cursor], "bytes": len(raw),
                          "bytes_sha256": _digest(raw)})
    if len(pad_items) != PAD_TOTAL:
        raise ValueError("padding denominator changed")
    pad_size = sum(item["bytes"] for item in pad_items)
    if pad_size != PAD_BYTES:
        raise ValueError("padding byte denominator changed")
    if len(covered) + pad_size != CLAIM[1] - CLAIM[0]:
        raise ValueError("claim coverage is not exact")

    pair_items: list[dict[str, Any]] = []
    for index, (descriptor_table, group_table) in enumerate(zip(descriptor_tables,
                                                                group_tables)):
        pair_items.append({
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

    table_items: list[dict[str, Any]] = []
    for index, table in enumerate(descriptor_tables + group_tables):
        table_items.append({
            "table_index": index,
            "kind": "descriptor_table" if index < len(descriptor_tables) else "group_table",
            "range": table["range"],
            "slot_count": table["slot_count"],
            "slots": table["slots"],
        })

    structure = {
        "descriptors": descriptors,
        "sequences": sequences,
        "pointer_slots": {
            "slot_count": len(slots),
            "pointer_slot_bytes": len(slots) * 4,
            "table_count": len(table_items),
            "tables": table_items,
        },
        "base_pairs": {"pair_count": len(pair_items), "items": pair_items},
        "padding": {"segment_count": len(pad_items), "padding_bytes": pad_size,
                    "items": pad_items},
        "byte_attribution": {
            "total_bytes": CLAIM[1] - CLAIM[0],
            "descriptor_bytes": descriptors["descriptor_bytes"],
            "sequence_bytes": sequences["sequence_bytes"],
            "pointer_slot_bytes": len(slots) * 4,
            "padding_bytes": pad_size,
            "unattributed_bytes": 0,
        },
    }

    if _digest(rom[CLAIM[0]:CLAIM[1]]) != CLAIM_DIGEST:
        raise ValueError("claim identity changed")
    if _digest(rom[FULL[0]:FULL[1]]) != FULL_DIGEST:
        raise ValueError("full segment identity changed")
    if _digest(rom[TAIL[0]:TAIL[1]]) != TAIL_DIGEST:
        raise ValueError("excluded tail identity changed")

    for span, digest, label in (
        (ALLOCATOR, ALLOCATOR_DIGEST, "allocator"),
        (SELECT, SELECT_DIGEST, "renderer select"),
        (STEP, STEP_DIGEST, "renderer step"),
        (ADVANCE, ADVANCE_DIGEST, "renderer advance"),
    ):
        if _digest(rom[span[0]:span[1]]) != digest:
            raise ValueError(f"{label} identity changed")

    def _halfwords(loads: tuple[int, int], halves: tuple[int, int],
                   call_site: int, call_half: int) -> None:
        for site, wanted in zip(loads, halves):
            half = _read(rom, site)
            if half != wanted:
                raise ValueError("caller literal load halfword changed")
            if (half & 0xF800) != 0x4800:
                raise ValueError("caller literal load is not a literal load")
        if _read(rom, call_site) != call_half:
            raise ValueError("caller call halfword changed")
        if (call_half & 0xF800) != 0xF000:
            raise ValueError("caller call is not a long branch")

    _halfwords(LOAD_A, HALF_A, CALL_A, CALL_HALF_A)
    _halfwords(LOAD_B, HALF_B, CALL_B, CALL_HALF_B)

    for span, digest, label in (
        (CALLER_A, CALLER_A_DIGEST, "caller a"),
        (POOL_A, POOL_A_DIGEST, "caller a literal pool"),
        (CALLER_B, CALLER_B_DIGEST, "caller b"),
        (POOL_B, POOL_B_DIGEST, "caller b literal pool"),
    ):
        if _digest(rom[span[0]:span[1]]) != digest:
            raise ValueError(f"{label} identity changed")
    for value, expected in PINNED.items():
        if _find_all(rom, value) != expected:
            raise ValueError("consumer literal denominator changed")

    def _caller(name: str, code: tuple[int, int], pool: tuple[int, int],
                loads: tuple[int, int], halves: tuple[int, int],
                call_site: int, call_half: int) -> dict[str, Any]:
        pool_sites: list[int] = []
        for site, wanted in zip(loads, halves):
            half = _read(rom, site)
            resolved = ((site + 4) & ~3) + (half & 0xFF) * 4
            if not pool[0] <= resolved < pool[1]:
                raise ValueError("caller literal pool alignment changed")
            pool_sites.append(resolved)
        if _read(rom, call_site) != call_half:
            raise ValueError("caller call halfword changed")
        if (call_half & 0xF800) != 0xF000:
            raise ValueError("caller call is not a long branch")
        values = [_dword(rom, site) for site in pool_sites]
        match = None
        for item in pair_items:
            if item["r0_literal"] == values[0] and item["r1_literal"] == values[1]:
                match = item
                break
        if match is None:
            raise ValueError("caller base pair is not part of the pool")
        return {
            "caller_id": f"animation-descriptor-base-caller-{name}",
            "code_range": list(code),
            "code_sha256": _digest(rom[code[0]:code[1]]),
            "literal_pool_range": list(pool),
            "literal_pool_sha256": _digest(rom[pool[0]:pool[1]]),
            "literal_load_sites": list(loads),
            "literal_load_halfwords": list(halves),
            "literal_pool_sites": pool_sites,
            "literal_values": values,
            "base_pair_index": match["pair_index"],
            "call_site": call_site,
            "call_halfword": call_half,
            "call_target": ALLOCATOR_TARGET,
        }

    callers = [
        _caller("a", CALLER_A, POOL_A, LOAD_A, HALF_A, CALL_A, CALL_HALF_A),
        _caller("b", CALLER_B, POOL_B, LOAD_B, HALF_B, CALL_B, CALL_HALF_B),
    ]

    descriptor_literals: dict[str, Any] = {}
    group_literals: dict[str, Any] = {}
    r0_occurrences = 0
    r1_occurrences = 0
    pool_count = 0
    for pair in pair_items:
        for key, bucket, register in (("r0_literal", descriptor_literals, 0),
                                      ("r1_literal", group_literals, 1)):
            literal = pair[key]
            sites = _find_all(rom, literal)
            loaders = []
            for site in sites:
                found, address = _loader(rom, site)
                if found != register:
                    raise ValueError("literal loader register changed")
                loaders.append({"site": site, "loader": address})
            bucket[f"0x{literal:08X}"] = {
                "register": REGISTERS[register],
                "occurrence_denominator": len(sites),
                "sites": sites,
                "loaders": loaders,
            }
            if register == 0:
                r0_occurrences += len(sites)
                # Each r0 literal anchors one literal pool that also holds the
                # matching r1 literal, so this counts the pools of the pair.
                pool_count += len(sites)
            else:
                r1_occurrences += len(sites)
    binding = {
        "scan_limit_bytes": SCAN_LIMIT,
        "rule": "nearest preceding Thumb LDR-literal instruction resolving to the literal site",
        "descriptor_table_literals": descriptor_literals,
        "group_table_literals": group_literals,
        "literal_occurrence_count": r0_occurrences + r1_occurrences,
        "r0_literal_occurrence_count": r0_occurrences,
        "r1_literal_occurrence_count": r1_occurrences,
        "base_pair_pool_count": pool_count,
    }

    consumer = {
        "identity_ranges": [
            {"label": "allocator", "range": list(ALLOCATOR),
             "bytes_sha256": ALLOCATOR_DIGEST},
            {"label": "renderer_select", "range": list(SELECT),
             "bytes_sha256": SELECT_DIGEST},
            {"label": "renderer_step", "range": list(STEP),
             "bytes_sha256": STEP_DIGEST},
            {"label": "renderer_advance", "range": list(ADVANCE),
             "bytes_sha256": ADVANCE_DIGEST},
        ],
        "allocator_object_fields": {"group_index": 0x14, "record_slot": 0x16,
                                    "descriptor_table": 0x1C, "group_table": 0x20},
        "allocator_call_target": ALLOCATOR_TARGET,
        "located_callers": callers,
        "located_caller_count": len(callers),
        "pinned_literal_occurrence_denominator": {
            f"0x{value:08X}": offsets for value, offsets in PINNED.items()},
        "literal_loader_binding": binding,
        "caller_site_denominator": {
            "base_pair_count": len(pair_items),
            "base_pair_pools": binding["base_pair_pool_count"],
            "attributed_callers": len(callers),
            "attributed_pools": len(callers),
            "unattributed_pools": binding["base_pair_pool_count"] - len(callers),
            "closed": False,
        },
    }

    claim = {
        "id": "animation-descriptor-pool-45832c",
        "range": list(CLAIM),
        "primary_class": PRIMARY_CLASS,
        "claim_kind": CLAIM_KIND,
        "bytes_sha256": CLAIM_DIGEST,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "claim": {"range": list(CLAIM), "bytes": CLAIM[1] - CLAIM[0],
                  "bytes_sha256": CLAIM_DIGEST,
                  "primary_class": PRIMARY_CLASS, "claim_kind": CLAIM_KIND},
        "descriptors": structure["descriptors"],
        "sequences": structure["sequences"],
        "pointer_slots": structure["pointer_slots"],
        "base_pairs": structure["base_pairs"],
        "padding": structure["padding"],
        "byte_attribution": structure["byte_attribution"],
        "consumer_contract": consumer,
        "excluded_regions": [{
            "range": list(TAIL),
            "bytes": TAIL[1] - TAIL[0],
            "bytes_sha256": TAIL_DIGEST,
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
            "promotion_bytes": CLAIM[1] - CLAIM[0],
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


def _expected_manifest(root: Path, payload_raw: bytes, artifact: Path) -> dict[str, Any]:
    exporter = Path("tools/export_rom_animation_descriptor_pool_v2.py")
    verifier = Path("tools/verify_rom_animation_descriptor_pool_v2.py")
    test = Path("tests/test_export_rom_animation_descriptor_pool_v2.py")
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _digest(payload_raw)}},
        "summary": {
            "descriptor_count": DESCRIPTOR_TOTAL,
            "descriptor_entry_count": ENTRY_TOTAL,
            "sequence_count": SEQUENCE_TOTAL,
            "base_pair_count": PAIR_TOTAL,
            "promotion_bytes": CLAIM[1] - CLAIM[0],
        },
        "producer": {"command": ["python3", exporter.as_posix(), "--root", ".",
                                 "--output", artifact.as_posix()]},
        "verifier": {"command": ["python3", verifier.as_posix(), "--root", ".",
                                  "--artifact", artifact.as_posix()]},
        "implementation": {
            "exporter_sha256": _digest((root / exporter).read_bytes()),
            "verifier_sha256": _digest((root / verifier).read_bytes()),
            "test_sha256": _digest((root / test).read_bytes()),
        },
    }


def verify_artifact(root: Path, artifact: Path,
                    expected_artifact: Path | None = None) -> dict[str, Any]:
    """Verify one published artifact directory; never partially succeed."""
    try:
        root = root.resolve(strict=True)
        artifact = artifact.resolve(strict=True)
        if not artifact.is_relative_to(root):
            raise ValueError("artifact escapes the repository root")
        if artifact.is_symlink():
            raise ValueError("artifact directory is a symlink")
        members = sorted(path.name for path in artifact.iterdir())
        if members != [MANIFEST_NAME, PAYLOAD_NAME]:
            raise ValueError(f"artifact members changed: {members}")
        for member in artifact.iterdir():
            if member.is_symlink():
                raise ValueError("artifact member is a symlink")
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        manifest_raw = (artifact / MANIFEST_NAME).read_bytes()
        if payload_raw != _canonical(json.loads(payload_raw.decode("utf-8"))):
            raise ValueError("payload is not canonical JSON")
        if manifest_raw != _canonical(json.loads(manifest_raw.decode("utf-8"))):
            raise ValueError("manifest is not canonical JSON")
        rom = (root / ROM_PATH).read_bytes()
        rebuilt = _rebuild(rom)
        if payload_raw != _canonical(rebuilt):
            raise ValueError("payload does not match the independent ROM rebuild")
        target = expected_artifact if expected_artifact is not None else artifact
        try:
            relative = target.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            raise ValueError("expected artifact escapes the repository root")
        expected = _expected_manifest(root, payload_raw, Path(relative))
        if manifest_raw != _canonical(expected):
            raise ValueError("manifest does not match the expected manifest")
        return {
            "schema": VERIFY_SCHEMA,
            "verified": True,
            "errors": [],
            "artifact": relative,
            "descriptor_count": rebuilt["descriptors"]["descriptor_count"],
            "descriptor_entry_count": rebuilt["descriptors"]["entry_count"],
            "base_pair_count": rebuilt["base_pairs"]["pair_count"],
            "promotion_bytes": rebuilt["promotion"]["promotion_bytes"],
        }
    except Exception as error:  # fail closed
        return {
            "schema": VERIFY_SCHEMA,
            "verified": False,
            "errors": [f"{type(error).__name__}: {error}"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--artifact-dir", type=Path, dest="artifact_dir",
                        help="alias of --artifact")
    args = parser.parse_args()
    artifact = args.artifact if args.artifact is not None else args.artifact_dir
    if artifact is None:
        parser.error("one of --artifact or --artifact-dir is required")
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
