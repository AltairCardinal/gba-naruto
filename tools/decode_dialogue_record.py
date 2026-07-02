#!/usr/bin/env python3
"""
decode_dialogue_record.py — Decode dialogue records from chapter 1 intro
at IWRAM 0x78 LE-interpreted offsets (0x8DF0..0xB8EB).

Each record (~374-383 bytes) contains multiple dialogue segments separated by
SJIS byte pair 0x8B62 (newline). Inside each segment are SJIS byte pairs
encoding Chinese characters + control bytes (0x01, 0x02, 0x0A, 0x1F, etc.)
and templates.

Usage:
  python3 tools/decode_dialogue_record.py <state_index>
  # or
  python3 tools/decode_dialogue_record.py <hex_offset>

Output: JSON with decoded segments using sjis-to-tile-mapping.json (currently 20 chars),
unknown byte pairs flagged for manual investigation.
"""

import sys
import json
import re
from pathlib import Path

# Load existing mapping
SCRIPT_DIR = Path(__file__).parent
MAP_PATH = SCRIPT_DIR.parent / "sequel" / "content" / "text" / "sjis-to-tile-mapping.json"
DIALOGUE_MAPPING = SCRIPT_DIR.parent / "sequel" / "analysis" / "mapping-extension-20260701" / "dialogue_pointer_mapping.json"

# LE-interpreted pointers (corrected from the BE bug in BREAKTHROUGH commit 473a737)
CORRECT_PTRS = [
    0x8DF0, 0x8F6F, 0x90E5, 0x9261, 0x93DD, 0x955A, 0x96D6, 0x9850, 0x99CB, 0x9B47,
    0x9CC4, 0x9E41, 0x9FC0, 0xA13E, 0xA2B6, 0xA42E, 0xA5AB, 0xA728, 0xA8A0, 0xAA1E,
    0xAB9E, 0xAD17, 0xAE8F, 0xB006, 0xB180, 0xB2FE, 0xB476, 0xB5F3, 0xB76F, 0xB8EB,
]

ROM_PATH = SCRIPT_DIR.parent / "build" / "naruto-sequel-dev.gba"


def load_mapping():
    with open(MAP_PATH) as f:
        raw = json.load(f)
    out = {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        # Map is keyed by SJIS bytes (hex) → Chinese char (or special)
        if isinstance(k, str) and len(k) == 4:
            try:
                bytes_seq = bytes.fromhex(k)
                out[bytes_seq] = v
            except ValueError:
                pass
    return out


def load_dialogue_mapping():
    with open(DIALOGUE_MAPPING) as f:
        data = json.load(f)
    # Index by state_index
    return {r["state"]: r for r in data}


def decode_record(record_bytes, mapping):
    """Decode a record into segments, applying the SJIS mapping."""
    segments = []
    cur_seg_bytes = []
    i = 0
    while i < len(record_bytes):
        b = record_bytes[i]
        if i + 1 < len(record_bytes) and b == 0x8B and record_bytes[i + 1] == 0x62:
            # newline delimiter
            segments.append(cur_seg_bytes)
            cur_seg_bytes = []
            i += 2
        else:
            cur_seg_bytes.append(b)
            i += 1
    if cur_seg_bytes:
        segments.append(cur_seg_bytes)

    # Now decode each segment
    decoded_segments = []
    unknown_pairs = set()
    for seg in segments:
        i = 0
        decoded = []
        while i < len(seg) - 1:
            bp = bytes([seg[i], seg[i + 1]])
            if bp in mapping:
                val = mapping[bp]
                if isinstance(val, str) and val.startswith("\\n"):
                    decoded.append("\n")
                else:
                    decoded.append(val)
                i += 2
            elif 0x81 <= seg[i] <= 0xFC and 0x40 <= seg[i + 1] <= 0xFC:
                # Possible SJIS pair but unknown mapping
                decoded.append(f"[{bp.hex().upper()}]")
                unknown_pairs.add(bp)
                i += 2
            else:
                decoded.append(f"({seg[i]:02X})")
                i += 1
        # Handle trailing single byte
        if i < len(seg):
            decoded.append(f"(tail:{seg[i]:02X})")
        decoded_segments.append("".join(decoded))

    return decoded_segments, sorted(unknown_pairs)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print()
        print("Available states: 0-29")
        sys.exit(1)

    arg = sys.argv[1]
    if arg.startswith("0x") or arg.startswith("0X"):
        offset = int(arg, 16)
        ptr_idx = None
    else:
        idx = int(arg)
        if idx < 0 or idx >= len(CORRECT_PTRS):
            print(f"State {idx} out of range")
            sys.exit(1)
        offset = CORRECT_PTRS[idx]
        ptr_idx = idx

    # Load ROM
    with open(ROM_PATH, "rb") as f:
        rom = f.read()

    if offset >= len(rom):
        print(f"Offset 0x{offset:X} exceeds ROM size")
        sys.exit(1)

    # Get record (next record is at pointer + record_size; record size varies slightly)
    # Just read 384 bytes for now
    record = rom[offset : offset + 384]

    # Find next pointer in CORRECT_PTRS
    next_ptr = None
    for p in CORRECT_PTRS:
        if p > offset:
            next_ptr = p
            break
    if next_ptr is None:
        next_ptr = offset + 384
    record_size = next_ptr - offset
    record = rom[offset : offset + record_size]

    # Load mappings
    mapping = load_mapping()
    dialogue = load_dialogue_mapping()

    # Print
    if ptr_idx is not None:
        meta = dialogue.get(ptr_idx, {})
        print(f"State {ptr_idx} @ offset 0x{offset:X}, size {record_size} bytes")
        print(f"OCR: {meta.get('ocr', '?')}")
    else:
        print(f"@ offset 0x{offset:X}, size {record_size} bytes")
    print()

    segments, unknowns = decode_record(record, mapping)

    print(f"Decoded segments ({len(segments)}):")
    for i, seg in enumerate(segments):
        print(f"  seg {i:>2}: {seg}")
    print()

    if unknowns:
        print(f"Unknown byte pairs ({len(unknowns)}):")
        for bp in unknowns:
            print(f"  {bp.hex().upper()}")


if __name__ == "__main__":
    main()
