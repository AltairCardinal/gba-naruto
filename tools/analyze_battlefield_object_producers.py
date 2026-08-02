#!/usr/bin/env python3
"""Enumerate direct battlefield-object producers and Group 18 selector paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thumb_branch import decode_thumb_bl, find_thumb_branches


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
OBJECT_ALLOCATOR = 0x08081024
SELECTOR = 0x0807FE2C
SPAWNER = 0x080800A4

GROUP_18_PATHS = (
    (0x0806C5BA, 18, 0x0806C5D8, "natural hardcoded selector path"),
    (0x08081BDA, 7, 0x08081BF4, "type-2 battlefield-object expiry branch"),
    (0x08081FB8, 7, 0x08081FD2, "type-1 battlefield-object expiry zero-event branch"),
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _u16(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError(f"Thumb address outside ROM: 0x{address:08X}")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _decode_bl_at(rom: bytes, address: int) -> int | None:
    return decode_thumb_bl(address, _u16(rom, address), _u16(rom, address + 2))


def _immediate_movs_r0(rom: bytes, address: int) -> int:
    instruction = _u16(rom, address)
    if instruction & 0xFF00 != 0x2000:
        raise ValueError(f"expected MOVS r0 immediate at 0x{address:08X}")
    return instruction & 0xFF


def _validate_group_18_paths(rom: bytes) -> list[dict[str, Any]]:
    paths = []
    for selector_callsite, sequence_id, spawn_callsite, source in GROUP_18_PATHS:
        if _immediate_movs_r0(rom, selector_callsite - 2) != sequence_id:
            raise ValueError(f"sequence mismatch at 0x{selector_callsite:08X}")
        if _decode_bl_at(rom, selector_callsite) != SELECTOR:
            raise ValueError(f"selector target mismatch at 0x{selector_callsite:08X}")
        if _decode_bl_at(rom, spawn_callsite) != SPAWNER:
            raise ValueError(f"spawn target mismatch at 0x{spawn_callsite:08X}")
        paths.append(
            {
                "selector_callsite": f"0x{selector_callsite:08X}",
                "sequence_id": sequence_id,
                "spawn_callsite": f"0x{spawn_callsite:08X}",
                "source": source,
            }
        )
    return paths


def analyze(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rom_path = root / "rom/base.gba"
    rom = rom_path.read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    branches = find_thumb_branches(rom, OBJECT_ALLOCATOR, rom_base=ROM_BASE)
    direct_calls = []
    for branch in branches:
        object_type = _immediate_movs_r0(rom, branch.address - 4)
        direct_calls.append(
            {
                "callsite": f"0x{branch.address:08X}",
                "object_type": object_type,
                "type_load": f"0x{branch.address - 4:08X}",
                "allocator": f"0x{OBJECT_ALLOCATOR:08X}",
                "callsite_window_sha256": _sha256(
                    rom[branch.address - ROM_BASE - 8 : branch.address - ROM_BASE + 4]
                ),
            }
        )

    direct_types = sorted({row["object_type"] for row in direct_calls})
    type_2 = [row for row in direct_calls if row["object_type"] == 2]
    return {
        "schema": "battlefield-object-producers-v1",
        "sources": {
            "rom": {
                "path": str(rom_path.relative_to(root)),
                "sha256": rom_sha256,
            },
            "object_allocator": f"0x{OBJECT_ALLOCATOR:08X}",
        },
        "counts": {
            "direct_allocator_calls": len(direct_calls),
            "immediate_type_calls": len(direct_calls),
            "direct_type_2_calls": len(type_2),
        },
        "direct_allocator_calls": direct_calls,
        "direct_object_types": direct_types,
        "type_2_direct_producers": type_2,
        "group_18_selector_paths": _validate_group_18_paths(rom),
        "scope": {
            "direct_allocator_call_denominator_complete": True,
            "direct_type_2_producer_found": bool(type_2),
            "indirect_or_post_allocation_type_2_producer_proven_absent": False,
            "natural_group_18_route_proven": False,
            "modified_rom_pixel_ab_proven": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = analyze(args.root)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
