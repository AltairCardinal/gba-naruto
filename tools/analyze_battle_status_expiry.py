#!/usr/bin/env python3
"""Bind generic battle status duration ticking to the side-end transition."""

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
EWRAM_BASE = 0x02000000
EWRAM_SIZE = 0x40000
UNIT_POOL_BASE = 0x020240C0
UNIT_RECORD_SIZE = 0x1D4
BATTLE_CONTROL = 0x0202680C
SIDE_OFFSET = 2
STATUS_CODE_OFFSET = 0xD4
STATUS_DURATION_OFFSET = 0xD6
STATUS_STRIDE = 8
STATUS_SLOT_COUNT = 16
STATUS_TICK = 0x0806C308
STATUS_REMOVE = 0x0806C1A4
SIDE_END_ENTRY = 0x0807367C
SIDE_TOGGLE = 0x080736B0


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


def _validate_audit(
    root: Path, rom_sha256: str, row: dict[str, Any]
) -> None:
    audit_path = root / row["audit"]
    _validate_hash(audit_path, row["audit_sha256"], "side-end audit")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    _expect(audit.get("success"), True, "side-end audit success")
    _expect(audit.get("status"), "capture-complete", "side-end audit status")
    _expect(audit.get("rom_sha256"), rom_sha256, "side-end audit ROM")
    _expect(audit.get("staged_rom_sha256"), rom_sha256, "side-end staged ROM")
    _expect(audit.get("evidence_mode"), "single-input", "side-end audit mode")
    inputs = audit.get("inputs", [])
    _expect(len(inputs), 1, "side-end input count")
    _expect(inputs[0]["key"], "A", "side-end input key")
    for key, expected in (
        ("input_state", row["input_sha256"]),
        ("output_state", row["output_sha256"]),
    ):
        _expect(audit[f"{key}_sha256"], expected, f"audit {key} hash")
        _validate_hash(_rooted_path(root, audit[key]), expected, key)


def build_status_expiry_manifest(
    root: Path | str,
    rom_path: Path | str,
    observations_path: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    rom_path = Path(rom_path)
    source = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if source.get("schema_version") != 1:
        raise ValueError("unsupported battle status expiry schema")
    rom_sha256 = _sha256(rom_path)
    _expect(rom_sha256, source["rom_sha256"], "ROM SHA-256")
    rom = rom_path.read_bytes()

    # State 0x1100 calls the global tick before toggling battle_control+2.
    _validate_bl(rom, SIDE_END_ENTRY, STATUS_TICK, "side-end status tick call")
    _expect(
        rom[_rom_offset(SIDE_TOGGLE) : _rom_offset(SIDE_TOGGLE) + 12].hex(),
        "0f498a78012042408a704878",
        "side toggle sequence",
    )
    _expect(SIDE_END_ENTRY < SIDE_TOGGLE, True, "tick-before-toggle address order")

    # The tick iterates units 1..12, sixteen 8-byte status slots, decrements a
    # nonzero duration, and removes the slot only after it reaches zero.
    _expect(_u16(rom, 0x0806C30A), 0x2501, "first unit slot")
    _expect(_u16(rom, 0x0806C35A), 0x2D0C, "last unit slot")
    _expect(_u16(rom, 0x0806C322), 0x00E0, "status index times eight")
    _expect(_u16(rom, 0x0806C328), 0x30D4, "status code offset")
    _expect(_u16(rom, 0x0806C330), 0x31D6, "status duration offset")
    _expect(_u16(rom, 0x0806C338), 0x3801, "duration decrement")
    _expect(_u16(rom, 0x0806C352), 0x2C0F, "last status slot")
    _validate_bl(rom, 0x0806C348, STATUS_REMOVE, "zero-duration removal")

    source_path = root / source["source_checkpoint"]
    _validate_hash(source_path, source["source_sha256"], "source checkpoint")
    source_state = load_gba_state(source_path)
    unit_slot = source["unit_slot"]
    unit_address = UNIT_POOL_BASE + unit_slot * UNIT_RECORD_SIZE
    _expect(_unit(source_state, unit_slot)[0], source["unit_character_id"], "unit identity")
    patch_addresses = [
        unit_address + STATUS_CODE_OFFSET,
        unit_address + STATUS_DURATION_OFFSET,
    ]
    runtime_samples = []
    for row in source["samples"]:
        _validate_audit(root, rom_sha256, row)
        input_path = root / row["input_checkpoint"]
        output_path = root / row["output_checkpoint"]
        _validate_hash(input_path, row["input_sha256"], "patched checkpoint")
        _validate_hash(output_path, row["output_sha256"], "side-end checkpoint")
        input_state = load_gba_state(input_path)
        output_state = load_gba_state(output_path)
        actual_patch_addresses = [
            EWRAM_BASE + offset
            for offset, (before, after) in enumerate(
                zip(
                    source_state.read_memory(EWRAM_BASE, EWRAM_SIZE),
                    input_state.read_memory(EWRAM_BASE, EWRAM_SIZE),
                )
            )
            if before != after
        ]
        _expect(actual_patch_addresses, patch_addresses, "controlled status patch")
        input_unit = _unit(input_state, unit_slot)
        output_unit = _unit(output_state, unit_slot)
        initial_duration = row["initial_duration"]
        _expect(input_unit[STATUS_CODE_OFFSET], 1, "patched status code")
        _expect(
            input_unit[STATUS_DURATION_OFFSET],
            initial_duration,
            "patched status duration",
        )
        side = [
            source_state.read_memory(BATTLE_CONTROL + SIDE_OFFSET, 1)[0],
            output_state.read_memory(BATTLE_CONTROL + SIDE_OFFSET, 1)[0],
        ]
        codes = [input_unit[STATUS_CODE_OFFSET], output_unit[STATUS_CODE_OFFSET]]
        durations = [
            input_unit[STATUS_DURATION_OFFSET],
            output_unit[STATUS_DURATION_OFFSET],
        ]
        runtime_samples.append(
            {
                "initial_duration": initial_duration,
                "side": side,
                "status_code": codes,
                "duration": durations,
                "removed_at_zero": codes[1] == 0 and durations[1] == 0,
            }
        )
    _expect(
        runtime_samples,
        [
            {
                "initial_duration": 1,
                "side": [0, 1],
                "status_code": [1, 0],
                "duration": [1, 0],
                "removed_at_zero": True,
            },
            {
                "initial_duration": 2,
                "side": [0, 1],
                "status_code": [1, 1],
                "duration": [2, 1],
                "removed_at_zero": False,
            },
        ],
        "side-end runtime samples",
    )

    return {
        "schema_version": 1,
        "identity": source["identity"],
        "method": source["method"],
        "controller_state": "0x1100",
        "status_tick": f"0x{STATUS_TICK:08X}",
        "unit_slots": [1, 12],
        "status_slots_per_unit": STATUS_SLOT_COUNT,
        "status_stride": STATUS_STRIDE,
        "code_offset": "unit+0xD4",
        "duration_offset": "unit+0xD6",
        "tick_occurs_before_side_toggle": True,
        "controlled_patch_offsets": ["unit+0xD4", "unit+0xD6"],
        "runtime_samples": runtime_samples,
        "conclusion": (
            "At state 0x1100 the original ROM decrements every active status duration "
            "for units 1 through 12 before toggling sides. Duration 2 becomes 1 and "
            "remains active; duration 1 reaches zero and the complete slot is removed."
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
        default=Path("notes/battle-status-expiry-observations-20260723.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-status-expiry-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_status_expiry_manifest(args.root, args.rom, args.observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
