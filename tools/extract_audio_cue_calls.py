#!/usr/bin/env python3
"""Inventory Thumb calls to the game's public sound-ID playback wrapper.

The extractor deliberately recognizes a sound ID only when the halfword
immediately before the call is ``movs r0, #imm8``.  Register-fed calls remain
dynamic instead of receiving a guessed value.
"""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

try:
    from tools.thumb_branch import decode_thumb_bl, encode_thumb_bl
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from thumb_branch import decode_thumb_bl, encode_thumb_bl

ROM_BASE = 0x08000000
PLAY_WRAPPER = 0x08061E6C


def scan_calls(
    rom: bytes, *, target: int = PLAY_WRAPPER, rom_base: int = ROM_BASE
) -> list[dict]:
    calls = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        callsite = rom_base + offset
        if decode_thumb_bl(callsite, first, second) != target:
            continue
        previous = struct.unpack_from("<H", rom, offset - 2)[0] if offset >= 2 else -1
        immediate = previous & 0xFF if previous & 0xFF00 == 0x2000 else None
        calls.append({
            "callsite": callsite,
            "callsite_hex": f"0x{callsite:08X}",
            "source": "immediate" if immediate is not None else "dynamic",
            "sound_id": immediate,
        })
    return calls


def build_inventory(rom: bytes) -> dict:
    calls = scan_calls(rom)
    counts = Counter(
        call["sound_id"] for call in calls if call["sound_id"] is not None
    )
    return {
        "target": f"0x{PLAY_WRAPPER:08X}",
        "callsite_count": len(calls),
        "immediate_callsite_count": sum(call["source"] == "immediate" for call in calls),
        "dynamic_callsite_count": sum(call["source"] == "dynamic" for call in calls),
        "immediate_sound_id_count": len(counts),
        "immediate_counts": {str(key): counts[key] for key in sorted(counts)},
        "calls": calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inventory = build_inventory(args.rom.read_bytes())
    rendered = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
