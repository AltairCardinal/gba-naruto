#!/usr/bin/env python3
"""Generate the remake's copy of the original's baked battlefield overlay.

Round 22 of the S49 reverse engineering established that the original's
move-range screen is not "one extra grid layer" but a **whole battlefield
layout map** the game writes into BG2's tilemap when the battle starts; the
move-range screen merely enables BG2 (``DISPCNT`` bit 10).  Two states of
that layout have been captured as read-only evidence:

``artifacts/s49-original-battlefield-overlay-v1/bg2-tilemap-field.bin``
    the layout as it stands in the plain field frame (BG2 still disabled);
``artifacts/s49-original-battlefield-overlay-v1/bg2-tilemap-movegrid.bin``
    the same tilemap in the frame where BG2 is enabled and the selected
    unit's move range is highlighted.

Both files are 2048 bytes: 32x32 tilemap entries of 16 bits little endian
(tile index 10 bit, palette bank 4 bit, hflip/vflip 2 bit).

This script turns them into a C++ constant the remake can read at runtime::

    butano-sequel/game/include/konoha/generated_battle_battlefield_overlay_content.h

The generator is the only writer of that header.  It re-hashes the source
asset and refuses to emit anything when the asset does not match the signed
manifest, so the header can never silently drift away from the evidence.

Usage::

    /usr/local/bin/python3 tools/generate_butano_battlefield_overlay.py
    /usr/local/bin/python3 tools/generate_butano_battlefield_overlay.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "artifacts/s49-original-battlefield-overlay-v1"
MANIFEST = ASSET_DIR / "manifest.json"
FIELD = ASSET_DIR / "bg2-tilemap-field.bin"
MOVEGRID = ASSET_DIR / "bg2-tilemap-movegrid.bin"
TILES = (
    ROOT
    / "artifacts/s49-original-movegrid-tilemap-v1"
    / "bg2-tiles-4bpp.bin"
)
PALETTE = (
    ROOT
    / "artifacts/s49-original-movegrid-tilemap-v1"
    / "bg2-palette.bin"
)
OUTPUT = (
    ROOT
    / "butano-sequel/game/include/konoha"
    / "generated_battle_battlefield_overlay_content.h"
)
TILES_OUTPUT = (
    ROOT
    / "butano-sequel/game/include/konoha"
    / "generated_battle_battlefield_overlay_tiles.h"
)

#: The files this generator writes.  Declaring them here is what puts the
#: generator into the provenance registry, so the auditor can check the
#: generated header's family declaration instead of reporting the header as
#: an unregistrable product.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/"
    "generated_battle_battlefield_overlay_content.h",
    "butano-sequel/game/include/konoha/"
    "generated_battle_battlefield_overlay_tiles.h",
)

TILEMAP_ENTRIES = 32 * 32
TILEMAP_BYTES = TILEMAP_ENTRIES * 2

#: The original's 32 overlay tiles are 4bpp (two pixels per byte, **the low
#: nibble is the left pixel** -- pinned against the original's own pixels in
#: round 26).  The remake's overlay layer is 8bpp, so the tiles have to be
#: expanded: the original's palette index ``v`` becomes the remake's palette
#: index ``224 + v`` for the eleven colours that carry meaning (1..11), and
#: ``0`` for the transparent entry 0 and for the unused 12..15.
TILE_COUNT = 32
TILE_BYTES_4BPP = 32
TILE_BYTES_8BPP = 64
TILE_BASE_INDEX = 256
PALETTE_BASE = 224
PALETTE_LAST = 11


class GeneratorError(RuntimeError):
    """Raised when the source asset does not match the signed manifest."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_assets() -> tuple[bytes, bytes, dict]:
    """Return the two tilemaps and the manifest, failing closed on drift."""
    if not MANIFEST.is_file():
        raise GeneratorError(f"missing manifest: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for path, key in ((FIELD, "field_tilemap_sha256"),
                      (MOVEGRID, "movegrid_tilemap_sha256")):
        if not path.is_file():
            raise GeneratorError(f"missing asset: {path}")
        data = path.read_bytes()
        if len(data) != TILEMAP_BYTES:
            raise GeneratorError(
                f"{path.name} must be {TILEMAP_BYTES} bytes, got {len(data)}"
            )
        digest = _sha256(data)
        if digest != manifest[key]:
            raise GeneratorError(
                f"{path.name} sha256 {digest} != manifest {key} {manifest[key]}"
            )
    for path, size in ((TILES, TILE_COUNT * TILE_BYTES_4BPP),
                       (PALETTE, 32)):
        if not path.is_file():
            raise GeneratorError(f"missing asset: {path}")
        if path.stat().st_size != size:
            raise GeneratorError(
                f"{path.name} must be {size} bytes, got {path.stat().st_size}"
            )
    return (
        FIELD.read_bytes(),
        MOVEGRID.read_bytes(),
        manifest,
        TILES.read_bytes(),
        PALETTE.read_bytes(),
    )


def _entries(data: bytes) -> list[int]:
    return [int.from_bytes(data[i:i + 2], "little")
            for i in range(0, len(data), 2)]


def _format_entries(entries: list[int]) -> str:
    lines = []
    for row in range(32):
        chunk = entries[row * 32:(row + 1) * 32]
        lines.append("    " + " ".join(f"0x{value:04X}," for value in chunk))
    return "\n".join(lines)


def expand_tiles_8bpp(tiles: bytes, palette: bytes) -> list[int]:
    """Expand the original's 4bpp overlay tiles into the remake's 8bpp form.

    GBA 4bpp stores two pixels per byte and **the low nibble is the left
    pixel** (pinned against the original's own pixels in round 26: inside one
    8 px tile the original shows the fill colour at x=46 and the edge colour
    at x=47, which only the low-nibble-first reading explains).

    The palette index of the original (``v``) becomes the remake's palette
    index ``224 + v`` for the eleven colours that carry meaning; index 0 is
    transparent and the unused 12..15 also carry 0x0000, so they map to 0.
    """
    colours = [
        int.from_bytes(palette[index:index + 2], "little")
        for index in range(0, len(palette), 2)
    ]
    if colours[0] != 0:
        raise GeneratorError("palette entry 0 must be 0x0000 (transparent)")
    expanded: list[int] = []
    for tile in range(TILE_COUNT):
        base = tile * TILE_BYTES_4BPP
        for row in range(8):
            for byte_index in range(4):
                byte = tiles[base + row * 4 + byte_index]
                for nibble in (byte & 0x0F, byte >> 4):
                    if nibble == 0 or nibble > PALETTE_LAST:
                        expanded.append(0)
                    else:
                        expanded.append(PALETTE_BASE + nibble)
    if len(expanded) != TILE_COUNT * TILE_BYTES_8BPP:
        raise GeneratorError("the expanded tile sheet has the wrong size")
    return expanded


def render_tiles(pixels: list[int]) -> str:
    lines = []
    for tile in range(TILE_COUNT):
        lines.append("    // tile %d" % (TILE_BASE_INDEX + tile))
        for row in range(8):
            chunk = pixels[
                tile * TILE_BYTES_8BPP + row * 8: tile * TILE_BYTES_8BPP
                + row * 8 + 8
            ]
            lines.append("    " + " ".join(f"{value}," for value in chunk))
    body = "\n".join(lines)
    return f"""// Generated by tools/generate_butano_battlefield_overlay.py. Do not edit.
// provenance-carrier: c-header-comment
// reverse-source: not-applicable - the tiles were dumped from the original's VRAM at runtime into artifacts/s49-original-movegrid-tilemap-v1/, which is a remake-tree runtime receipt and not a reverse-tree artifact family
// reverse-source-rom: none
#ifndef KONOHA_GENERATED_BATTLE_BATTLEFIELD_OVERLAY_TILES_H
#define KONOHA_GENERATED_BATTLE_BATTLEFIELD_OVERLAY_TILES_H

#include <array>
#include <cstdint>

namespace konoha
{{

// The original's 32 overlay tiles (BG2, tiles 256..287), expanded from 4bpp
// to the remake's 8bpp layer.  Tile k here is the original's tile 256+k, so
// the original's tilemap entries can be used with the index shifted by 256.
//
// The pixel values are the REMAKE's palette indices: 0 is transparent and
// 225..235 carry the original's bank-12 colours 1..11.
inline constexpr int battle_battlefield_overlay_tile_count = {TILE_COUNT};
inline constexpr int battle_battlefield_overlay_tiles_8bpp_bytes = {TILE_BYTES_8BPP};
inline constexpr int battle_battlefield_overlay_tiles_8bpp_base_index = {TILE_BASE_INDEX};
inline constexpr int battle_battlefield_overlay_tiles_8bpp_palette_base = {PALETTE_BASE};
inline constexpr int battle_battlefield_overlay_tiles_8bpp_palette_last = {PALETTE_LAST};

inline constexpr std::array<std::uint8_t, {TILE_COUNT * TILE_BYTES_8BPP}>
        battle_battlefield_overlay_tiles_8bpp = {{
{body}
}};

}}
#endif
"""


def render(field: bytes, movegrid: bytes, manifest: dict) -> str:
    field_entries = _entries(field)
    movegrid_entries = _entries(movegrid)
    changed = [
        index
        for index in range(TILEMAP_ENTRIES)
        if field_entries[index] != movegrid_entries[index]
    ]
    if len(changed) != int(manifest["changed_entries_vs_field"]):
        raise GeneratorError(
            "changed entry count "
            f"{len(changed)} != manifest {manifest['changed_entries_vs_field']}"
        )
    for entry in field_entries + movegrid_entries:
        if entry & 0x0C00:
            raise GeneratorError(
                "the captured layout uses hflip/vflip, which the remake's "
                "8bpp layer cannot express yet"
            )
    return f"""// Generated by tools/generate_butano_battlefield_overlay.py. Do not edit.
// provenance-carrier: c-header-comment
// reverse-source: not-applicable - the layout was dumped from the original's VRAM at runtime into artifacts/s49-original-battlefield-overlay-v1/, which is a remake-tree runtime receipt and not a reverse-tree artifact family
// reverse-source-rom: none
#ifndef KONOHA_GENERATED_BATTLE_BATTLEFIELD_OVERLAY_CONTENT_H
#define KONOHA_GENERATED_BATTLE_BATTLEFIELD_OVERLAY_CONTENT_H

#include <array>
#include <cstdint>

namespace konoha
{{

// The original's BG2 tilemap is 32x32 entries of 16 bits: tile index 10 bit,
// palette bank 4 bit, hflip/vflip 2 bit.  Every captured entry uses palette
// bank 12 and no flip, so only the low 10 bits carry meaning for the remake.
inline constexpr int battle_battlefield_overlay_tile_mask = 0x03FF;
inline constexpr int battle_battlefield_overlay_tilemap_entries = {TILEMAP_ENTRIES};
inline constexpr int battle_battlefield_overlay_tilemap_columns = 32;
inline constexpr int battle_battlefield_overlay_tilemap_rows = 32;
// The layout covers a 16x16 grid of 16x16 px logical cells (2x2 tiles each).
inline constexpr int battle_battlefield_overlay_logical_columns = 16;
inline constexpr int battle_battlefield_overlay_logical_rows = 16;
inline constexpr int battle_battlefield_overlay_first_tile = 256;
inline constexpr int battle_battlefield_overlay_tiles_8bpp_count = 32;
inline constexpr int battle_battlefield_overlay_changed_entries = {len(changed)};
inline constexpr char battle_battlefield_overlay_field_sha256[] =
        "{manifest['field_tilemap_sha256']}";
inline constexpr char battle_battlefield_overlay_movegrid_sha256[] =
        "{manifest['movegrid_tilemap_sha256']}";

// The field frame layout: BG2 still disabled, the baked battlefield web.
inline constexpr std::array<std::uint16_t, {TILEMAP_ENTRIES}>
        battle_battlefield_overlay_tilemap_field = {{
{_format_entries(field_entries)}
}};

// The move-range frame layout: the same web with the selected unit's move
// range highlighted.
inline constexpr std::array<std::uint16_t, {TILEMAP_ENTRIES}>
        battle_battlefield_overlay_tilemap_movegrid = {{
{_format_entries(movegrid_entries)}
}};

}}
#endif
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the generated header is not up to date",
    )
    args = parser.parse_args(argv)
    try:
        field, movegrid, manifest, tiles, palette = load_assets()
        content = render(field, movegrid, manifest)
        tile_content = render_tiles(expand_tiles_8bpp(tiles, palette))
    except GeneratorError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    products = ((OUTPUT, content), (TILES_OUTPUT, tile_content))
    if args.check:
        problems = []
        for path, expected in products:
            if not path.is_file():
                problems.append(f"missing generated header: {path}")
            elif path.read_text(encoding="utf-8") != expected:
                problems.append(
                    f"generated header is stale: {path}\n"
                    "run tools/generate_butano_battlefield_overlay.py"
                )
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"{len(products)} generated headers are up to date")
        return 0
    for path, data in products:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        print(f"wrote {path} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
