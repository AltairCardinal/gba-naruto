#!/usr/bin/env python3
"""Scan mGBA savestates for natural seeds of delayed battlefield effects."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.inspect_mgba_savestate import load_gba_state


OBJECT_TABLE = 0x02026604
OBJECT_COUNT = 32
OBJECT_STRIDE = 0x10
UNIT_POOL = 0x020240C0
UNIT_COUNT = 13
UNIT_STRIDE = 0x1D4
PERSISTENT_TEMPLATE_POOL = 0x02022E34
PERSISTENT_TEMPLATE_COUNT = 24
PERSISTENT_TEMPLATE_STRIDE = 0xBC
TOOL_COUNT_OFFSET = 0xB0
TOOL_FIRST_ID_OFFSET = 0xB1
TOOL_SLOT_COUNT = 15
PERSISTENT_TOOL_SLOT_COUNT = PERSISTENT_TEMPLATE_STRIDE - TOOL_FIRST_ID_OFFSET
NINJA_TOOL_INVENTORY = 0x02023FD4
NINJA_TOOL_INVENTORY_SIZE = 0x71
NINJA_TOOL_INVENTORY_ID_BIAS = 1
SPECIAL_ENCODED_ACTIONS = set(range(0xC3, 0xC9))
SPECIAL_TOOL_IDS = set(range(67, 73))


def inspect_state(state: Any) -> dict[str, list[dict[str, Any]]]:
    active_objects = []
    type_2_sequence_7_candidates = []
    active_special_objects = []
    for slot in range(1, OBJECT_COUNT):
        raw = state.read_memory(OBJECT_TABLE + slot * OBJECT_STRIDE, OBJECT_STRIDE)
        object_state = raw[0]
        encoded_action = raw[4]
        if object_state:
            aux_pointer = int.from_bytes(raw[0xC:0x10], "little")
            entry = {
                "slot": slot,
                "type": object_state,
                "x": raw[1],
                "y": raw[2],
                "union_u16_4": int.from_bytes(raw[4:6], "little"),
                "union_u16_6": int.from_bytes(raw[6:8], "little"),
                "aux_pointer": f"0x{aux_pointer:08X}" if aux_pointer else None,
                "raw_hex": raw.hex(),
            }
            active_objects.append(entry)
            if object_state == 2 and entry["union_u16_6"] > 0:
                type_2_sequence_7_candidates.append(entry)
        if object_state in (1, 2) and encoded_action in SPECIAL_ENCODED_ACTIONS:
            active_special_objects.append(
                {
                    "slot": slot,
                    "state": object_state,
                    "encoded_action": f"0x{encoded_action:02X}",
                    "remaining_turns": int.from_bytes(raw[6:8], "little"),
                }
            )

    equipped_special_tools = []
    for unit_slot in range(UNIT_COUNT):
        raw = state.read_memory(UNIT_POOL + unit_slot * UNIT_STRIDE, UNIT_STRIDE)
        character_id = raw[0]
        if character_id == 0:
            continue
        equipped_count = min(raw[TOOL_COUNT_OFFSET], TOOL_SLOT_COUNT)
        for tool_slot, tool_id in enumerate(
            raw[TOOL_FIRST_ID_OFFSET : TOOL_FIRST_ID_OFFSET + equipped_count]
        ):
            if tool_id in SPECIAL_TOOL_IDS:
                equipped_special_tools.append(
                    {
                        "unit_slot": unit_slot,
                        "character_id": character_id,
                        "tool_slot": tool_slot,
                        "ninja_tool_id": tool_id,
                    }
                )
    persistent_equipped_special_tools = []
    for template_slot in range(PERSISTENT_TEMPLATE_COUNT):
        raw = state.read_memory(
            PERSISTENT_TEMPLATE_POOL
            + template_slot * PERSISTENT_TEMPLATE_STRIDE,
            PERSISTENT_TEMPLATE_STRIDE,
        )
        character_id = raw[0]
        if character_id == 0:
            continue
        equipped_count = min(raw[TOOL_COUNT_OFFSET], PERSISTENT_TOOL_SLOT_COUNT)
        for tool_slot, tool_id in enumerate(
            raw[TOOL_FIRST_ID_OFFSET : TOOL_FIRST_ID_OFFSET + equipped_count]
        ):
            if tool_id in SPECIAL_TOOL_IDS:
                persistent_equipped_special_tools.append(
                    {
                        "template_slot": template_slot,
                        "character_id": character_id,
                        "tool_slot": tool_slot,
                        "ninja_tool_id": tool_id,
                    }
                )
    inventory = state.read_memory(NINJA_TOOL_INVENTORY, NINJA_TOOL_INVENTORY_SIZE)
    inventory_special_tools = [
        {
            "ninja_tool_id": tool_id,
            "count": inventory[tool_id + NINJA_TOOL_INVENTORY_ID_BIAS],
        }
        for tool_id in sorted(SPECIAL_TOOL_IDS)
        if inventory[tool_id + NINJA_TOOL_INVENTORY_ID_BIAS]
    ]
    return {
        "active_objects": active_objects,
        "type_2_sequence_7_candidates": type_2_sequence_7_candidates,
        "active_special_objects": active_special_objects,
        "equipped_special_tools": equipped_special_tools,
        "persistent_equipped_special_tools": persistent_equipped_special_tools,
        "inventory_special_tools": inventory_special_tools,
    }


def scan_paths(paths: list[Path]) -> dict[str, Any]:
    candidate_set: set[Path] = set()
    errors = []
    for root in paths:
        if not root.exists():
            errors.append({"path": str(root), "error": "input path does not exist"})
            continue
        if root.is_file():
            if root.suffix != ".ss9":
                errors.append({"path": str(root), "error": "input file is not an .ss9 savestate"})
            else:
                candidate_set.add(root.resolve())
            continue
        if not root.is_dir():
            errors.append({"path": str(root), "error": "input path is neither a file nor a directory"})
            continue
        try:
            candidate_set.update(path.resolve() for path in root.rglob("*.ss9"))
        except OSError as error:
            errors.append({"path": str(root), "error": f"cannot enumerate input directory: {error}"})
    candidates = sorted(candidate_set)
    hits = []
    parsed = 0
    for path in candidates:
        try:
            state = load_gba_state(path)
            inspected = inspect_state(state)
        except (OSError, ValueError) as error:
            errors.append({"path": str(path), "error": str(error)})
            continue
        parsed += 1
        if any(inspected.values()):
            hits.append(
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    **inspected,
                }
            )
    return {
        "schema_version": 1,
        "scanned": len(candidates),
        "parsed": parsed,
        "hit_count": len(hits),
        "hits": hits,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = scan_paths(args.paths)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
