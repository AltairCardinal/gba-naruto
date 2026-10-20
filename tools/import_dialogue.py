#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.lib import load_json
from tools import text_codec


def build_patch(
    bank_entry: dict,
    content_entry: dict,
    mapping: dict[int, str] | None = None,
) -> list[dict]:
    # "font" is the game's own double-byte font code.  It is the only encoding
    # whose bytes the game can render as the authored characters - see
    # notes/font-encoding.md.  Legacy cp932 entries still build, but
    # text_codec.encode() warns about them.
    encoding = bank_entry.get("encoding", text_codec.FONT_ENCODING)
    text = content_entry["text"]
    encoded = text_codec.encode(text, encoding, mapping)
    max_bytes = int(bank_entry["max_bytes"])

    if len(encoded) <= max_bytes:
        after_hex = encoded + b"\x00" * (max_bytes - len(encoded))
        return [{
            "id": f"dialogue.{content_entry['id']}",
            "type": "dialogue",
            "offset": int(bank_entry["offset"]),
            "before_hex": bank_entry["expected_hex"],
            "after_hex": after_hex.hex(),
            "encoding": encoding,
            "text": text,
            "max_bytes": max_bytes,
            "source_entry": content_entry["id"],
            "strategy": "same_length",
        }]

    ptr_offset = int(bank_entry["table_offset"])
    orig_ptr_hex = int(bank_entry["text_rom_offset"]).to_bytes(4, "little").hex()
    redirect_offset = int(bank_entry.get("redirect_offset", 0))
    if redirect_offset == 0:
        raise ValueError(
            f"dialogue entry {content_entry['id']} requires variable-length redirect "
            f"but bank entry has no redirect_offset. Add redirect_offset to bank entry."
        )

    new_text_bytes = encoded + b"\x00"
    new_ptr = (0x08000000 + redirect_offset).to_bytes(4, "little").hex()
    new_text_hex = new_text_bytes.hex()

    return [
        {
            "id": f"dialogue.{content_entry['id']}.ptr",
            "type": "pointer_redirect",
            "sub_type": "pointer_redirect",
            "pointer_table_offset": ptr_offset,
            "expected_pointer_hex": orig_ptr_hex,
            "new_pointer_hex": new_ptr,
            "encoding": encoding,
            "text": text,
            "source_entry": content_entry["id"],
            "strategy": "pointer_redirect",
        },
        {
            "id": f"dialogue.{content_entry['id']}.text",
            "type": "bytes",
            "sub_type": "bytes",
            "offset": redirect_offset,
            "before_hex": "00" * len(new_text_bytes),
            "after_hex": new_text_hex,
            "encoding": encoding,
            "text": text,
            "max_bytes": max_bytes,
            "source_entry": content_entry["id"],
            "strategy": "pointer_redirect",
        },
    ]


def import_dialogue(
    bank_path: Path,
    content_path: Path,
    overrides: dict[str, str] | None = None,
    rom_path: Path | None = None,
) -> list[dict]:
    """Convert high-level dialogue content into ROM patch entries.

    Args:
        bank_path: Path to dialogue-bank.json (ROM offset / max_bytes info).
        content_path: Path to dialogue-patches.json (text content).
        overrides: Optional dict {entry_id: text} that takes precedence over
                   whatever is in dialogue-patches.json. Used by build_db_patches
                   to inject dialogues created via the editor (which live in
                   sequel/editor.db) without rewriting the content JSON file.
        rom_path: Optional ROM used for the font code table. Defaults to
                  rom/base.gba; only needed for encoding="font" entries.
    """
    bank = load_json(bank_path)
    content = load_json(content_path)
    bank_map = {entry["id"]: entry for entry in bank["entries"]}
    patches = []
    mapping: dict[int, str] | None = None
    for entry in content["entries"]:
        patch_id = entry["id"]
        if patch_id not in bank_map:
            raise ValueError(f"dialogue entry {patch_id} missing from bank")
        # Apply editor override if present
        if overrides is not None and patch_id in overrides:
            entry = {**entry, "text": overrides[patch_id]}
        bank_entry = bank_map[patch_id]
        encoding = bank_entry.get("encoding", text_codec.FONT_ENCODING)
        if encoding == text_codec.FONT_ENCODING and mapping is None:
            mapping, _ = text_codec.load_mapping(rom_path)
        result = build_patch(bank_entry, entry, mapping)
        patches.extend(result)
    return patches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert high-level dialogue content into ROM patch entries."
    )
    parser.add_argument("--bank", default="sequel/content/text/dialogue-bank.json")
    parser.add_argument(
        "--content", default="sequel/content/text/dialogue-patches.json"
    )
    parser.add_argument("--output", help="Optional output JSON path")
    parser.add_argument(
        "--rom",
        default=None,
        help="ROM used for the font code table (default rom/base.gba)",
    )
    args = parser.parse_args()

    patches = import_dialogue(
        ROOT / args.bank, ROOT / args.content, rom_path=args.rom
    )
    text = json.dumps({"patches": patches}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        from tools.lib.io import write_text as write_text_lf
        write_text_lf(ROOT / args.output, text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
