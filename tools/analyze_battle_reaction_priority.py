#!/usr/bin/env python3
"""Bind reaction priority and first-effective-hit replacement to original ROM evidence."""

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
from tools.thumb_branch import decode_thumb_b, decode_thumb_bl


ROM_BASE = 0x08000000
EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x40000
QUEUE_BASE = 0x0202680C
QUEUE_HEADER_SIZE = 0x10
QUEUE_RECORD_SIZE = 0x20
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
CURRENT_HP_OFFSET = 0x0C
EQUIPPED_TOOL_COUNT_OFFSET = 0xB0
EQUIPPED_TOOL_FIRST_ID_OFFSET = 0xB1
PREPARED_REACTION_CODE_OFFSET = 0xD4
PREPARED_ACTION_ID_OFFSET = 0xD5

STATUS_LOOKUP = 0x0806C160
STATUS_REMOVE = 0x0806C1A4
SHARED_RESOLVER = 0x08076A30
REACTION_HELPER = 0x080768D8

BLOCKING_LOOKUPS = [
    (0x08076554, 0x3F),
    (0x08076566, 0x3E),
    (0x08076578, 0x3D),
    (0x0807658A, 0x0F),
    (0x0807659C, 0x11),
    (0x080765AE, 0x15),
]
REACTION_LOOKUPS = [
    (0x080765EC, 0x04),
    (0x080765FE, 0x0A),
    (0x0807669C, 0x09),
    (0x08076734, 0x10),
    (0x08076744, 0x16),
    (0x08076754, 0x19),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _validate_hash(path: Path, expected: str, label: str) -> None:
    _expect(_sha256(path), expected, f"{label} SHA-256")


def _rooted_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return root / path
    try:
        build_index = path.parts.index("build")
    except ValueError as error:
        raise ValueError(f"evidence path is outside build tree: {raw_path}") from error
    return root.joinpath(*path.parts[build_index:])


def _validate_audit(root: Path, rom_sha256: str, row: dict[str, Any]) -> None:
    path = root / row["path"]
    _validate_hash(path, row["sha256"], f"{row['id']} audit")
    audit = json.loads(path.read_text(encoding="utf-8"))
    _expect(audit.get("success"), True, f"{row['id']} audit success")
    _expect(audit.get("status"), "capture-complete", f"{row['id']} audit status")
    _expect(audit.get("rom_sha256"), rom_sha256, f"{row['id']} audit ROM")
    _expect(audit.get("staged_rom_sha256"), rom_sha256, f"{row['id']} staged ROM")
    _expect(audit.get("evidence_mode"), row["mode"], f"{row['id']} evidence mode")
    inputs = audit.get("inputs", [])
    if row["mode"] == "zero-input":
        _expect(inputs, [], f"{row['id']} zero-input list")
        _expect(audit.get("zero_input_verified"), True, f"{row['id']} zero-input gate")
    else:
        _expect(len(inputs), 1, f"{row['id']} input count")
        _expect(inputs[0]["key"], row["key"], f"{row['id']} input key")
    for key in ("input_state", "output_state"):
        checkpoint = _rooted_path(root, audit[key])
        _validate_hash(checkpoint, audit[f"{key}_sha256"], f"{row['id']} {key}")


def _rom_offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _rom_offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _rom_offset(address))[0]


def _validate_bl(rom: bytes, address: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(address, _u16(rom, address), _u16(rom, address + 2))
    _expect(actual, target, label)


def _validate_b(rom: bytes, address: int, target: int, label: str) -> None:
    actual = decode_thumb_b(address, _u16(rom, address))
    _expect(actual, target, label)


def _validate_conditional_b(
    rom: bytes, address: int, target: int, condition: int, label: str
) -> None:
    halfword = _u16(rom, address)
    _expect((halfword >> 8) & 0xF, condition, f"{label} condition")
    _expect(halfword & 0xF000, 0xD000, f"{label} opcode")
    displacement = (halfword & 0xFF) << 1
    if displacement & 0x100:
        displacement -= 0x200
    _expect(address + 4 + displacement, target, label)


def _validate_status_lookup_sequence(
    rom: bytes, rows: list[tuple[int, int]], label: str
) -> list[int]:
    result = []
    for callsite, status_id in rows:
        immediate = _u16(rom, callsite - 2)
        _expect(immediate & 0xFF00, 0x2100, f"{label} MOVS r1 at 0x{callsite - 2:08X}")
        _expect(immediate & 0xFF, status_id, f"{label} status at 0x{callsite:08X}")
        _validate_bl(rom, callsite, STATUS_LOOKUP, f"{label} lookup at 0x{callsite:08X}")
        result.append(status_id)
    return result


def _queue_record(state_path: Path) -> tuple[int, bytes]:
    state = load_gba_state(state_path)
    header = state.read_memory(QUEUE_BASE, QUEUE_HEADER_SIZE)
    count = header[0x0D]
    record = state.read_memory(QUEUE_BASE + QUEUE_HEADER_SIZE, QUEUE_RECORD_SIZE)
    return count, record


def _unit_hp(state_path: Path, slot: int) -> int:
    state = load_gba_state(state_path)
    record = state.read_memory(UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE)
    return int.from_bytes(record[0x0C:0x0E], "little")


def _unit_record(state: Any, slot: int) -> bytes:
    return state.read_memory(
        UNIT_POOL_BASE + slot * UNIT_RECORD_SIZE, UNIT_RECORD_SIZE
    )


def build_reaction_priority_manifest(
    root: Path | str,
    rom_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle reaction priority schema")

    rom_sha256 = _sha256(rom_path)
    _expect(rom_sha256, source["rom_sha256"], "ROM SHA-256")
    rom = rom_path.read_bytes()

    blocking_status_priority = _validate_status_lookup_sequence(
        rom, BLOCKING_LOOKUPS, "blocking status"
    )
    reaction_status_priority = _validate_status_lookup_sequence(
        rom, REACTION_LOOKUPS, "reaction status"
    )

    # The preprocessor gates reaction selection on a non-zero two-bit hit result.
    _expect(
        rom[_rom_offset(0x080765DC) : _rom_offset(0x080765E8)].hex(),
        "017803200840002800d1d7e0",
        "effective-hit gate",
    )
    # Status 0x10 branches to a block that stores current hit index + 1 into event+0x12.
    _validate_conditional_b(
        rom, 0x0807673E, 0x080767D8, 0x1, "status 0x10 dispatch"
    )
    _expect(_u16(rom, 0x080767DC), 0x74B0, "event hit-count truncation store")
    _validate_bl(rom, 0x080767F6, STATUS_REMOVE, "status 0x10 one-shot removal")

    # Jump table entry 1 is the normal damage/effect handler.
    _expect(_u32(rom, 0x08076F40), 0x08076F44, "effect jump-table pointer")
    normal_handler = _u32(rom, 0x08076F44)
    _expect(normal_handler, 0x08077040, "effect subtype 1 handler")
    _validate_bl(rom, 0x08077058, SHARED_RESOLVER, "normal handler resolver call")
    _expect(
        rom[_rom_offset(0x08077062) : _rom_offset(0x0807706A)].hex(),
        "00203481f4807071",
        "reaction metadata clear",
    )

    # Shared resolver dispatches status 0x10 directly to the reaction helper.
    _validate_b(rom, 0x08076A94, 0x08076CA8, "status 0x10 resolver dispatch")
    _validate_bl(rom, 0x08076CB0, REACTION_HELPER, "status 0x10 helper call")

    # Counter-like paths recurse with original target as source and original source as target.
    for callsite, label in (
        (0x08076B3A, "status 0x0A reverse resolver"),
        (0x08076BC6, "status 0x09 reverse resolver"),
        (0x08076C20, "status 0x19 reverse resolver"),
    ):
        _validate_bl(rom, callsite, SHARED_RESOLVER, label)

    runtime = source["runtime_queue"]
    checkpoint = root / runtime["checkpoint"]
    post_checkpoint = root / runtime["post_checkpoint"]
    _expect(_sha256(checkpoint), runtime["sha256"], "queue checkpoint SHA-256")
    _expect(_sha256(post_checkpoint), runtime["post_sha256"], "post checkpoint SHA-256")
    count, record = _queue_record(checkpoint)
    post_count, post_record = _queue_record(post_checkpoint)
    _expect(count, 1, "queue event count")
    _expect(post_count, 1, "post queue event count")
    queue_binding = {
        "attacker_slot": record[0x00],
        "target_slot": record[0x01],
        "action_id": record[0x0C],
        "reaction_action_id": record[0x05],
        "reaction_code": int.from_bytes(record[0x06:0x08], "little"),
        "queued_hit_count": record[0x12],
    }
    _expect(
        queue_binding,
        {
            "attacker_slot": 5,
            "target_slot": 2,
            "action_id": 5,
            "reaction_action_id": 15,
            "reaction_code": 0x10,
            "queued_hit_count": 1,
        },
        "Sharingan runtime queue",
    )
    _expect(post_record[0x05:0x08], b"\x00\x00\x00", "post reaction metadata")

    multihit = source["natural_multihit_baseline"]
    multihit_preview = root / multihit["preview_checkpoint"]
    multihit_resolved = root / multihit["resolved_checkpoint"]
    _expect(
        _sha256(multihit_preview),
        multihit["preview_sha256"],
        "multi-hit preview checkpoint SHA-256",
    )
    _expect(
        _sha256(multihit_resolved),
        multihit["resolved_sha256"],
        "multi-hit resolved checkpoint SHA-256",
    )
    multihit_count, multihit_record = _queue_record(multihit_preview)
    _expect(multihit_count, 1, "multi-hit queue event count")
    target_slot = multihit_record[0x01]
    target_hp = [
        _unit_hp(multihit_preview, target_slot),
        _unit_hp(multihit_resolved, target_slot),
    ]
    natural_multihit_baseline = {
        "action_id": multihit_record[0x0C],
        "attacker_slot": multihit_record[0x00],
        "target_slot": target_slot,
        "queued_hit_count": multihit_record[0x12],
        "target_hp": target_hp,
        "total_damage": target_hp[0] - target_hp[1],
    }
    _expect(
        natural_multihit_baseline,
        {
            "action_id": 129,
            "attacker_slot": 1,
            "target_slot": 5,
            "queued_hit_count": 3,
            "target_hp": [49, 31],
            "total_damage": 18,
        },
        "natural multi-hit baseline",
    )

    counter = source["counter_runtime_sample"]
    for audit in counter["audits"]:
        _validate_audit(root, rom_sha256, audit)

    patch = counter["controlled_patch"]
    patch_source_path = root / patch["source"]
    patch_target_path = root / patch["patched"]
    _validate_hash(patch_source_path, patch["source_sha256"], "counter patch source")
    _validate_hash(patch_target_path, patch["patched_sha256"], "counter patch target")
    patch_source_state = load_gba_state(patch_source_path)
    patch_target_state = load_gba_state(patch_target_path)
    actual_patch_addresses = [
        EWRAM_BASE + offset
        for offset, (before, after) in enumerate(
            zip(
                patch_source_state.read_memory(EWRAM_BASE, EWRAM_SIZE),
                patch_target_state.read_memory(EWRAM_BASE, EWRAM_SIZE),
            )
        )
        if before != after
    ]
    expected_patch_addresses = [int(row["address"], 0) for row in patch["writes"]]
    _expect(actual_patch_addresses, expected_patch_addresses, "counter controlled patch")
    for row in patch["writes"]:
        address = int(row["address"], 0)
        _expect(
            patch_source_state.read_memory(address, 1)[0],
            row["before"],
            f"counter patch source byte at {row['address']}",
        )
        _expect(
            patch_target_state.read_memory(address, 1)[0],
            row["after"],
            f"counter patch target byte at {row['address']}",
        )

    prepared_path = root / counter["prepared_checkpoint"]
    counter_queue_path = root / counter["queue_checkpoint"]
    resolved_path = root / counter["resolved_checkpoint"]
    _validate_hash(prepared_path, counter["prepared_sha256"], "counter prepared checkpoint")
    _validate_hash(counter_queue_path, counter["queue_sha256"], "counter queue checkpoint")
    _validate_hash(resolved_path, counter["resolved_sha256"], "counter resolved checkpoint")
    prepared_state = load_gba_state(prepared_path)
    counter_queue_state = load_gba_state(counter_queue_path)
    resolved_state = load_gba_state(resolved_path)
    prepared_slot = counter["prepared_unit_slot"]
    prepared_character_id = counter["prepared_character_id"]
    tool_id = counter["tool_id"]
    runtime_action_id = counter["runtime_action_id"]
    reaction_code = counter["reaction_code"]
    _expect(runtime_action_id, 0x80 | tool_id, "counter high-bit tool action ID")

    source_unit = _unit_record(patch_source_state, prepared_slot)
    patched_unit = _unit_record(patch_target_state, prepared_slot)
    prepared_unit = _unit_record(prepared_state, prepared_slot)
    queue_unit = _unit_record(counter_queue_state, prepared_slot)
    resolved_unit = _unit_record(resolved_state, prepared_slot)
    _expect(
        [
            source_unit[0],
            patched_unit[0],
            prepared_unit[0],
            queue_unit[0],
            resolved_unit[0],
        ],
        [prepared_character_id] * 5,
        "counter defender identity",
    )
    _expect(
        patched_unit[EQUIPPED_TOOL_COUNT_OFFSET : EQUIPPED_TOOL_FIRST_ID_OFFSET + 1],
        bytes([1, tool_id]),
        "controlled equipped tool",
    )
    _expect(
        prepared_unit[EQUIPPED_TOOL_COUNT_OFFSET : EQUIPPED_TOOL_FIRST_ID_OFFSET + 1],
        b"\x01\x00",
        "consumed equipped tool slot",
    )
    _expect(
        prepared_unit[PREPARED_REACTION_CODE_OFFSET : PREPARED_ACTION_ID_OFFSET + 1],
        bytes([reaction_code, runtime_action_id]),
        "prepared counter metadata",
    )
    _expect(
        queue_unit[PREPARED_REACTION_CODE_OFFSET],
        0,
        "one-shot counter consumption",
    )

    counter_count, counter_record = _queue_record(counter_queue_path)
    resolved_count, resolved_record = _queue_record(resolved_path)
    _expect(counter_count, 1, "counter queue event count")
    _expect(resolved_count, 1, "resolved counter queue event count")
    counter_queue_binding = {
        "attacker_slot": counter_record[0x00],
        "target_slot": counter_record[0x01],
        "incoming_action_id": counter_record[0x0C],
        "reaction_action_id": counter_record[0x05],
        "reaction_code": int.from_bytes(counter_record[0x06:0x08], "little"),
        "queued_hit_count": counter_record[0x12],
    }
    _expect(
        counter_queue_binding,
        {
            "attacker_slot": 5,
            "target_slot": prepared_slot,
            "incoming_action_id": 5,
            "reaction_action_id": runtime_action_id,
            "reaction_code": reaction_code,
            "queued_hit_count": 1,
        },
        "Fire Bomb runtime queue",
    )
    _expect(
        resolved_record[0x05:0x08],
        b"\x00\x00\x00",
        "resolved counter metadata",
    )

    defender_hp = [
        int.from_bytes(prepared_unit[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"),
        int.from_bytes(resolved_unit[CURRENT_HP_OFFSET : CURRENT_HP_OFFSET + 2], "little"),
    ]
    attacker_slot = counter_queue_binding["attacker_slot"]
    attacker_hp = [
        _unit_hp(prepared_path, attacker_slot),
        _unit_hp(resolved_path, attacker_slot),
    ]
    counter_runtime_sample = {
        "prepared_unit_slot": prepared_slot,
        "prepared_character_id": prepared_character_id,
        "tool_id": tool_id,
        "runtime_action_id": runtime_action_id,
        "reaction_code": reaction_code,
        "attacker_slot": attacker_slot,
        "target_slot": counter_queue_binding["target_slot"],
        "incoming_action_id": counter_queue_binding["incoming_action_id"],
        "queued_hit_count": counter_queue_binding["queued_hit_count"],
        "defender_hp": defender_hp,
        "attacker_hp": attacker_hp,
        "counter_damage": attacker_hp[0] - attacker_hp[1],
        "reaction_was_consumed": (
            prepared_unit[PREPARED_REACTION_CODE_OFFSET] == reaction_code
            and queue_unit[PREPARED_REACTION_CODE_OFFSET] == 0
        ),
        "reaction_metadata_was_cleared": resolved_record[0x05:0x08] == b"\x00\x00\x00",
    }
    _expect(defender_hp, [134, 134], "counter defender HP")
    _expect(attacker_hp, [17, 3], "counter attacker HP")

    return {
        "schema_version": 1,
        "identity": source["identity"],
        "method": source["method"],
        "preprocessor": {
            "address": "0x080763E0",
            "blocking_status_priority": blocking_status_priority,
            "reaction_status_priority": reaction_status_priority,
            "only_nonzero_hit_can_trigger": True,
            "hit_count_field_offset": "0x12",
        },
        "runtime_queue": queue_binding,
        "natural_multihit_baseline": natural_multihit_baseline,
        "counter_runtime_sample": counter_runtime_sample,
        "runtime_queue_checkpoint_sha256": runtime["sha256"],
        "runtime_queue_post_checkpoint_sha256": runtime["post_sha256"],
        "resolver": {
            "normal_handler": f"0x{normal_handler:08X}",
            "shared_resolver": f"0x{SHARED_RESOLVER:08X}",
            "reaction_helper": f"0x{REACTION_HELPER:08X}",
            "reaction_metadata_is_cleared_after_hit": True,
            "status_0x10_policy": "replace_first_effective_hit_and_truncate_following_hits",
            "reverse_source_target_statuses": [0x0A, 0x09, 0x19],
            "adjacency_required_statuses": [0x04, 0x16, 0x19],
            "counter_runtime_sample_complete": True,
        },
        "conclusion": (
            "The original ROM preprocesses reactions only for non-zero hit entries. "
            "Sharingan status 0x10 stores action 15 in the attack event, truncates the "
            "event at that first effective hit, routes subtype-1 handling through the "
            "shared resolver without normal damage, and clears reaction metadata after use. "
            "Fire Bomb status 0x19 is consumed on the enemy hit, recursively resolves action "
            "0xAE with source and target reversed, preserves the defender at 134 HP, and "
            "reduces the original attacker from 17 HP to 3 HP."
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
        default=Path("notes/battle-reaction-priority-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-reaction-priority-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_reaction_priority_manifest(args.root, args.rom, args.observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
