#!/usr/bin/env python3
"""Decode a dialogue record with the game's own font codes.

History
-------
This tool used to decode "chapter 1 intro" dialogue records with a hand-made
20-character table (``sequel/content/text/sjis-to-tile-mapping.json``) whose
values were double-encoded mojibake, and it split records on the byte pair
0x8B62.  Both are wrong on this ROM:

* the ROM's text is a custom double-byte *font code* (lead byte 0x80..0x9F),
  not Shift-JIS - see notes/font-encoding.md;
* 0x8B62 is the font code for the character U+7684 ("的"), not a delimiter.
  Splitting on it chopped sentences in the middle of a word.

The hand-made table is retired; this tool now goes through
``tools/text_codec.py``, the single sanctioned codec entry point.

What it does now
----------------
Given a byte range (a record captured in RAM, or a stretch of the ROM), split
it into the game's control codes / text tokens and render the text with the
ROM's own font.  Control codes are reported, not silently dropped, because
they carry layout meaning.

The 30 "state" offsets below are IWRAM addresses from an old RAM-dump
analysis, *not* ROM file offsets - reading them out of the ROM file yields
arbitrary bytes (mostly zeroes and stray font codes), not dialogue.  They
are kept so an old RAM capture can still be decoded with the same state
indexes, and the tool says so when it is used that way.

Usage:
    python tools/decode_dialogue_record.py 0x8DF0 --file ram-dump.bin
    python tools/decode_dialogue_record.py 0 --file ram-dump.bin
    python tools/decode_dialogue_record.py 0x459414 --rom rom/base.gba
    python tools/decode_dialogue_record.py 0x459414 --rom rom/base.gba --length 41
"""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import konoha_font as kf  # noqa: E402
import text_codec as tc  # noqa: E402

# LE-interpreted IWRAM pointers (corrected from the BE bug in BREAKTHROUGH
# commit 473a737).  These are RAM addresses of a captured chapter-1 intro
# state table - they are NOT ROM file offsets.
CORRECT_PTRS = [
    0x8DF0, 0x8F6F, 0x90E5, 0x9261, 0x93DD, 0x955A, 0x96D6, 0x9850, 0x99CB, 0x9B47,
    0x9CC4, 0x9E41, 0x9FC0, 0xA13E, 0xA2B6, 0xA42E, 0xA5AB, 0xA728, 0xA8A0, 0xAA1E,
    0xAB9E, 0xAD17, 0xAE8F, 0xB006, 0xB180, 0xB2FE, 0xB476, 0xB5F3, 0xB76F, 0xB8EB,
]

DEFAULT_RECORD_LENGTH = 384


def decode_record(record: bytes, mapping: dict[int, str]) -> tuple[list[dict], list[int]]:
    """Decode a record into segments.

    A segment is a run of text between control codes.  Returns the segments
    and the list of unknown font codes that were hit (so a caller can report
    characters the ROM's font cannot draw).
    """
    tokens = kf.scan_tokens(record, 0)
    segments: list[dict] = []
    current: list[str] = []
    unknown: list[int] = []
    for kind, value in tokens:
        if kind == "ctrl":
            segments.append({
                "text": "".join(current),
                "control": value.hex().upper(),
            })
            current = []
            continue
        code = value
        if code == 10:
            current.append("\n")
        elif 32 <= code < 127:
            current.append(chr(code))
        elif code == 0x8140:
            current.append("　")
        else:
            char = mapping.get(code)
            if char is None:
                unknown.append(code)
                current.append(f"{{字{code:04X}}}")
            else:
                current.append(char)
    if current:
        segments.append({"text": "".join(current), "control": None})
    return segments, sorted(set(unknown))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode a dialogue record with the game's font codes.")
    parser.add_argument("offset", help="offset: hex (0x1234) or a state index 0-29")
    parser.add_argument("--file", type=pathlib.Path, default=None,
                        help="read the record from this file (e.g. a RAM dump)")
    parser.add_argument("--rom", type=pathlib.Path, default=None,
                        help="read the record from the ROM (default: rom/base.gba)")
    parser.add_argument("--length", type=int, default=DEFAULT_RECORD_LENGTH,
                        help="record length in bytes")
    parser.add_argument("--json", type=pathlib.Path, default=None,
                        help="write the decoded record as JSON here")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    state_index = None
    if args.offset.lower().startswith("0x"):
        offset = int(args.offset, 16)
    else:
        state_index = int(args.offset)
        if not 0 <= state_index < len(CORRECT_PTRS):
            print(f"State {state_index} out of range (0..{len(CORRECT_PTRS) - 1})",
                  file=sys.stderr)
            return 2
        offset = CORRECT_PTRS[state_index]

    if args.file is not None:
        blob = args.file.read_bytes()
        source = str(args.file)
        is_ram = True
    else:
        rom_path = tc.resolve_rom(args.rom)
        blob = rom_path.read_bytes()
        source = str(rom_path)
        is_ram = False

    if offset >= len(blob):
        print(f"Offset 0x{offset:X} exceeds the size of {source}", file=sys.stderr)
        return 2

    length = args.length
    if state_index is not None and is_ram:
        nxt = next((p for p in CORRECT_PTRS if p > offset), None)
        if nxt is not None:
            length = nxt - offset
    record = blob[offset:offset + length]

    mapping, report = tc.load_mapping(args.rom)
    segments, unknown = decode_record(record, mapping)

    print(f"source   : {source}")
    if state_index is not None:
        print(f"state {state_index} @ IWRAM 0x{offset:04X}, {len(record)} bytes")
        if is_ram:
            print("           (IWRAM state pointer from the captured chapter-1 intro table)")
        else:
            print("           WARNING: this is an IWRAM address, not a ROM file offset;")
            print("           reading it from the ROM yields arbitrary bytes.")
    else:
        print(f"offset   : 0x{offset:X}, {len(record)} bytes")
    print(f"mapping  : {len(mapping)} font codes, "
          f"{report['catalog_segments_matched']}/"
          f"{report['catalog_segments_total']} segments fingerprint-matched")
    print()

    print(f"Decoded segments ({len(segments)}):")
    for index, seg in enumerate(segments):
        text = seg["text"].replace("\n", "\\n")
        ctrl = f"  [ctrl {seg['control']}]" if seg["control"] else ""
        print(f"  seg {index:>2}: {text!r}{ctrl}")

    if unknown:
        print(f"\nUnknown font codes ({len(unknown)}):")
        for code in unknown:
            print(f"  0x{code:04X}")

    if args.json is not None:
        import json
        from tools.lib.io import write_text
        payload = {
            "source": source,
            "offset": offset,
            "length": len(record),
            "state_index": state_index,
            "segments": segments,
            "unknown_codes": ["0x%04X" % c for c in unknown],
        }
        write_text(args.json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"\nJSON report written to: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
