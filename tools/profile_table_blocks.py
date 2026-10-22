#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from analyze_table import analyze_table, parse_int
from inspect_block import inspect_block


ROM_BASE = 0x08000000


def profile_table_blocks(
    rom_path: Path,
    start: int,
    entry_size: int,
    count: int,
    block_size: int,
    skip_zero_rows: bool,
) -> dict:
    buf = rom_path.read_bytes()
    table = analyze_table(buf, start, entry_size, count)
    rows = []
    column_guesses: dict[int, Counter[str]] = defaultdict(Counter)

    for row in table["rows"]:
        values = [field["value"] for field in row["fields"]]
        if skip_zero_rows and all(value == 0 for value in values):
            continue
        inspected_fields = []
        for col, value in enumerate(values):
            if ROM_BASE <= value < ROM_BASE + len(buf):
                block = inspect_block(buf, value - ROM_BASE, block_size)
                inspected_fields.append(
                    {
                        "column": col,
                        "target_offset": value - ROM_BASE,
                        "guess": block["guess"],
                        "zero_ratio": block["zero_ratio"],
                        "entropy": block["entropy"],
                    }
                )
                column_guesses[col][block["guess"]] += 1
            else:
                inspected_fields.append(
                    {
                        "column": col,
                        "target_offset": None,
                        "guess": "non_pointer",
                        "zero_ratio": None,
                        "entropy": None,
                    }
                )
                column_guesses[col]["non_pointer"] += 1
        rows.append({"index": row["index"], "offset": row["offset"], "fields": inspected_fields})

    return {
        "table_start": start,
        "entry_size": entry_size,
        "rows": rows,
        "column_guess_summary": {str(col): dict(counter) for col, counter in column_guesses.items()},
    }


def summarize(report: dict) -> str:
    lines = []
    lines.append(f"Table start: 0x{report['table_start']:06X}")
    lines.append(f"Entry size: {report['entry_size']}")
    lines.append("Column guess summary:")
    for col, summary in sorted(report["column_guess_summary"].items(), key=lambda item: int(item[0])):
        parts = ", ".join(f"{k}={v}" for k, v in sorted(summary.items()))
        lines.append(f"  - col {col}: {parts}")
    lines.append("Sample rows:")
    for row in report["rows"][:10]:
        parts = []
        for field in row["fields"]:
            if field["target_offset"] is None:
                parts.append(f"c{field['column']}=non_pointer")
            else:
                parts.append(
                    f"c{field['column']}=0x{field['target_offset']:06X}:{field['guess']}"
                )
        lines.append(f"  - row {row['index']} @ 0x{row['offset']:06X}: " + ", ".join(parts))
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect each pointer field in a fixed-size table.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("start", help="Start offset in ROM")
    parser.add_argument("entry_size", type=parse_int, help="Entry size in bytes")
    parser.add_argument("count", type=parse_int, help="Number of rows to inspect")
    parser.add_argument("--block-size", type=parse_int, default=0x40, help="Bytes inspected per pointed block")
    parser.add_argument("--include-zero-rows", action="store_true", help="Keep all-zero rows in row output")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = profile_table_blocks(
        args.rom,
        parse_int(args.start),
        args.entry_size,
        args.count,
        args.block_size,
        skip_zero_rows=not args.include_zero_rows,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(summarize(report))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
