#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_patch(bank_entry: dict, content_entry: dict) -> dict:
    encoding = bank_entry.get("encoding", "cp932")
    text = content_entry["text"]
    encoded = text.encode(encoding)
    max_bytes = int(bank_entry["max_bytes"])
    if len(encoded) != max_bytes:
        raise ValueError(
            f"dialogue entry {content_entry['id']} encoded length {len(encoded)} does not match max_bytes {max_bytes}"
        )
    return {
        "id": f"dialogue.{content_entry['id']}",
        "type": "dialogue",
        "offset": int(bank_entry["offset"]),
        "before_hex": bank_entry["expected_hex"],
        "after_hex": encoded.hex(),
        "encoding": encoding,
        "text": text,
        "max_bytes": max_bytes,
        "source_entry": content_entry["id"],
    }


def import_dialogue(bank_path: Path, content_path: Path) -> list[dict]:
    bank = load_json(bank_path)
    content = load_json(content_path)
    bank_map = {entry["id"]: entry for entry in bank["entries"]}
    patches = []
    for entry in content["entries"]:
        patch_id = entry["id"]
        if patch_id not in bank_map:
            raise ValueError(f"dialogue entry {patch_id} missing from bank")
        patches.append(build_patch(bank_map[patch_id], entry))
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
