#!/usr/bin/env python3
"""Extract the ROM-bound battle presentation selector control graphs."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

BATTLE_COUNT = 47
SELECTOR_TABLE = 0x08060E34
PRESENTATION_TABLE = 0x08060EF0
SELECTOR_TABLE_SHA256 = "d0abb00332b73cd36637dbfcf5a7811622438f9c6382dc8c8ff45b00455d00ae"
PRESENTATION_TABLE_SHA256 = "8d04bc657bb656acb5c6ccd0e9f7a38c9c90acdbe01f1f6b189e4db2fbd7a478"

CONTROLLER_CALLSITE = 0x080736F8
CONTROLLER_CALLSITE_END = 0x080737C8
CONTROLLER_CALLSITE_SHA256 = "cc733f730f1dafe773dfe9713a57e89d8a3accc5187ef6a84e93bfd8afcbdcc8"
SELECTOR_BUILDER = 0x0808A534
SELECTOR_BUILDER_END = 0x0808A588
SELECTOR_BUILDER_SHA256 = "2eebdb3fecb96d74024180c6c3ff764d9ed0af2a25860a985f714cc9da8d57ad"
PRESENTATION_RUNNER = 0x0808A588
PRESENTATION_RUNNER_END = 0x0808A630
PRESENTATION_RUNNER_SHA256 = "316b38ca78b84f67eb88df86531dbdc5e179b031067692acbdcd6372d0d195e0"
INTERPRETER = 0x080977B8
INTERPRETER_END = 0x08097E54
INTERPRETER_SHA256 = "7cf438eff6db6de3cd94e9d60aece0f12ca587ea2d79eaf557e4aa15e9ef4e55"
DISPATCH_TABLE = 0x080977F4
DISPATCH_COUNT = 0x3A
DISPATCH_TABLE_SHA256 = "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"
CONTROL_HANDLERS = 0x08097CF8
CONTROL_HANDLERS_END = 0x08097E0E
CONTROL_HANDLERS_SHA256 = "77f152a06a19d1086a058f4cfec30c848d993628128cbaeaba075d9e11dfee00"

CONTROL_DISPATCH = {
    0x07: 0x08097D20,
    0x32: 0x08097CF8,
    0x33: 0x08097D2A,
    0x34: 0x08097D4C,
    0x35: 0x08097D86,
    0x36: 0x08097DA6,
    0x37: 0x08097DC4,
    0x38: 0x08097DCE,
    0x39: 0x08097DF6,
}

CONDITIONAL_LAYOUTS = {
    0x34: (8, 4, "conditional_round_and_side"),
    0x35: (9, 5, "conditional_three_operand_compare"),
    0x36: (8, 4, "conditional_two_operand_compare"),
    0x38: (7, 3, "conditional_flag_query"),
    0x39: (6, 2, "conditional_secondary_battle_id"),
}

PAYLOAD_FIXED_LAYOUTS = {
    0x02: (4, "show_portrait"),
    0x03: (2, "hide_portrait"),
    0x04: (4, "update_portrait"),
    0x08: (2, "select_message_speaker"),
    0x0F: (2, "wait_frames"),
    0x11: (2, "set_portrait_focus"),
    0x12: (5, "initialize_portrait_pair"),
    0x17: (4, "animate_portrait"),
}

PAYLOAD_OPCODES = frozenset(
    {0x01, 0x20, *PAYLOAD_FIXED_LAYOUTS}
)

PORTRAIT_HELPERS = {
    "show_portrait": (
        0x080967E8,
        0x080968EC,
        "3a4849197fc7786e7645f6c1a2d1ed0125a2057c7dd7faa375bfc245d0a962df",
        "show portrait helper SHA-256",
    ),
    "hide_portrait": (
        0x08096668,
        0x08096740,
        "23634345bdc0e80f725f9b11dd96c9e546d4df5e4afe923affbe158451143e0b",
        "hide portrait helper SHA-256",
    ),
    "update_portrait": (
        0x08096A04,
        0x08096A34,
        "4cae8974a3dcae837944eee60d09d590658c91f08130aba2e3cb49a1c307d726",
        "update portrait helper SHA-256",
    ),
    "initialize_portrait_pair": (
        0x080968EC,
        0x08096A04,
        "ab4715cd5991475dc4596ba7aa86240e9418abb89eaeb6012be309b9ec7d9f01",
        "initialize portrait pair helper SHA-256",
    ),
    "animate_portrait": (
        0x08096B74,
        0x08096D16,
        "01587c0f3edfc01a912ad68b0da3b85c4ec6b01a30ee508221e478665d8062ec",
        "animate portrait helper SHA-256",
    ),
    "clear_portrait_focus": (
        0x08096D8C,
        0x08096DCA,
        "37e1d70134245831fe254ea5643ee7e1ab7e8fff2a365cf9796429f65ecf9805",
        "clear portrait focus helper SHA-256",
    ),
    "set_portrait_focus": (
        0x08096DD4,
        0x08096E52,
        "a0bad94b78b489589e10075ce24144fff81a5e1d5798a2ee8dd1ccafdf38a9e3",
        "set portrait focus helper SHA-256",
    ),
}

COMPARISON_NAMES = {
    0: "equal",
    1: "not_equal",
    2: "greater",
    3: "greater_or_equal",
    4: "less",
    5: "less_or_equal",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _offset(address: int) -> int:
    return address - ROM_BASE


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


class _ScriptReader:
    def __init__(self, rom: bytes):
        self._rom = rom

    def valid_address(self, address: int) -> bool:
        return ROM_BASE <= address < ROM_BASE + len(self._rom)

    def require_address(self, address: int, label: str) -> None:
        if not self.valid_address(address):
            raise ValueError(f"{label} is outside ROM: {_address(address)}")

    def u8(self, address: int) -> int:
        self.require_address(address, "script byte")
        return self._rom[_offset(address)]

    def u32(self, address: int, label: str = "script pointer") -> int:
        self.require_address(address, label)
        if _offset(address) + 4 > len(self._rom):
            raise ValueError(f"{label} is truncated at {_address(address)}")
        value = struct.unpack_from("<I", self._rom, _offset(address))[0]
        self.require_address(value, label)
        return value

    def bytes(self, address: int, length: int) -> bytes:
        self.require_address(address, "script record")
        end = _offset(address) + length
        if end > len(self._rom):
            raise ValueError(f"script record is truncated at {_address(address)}")
        return self._rom[_offset(address) : end]

    def terminated_bytes(
        self, address: int, label: str
    ) -> tuple[bytes, int]:
        self.require_address(address, label)
        start = _offset(address)
        end = self._rom.find(b"\x00", start)
        if end < 0:
            raise ValueError(
                f"{label} has no terminator at {_address(address)}"
            )
        return self._rom[start:end], ROM_BASE + end + 1


def _parse_payload_command(
    reader: _ScriptReader, address: int
) -> tuple[dict[str, Any], list[int], bool]:
    opcode = reader.u8(address)
    if opcode == 0x00:
        return (
            {
                "address": _address(address),
                "opcode": "0x00",
                "name": "end",
                "length": 1,
                "raw_hex": reader.bytes(address, 1).hex(),
            },
            [],
            True,
        )
    if opcode == 0x01:
        encoded, fallthrough = reader.terminated_bytes(
            address + 1, "opcode 0x01 encoded text"
        )
        length = fallthrough - address
        return (
            {
                "address": _address(address),
                "opcode": "0x01",
                "name": "render_encoded_text",
                "length": length,
                "raw_hex": reader.bytes(address, length).hex(),
                "encoded_text_hex": encoded.hex(),
                "fallthrough": _address(fallthrough),
                "semantics": (
                    "text_boundary_closed_display_glyph_mapping_pending"
                ),
            },
            [fallthrough],
            True,
        )
    if opcode == 0x20:
        encoded, fallthrough = reader.terminated_bytes(
            address + 2, "opcode 0x20 encoded text"
        )
        length = fallthrough - address
        return (
            {
                "address": _address(address),
                "opcode": "0x20",
                "name": "render_parameterized_encoded_text",
                "length": length,
                "raw_hex": reader.bytes(address, length).hex(),
                "parameter": reader.u8(address + 1),
                "encoded_text_hex": encoded.hex(),
                "fallthrough": _address(fallthrough),
                "semantics": (
                    "text_boundary_closed_parameter_meaning_pending"
                ),
            },
            [fallthrough],
            True,
        )
    layout = PAYLOAD_FIXED_LAYOUTS.get(opcode)
    if layout:
        length, name = layout
        raw = reader.bytes(address, length)
        command: dict[str, Any] = {
            "address": _address(address),
            "opcode": f"0x{opcode:02X}",
            "name": name,
            "length": length,
            "raw_hex": raw.hex(),
            "operand_hex": raw[1:].hex(),
            "fallthrough": _address(address + length),
            "semantics": (
                "handler_and_record_boundary_closed_visual_effect_pending"
            ),
        }
        if opcode == 0x08:
            command["speaker"] = raw[1]
            command["semantics"] = (
                "select_message_speaker_and_matching_portrait_focus"
            )
        elif opcode == 0x0F:
            command["frames"] = raw[1]
            command["semantics"] = "handler_waits_exact_frame_count"
        elif opcode in {0x02, 0x04}:
            command.update(
                {
                    "portrait_slot": raw[1],
                    "portrait_id": raw[2],
                    "expression_id": raw[3],
                    "semantics": (
                        "show_portrait_with_entry_transition"
                        if opcode == 0x02
                        else "replace_existing_portrait_resources"
                    ),
                }
            )
        elif opcode == 0x03:
            command.update(
                {
                    "portrait_slot": raw[1],
                    "semantics": (
                        "hide_all_portrait_slots"
                        if raw[1] == 0xFF
                        else "hide_selected_portrait_slot"
                    ),
                }
            )
        elif opcode == 0x11:
            command.update(
                {
                    "portrait_slot": raw[1],
                    "semantics": (
                        "clear_portrait_focus"
                        if raw[1] == 0xFF
                        else "focus_selected_portrait_slot"
                    ),
                }
            )
        elif opcode == 0x12:
            command.update(
                {
                    "left_portrait_id": raw[1],
                    "left_expression_id": raw[2],
                    "right_portrait_id": raw[3],
                    "right_expression_id": raw[4],
                    "semantics": (
                        "initialize_left_and_right_portrait_slots"
                    ),
                }
            )
        elif opcode == 0x17:
            command.update(
                {
                    "portrait_slot": raw[1],
                    "motion_mode": raw[2],
                    "motion_parameter": raw[3],
                    "semantics": (
                        "run_original_portrait_motion_state_machine"
                    ),
                }
            )
        return command, [address + length], True
    return (
        {
            "address": _address(address),
            "opcode": f"0x{opcode:02X}",
            "name": "opaque_presentation_payload",
            "length": None,
            "raw_hex": f"{opcode:02x}",
            "semantics": "not_yet_decoded",
        },
        [],
        False,
    )


def _parse_control_node(
    reader: _ScriptReader, address: int
) -> tuple[dict[str, Any], list[int], bool]:
    opcode = reader.u8(address)
    if opcode == 0x00 or opcode in PAYLOAD_OPCODES:
        return _parse_payload_command(reader, address)
    if opcode == 0x07:
        target = reader.u32(address + 1, "opcode 0x07 branch target")
        return (
            {
                "address": _address(address),
                "opcode": "0x07",
                "name": "goto",
                "length": 5,
                "raw_hex": reader.bytes(address, 5).hex(),
                "branch_target": _address(target),
            },
            [target],
            True,
        )
    if opcode == 0x32:
        cases: list[dict[str, Any]] = []
        cursor = address
        selector = 1
        while reader.u8(cursor) == 0x32:
            target = reader.u32(
                cursor + 1,
                f"opcode 0x32 selector {selector} target",
            )
            cases.append(
                {
                    "selector": selector,
                    "target": _address(target),
                }
            )
            cursor += 5
            selector += 1
        targets = [
            int(case["target"], 16)
            for case in cases
        ]
        targets.append(cursor)
        return (
            {
                "address": _address(address),
                "opcode": "0x32",
                "name": "selector_dispatch",
                "length": cursor - address,
                "raw_hex": reader.bytes(address, cursor - address).hex(),
                "cases": cases,
                "fallthrough": _address(cursor),
            },
            targets,
            True,
        )
    if opcode == 0x33:
        next_address = address + 2
        return (
            {
                "address": _address(address),
                "opcode": "0x33",
                "name": "append_selector",
                "length": 2,
                "raw_hex": reader.bytes(address, 2).hex(),
                "selector": reader.u8(address + 1),
                "fallthrough": _address(next_address),
            },
            [next_address],
            True,
        )
    if opcode in CONDITIONAL_LAYOUTS:
        length, pointer_offset, name = CONDITIONAL_LAYOUTS[opcode]
        target = reader.u32(
            address + pointer_offset,
            f"opcode 0x{opcode:02X} branch target",
        )
        fallthrough = address + length
        raw = reader.bytes(address, length)
        node = {
            "address": _address(address),
            "opcode": f"0x{opcode:02X}",
            "name": name,
            "length": length,
            "raw_hex": raw.hex(),
            "operand_hex": raw[1:pointer_offset].hex(),
            "branch_target": _address(target),
            "fallthrough": _address(fallthrough),
            "semantics": "control_flow_closed_business_meaning_unresolved",
        }
        if opcode == 0x34:
            comparison = raw[1]
            if comparison not in COMPARISON_NAMES:
                raise ValueError(
                    "opcode 0x34 has invalid comparison "
                    f"{comparison} at {_address(address)}"
                )
            node.update(
                {
                    "comparison_id": comparison,
                    "comparison": COMPARISON_NAMES[comparison],
                    "round_value": raw[2],
                    "side": raw[3],
                    "semantics": (
                        "branch_when_side_matches_and_round_comparison_is_true"
                    ),
                }
            )
        elif opcode == 0x35:
            node.update(
                {
                    "expected": raw[1],
                    "relationship_mode": raw[2],
                    "first_character_id": raw[3],
                    "second_character_id": raw[4],
                    "semantics": (
                        "branch_when_unit_relationship_result_matches_expected"
                    ),
                }
            )
        elif opcode == 0x36:
            node.update(
                {
                    "expected": raw[1],
                    "side": raw[2],
                    "character_id": raw[3],
                    "semantics": (
                        "branch_when_unit_query_result_matches_expected"
                    ),
                }
            )
        elif opcode == 0x38:
            node.update(
                {
                    "query_mode": raw[1],
                    "flag": raw[2],
                    "semantics": (
                        "branch_when_script_flag_query_is_true"
                    ),
                }
            )
        elif opcode == 0x39:
            node.update(
                {
                    "battle_state": raw[1],
                    "semantics": "branch_when_battle_state_matches",
                }
            )
        return node, [target, fallthrough], True
    if opcode == 0x37:
        next_address = address + 3
        raw = reader.bytes(address, 3)
        return (
            {
                "address": _address(address),
                "opcode": "0x37",
                "name": "set_script_flag",
                "length": 3,
                "raw_hex": raw.hex(),
                "operand_hex": raw[1:].hex(),
                "fallthrough": _address(next_address),
                "value": raw[1],
                "flag": raw[2],
                "semantics": "set_script_flag",
            },
            [next_address],
            True,
        )
    return (
        {
            "address": _address(address),
            "opcode": f"0x{opcode:02X}",
            "name": "opaque_presentation_payload",
            "length": None,
            "raw_hex": f"{opcode:02x}",
            "semantics": "not_yet_decoded",
        },
        [],
        False,
    )


def _build_control_graph(
    reader: _ScriptReader, root: int
) -> dict[str, Any]:
    reader.require_address(root, "selector root")
    pending = [root]
    nodes: dict[int, dict[str, Any]] = {}
    complete = True
    opaque_opcodes: set[int] = set()
    while pending:
        address = pending.pop()
        if address in nodes:
            continue
        node, edges, node_complete = _parse_control_node(reader, address)
        nodes[address] = node
        if not node_complete:
            complete = False
            opaque_opcodes.add(reader.u8(address))
        for edge in edges:
            reader.require_address(edge, "control-flow edge")
            if edge not in nodes:
                pending.append(edge)

    ordered_nodes = [
        nodes[address]
        for address in sorted(nodes)
    ]
    opcode_counts = Counter(
        node["opcode"]
        for node in ordered_nodes
    )
    return {
        "complete": complete,
        "nodes": ordered_nodes,
        "opcode_counts": {
            opcode: opcode_counts[opcode]
            for opcode in sorted(opcode_counts)
        },
        "opaque_opcodes": [
            f"0x{opcode:02X}"
            for opcode in sorted(opaque_opcodes)
        ],
    }


def _enumerate_selector_sequences(
    graph: dict[str, Any],
) -> list[list[int]] | None:
    if not graph["complete"]:
        return None
    append_count = graph["opcode_counts"].get("0x33", 0)
    if append_count > 8:
        return None

    nodes = {
        int(node["address"], 16): node
        for node in graph["nodes"]
    }
    root = min(nodes)
    # A root is not guaranteed to be the lowest address when a branch jumps
    # backwards, so callers overwrite this private marker below.
    root = graph["_root"]
    pending: list[tuple[int, tuple[int, ...]]] = [(root, ())]
    seen: set[tuple[int, tuple[int, ...]]] = set()
    completed: set[tuple[int, ...]] = set()
    while pending:
        address, selectors = pending.pop()
        state = (address, selectors)
        if state in seen:
            continue
        seen.add(state)
        if len(seen) > 200_000:
            raise ValueError("selector control graph exceeds state limit")
        node = nodes.get(address)
        if not node:
            raise ValueError(
                f"selector graph is missing node {_address(address)}"
            )
        opcode = int(node["opcode"], 16)
        if opcode == 0x00:
            completed.add(selectors)
            continue
        if opcode == 0x33:
            if len(selectors) == 16:
                raise ValueError("selector builder exceeds the 16-entry ROM limit")
            pending.append(
                (
                    int(node["fallthrough"], 16),
                    selectors + (node["selector"],),
                )
            )
            continue
        if opcode == 0x07:
            pending.append((int(node["branch_target"], 16), selectors))
            continue
        if opcode == 0x32:
            for case in node["cases"]:
                pending.append((int(case["target"], 16), selectors))
            pending.append((int(node["fallthrough"], 16), selectors))
            continue
        if opcode == 0x37:
            pending.append((int(node["fallthrough"], 16), selectors))
            continue
        if opcode in PAYLOAD_OPCODES:
            pending.append((int(node["fallthrough"], 16), selectors))
            continue
        if opcode in CONDITIONAL_LAYOUTS:
            pending.append((int(node["branch_target"], 16), selectors))
            pending.append((int(node["fallthrough"], 16), selectors))
            continue
        raise ValueError(
            f"unsupported complete selector opcode 0x{opcode:02X}"
        )
    if not completed:
        raise ValueError("complete selector graph has no terminal path")
    return [list(sequence) for sequence in sorted(completed)]


def _compare(left: int, comparison: int, right: int) -> bool:
    if comparison == 0:
        return left == right
    if comparison == 1:
        return left != right
    if comparison == 2:
        return left > right
    if comparison == 3:
        return left >= right
    if comparison == 4:
        return left < right
    if comparison == 5:
        return left <= right
    raise ValueError(f"invalid comparison id {comparison}")


def evaluate_round_side_selector_sequence(
    battle: dict[str, Any],
    round_index: int,
    side: int,
) -> list[int]:
    """Execute a selector graph whose only predicate is original opcode 0x34."""
    if battle.get("selector_root") is None:
        return []
    nodes = {
        int(node["address"], 16): node
        for node in battle["selector_nodes"]
    }
    address = int(battle["selector_root"], 16)
    selectors: list[int] = []
    for _ in range(4096):
        node = nodes.get(address)
        if not node:
            raise ValueError(
                f"selector graph is missing node {_address(address)}"
            )
        opcode = int(node["opcode"], 16)
        if opcode == 0x00:
            return selectors
        if opcode == 0x33:
            if len(selectors) == 16:
                raise ValueError("selector builder exceeds the 16-entry ROM limit")
            selectors.append(node["selector"])
            address = int(node["fallthrough"], 16)
            continue
        if opcode == 0x34:
            condition = (
                side == node["side"]
                and _compare(
                    round_index,
                    node["comparison_id"],
                    node["round_value"],
                )
            )
            address = int(
                node[
                    "branch_target"
                    if condition
                    else "fallthrough"
                ],
                16,
            )
            continue
        if opcode == 0x07:
            address = int(node["branch_target"], 16)
            continue
        if opcode in PAYLOAD_OPCODES or opcode == 0x37:
            address = int(node["fallthrough"], 16)
            continue
        raise ValueError(
            "round/side evaluator cannot execute "
            f"opcode 0x{opcode:02X} at {_address(address)}"
        )
    raise ValueError("selector graph exceeds 4096 execution steps")


def _presentation_cases(
    reader: _ScriptReader, root: int
) -> list[dict[str, Any]]:
    reader.require_address(root, "presentation root")
    if reader.u8(root) != 0x32:
        raise ValueError(
            f"presentation root {_address(root)} does not start with opcode 0x32"
        )
    node, _, complete = _parse_control_node(reader, root)
    if not complete or node["opcode"] != "0x32":
        raise ValueError(
            f"presentation root {_address(root)} is not a selector dispatch"
        )
    result: list[dict[str, Any]] = []
    for case in node["cases"]:
        address = int(case["target"], 16)
        commands: list[dict[str, Any]] = []
        complete = False
        for _ in range(4096):
            command, edges, command_complete = (
                _parse_payload_command(reader, address)
            )
            commands.append(command)
            if not command_complete:
                break
            if command["opcode"] == "0x00":
                complete = True
                break
            if len(edges) != 1:
                raise ValueError(
                    "linear presentation payload has invalid edge count "
                    f"at {_address(address)}"
                )
            address = edges[0]
        else:
            raise ValueError(
                "presentation payload exceeds 4096 commands at "
                f"{case['target']}"
            )
        result.append(
            {
                **case,
                "payload_complete": complete,
                "commands": commands,
            }
        )
    return result


def _validate_hash(
    rom: bytes,
    start: int,
    end: int,
    expected: str,
    label: str,
) -> None:
    actual = _sha256(rom[_offset(start) : _offset(end)])
    _expect(actual, expected, label)


def build_battle_presentation_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    _validate_hash(
        rom,
        CONTROLLER_CALLSITE,
        CONTROLLER_CALLSITE_END,
        CONTROLLER_CALLSITE_SHA256,
        "controller callsite SHA-256",
    )
    _validate_hash(
        rom,
        SELECTOR_BUILDER,
        SELECTOR_BUILDER_END,
        SELECTOR_BUILDER_SHA256,
        "selector builder SHA-256",
    )
    _validate_hash(
        rom,
        PRESENTATION_RUNNER,
        PRESENTATION_RUNNER_END,
        PRESENTATION_RUNNER_SHA256,
        "presentation runner SHA-256",
    )
    _validate_hash(
        rom,
        INTERPRETER,
        INTERPRETER_END,
        INTERPRETER_SHA256,
        "interpreter SHA-256",
    )
    _validate_hash(
        rom,
        DISPATCH_TABLE,
        DISPATCH_TABLE + DISPATCH_COUNT * 4,
        DISPATCH_TABLE_SHA256,
        "dispatch table SHA-256",
    )
    _validate_hash(
        rom,
        CONTROL_HANDLERS,
        CONTROL_HANDLERS_END,
        CONTROL_HANDLERS_SHA256,
        "control handlers SHA-256",
    )
    _validate_hash(
        rom,
        SELECTOR_TABLE,
        SELECTOR_TABLE + BATTLE_COUNT * 4,
        SELECTOR_TABLE_SHA256,
        "selector table SHA-256",
    )
    _validate_hash(
        rom,
        PRESENTATION_TABLE,
        PRESENTATION_TABLE + BATTLE_COUNT * 4,
        PRESENTATION_TABLE_SHA256,
        "presentation table SHA-256",
    )
    for start, end, expected, label in PORTRAIT_HELPERS.values():
        _validate_hash(
            rom,
            start,
            end,
            expected,
            label,
        )
    # Keep the whole-ROM binding as the final identity check. Verifying the
    # smaller evidence ranges first makes corruption reports identify the
    # exact routine or table that no longer matches.
    _expect(_sha256(rom), ROM_SHA256, "ROM SHA-256")

    dispatch = struct.unpack_from(
        f"<{DISPATCH_COUNT}I",
        rom,
        _offset(DISPATCH_TABLE),
    )
    for opcode, target in CONTROL_DISPATCH.items():
        _expect(
            dispatch[opcode],
            target,
            f"opcode 0x{opcode:02X} dispatch target",
        )
    for opcode in range(0x24, 0x32):
        _expect(
            dispatch[opcode],
            0x08097E2C,
            f"reserved opcode 0x{opcode:02X} rejection target",
        )

    selector_roots = struct.unpack_from(
        f"<{BATTLE_COUNT}I",
        rom,
        _offset(SELECTOR_TABLE),
    )
    presentation_roots = struct.unpack_from(
        f"<{BATTLE_COUNT}I",
        rom,
        _offset(PRESENTATION_TABLE),
    )
    _expect(selector_roots[0], 0, "selector sentinel")
    _expect(presentation_roots[0], 0, "presentation sentinel")
    reader = _ScriptReader(rom)
    battles: list[dict[str, Any]] = [
        {
            "battle_id": 0,
            "selector_root": None,
            "presentation_root": None,
            "selector_graph_complete": True,
            "selector_opcode_counts": {},
            "selector_opaque_opcodes": [],
            "reachable_selector_sequences": [[]],
            "presentation_cases": [],
        }
    ]
    partial_ids: list[int] = []
    for battle_id in range(1, BATTLE_COUNT):
        selector_root = selector_roots[battle_id]
        presentation_root = presentation_roots[battle_id]
        reader.require_address(
            selector_root,
            f"battle {battle_id} selector root",
        )
        reader.require_address(
            presentation_root,
            f"battle {battle_id} presentation root",
        )
        graph = _build_control_graph(reader, selector_root)
        graph["_root"] = selector_root
        sequences = _enumerate_selector_sequences(graph)
        graph.pop("_root")
        if not graph["complete"]:
            partial_ids.append(battle_id)
        battles.append(
            {
                "battle_id": battle_id,
                "selector_root": _address(selector_root),
                "presentation_root": _address(presentation_root),
                "selector_graph_complete": graph["complete"],
                "selector_opcode_counts": graph["opcode_counts"],
                "selector_opaque_opcodes": graph["opaque_opcodes"],
                "selector_nodes": graph["nodes"],
                "reachable_selector_sequences": sequences,
                "presentation_cases": _presentation_cases(
                    reader, presentation_root
                ),
            }
        )

    complete_count = sum(
        1
        for battle in battles[1:]
        if battle["selector_graph_complete"]
    )
    presentation_cases = [
        case
        for battle in battles[1:]
        for case in battle["presentation_cases"]
    ]
    payload_opcode_counts = Counter(
        command["opcode"]
        for case in presentation_cases
        for command in case["commands"]
    )
    return {
        "schema_version": 1,
        "identity": "battle_presentation_selector_control_graphs",
        "rom_sha256": ROM_SHA256,
        "controller_callsite": _address(CONTROLLER_CALLSITE),
        "selector_builder": _address(SELECTOR_BUILDER),
        "presentation_runner": _address(PRESENTATION_RUNNER),
        "interpreter": _address(INTERPRETER),
        "dispatch_table": _address(DISPATCH_TABLE),
        "selector_table": _address(SELECTOR_TABLE),
        "presentation_table": _address(PRESENTATION_TABLE),
        "battle_count": BATTLE_COUNT,
        "selector_non_null_count": sum(bool(root) for root in selector_roots),
        "presentation_non_null_count": sum(
            bool(root) for root in presentation_roots
        ),
        "control_dispatch": {
            f"0x{opcode:02X}": _address(target)
            for opcode, target in CONTROL_DISPATCH.items()
        },
        "portrait_helpers": {
            name: {
                "start": _address(start),
                "end": _address(end),
                "sha256": expected,
            }
            for name, (start, end, expected, _) in PORTRAIT_HELPERS.items()
        },
        "reserved_rejected_opcodes": [
            f"0x{opcode:02X}"
            for opcode in range(0x24, 0x32)
        ],
        "complete_control_graph_count": complete_count,
        "partial_control_graph_battle_ids": partial_ids,
        "presentation_case_count": len(presentation_cases),
        "complete_presentation_case_count": sum(
            case["payload_complete"]
            for case in presentation_cases
        ),
        "presentation_payload_opcode_counts": {
            opcode: payload_opcode_counts[opcode]
            for opcode in sorted(payload_opcode_counts)
        },
        "battles": battles,
        "boundary": (
            "Selector-builder control flow and record boundaries are complete for "
            "all 46 non-sentinel battles. All 400 presentation case payloads reach "
            "an explicit end through the eleven ROM opcodes observed there. Portrait "
            "slot creation, replacement, hiding, focus, and motion parameters are "
            "bound to their original helper routines. Exact motion-mode appearance, "
            "localized glyph mapping, and controller triggers are not yet declared "
            "playable."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = build_battle_presentation_manifest(args.rom)
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
