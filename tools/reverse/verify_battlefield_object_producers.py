#!/usr/bin/env python3
"""Independently verify the battlefield-object producer inventory."""

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
ALLOCATOR = 0x08081024
SELECTOR = 0x0807FE2C
SPAWNER = 0x080800A4
EXPECTED_PATHS = (
    (0x0806C5BA, 18, 0x0806C5D8, "natural hardcoded selector path"),
    (0x08081BDA, 7, 0x08081BF4, "type-2 battlefield-object expiry branch"),
    (0x08081FB8, 7, 0x08081FD2, "type-1 battlefield-object expiry zero-event branch"),
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _u16(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("verification address outside ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _bl(rom: bytes, address: int) -> int | None:
    return decode_thumb_bl(address, _u16(rom, address), _u16(rom, address + 2))


def _movs_r0(rom: bytes, address: int) -> int:
    halfword = _u16(rom, address)
    if halfword & 0xFF00 != 0x2000:
        raise ValueError(f"missing MOVS r0 at 0x{address:08X}")
    return halfword & 0xFF


def verify(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    if payload.get("schema") != "battlefield-object-producers-v1":
        raise ValueError("schema mismatch")
    if payload.get("sources", {}).get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("source ROM hash mismatch")

    branches = find_thumb_branches(rom, ALLOCATOR, rom_base=ROM_BASE)
    rows = payload.get("direct_allocator_calls")
    if not isinstance(rows, list) or len(rows) != len(branches):
        raise ValueError("direct allocator call denominator mismatch")
    expected_types = []
    for branch, row in zip(branches, rows, strict=True):
        object_type = _movs_r0(rom, branch.address - 4)
        expected_types.append(object_type)
        expected = {
            "callsite": f"0x{branch.address:08X}",
            "object_type": object_type,
            "type_load": f"0x{branch.address - 4:08X}",
            "allocator": f"0x{ALLOCATOR:08X}",
            "callsite_window_sha256": _sha256(
                rom[branch.address - ROM_BASE - 8 : branch.address - ROM_BASE + 4]
            ),
        }
        if row != expected:
            raise ValueError(f"direct allocator row mismatch at 0x{branch.address:08X}")

    type_2_rows = [row for row in rows if row["object_type"] == 2]
    expected_counts = {
        "direct_allocator_calls": len(branches),
        "immediate_type_calls": len(branches),
        "direct_type_2_calls": len(type_2_rows),
    }
    if payload.get("counts") != expected_counts:
        raise ValueError("direct allocator counts mismatch")
    if payload.get("direct_object_types") != sorted(set(expected_types)):
        raise ValueError("direct object type set mismatch")
    if payload.get("type_2_direct_producers") != type_2_rows:
        raise ValueError("type-2 producer list mismatch")

    expected_paths = []
    for selector_call, sequence_id, spawn_call, source in EXPECTED_PATHS:
        if _movs_r0(rom, selector_call - 2) != sequence_id:
            raise ValueError("ROM selector immediate mismatch")
        if _bl(rom, selector_call) != SELECTOR or _bl(rom, spawn_call) != SPAWNER:
            raise ValueError("ROM selector/spawn target mismatch")
        expected_paths.append(
            {
                "selector_callsite": f"0x{selector_call:08X}",
                "sequence_id": sequence_id,
                "spawn_callsite": f"0x{spawn_call:08X}",
                "source": source,
            }
        )
    if payload.get("group_18_selector_paths") != expected_paths:
        raise ValueError("group 18 selector paths mismatch")

    expected_scope = {
        "direct_allocator_call_denominator_complete": True,
        "direct_type_2_producer_found": bool(type_2_rows),
        "indirect_or_post_allocation_type_2_producer_proven_absent": False,
        "natural_group_18_route_proven": False,
        "modified_rom_pixel_ab_proven": False,
    }
    if payload.get("scope") != expected_scope:
        raise ValueError("scope mismatch")
    return {
        "errors": [],
        "verified_direct_allocator_calls": len(branches),
        "verified_group_18_paths": len(expected_paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    payload = json.loads(args.artifact.read_text(encoding="utf-8"))
    print(json.dumps(verify(args.root, payload), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
