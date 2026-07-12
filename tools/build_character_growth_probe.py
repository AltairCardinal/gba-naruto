#!/usr/bin/env python3
"""Build controlled diagnostic ROMs for the character-growth consumer chain."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


BASE_SHA1 = "26f60795fa5e63b4f0264b84e453beffd56b9f7d"
LEVEL_MINUS_ONE_IMMEDIATE = 0x06D9BA
CHAR1_TEMPLATE_02_GROWTH = 0x54507C


def replace_checked(rom: bytearray, offset: int, before: bytes, after: bytes) -> None:
    actual = bytes(rom[offset : offset + len(before)])
    if actual != before:
        raise ValueError(
            f"before-byte mismatch at 0x{offset:X}: expected {before.hex()}, got {actual.hex()}"
        )
    if len(before) != len(after):
        raise ValueError("probe replacements must preserve ROM length")
    rom[offset : offset + len(after)] = after


def build_probe(base: bytes, growth_value: int | None) -> bytes:
    digest = hashlib.sha1(base).hexdigest()
    if digest != BASE_SHA1:
        raise ValueError(f"base ROM SHA-1 must be {BASE_SHA1}, got {digest}")
    rom = bytearray(base)
    # Thumb `subs r0, #1` -> `subs r0, #0`.  This diagnostic-only change makes
    # a level-1 opening unit exercise the existing growth arithmetic path.
    replace_checked(rom, LEVEL_MINUS_ONE_IMMEDIATE, bytes.fromhex("0138"), bytes.fromhex("0038"))
    if growth_value is not None:
        if not 0 <= growth_value <= 0xFFFF:
            raise ValueError("growth value must fit u16")
        replace_checked(
            rom,
            CHAR1_TEMPLATE_02_GROWTH,
            (100).to_bytes(2, "little"),
            growth_value.to_bytes(2, "little"),
        )
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument(
        "--growth-value",
        type=lambda value: int(value, 0),
        default=None,
        help="Optional character-1 template+2 growth replacement (baseline is 100)",
    )
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes(), args.growth_value)
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(output)
    print(
        f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()} "
        f"growth={args.growth_value if args.growth_value is not None else 100}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
