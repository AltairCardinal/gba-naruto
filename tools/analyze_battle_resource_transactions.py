#!/usr/bin/env python3
"""Bind chakra exchange and rest transactions to original-ROM savestate pairs."""

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
CURRENT_CHAKRA_OFFSET = 0x07
CURRENT_HP_OFFSET = 0x0C
ACTION_FLAGS_LOW_OFFSET = 0xC0
BATTLE_LOCAL_TOOL_SLOT_OFFSET = 0xB1
NINJA_TOOL_INVENTORY_BASE = 0x02023FD4
NINJA_TOOL_INVENTORY_SIZE = 0x71


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(root: Path, relative: str, expected: str, label: str) -> Path:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {relative}")
    return path


def _diff_region(before: bytes, after: bytes, base: int) -> list[dict[str, int | str]]:
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


def _expect(actual: Any, expected: Any, label: str, transition_id: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch for {transition_id}: expected {expected!r}, got {actual!r}"
        )


def analyze_resource_transition(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    root = Path(root)
    transition_id = observation["id"]
    before_path = _validate_hash(
        root, observation["before"], observation["before_sha256"], "checkpoint"
    )
    after_path = _validate_hash(
        root, observation["after"], observation["after_sha256"], "checkpoint"
    )
    _validate_hash(root, observation["audit"], observation["audit_sha256"], "audit")

    before_binding = analyze_checkpoint(rom_path, states_path, before_path)
    after_binding = analyze_checkpoint(rom_path, states_path, after_path)
    before_state_name = before_binding["controller_state_hex"]
    after_state_name = after_binding["controller_state_hex"]
    _expect(
        before_state_name,
        observation["expected_before_state"],
        "before controller state",
        transition_id,
    )
    _expect(
        after_state_name,
        observation["expected_after_state"],
        "after controller state",
        transition_id,
    )

    before = load_gba_state(before_path)
    after = load_gba_state(after_path)
    slot = observation["unit_slot"]
    unit_address = UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE
    unit_before = before.read_memory(unit_address, UNIT_RECORD_SIZE)
    unit_after = after.read_memory(unit_address, UNIT_RECORD_SIZE)
    character_before = unit_before[0]
    character_after = unit_after[0]
    _expect(
        character_before,
        observation["expected_character_id"],
        "before character ID",
        transition_id,
    )
    _expect(
        character_after,
        observation["expected_character_id"],
        "after character ID",
        transition_id,
    )
    hp_before = int.from_bytes(
        unit_before[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"
    )
    hp_after = int.from_bytes(
        unit_after[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"
    )
    chakra_before = unit_before[CURRENT_CHAKRA_OFFSET]
    chakra_after = unit_after[CURRENT_CHAKRA_OFFSET]
    _expect(hp_before, observation["expected_hp_before"], "before HP", transition_id)
    _expect(hp_after, observation["expected_hp_after"], "after HP", transition_id)
    _expect(
        chakra_before,
        observation["expected_chakra_before"],
        "before chakra",
        transition_id,
    )
    _expect(
        chakra_after,
        observation["expected_chakra_after"],
        "after chakra",
        transition_id,
    )
    inventory_before = before.read_memory(
        NINJA_TOOL_INVENTORY_BASE, NINJA_TOOL_INVENTORY_SIZE
    )
    inventory_after = after.read_memory(
        NINJA_TOOL_INVENTORY_BASE, NINJA_TOOL_INVENTORY_SIZE
    )
    inventory_diffs = _diff_region(
        inventory_before, inventory_after, NINJA_TOOL_INVENTORY_BASE
    )
    result: dict[str, Any] = {
        "id": transition_id,
        "kind": observation["kind"],
        "before": observation["before"],
        "before_sha256": observation["before_sha256"],
        "after": observation["after"],
        "after_sha256": observation["after_sha256"],
        "audit": observation["audit"],
        "audit_sha256": observation["audit_sha256"],
        "before_controller_state": before_state_name,
        "after_controller_state": after_state_name,
        "unit_slot": slot,
        "character_id": character_before,
        "current_hp": {"before": hp_before, "after": hp_after},
        "current_chakra": {"before": chakra_before, "after": chakra_after},
        "unit_record_diffs": _diff_region(unit_before, unit_after, unit_address),
        "ninja_tool_inventory_diffs": inventory_diffs,
    }

    if observation["kind"] == "chakra_exchange":
        result["resource_exchange_committed"] = (
            before_state_name == "0x3000"
            and after_state_name == "0x3210"
            and hp_after < hp_before
            and chakra_after > chakra_before
            and not inventory_diffs
        )
        if not result["resource_exchange_committed"]:
            raise ValueError(f"chakra exchange boundary not proven for {transition_id}")
        return result

    if observation["kind"] not in {"rest", "ninja_tool"}:
        raise ValueError(f"unsupported resource transaction kind: {observation['kind']}")
    action_before = unit_before[ACTION_FLAGS_LOW_OFFSET]
    action_after = unit_after[ACTION_FLAGS_LOW_OFFSET]
    _expect(
        action_before,
        observation["expected_action_flags_low_before"],
        "before action flags",
        transition_id,
    )
    _expect(
        action_after,
        observation["expected_action_flags_low_after"],
        "after action flags",
        transition_id,
    )
    result["action_flags_low"] = {"before": action_before, "after": action_after}

    if observation["kind"] == "ninja_tool":
        tool_slot_offset = int(observation["tool_slot_offset"], 16)
        _expect(
            tool_slot_offset,
            BATTLE_LOCAL_TOOL_SLOT_OFFSET,
            "battle-local tool slot offset",
            transition_id,
        )
        tool_before = unit_before[tool_slot_offset]
        tool_after = unit_after[tool_slot_offset]
        _expect(
            tool_before,
            observation["expected_tool_slot_before"],
            "before battle-local tool slot",
            transition_id,
        )
        _expect(
            tool_after,
            observation["expected_tool_slot_after"],
            "after battle-local tool slot",
            transition_id,
        )
        result["battle_local_tool_slot"] = {
            "offset": _hex(tool_slot_offset, 2),
            "address": _hex(unit_address + tool_slot_offset),
            "before": tool_before,
            "after": tool_after,
        }
        result["battle_local_tool_consumed"] = (
            before_state_name == "0x4100"
            and after_state_name == "0x9000"
            and hp_after == hp_before
            and chakra_after == chakra_before
            and tool_before != 0
            and tool_after == 0
            and action_after != action_before
            and not inventory_diffs
        )
        if not result["battle_local_tool_consumed"]:
            raise ValueError(f"ninja-tool consumption boundary not proven for {transition_id}")
        return result

    result["rest_committed_and_action_completed"] = (
        before_state_name == "0x3310"
        and hp_after > hp_before
        and chakra_after == chakra_before
        and action_after != action_before
        and not inventory_diffs
    )
    if not result["rest_committed_and_action_completed"]:
        raise ValueError(f"rest boundary not proven for {transition_id}")
    return result


def build_resource_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle resource transaction schema")
    transitions = [
        analyze_resource_transition(root, rom_path, states_path, observation)
        for observation in source["observations"]
    ]
    return {
        "schema_version": 1,
        "identity": "battle_resource_transaction_boundaries",
        "method": source["method"],
        "rom": str(Path(rom_path)),
        "state_inventory": str(Path(states_path)),
        "transition_count": len(transitions),
        "transitions": transitions,
        "conclusion": (
            "The sampled chakra command exchanges 15 HP for one current-chakra point "
            "at 0x3000 to 0x3210. The sampled rest command restores 17 HP, preserves "
            "chakra and persistent ninja-tool inventory, and marks the unit action "
            "complete. The sampled ninja-tool commit clears the acting unit's first "
            "battle-local equipped-tool slot while preserving HP, chakra, and the "
            "persistent inventory region."
        ),
        "boundary": (
            "The concrete deltas are sample values. They do not establish the general "
            "HP/chakra formula, max-resource clamping, passive modifiers, item costs, "
            "or the meaning and extent of every byte near the equipped-tool slot."
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
        default=Path("notes/battle-resource-transaction-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-resource-transaction-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_resource_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
