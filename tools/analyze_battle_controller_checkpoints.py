#!/usr/bin/env python3
"""Bind visible mGBA checkpoints to validated original battle-controller frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.inspect_mgba_savestate import (
    TASK_CONTEXT_BASE,
    TASK_CONTEXT_SIZE,
    load_gba_state,
)
from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
DEFAULT_TASK_SLOT = 2
DEFAULT_STACK_SCAN_SIZE = 0x300
CURRENT_SIDE_ADDRESS = 0x0202680E
CURRENT_UNIT_POINTER_ADDRESS = 0x02026810
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
UNIT_SLOT_COUNT = 13


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_state_inventory(path: Path, rom: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inventory = json.loads(path.read_text(encoding="utf-8"))
    controller_start = int(inventory["controller_entry"], 16)
    controller_end = int(inventory["controller_end"], 16)
    body = rom[controller_start - ROM_BASE : controller_end - ROM_BASE]
    if hashlib.sha256(body).hexdigest() != inventory["controller_sha256"]:
        raise ValueError("ROM controller SHA-256 does not match state inventory")
    states = sorted(inventory["states"], key=lambda item: int(item["entry"], 16))
    return inventory, states


def _state_for_address(
    address: int,
    states: list[dict[str, Any]],
    controller_end: int,
) -> tuple[dict[str, Any], int] | None:
    for index, state in enumerate(states):
        start = int(state["entry"], 16)
        end = (
            int(states[index + 1]["entry"], 16)
            if index + 1 < len(states)
            else controller_end
        )
        if start <= address < end:
            return state, end
    return None


def _validated_stack_returns(
    state: Any,
    rom: bytes,
    stack_pointer: int,
    scan_size: int,
) -> list[dict[str, Any]]:
    raw = state.read_memory(stack_pointer, scan_size)
    frames: list[dict[str, Any]] = []
    for offset in range(0, len(raw) - 3, 4):
        raw_return = struct.unpack_from("<I", raw, offset)[0]
        if raw_return & 1 == 0:
            continue
        resume_pc = raw_return - 1
        callsite = raw_return - 5
        rom_offset = callsite - ROM_BASE
        if rom_offset < 0 or rom_offset + 4 > len(rom):
            continue
        first, second = struct.unpack_from("<HH", rom, rom_offset)
        target = decode_thumb_bl(callsite, first, second)
        if target is None:
            continue
        frames.append(
            {
                "stack_address_value": stack_pointer + offset,
                "stack_address": _hex(stack_pointer + offset),
                "raw_return_word": _hex(raw_return),
                "resume_pc_value": resume_pc,
                "resume_pc": _hex(resume_pc),
                "callsite": _hex(callsite),
                "decoded_target_value": target,
                "decoded_target": _hex(target),
            }
        )
    return frames


def analyze_checkpoint(
    rom_path: Path | str,
    states_path: Path | str,
    checkpoint_path: Path | str,
    *,
    task_slot: int = DEFAULT_TASK_SLOT,
    stack_scan_size: int = DEFAULT_STACK_SCAN_SIZE,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    states_path = Path(states_path)
    checkpoint_path = Path(checkpoint_path)
    if not 1 <= task_slot <= 8:
        raise ValueError("task_slot must be between 1 and 8")
    rom = rom_path.read_bytes()
    inventory, states = _load_state_inventory(states_path, rom)
    controller_start = int(inventory["controller_entry"], 16)
    controller_end = int(inventory["controller_end"], 16)
    gba_state = load_gba_state(checkpoint_path)
    context_address = TASK_CONTEXT_BASE + (task_slot - 1) * TASK_CONTEXT_SIZE
    context = gba_state.read_memory(context_address, TASK_CONTEXT_SIZE)
    stack_pointer = struct.unpack_from("<I", context, 4)[0]
    saved_lr = struct.unpack_from("<I", context, 8)[0]
    resume_pc = saved_lr - 1 if saved_lr & 1 else saved_lr
    maximum_scan = 0x03008000 - stack_pointer
    if maximum_scan <= 0:
        raise ValueError("task stack pointer is outside IWRAM")
    frames = _validated_stack_returns(
        gba_state, rom, stack_pointer, min(stack_scan_size, maximum_scan)
    )
    callers = [frame for frame in frames if frame["decoded_target_value"] == controller_start]
    if not callers:
        raise ValueError("checkpoint has no validated caller of the battle controller")
    controller_caller = callers[0]

    direct = _state_for_address(resume_pc, states, controller_end)
    if direct:
        state_record, interval_end = direct
        controller_frame = {
            "resume_pc": _hex(resume_pc),
            "entry": state_record["entry"],
            "interval_end": _hex(interval_end),
        }
        binding_kind = "direct_controller_resume"
    else:
        ancestors = []
        for frame in frames:
            if frame["stack_address_value"] >= controller_caller["stack_address_value"]:
                continue
            match = _state_for_address(
                frame["resume_pc_value"], states, controller_end
            )
            if match:
                ancestors.append((frame, match))
        if not ancestors:
            raise ValueError("checkpoint has no validated controller ancestor frame")
        frame, (state_record, interval_end) = ancestors[0]
        controller_frame = {
            key: value
            for key, value in frame.items()
            if not key.endswith("_value")
        }
        controller_frame["entry"] = state_record["entry"]
        controller_frame["interval_end"] = _hex(interval_end)
        binding_kind = "validated_controller_ancestor"

    clean_caller = {
        key: value for key, value in controller_caller.items() if not key.endswith("_value")
    }
    current_side = gba_state.read_memory(CURRENT_SIDE_ADDRESS, 1)[0]
    current_unit_pointer = gba_state.read_u32(CURRENT_UNIT_POINTER_ADDRESS)
    current_unit = None
    unit_pool_end = UNIT_POOL_BASE + UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
    if UNIT_POOL_BASE <= current_unit_pointer < unit_pool_end:
        relative = current_unit_pointer - UNIT_POOL_BASE
        if relative % UNIT_RECORD_SIZE != 0:
            raise ValueError("current unit pointer is not aligned to a battle unit slot")
        unit = gba_state.read_memory(current_unit_pointer, UNIT_RECORD_SIZE)
        current_unit = {
            "slot": relative // UNIT_RECORD_SIZE,
            "character_id": unit[0],
            "affiliation": unit[0xCC],
            "action_state": unit[0xCD],
            "position_x": unit[0xC4],
            "position_y": unit[0xC5],
            "action_flags": _hex(struct.unpack_from("<I", unit, 0xC0)[0]),
        }
    return {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "task_slot": task_slot,
        "task_stack_pointer": _hex(stack_pointer),
        "resume_pc": _hex(resume_pc),
        "binding_kind": binding_kind,
        "controller_state": state_record["state"],
        "controller_state_hex": state_record["state_hex"],
        "controller_frame": controller_frame,
        "controller_caller": clean_caller,
        "current_side": current_side,
        "current_unit_pointer": _hex(current_unit_pointer),
        "current_unit": current_unit,
    }


def build_checkpoint_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    observations_path = Path(observations_path)
    source = json.loads(observations_path.read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported checkpoint observation schema")
    results = []
    for observation in source["observations"]:
        checkpoint = root / observation["checkpoint"]
        actual_hash = _sha256(checkpoint)
        if actual_hash != observation["sha256"]:
            raise ValueError(
                f"checkpoint SHA-256 mismatch for {observation['checkpoint']}"
            )
        analysis = analyze_checkpoint(rom_path, states_path, checkpoint)
        expected_state = int(observation["expected_controller_state"], 16)
        if analysis["controller_state"] != expected_state:
            raise ValueError(
                f"controller state mismatch for {observation['checkpoint']}: "
                f"expected {_hex(expected_state, 4)}, got {analysis['controller_state_hex']}"
            )
        optional_expectations = {
            "expected_current_side": analysis["current_side"],
            "expected_current_unit_pointer": analysis["current_unit_pointer"],
        }
        for expectation, actual in optional_expectations.items():
            if expectation in observation and observation[expectation] != actual:
                raise ValueError(
                    f"{expectation} mismatch for {observation['checkpoint']}: "
                    f"expected {observation[expectation]}, got {actual}"
                )
        for suffix, field in (
            ("character_id", "character_id"),
            ("affiliation", "affiliation"),
            ("action_state", "action_state"),
        ):
            expectation = f"expected_current_unit_{suffix}"
            if expectation not in observation:
                continue
            if analysis["current_unit"] is None:
                raise ValueError(
                    f"{expectation} requires a current unit for {observation['checkpoint']}"
                )
            actual = analysis["current_unit"][field]
            if observation[expectation] != actual:
                raise ValueError(
                    f"{expectation} mismatch for {observation['checkpoint']}: "
                    f"expected {observation[expectation]}, got {actual}"
                )
        analysis["checkpoint"] = observation["checkpoint"]
        analysis["visible_phase"] = observation["visible_phase"]
        results.append(analysis)
    return {
        "schema_version": 1,
        "method": source["method"],
        "rom": str(Path(rom_path)),
        "state_inventory": str(Path(states_path)),
        "checkpoint_count": len(results),
        "checkpoints": results,
        "caveat": (
            "A visible phase is bound only to the containing controller state. "
            "Multiple visible subphases may share one controller state and remain "
            "separate nested-controller behavior."
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
        default=Path(
            "notes/battle-controller-checkpoint-observations-20260723.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-controller-checkpoint-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_checkpoint_manifest(
        args.root, args.rom, args.states, args.observations
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
