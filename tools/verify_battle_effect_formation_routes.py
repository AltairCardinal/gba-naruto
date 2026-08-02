#!/usr/bin/env python3
"""Independently verify the battle-effect formation-route inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


FORMATION_TABLE = 0x5461C4
GROUP_COUNT = 48
GROUP_STRIDE = 0x1AAC
VARIANT_COUNT = 3
VARIANT_STRIDE = 0x08E4
RECORD_HEADER = 4
RECORD_COUNT = 12
RECORD_STRIDE = 0xB8
PRIMARY_ACTION_OFFSET = 0x10
PRIMARY_ACTION_SLOT_COUNT = 15
ACTION_SLOT_STRIDE = 4


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    return (
        FORMATION_TABLE
        + group_id * GROUP_STRIDE
        + variant_id * VARIANT_STRIDE
        + RECORD_HEADER
        + record_id * RECORD_STRIDE
    )


def _compare(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label} mismatch")


def verify_manifest(root: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    root = Path(root)
    manifest_path = Path(manifest_path)
    manifest = _read_json(manifest_path)
    errors: list[str] = []

    rom_path = root / "rom/base.gba"
    positions_path = root / "sequel/content/positions/bank.json"
    identities_path = root / "sequel/content/battle-config/action-identities.json"
    bindings_path = root / "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
    rom = rom_path.read_bytes()
    positions = _read_json(positions_path)
    identities = _read_json(identities_path)
    bindings = _read_json(bindings_path)

    _compare(errors, "schema_version", manifest.get("schema_version"), 1)
    _compare(
        errors,
        "identity",
        manifest.get("identity"),
        "battle_effect_original_formation_action_routes",
    )
    expected_inputs = {
        "rom": "rom/base.gba",
        "rom_sha256": _sha256(rom_path),
        "positions_bank": "sequel/content/positions/bank.json",
        "positions_bank_sha256": _sha256(positions_path),
        "action_identities": "sequel/content/battle-config/action-identities.json",
        "action_identities_sha256": _sha256(identities_path),
        "sequence_bindings": "artifacts/battle-effect-sequence-bindings-v1/manifest.json",
        "sequence_bindings_sha256": _sha256(bindings_path),
    }
    _compare(errors, "inputs", manifest.get("inputs"), expected_inputs)

    bank_by_id = {entry["id"]: entry for entry in positions["entries"]}
    expected_records: dict[str, dict[str, Any]] = {}
    bank_raw_mismatches: list[str] = []
    action_records: dict[int, list[str]] = defaultdict(list)
    action_occurrences: dict[int, int] = defaultdict(int)
    for group_id in range(GROUP_COUNT):
        for variant_id in range(VARIANT_COUNT):
            for record_id in range(RECORD_COUNT):
                record_key = f"g{group_id:02d}_v{variant_id}_r{record_id:02d}"
                offset = _record_offset(group_id, variant_id, record_id)
                raw = rom[offset : offset + RECORD_STRIDE]
                if len(raw) != RECORD_STRIDE:
                    errors.append(f"truncated ROM record {record_key}")
                    continue
                bank_entry = bank_by_id.get(record_key)
                if bank_entry is None or bank_entry.get("raw_hex") != raw.hex():
                    bank_raw_mismatches.append(record_key)
                slot_ids = [
                    raw[PRIMARY_ACTION_OFFSET + slot * ACTION_SLOT_STRIDE]
                    for slot in range(PRIMARY_ACTION_SLOT_COUNT)
                ]
                action_ids = [action_id for action_id in slot_ids if action_id]
                expected_records[record_key] = {
                    "group_id": group_id,
                    "variant_id": variant_id,
                    "record_id": record_id,
                    "rom_offset": f"0x{offset:06X}",
                    "selector": raw[0],
                    "active": any(raw),
                    "primary_action_slot_ids": slot_ids,
                    "primary_action_ids": action_ids,
                }
                for action_id in action_ids:
                    action_occurrences[action_id] += 1
                    if record_key not in action_records[action_id]:
                        action_records[action_id].append(record_key)

    expected_matrix = {
        "table_offset": f"0x{FORMATION_TABLE:06X}",
        "group_count": GROUP_COUNT,
        "variant_count": VARIANT_COUNT,
        "records_per_variant": RECORD_COUNT,
        "record_count": GROUP_COUNT * VARIANT_COUNT * RECORD_COUNT,
        "record_stride": RECORD_STRIDE,
        "primary_action_offset": PRIMARY_ACTION_OFFSET,
        "primary_action_slots_per_record": PRIMARY_ACTION_SLOT_COUNT,
        "primary_action_slot_stride": ACTION_SLOT_STRIDE,
        "bank_raw_mismatches": bank_raw_mismatches,
    }
    _compare(errors, "formation_matrix", manifest.get("formation_matrix"), expected_matrix)
    _compare(errors, "records", manifest.get("records"), expected_records)

    identity_by_id = {entry["action_id"]: entry for entry in identities["entries"]}
    sequence_by_id = {entry["sequence_id"]: entry for entry in bindings["sequences"]}
    expected_actions: dict[str, dict[str, Any]] = {}
    group_actions: dict[int, set[int]] = defaultdict(set)
    for binding in sorted(bindings["active_action_bindings"], key=lambda row: row["action_id"]):
        action_id = binding["action_id"]
        sequence_id = binding["sequence_id"]
        resource_group_ids = sorted(
            set(sequence_by_id[sequence_id]["nonzero_resource_group_ids"])
        )
        for resource_group_id in resource_group_ids:
            group_actions[resource_group_id].add(action_id)
        identity = identity_by_id.get(action_id, {})
        formation_records = action_records.get(action_id, [])
        expected_actions[str(action_id)] = {
            "display_name": identity.get("display_name"),
            "display_name_confidence": identity.get("confidence"),
            "sequence_ids": [sequence_id],
            "resource_group_ids": resource_group_ids,
            "formation_occurrence_count": action_occurrences.get(action_id, 0),
            "formation_record_count": len(formation_records),
            "formation_records": formation_records,
        }
    _compare(errors, "actions", manifest.get("actions"), expected_actions)

    expected_groups: dict[str, dict[str, Any]] = {}
    for resource_group_id in range(1, 19):
        active_action_ids = sorted(group_actions.get(resource_group_id, set()))
        formation_action_ids = [
            action_id for action_id in active_action_ids if action_records.get(action_id)
        ]
        formation_records = sorted(
            {
                record_key
                for action_id in formation_action_ids
                for record_key in action_records[action_id]
            }
        )
        expected_groups[str(resource_group_id)] = {
            "active_action_ids": active_action_ids,
            "formation_action_ids": formation_action_ids,
            "formation_record_count": len(formation_records),
            "formation_records": formation_records,
            "has_original_formation_action_route": bool(formation_records),
        }
    _compare(errors, "groups", manifest.get("groups"), expected_groups)

    expected_scope = {
        "proves": (
            "Which active-action IDs stored in the original 48x3x12 formation matrix "
            "map through the accepted action-to-sequence catalog to effect groups."
        ),
        "does_not_prove": (
            "Story reachability, unlock/menu eligibility, AI selection, hardcoded effect "
            "producers, ninja-tool routes, or runtime execution of any listed action."
        ),
    }
    _compare(errors, "scope", manifest.get("scope"), expected_scope)
    return {
        "verified_record_count": len(expected_records),
        "verified_action_count": len(expected_actions),
        "verified_group_count": len(expected_groups),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = verify_manifest(args.root, args.manifest)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
