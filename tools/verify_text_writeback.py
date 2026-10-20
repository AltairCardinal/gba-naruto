#!/usr/bin/env python3
"""Verify that the dialogue write path produces text the game can render.

This is the check the previous pipeline never ran.  Every earlier "E2E ROM
verification" proved that *bytes landed at an offset*; none of them asked what
those bytes **render as**.  With the old cp932 write path that difference
mattered: the ROM stores font codes, so Shift-JIS bytes are drawn as whatever
font codes they collide with, and the player reads garbage.

The check is end to end and uses the real build code path:

    content JSON -> import_dialogue -> build_mod.apply_bytes_patch -> ROM
                -> text_codec.decode -> rendered text -> compare with the
                   authored text

A pass means: the bytes the build writes decode back to exactly the text the
author wrote.

Usage
-----
    python tools/verify_text_writeback.py
    python tools/verify_text_writeback.py --json build/text-writeback.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import build_mod  # noqa: E402
from tools import text_codec  # noqa: E402
from tools.import_dialogue import import_dialogue  # noqa: E402

BANK = REPO / "sequel" / "content" / "text" / "dialogue-bank.json"
CONTENT = REPO / "sequel" / "content" / "text" / "dialogue-patches.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None, help="base ROM (default rom/base.gba)")
    ap.add_argument(
        "--verify-rom",
        default=None,
        help="check an already built ROM's dialogue slots instead of applying "
             "the patches to the base ROM",
    )
    ap.add_argument("--json", default=None, help="write the JSON report here")
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = bytearray(rom_path.read_bytes())
    mapping, meta = text_codec.load_mapping(rom_path)

    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    authored = {e["id"]: e["text"] for e in content["entries"]}
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    bank_map = {e["id"]: e for e in bank["entries"]}

    if args.verify_rom:
        built_path = pathlib.Path(args.verify_rom)
        rom = bytearray(built_path.read_bytes())
        results = []
        ok = True
        for entry_id, text in authored.items():
            bank_entry = bank_map[entry_id]
            offset = int(bank_entry["offset"])
            max_bytes = int(bank_entry["max_bytes"])
            patched = bytes(rom[offset : offset + max_bytes])
            rendered = text_codec.decode(patched, mapping)
            match = rendered == text
            unresolved = "{字" in rendered
            ok = ok and match and not unresolved
            results.append({
                "entry_id": entry_id,
                "offset": hex(offset),
                "strategy": "built_rom",
                "encoding": bank_entry.get("encoding"),
                "bytes": max_bytes,
                "authored": text,
                "rendered": rendered,
                "legacy_cp932_decode": patched.decode("cp932", errors="replace"),
                "match": match,
                "unresolved_glyphs": unresolved,
            })
        rom_path = built_path
    else:
        patches = import_dialogue(BANK, CONTENT, rom_path=rom_path)

        results = []
        ok = True
        for patch in patches:
            entry_id = patch.get("source_entry", patch["id"])
            sub_type = patch.get("sub_type", patch["type"])
            if sub_type == "pointer_redirect":
                build_mod.apply_pointer_redirect_patch(rom, patch)
                target = int(patch["offset"])
                length = len(bytes.fromhex(patch["after_hex"]))
            else:
                # The real build path: raises when the ROM bytes do not match
                # before_hex, so a stale bank cannot slip through unnoticed.
                build_mod.apply_bytes_patch(rom, patch)
                target = int(patch["offset"])
                length = len(bytes.fromhex(patch["after_hex"]))

            patched = bytes(rom[target : target + length])
            rendered = text_codec.decode(patched, mapping)
            legacy = patched.decode("cp932", errors="replace")
            expected = authored.get(entry_id, "")

            match = rendered == expected
            unresolved = "{字" in rendered
            ok = ok and match and not unresolved
            results.append({
                "entry_id": entry_id,
                "offset": hex(target),
                "strategy": patch.get("strategy", sub_type),
                "encoding": patch.get("encoding"),
                "bytes": length,
                "authored": expected,
                "rendered": rendered,
                "legacy_cp932_decode": legacy,
                "match": match,
                "unresolved_glyphs": unresolved,
                "before_hex": patch.get("before_hex"),
                "after_hex": patch.get("after_hex"),
            })

    report = {
        "rom": str(rom_path),
        "font_codes": len(mapping),
        "catalog_segments_matched": meta["catalog_segments_matched"],
        "entries": len(results),
        "all_match": ok,
        "results": results,
    }

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM            : {rom_path.name}")
    print(f"font codes     : {len(mapping)} "
          f"({meta['catalog_segments_matched']}/{meta['catalog_segments_total']} "
          f"segments fingerprint-matched)")
    print(f"entries checked: {len(results)}")
    print()
    for r in results:
        flag = "OK  " if r["match"] and not r["unresolved_glyphs"] else "FAIL"
        print(f"[{flag}] {r['entry_id']} @ {r['offset']} "
              f"({r['bytes']} bytes, encoding={r['encoding']})")
        print(f"        authored : {r['authored']!r}")
        print(f"        rendered : {r['rendered']!r}")
        if not r["match"]:
            print(f"        legacy cp932 would read: {r['legacy_cp932_decode']!r}")
    print()
    print("RESULT:", "PASS - every patched slot renders the authored text"
          if ok else "FAIL - a patched slot does not render the authored text")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
