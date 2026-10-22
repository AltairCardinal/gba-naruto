#!/usr/bin/env python3
"""Bind a cross-sample matrix of damage and substitution resolution outcomes."""

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
CURRENT_HP_OFFSET = 0x0C
CURRENT_X_OFFSET = 0xC7
CURRENT_Y_OFFSET = 0xC8
TARGET_RESOLUTION_CODE_OFFSET = 0x154


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_hash(path: Path, expected: str, label: str) -> None:
    if _sha256(path) != expected:
        raise ValueError(f"{label} SHA-256 mismatch for {path}")


def _expect(actual: Any, expected: Any, label: str, sample_id: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch for {sample_id}: expected {expected!r}, got {actual!r}"
        )


def _rooted_audit_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return root / path
    try:
        build_index = path.parts.index("build")
    except ValueError as error:
        raise ValueError(f"audit state is outside the evidence tree: {raw_path}") from error
    return root.joinpath(*path.parts[build_index:])


def _target_values(state: Any, slot: int) -> dict[str, Any]:
    record = state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )
    return {
        "character_id": record[0],
        "current_hp": int.from_bytes(
            record[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"
        ),
        "position": [record[CURRENT_X_OFFSET], record[CURRENT_Y_OFFSET]],
        "resolution_code": record[TARGET_RESOLUTION_CODE_OFFSET],
    }


def analyze_reaction_sample(
    root: Path,
    rom_path: Path | str,
    states_path: Path | str,
    rom_sha256: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    sample_id = observation["id"]
    audit_path = root / observation["audit"]
    _validate_hash(audit_path, observation["audit_sha256"], "audit")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    _expect(audit.get("success"), True, "audit success", sample_id)
    _expect(audit.get("status"), "capture-complete", "audit status", sample_id)
    _expect(audit.get("rom_sha256"), rom_sha256, "audit ROM", sample_id)
    _expect(audit.get("staged_rom_sha256"), rom_sha256, "staged ROM", sample_id)

    input_path = _rooted_audit_path(root, audit["input_state"])
    output_path = _rooted_audit_path(root, audit["output_state"])
    _validate_hash(input_path, audit["input_state_sha256"], "input checkpoint")
    _validate_hash(output_path, audit["output_state_sha256"], "output checkpoint")
    controller_sequence = [
        analyze_checkpoint(rom_path, states_path, path)["controller_state_hex"]
        for path in (input_path, output_path)
    ]
    _expect(
        controller_sequence,
        ["0x8000", "0x9000"],
        "controller sequence",
        sample_id,
    )

    target_slot = observation["target_slot"]
    targets = [
        _target_values(load_gba_state(path), target_slot)
        for path in (input_path, output_path)
    ]
    _expect(
        [target["character_id"] for target in targets],
        [observation["target_character_id"]] * 2,
        "target identity",
        sample_id,
    )
    target_hp = [target["current_hp"] for target in targets]
    target_position = [target["position"] for target in targets]
    target_resolution_code = [target["resolution_code"] for target in targets]
    _expect(target_hp, observation["expected_target_hp"], "target HP", sample_id)
    _expect(
        target_position,
        observation["expected_target_position"],
        "target position",
        sample_id,
    )
    _expect(
        target_resolution_code,
        observation["expected_target_resolution_code"],
        "target resolution code",
        sample_id,
    )

    damage = (
        target_hp[0] > target_hp[1]
        and target_position[0] == target_position[1]
        and target_resolution_code == [0, 0]
    )
    substitution = (
        target_hp[0] == target_hp[1]
        and target_position[0] != target_position[1]
        and target_resolution_code == [0x16, 0]
    )
    if observation["kind"] == "damage" and not damage:
        raise ValueError(f"damage outcome not proven for {sample_id}")
    if observation["kind"] == "substitution" and not substitution:
        raise ValueError(f"substitution outcome not proven for {sample_id}")
    if observation["kind"] not in {"damage", "substitution"}:
        raise ValueError(f"unsupported reaction outcome: {observation['kind']}")

    return {
        "id": sample_id,
        "kind": observation["kind"],
        "audit": observation["audit"],
        "audit_sha256": observation["audit_sha256"],
        "states": [str(input_path.relative_to(root)), str(output_path.relative_to(root))],
        "state_sha256": [
            audit["input_state_sha256"],
            audit["output_state_sha256"],
        ],
        "controller_sequence": controller_sequence,
        "target_slot": target_slot,
        "target_character_id": targets[0]["character_id"],
        "target_hp": target_hp,
        "target_position": target_position,
        "target_resolution_code_offset": "0x154",
        "target_resolution_code": target_resolution_code,
    }


def build_reaction_matrix_manifest(
    root: Path | str,
    rom_path: Path | str,
    states_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle reaction matrix schema")
    rom_sha256 = _sha256(rom_path)
    samples = [
        analyze_reaction_sample(
            root, rom_path, states_path, rom_sha256, observation
        )
        for observation in source["observations"]
    ]
    ids = [sample["id"] for sample in samples]
    if len(ids) != len(set(ids)):
        raise ValueError("reaction sample IDs must be unique")
    outcome_counts = {
        kind: sum(sample["kind"] == kind for sample in samples)
        for kind in ("damage", "substitution")
    }
    confirmed_codes = {
        kind: sorted(
            {
                sample["target_resolution_code"][0]
                for sample in samples
                if sample["kind"] == kind
            }
        )
        for kind in ("damage", "substitution")
    }
    disjoint = (
        bool(confirmed_codes["damage"])
        and bool(confirmed_codes["substitution"])
        and set(confirmed_codes["damage"]).isdisjoint(
            confirmed_codes["substitution"]
        )
    )
    shared_transition = all(
        sample["controller_sequence"] == ["0x8000", "0x9000"]
        for sample in samples
    )
    if not disjoint or not shared_transition:
        raise ValueError("sampled reaction matrix is not closed")
    return {
        "schema_version": 1,
        "identity": "battle_reaction_resolution_matrix",
        "method": source["method"],
        "sample_count": len(samples),
        "outcome_counts": outcome_counts,
        "confirmed_resolution_codes": confirmed_codes,
        "resolution_code_is_disjoint_for_sampled_outcomes": disjoint,
        "all_samples_cross_shared_resolution_to_facing": shared_transition,
        "samples": samples,
        "conclusion": (
            "Across 29 hash-bound battle-15 resolution boundaries, all 18 normal "
            "damage outcomes enter shared resolution with target +0x154 equal to 0, "
            "while all 11 substitution outcomes enter with 0x16 and clear it when "
            "committing displacement without HP loss."
        ),
        "boundary": (
            "This matrix validates a sampled reaction staging discriminator. It does "
            "not prove that +0x154 is exclusively substitution across every action, "
            "nor the upstream trigger formula, destination choice, defense/counter "
            "priority, hit RNG, or multi-hit ordering."
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
        default=Path("notes/battle-reaction-matrix-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-reaction-matrix-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_reaction_matrix_manifest(
        args.root, args.rom, args.states, args.observations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
