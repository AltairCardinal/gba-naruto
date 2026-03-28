#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROM_BASE = 0x08000000


def parse_target(value: str) -> int:
    target = int(value, 0)
    if target >= ROM_BASE:
        target -= ROM_BASE
    return target


def read_u32_le(buf: bytes, offset: int) -> int:
    return int.from_bytes(buf[offset : offset + 4], "little")


def classify_ref_context(buf: bytes, offset: int) -> str:
    if offset >= 8:
        prev_halfword = int.from_bytes(buf[offset - 2 : offset], "little")
        prev_word = int.from_bytes(buf[offset - 4 : offset], "little")
        prev_dword = int.from_bytes(buf[offset - 8 : offset - 4], "little")
        if (prev_halfword & 0xF800) in {0x4800, 0x4900, 0x4A00, 0x4B00}:
            return "likely_literal_pool_after_ldr"
        if ROM_BASE <= prev_word < ROM_BASE + len(buf):
            return "likely_pointer_table"
        if ROM_BASE <= prev_dword < ROM_BASE + len(buf):
            return "likely_pointer_table"
    return "unknown"


def scan_references(buf: bytes, target_offset: int, aligned_only: bool) -> dict:
    target_value = ROM_BASE + target_offset
    refs = []
    step = 4 if aligned_only else 1
    for offset in range(0, len(buf) - 3, step):
        if read_u32_le(buf, offset) == target_value:
            refs.append(
                {
                    "offset": offset,
                    "context": classify_ref_context(buf, offset),
                }
            )
    return {
        "target_offset": target_offset,
        "target_address": target_value,
        "reference_count": len(refs),
        "references": refs,
    }


def summarize(report: dict) -> str:
    lines = []
    lines.append(
        f"Target ROM offset: 0x{report['target_offset']:06X} "
        f"(address 0x{report['target_address']:08X})"
    )
    lines.append(f"References found: {report['reference_count']}")

    context_counts: dict[str, int] = {}
    for ref in report["references"]:
        context_counts[ref["context"]] = context_counts.get(ref["context"], 0) + 1

    if context_counts:
        lines.append("Context summary:")
        for context, count in sorted(context_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  - {context}: {count}")

    lines.append("First references:")
    for ref in report["references"][:32]:
        lines.append(f"  - 0x{ref['offset']:06X} {ref['context']}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find references to a ROM target address.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("target", help="ROM offset like 0x4081 or absolute GBA address like 0x08004081")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path",
    )
    parser.add_argument(
        "--unaligned",
        action="store_true",
        help="Scan every byte instead of aligned 32-bit offsets only",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    report = scan_references(buf, parse_target(args.target), aligned_only=not args.unaligned)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(summarize(report))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
