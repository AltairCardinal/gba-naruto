#!/usr/bin/env python3
"""Strict codec for the code-proven chapter opcode subset.

Only opcodes whose operand length and runtime meaning are closed are accepted.
Unsupported bytes fail explicitly instead of being guessed or copied through.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


OP_END = 0x00
OP_RENDER_TEXT = 0x01
OP_SHOW_PORTRAIT = 0x02
OP_UPDATE_PORTRAIT = 0x04
OP_SET_SPEAKER_LABEL = 0x08
OP_SET_BATTLE = 0x1A
OP_AUDIO_CUE = 0x1B
RESERVED_OPCODES = frozenset(range(0x24, 0x32))
END_SEMANTICS = "end script at depth zero; otherwise return from interpreter subroutine"
AUDIO_MODES = {
    0: "play",
    1: "play_and_wait",
    2: "stop",
}
_AUDIO_MODE_VALUES = {name: value for value, name in AUDIO_MODES.items()}


class ChapterScriptError(ValueError):
    """Base error for an unsafe or malformed chapter script."""


class TruncatedCommandError(ChapterScriptError):
    """A known opcode does not have all of its required operands."""


class ReservedOpcodeError(ChapterScriptError):
    """The interpreter dispatches this opcode to the invalid/reserved path."""


class UnsupportedOpcodeError(ChapterScriptError):
    """The opcode exists, but its semantics are not yet safe to author."""


def _opcode_error(opcode: int, offset: int) -> ChapterScriptError:
    message = f"opcode 0x{opcode:02X} at offset 0x{offset:X}"
    if opcode in RESERVED_OPCODES:
        return ReservedOpcodeError(f"reserved {message}")
    return UnsupportedOpcodeError(f"unsupported/unproved {message}")


def find_render_text_end(data: bytes, start: int) -> int:
    """Return the renderer-visible NUL terminator at a token boundary."""
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
            width = 1
        if cursor + width > len(data):
            raise ChapterScriptError(
                f"truncated render-text token at offset 0x{cursor:X}"
            )
        cursor += width
    raise ChapterScriptError(f"unterminated render text beginning at offset 0x{start:X}")


def decode_script(data: bytes) -> list[dict[str, Any]]:
    """Decode a complete script containing only the code-proven safe subset."""
    if not isinstance(data, bytes):
        raise TypeError("chapter script must be bytes")
    if not data:
        raise ChapterScriptError("chapter script is empty; terminal end is required")

    commands: list[dict[str, Any]] = []
    cursor = 0
    ended = False
    while cursor < len(data):
        if ended:
            raise ChapterScriptError(f"bytes remain after end at offset 0x{cursor:X}")
        opcode = data[cursor]
        if opcode == OP_END:
            commands.append({
                "opcode": opcode,
                "name": "end",
                "offset": cursor,
                "length": 1,
                "call_depth_semantics": END_SEMANTICS,
            })
            cursor += 1
            ended = True
            continue
        if opcode == OP_RENDER_TEXT:
            terminator = find_render_text_end(data, cursor + 1)
            commands.append({
                "opcode": opcode,
                "name": "render_text",
                "offset": cursor,
                "length": terminator - cursor + 1,
                "encoded_text_hex": data[cursor + 1:terminator].hex(),
            })
            cursor = terminator + 1
            continue
        if opcode in (OP_SHOW_PORTRAIT, OP_UPDATE_PORTRAIT):
            name = "show_portrait" if opcode == OP_SHOW_PORTRAIT else "update_portrait"
            if cursor + 4 > len(data):
                raise TruncatedCommandError(
                    f"truncated {name} at offset 0x{cursor:X}: need 4 bytes"
                )
            portrait_slot = data[cursor + 1]
            portrait_id = data[cursor + 2]
            expression_id = data[cursor + 3]
            if portrait_slot > 1:
                raise ChapterScriptError(
                    f"portrait_slot must be in 0..1 at offset 0x{cursor:X}"
                )
            if portrait_id > 62:
                raise ChapterScriptError(
                    f"portrait_id must be in 0..62 at offset 0x{cursor:X}"
                )
            if expression_id > 5:
                raise ChapterScriptError(
                    f"expression_id must be in 0..5 at offset 0x{cursor:X}"
                )
            commands.append({
                "opcode": opcode,
                "name": name,
                "offset": cursor,
                "length": 4,
                "portrait_slot": portrait_slot,
                "portrait_id": portrait_id,
                "expression_id": expression_id,
            })
            cursor += 4
            continue
        if opcode == OP_SET_BATTLE:
            if cursor + 3 > len(data):
                raise TruncatedCommandError(
                    f"truncated set_battle at offset 0x{cursor:X}: need 3 bytes"
                )
            commands.append({
                "opcode": opcode,
                "name": "set_battle",
                "offset": cursor,
                "length": 3,
                "battle_id": data[cursor + 1],
                "mode": data[cursor + 2],
            })
            cursor += 3
            continue
        if opcode == OP_AUDIO_CUE:
            if cursor + 3 > len(data):
                raise TruncatedCommandError(
                    f"truncated audio_cue at offset 0x{cursor:X}: need 3 bytes"
                )
            mode_value = data[cursor + 2]
            if mode_value not in AUDIO_MODES:
                raise ChapterScriptError(
                    f"unsupported audio mode 0x{mode_value:02X} at offset 0x{cursor:X}"
                )
            commands.append({
                "opcode": opcode,
                "name": "audio_cue",
                "offset": cursor,
                "length": 3,
                "cue_id": data[cursor + 1],
                "mode": AUDIO_MODES[mode_value],
            })
            cursor += 3
            continue
        if opcode == OP_SET_SPEAKER_LABEL:
            if cursor + 2 > len(data):
                raise TruncatedCommandError(
                    f"truncated set_speaker_label at offset 0x{cursor:X}: need 2 bytes"
                )
            commands.append({
                "opcode": opcode,
                "name": "set_speaker_label",
                "offset": cursor,
                "length": 2,
                "speaker_label_id": data[cursor + 1],
            })
            cursor += 2
            continue
        raise _opcode_error(opcode, cursor)

    if not ended:
        raise ChapterScriptError("chapter script requires terminal end")
    return commands


def _u8(command: Mapping[str, Any], field: str) -> int:
    value = command.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ChapterScriptError(f"{field} must be an integer in 0..255")
    return value


def _bounded_u8(command: Mapping[str, Any], field: str, maximum: int) -> int:
    value = _u8(command, field)
    if value > maximum:
        raise ChapterScriptError(f"{field} must be in 0..{maximum}")
    return value


def encode_script(commands: Sequence[Mapping[str, Any]]) -> bytes:
    """Encode the safe subset and require exactly one terminal END command."""
    if not isinstance(commands, Sequence) or isinstance(commands, (str, bytes, bytearray)):
        raise TypeError("commands must be a sequence of mappings")
    output = bytearray()
    ended = False
    for index, command in enumerate(commands):
        if not isinstance(command, Mapping):
            raise TypeError(f"command {index} must be a mapping")
        if ended:
            raise ChapterScriptError(f"command remains after end at index {index}")
        name = command.get("name")
        if name == "render_text":
            encoded_text_hex = command.get("encoded_text_hex")
            if not isinstance(encoded_text_hex, str):
                raise ChapterScriptError("encoded_text_hex must be a hexadecimal string")
            try:
                encoded_text = bytes.fromhex(encoded_text_hex)
            except ValueError as exc:
                raise ChapterScriptError("encoded_text_hex must be valid hexadecimal") from exc
            candidate = encoded_text + b"\x00"
            try:
                terminator = find_render_text_end(candidate, 0)
            except ChapterScriptError as exc:
                raise ChapterScriptError(f"invalid encoded_text_hex: {exc}") from exc
            if terminator != len(encoded_text):
                raise ChapterScriptError("encoded_text_hex contains an early text terminator")
            output.extend((OP_RENDER_TEXT,))
            output.extend(candidate)
        elif name in ("show_portrait", "update_portrait"):
            opcode = OP_SHOW_PORTRAIT if name == "show_portrait" else OP_UPDATE_PORTRAIT
            output.extend((
                opcode,
                _bounded_u8(command, "portrait_slot", 1),
                _bounded_u8(command, "portrait_id", 62),
                _bounded_u8(command, "expression_id", 5),
            ))
        elif name == "set_battle":
            output.extend((OP_SET_BATTLE, _u8(command, "battle_id"), _u8(command, "mode")))
        elif name == "audio_cue":
            mode = command.get("mode")
            if mode not in _AUDIO_MODE_VALUES:
                raise ChapterScriptError(f"audio mode must be one of {tuple(_AUDIO_MODE_VALUES)}")
            output.extend((OP_AUDIO_CUE, _u8(command, "cue_id"), _AUDIO_MODE_VALUES[mode]))
        elif name == "set_speaker_label":
            output.extend((OP_SET_SPEAKER_LABEL, _u8(command, "speaker_label_id")))
        elif name == "end":
            output.append(OP_END)
            ended = True
        else:
            raise ChapterScriptError(f"unsupported command name at index {index}: {name!r}")
    if not ended:
        raise ChapterScriptError("chapter script requires terminal end")
    return bytes(output)
