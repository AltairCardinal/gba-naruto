#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from tools.thumb_branch import find_thumb_branches
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from thumb_branch import find_thumb_branches

ROM_BASE = 0x08000000


def scan_calls(
    rom_path: Path,
    target: int,
    *,
    start: int | None = None,
    end: int | None = None,
) -> list[tuple[int, str, str]]:
    data = rom_path.read_bytes()
    return [
        (branch.address, branch.mnemonic, branch.op_str)
        for branch in find_thumb_branches(
            data,
            target,
            rom_base=ROM_BASE,
            start=start,
            end=end,
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find Thumb branch/call sites that target a ROM address."
    )
    parser.add_argument("rom", help="ROM path")
    parser.add_argument("target", help="GBA ROM address, e.g. 0x08066D14")
    parser.add_argument("--start", type=lambda value: int(value, 0))
    parser.add_argument("--end", type=lambda value: int(value, 0))
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    target = int(args.target, 0)
    hits = scan_calls(rom_path, target, start=args.start, end=args.end)
    lines = [f"rom={rom_path}", f"target=0x{target:08X}", f"matches={len(hits)}", ""]
    for address, mnemonic, op_str in hits:
        lines.append(f"0x{address:08X}: {mnemonic:<4} {op_str}")
    text = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
