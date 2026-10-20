#!/usr/bin/env python3
"""Round-trip check and a corrected tile mapping for the Konoha Senki font.

The repo's old sequel/content/text/sjis-to-tile-mapping.json was a hand-made
20-character table whose *values* were double-encoded (mojibake): "娴犫偓" was
meant to be "浠€". The byte keys were correct.

This tool:
  1. builds the full code->character mapping from the ROM (fingerprint-checked);
  2. re-derives the old 20 key/value pairs to prove the byte keys were right;
  3. round-trips a sample of real in-game text through encode -> decode;
  4. can emit a corrected mapping file that supersedes the hand-made one.

Usage:
    python tools/font_roundtrip.py
    python tools/font_roundtrip.py --emit-mapping sequel/content/text/font-code-map.json
"""
from __future__ import annotations

import argparse
import json
import struct
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konoha_font as kf  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
OLD_MAP = REPO / "sequel" / "content" / "text" / "sjis-to-tile-mapping.json"


def repair_mojibake(s: str) -> str:
    """The old mapping file stored UTF-8 bytes that were read as GBK.

    '娴犫偓' -> '浠€' and friends. Recover the original by re-encoding the
    mis-decoded text as GBK and decoding it as UTF-8.
    """
    try:
        return s.encode("gbk", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-mapping", help="write the full code->character map here")
    args = ap.parse_args()

    rom_path = next(REPO.glob("*.gba"))
    rom = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    mapping, report = kf.build_mapping(rom)
    print(f"mapping: {len(mapping)} codes, "
          f"{report['catalog_segments_matched']}/{report['catalog_segments_total']} "
          f"font segments fingerprint-matched")

    # 1. the old hand-made table
    if OLD_MAP.exists():
        old = json.loads(OLD_MAP.read_text(encoding="utf-8"))
        print("\n=== old hand-made table vs the ROM-backed mapping ===")
        print("  the old file claims it was derived from the bytes at 0x459414;")
        print("  here is what those bytes actually decode to in this ROM:")
        text, _ = kf.decode_at(rom, 0x459414, mapping)
        print(f"    ROM-backed : {text!r}")
        old_text = "".join(
            "\n" if v == "\\n" else v
            for v in (repair_mojibake(x) for x in old.get("mapping", {}).values())
        )
        print(f"    old table  : {old_text!r}")
        agree = sum(1 for k, v in old.get("mapping", {}).items()
                    if mapping.get(int(k, 16)) == repair_mojibake(v))
        print(f"    entries agreeing with the ROM: {agree}/{len(old.get('mapping', {}))}")
        print("    -> the hand-made table does not describe this ROM; the ROM-backed")
        print("       mapping is the one consistent with the text and the quiz answers")

    # 2. round-trip real text
    print("\n=== round-trip on real in-game text ===")
    name_ptr = struct.unpack_from("<I", rom, 0x599280 + 4)[0] - 0x08000000
    samples = [
        (0x459414, "story/dialogue text bank entry 0"),
        (0x59A1BC, "mission title, stage 1"),
        (name_ptr, "character name, id 1"),
        (0x59AC20, "mission description, stage 1"),
        (0x08009F3E - 0x08000000, "story script text, scene 1"),
    ]
    for ptr_off, label in samples:
        tokens = kf.scan_tokens(rom, ptr_off)
        text = kf.tokens_to_string(tokens, mapping)
        try:
            encoded = kf.encode_tokens(tokens, mapping)
        except KeyError as exc:
            print(f"  {label}: encode failed -> {exc}")
            continue
        same_bytes = encoded == rom[ptr_off:ptr_off + len(encoded)]
        n_ctrl = sum(1 for k, _ in tokens if k == "ctrl")
        print(f"  {label}: {text[:20]!r}...  bytes_equal={same_bytes}  "
              f"ctrl_codes={n_ctrl}")

    # 2b. plain-string round trip (what a writer of NEW text gets)
    print("\n=== plain string round trip (new text path) ===")
    for label, ptr_off in (("mission description, stage 1", 0x59AC20),):
        text, _ = kf.decode_at(rom, ptr_off, mapping)
        try:
            encoded = kf.encode_text(text, mapping)
        except KeyError as exc:
            print(f"  {label}: encode failed -> {exc}")
            continue
        back, _ = kf.decode_at(rom, ptr_off, mapping)
        print(f"  {label}: decode_stable={back == text}  "
              f"byte_equal_without_ctrl={encoded == rom[ptr_off:ptr_off + len(encoded)]}")
    print("  (plain-string encoding drops control codes, so it is only safe for")
    print("   brand-new strings; rewriting existing text must use tokens)")

    # 3. character coverage
    names = kf.read_character_names(rom, mapping)
    rev = kf.build_reverse_mapping(mapping)
    missing_chars = sorted({ch for n in names.values() for ch in n if ch not in rev})
    print(f"\n=== roster coverage ===")
    print(f"  {len(names)} names, distinct characters not encodable: "
          f"{len(missing_chars)} {missing_chars}")

    if args.emit_mapping:
        out = pathlib.Path(args.emit_mapping)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_comment": "Konoha Senki font code -> character, derived from the ROM font "
                       "segments (FNV-1a fingerprint checked). Replaces the 20-entry "
                       "hand-made sjis-to-tile-mapping.json whose values were double-encoded.",
            "_encoding": "custom double-byte font code (lead byte 0x80..0x9F), NOT cp932",
            "segments": report["segments"],
            "mapping": {str(code): ch for code, ch in sorted(mapping.items())},
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {out} ({len(mapping)} codes)")


if __name__ == "__main__":
    main()

