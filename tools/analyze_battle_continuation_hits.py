#!/usr/bin/env python3
"""Bind the original-ROM continuation-hit passives to static and runtime evidence."""

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
PASSIVE_QUERY = 0x0806DDA4
RNG = 0x0809C110
CONTINUATION_GATE = 0x08076208
APPLY_CONTINUATION = 0x08076360
HIT_GENERATOR = 0x08076034
EVENT_BASE = 0x0202681C
CONTINUATION_MARK_BASE = 0x020269A4
HIT_FLAGS_BASE = 0x020269B0
EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x40000
PASSIVE_LEVEL_TABLE_OFFSET = 0x5459C8
PASSIVE_LEVEL_RECORD_SIZE = 12

EVIDENCE_RANGES = {
    "continuation_gate": (
        0x08076208,
        0x0807635C,
        "9cb961a796fa4ed3664112d6d076a464f03e3a99d5ccb89b8418e086a14d759e",
    ),
    "apply_continuation": (
        0x08076360,
        0x080763A0,
        "3e18cc348c27beeef787bfbfbb22516fbadb35150e72016c3522f6add9e0fdab",
    ),
    "call_order": (
        0x08072AC8,
        0x08072AD4,
        "d2cf0c2595bf92bcece14c504d4cd807ea0e635b05796350193a570f676de3a8",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _validate_hash(path: Path, expected: str, label: str) -> None:
    _expect(_sha256(path), expected, f"{label} SHA-256")


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _slice(rom: bytes, start: int, end: int) -> bytes:
    return rom[_offset(start) : _offset(end)]


def _validate_bl(rom: bytes, callsite: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(
        callsite,
        _u16(rom, callsite),
        _u16(rom, callsite + 2),
    )
    _expect(actual, target, label)


def _passive_record(rom: bytes, passive_id: int) -> dict[str, int]:
    offset = PASSIVE_LEVEL_TABLE_OFFSET + passive_id * PASSIVE_LEVEL_RECORD_SIZE
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


def _validate_audit(root: Path, row: dict[str, Any], label: str) -> None:
    path = root / row["audit"]
    _validate_hash(path, row["audit_sha256"], f"{label} audit")
    audit = json.loads(path.read_text(encoding="utf-8"))
    _expect(audit.get("status"), "capture-complete", f"{label} audit status")
    _expect(audit.get("success"), True, f"{label} audit success")
    _expect(audit.get("evidence_mode"), "single-input", f"{label} evidence mode")
    _expect(audit.get("inputs"), [{
        "down_frame": 5,
        "hold_frames": 8,
        "key": "A",
        "up_frame": 13,
    }], f"{label} fixed input")
    _expect(audit.get("pgid_clean"), True, f"{label} PGID cleanup")
    residue = audit.get("runtime_residue", {})
    _expect(residue.get("pgid_clean"), True, f"{label} residue PGID cleanup")
    _expect(
        residue.get("mgba_listener_clean"),
        True,
        f"{label} listener cleanup",
    )


def _runtime_row(root: Path, row: dict[str, Any], label: str) -> dict[str, Any]:
    path = root / row["output_checkpoint"]
    _validate_hash(path, row["output_sha256"], f"{label} output checkpoint")
    _validate_audit(root, row, label)
    state = load_gba_state(path)
    event = state.read_memory(EVENT_BASE, 0x20)
    _expect(event[0], 1, f"{label} source slot")
    _expect(event[1], 2, f"{label} target slot")
    _expect(event[0x0C], 5, f"{label} action ID")
    _expect(event[0x0E] & 0x3F, 1, f"{label} effect code")
    _expect(event[0x16], 0, f"{label} event +0x16 gate")
    _expect(event[0x17], 2, f"{label} current-HP/melee runtime kind")
    hit_count = event[0x12]
    return {
        "base_hit_count": hit_count,
        "continuation_mark": state.read_memory(CONTINUATION_MARK_BASE, 1)[0],
        "hit_flags": list(state.read_memory(HIT_FLAGS_BASE, hit_count)),
    }


def build_battle_continuation_manifest(
    root: Path | str,
    rom_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    _expect(source.get("schema_version"), 1, "observation schema")
    _validate_hash(rom_path, source["rom_sha256"], "ROM")
    rom = rom_path.read_bytes()

    ranges = {}
    for name, (start, end, expected_sha) in EVIDENCE_RANGES.items():
        actual = hashlib.sha256(_slice(rom, start, end)).hexdigest()
        _expect(actual, expected_sha, f"{name} bytes")
        ranges[name] = {
            "start": f"0x{start:08X}",
            "end": f"0x{end:08X}",
            "sha256": actual,
        }

    # The action transaction first rolls continuation, applies +1 to the queued
    # event hit counts, and only then generates the ordinary per-hit flags.
    _validate_bl(rom, 0x08072AC8, CONTINUATION_GATE, "continuation gate call")
    _validate_bl(rom, 0x08072ACC, APPLY_CONTINUATION, "hit-count increment call")
    _validate_bl(rom, 0x08072AD0, HIT_GENERATOR, "per-hit generator call")

    for address, expected in {
        0x08076228: 0x89E8,  # ldrh r0, [event, +0x0E]
        0x0807622A: 0x213F,  # effect-code mask
        0x0807622E: 0x2901,
        0x08076232: 0x2914,
        0x0807623A: 0x2915,
        0x08076240: 0x7DA8,  # ldrb r0, [event, +0x16]
        0x08076286: 0x7DE8,  # ldrb runtime kind, [event, +0x17]
        0x08076298: 0x2116,
        0x080762BC: 0x2117,
        0x080762E0: 0x2118,
        0x08076300: 0xF025,  # BL first halfword to RNG
        0x08076304: 0x2164,
        0x08076384: 0x7C88,  # ldrb event +0x12
        0x08076386: 0x3001,
        0x08076388: 0x7488,  # strb event +0x12
    }.items():
        _expect(_u16(rom, address), expected, f"instruction at 0x{address:08X}")
    _validate_bl(rom, 0x0807629C, PASSIVE_QUERY, "current-HP passive query")
    _validate_bl(rom, 0x080762C0, PASSIVE_QUERY, "current-chakra passive query")
    _validate_bl(rom, 0x080762E4, PASSIVE_QUERY, "ninja-tool passive query")
    _validate_bl(rom, 0x08076300, RNG, "continuation RNG")

    expected_records = {
        17: {
            "target_type": 0x16,
            "reserved": 0,
            "base_a": 10,
            "base_b": 0,
            "per_level_a": 5,
            "per_level_b": 0,
        },
        18: {
            "target_type": 0x17,
            "reserved": 0,
            "base_a": 10,
            "base_b": 0,
            "per_level_a": 5,
            "per_level_b": 0,
        },
        19: {
            "target_type": 0x18,
            "reserved": 0,
            "base_a": 10,
            "base_b": 0,
            "per_level_a": 5,
            "per_level_b": 0,
        },
    }
    for passive_id, expected in expected_records.items():
        _expect(
            _passive_record(rom, passive_id),
            expected,
            f"passive {passive_id} progression",
        )

    source_path = root / source["source_checkpoint"]
    controlled = source["controlled_patch"]
    controlled_path = root / controlled["input_checkpoint"]
    _validate_hash(source_path, source["source_sha256"], "source checkpoint")
    _validate_hash(
        controlled_path,
        controlled["input_sha256"],
        "controlled input checkpoint",
    )
    source_state = load_gba_state(source_path)
    controlled_state = load_gba_state(controlled_path)
    source_ewram = source_state.read_memory(EWRAM_BASE, EWRAM_SIZE)
    controlled_ewram = controlled_state.read_memory(EWRAM_BASE, EWRAM_SIZE)
    diffs = [
        EWRAM_BASE + index
        for index, (before, after) in enumerate(
            zip(source_ewram, controlled_ewram)
        )
        if before != after
    ]
    patch_address = int(controlled["address"], 16)
    _expect(diffs, [patch_address], "single-byte controlled EWRAM patch")
    _expect(
        source_state.read_memory(patch_address - 1, 1)[0],
        controlled["passive_id"],
        "controlled passive ID",
    )
    before = source_state.read_memory(patch_address, 1)[0]
    after = controlled_state.read_memory(patch_address, 1)[0]
    _expect((before, after), (controlled["before"], controlled["after"]), "patch")
    record = expected_records[controlled["passive_id"]]
    chance = record["base_a"] + record["per_level_a"] * (after - 1)
    _expect(chance, 100, "controlled continuation chance")

    baseline = _runtime_row(root, source["baseline"], "baseline")
    controlled_runtime = _runtime_row(
        root,
        source["controlled_100_percent"],
        "controlled 100-percent",
    )
    _expect(
        baseline,
        {
            "base_hit_count": 1,
            "continuation_mark": 0,
            "hit_flags": [1],
        },
        "baseline runtime",
    )
    _expect(
        controlled_runtime,
        {
            "base_hit_count": 2,
            "continuation_mark": 1,
            "hit_flags": [1, 1],
        },
        "controlled runtime",
    )

    return {
        "schema_version": 1,
        "identity": source["identity"],
        "rom": str(rom_path),
        "rom_sha256": source["rom_sha256"],
        "evidence_ranges": ranges,
        "category_bindings": {
            "current_chakra": {
                "runtime_kind": 1,
                "passive_target_type": 0x17,
            },
            "current_hp": {
                "runtime_kind": 2,
                "passive_target_type": 0x16,
            },
            "ninja_tool": {
                "runtime_kind": 5,
                "passive_target_type": 0x18,
            },
        },
        "eligible_effect_codes": [0x01, 0x14, 0x15],
        "chance_formula": "base_a + per_level_a * (stored_level - 1)",
        "success_condition": "(rng_value * 100 >> 15) < chance_percent",
        "shared_roll": (
            "One roll per unique action ID; all queued events with that action ID "
            "reuse the first event's continuation result."
        ),
        "rng_order": [
            "one continuation roll per unique action id when its passive exists",
            "increase every matching queued event base hit count by one on success",
            "ordinary base-hit roll for every generated hit",
            "critical roll for every landed hit when its passive exists",
            "ignore-defense roll for every landed hit when its passive exists",
        ],
        "controlled_patch": {
            "address": controlled["address"],
            "passive_id": controlled["passive_id"],
            "before": before,
            "after": after,
            "computed_chance_percent": chance,
        },
        "runtime_sample": {
            "action_id": 5,
            "effect_code": 1,
            "runtime_kind": 2,
            "base_hit_count": {
                "baseline": baseline["base_hit_count"],
                "controlled_100_percent": controlled_runtime["base_hit_count"],
            },
            "continuation_mark": {
                "baseline": baseline["continuation_mark"],
                "controlled_100_percent": controlled_runtime[
                    "continuation_mark"
                ],
            },
            "hit_flags": {
                "baseline": baseline["hit_flags"],
                "controlled_100_percent": controlled_runtime["hit_flags"],
            },
        },
        "guide_corroboration": source["guide_corroboration"],
        "conclusion": (
            "Continuation is a pre-hit-count probability gate, not bonus damage. "
            "A success appends exactly one ordinary hit; that new hit independently "
            "uses the existing hit, critical, ignore-defense, and reaction pipeline."
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
        default=Path(
            "notes/battle-continuation-hit-observations-20260725.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-continuation-hit-bindings-20260725.json"),
    )
    args = parser.parse_args()
    result = build_battle_continuation_manifest(
        args.root,
        args.rom,
        args.observations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
