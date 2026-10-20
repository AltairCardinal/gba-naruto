#!/usr/bin/env python3
"""Migrate the dialogue bank and content files from cp932 to the font codes.

Why this exists
---------------
`sequel/content/text/dialogue-bank.json` declared every entry as
``"encoding": "cp932"`` and `sequel/content/text/dialogue-patches.json` stored
its text as **mojibake**: the ROM's font-code bytes decoded as cp932.  That
trick is byte-preserving (encode the mojibake with cp932 and you get the
original bytes back) but it has two fatal properties:

  1. New content cannot be written.  Any Chinese text is encoded as
     Shift-JIS, and the game then draws whatever font codes those bytes
     happen to collide with - in practice unreadable.
  2. Nothing in the pipeline ever checked what the player would *see*.
     The existing patches proved the bytes landed, not that they render.

This tool rewrites the bank to ``"encoding": "font"`` and replaces the mojibake
notes with the real Chinese the ROM actually contains.  It also rewrites the
content file's text fields with the ROM's own text, so the migrated pipeline
can be checked for byte-identical output.

Usage
-----
    python tools/migrate_text_bank_to_font.py              # dry run
    python tools/migrate_text_bank_to_font.py --apply
    python tools/migrate_text_bank_to_font.py --apply --content-only
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import konoha_font as kf  # noqa: E402
from tools import text_codec  # noqa: E402

BANK = REPO / "sequel" / "content" / "text" / "dialogue-bank.json"
CONTENT = REPO / "sequel" / "content" / "text" / "dialogue-patches.json"

DECODED_PREFIX = "Decoded: "


def rom_text(rom: bytes, mapping: dict[int, str], offset: int, max_bytes: int) -> tuple[str, int]:
    """Return (text, control-code count) for the text run at `offset`.

    The text is truncated at the slot's byte budget, so an entry that points
    at the start of a long run (like the title-screen menu list) only reports
    the characters that actually fit in its slot.
    """
    return text_codec.decode_bounded(rom, offset, max_bytes, mapping)


def rewrite_notes(notes: str, text: str, n_ctrl: int) -> str:
    """Replace a stale "Decoded: ..." tail with the real decoded text."""
    base = notes.split(DECODED_PREFIX)[0].rstrip()
    tail = f"{DECODED_PREFIX}{text}"
    if n_ctrl:
        tail += f" [{n_ctrl} control code(s)]"
    return f"{base} {tail}" if base else tail


def migrate_bank(rom: bytes, mapping: dict[int, str], apply: bool) -> list[dict]:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    report = []
    for entry in bank["entries"]:
        offset = int(entry["offset"])
        max_bytes = int(entry["max_bytes"])
        actual = rom[offset:offset + max_bytes].hex()
        text, n_ctrl = rom_text(rom, mapping, offset, max_bytes)
        expected_ok = entry.get("expected_hex", "").lower() == actual
        report.append({
            "id": entry["id"],
            "offset": hex(offset),
            "expected_hex_matches_rom": expected_ok,
            "old_encoding": entry.get("encoding"),
            "decoded": text,
            "control_codes": n_ctrl,
        })
        if apply:
            entry["encoding"] = text_codec.FONT_ENCODING
            entry["notes"] = rewrite_notes(entry.get("notes", ""), text, n_ctrl)
    if apply:
        from tools.lib.io import write_text as write_text_lf
        write_text_lf(
            BANK, json.dumps(bank, ensure_ascii=False, indent=2) + "\n"
        )
    return report


def migrate_content(rom: bytes, mapping: dict[int, str], apply: bool) -> list[dict]:
    """Replace the mojibake content text with the ROM's real text."""
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    bank_map = {e["id"]: e for e in bank["entries"]}
    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    report = []
    for entry in content["entries"]:
        bank_entry = bank_map.get(entry["id"])
        if bank_entry is None:
            continue
        offset = int(bank_entry["offset"])
        max_bytes = int(bank_entry["max_bytes"])
        text, _ = rom_text(rom, mapping, offset, max_bytes)
        old = entry.get("text", "")
        rec = {
            "id": entry["id"],
            "old_text": old,
            "rom_text": text,
            "max_bytes": max_bytes,
        }
        # Can the ROM text be written back verbatim in the font encoding?
        try:
            encoded = text_codec.encode(text, text_codec.FONT_ENCODING, mapping)
            rec["rom_text_encoded_len"] = len(encoded)
            rec["fits_max_bytes"] = len(encoded) <= max_bytes
            rec["bytes_match_rom"] = (
                encoded == rom[offset:offset + len(encoded)]
            )
        except KeyError as exc:
            rec["encode_error"] = str(exc)
        report.append(rec)
        if apply:
            entry["text"] = text
            entry["notes"] = rewrite_notes(entry.get("notes", ""), text, 0)
    if apply:
        from tools.lib.io import write_text as write_text_lf
        write_text_lf(
            CONTENT, json.dumps(content, ensure_ascii=False, indent=2) + "\n"
        )
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--bank-only", action="store_true",
                    help="only migrate dialogue-bank.json")
    ap.add_argument("--content-only", action="store_true",
                    help="only migrate dialogue-patches.json")
    ap.add_argument("--rom", default=None)
    ap.add_argument("--out", default=None, help="write the JSON report here")
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    mapping, report_meta = text_codec.load_mapping(rom_path)

    result = {
        "rom": str(rom_path),
        "mapping_codes": len(mapping),
        "catalog_segments_matched": report_meta["catalog_segments_matched"],
    }
    if not args.content_only:
        result["bank"] = migrate_bank(rom, mapping, args.apply)
    if not args.bank_only:
        result["content"] = migrate_content(rom, mapping, args.apply)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
