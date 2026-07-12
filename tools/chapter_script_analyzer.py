#!/usr/bin/env python3
"""Read-only structural analyzer for the opcodes observed in alternate scenario 39.

This module records exact command boundaries without assigning unproved operand
semantics.  Authoring remains restricted to ``chapter_script_codec``.
"""

from __future__ import annotations

from typing import Any

try:
    from tools.chapter_script_codec import AUDIO_MODES
except ModuleNotFoundError:
    from chapter_script_codec import AUDIO_MODES


FIXED_LENGTHS = {
    0x02: 4,
    0x04: 4,
    0x08: 2,
    0x1B: 3,
}


def find_render_text_end(data: bytes, start: int) -> int:
    """Return the NUL terminator used by renderer 0x0806626C.

    Control records 0x01 and 0x02 carry operand bytes which may themselves be
    zero, so a raw ``bytes.find(0)`` would truncate valid records.
    """
    cursor = start
    while cursor < len(data):
        value = data[cursor]
        if value == 0:
            return cursor
        if value == 0x01:
            width = 2
        elif value == 0x02:
            width = 3
        elif value >= 0x80:
            width = 2
        else:
            # 0x03, 0x0A and other single-byte renderer controls/ASCII.
            width = 1
        if cursor + width > len(data):
            raise ValueError(f"truncated render-text token at offset 0x{cursor:X}")
        cursor += width
    raise ValueError(f"unterminated render text beginning at offset 0x{start:X}")


def _address(base_address: int, offset: int) -> str:
    return f"0x{base_address + offset:08X}"


def analyze_observed_script(data: bytes, *, base_address: int) -> list[dict[str, Any]]:
    """Decode exact boundaries for the six-opcode observed dialogue subset."""
    if not isinstance(data, bytes):
        raise TypeError("chapter script must be bytes")
    commands: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(data):
        opcode = data[cursor]
        if opcode == 0x00:
            commands.append({
                "opcode": opcode,
                "name": "end",
                "offset": cursor,
                "address": _address(base_address, cursor),
                "length": 1,
                "raw_hex": "00",
            })
            cursor += 1
            if cursor != len(data):
                raise ValueError(f"bytes remain after end at offset 0x{cursor:X}")
            return commands
        if opcode == 0x01:
            terminator = find_render_text_end(data, cursor + 1)
            length = terminator - cursor + 1
            name = "render_text_record"
        elif opcode in FIXED_LENGTHS:
            length = FIXED_LENGTHS[opcode]
            name = f"opcode_{opcode:02x}"
        else:
            raise ValueError(f"unsupported observed-script opcode 0x{opcode:02X} at 0x{cursor:X}")
        if cursor + length > len(data):
            raise ValueError(f"truncated opcode 0x{opcode:02X} at offset 0x{cursor:X}")
        raw = data[cursor:cursor + length]
        command = {
            "opcode": opcode,
            "name": name,
            "offset": cursor,
            "address": _address(base_address, cursor),
            "length": length,
            "raw_hex": raw.hex(),
            "operand_hex": raw[1:].hex(),
        }
        if opcode == 0x1B:
            mode_value = raw[2]
            if mode_value not in AUDIO_MODES:
                raise ValueError(
                    f"unsupported audio mode 0x{mode_value:02X} at offset 0x{cursor:X}"
                )
            command.update({
                "name": "audio_cue",
                "cue_id": raw[1],
                "mode": AUDIO_MODES[mode_value],
            })
        elif opcode == 0x08:
            command.update({
                "name": "set_speaker_label",
                "speaker_label_id": raw[1],
            })
        commands.append(command)
        cursor += length
    raise ValueError("observed chapter script has no terminal opcode 0x00")
