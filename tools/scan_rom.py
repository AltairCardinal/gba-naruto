#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.lib import read_u32_le


def scan_gba_pointers(buf: bytes, min_hits_per_target: int) -> dict:
    aligned_offsets: list[int] = []
    targets: Counter[int] = Counter()

    for offset in range(0, len(buf) - 3, 4):
        value = read_u32_le(buf, offset)
        if ROM_BASE <= value < ROM_BASE + len(buf):
            aligned_offsets.append(offset)
            targets[value - ROM_BASE] += 1

    hot_targets = [
        {"target_offset": target, "hits": hits}
        for target, hits in targets.most_common()
        if hits >= min_hits_per_target
    ]

    return {
        "aligned_pointer_count": len(aligned_offsets),
        "unique_targets": len(targets),
        "sample_pointer_offsets": aligned_offsets[:128],
        "hot_targets": hot_targets[:128],
    }


def is_probably_ascii_text(byte_value: int) -> bool:
    return byte_value in PRINTABLE_ASCII or byte_value in CONTROL_BYTES


def scan_ascii_runs(buf: bytes, min_len: int) -> list[dict]:
    runs: list[dict] = []
    start: int | None = None

    for i, byte_value in enumerate(buf):
        if is_probably_ascii_text(byte_value):
            if start is None:
                start = i
        else:
            if start is not None:
                length = i - start
                if length >= min_len:
                    sample = buf[start:i][:64].decode("ascii", errors="replace")
                    runs.append(
                        {
                            "offset": start,
                            "length": length,
                            "sample": sample,
                        }
                    )
                start = None

    if start is not None:
        length = len(buf) - start
        if length >= min_len:
            sample = buf[start:][:64].decode("ascii", errors="replace")
            runs.append(
                {
                    "offset": start,
                    "length": length,
                    "sample": sample,
                }
            )

    return runs


def scan_zero_runs(buf: bytes, min_len: int) -> list[dict]:
    runs: list[dict] = []
    start: int | None = None

    for i, byte_value in enumerate(buf):
        if byte_value == 0:
            if start is None:
                start = i
        else:
            if start is not None:
                length = i - start
                if length >= min_len:
                    runs.append({"offset": start, "length": length})
                start = None

    if start is not None:
        length = len(buf) - start
        if length >= min_len:
            runs.append({"offset": start, "length": length})

    return runs


def scan_byte_frequency(buf: bytes) -> dict:
    counts = Counter(buf)
    top = [{"byte": byte_value, "count": count} for byte_value, count in counts.most_common(16)]
    return {"top_bytes": top}


def build_report(buf: bytes, args: argparse.Namespace) -> dict:
    return {
        "rom_size": len(buf),
        "rom_size_hex": hex(len(buf)),
        "pointer_scan": scan_gba_pointers(buf, args.min_pointer_hits),
        "ascii_runs": scan_ascii_runs(buf, args.min_ascii_run)[:256],
        "zero_runs": scan_zero_runs(buf, args.min_zero_run)[:256],
        "byte_frequency": scan_byte_frequency(buf),
    }


def write_report(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_summary(report: dict) -> str:
    lines = []
    lines.append(f"ROM size: {report['rom_size']} bytes ({report['rom_size_hex']})")
    pointer_scan = report["pointer_scan"]
    lines.append(
        "Aligned in-ROM pointers: "
        f"{pointer_scan['aligned_pointer_count']} "
        f"across {pointer_scan['unique_targets']} unique targets"
    )
    lines.append(f"ASCII-like runs found: {len(report['ascii_runs'])}")
    lines.append(f"Zero runs found: {len(report['zero_runs'])}")

    if pointer_scan["hot_targets"]:
        lines.append("Top pointer targets:")
        for item in pointer_scan["hot_targets"][:10]:
            lines.append(
                f"  - target 0x{item['target_offset']:06X} hit {item['hits']} times"
            )

    if report["ascii_runs"]:
        lines.append("Sample ASCII-like runs:")
        for item in report["ascii_runs"][:10]:
            lines.append(
                f"  - 0x{item['offset']:06X} len {item['length']}: {item['sample']!r}"
            )

    if report["zero_runs"]:
        lines.append("Largest zero runs:")
        for item in sorted(report["zero_runs"], key=lambda x: x["length"], reverse=True)[:10]:
            lines.append(f"  - 0x{item['offset']:06X} len {item['length']}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a GBA ROM for preliminary reverse-engineering clues.")
    parser.add_argument("rom", type=Path, help="Path to the ROM file")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/scan-report.json"),
        help="Path to the JSON report",
    )
    parser.add_argument("--min-ascii-run", type=int, default=8, help="Minimum ASCII-like run length")
    parser.add_argument("--min-zero-run", type=int, default=32, help="Minimum zero-filled run length")
    parser.add_argument("--min-pointer-hits", type=int, default=4, help="Minimum hits for a hot pointer target")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    buf = args.rom.read_bytes()
    report = build_report(buf, args)
    write_report(report, args.output)
    print(render_summary(report))
    print(f"\nJSON report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
