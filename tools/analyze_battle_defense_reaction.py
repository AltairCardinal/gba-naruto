#!/usr/bin/env python3
"""Bind a controlled defense preparation to one-shot reaction consumption."""

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


EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x40000
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
UNIT_SLOT_COUNT = 13
CURRENT_CHAKRA_OFFSET = 0x07
CURRENT_HP_OFFSET = 0x0C
POSITION_X_OFFSET = 0xC4
POSITION_Y_OFFSET = 0xC5
PREPARED_REACTION_CODE_OFFSET = 0xD4
PREPARED_ACTION_ID_OFFSET = 0xD5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(path: Path, expected: str, label: str) -> None:
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {path}")


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _rooted_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return root / path
    try:
        build_index = path.parts.index("build")
    except ValueError as error:
        raise ValueError(f"evidence path is outside build tree: {raw_path}") from error
    return root.joinpath(*path.parts[build_index:])


def _unit(state: Any, slot: int) -> bytes:
    return state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )


def _diff_bytes(before: bytes, after: bytes) -> list[dict[str, int | str]]:
    return [
        {"offset": f"0x{offset:02X}", "before": old, "after": new}
        for offset, (old, new) in enumerate(zip(before, after))
        if old != new
    ]


def _validate_audit(root: Path, rom_sha256: str, row: dict[str, Any]) -> None:
    path = root / row["path"]
    _validate_hash(path, row["sha256"], "audit")
    audit = json.loads(path.read_text(encoding="utf-8"))
    _expect(audit.get("success"), True, f"audit success for {row['id']}")
    _expect(audit.get("status"), "capture-complete", f"audit status for {row['id']}")
    _expect(audit.get("rom_sha256"), rom_sha256, f"audit ROM for {row['id']}")
    _expect(audit.get("staged_rom_sha256"), rom_sha256, f"staged ROM for {row['id']}")
    _expect(audit.get("evidence_mode"), row["mode"], f"audit mode for {row['id']}")
    inputs = audit.get("inputs", [])
    if row["mode"] == "zero-input":
        _expect(inputs, [], f"zero-input audit inputs for {row['id']}")
        _expect(audit.get("zero_input_verified"), True, f"zero-input gate for {row['id']}")
    else:
        _expect(len(inputs), 1, f"single-input count for {row['id']}")
        _expect(inputs[0]["key"], row["key"], f"single-input key for {row['id']}")
    for key, label in (("input_state", "input checkpoint"), ("output_state", "output checkpoint")):
        checkpoint = _rooted_path(root, audit[key])
        _validate_hash(checkpoint, audit[f"{key}_sha256"], label)


def build_defense_reaction_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle defense reaction schema")
    rom_sha256 = _sha256(rom_path)
    _expect(rom_sha256, source["rom_sha256"], "ROM SHA-256")
    for audit in source["audits"]:
        _validate_audit(root, rom_sha256, audit)

    actor_slot = source["actor_slot"]
    actor_address = UNIT_POOL_BASE + actor_slot * UNIT_RECORD_SIZE
    patch = source["controlled_patch"]
    source_path = root / patch["source"]
    patched_path = root / patch["patched"]
    _validate_hash(source_path, patch["source_sha256"], "checkpoint")
    _validate_hash(patched_path, patch["patched_sha256"], "checkpoint")
    source_state = load_gba_state(source_path)
    patched_state = load_gba_state(patched_path)
    ewram_diffs = [
        EWRAM_BASE + offset
        for offset, (old, new) in enumerate(
            zip(
                source_state.read_memory(EWRAM_BASE, EWRAM_SIZE),
                patched_state.read_memory(EWRAM_BASE, EWRAM_SIZE),
            )
        )
        if old != new
    ]
    expected_writes = [int(row["address"], 0) for row in patch["writes"]]
    _expect(ewram_diffs, expected_writes, "controlled patch addresses")
    controlled_unit_diffs = _diff_bytes(
        _unit(source_state, actor_slot), _unit(patched_state, actor_slot)
    )
    expected_unit_diffs = [
        {
            "offset": f"0x{int(row['address'], 0) - actor_address:02X}",
            "before": row["before"],
            "after": row["after"],
        }
        for row in patch["writes"]
    ]
    _expect(controlled_unit_diffs, expected_unit_diffs, "controlled unit patch")

    state_paths: list[Path] = []
    bindings: list[dict[str, Any]] = []
    states = []
    for row in source["states"]:
        path = root / row["checkpoint"]
        _validate_hash(path, row["sha256"], "checkpoint")
        binding = analyze_checkpoint(rom_path, states_path, path)
        _expect(
            binding["controller_state_hex"],
            row["expected_controller_state"],
            f"controller state for {row['id']}",
        )
        state_paths.append(path)
        bindings.append(binding)
        states.append(load_gba_state(path))

    actor_records = [_unit(state, actor_slot) for state in states]
    _expect(
        [record[0] for record in actor_records],
        [source["actor_character_id"]] * len(actor_records),
        "actor identity sequence",
    )
    controller_sequence = [binding["controller_state_hex"] for binding in bindings]
    actor_current_chakra = [record[CURRENT_CHAKRA_OFFSET] for record in actor_records]
    actor_current_hp = [
        int.from_bytes(record[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little")
        for record in actor_records
    ]
    actor_position = [
        [record[POSITION_X_OFFSET], record[POSITION_Y_OFFSET]]
        for record in actor_records
    ]
    prepared_reaction_code = [
        record[PREPARED_REACTION_CODE_OFFSET] for record in actor_records
    ]
    prepared_action_id = [
        record[PREPARED_ACTION_ID_OFFSET] for record in actor_records
    ]

    preview_from = source["preview_from"]
    preview_from_path = root / preview_from["checkpoint"]
    _validate_hash(preview_from_path, preview_from["sha256"], "checkpoint")
    preview_pool = load_gba_state(preview_from_path).read_memory(
        UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
    )
    confirmed_pool = states[0].read_memory(
        UNIT_POOL_BASE, UNIT_RECORD_SIZE * UNIT_SLOT_COUNT
    )
    preview_has_no_domain_write = preview_pool == confirmed_pool

    commit_is_atomic = (
        actor_current_chakra[:2] == [5, 3]
        and prepared_reaction_code[:2] == [0, 0x10]
        and prepared_action_id[:2] == [0, 15]
    )
    reaction_is_consumed_once = (
        prepared_reaction_code == [0, 0x10, 0, 0]
        and prepared_action_id == [0, 15, 15, 15]
    )
    _expect(preview_has_no_domain_write, True, "preview domain immutability")
    _expect(commit_is_atomic, True, "atomic defense commit")
    _expect(reaction_is_consumed_once, True, "one-shot defense reaction")

    consume_binding = bindings[2]
    attacker_unit = consume_binding.get("current_unit")
    if not attacker_unit:
        raise ValueError("reaction-consumption checkpoint has no current attacker")
    attacker = {
        "slot": attacker_unit["slot"],
        "character_id": attacker_unit["character_id"],
        "position": [attacker_unit["position_x"], attacker_unit["position_y"]],
        "controller_state": consume_binding["controller_state_hex"],
    }

    visual = source["reaction_visual"]
    visual_checkpoint = root / visual["checkpoint"]
    visual_screenshot = root / visual["screenshot"]
    _validate_hash(visual_checkpoint, visual["checkpoint_sha256"], "checkpoint")
    _validate_hash(visual_screenshot, visual["screenshot_sha256"], "screenshot")
    visual_binding = analyze_checkpoint(rom_path, states_path, visual_checkpoint)
    _expect(visual_binding["controller_state_hex"], "0x8000", "visual controller")
    visual_actor = _unit(load_gba_state(visual_checkpoint), actor_slot)
    _expect(
        int.from_bytes(visual_actor[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"),
        actor_current_hp[0],
        "visual actor HP",
    )

    return {
        "schema_version": 1,
        "identity": "battle_defense_preparation_and_reaction",
        "method": source["method"],
        "controlled_patch": {
            "source": patch["source"],
            "patched": patch["patched"],
            "action_id": patch["action_id"],
            "unit_diffs": controlled_unit_diffs,
        },
        "states": [str(path.relative_to(root)) for path in state_paths],
        "state_sha256": [row["sha256"] for row in source["states"]],
        "controller_sequence": controller_sequence,
        "actor_slot": actor_slot,
        "actor_character_id": source["actor_character_id"],
        "actor_current_chakra": actor_current_chakra,
        "actor_current_hp": actor_current_hp,
        "actor_position": actor_position,
        "prepared_reaction_code_offset": "0xD4",
        "prepared_reaction_code": prepared_reaction_code,
        "prepared_action_id_offset": "0xD5",
        "prepared_action_id": prepared_action_id,
        "preview_has_no_domain_write": preview_has_no_domain_write,
        "commit_is_atomic": commit_is_atomic,
        "reaction_is_consumed_once": reaction_is_consumed_once,
        "attacker": attacker,
        "reaction_visual": visual["label"],
        "reaction_visual_checkpoint_sha256": visual["checkpoint_sha256"],
        "reaction_visual_screenshot_sha256": visual["screenshot_sha256"],
        "conclusion": (
            "In a hash-bound controlled original-ROM route, Sharingan defense preview "
            "does not mutate the unit pool. Commit atomically spends two chakra and "
            "writes reaction code 0x10 plus action ID 15. An adjacent enemy attack "
            "consumes code 0x10 at shared 0x8000 resolution, shows the Sharingan cut-in, "
            "and leaves Sasuke HP and position unchanged."
        ),
        "boundary": (
            "The controlled patch changes only current chakra and the pre-existing "
            "locked action-15 level. This proves one sampled evasion reaction, not all "
            "defense actions, expiry rules without an attack, counter priority, or "
            "multi-hit consumption semantics."
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
        default=Path("notes/battle-defense-reaction-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-defense-reaction-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_defense_reaction_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
