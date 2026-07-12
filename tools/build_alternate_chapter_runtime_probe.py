#!/usr/bin/env python3
"""Force the chapter selector through table 0x60D54 and trace its opcode."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

try:
    from tools.build_chapter_script_probe import build_probe as build_script_probe
except ModuleNotFoundError:
    from build_chapter_script_probe import build_probe as build_script_probe

ROM_BASE = 0x08000000
SELECTOR_BRANCH = 0x0808F5A4
SELECTOR_OFFSET = SELECTOR_BRANCH - ROM_BASE
EXPECTED_BRANCH = bytes.fromhex("0cd0")  # beq primary path at 0x0808F5C0
FORCE_ALTERNATE = bytes.fromhex("c046")  # nop: fall through alternate path


def build_probe(base: bytes) -> bytes:
    if base[SELECTOR_OFFSET:SELECTOR_OFFSET + 2] != EXPECTED_BRANCH:
        raise ValueError("alternate selector branch bytes do not match")
    rom = bytearray(build_script_probe(base))
    rom[SELECTOR_OFFSET:SELECTOR_OFFSET + 2] = FORCE_ALTERNATE
    return bytes(rom)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    args = parser.parse_args()
    output = build_probe(args.base_rom.read_bytes())
    args.output_rom.write_bytes(output)
    print(f"wrote {args.output_rom}: sha256={hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
