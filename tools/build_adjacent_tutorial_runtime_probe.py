#!/usr/bin/env python3
"""Move tutorial Iruka into Naruto's live target range for action probes."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

try:
    from tools.build_chapter_script_probe import BASE_SHA1
except ModuleNotFoundError:
    from build_chapter_script_probe import BASE_SHA1


IRUKA_RECORD = 0x58A80C
EXPECTED_PREFIX = bytes.fromhex("1e01040402000000")
GRID_WIDTH = 9
GRID_HEIGHT = 22


def build_probe(
    base: bytes, *, x: int = 5, y: int = 10, affiliation: int = 1,
    trace: str = "none",
) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if not 0 <= x < GRID_WIDTH or not 0 <= y < GRID_HEIGHT:
        raise ValueError("coordinate must fit the tutorial 9x22 grid")
    if affiliation not in (0, 1):
        raise ValueError("affiliation must be 0 or 1")
    if trace not in {"none", "battle-message", "resource-pointer", "skill-relation"}:
        raise ValueError("unknown trace mode")
    if base[IRUKA_RECORD:IRUKA_RECORD + len(EXPECTED_PREFIX)] != EXPECTED_PREFIX:
        raise ValueError("tutorial Iruka formation record does not match")
    if trace == "battle-message":
        try:
            from tools.build_battle_message_runtime_probe import build_probe as traced
        except ModuleNotFoundError:
            from build_battle_message_runtime_probe import build_probe as traced
        rom = bytearray(traced(base))
    elif trace == "resource-pointer":
        try:
            from tools.build_resource_pointer_runtime_probe import build_probe as traced
        except ModuleNotFoundError:
            from build_resource_pointer_runtime_probe import build_probe as traced
        rom = bytearray(traced(base))
    elif trace == "skill-relation":
        try:
            from tools.build_skill_relation_runtime_probe import build_probe as traced
        except ModuleNotFoundError:
            from build_skill_relation_runtime_probe import build_probe as traced
        rom = bytearray(traced(base))
    else:
        rom = bytearray(base)
    rom[IRUKA_RECORD + 1:IRUKA_RECORD + 4] = bytes((affiliation, x, y))
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--x", type=int, default=5)
    parser.add_argument("--y", type=int, default=10)
    parser.add_argument("--affiliation", type=int, default=1)
    parser.add_argument(
        "--trace", choices=("none", "battle-message", "resource-pointer", "skill-relation"),
        default="none",
    )
    args = parser.parse_args()
    output = build_probe(
        args.base_rom.read_bytes(), x=args.x, y=args.y,
        affiliation=args.affiliation, trace=args.trace,
    )
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
