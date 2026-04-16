#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lib import parse_int, read_u32_le


def read_u16_le(buf: bytes, offset: int) -> int:
    return int.from_bytes(buf[offset : offset + 2], "little")


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


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


def palette_score(data: bytes) -> dict:
    halfwords = len(data) // 2
    if halfwords == 0:
        return {"palette_like_ratio": 0.0, "nonzero_halfwords": 0}
    values = [read_u16_le(data, i * 2) for i in range(halfwords)]
    palette_like = sum(1 for value in values if value <= 0x7FFF)
    nonzero = sum(1 for value in values if value != 0)
    return {
        "palette_like_ratio": palette_like / halfwords,
        "nonzero_halfwords": nonzero,
        "first_u16": values[:32],
    }


def pointer_prefix(buf: bytes, start: int, max_words: int) -> list[dict]:
    items = []
    for i in range(max_words):
        offset = start + i * 4
        if offset + 4 > len(buf):
            break
        value = read_u32_le(buf, offset)
        kind = classify_u32(value, len(buf))
        items.append(
            {
                "index": i,
                "offset": offset,
                "value": value,
                "kind": kind,
            }
        )
    return items


def guess_kind(data: bytes, ptr_prefix: list[dict], palette: dict) -> str:
    leading_ptrs = 0
    for item in ptr_prefix:
        if item["kind"] == "rom_ptr":
            leading_ptrs += 1
        else:
            break

    if leading_ptrs >= 3:
        return "nested_descriptor"
    if palette["palette_like_ratio"] >= 0.95 and palette["nonzero_halfwords"] >= 8:
        return "palette_like"
    if data.count(0) / len(data) >= 0.7:
        return "sparse_binary"
    return "binary_or_compressed"


def inspect_block(buf: bytes, start: int, size: int) -> dict:
    data = buf[start : start + size]
    ptr_prefix = pointer_prefix(buf, start, min(16, size // 4))
    palette = palette_score(data[:64])
    report = {
        "start": start,
        "size": len(data),
        "entropy": round(shannon_entropy(data), 4),
        "zero_ratio": round(data.count(0) / len(data), 4) if data else 0.0,
        "u32_prefix": ptr_prefix,
        "palette_probe": palette,
        "guess": guess_kind(data, ptr_prefix, palette),
        "head_hex": data[:64].hex(),
    }
    return report


def summarize(report: dict) -> str:
    lines = []
    lines.append(f"Start: 0x{report['start']:06X}")
    lines.append(f"Size inspected: {report['size']} bytes")
    lines.append(f"Entropy: {report['entropy']}")
    lines.append(f"Zero ratio: {report['zero_ratio']}")
    lines.append(f"Guess: {report['guess']}")
    lines.append(
        "Palette probe: "
        f"ratio={report['palette_probe']['palette_like_ratio']:.3f}, "
        f"nonzero_halfwords={report['palette_probe']['nonzero_halfwords']}"
    )
    lines.append("u32 prefix:")
    for item in report["u32_prefix"][:8]:
        value = item["value"]
        if item["kind"] == "rom_ptr":
            rendered = f"0x{value:08X}->0x{value - ROM_BASE:06X}"
        else:
            rendered = f"0x{value:08X}"
        lines.append(f"  - +0x{item['index'] * 4:02X}: {rendered} {item['kind']}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a ROM block and classify its shape.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("start", help="Start offset in ROM")
    parser.add_argument("size", type=parse_int, help="Bytes to inspect")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    report = inspect_block(buf, parse_int(args.start), args.size)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(summarize(report))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
