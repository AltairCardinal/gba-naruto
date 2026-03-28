#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def render_diff(a: bytes, b: bytes, start: int, length: int) -> str:
    lines = [f"region=0x{start:08X}-0x{start + length:08X}", ""]
    for off in range(0, length, 16):
        ra = a[start + off : start + off + 16]
        rb = b[start + off : start + off + 16]
        if ra == rb:
            continue
        delta = "".join("^" if x != y else "." for x, y in zip(ra, rb))
        lines.append(f"{start + off:08X}: {' '.join(f'{x:02X}' for x in ra)}")
        lines.append(f"{start + off:08X}: {' '.join(f'{x:02X}' for x in rb)}")
        lines.append(f"{start + off:08X}: {delta}")
        lines.append("")
    if len(lines) == 2:
        lines.append("no differences")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a region between two WRAM dumps."
    )
    parser.add_argument("dump_a")
    parser.add_argument("dump_b")
    parser.add_argument("start")
    parser.add_argument("length")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    a = Path(args.dump_a).read_bytes()
    b = Path(args.dump_b).read_bytes()
    start = int(args.start, 0)
    length = int(args.length, 0)
    text = render_diff(a, b, start, length)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
