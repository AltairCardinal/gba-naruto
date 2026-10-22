#!/usr/bin/env python3
"""Bind critical and ignore-defense per-hit probability gates to original-ROM evidence."""

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

from tools.inspect_mgba_savestate import load_gba_state
from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
HIT_GENERATOR = 0x08076034
PASSIVE_QUERY = 0x0806DDA4
RNG = 0x0809C110
LEVEL_TABLE_OFFSET = 0x5459C8
LEVEL_RECORD_SIZE = 12
EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x40000
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
ATTACKER_SLOT = 1
TARGET_SLOT = 5
EVENT_BASE = 0x0202681C
HIT_FLAGS_BASE = 0x020269B0


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


def _validate_bl(rom: bytes, address: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(address, _u16(rom, address), _u16(rom, address + 2))
    _expect(actual, target, label)


def _validate_bytes(rom: bytes, start: int, expected_hex: str, label: str) -> None:
    expected = bytes.fromhex(expected_hex)
    actual = rom[_rom_offset(start) : _rom_offset(start) + len(expected)]
    _expect(actual, expected, label)


def _unit(state: Any, slot: int) -> bytes:
    return state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )


def _validate_audit(root: Path, row: dict[str, Any], prefix: str) -> None:
    audit_path = root / row[f"{prefix}_audit"]
    _validate_hash(
        audit_path,
        row[f"{prefix}_audit_sha256"],
        f"{prefix} audit",
    )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    _expect(audit.get("status"), "capture-complete", f"{prefix} audit status")
    _expect(audit.get("success"), True, f"{prefix} audit success")
    _expect(audit.get("pgid_clean"), True, f"{prefix} PGID cleanup")
    residue = audit.get("runtime_residue", {})
    _expect(residue.get("pgid_clean"), True, f"{prefix} residue PGID cleanup")
    _expect(
        residue.get("mgba_listener_clean"),
        True,
        f"{prefix} listener cleanup",
    )


def _level_record(rom: bytes, record_id: int) -> dict[str, int]:
    offset = LEVEL_TABLE_OFFSET + record_id * LEVEL_RECORD_SIZE
    target_type, reserved, base_a, base_b, per_a, per_b = struct.unpack_from(
        "<BBHHHH", rom, offset
    )
    return {
        "target_type": target_type,
        "reserved": reserved,
        "base_a": base_a,
        "base_b": base_b,
        "per_level_a": per_a,
        "per_level_b": per_b,
    }


def _runtime_sample(
    root: Path,
    row: dict[str, Any],
    sample_id: str,
    expected_flags: list[int],
    expected_hp: list[int],
    candidate_index: int,
) -> dict[str, Any]:
    ready_path = root / row["ready_checkpoint"]
    resolved_path = root / row["resolved_checkpoint"]
    _validate_hash(ready_path, row["ready_sha256"], f"{sample_id} ready checkpoint")
    _validate_hash(
        resolved_path,
        row["resolved_sha256"],
        f"{sample_id} resolved checkpoint",
    )
    _validate_audit(root, row, "ready")
    _validate_audit(root, row, "resolved")
    ready = load_gba_state(ready_path)
    resolved = load_gba_state(resolved_path)
    event = ready.read_memory(EVENT_BASE, 0x20)
    _expect(event[0], ATTACKER_SLOT, f"{sample_id} attacker slot")
    _expect(event[1], TARGET_SLOT, f"{sample_id} target slot")
    _expect(event[0x0C], 129, f"{sample_id} action ID")
    _expect(event[0x12], 3, f"{sample_id} hit count")
    candidates = [
        int.from_bytes(event[offset : offset + 2], "little")
        for offset in (0x18, 0x1A, 0x1C, 0x1E)
    ]
    _expect(candidates, [9, 13, 11, 16], f"{sample_id} damage candidates")
    flags = list(ready.read_memory(HIT_FLAGS_BASE, 3))
    _expect(flags, expected_flags, f"{sample_id} hit flags")
    hp = [
        int.from_bytes(_unit(ready, TARGET_SLOT)[0x0C:0x0E], "little"),
        int.from_bytes(_unit(resolved, TARGET_SLOT)[0x0C:0x0E], "little"),
    ]
    _expect(hp, expected_hp, f"{sample_id} target HP")
    damage = hp[0] - hp[1]
    candidate = candidates[candidate_index]
    landed = sum(flag != 0 for flag in flags)
    _expect(damage, landed * candidate, f"{sample_id} candidate damage total")
    return {
        "id": sample_id,
        "hit_flags": flags,
        "target_hp": hp,
        "total_damage": damage,
        "candidate_per_landed_hit": candidate,
    }


def build_hit_modifier_manifest(
    root: Path | str,
    rom_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle hit modifier observation schema")
    _expect(_sha256(rom_path), source["rom_sha256"], "ROM SHA-256")
    rom = rom_path.read_bytes()

    # Every hit first consumes the ordinary hit RNG. Only a landed hit reaches the
    # critical passive query/RNG, followed by the independent ignore-defense query/RNG.
    _validate_bl(rom, 0x08076082, RNG, "base hit RNG")
    _expect(_u16(rom, 0x08076136), 0x210C, "critical passive target type")
    _validate_bl(rom, 0x0807613A, PASSIVE_QUERY, "critical passive query")
    _validate_bytes(
        rom,
        0x08076146,
        "684600880a300004040c642c00d964240748006825f0d9ff64214843c00b844207dd414678185044022106e0",
        "critical chance, RNG, and flag write",
    )
    _validate_bytes(
        rom,
        0x08076178,
        "41467818504401210170",
        "ordinary-hit fallback flag write",
    )
    _expect(_u16(rom, 0x08076188), 0x2119, "ignore-defense passive target type")
    _validate_bl(rom, 0x0807618C, PASSIVE_QUERY, "ignore-defense passive query")
    _validate_bytes(
        rom,
        0x08076198,
        "684604880848006825f0b6ff64214843c00b84420fdd0199681880003818504401780422114305e0",
        "ignore-defense chance, RNG, and flag OR",
    )

    critical_record = _level_record(rom, 9)
    ignore_record = _level_record(rom, 20)
    _expect(
        critical_record,
        {
            "target_type": 12,
            "reserved": 0,
            "base_a": 10,
            "base_b": 0,
            "per_level_a": 5,
            "per_level_b": 0,
        },
        "critical passive progression record",
    )
    _expect(
        ignore_record,
        {
            "target_type": 25,
            "reserved": 0,
            "base_a": 20,
            "base_b": 0,
            "per_level_a": 5,
            "per_level_b": 0,
        },
        "ignore-defense passive progression record",
    )

    source_checkpoint = root / source["source_checkpoint"]
    _validate_hash(source_checkpoint, source["source_sha256"], "source checkpoint")
    source_state = load_gba_state(source_checkpoint)
    source_ewram = source_state.read_memory(EWRAM_BASE, EWRAM_SIZE)
    controlled_patches = []
    controlled_by_id: dict[str, dict[str, Any]] = {}
    for row in source["controlled_samples"]:
        input_path = root / row["input_checkpoint"]
        _validate_hash(input_path, row["input_sha256"], f"{row['id']} input checkpoint")
        input_state = load_gba_state(input_path)
        input_ewram = input_state.read_memory(EWRAM_BASE, EWRAM_SIZE)
        diffs = [
            EWRAM_BASE + index
            for index, (before, after) in enumerate(zip(source_ewram, input_ewram))
            if before != after
        ]
        address = int(row["patch_address"], 16)
        _expect(diffs, [address], f"{row['id']} single-byte controlled patch")
        _expect(source_state.read_memory(address - 1, 1)[0], row["record_id"], f"{row['id']} record ID")
        before = source_state.read_memory(address, 1)[0]
        after = input_state.read_memory(address, 1)[0]
        _expect((before, after), (0xFF, 17), f"{row['id']} passive level patch")
        record = _level_record(rom, row["record_id"])
        _expect(record["target_type"], row["target_type"], f"{row['id']} target type")
        passive_value = record["base_a"] + record["per_level_a"] * (after - 1)
        expected_value = 90 if row["id"] == "critical_100_percent" else 100
        _expect(passive_value, expected_value, f"{row['id']} passive value")
        controlled_patches.append(
            {
                "id": row["id"],
                "address": f"0x{address:08X}",
                "before": before,
                "after": after,
                "record_id": row["record_id"],
            }
        )
        controlled_by_id[row["id"]] = row

    runtime_samples = [
        _runtime_sample(
            root,
            source["baseline"],
            "natural_baseline",
            [0, 1, 1],
            [49, 31],
            0,
        ),
        _runtime_sample(
            root,
            controlled_by_id["critical_100_percent"],
            "critical_100_percent",
            [2, 2, 2],
            [49, 10],
            1,
        ),
        _runtime_sample(
            root,
            controlled_by_id["ignore_defense_100_percent"],
            "ignore_defense_100_percent",
            [5, 5, 5],
            [49, 16],
            2,
        ),
    ]

    return {
        "schema_version": 1,
        "identity": source["identity"],
        "method": source["method"],
        "hit_generator": f"0x{HIT_GENERATOR:08X}",
        "critical": {
            "passive_target_type": "0x0C",
            "chance": "min(100, passive_value + 10)",
            "rng_percent": "(rng_value * 100) >> 15",
            "success_condition": "rng_percent < chance",
            "flag": 2,
        },
        "ignore_defense": {
            "passive_target_type": "0x19",
            "chance": "passive_value",
            "rng_percent": "(rng_value * 100) >> 15",
            "success_condition": "rng_percent < chance",
            "flag_or_mask": 4,
        },
        "rng_order": [
            "base_hit",
            "critical_if_passive_present",
            "ignore_defense_if_passive_present",
        ],
        "controlled_patches": controlled_patches,
        "runtime_samples": runtime_samples,
        "conclusion": (
            "After a successful base hit, passive type 0x0C independently upgrades flag "
            "1 to critical flag 2, then passive type 0x19 independently ORs mask 4. "
            "The controlled 100-percent samples resolve exactly through the critical "
            "defended and normal ignore-defense candidates."
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
        default=Path("notes/battle-hit-modifier-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-hit-modifier-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_hit_modifier_manifest(args.root, args.rom, args.observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
