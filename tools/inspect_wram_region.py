#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def printable(byte: int) -> str:
    if 32 <= byte <= 126:
        return chr(byte)
    return "."


def render_region(data: bytes, base: int, start: int, length: int) -> str:
    out = [f"base=0x{base:08X}", f"region=0x{start:08X}-0x{start + length:08X}", ""]
    for off in range(0, length, 16):
        row = data[start + off : start + off + 16]
        hex_bytes = " ".join(f"{b:02X}" for b in row)
        ascii_bytes = "".join(printable(b) for b in row)
        halfwords = " ".join(
            f"{int.from_bytes(row[i : i + 2], 'little'):04X}"
            for i in range(0, len(row) - 1, 2)
        )
        out.append(
            f"{start + off:08X}: {hex_bytes:<47} | {ascii_bytes:<16} | {halfwords}"
        )
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a region inside a WRAM dump.")
    parser.add_argument("dump", help="Path to WRAM dump")
    parser.add_argument("start", help="Start offset within dump, e.g. 0x2880")
    parser.add_argument("length", help="Length, e.g. 0x140")
    parser.add_argument("--base", default="0x02000000", help="Address base for display")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    dump_path = Path(args.dump)
    data = dump_path.read_bytes()
    start = int(args.start, 0)
    length = int(args.length, 0)
    base = int(args.base, 0)
    text = render_region(data, base, start, length)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
