#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lib import parse_int, read_u32_le


def classify_u32(value: int, rom_size: int) -> str:
    if ROM_BASE <= value < ROM_BASE + rom_size:
        return "rom_ptr"
    if value == 0:
        return "zero"
    if value < 0x100:
        return "small"
    if value < 0x10000:
        return "u16ish"
    return "raw32"


def analyze_table(buf: bytes, start: int, entry_size: int, count: int) -> dict:
    rows = []
    column_count = entry_size // 4
    column_stats = [Counter() for _ in range(column_count)]

    for row_index in range(count):
        row_offset = start + row_index * entry_size
        if row_offset + entry_size > len(buf):
            break
        entry = buf[row_offset : row_offset + entry_size]
        fields = []
        for col in range(column_count):
            value = read_u32_le(entry, col * 4)
            kind = classify_u32(value, len(buf))
            fields.append({"value": value, "kind": kind})
            column_stats[col][kind] += 1
        rows.append({"index": row_index, "offset": row_offset, "fields": fields})

    summary = []
    for index, stats in enumerate(column_stats):
        summary.append(
            {
                "column": index,
                "counts": dict(stats),
            }
        )

    return {
        "start": start,
        "entry_size": entry_size,
        "row_count": len(rows),
        "column_count": column_count,
        "column_summary": summary,
        "rows": rows,
    }


def format_value(value: int, kind: str) -> str:
    if kind == "rom_ptr":
        return f"0x{value:08X}->0x{value - ROM_BASE:06X}"
    return f"0x{value:08X}"


def summarize(report: dict, max_rows: int) -> str:
    lines = []
    lines.append(f"Start: 0x{report['start']:06X}")
    lines.append(f"Entry size: {report['entry_size']} bytes")
    lines.append(f"Rows analyzed: {report['row_count']}")
    lines.append(f"Columns: {report['column_count']}")
    lines.append("Column summary:")
    for column in report["column_summary"]:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(column["counts"].items()))
        lines.append(f"  - col {column['column']}: {parts}")

    lines.append("Sample rows:")
    for row in report["rows"][:max_rows]:
        rendered_fields = []
        for idx, field in enumerate(row["fields"]):
            rendered_fields.append(f"c{idx}={format_value(field['value'], field['kind'])}")
        lines.append(f"  - row {row['index']} @ 0x{row['offset']:06X}: " + ", ".join(rendered_fields))

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a ROM region as a fixed-size table.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("start", help="Start offset in ROM")
    parser.add_argument("entry_size", type=parse_int, help="Entry size in bytes")
    parser.add_argument("count", type=parse_int, help="Number of rows to inspect")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    parser.add_argument("--max-rows", type=int, default=12, help="Rows to print in summary")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    report = analyze_table(buf, parse_int(args.start), args.entry_size, args.count)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(summarize(report, args.max_rows))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
