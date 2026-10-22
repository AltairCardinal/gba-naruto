#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ASCII_OK = set(range(0x20, 0x7F))
CONTROL_OK = {0x00, 0x09, 0x0A, 0x0D}


def is_sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xEF


def is_sjis_trail(value: int) -> bool:
    return (0x40 <= value <= 0x7E) or (0x80 <= value <= 0xFC and value != 0x7F)


def is_halfwidth_kana(value: int) -> bool:
    return 0xA1 <= value <= 0xDF


def decode_run(data: bytes) -> str:
    return data.decode("shift_jis", errors="replace")


def scan_sjis_blocks(buf: bytes, min_chars: int, min_pairs: int) -> list[dict]:
    results = []
    i = 0
    n = len(buf)
    while i < n:
        start = i
        pair_count = 0
        char_count = 0
        while i < n:
            b = buf[i]
            if b in ASCII_OK or b in CONTROL_OK or is_halfwidth_kana(b):
                i += 1
                char_count += 1
                continue
            if i + 1 < n and is_sjis_lead(b) and is_sjis_trail(buf[i + 1]):
                i += 2
                char_count += 1
                pair_count += 1
                continue
            break
        if char_count >= min_chars and pair_count >= min_pairs:
            data = buf[start:i]
            results.append(
                {
                    "offset": start,
                    "length": len(data),
                    "char_count": char_count,
                    "pair_count": pair_count,
                    "sample": decode_run(data[:96]),
                }
            )
        i = max(i + 1, start + 1)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find Shift-JIS-like blocks in a ROM.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("--min-chars", type=int, default=12, help="Minimum decoded character count")
    parser.add_argument("--min-pairs", type=int, default=4, help="Minimum Shift-JIS double-byte pair count")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    return parser.parse_args()


def summarize(blocks: list[dict]) -> str:
    lines = [f"Blocks found: {len(blocks)}", "Sample blocks:"]
    for block in blocks[:20]:
        sample = block["sample"].replace("\n", "\\n")
        lines.append(
            f"  - 0x{block['offset']:06X} len {block['length']} chars {block['char_count']} pairs {block['pair_count']}: {sample!r}"
        )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    blocks = scan_sjis_blocks(buf, args.min_chars, args.min_pairs)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(blocks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summarize(blocks))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
