#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.lib import load_json


def find_free_space(data: bytes, size: int, start: int = 0) -> int:
    """Find a zero-filled region of at least `size` bytes."""
    needed = size
    run_start = -1
    for i in range(start, len(data)):
        if data[i] == 0:
            if run_start < 0:
                run_start = i
            if i - run_start + 1 >= needed:
                return run_start
        else:
            run_start = -1
    raise ValueError(f"no free space of {size} bytes found after offset 0x{start:X}")


def build_pointer_redirect(
    table_offset: int, old_text_offset: int, new_text_offset: int
) -> dict:
    """Build a pointer_redirect patch for a dialogue pointer table entry."""
    old_ptr = ROM_BASE + old_text_offset
    new_ptr = ROM_BASE + new_text_offset
    return {
        "type": "pointer_redirect",
        "pointer_table_offset": table_offset,
        "expected_pointer_hex": struct.pack("<I", old_ptr).hex(),
        "new_pointer_hex": struct.pack("<I", new_ptr).hex(),
    }


FREE_SPACE_START = 0x5DFBEC  # first 0xFF-filled byte after all game data (128 KB free)
FREE_SPACE_END   = 0x5FFFFF  # last byte of ROM


def import_dialogue_variable(
    bank_path: Path,
    content_path: Path,
    free_space_start: int = FREE_SPACE_START,
) -> list[dict]:
    """Generate patches for variable-length dialogue entries.

    For each dialogue content entry:
    1. Encode text in the target encoding
    2. If length matches existing slot, generate a bytes patch (in-place)
    3. If length differs, generate:
       - a bytes patch to write new text into free space
       - a pointer_redirect patch to update the pointer table
    """
    bank = load_json(bank_path)
    content = load_json(content_path)
    bank_map = {entry["id"]: entry for entry in bank["entries"]}

    patches = []
    text_cursor = free_space_start

    for entry in content["entries"]:
        entry_id = entry["id"]
        if entry_id not in bank_map:
            raise ValueError(f"dialogue entry {entry_id} missing from bank")

        bank_entry = bank_map[entry_id]
        encoding = bank_entry.get("encoding", "cp932")
        text = entry["text"]
        encoded = text.encode(encoding)
        max_bytes = int(bank_entry["max_bytes"])

        text_offset = int(bank_entry["offset"])
        table_offset = int(bank_entry.get("table_offset", 0))
        old_text_offset = int(bank_entry.get("text_rom_offset", text_offset))

        if len(encoded) <= max_bytes:
            # Same-length or shorter: patch in place
            # Pad with null if shorter
            padded = encoded + b"\x00" * (max_bytes - len(encoded))
            patches.append(
                {
                    "id": f"dialogue.{entry_id}",
                    "type": "bytes",
                    "offset": text_offset,
                    "before_hex": bank_entry["expected_hex"],
                    "after_hex": padded.hex(),
                    "encoding": encoding,
                    "text": text,
                    "max_bytes": max_bytes,
                    "source_entry": entry_id,
                    "method": "in_place",
                }
            )
        else:
            # Longer than existing slot: write to free space + redirect pointer
            if not table_offset:
                raise ValueError(
                    f"dialogue entry {entry_id} needs variable-length import "
                    f"but has no table_offset in bank"
                )

            # Align to 4 bytes
            text_cursor = (text_cursor + 3) & ~3

            after_bytes = encoded + b"\x00"
            patches.append(
                {
                    "id": f"dialogue.{entry_id}.write_text",
                    "type": "bytes",
                    "offset": text_cursor,
                    "before_hex": "ff" * len(after_bytes),  # free space is 0xFF-filled
                    "after_hex": after_bytes.hex(),
                    "encoding": encoding,
                    "text": text,
                    "source_entry": entry_id,
                    "method": "free_space_write",
                }
            )

            old_ptr = ROM_BASE + old_text_offset
            new_ptr = ROM_BASE + text_cursor
            patches.append(
                {
                    "id": f"dialogue.{entry_id}.redirect_ptr",
                    "type": "pointer_redirect",
                    "pointer_table_offset": table_offset,
                    "expected_pointer_hex": struct.pack("<I", old_ptr).hex(),
                    "new_pointer_hex": struct.pack("<I", new_ptr).hex(),
                    "source_entry": entry_id,
                }
            )

            text_cursor += len(encoded) + 1  # +1 for null terminator

    return patches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert high-level dialogue content into ROM patch entries (supports variable length)."
    )
    parser.add_argument("--bank", default="sequel/content/text/dialogue-bank.json")
    parser.add_argument(
        "--content", default="sequel/content/text/dialogue-patches.json"
    )
    parser.add_argument(
        "--free-space-start",
        default=hex(FREE_SPACE_START),
        help="Start offset for free space in ROM (hex)",
    )
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    free_start = int(args.free_space_start, 0)
    patches = import_dialogue_variable(
        ROOT / args.bank, ROOT / args.content, free_start
    )
    text = json.dumps({"patches": patches}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        (ROOT / args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
