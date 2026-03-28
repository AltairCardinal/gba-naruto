#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROM_BASE = 0x08000000


def parse_int(value: str) -> int:
    return int(value, 0)


def read_u32_le(buf: bytes, offset: int) -> int:
    return int.from_bytes(buf[offset : offset + 4], "little")


def is_rom_ptr(value: int, rom_size: int) -> bool:
    return ROM_BASE <= value < ROM_BASE + rom_size


def row_kind(buf: bytes, offset: int) -> str:
    values = [read_u32_le(buf, offset + i * 4) for i in range(4)]
    ptrs = [is_rom_ptr(v, len(buf)) for v in values]
    if all(v == 0 for v in values):
        return "zero"
    if all(ptrs):
        return "all_ptrs"
    if any(ptrs):
        return "mixed"
    return "other"


def find_tables(buf: bytes, start: int, end: int, min_rows: int) -> list[dict]:
    results = []
    offset = start
    while offset + 0x10 <= min(end, len(buf)):
        kind = row_kind(buf, offset)
        if kind == "all_ptrs":
            run_start = offset
            rows = 0
            reused_first_col = 0
            prev_first = None
            zero_gap_rows = 0
            while offset + 0x10 <= min(end, len(buf)):
                current_kind = row_kind(buf, offset)
                if current_kind not in {"all_ptrs", "zero"}:
                    break
                if current_kind == "zero":
                    zero_gap_rows += 1
                else:
                    values = [read_u32_le(buf, offset + i * 4) for i in range(4)]
                    if prev_first == values[0]:
                        reused_first_col += 1
                    prev_first = values[0]
                    rows += 1
                offset += 0x10
            if rows >= min_rows:
                results.append(
                    {
                        "start": run_start,
                        "end": offset,
                        "nonzero_rows": rows,
                        "zero_gap_rows": zero_gap_rows,
                        "reused_first_col_pairs": reused_first_col,
                    }
                )
            continue
        offset += 4
    return results


def summarize(results: list[dict]) -> str:
    lines = [f"Candidate tables: {len(results)}", "Top candidates:"]
    ranked = sorted(
        results,
        key=lambda item: (item["nonzero_rows"], item["reused_first_col_pairs"]),
        reverse=True,
    )
    for item in ranked[:20]:
        lines.append(
            f"  - 0x{item['start']:06X}-0x{item['end']:06X} "
            f"rows={item['nonzero_rows']} zero_rows={item['zero_gap_rows']} "
            f"reused_col0={item['reused_first_col_pairs']}"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find 0x10-byte pointer-table candidates in a ROM.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("--start", default="0", help="Start offset")
    parser.add_argument("--end", default=None, help="End offset")
    parser.add_argument("--min-rows", type=int, default=4, help="Minimum nonzero pointer rows")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    start = parse_int(args.start)
    end = parse_int(args.end) if args.end is not None else len(buf)
    results = find_tables(buf, start, end, args.min_rows)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(summarize(results))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
