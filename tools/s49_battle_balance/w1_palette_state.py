#!/usr/bin/env python3
"""Decode Butano's OBJ/ BG palette bank state out of a probe memory dump.

The layout is the one of ``bn::palettes_bank`` (Butano's
``bn/src/bn_palettes_bank.h``), confirmed with the DWARF info of the linked
ELF:

    struct palette          // 28 bytes
    {
        unsigned usages;             // +0
        fixed    grayscale_intensity;// +4
        fixed    hue_shift_intensity;// +8
        fixed    fade_intensity;     // +12
        color    fade_color;         // +16
        uint16_t hash;               // +18
        int16_t  rotate_count;       // +20
        int8_t   slots_count;        // +22
        int8_t   rotate_range_start; // +23
        int8_t   rotate_range_size;  // +24
        uint8_t  flags;              // +25  (bit0 = bpp_8)
    };
    palette _palettes[16];           // +0 of palettes_bank

``palettes_manager`` keeps two of those banks in one EWRAM block:
``data_buffer`` holds the sprite bank first and the BG bank second, so the
BG bank starts ``sizeof(palettes_bank)`` bytes further (1704).
"""

from __future__ import annotations

import dataclasses
import sys

PALETTE_RECORD_SIZE = 28
BANK_SLOTS = 16
PALETTES_BANK_SIZE = 1704
SPRITE_BANK_ADDRESS = 0x02028588
BG_BANK_ADDRESS = SPRITE_BANK_ADDRESS + PALETTES_BANK_SIZE


@dataclasses.dataclass
class Slot:
    index: int
    usages: int
    slots_count: int
    bpp_8: bool
    locked: bool

    @property
    def banks(self) -> int:
        return self.slots_count if self.usages else 0


def decode_bank(data: bytes, label: str) -> dict[str, object]:
    slots: list[Slot] = []
    for index in range(BANK_SLOTS):
        base = index * PALETTE_RECORD_SIZE
        usages = int.from_bytes(data[base:base + 4], "little")
        slots_count = data[base + 22]
        flags = data[base + 25]
        slots.append(Slot(index=index, usages=usages,
                          slots_count=slots_count,
                          bpp_8=bool(flags & 1),
                          locked=bool(flags & 8)))
    used_banks = sum(slot.banks for slot in slots)
    first_bpp4 = next((slot.index for slot in slots
                       if slot.usages and not slot.bpp_8), BANK_SLOTS)
    return {
        "label": label,
        "used_banks": used_banks,
        "used_colors": used_banks * 16,
        "first_bpp4_index": first_bpp4,
        "slots": slots,
    }


def describe(bank: dict[str, object]) -> str:
    lines = [f"{bank['label']}: used_banks={bank['used_banks']} "
             f"used_colors={bank['used_colors']} "
             f"first_bpp4_index={bank['first_bpp4_index']}"]
    for slot in bank["slots"]:  # type: ignore[index]
        if slot.usages:
            lines.append(
                f"    slot {slot.index:2d}: usages={slot.usages} "
                f"slots_count={slot.slots_count} "
                f"bpp8={'Y' if slot.bpp_8 else 'n'} "
                f"locked={'Y' if slot.locked else 'n'}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    data = bytes.fromhex(argv[1])
    if len(data) < PALETTES_BANK_SIZE:
        print(f"need {PALETTES_BANK_SIZE} bytes, got {len(data)}")
        return 2
    sprite = decode_bank(data[:PALETTES_BANK_SIZE], "sprite")
    bg = decode_bank(data[PALETTES_BANK_SIZE:2 * PALETTES_BANK_SIZE], "bg")
    print(describe(sprite))
    print(describe(bg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
