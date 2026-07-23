#!/usr/bin/env python3
"""Verify cancel/commit boundaries from hash-bound original-ROM savestate pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.analyze_battle_controller_checkpoints import analyze_checkpoint
from tools.inspect_mgba_savestate import load_gba_state


UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
UNIT_SLOT_COUNT = 13
NINJA_TOOL_INVENTORY_BASE = 0x02023FD4
NINJA_TOOL_INVENTORY_SIZE = 0x71
BATTLE_CONTROL_BASE = 0x02026804
BATTLE_CONTROL_SIZE = 0x10
CURRENT_UNIT_POINTER = 0x02026810


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _diff_region(before: bytes, after: bytes, base: int) -> list[dict[str, Any]]:
    if len(before) != len(after):
        raise ValueError("compared memory regions have different sizes")
    return [
        {
            "address": _hex(base + offset),
            "offset": _hex(offset, 2),
            "before": old,
            "after": new,
        }
        for offset, (old, new) in enumerate(zip(before, after))
        if old != new
    ]


def _read_regions(state: Any) -> dict[str, bytes]:
    return {
        "unit_pool": state.read_memory(
            UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
        ),
        "ninja_tool_inventory": state.read_memory(
            NINJA_TOOL_INVENTORY_BASE, NINJA_TOOL_INVENTORY_SIZE
        ),
        "battle_control": state.read_memory(
            BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE
        ),
    }


def _validate_hash(root: Path, relative: str, expected: str) -> Path:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f"checkpoint SHA-256 mismatch for {relative}")
    return path


def analyze_transition(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    root = Path(root)
    before_path = _validate_hash(
        root, observation["before"], observation["before_sha256"]
    )
    after_path = _validate_hash(
        root, observation["after"], observation["after_sha256"]
    )
    before_binding = analyze_checkpoint(rom_path, states_path, before_path)
    after_binding = analyze_checkpoint(rom_path, states_path, after_path)
    before_state = before_binding["controller_state_hex"]
    after_state = after_binding["controller_state_hex"]
    if before_state != observation["expected_before_state"]:
        raise ValueError(
            f"before controller state mismatch for {observation['id']}: "
            f"expected {observation['expected_before_state']}, got {before_state}"
        )
    if after_state != observation["expected_after_state"]:
        raise ValueError(
            f"after controller state mismatch for {observation['id']}: "
            f"expected {observation['expected_after_state']}, got {after_state}"
        )

    before = load_gba_state(before_path)
    after = load_gba_state(after_path)
    before_regions = _read_regions(before)
    after_regions = _read_regions(after)
    unit_pool_diffs = _diff_region(
        before_regions["unit_pool"], after_regions["unit_pool"], UNIT_POOL_BASE
    )
    inventory_diffs = _diff_region(
        before_regions["ninja_tool_inventory"],
        after_regions["ninja_tool_inventory"],
        NINJA_TOOL_INVENTORY_BASE,
    )
    control_diffs = _diff_region(
        before_regions["battle_control"],
        after_regions["battle_control"],
        BATTLE_CONTROL_BASE,
    )
    before_pointer = before.read_u32(CURRENT_UNIT_POINTER)
    after_pointer = after.read_u32(CURRENT_UNIT_POINTER)

    result: dict[str, Any] = {
        "id": observation["id"],
        "kind": observation["kind"],
        "before": observation["before"],
        "before_sha256": observation["before_sha256"],
        "after": observation["after"],
        "after_sha256": observation["after_sha256"],
        "before_controller_state": before_state,
        "after_controller_state": after_state,
        "current_unit_pointer_before": _hex(before_pointer),
        "current_unit_pointer_after": _hex(after_pointer),
        "unit_pool_diffs": unit_pool_diffs,
        "ninja_tool_inventory_diffs": inventory_diffs,
        "battle_control_diffs": control_diffs,
        "domain_state_preserved": not (
            unit_pool_diffs or inventory_diffs or control_diffs
        ),
    }

    if observation["kind"] == "cancel":
        if not result["domain_state_preserved"]:
            raise ValueError(
                f"cancel transition {observation['id']} changed persistent domain state"
            )
        return result
    if observation["kind"] != "commit":
        raise ValueError(f"unsupported transaction kind: {observation['kind']}")
    expected_pointer = int(observation["expected_current_unit_pointer"], 16)
    if before_pointer != expected_pointer or after_pointer != expected_pointer:
        raise ValueError(f"current unit pointer mismatch for {observation['id']}")
    current_before = before.read_memory(expected_pointer, UNIT_RECORD_SIZE)
    current_after = after.read_memory(expected_pointer, UNIT_RECORD_SIZE)
    semantic_diffs: dict[str, dict[str, Any]] = {}
    for semantic, expected in observation["expected_current_unit_diffs"].items():
        offset = int(expected["offset"], 16)
        old = current_before[offset]
        new = current_after[offset]
        if old != expected["before"] or new != expected["after"]:
            raise ValueError(
                f"{semantic} mismatch for {observation['id']}: "
                f"expected {expected['before']}->{expected['after']}, got {old}->{new}"
            )
        semantic_diffs[semantic] = {
            "offset": _hex(offset, 2),
            "before": old,
            "after": new,
        }
    result["current_unit_pointer"] = _hex(expected_pointer)
    result["semantic_current_unit_diffs"] = semantic_diffs
    result["atomic_resource_and_position_commit"] = (
        before_state == "0x8000"
        and after_state == "0x9000"
        and semantic_diffs["current_chakra"]["before"]
        > semantic_diffs["current_chakra"]["after"]
        and any(
            semantic_diffs[key]["before"] != semantic_diffs[key]["after"]
            for key in ("position_x", "position_y")
        )
        and not inventory_diffs
    )
    if not result["atomic_resource_and_position_commit"]:
        raise ValueError(f"commit boundary not proven for {observation['id']}")
    return result


def build_transaction_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle action transaction schema")
    transitions = [
        analyze_transition(root, rom_path, states_path, observation)
        for observation in source["observations"]
    ]
    return {
        "schema_version": 1,
        "identity": "battle_action_cancel_and_commit_boundaries",
        "method": source["method"],
        "rom": str(Path(rom_path)),
        "state_inventory": str(Path(states_path)),
        "transition_count": len(transitions),
        "transitions": transitions,
        "conclusion": (
            "The sampled cancel paths change only nested UI/controller state. "
            "Persistent unit, inventory, and battle-control state remains unchanged. "
            "In the teleport sample, chakra, position, and action flags commit together "
            "only after confirmation while crossing resolution 0x8000 to facing 0x9000."
        ),
        "boundary": (
            "This proves transaction timing for the four bound samples, not every action "
            "type, failure branch, passive, linked action, or ninja-tool consumption rule."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--states",
        type=Path,
        default=Path("notes/battle-controller-states-20260723.json"),
    )
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("notes/battle-action-transaction-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-action-transaction-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_transaction_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
