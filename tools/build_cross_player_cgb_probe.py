#!/usr/bin/env python3
"""Clone one CGB cue to another player and start both before SoundMain."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_controlled_audio_runtime_probe import (
        BASE_SHA1,
        HOOK,
        ROM_BASE,
        SOUND_DISPATCH,
        SOUND_INIT,
        STUB,
        STUB_OFFSET,
    )
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_controlled_audio_runtime_probe import (
        BASE_SHA1,
        HOOK,
        ROM_BASE,
        SOUND_DISPATCH,
        SOUND_INIT,
        STUB,
        STUB_OFFSET,
    )
    from build_save_state_runtime_probe import encode_thumb_bl


MASTER_OFFSET = 0x465B70
STUB_SIZE = 22


def _sound_id(value: int) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError("sound ID must fit in one byte")
    return value


def build_probe(
    base: bytes,
    *,
    source_sound_id: int,
    clone_sound_id: int,
    clone_player_slot: int,
) -> bytes:
    source_sound_id = _sound_id(source_sound_id)
    clone_sound_id = _sound_id(clone_sound_id)
    if source_sound_id == clone_sound_id:
        raise ValueError("clone sound ID must differ from source")
    if clone_player_slot not in range(4):
        raise ValueError("clone player slot must be in 0..3")
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")

    rom = bytearray(base)
    hook_offset = HOOK - ROM_BASE
    if rom[hook_offset:hook_offset + 4] != encode_thumb_bl(HOOK, SOUND_INIT):
        raise ValueError("m4a initialization call-site bytes do not match")
    if any(rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE]):
        raise ValueError("cross-player CGB stub region is not zero-filled")
    source_offset = MASTER_OFFSET + source_sound_id * 8
    clone_offset = MASTER_OFFSET + clone_sound_id * 8
    if source_offset + 8 > len(rom) or clone_offset + 8 > len(rom):
        raise ValueError("sound ID master entry lies outside ROM")
    source_row = rom[source_offset:source_offset + 8]
    if not any(source_row[:4]):
        raise ValueError("source sound ID has no descriptor")
    clone_row = bytearray(source_row)
    struct.pack_into("<HH", clone_row, 4, clone_player_slot, clone_player_slot)
    rom[clone_offset:clone_offset + 8] = clone_row

    stub = struct.pack("<H", 0xB500)  # push {lr}
    stub += encode_thumb_bl(STUB + len(stub), SOUND_INIT)
    for sound_id in (clone_sound_id, source_sound_id):
        stub += struct.pack("<H", 0x2000 | sound_id)
        stub += encode_thumb_bl(STUB + len(stub), SOUND_DISPATCH)
    stub += struct.pack("<HH", 0xBC01, 0x4700)
    if len(stub) != STUB_SIZE:
        raise AssertionError(len(stub))
    rom[STUB_OFFSET:STUB_OFFSET + STUB_SIZE] = stub
    rom[hook_offset:hook_offset + 4] = encode_thumb_bl(HOOK, STUB)
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--source-sound-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--clone-sound-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--clone-player-slot", type=int, required=True)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        source_sound_id=args.source_sound_id,
        clone_sound_id=args.clone_sound_id,
        clone_player_slot=args.clone_player_slot,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
