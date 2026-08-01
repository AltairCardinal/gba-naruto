#!/usr/bin/env python3
"""Build a minimal route probe by changing scenario 39's selected battle ID."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

try:
    from tools.build_chapter_script_probe import BASE_SHA1
except ModuleNotFoundError:
    from build_chapter_script_probe import BASE_SHA1


BATTLE_COMMAND_OFFSET = 0x31070
EXPECTED_COMMAND = b"\x1A\x28\x02\x00"
BATTLE_GROUP_COUNT = 47


def build_probe(base: bytes, *, battle_id: int, verify_sha1: bool = True) -> bytes:
    if verify_sha1:
        digest = hashlib.sha1(base).hexdigest()
        if digest != BASE_SHA1:
            raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    if not isinstance(battle_id, int) or isinstance(battle_id, bool):
        raise ValueError("battle ID must be an integer")
    if not 0 <= battle_id < BATTLE_GROUP_COUNT:
        raise ValueError(f"battle ID must be in 0..{BATTLE_GROUP_COUNT - 1}")
    command = base[BATTLE_COMMAND_OFFSET:BATTLE_COMMAND_OFFSET + len(EXPECTED_COMMAND)]
    if command != EXPECTED_COMMAND:
        raise ValueError(
            f"scenario 39 battle command mismatch: expected {EXPECTED_COMMAND.hex()}, got {command.hex()}"
        )
    output = bytearray(base)
    output[BATTLE_COMMAND_OFFSET + 1] = battle_id
    return bytes(output)


def write_probe(base_rom: Path, output_rom: Path, *, battle_id: int) -> str:
    """Write a new probe without following links or replacing existing files."""

    base_rom = Path(base_rom)
    output_rom = Path(output_rom)
    if base_rom.is_symlink() or output_rom.is_symlink():
        raise ValueError("base and output ROM paths must not be symbolic links")
    try:
        resolved_base = base_rom.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"base ROM is missing: {base_rom}") from error
    resolved_output = output_rom.resolve(strict=False)
    if resolved_output == resolved_base:
        raise ValueError("output ROM must not replace the base ROM")
    if output_rom.exists():
        raise ValueError(f"output ROM already exists: {output_rom}")
    output = build_probe(resolved_base.read_bytes(), battle_id=battle_id)
    output_rom.parent.mkdir(parents=True, exist_ok=True)
    if output_rom.is_symlink() or output_rom.exists():
        raise ValueError(f"output ROM appeared before creation: {output_rom}")
    try:
        with output_rom.open("xb") as destination:
            destination.write(output)
    except FileExistsError as error:
        raise ValueError(f"output ROM already exists: {output_rom}") from error
    return hashlib.sha256(output).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--battle-id", type=int, required=True)
    args = parser.parse_args()
    digest = write_probe(args.base_rom, args.output_rom, battle_id=args.battle_id)
    print(f"wrote {args.output_rom}: sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
