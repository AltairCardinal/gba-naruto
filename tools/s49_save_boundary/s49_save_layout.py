#!/usr/bin/env python3
"""Decode one 32 KiB cartridge-SRAM image into records / slots.

Two formats live in the same 32 KiB SRAM window:

``original``
    Ten records described by the reverse line's descriptor table
    (ROM ``0x53D848``).  Each record is
    ``19-byte identity header + payload_length payload bytes + 1 checksum
    byte``; the checksum is ``~sum(payload) & 0xFF``.  The next record starts
    ``payload_length + 0x14`` bytes further.  An unused record is all ``FF``.

``remake``
    Two 4096-byte slots.  Each slot is
    ``'KBCS' | version | reserved | u16 payload_size | u32 generation |
    payload | u32 CRC32``.  The payload is the campaign state
    (chapter, flags, party, inventory, per-character progression).

The decoders are pure functions over bytes so they can be unit-checked
offline without an emulator.
"""
from __future__ import annotations

import zlib

from s49_save_common import (
    ORIGINAL_BATTLE_POOL_DESCRIPTOR,
    ORIGINAL_BATTLE_POOL_SLOT_SIZE,
    ORIGINAL_BATTLE_POOL_SLOTS,
    ORIGINAL_DESCRIPTORS,
    ORIGINAL_RECORD_HEADER,
    ORIGINAL_RECORD_HEADER_SIZE,
    ORIGINAL_SRAM_ADVANCE_OVERHEAD,
    REMAKE_CHARACTER_CAPACITY,
    REMAKE_CHARACTER_SIZE,
    REMAKE_CRC_OFFSET,
    REMAKE_EQUIPPED_TOOL_CAPACITY,
    REMAKE_HEADER_SIZE,
    REMAKE_INVENTORY_SIZE,
    REMAKE_MAGIC,
    REMAKE_MATERIAL_CAPACITY,
    REMAKE_NINJA_TOOL_CAPACITY,
    REMAKE_PARTY_CAPACITY,
    REMAKE_PAYLOAD_OFFSET,
    REMAKE_PAYLOAD_SIZE,
    REMAKE_PRIMARY_ACTION_CAPACITY,
    REMAKE_SECONDARY_ACTION_CAPACITY,
    REMAKE_SLOT_COUNT,
    REMAKE_SLOT_SIZE,
    REMAKE_VERSION,
    original_record_offsets,
    sha256_bytes,
)


def original_checksum(payload: bytes) -> int:
    return (~sum(payload)) & 0xFF


def decode_original(image: bytes) -> dict:
    """Decode the original's ten descriptor records out of ``image``."""

    offsets = original_record_offsets()
    records = []
    for entry, offset in zip(ORIGINAL_DESCRIPTORS, offsets):
        length = entry["payload_length"]
        header = image[offset:offset + ORIGINAL_RECORD_HEADER_SIZE]
        payload = image[
            offset + ORIGINAL_RECORD_HEADER_SIZE:
            offset + ORIGINAL_RECORD_HEADER_SIZE + length
        ]
        checksum = image[offset + ORIGINAL_RECORD_HEADER_SIZE + length]
        erased = all(byte == 0xFF for byte in header)
        expected = original_checksum(payload)
        record = {
            "descriptor_index": entry["index"],
            "sram_offset": offset,
            "header_offset": offset,
            "payload_offset": offset + ORIGINAL_RECORD_HEADER_SIZE,
            "payload_length": length,
            "checksum_offset": offset + ORIGINAL_RECORD_HEADER_SIZE + length,
            "record_bytes": length + ORIGINAL_SRAM_ADVANCE_OVERHEAD,
            "header_hex": header.hex(),
            "header_text": header.rstrip(b"\x00").decode("latin-1"),
            "header_is_identity": header == ORIGINAL_RECORD_HEADER,
            "erased": erased,
            "checksum": checksum,
            "checksum_expected": expected,
            "checksum_ok": checksum == expected,
            "payload_sha256": sha256_bytes(payload),
            "payload_nonzero_bytes": sum(1 for b in payload if b),
        }
        if entry["index"] == ORIGINAL_BATTLE_POOL_DESCRIPTOR:
            record["is_battle_pool"] = True
            record["battle_pool_slot_size"] = ORIGINAL_BATTLE_POOL_SLOT_SIZE
            record["battle_pool_slots"] = ORIGINAL_BATTLE_POOL_SLOTS
        records.append(record)
    active = [r for r in records if not r["erased"]]
    return {
        "format": "original",
        "sram_size": len(image),
        "record_count": len(records),
        "records": records,
        "active_record_count": len(active),
        "active_descriptors": [r["descriptor_index"] for r in active],
        "all_active_checksums_ok": all(r["checksum_ok"] for r in active),
    }


def _decode_remake_character(block: bytes) -> dict:
    offset = 0
    active = block[offset]
    offset += 1
    level = block[offset]
    offset += 1
    experience = block[offset] | (block[offset + 1] << 8)
    offset += 2
    training_points = block[offset]
    offset += 1
    initialized = block[offset]
    offset += 1
    primary = list(block[offset:offset + REMAKE_PRIMARY_ACTION_CAPACITY])
    offset += REMAKE_PRIMARY_ACTION_CAPACITY
    secondary = list(
        block[offset:offset + REMAKE_SECONDARY_ACTION_CAPACITY]
    )
    offset += REMAKE_SECONDARY_ACTION_CAPACITY
    tools = list(block[offset:offset + REMAKE_EQUIPPED_TOOL_CAPACITY])
    offset += REMAKE_EQUIPPED_TOOL_CAPACITY
    return {
        "active": active,
        "level": level,
        "experience": experience,
        "training_points": training_points,
        "action_states_initialized": initialized,
        "primary_action_levels": primary,
        "secondary_action_levels": secondary,
        "equipped_tools": tools,
        "bytes_consumed": offset,
    }


def decode_remake(image: bytes) -> dict:
    """Decode the remake's two ``KBCS`` slots out of ``image``."""

    slots = []
    for index in range(REMAKE_SLOT_COUNT):
        base = index * REMAKE_SLOT_SIZE
        block = image[base:base + REMAKE_SLOT_SIZE]
        magic = block[0:4]
        version = block[4]
        reserved = block[5]
        payload_size = block[6] | (block[7] << 8)
        generation = int.from_bytes(block[8:12], "little")
        stored_crc = int.from_bytes(
            block[REMAKE_CRC_OFFSET:REMAKE_CRC_OFFSET + 4], "little"
        )
        computed_crc = zlib.crc32(block[:REMAKE_CRC_OFFSET]) & 0xFFFFFFFF
        erased = all(byte == 0xFF for byte in block)
        slot = {
            "slot_index": index,
            "sram_offset": base,
            "magic": magic.hex(),
            "magic_ok": magic == REMAKE_MAGIC,
            "version": version,
            "version_ok": version == REMAKE_VERSION,
            "reserved": reserved,
            "payload_size": payload_size,
            "payload_size_ok": payload_size == REMAKE_PAYLOAD_SIZE,
            "generation": generation,
            "stored_crc32": stored_crc,
            "computed_crc32": computed_crc,
            "crc_ok": stored_crc == computed_crc,
            "erased": erased,
            "slot_sha256": sha256_bytes(block),
        }
        if slot["magic_ok"] and slot["payload_size_ok"]:
            payload = block[REMAKE_PAYLOAD_OFFSET:
                            REMAKE_PAYLOAD_OFFSET + payload_size]
            offset = 0
            chapter_id = payload[offset] | (payload[offset + 1] << 8)
            offset += 2
            flags = int.from_bytes(payload[offset:offset + 4], "little")
            offset += 4
            party = list(payload[offset:offset + REMAKE_PARTY_CAPACITY])
            offset += REMAKE_PARTY_CAPACITY
            party_reserved = payload[offset]
            offset += 1
            ninja_tools = list(
                payload[offset:offset + REMAKE_NINJA_TOOL_CAPACITY]
            )
            offset += REMAKE_NINJA_TOOL_CAPACITY
            materials = list(
                payload[offset:offset + REMAKE_MATERIAL_CAPACITY]
            )
            offset += REMAKE_MATERIAL_CAPACITY
            characters = []
            for _ in range(REMAKE_CHARACTER_CAPACITY):
                characters.append(
                    _decode_remake_character(
                        payload[offset:offset + REMAKE_CHARACTER_SIZE]
                    )
                )
                offset += REMAKE_CHARACTER_SIZE
            slot["payload"] = {
                "chapter_id": chapter_id,
                "flags": flags,
                "party": party,
                "party_reserved": party_reserved,
                "ninja_tools": ninja_tools,
                "materials": materials,
                "characters": characters,
                "payload_consumed": offset,
                "payload_size": payload_size,
            }
            slot["payload_sha256"] = sha256_bytes(payload)
        slots.append(slot)
    return {
        "format": "remake",
        "sram_size": len(image),
        "slot_count": len(slots),
        "slots": slots,
        "active_slot_count": sum(
            1 for s in slots if s["magic_ok"] and not s["erased"]
        ),
        "all_active_crc_ok": all(
            s["crc_ok"] for s in slots if s["magic_ok"] and not s["erased"]
        ),
    }


def decode_image(image: bytes) -> dict:
    """Decode an SRAM image with whichever format it carries."""

    original = decode_original(image)
    remake = decode_remake(image)
    original_active = original["active_record_count"]
    remake_active = remake["active_slot_count"]
    if original_active and remake_active:
        verdict = "both"
    elif original_active:
        verdict = "original"
    elif remake_active:
        verdict = "remake"
    else:
        verdict = "empty"
    return {
        "verdict": verdict,
        "original": original,
        "remake": remake,
    }


def slot_field_map(slot: dict) -> list[tuple[int, int, str]]:
    """(offset, size, name) for every field of a decoded remake slot."""

    if "payload" not in slot:
        return []
    base = slot["sram_offset"]
    fields = [
        (base + 0, 4, "magic"),
        (base + 4, 1, "version"),
        (base + 5, 1, "reserved"),
        (base + 6, 2, "payload_size"),
        (base + 8, 4, "generation"),
    ]
    payload_base = base + REMAKE_PAYLOAD_OFFSET
    offset = payload_base
    fields.append((offset, 2, "chapter_id"))
    offset += 2
    fields.append((offset, 4, "flags"))
    offset += 4
    fields.append((offset, REMAKE_PARTY_CAPACITY, "party"))
    offset += REMAKE_PARTY_CAPACITY
    fields.append((offset, 1, "party_reserved"))
    offset += 1
    fields.append((offset, REMAKE_NINJA_TOOL_CAPACITY, "inventory.ninja_tools"))
    offset += REMAKE_NINJA_TOOL_CAPACITY
    fields.append((offset, REMAKE_MATERIAL_CAPACITY, "inventory.materials"))
    offset += REMAKE_MATERIAL_CAPACITY
    for index in range(REMAKE_CHARACTER_CAPACITY):
        prefix = "characters[%d]." % index
        fields.append((offset, 1, prefix + "active"))
        offset += 1
        fields.append((offset, 1, prefix + "level"))
        offset += 1
        fields.append((offset, 2, prefix + "experience"))
        offset += 2
        fields.append((offset, 1, prefix + "training_points"))
        offset += 1
        fields.append((offset, 1, prefix + "action_states_initialized"))
        offset += 1
        fields.append(
            (offset, REMAKE_PRIMARY_ACTION_CAPACITY,
             prefix + "primary_action_levels"))
        offset += REMAKE_PRIMARY_ACTION_CAPACITY
        fields.append(
            (offset, REMAKE_SECONDARY_ACTION_CAPACITY,
             prefix + "secondary_action_levels"))
        offset += REMAKE_SECONDARY_ACTION_CAPACITY
        fields.append(
            (offset, REMAKE_EQUIPPED_TOOL_CAPACITY,
             prefix + "equipped_tools"))
        offset += REMAKE_EQUIPPED_TOOL_CAPACITY
    fields.append((base + REMAKE_CRC_OFFSET, 4, "crc32"))
    return fields


def original_field_map(record: dict) -> list[tuple[int, int, str]]:
    base = record["sram_offset"]
    return [
        (base, ORIGINAL_RECORD_HEADER_SIZE, "identity_header"),
        (record["payload_offset"], record["payload_length"], "payload"),
        (record["checksum_offset"], 1, "checksum"),
    ]


__all__ = [
    "decode_image",
    "decode_original",
    "decode_remake",
    "original_checksum",
    "original_field_map",
    "slot_field_map",
    "REMAKE_HEADER_SIZE",
    "REMAKE_INVENTORY_SIZE",
]
