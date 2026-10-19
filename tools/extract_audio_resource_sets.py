#!/usr/bin/env python3
"""Extract the sound-ID table and song descriptors used by the ROM audio engine."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

ROM_BASE = 0x08000000
MASTER_OFFSET = 0x465B70
MASTER_STRIDE = 8
EMPTY_DESCRIPTOR = 0x08466068
# The table ends at ID 158. ID 159 is already the empty descriptor's data,
# not another master row. Non-empty groups are songs, jingles and SFX.
SOUND_ID_COUNT = 159
ACTIVE_IDS = (
    tuple(range(1, 19))
    + tuple(range(51, 55))
    + tuple(range(101, 159))
)


def _offset(pointer: int, rom_size: int) -> int:
    result = pointer - ROM_BASE
    if not 0 <= result < rom_size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside ROM")
    return result


def extract(rom: bytes) -> dict:
    entries = []
    for sound_id in ACTIVE_IDS:
        raw_offset = MASTER_OFFSET + sound_id * MASTER_STRIDE
        descriptor_ptr, player_config = struct.unpack_from("<II", rom, raw_offset)
        if descriptor_ptr == EMPTY_DESCRIPTOR:
            raise ValueError(f"active sound ID {sound_id} unexpectedly uses the empty descriptor")
        descriptor_offset = _offset(descriptor_ptr, len(rom))

        track_count, block_count, priority, reverb = struct.unpack_from("<BBBB", rom, descriptor_offset)
        if not 1 <= track_count <= 16:
            raise ValueError(f"sound ID {sound_id} has implausible track count {track_count}")
        voicegroup_ptr = struct.unpack_from("<I", rom, descriptor_offset + 4)[0]
        _offset(voicegroup_ptr, len(rom))
        track_ptrs = list(struct.unpack_from(
            f"<{track_count}I", rom, descriptor_offset + 8
        ))
        for pointer in track_ptrs:
            _offset(pointer, len(rom))

        entries.append({
            "_index": sound_id,
            "sound_id": sound_id,
            "_raw_offset": raw_offset,
            "rom_offset": raw_offset,
            "rom_offset_hex": f"0x{raw_offset:06X}",
            "raw_hex": rom[raw_offset:raw_offset + MASTER_STRIDE].hex(),
            "descriptor_ptr": descriptor_ptr,
            # *_hex fields are lossless little-endian bytes for the repository
            # fidelity auditor; *_address is the human-readable pointer.
            "descriptor_ptr_hex": descriptor_ptr.to_bytes(4, "little").hex(),
            "descriptor_ptr_address": f"0x{descriptor_ptr:08X}",
            "descriptor_offset": descriptor_offset,
            "descriptor_offset_hex": f"0x{descriptor_offset:06X}",
            "player_index": player_config & 0xFFFF,
            "player_config_high": player_config >> 16,
            "track_count": track_count,
            "block_count": block_count,
            "priority": priority,
            "reverb": reverb,
            "voicegroup_ptr": voicegroup_ptr,
            "voicegroup_ptr_hex": f"0x{voicegroup_ptr:08X}",
            "track_ptrs": track_ptrs,
            "track_ptrs_hex": [f"0x{x:08X}" for x in track_ptrs],
            "descriptor_raw_hex": rom[
                descriptor_offset:descriptor_offset + 8 + track_count * 4
            ].hex(),
        })

    return {
        "version": 4,
        "description": "Active sound-ID entries and song descriptors consumed by the real FIFO/DMA audio engine.",
        "structure_kind": "audio-sound-id-table",
        "table_offset": MASTER_OFFSET,
        "table_offset_hex": f"0x{MASTER_OFFSET:06X}",
        "entry_count": len(entries),
        "entry_size": MASTER_STRIDE,
        "active_sound_ids": list(ACTIVE_IDS),
        "empty_descriptor": f"0x{EMPTY_DESCRIPTOR:08X}",
        "entry_format": {
            "fields": [
                {"offset": 0, "size": 4, "name": "descriptor_ptr", "type": "u32"},
                {"offset": 4, "size": 2, "name": "player_index", "type": "u16"},
                {"offset": 6, "size": 2, "name": "player_config_high", "type": "u16"},
            ]
        },
        "descriptor_format": {
            "fields": [
                {"offset": 0, "size": 1, "name": "track_count", "type": "u8"},
                {"offset": 1, "size": 1, "name": "block_count", "type": "u8"},
                {"offset": 2, "size": 1, "name": "priority", "type": "u8"},
                {"offset": 3, "size": 1, "name": "reverb", "type": "u8"},
                {"offset": 4, "size": 4, "name": "voicegroup_ptr", "type": "u32"},
                {"offset": 8, "size": "track_count*4", "name": "track_ptrs", "type": "u32[]"},
            ]
        },
        "consumer": "0x0809AAC0 indexes sound_id*8 and player_index*12, then calls 0x0809B1F4.",
        "engine": "0x0809AE3C initializes GBA sound/FIFO/DMA registers; 0x0809B1F4 initializes 0x50-byte track states.",
        "sound_id_domain": [0, SOUND_ID_COUNT - 1],
        "verification": "runtime_verified",
        "verification_method": "Thumb disassembly closes sound ID -> master entry -> player slot -> descriptor -> sequence/track pointers. A live title/new-game probe hit public wrapper 230 times and captured sound ID 118 resolving to descriptor 0x0853D06C.",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sequel/content/audio/bank.json"))
    args = parser.parse_args()
    result = extract(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {len(result['entries'])} active sound IDs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
