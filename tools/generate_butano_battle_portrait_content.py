#!/usr/bin/env python3
"""Generate the ROM-derived portrait resources used by battle scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress

from tools.audit_butano_reverse_provenance import provenance_block

PROVENANCE = provenance_block(
    sources=(
        (
            "menu-portraits-v1",
            "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3",
        ),
    ),
    roms=(
        (
            0x5A4DEC,
            2520,
            "bfc995240519eca9035e140a45e506a5c1f6f561e05827a589b5ac03543bba7e",
        ),
    ),
)

# The products this generator writes.  The provenance auditor reads this
# registry to learn the product set; it never guesses the set from a file
# name pattern.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/"
    "generated_battle_presentation_portrait_content.h",
)


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PORTRAIT_BYTES = 6400
PORTRAIT_COLORS = 64

# The original OAM task consumes the 100 8bpp tiles in this order. Together
# these six hardware-supported shapes cover one 80x80 portrait canvas.
PORTRAIT_COMPONENTS = (
    (64, 64, 16, 16, 0, 256),
    (64, 32, 16, 32, 256, 512),
    (64, 0, 16, 32, 768, 512),
    (32, 64, 32, 16, 1280, 512),
    (0, 64, 32, 16, 1792, 512),
    (0, 0, 64, 64, 2304, 4096),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _used_pairs(manifest: dict[str, Any]) -> list[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for battle in manifest["battles"]:
        for case in battle.get("presentation_cases", []):
            for command in case["commands"]:
                opcode = command["opcode"]
                operands = bytes.fromhex(command.get("operand_hex", ""))
                if opcode in {"0x02", "0x04"}:
                    result.add((operands[1], operands[2]))
                elif opcode == "0x12":
                    result.add((operands[0], operands[1]))
                    result.add((operands[2], operands[3]))
    return sorted(result)


def _lz77_record(rom: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"portrait graphics is not LZ77 at 0x{offset:06X}")
    expected_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output_size = 0
    cursor = offset + 4
    while output_size < expected_size:
        if cursor >= len(rom):
            raise ValueError("truncated portrait LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if output_size >= expected_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated portrait LZ77 back-reference")
                output_size += ((rom[cursor] >> 4) & 0x0F) + 3
                cursor += 2
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated portrait LZ77 literal")
                output_size += 1
                cursor += 1
    return rom[offset:cursor]


def extract_battle_portrait_content(root: Path) -> dict[str, Any]:
    root = Path(root)
    rom = (root / "rom/base.gba").read_bytes()
    actual_rom_sha256 = _sha256(rom)
    if actual_rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {actual_rom_sha256}"
        )
    scripts = json.loads(
        (root / "sequel/content/battle-presentation-scripts/bank.json")
        .read_text(encoding="utf-8")
    )
    matrix = json.loads(
        (root / "sequel/content/menu-ui/bank.json").read_text(encoding="utf-8")
    )
    if scripts.get("schema_version") != 1:
        raise ValueError("unsupported battle presentation script schema")
    if (
        matrix.get("table_offset") != 0x5A4DEC
        or matrix.get("entry_count") != 63
        or len(matrix.get("entries", [])) != 63
    ):
        raise ValueError("unexpected visual variant matrix")

    compressed_gfx = bytearray()
    palettes: list[int] = []
    resources: list[dict[str, Any]] = []
    for portrait_id, expression_id in _used_pairs(scripts):
        if not 0 <= portrait_id < len(matrix["entries"]):
            raise ValueError(f"portrait ID is out of range: {portrait_id}")
        if not 0 <= expression_id < 5:
            raise ValueError(
                f"portrait expression is out of range: {expression_id}"
            )
        row = matrix["entries"][portrait_id]
        gfx_pointer = row[f"gfx_ptr_{expression_id}"]
        palette_pointer = row[f"palette_ptr_{expression_id}"]
        gfx_offset = gfx_pointer - ROM_BASE
        palette_offset = palette_pointer - ROM_BASE
        compressed = _lz77_record(rom, gfx_offset)
        decompressed = lz77_decompress(rom, gfx_offset)
        if len(decompressed) != PORTRAIT_BYTES:
            raise ValueError(
                "unexpected portrait graphics size "
                f"for {portrait_id}/{expression_id}: {len(decompressed)}"
            )
        if not 0 <= palette_offset <= len(rom) - PORTRAIT_COLORS * 2:
            raise ValueError("portrait palette is outside the ROM")
        palette_bytes = rom[
            palette_offset : palette_offset + PORTRAIT_COLORS * 2
        ]
        padding = (-len(compressed_gfx)) % 4
        if padding:
            compressed_gfx.extend(b"\0" * padding)
        resource = {
            "portrait_id": portrait_id,
            "expression_id": expression_id,
            "gfx_pointer": gfx_pointer,
            "palette_pointer": palette_pointer,
            "gfx_offset": len(compressed_gfx),
            "compressed_size": len(compressed),
            "palette_offset": len(palettes),
            "decompressed_size": len(decompressed),
            "compressed_sha256": _sha256(compressed),
            "decompressed_sha256": _sha256(decompressed),
            "palette_sha256": _sha256(palette_bytes),
        }
        resources.append(resource)
        compressed_gfx.extend(compressed)
        palettes.extend(
            struct.unpack(f"<{PORTRAIT_COLORS}H", palette_bytes)
        )
    return {
        "resources": resources,
        "compressed_gfx": bytes(compressed_gfx),
        "palettes": palettes,
    }


def _wrapped_values(values: list[str], width: int = 16) -> str:
    return "\n".join(
        "    " + ", ".join(values[index : index + width]) + ","
        for index in range(0, len(values), width)
    )


def generate_header(content: dict[str, Any]) -> str:
    resources = "\n".join(
        "    battle_presentation_portrait_resource{ "
        f"{row['portrait_id']}, {row['expression_id']}, "
        f"{row['gfx_offset']}U, {row['compressed_size']}, "
        f"{row['palette_offset']}, "
        f"0x{row['gfx_pointer']:08X}U, "
        f"0x{row['palette_pointer']:08X}U }},"
        for row in content["resources"]
    )
    gfx = _wrapped_values(
        [f"0x{value:02X}" for value in content["compressed_gfx"]]
    )
    palettes = _wrapped_values(
        [f"0x{value:04X}" for value in content["palettes"]]
    )
    return f"""// Generated by tools/generate_butano_battle_portrait_content.py. Do not edit.
{PROVENANCE}
#ifndef KONOHA_GENERATED_BATTLE_PRESENTATION_PORTRAIT_CONTENT_H
#define KONOHA_GENERATED_BATTLE_PRESENTATION_PORTRAIT_CONTENT_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{{

struct battle_presentation_portrait_resource
{{
    std::uint8_t portrait_id;
    std::uint8_t expression_id;
    std::uint32_t gfx_offset;
    std::uint16_t compressed_size;
    std::uint16_t palette_offset;
    std::uint32_t source_gfx_pointer;
    std::uint32_t source_palette_pointer;
}};

inline constexpr std::array<battle_presentation_portrait_resource, {len(content['resources'])}>
        battle_presentation_portrait_resources = {{{{
{resources}
}}}};

alignas(4) inline constexpr std::array<std::uint8_t, {len(content['compressed_gfx'])}>
        battle_presentation_portrait_compressed_gfx = {{{{
{gfx}
}}}};

inline constexpr std::array<std::uint16_t, {len(content['palettes'])}>
        battle_presentation_portrait_palettes = {{{{
{palettes}
}}}};

[[nodiscard]] inline constexpr const battle_presentation_portrait_resource*
battle_presentation_portrait_resource_for(
        std::uint8_t portrait_id,
        std::uint8_t expression_id)
{{
    for(const battle_presentation_portrait_resource& resource :
            battle_presentation_portrait_resources)
    {{
        if(resource.portrait_id == portrait_id &&
                resource.expression_id == expression_id)
        {{
            return &resource;
        }}
    }}
    return nullptr;
}}

}}

#endif
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/"
            "generated_battle_presentation_portrait_content.h"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    content = extract_battle_portrait_content(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_header(content), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
