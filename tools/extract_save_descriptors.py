#!/usr/bin/env python3
"""Extract save-buffer descriptors and their cumulative SRAM layout."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

TABLE_OFFSET = 0x53D848
ENTRY_COUNT = 10
ENTRY_SIZE = 8
SRAM_ADVANCE_OVERHEAD = 0x14
RECORD_HEADER_LENGTH = 0x13


def build_bank(rom: bytes) -> dict:
    entries = []
    sram_offset = 0
    for index in range(ENTRY_COUNT):
        raw_offset = TABLE_OFFSET + index * ENTRY_SIZE
        ewram_buffer, payload_length = struct.unpack_from("<II", rom, raw_offset)
        entries.append({
            "descriptor_index": index,
            "_index": index,
            "_raw_offset": raw_offset,
            "ewram_buffer": ewram_buffer,
            "ewram_buffer_hex": ewram_buffer.to_bytes(4, "little").hex(),
            "payload_length": payload_length,
            "payload_length_hex": payload_length.to_bytes(4, "little").hex(),
            "sram_record_offset": sram_offset,
            "sram_record_offset_hex": f"0x{sram_offset:04X}",
            "header_offset": sram_offset,
            "payload_offset": sram_offset + RECORD_HEADER_LENGTH,
            "checksum_offset": sram_offset + RECORD_HEADER_LENGTH + payload_length,
            "record_bytes_written": payload_length + SRAM_ADVANCE_OVERHEAD,
            "next_record_offset": sram_offset + payload_length + SRAM_ADVANCE_OVERHEAD,
        })
        sram_offset += payload_length + SRAM_ADVANCE_OVERHEAD
    return {
        "version": 3,
        "description": "Ten save-buffer descriptors consumed by 0x08068684. Each SRAM record is a 19-byte identity header, payload_length bytes, and one NOT-sum payload checksum; starts advance by payload_length+0x14.",
        "structure_kind": "save-buffer-descriptor-table",
        "table_offset": TABLE_OFFSET,
        "table_offset_hex": f"0x{TABLE_OFFSET:06X}",
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
        "entry_format": {"fields": [
            {"offset": 0, "size": 4, "name": "ewram_buffer", "type": "u32"},
            {"offset": 4, "size": 4, "name": "payload_length", "type": "u32"},
        ]},
        "verification": "runtime_verified",
        "verification_method": "After genuine tutorial victory, the in-game Save menu wrote a 32 KiB .sav. Active descriptors 0 and 2 contain the 19-byte Naruto-KONOHASENKI identity header and payload checksums matching ~sum(payload); unused records are all-FF. A cold ROM restart recognized slot 1 and restored the saved Konoha overworld. Static disassembly at 0x08068684 proves the same header+payload+checksum layout for every descriptor; group 3..9 wrappers remain code-level subchains.",
        "handler": "0x08068684",
        "save_wrapper": "0x080689A4 (groups 3..9)",
        "load_wrapper": "0x08068AF0 (groups 3..9)",
        "sram_advance_overhead": SRAM_ADVANCE_OVERHEAD,
        "record_header_length": RECORD_HEADER_LENGTH,
        "record_layout": "19-byte identity header + payload_length bytes + 1 checksum byte",
        "checksum": "bitwise NOT of the 8-bit sum of all payload bytes",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--write-bank", action="store_true")
    args = parser.parse_args()
    bank = build_bank(args.rom.read_bytes())
    if args.write_bank:
        path = Path(__file__).resolve().parent.parent / "sequel/content/save-state/bank.json"
        path.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(bank['entries'])} save descriptors")
    else:
        print(json.dumps(bank, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
