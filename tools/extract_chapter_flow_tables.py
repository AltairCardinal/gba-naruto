#!/usr/bin/env python3
"""Extract the two 56-entry scenario/chapter script pointer tables."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

try:
    from tools.chapter_script_codec import decode_script
    from tools.chapter_script_analyzer import analyze_observed_script
except ModuleNotFoundError:
    from chapter_script_codec import decode_script
    from chapter_script_analyzer import analyze_observed_script

ROM_BASE = 0x08000000
TABLES = {
    "story": (0x60C74, "runtime_verified"),
    "story-b": (0x60D54, "runtime_verified"),
}
ENTRY_COUNT = 56


def build_bank(rom: bytes, slug: str) -> dict:
    table_offset, verification = TABLES[slug]
    entries = []
    for index in range(ENTRY_COUNT):
        raw_offset = table_offset + index * 4
        pointer = struct.unpack_from("<I", rom, raw_offset)[0]
        if index == 0:
            if pointer != 0:
                raise ValueError(f"{slug} sentinel entry 0 is not null")
            target_offset = None
            preview = ""
        else:
            target_offset = pointer - ROM_BASE
            if not 0 <= target_offset < len(rom):
                raise ValueError(f"{slug}[{index}] invalid script pointer 0x{pointer:08X}")
            preview = rom[target_offset:target_offset + 16].hex()
        entries.append({
            "scenario_id": index,
            "_index": index,
            "_raw_offset": raw_offset,
            "rom_offset": raw_offset,
            "rom_offset_hex": f"0x{raw_offset:06X}",
            "script_ptr": pointer,
            "script_ptr_hex": pointer.to_bytes(4, "little").hex(),
            "target_offset": target_offset,
            "target_offset_hex": None if target_offset is None else f"0x{target_offset:06X}",
            "script_preview_hex": preview,
        })
    description = (
        "Primary scenario/chapter flow script pointer table selected when state +0x18 is zero."
        if slug == "story" else
        "Alternate scenario/chapter flow script pointer table selected when state +0x18 is nonzero."
    )
    return {
        "version": 5,
        "description": description,
        "structure_kind": "chapter-flow-script-pointer-table",
        "table_offset": table_offset,
        "table_offset_hex": f"0x{table_offset:06X}",
        "entry_count": ENTRY_COUNT,
        "entry_size": 4,
        "entry_format": {"fields": [{"offset": 0, "size": 4, "name": "script_ptr", "type": "u32"}]},
        "verification": verification,
        "verification_method": (
            "0x0808F544 indexes scenario_id*4 from 0x08060C74 or 0x08060D54 according to state +0x18, then calls interpreter 0x080977B8. Live primary scenario 39 selected 0x08031020; opcode 0x1A at 0x08031070 supplied battle ID 40."
            if slug == "story" else
            "A forced-alternate runtime probe captured selector scenario 39 choosing 0x08060D54[39] = 0x08031281, then 25 generic interpreter dispatches ending at opcode 0x00 at 0x0803142E. ROM bytes matched at the live cursor; opcode 0x00 returns normally at zero call depth, so no battle ID is expected."
        ),
        "consumer": {
            "selector": "0x0808F544",
            "interpreter": "0x080977B8",
            "set_battle_handler": "0x08097C6C",
            "audio_cue_handler": "0x08097C9C",
            "audio_cue_helper": "0x08097140",
            "speaker_label_handler": "0x080979E8",
            "speaker_label_table": "0x085A57C4",
            "end_handler": "0x08097916",
            "opcode_dispatch": "0x080977D8",
            "state_selector": "0x020311EC (+0x18)",
        },
        "runtime_sample": ({
            "scenario_id": 39,
            "script_ptr": "0x08031020",
            "opcode_address": "0x08031070",
            "script_bytes": "1a280200",
            "semantic_commands": decode_script(bytes.fromhex("1a280200")),
            "battle_id": 40,
        } if slug == "story" else {
            "scenario_id": 39,
            "script_ptr": "0x08031281",
            "dispatch_hit_count": 25,
            "terminal_opcode_address": "0x0803142E",
            "terminal_opcode_bytes": "00001b04",
            "termination": "opcode 0x00 returns from the interpreter at zero call depth",
            "battle_id": 0,
            "forced_alternate_selector": True,
            "observed_commands": analyze_observed_script(
                rom[0x31281:0x3142F], base_address=0x08031281
            ),
        }),
        "writeback": (
            "Lossless pointer mirror requires immutable-base and ROM-range checks. The strict "
            "chapter_script_codec currently authors only code-proven END, SET_SPEAKER_LABEL, "
            "SET_BATTLE, and AUDIO_CUE scripts; "
            "production script allocation and atomic pointer+payload writeback remain disabled."
        ),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--write-banks", action="store_true")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    result = {slug: build_bank(rom, slug) for slug in TABLES}
    if args.write_banks:
        root = Path(__file__).resolve().parent.parent
        for slug, bank in result.items():
            path = root / "sequel/content" / slug / "bank.json"
            path.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {slug}: {ENTRY_COUNT} entries at {bank['table_offset_hex']}")
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
