#!/usr/bin/env python3
"""Extract the 100-entry message command pointer table used by 0x08079668."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

TABLE_OFFSET = 0x599634
ENTRY_COUNT = 100
ENTRY_SIZE = 4


def build_bank(rom: bytes) -> dict:
    entries = []
    for index in range(ENTRY_COUNT):
        offset = TABLE_OFFSET + index * 4
        pointer = struct.unpack_from("<I", rom, offset)[0]
        if pointer != 0 and not 0x08000000 <= pointer < 0x08000000 + len(rom):
            raise ValueError(f"audio command {index} pointer out of ROM: 0x{pointer:08X}")
        target = pointer - 0x08000000 if pointer else None
        end = rom.find(b"\0", target, min(len(rom), target + 256)) if target is not None else -1
        raw = rom[target:end if end >= 0 else target] if target is not None else b""
        try:
            label = raw.decode("cp932")
        except UnicodeDecodeError:
            label = None
        entries.append({
            "command_id": 0x80 + index,
            "_index": index,
            "_raw_offset": offset,
            "rom_offset": offset,
            "rom_offset_hex": f"0x{offset:X}",
            "message_ptr": pointer,
            "message_ptr_hex": struct.pack("<I", pointer).hex(),
            "target_offset": target,
            "target_offset_hex": f"0x{target:X}" if target is not None else None,
            "message_raw_hex": raw.hex(),
            "diagnostic_cp932": label,
        })
    return {
        "version": 3,
        "description": "Message command 0x80..0xE3 pointer table consumed by dispatcher 0x08079668. Stored under the legacy audio slug pending catalog migration.",
        "structure_kind": "message-command-table",
        "legacy_slug": "audio",
        "table_offset": TABLE_OFFSET,
        "table_offset_hex": f"0x{TABLE_OFFSET:X}",
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
        "verification": "code_verified",
        "verification_method": "0x080796E4 indexes 0x08599634 and calls 0x08066758; that function passes the pointed zero-terminated data to text parser 0x0806626C and creates a message object.",
        "entry_format": {"fields": [{"offset": 0, "size": 4, "name": "message_ptr", "type": "u32"}]},
        "dispatcher": {"address": "0x08079668", "indexed_range": "0x80-0xE3", "message_call": "0x08066758", "text_parser": "0x0806626C"},
        "notes": "The former audio identity is revoked. 0x53F138 belongs to palettes; actual audio resources remain a separate unresolved target.",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sequel/content/audio/bank.json"))
    args = parser.parse_args()
    bank = build_bank(args.rom.read_bytes())
    args.output.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {ENTRY_COUNT} audio commands at 0x{TABLE_OFFSET:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
