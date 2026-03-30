#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_patch(bank_entry: dict, content_entry: dict) -> list[dict]:
    encoding = bank_entry.get("encoding", "cp932")
    text = content_entry["text"]
    encoded = text.encode(encoding)
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


def import_dialogue(bank_path: Path, content_path: Path) -> list[dict]:
    bank = load_json(bank_path)
    content = load_json(content_path)
    bank_map = {entry["id"]: entry for entry in bank["entries"]}
    patches = []
    for entry in content["entries"]:
        patch_id = entry["id"]
        if patch_id not in bank_map:
            raise ValueError(f"dialogue entry {patch_id} missing from bank")
        result = build_patch(bank_map[patch_id], entry)
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
    args = parser.parse_args()

    patches = import_dialogue(ROOT / args.bank, ROOT / args.content)
    text = json.dumps({"patches": patches}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        (ROOT / args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
