#!/usr/bin/env python3
"""Read-only structural analyzer for the opcodes observed in alternate scenario 39.

This module records exact command boundaries and the code-proven semantics while
preserving opaque inline text bytes. Authoring remains more restricted than
analysis until the text encoding/control grammar is closed.
"""

from __future__ import annotations

from typing import Any

try:
    from tools.chapter_script_codec import AUDIO_MODES, find_render_text_end
except ModuleNotFoundError:
    from chapter_script_codec import AUDIO_MODES, find_render_text_end


FIXED_LENGTHS = {
    0x02: 4,
    0x04: 4,
    0x08: 2,
    0x1B: 3,
}


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
            name = "render_text"
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
        if opcode == 0x01:
            command["encoded_text_hex"] = raw[1:-1].hex()
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
        elif opcode in (0x02, 0x04):
            command.update({
                "name": "show_portrait" if opcode == 0x02 else "update_portrait",
                "portrait_slot": raw[1],
                "portrait_id": raw[2],
                "expression_id": raw[3],
            })
        commands.append(command)
        cursor += length
    raise ValueError("observed chapter script has no terminal opcode 0x00")
