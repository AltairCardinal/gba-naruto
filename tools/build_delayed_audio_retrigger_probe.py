#!/usr/bin/env python3
"""Replace an active cue on the same player after N SoundMain invocations."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

try:
    from tools.build_controlled_audio_runtime_probe import BASE_SHA1
    from tools.build_save_state_runtime_probe import encode_thumb_bl
except ModuleNotFoundError:
    from build_controlled_audio_runtime_probe import BASE_SHA1
    from build_save_state_runtime_probe import encode_thumb_bl


ROM_BASE = 0x08000000
INIT_HOOK = 0x08061E28
MAIN_HOOK = 0x08061F76
SOUND_INIT = 0x0809AA3C
SOUND_DISPATCH = 0x0809AAC0
SOUND_MAIN_WRAPPER = 0x0809AAB4
INIT_STUB = 0x0809E800
INIT_STUB_OFFSET = INIT_STUB - ROM_BASE
INIT_STUB_SIZE = 28
MAIN_STUB = 0x0809E840
MAIN_STUB_OFFSET = MAIN_STUB - ROM_BASE
MAIN_STUB_SIZE = 44
SCRATCH_COUNTER = 0x0203FF50


def _sound_id(value: int) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError("sound ID must fit in one byte")
    return value


def build_probe(
    base: bytes,
    *,
    first_sound_id: int,
    replacement_sound_id: int,
    switch_after_invocations: int,
) -> bytes:
    first_sound_id = _sound_id(first_sound_id)
    replacement_sound_id = _sound_id(replacement_sound_id)
    if not 1 <= switch_after_invocations <= 0xFF:
        raise ValueError("switch invocations must be in 1..255")
    # One unhooked SoundMain call at 0x08061006 produces capture invocation 0.
    # The per-frame hook therefore counts only the remaining old-cue chunks.
    per_frame_delay = switch_after_invocations - 1
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")

    rom = bytearray(base)
    init_hook_offset = INIT_HOOK - ROM_BASE
    main_hook_offset = MAIN_HOOK - ROM_BASE
    if rom[init_hook_offset:init_hook_offset + 4] != encode_thumb_bl(
        INIT_HOOK, SOUND_INIT
    ):
        raise ValueError("m4a initialization call-site bytes do not match")
    if rom[main_hook_offset:main_hook_offset + 4] != encode_thumb_bl(
        MAIN_HOOK, SOUND_MAIN_WRAPPER
    ):
        raise ValueError("SoundMain call-site bytes do not match")
    if any(rom[INIT_STUB_OFFSET:INIT_STUB_OFFSET + INIT_STUB_SIZE]):
        raise ValueError("initialization stub region is not zero-filled")
    if any(rom[MAIN_STUB_OFFSET:MAIN_STUB_OFFSET + MAIN_STUB_SIZE]):
        raise ValueError("SoundMain stub region is not zero-filled")

    init_stub = struct.pack("<H", 0xB500)  # push {lr}
    init_stub += encode_thumb_bl(INIT_STUB + len(init_stub), SOUND_INIT)
    init_stub += struct.pack(
        "<HHHH", 0x4904, 0x2000 | per_frame_delay,
        0x6008, 0x2000 | first_sound_id,
    )
    init_stub += encode_thumb_bl(INIT_STUB + len(init_stub), SOUND_DISPATCH)
    init_stub += struct.pack("<HH", 0xBC01, 0x4700)  # pop {r0}; bx r0
    init_stub += bytes(24 - len(init_stub))
    init_stub += struct.pack("<I", SCRATCH_COUNTER)
    if len(init_stub) != INIT_STUB_SIZE:
        raise AssertionError(len(init_stub))

    main_halfwords = (
        0xB510,  # push {r4,lr}
        0x4C09,  # ldr r4, =SCRATCH_COUNTER
        0x6820,  # ldr r0, [r4]
        0x2800,  # cmp r0, #0
        0xD002,  # beq trigger
        0x3801,  # subs r0, #1
        0x6020,  # str r0, [r4]
        0xE005,  # b call_soundmain
        0x2000,  # trigger: movs r0, #0
        0x3801,  # subs r0, #1 (sentinel 0xFFFFFFFF)
        0x6020,  # str r0, [r4]
        0x2000 | replacement_sound_id,
    )
    main_stub = struct.pack(f"<{len(main_halfwords)}H", *main_halfwords)
    main_stub += encode_thumb_bl(MAIN_STUB + len(main_stub), SOUND_DISPATCH)
    main_stub += encode_thumb_bl(MAIN_STUB + len(main_stub), SOUND_MAIN_WRAPPER)
    main_stub += struct.pack("<HHH", 0xBC10, 0xBC01, 0x4700)
    main_stub += bytes(40 - len(main_stub))
    main_stub += struct.pack("<I", SCRATCH_COUNTER)
    if len(main_stub) != MAIN_STUB_SIZE:
        raise AssertionError(len(main_stub))

    rom[INIT_STUB_OFFSET:INIT_STUB_OFFSET + INIT_STUB_SIZE] = init_stub
    rom[MAIN_STUB_OFFSET:MAIN_STUB_OFFSET + MAIN_STUB_SIZE] = main_stub
    rom[init_hook_offset:init_hook_offset + 4] = encode_thumb_bl(
        INIT_HOOK, INIT_STUB
    )
    rom[main_hook_offset:main_hook_offset + 4] = encode_thumb_bl(
        MAIN_HOOK, MAIN_STUB
    )
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--first-sound-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument(
        "--replacement-sound-id", type=lambda value: int(value, 0), required=True
    )
    parser.add_argument("--switch-after-invocations", type=int, required=True)
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(),
        first_sound_id=args.first_sound_id,
        replacement_sound_id=args.replacement_sound_id,
        switch_after_invocations=args.switch_after_invocations,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
