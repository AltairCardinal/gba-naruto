#!/usr/bin/env python3
"""Strict codec for the code-proven chapter opcode subset.

Only opcodes whose operand length and runtime meaning are closed are accepted.
Unsupported bytes fail explicitly instead of being guessed or copied through.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


OP_END = 0x00
OP_SET_BATTLE = 0x1A
RESERVED_OPCODES = frozenset(range(0x24, 0x32))
END_SEMANTICS = "end script at depth zero; otherwise return from interpreter subroutine"


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


def decode_script(data: bytes) -> list[dict[str, Any]]:
    """Decode a complete script containing only END and SET_BATTLE."""
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
        raise _opcode_error(opcode, cursor)

    if not ended:
        raise ChapterScriptError("chapter script requires terminal end")
    return commands


def _u8(command: Mapping[str, Any], field: str) -> int:
    value = command.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ChapterScriptError(f"{field} must be an integer in 0..255")
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
        if name == "set_battle":
            output.extend((OP_SET_BATTLE, _u8(command, "battle_id"), _u8(command, "mode")))
        elif name == "end":
            output.append(OP_END)
            ended = True
        else:
            raise ChapterScriptError(f"unsupported command name at index {index}: {name!r}")
    if not ended:
        raise ChapterScriptError("chapter script requires terminal end")
    return bytes(output)
