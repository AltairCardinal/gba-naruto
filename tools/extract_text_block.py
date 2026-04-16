#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


from tools.lib import parse_int


def clean_segment(data: bytes) -> bytes:
    while data and data[0] in {0x00, 0x0A, 0x0D, 0x20}:
        data = data[1:]
    while data and data[-1] in {0x00, 0x0A, 0x0D, 0x20}:
        data = data[:-1]
    return data


def split_block(data: bytes) -> list[bytes]:
    parts: list[bytes] = []
    current = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0x00:
            if current:
                parts.append(bytes(current))
                current.clear()
            i += 1
            continue
        if b in {0x0A, 0x0D}:
            current.append(0x0A)
            i += 1
            continue
        current.append(b)
        i += 1
    if current:
        parts.append(bytes(current))
    return [clean_segment(part) for part in parts if clean_segment(part)]


def render_text(data: bytes) -> str:
    return data.decode("shift_jis", errors="replace")


def extract_block(buf: bytes, start: int, size: int) -> dict:
    raw = buf[start : start + size]
    segments = []
    for index, part in enumerate(split_block(raw)):
        segments.append(
            {
                "index": index,
                "length": len(part),
                "hex": part.hex(),
                "text": render_text(part),
            }
        )
    return {
        "start": start,
        "size": size,
        "segment_count": len(segments),
        "segments": segments,
    }


def summarize(report: dict) -> str:
    lines = [
        f"Start: 0x{report['start']:06X}",
        f"Size: {report['size']}",
        f"Segments: {report['segment_count']}",
        "Sample segments:",
    ]
    for seg in report["segments"][:20]:
        text = seg["text"].replace("\n", "\\n")
        lines.append(f"  - [{seg['index']}] len {seg['length']}: {text!r}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split a suspected text block into candidate strings.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument("start", help="Start offset in ROM")
    parser.add_argument("size", type=parse_int, help="Bytes to inspect")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    report = extract_block(buf, parse_int(args.start), args.size)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summarize(report))
    if args.output is not None:
        print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
