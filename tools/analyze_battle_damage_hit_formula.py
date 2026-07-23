#!/usr/bin/env python3
"""Bind the original-ROM base damage and per-hit success formulas to runtime data."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.inspect_mgba_savestate import load_gba_state
from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
EVENT_BUILDER = 0x080754A8
HIT_GENERATOR = 0x08076034
RNG = 0x0809C110
SIGNED_DIVIDE = 0x0809C14C
INTEGER_SQRT = 0x0809C0F0
QUEUE_BASE = 0x0202680C
QUEUE_RECORD = QUEUE_BASE + 0x10
RUNTIME_TEMPLATE = QUEUE_BASE + 0x396
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _validate_hash(path: Path, expected: str, label: str) -> None:
    _expect(_sha256(path), expected, f"{label} SHA-256")


def _rom_offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _rom_offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _rom_offset(address))[0]


def _validate_bl(rom: bytes, address: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(address, _u16(rom, address), _u16(rom, address + 2))
    _expect(actual, target, label)


def _validate_bytes(
    rom: bytes, start: int, expected_hex: str, label: str
) -> None:
    expected = bytes.fromhex(expected_hex)
    actual = rom[_rom_offset(start) : _rom_offset(start) + len(expected)]
    _expect(actual, expected, label)


def _unit(state: Any, slot: int) -> bytes:
    return state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )


def _trunc_half(value: int) -> int:
    return -(abs(value) // 2) if value < 0 else value // 2


def _damage_candidates(power: int, attack: int, defense: int) -> list[int]:
    attack_percent = 100
    scaled_attack = attack * attack_percent // 100
    raw_power = power * scaled_attack // 10
    defense_factor = 100 - 5 * math.isqrt(defense)
    critical_raw_power = 150 * raw_power // 100
    return [
        raw_power * defense_factor // 100,
        critical_raw_power * defense_factor // 100,
        raw_power,
        critical_raw_power,
    ]


def _infer_outcome_composition(
    hit_count: int, candidates: list[int], total_damage: int
) -> dict[str, int]:
    labels = [
        "miss",
        "normal_defended",
        "critical_defended",
        "normal_ignore_defense",
        "critical_ignore_defense",
    ]
    values = [0, *candidates]
    matches = [
        outcomes
        for outcomes in itertools.product(range(len(values)), repeat=hit_count)
        if sum(values[index] for index in outcomes) == total_damage
    ]
    if not matches:
        raise ValueError("natural damage has no composition from queued candidates")
    compositions = {
        tuple(sorted(Counter(labels[index] for index in outcomes).items()))
        for outcomes in matches
    }
    if len(compositions) != 1:
        raise ValueError("natural damage does not uniquely identify an outcome composition")
    return dict(next(iter(compositions)))


def build_damage_hit_manifest(
    root: Path | str,
    rom_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle damage/hit observation schema")
    rom_sha256 = _sha256(rom_path)
    _expect(rom_sha256, source["rom_sha256"], "ROM SHA-256")
    rom = rom_path.read_bytes()

    # The event builder points at the unit pool and battle queue, then computes attack
    # power, the square-root defense factor, and four candidate damages.
    _expect(_u32(rom, 0x08075584), UNIT_POOL_BASE, "unit pool literal")
    _expect(_u32(rom, 0x08075590), QUEUE_BASE, "battle queue literal")
    _expect(_u32(rom, 0x080755CC), QUEUE_BASE, "event builder queue literal")
    _expect(_u32(rom, 0x080755D0), 0x396, "runtime template offset")
    for callsite in (0x08075680, 0x08075688, 0x08075698, 0x08075708, 0x08075714, 0x08075720):
        _validate_bl(rom, callsite, SIGNED_DIVIDE, f"signed divide at 0x{callsite:08X}")
    _validate_bl(rom, 0x080756EE, INTEGER_SQRT, "integer square root")
    _validate_bytes(
        rom,
        0x08075746,
        "08990879099a1179401ac10f401840102b7cc018002628740006000e632801d963202874",
        "agility success-rate adjustment",
    )

    # One RNG sample is converted to [0, 99] for each hit and compared strictly
    # against the event success rate.
    _validate_bl(rom, 0x08076082, RNG, "per-hit RNG call")
    _validate_bytes(
        rom,
        0x0807607C,
        "0c7c1048006826f045f864214843c00b844200dc98e0",
        "per-hit base success gate",
    )
    _validate_bytes(
        rom,
        0x08076E2E,
        "1a780321114000291ed00125069504201040002811d1187801384000311c1831091809888846",
        "defended damage candidate selection",
    )
    _validate_bytes(
        rom,
        0x08076E68,
        "01314900301c1830401800888046",
        "ignore-defense damage candidate selection",
    )

    observation = source["natural_sample"]
    preview_path = root / observation["preview_checkpoint"]
    resolved_path = root / observation["resolved_checkpoint"]
    _validate_hash(preview_path, observation["preview_sha256"], "preview checkpoint")
    _validate_hash(resolved_path, observation["resolved_sha256"], "resolved checkpoint")
    preview_state = load_gba_state(preview_path)
    resolved_state = load_gba_state(resolved_path)
    event = preview_state.read_memory(QUEUE_RECORD, 0x20)
    runtime_template = preview_state.read_memory(RUNTIME_TEMPLATE, 0x10)
    attacker_slot = event[0]
    target_slot = event[1]
    _expect(attacker_slot, observation["expected_attacker_slot"], "attacker slot")
    _expect(target_slot, observation["expected_target_slot"], "target slot")
    _expect(event[0x0C], observation["action_id"], "action ID")

    attacker = _unit(preview_state, attacker_slot)
    target = _unit(preview_state, target_slot)
    power = runtime_template[2]
    hit_count = runtime_template[3]
    template_success_rate = runtime_template[4]
    source_attack = attacker[2]
    source_agility = attacker[4]
    target_defense = target[3]
    target_agility = target[4]
    computed_success_rate = min(
        99,
        template_success_rate
        + _trunc_half(source_agility - target_agility),
    )
    candidates = _damage_candidates(power, source_attack, target_defense)
    queued_candidates = [
        int.from_bytes(event[offset : offset + 2], "little")
        for offset in (0x18, 0x1A, 0x1C, 0x1E)
    ]
    _expect(event[0x10], computed_success_rate, "queued success rate")
    _expect(event[0x12], hit_count, "queued hit count")
    _expect(queued_candidates, candidates, "queued damage candidates")

    target_hp = [
        int.from_bytes(target[0x0C:0x0E], "little"),
        int.from_bytes(_unit(resolved_state, target_slot)[0x0C:0x0E], "little"),
    ]
    total_damage = target_hp[0] - target_hp[1]
    inferred = _infer_outcome_composition(hit_count, candidates, total_damage)

    natural_sample = {
        "action_id": observation["action_id"],
        "power": power,
        "hit_count": hit_count,
        "template_success_rate": template_success_rate,
        "source_attack": source_attack,
        "source_agility": source_agility,
        "target_defense": target_defense,
        "target_agility": target_agility,
        "computed_success_rate": computed_success_rate,
        "damage_candidates": candidates,
        "target_hp": target_hp,
        "total_damage": total_damage,
        "uniquely_inferred_outcomes": inferred,
    }
    _expect(
        natural_sample,
        {
            "action_id": 129,
            "power": 6,
            "hit_count": 3,
            "template_success_rate": 90,
            "source_attack": 19,
            "source_agility": 13,
            "target_defense": 14,
            "target_agility": 14,
            "computed_success_rate": 90,
            "damage_candidates": [9, 13, 11, 16],
            "target_hp": [49, 31],
            "total_damage": 18,
            "uniquely_inferred_outcomes": {
                "miss": 1,
                "normal_defended": 2,
            },
        },
        "natural three-hit formula sample",
    )

    return {
        "schema_version": 1,
        "identity": source["identity"],
        "method": source["method"],
        "event_builder": f"0x{EVENT_BUILDER:08X}",
        "hit_generator": f"0x{HIT_GENERATOR:08X}",
        "damage_formula": {
            "scaled_attack": "floor(attack * attack_percent / 100)",
            "raw_power": "floor(power * scaled_attack / 10)",
            "defense_factor": "100 - 5 * isqrt(defense)",
            "critical_raw_power": "floor(150 * raw_power / 100)",
            "candidate_offsets": {
                "normal_defended": "event+0x18",
                "critical_defended": "event+0x1A",
                "normal_ignore_defense": "event+0x1C",
                "critical_ignore_defense": "event+0x1E",
            },
        },
        "base_hit_formula": {
            "success_rate": "min(99, template_rate + trunc((source_agility - target_agility) / 2))",
            "rng_percent": "(rng_value * 100) >> 15",
            "hit_condition": "rng_percent < success_rate",
            "evaluated_per_hit": True,
        },
        "natural_sample": natural_sample,
        "conclusion": (
            "The queued attack stores four integer damage candidates before animation. "
            "The natural three-hit sample queues normal defended damage 9 and resolves "
            "18 total damage, which uniquely requires two normal hits and one miss; the "
            "visible template value 6x3 is not final damage."
        ),
        "boundary": source["boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--observations",
        type=Path,
        default=Path("notes/battle-damage-hit-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-damage-hit-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_damage_hit_manifest(args.root, args.rom, args.observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
