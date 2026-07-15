#!/usr/bin/env python3
"""Build the catalog record for the ROM's real FIFO/DMA audio engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ENGINE_OFFSET = 0x09AE3C
CODE_SIZE = 0x80


def extract(rom: bytes) -> dict:
    code = rom[ENGINE_OFFSET:ENGINE_OFFSET + CODE_SIZE]
    if len(code) != CODE_SIZE:
        raise ValueError("ROM is too short for audio engine code")
    return {
        "version": 3,
        "description": "Real GBA FIFO/DMA audio-engine initialization code, replacing the disproved message-dispatcher identity.",
        "structure_kind": "gba-fifo-dma-audio-engine-code",
        "table_offset": ENGINE_OFFSET,
        "table_offset_hex": f"0x{ENGINE_OFFSET:06X}",
        "entry_count": 1,
        "entry_size": CODE_SIZE,
        "entry_format": {"fields": [{"offset": 0, "size": CODE_SIZE, "name": "code", "type": "bytes"}]},
        "hardware_registers": [
            "0x04000060", "0x04000080", "0x04000084", "0x040000A0", "0x040000A4"
        ],
        "related_functions": {
            "sound_id_dispatch": "0x0809AAC0",
            "song_track_initializer": "0x0809B1F4",
            "stop_song": "0x0809B2D8",
            "public_sound_id_wrapper": "0x08061E6C",
        },
        "verification": "code_verified",
        "verification_method": "Literal and Thumb-flow audit proves writes to SOUNDCNT/FIFO/DMA registers and connects public sound-ID wrapper to the song descriptor loader.",
        "entries": [{
            "_index": 0,
            "_raw_offset": ENGINE_OFFSET,
            "rom_offset": ENGINE_OFFSET,
            "rom_offset_hex": f"0x{ENGINE_OFFSET:06X}",
            "code": code.hex(),
            "code_hex": code.hex(),
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sequel/content/sappy-engine/bank.json"))
    args = parser.parse_args()
    args.output.write_text(json.dumps(extract(args.rom.read_bytes()), indent=2) + "\n", encoding="utf-8")
    print(f"wrote real audio engine catalog to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
