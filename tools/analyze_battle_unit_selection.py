#!/usr/bin/env python3
"""Bind original-ROM L-button unit cycling to precommit roster selection state."""

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
UNIT_SELECTION_MARKER_OFFSET = 0xC1
BATTLE_CONTROL_BASE = 0x02026804
BATTLE_CONTROL_SIZE = 0x40


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(root: Path, relative: str, expected: str, label: str) -> Path:
    path = root / relative
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {relative}")
    return path


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


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


def _selected_slot(state: Any) -> int:
    selected = []
    for slot in range(UNIT_SLOT_COUNT):
        address = UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE
        record = state.read_memory(address, UNIT_RECORD_SIZE)
        marker = record[UNIT_SELECTION_MARKER_OFFSET]
        if record[0] != 0 and marker == 1:
            selected.append(slot)
    if len(selected) != 1:
        raise ValueError(f"expected exactly one unit selection marker, got {selected}")
    return selected[0]


def _unit_pool_diffs(before: bytes, after: bytes) -> list[dict[str, int | str]]:
    result = []
    for offset, (old, new) in enumerate(zip(before, after)):
        if old == new:
            continue
        slot, unit_offset = divmod(offset, UNIT_RECORD_SIZE)
        record_start = slot * UNIT_RECORD_SIZE
        result.append(
            {
                "slot": slot,
                "character_id": before[record_start],
                "offset": _hex(unit_offset, 2),
                "address": _hex(UNIT_POOL_BASE + offset),
                "before": old,
                "after": new,
            }
        )
    return result


def build_unit_selection_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    content_catalog_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle unit selection schema")

    catalog = json.loads(Path(content_catalog_path).read_text(encoding="utf-8"))
    names = {
        row["unit_id"]: row["display_identity"]["display_name"]
        for row in catalog["units"]
    }
    states: dict[str, dict[str, Any]] = {}
    ordered_states = []
    for observation in source["states"]:
        checkpoint = _validate_hash(
            root, observation["checkpoint"], observation["sha256"], "checkpoint"
        )
        binding = analyze_checkpoint(rom_path, states_path, checkpoint)
        _expect(
            binding["controller_state_hex"],
            observation["expected_controller_state"],
            f"controller state for {observation['id']}",
        )
        state = load_gba_state(checkpoint)
        selected_slot = _selected_slot(state)
        _expect(
            selected_slot,
            observation["expected_selected_slot"],
            f"selected slot for {observation['id']}",
        )
        record = state.read_memory(
            UNIT_POOL_BASE + selected_slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
        )
        character_id = record[0]
        _expect(
            character_id,
            observation["expected_character_id"],
            f"selected character for {observation['id']}",
        )
        row = {
            "id": observation["id"],
            "checkpoint": observation["checkpoint"],
            "checkpoint_sha256": observation["sha256"],
            "binding": binding,
            "state": state,
            "selection": {
                "slot": selected_slot,
                "character_id": character_id,
                "display_name": names[character_id],
            },
            "primary_sequence": observation.get("primary_sequence", True),
        }
        states[observation["id"]] = row
        ordered_states.append(row)

    transitions = []
    for observation in source["transitions"]:
        audit_path = _validate_hash(
            root, observation["audit"], observation["audit_sha256"], "audit"
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        before = states[observation["from_state"]]
        after = states[observation["to_state"]]
        _expect(audit["evidence_mode"], "single-input", "audit evidence mode")
        _expect(len(audit["inputs"]), 1, "audit input count")
        key = audit["inputs"][0]["key"]
        _expect(key, observation["expected_key"], "audit input key")
        _expect(
            audit["input_state_sha256"],
            before["checkpoint_sha256"],
            "audit input checkpoint hash",
        )
        _expect(
            audit["output_state_sha256"],
            after["checkpoint_sha256"],
            "audit output checkpoint hash",
        )
        before_state = before["state"]
        after_state = after["state"]
        before_pool = before_state.read_memory(
            UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
        )
        after_pool = after_state.read_memory(
            UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
        )
        unit_diffs = _unit_pool_diffs(before_pool, after_pool)
        before_control = before_state.read_memory(
            BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE
        )
        after_control = after_state.read_memory(
            BATTLE_CONTROL_BASE, BATTLE_CONTROL_SIZE
        )
        control_diffs = _diff_region(
            before_control, after_control, BATTLE_CONTROL_BASE
        )
        expected_selection_diffs = {
            (before["selection"]["slot"], 1, 0),
            (after["selection"]["slot"], 0, 1),
        }
        actual_selection_diffs = {
            (row["slot"], row["before"], row["after"])
            for row in unit_diffs
            if row["offset"] == _hex(UNIT_SELECTION_MARKER_OFFSET, 2)
        }
        only_marker = (
            len(unit_diffs) == 2
            and actual_selection_diffs == expected_selection_diffs
            and not control_diffs
        )
        if not only_marker:
            raise ValueError(
                f"L selection transition changed unexpected domain state: {observation['id']}"
            )
        transitions.append(
            {
                "id": observation["id"],
                "key": key,
                "audit": observation["audit"],
                "audit_sha256": observation["audit_sha256"],
                "from_selection": before["selection"],
                "to_selection": after["selection"],
                "unit_pool_diffs": unit_diffs,
                "battle_control_diffs": control_diffs,
                "only_selection_marker_changed": only_marker,
            }
        )

    controller_states = {
        row["binding"]["controller_state_hex"] for row in ordered_states
    }
    primary_states = [row for row in ordered_states if row["primary_sequence"]]
    all_current_unit_pointers = [
        row["binding"]["current_unit_pointer"] for row in ordered_states
    ]
    current_unit_pointers = [
        row["binding"]["current_unit_pointer"] for row in primary_states
    ]
    precommit = (
        controller_states == {"0x2000"}
        and all_current_unit_pointers == ["0x00000000"] * len(ordered_states)
        and all(row["only_selection_marker_changed"] for row in transitions)
    )
    if not precommit:
        raise ValueError("unit selection is not proven to remain precommit")
    l_transitions = [row for row in transitions if row["key"] == "L"]
    l_cycle_wraps = (
        len(primary_states) > 1
        and primary_states[0]["selection"] == primary_states[-1]["selection"]
        and len(l_transitions) == len(primary_states) - 1
    )
    if not l_cycle_wraps:
        raise ValueError("sampled L roster sequence does not wrap to its initial unit")
    return {
        "schema_version": 1,
        "identity": "battle_unit_selection_lr_cycle",
        "method": source["method"],
        "controller_state": "0x2000",
        "selection_marker_offset": _hex(UNIT_SELECTION_MARKER_OFFSET, 2),
        "selection_sequence": [row["selection"] for row in primary_states],
        "input_sequence": [row["key"] for row in l_transitions],
        "current_unit_pointers": current_unit_pointers,
        "r_selection_from_initial": states["after_r_sasuke"]["selection"],
        "r_current_unit_pointer": states["after_r_sasuke"]["binding"][
            "current_unit_pointer"
        ],
        "l_cycle_wraps_to_initial": l_cycle_wraps,
        "transitions": transitions,
        "selection_is_precommit": precommit,
        "conclusion": (
            "Four sampled L inputs cycle the visible roster from Naruto to the cat "
            "objective unit, Sakura, Sasuke, and back to Naruto; a sampled R input "
            "from Naruto selects Sasuke. All remain in controller state 0x2000. Only the "
            "per-unit +0xC1 selection marker moves; no acting-unit pointer or "
            "battle-control state is committed."
        ),
        "boundary": (
            "This sample proves L/R direction and one full precommit wraparound order "
            "for one multi-unit scenario. It does not yet prove "
            "eligibility filtering for dead, disabled, summoned, or completed units."
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
        "--content-catalog",
        type=Path,
        default=Path("notes/battle-content-catalog-20260723.json"),
    )
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("notes/battle-unit-selection-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-unit-selection-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_unit_selection_manifest(
        args.root, args.rom, args.states, args.content_catalog, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
