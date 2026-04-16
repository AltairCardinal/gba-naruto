#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lib import parse_int


def render_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch a ROM at a given offset with Shift-JIS text.")
    parser.add_argument("input_rom", type=Path, help="Input ROM path")
    parser.add_argument("output_rom", type=Path, help="Output ROM path")
    parser.add_argument("offset", help="Target ROM offset")
    parser.add_argument("text", help="Replacement text to encode as Shift-JIS")
    parser.add_argument(
        "--expected-len",
        type=parse_int,
        default=None,
        help="Require the encoded replacement to match this byte length",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    offset = parse_int(args.offset)
    replacement = args.text.encode("shift_jis")
    if args.expected_len is not None and len(replacement) != args.expected_len:
        raise SystemExit(
            f"replacement length {len(replacement)} does not match expected {args.expected_len}"
        )

    buf = bytearray(args.input_rom.read_bytes())
    if offset + len(replacement) > len(buf):
        raise SystemExit(f"offset 0x{offset:06X} + replacement ({len(replacement)} bytes) exceeds ROM size ({len(buf)} bytes)")
    original = bytes(buf[offset : offset + len(replacement)])
    buf[offset : offset + len(replacement)] = replacement

    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(buf)

    print(f"Patched: {args.input_rom} -> {args.output_rom}")
    print(f"Offset: 0x{offset:06X}")
    print(f"Original bytes:   {render_bytes(original)}")
    print(f"Replacement bytes:{render_bytes(replacement)}")
    print(f"Original text:    {original.decode('shift_jis', errors='replace')!r}")
    print(f"Replacement text: {args.text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
