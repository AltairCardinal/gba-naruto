#!/usr/bin/env python3
"""Bind base battle resource-command rules to ROM and checkpoint evidence."""

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


ROM_BASE = 0x08000000
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
LEVEL_OFFSET = 0x01
CURRENT_CHAKRA_OFFSET = 0x07
MAX_CHAKRA_OFFSET = 0x08
HAND_SEALS_OFFSET = 0x0A
CURRENT_HP_OFFSET = 0x0C
MAX_HP_OFFSET = 0x0E

STATIC_RANGES = {
    "chakra_initial_preview": (
        0x08073E14,
        0x08073E6C,
        "b1490ea677af7571a4ac2662436f568d0b2fc694447b499b3743a700fdda758a",
    ),
    "chakra_amount_adjustment": (
        0x08073FC8,
        0x08074036,
        "89042d133a9f82534998a8e63d5ae6f1eac4e88ccf51603a4de3cbb2b6c9e49e",
    ),
    "chakra_confirmation_rollback": (
        0x08074074,
        0x080740C0,
        "626fa23193526eb84428a1329b35e7f4683cfe14d283485899cd2185f74705af",
    ),
    "rest_confirmation": (
        0x080740D4,
        0x080740FA,
        "16f5256d1e464777948e27ad18beaa18cfdb63f3e24ae2cd54c4616960b30475",
    ),
    "resource_event_commit_gate": (
        0x0807503C,
        0x0807504E,
        "9854e04ef100fb49a1540da125fc80c2e2fb80a7958fbbfd5edc3d59df6fa3a4",
    ),
}

CHECKPOINTS = {
    "battle_13_entry": (
        "scenario-47-battle-13-entry.ss9",
        "af1c2f79643bbe45bf4f179ea36e4b951bdaa4de70d54aa754c11085c30f8e03",
    ),
    "battle_15_entry": (
        "scenario-50-battle-15-entry.ss9",
        "9e74b086029b0873dfae1c6237e1ebf5fbccc4a01b493cdff35981b0bb6c2cc8",
    ),
    "battle_15_rest_before": (
        "scenario-50-battle-15-round8-objective28-frontblock.ss9",
        "ef761db1ff4ba3d985150d9ec7d1e75d49e35717d3fe76acaf995ea1673922b8",
    ),
}

TRANSACTION_BINDINGS_SHA256 = (
    "6e6bdde545219997980eb6fe0a6ed798813457f8efa50cabe8bf15aafc77c1a5"
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_file(path: Path, expected_sha256: str) -> None:
    actual = _sha256_bytes(path.read_bytes())
    if actual != expected_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected_sha256}, got {actual}"
        )


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _validated_transaction_bindings(
    payload: bytes,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    actual_sha256 = _sha256_bytes(payload)
    if actual_sha256 != TRANSACTION_BINDINGS_SHA256:
        raise ValueError(
            "transaction bindings SHA-256 mismatch: expected "
            f"{TRANSACTION_BINDINGS_SHA256}, got {actual_sha256}"
        )
    bindings = json.loads(payload.decode("utf-8"))
    _expect(bindings.get("schema_version"), 1, "transaction bindings schema")
    _expect(
        bindings.get("identity"),
        "battle_resource_transaction_boundaries",
        "transaction bindings identity",
    )
    _expect(bindings.get("rom"), "rom/base.gba", "transaction bindings ROM")
    transitions = bindings.get("transitions")
    if not isinstance(transitions, list):
        raise ValueError("transaction bindings transitions must be a list")
    _expect(bindings.get("transition_count"), len(transitions), "transition count")

    by_id = {
        transition.get("id"): transition
        for transition in transitions
        if isinstance(transition, dict)
    }
    chakra = by_id.get("chakra_exchange")
    rest = by_id.get("rest_heal")
    if not isinstance(chakra, dict) or not isinstance(rest, dict):
        raise ValueError("required resource transitions are missing")

    expected_chakra = {
        "kind": "chakra_exchange",
        "before_controller_state": "0x3000",
        "after_controller_state": "0x3210",
        "unit_slot": 1,
        "character_id": 1,
        "current_hp": {"before": 134, "after": 119},
        "current_chakra": {"before": 4, "after": 5},
        "resource_exchange_committed": True,
    }
    expected_rest = {
        "kind": "rest",
        "before_controller_state": "0x3310",
        "after_controller_state": "0x1220",
        "unit_slot": 2,
        "character_id": 2,
        "current_hp": {"before": 24, "after": 41},
        "current_chakra": {"before": 4, "after": 4},
        "action_flags_low": {"before": 0, "after": 32},
        "rest_committed_and_action_completed": True,
    }
    for field, expected in expected_chakra.items():
        _expect(chakra.get(field), expected, f"chakra transition {field}")
    for field, expected in expected_rest.items():
        _expect(rest.get(field), expected, f"rest transition {field}")
    return bindings, chakra, rest


def _read_unit(path: Path, slot: int) -> dict[str, int]:
    state = load_gba_state(path)
    record = state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE,
        UNIT_RECORD_SIZE,
    )
    return {
        "character_id": record[0],
        "level": record[LEVEL_OFFSET],
        "current_chakra": record[CURRENT_CHAKRA_OFFSET],
        "max_chakra": record[MAX_CHAKRA_OFFSET],
        "hand_seals": int.from_bytes(
            record[HAND_SEALS_OFFSET : HAND_SEALS_OFFSET + 2], "little"
        ),
        "current_hp": int.from_bytes(
            record[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"
        ),
        "max_hp": int.from_bytes(
            record[MAX_HP_OFFSET : MAX_HP_OFFSET + 2], "little"
        ),
    }


def build_resource_command_rule_manifest(
    rom_path: Path | str,
    transaction_bindings_path: Path | str,
    checkpoint_dir: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    bindings_path = Path(transaction_bindings_path)
    checkpoint_dir = Path(checkpoint_dir)
    rom = rom_path.read_bytes()

    static_ranges: dict[str, dict[str, Any]] = {}
    for name, (start, end, expected_sha256) in STATIC_RANGES.items():
        payload = rom[start - ROM_BASE : end - ROM_BASE]
        actual_sha256 = _sha256_bytes(payload)
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"{name} ROM range mismatch: expected {expected_sha256}, "
                f"got {actual_sha256}"
            )
        static_ranges[name] = {
            "start": f"0x{start:08X}",
            "end": f"0x{end:08X}",
            "sha256": actual_sha256,
        }

    paths: dict[str, Path] = {}
    checkpoint_inputs: dict[str, dict[str, str]] = {}
    for name, (filename, expected_sha256) in CHECKPOINTS.items():
        path = checkpoint_dir / filename
        _validate_file(path, expected_sha256)
        paths[name] = path
        checkpoint_inputs[name] = {
            "path": str(path),
            "sha256": expected_sha256,
        }

    bindings_payload = bindings_path.read_bytes()
    _, chakra_binding, rest_binding = _validated_transaction_bindings(
        bindings_payload
    )
    sasuke = _read_unit(paths["battle_13_entry"], 2)
    naruto = _read_unit(paths["battle_15_entry"], 1)
    naruto_before_rest = _read_unit(paths["battle_15_rest_before"], 1)
    if sasuke["character_id"] != 2 or sasuke["level"] != 3:
        raise ValueError("battle 13 Sasuke identity mismatch")
    if naruto["character_id"] != 1 or naruto["level"] != 6:
        raise ValueError("battle 15 Naruto identity mismatch")
    if (
        naruto_before_rest["character_id"] != 1
        or naruto_before_rest["current_hp"] != 17
        or naruto_before_rest["max_hp"] != naruto["max_hp"]
    ):
        raise ValueError("battle 15 pre-rest checkpoint mismatch")

    root = checkpoint_dir.parent.parent
    battle_15_notes = (
        root / "notes" / "scenario-50-battle-15-runtime-20260720.md"
    ).read_text(encoding="utf-8")
    if "Naruto HP\n  `17 -> 47`" not in battle_15_notes:
        raise ValueError("battle 15 rest observation is missing")

    samples = [
        {
            "character_id": 2,
            "level": 3,
            "max_hp": sasuke["max_hp"],
            "hp_before": rest_binding["current_hp"]["before"],
            "hp_after": rest_binding["current_hp"]["after"],
            "expected_restore": sasuke["max_hp"] // 5,
        },
        {
            "character_id": 1,
            "level": 6,
            "max_hp": naruto["max_hp"],
            "hp_before": naruto_before_rest["current_hp"],
            "hp_after": 47,
            "expected_restore": naruto["max_hp"] // 5,
        },
    ]
    for sample in samples:
        if (
            sample["hp_after"] - sample["hp_before"]
            != sample["expected_restore"]
        ):
            raise ValueError(f"rest formula mismatch: {sample}")

    if (
        chakra_binding["current_hp"]["before"]
        - chakra_binding["current_hp"]["after"]
        != naruto["hand_seals"]
        or chakra_binding["current_chakra"]["after"]
        - chakra_binding["current_chakra"]["before"]
        != 1
    ):
        raise ValueError("chakra exchange does not match unit+0x0A cost")

    return {
        "schema_version": 1,
        "identity": "battle_resource_command_rules",
        "rom": str(rom_path),
        "rom_sha256": _sha256_bytes(rom),
        "inputs": {
            "transaction_bindings": {
                "path": str(bindings_path),
                "sha256": _sha256_bytes(bindings_payload),
                "identity": "battle_resource_transaction_boundaries",
            },
            "checkpoints": checkpoint_inputs,
        },
        "static_ranges": static_ranges,
        "chakra_exchange": {
            "cost_field": "unit+0x0A",
            "cost_semantic": "hand_seals",
            "hp_guard": "current_hp > cost",
            "per_point": True,
            "minimum_remaining_hp": 1,
            "current_chakra_cap_field": "unit+0x08",
            "preview_is_rolled_back_before_confirmation": True,
        },
        "rest": {
            "formula": "floor(max_hp / 5)",
            "max_hp_field": "unit+0x0E",
            "commit_behavior": "complete_unit_action",
            "samples": samples,
        },
        "boundary": (
            "The base command formula and transaction boundary are closed for the "
            "sampled unmodified units; passive modifiers, status modifiers, scripted "
            "scenario overrides, and presentation timing remain separate policies."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--transactions", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_resource_command_rule_manifest(
        args.rom,
        args.transactions,
        args.checkpoints,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
