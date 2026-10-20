#!/usr/bin/env python3
"""Generate ROM-derived 8x16 glyph sprites for battle presentation text."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

try:
    from tools.butano.indexed_bmp import write_4bpp_bmp
except ModuleNotFoundError:
    from butano.indexed_bmp import write_4bpp_bmp

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit_butano_reverse_provenance import provenance_block

PROVENANCE = provenance_block(
    sources=(
        (
            "dialogue-font-v2",
            "818684d7533ae44bbe4f56b4b6df9a6d6f69612a43ae041dfb5a7b0b0698e69c",
        ),
    ),
    roms=(
        (
            0x53D644,
            208,
            "6c396ab55b0cbeacb4d2d2d8df55666ab79fcfa426377ef91d03ab7743a7b18d",
        ),
    ),
)

# The products this generator writes.  The provenance auditor reads this
# registry to learn the product set; it never guesses the set from a file
# name pattern.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/"
    "generated_battle_presentation_glyph_content.h",
    "butano-sequel/graphics/"
    "generated_battle_presentation_glyph_content.h",
)


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
FONT_TABLE_OFFSET = 0x53D644
FONT_TABLE_ENTRY_COUNT = 26
FONT_TABLE_ENTRY_SIZE = 8
FONT_TABLE_SHA256 = "6c396ab55b0cbeacb4d2d2d8df55666ab79fcfa426377ef91d03ab7743a7b18d"

PALETTE = [
    (255, 0, 255),
    *[
        (16 + index * 15,) * 3
        for index in range(1, 16)
    ],
]


def _presentation_texts(manifest: dict[str, Any]) -> list[bytes]:
    return [
        bytes.fromhex(command["encoded_text_hex"])
        for battle in manifest["battles"][1:]
        for case in battle["presentation_cases"]
        for command in case["commands"]
        if "encoded_text_hex" in command
    ]


def _codes(texts: list[bytes]) -> list[int]:
    result: set[int] = set()
    for text in texts:
        index = 0
        while index < len(text):
            lead = text[index]
            if (
                (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC)
                and index + 1 < len(text)
            ):
                result.add((lead << 8) | text[index + 1])
                index += 2
            elif lead == 0x0A:
                index += 1
            else:
                raise ValueError(
                    "unsupported single-byte presentation text code "
                    f"0x{lead:02X}"
                )
    return sorted(result)


def _font_entries(rom: bytes) -> list[tuple[int, int, int]]:
    table = rom[
        FONT_TABLE_OFFSET:
        FONT_TABLE_OFFSET
        + FONT_TABLE_ENTRY_COUNT * FONT_TABLE_ENTRY_SIZE
    ]
    actual = hashlib.sha256(table).hexdigest()
    if actual != FONT_TABLE_SHA256:
        raise ValueError(
            "battle presentation font table SHA-256 mismatch: "
            f"expected {FONT_TABLE_SHA256}, got {actual}"
        )
    entries = []
    for index in range(FONT_TABLE_ENTRY_COUNT):
        lower, size, padding, tile_address = struct.unpack_from(
            "<HBBI", table, index * FONT_TABLE_ENTRY_SIZE
        )
        if size == 0:
            raise ValueError(
                f"invalid font table entry {index}"
            )
        entries.append((lower, size, tile_address))
    return entries


def _tile_address(
    code: int,
    entries: list[tuple[int, int, int]],
) -> int:
    for lower, size, address in entries:
        if lower <= code < lower + size:
            return address + (code - lower) * 32
    raise ValueError(f"presentation code 0x{code:04X} has no ROM glyph")


def _decode_glyph(glyph: bytes) -> list[int]:
    if len(glyph) != 32:
        raise ValueError("truncated 8x16 2bpp font glyph")
    pixels: list[int] = []
    for row in range(16):
        for packed in glyph[row * 2:row * 2 + 2]:
            for column in range(4):
                pixels.append(
                    ((packed >> (column * 2)) & 3) * 5
                )
    return pixels


def load_battle_presentation_glyphs(
    root: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    rom = (root / "rom/base.gba").read_bytes()
    actual_rom_hash = hashlib.sha256(rom).hexdigest()
    if actual_rom_hash != ROM_SHA256:
        raise ValueError(
            "battle presentation ROM SHA-256 mismatch: "
            f"expected {ROM_SHA256}, got {actual_rom_hash}"
        )
    manifest = json.loads(
        (
            root
            / "sequel/content/battle-presentation-scripts/bank.json"
        ).read_text(encoding="utf-8")
    )
    codes = _codes(_presentation_texts(manifest))
    entries = _font_entries(rom)
    addresses = [
        _tile_address(code, entries)
        for code in codes
    ]
    pixels: list[int] = []
    for address in addresses:
        offset = address - ROM_BASE
        if offset < 0 or offset + 32 > len(rom):
            raise ValueError(
                f"font tile address 0x{address:08X} is outside ROM"
            )
        pixels.extend(
            _decode_glyph(rom[offset:offset + 32])
        )
    return {
        "codes": codes,
        "tile_addresses": addresses,
        "pixels": pixels,
    }


def generate_header(content: dict[str, Any]) -> str:
    codes = ", ".join(
        f"0x{code:04X}" for code in content["codes"]
    )
    return f"""// Generated by tools/generate_butano_battle_presentation_glyphs.py. Do not edit.
{PROVENANCE}
#ifndef KONOHA_GENERATED_BATTLE_PRESENTATION_GLYPH_CONTENT_H
#define KONOHA_GENERATED_BATTLE_PRESENTATION_GLYPH_CONTENT_H

#include <array>
#include <cstdint>

namespace konoha
{{

inline constexpr std::array<std::uint16_t, {len(content["codes"])}>
        battle_presentation_glyph_codes = {{{{
    {codes}
}}}};

[[nodiscard]] inline constexpr int
battle_presentation_glyph_index(std::uint16_t code)
{{
    int first = 0;
    int last = static_cast<int>(
            battle_presentation_glyph_codes.size());
    while(first < last)
    {{
        const int middle = first + (last - first) / 2;
        const std::uint16_t candidate =
                battle_presentation_glyph_codes[
                        static_cast<std::size_t>(middle)];
        if(candidate < code)
        {{
            first = middle + 1;
        }}
        else
        {{
            last = middle;
        }}
    }}
    return first <
                           static_cast<int>(
                                   battle_presentation_glyph_codes.size()) &&
                   battle_presentation_glyph_codes[
                           static_cast<std::size_t>(first)] == code ?
            first :
            -1;
}}

}}

#endif
"""


def generate_outputs(
    root: Path | str,
    output_root: Path | str,
) -> dict[str, Path]:
    root = Path(root)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    content = load_battle_presentation_glyphs(root)
    bitmap = output_root / "battle_presentation_glyphs.bmp"
    metadata = output_root / "battle_presentation_glyphs.json"
    header = output_root / "generated_battle_presentation_glyph_content.h"
    write_4bpp_bmp(
        bitmap,
        8,
        len(content["codes"]) * 16,
        content["pixels"],
        PALETTE,
    )
    metadata.write_text(
        '{\n  "type": "sprite",\n  "height": 16\n}\n',
        encoding="utf-8",
    )
    header.write_text(
        generate_header(content),
        encoding="utf-8",
    )
    return {
        "bitmap": bitmap,
        "metadata": metadata,
        "header": header,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--graphics-output",
        type=Path,
        default=Path("butano-sequel/graphics"),
    )
    parser.add_argument(
        "--header-output",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/"
            "generated_battle_presentation_glyph_content.h"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    graphics = args.graphics_output
    if not graphics.is_absolute():
        graphics = root / graphics
    outputs = generate_outputs(root, graphics)
    header_output = args.header_output
    if not header_output.is_absolute():
        header_output = root / header_output
    header_output.parent.mkdir(parents=True, exist_ok=True)
    header_output.write_bytes(outputs["header"].read_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
