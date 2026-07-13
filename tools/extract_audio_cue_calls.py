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

ROM_BASE = 0x08000000
PLAY_WRAPPER = 0x08061E6C


def encode_thumb_bl(callsite: int, target: int) -> bytes:
    """Encode an ARMv4T two-halfword BL, primarily for regression fixtures."""
    displacement = target - (callsite + 4)
    if displacement & 1:
        raise ValueError("Thumb BL target must be halfword aligned")
    if not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("Thumb BL target is outside ARMv4T range")
    encoded = displacement & 0x7FFFFF
    return struct.pack(
        "<HH", 0xF000 | ((encoded >> 12) & 0x7FF),
        0xF800 | ((encoded >> 1) & 0x7FF),
    )


def _thumb_bl_target(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def scan_calls(
    rom: bytes, *, target: int = PLAY_WRAPPER, rom_base: int = ROM_BASE
) -> list[dict]:
    calls = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        callsite = rom_base + offset
        if _thumb_bl_target(callsite, first, second) != target:
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
