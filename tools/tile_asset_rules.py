#!/usr/bin/env python3
"""Battle-map tile-asset rules: parse, measure, and dry-run a single-cell swap.

The rules implemented here were reverse engineered from
``third_party/konoha-workshop/源码/editor/asset_imports.js`` (``P.setTileAsset``
and ``P.buildExtras``) and then re-verified against this repository's own ROM
(``rom/base.gba``).  See ``notes/tile-asset-rules-20261020.md`` for the
per-rule evidence.

Map descriptor table
---------------------
File offset ``0x53D910`` (ARM ``0x0853D910``), 32 bytes per entry, entries
0..46 are the 47 valid battle maps (entry 47 is the start of a different
table and fails the size checks).

===========  ========  =====================================================
Offset       Type      Meaning
===========  ========  =====================================================
+0x00        u16       raw width      (cell columns = raw_width // 4)
+0x02        u16       raw height     (cell rows    = raw_height // 2)
+0x04        u32 ptr   tile graphics  (LZ77)
+0x08        u32 ptr   colour palette (LZ77)
+0x0C        u32 ptr   layer 0 tilemap(LZ77)
+0x10        u32 ptr   layer 1 tilemap(LZ77, 0 = absent)
+0x14        u32 ptr   metatile table (LZ77)
+0x18        u32 ptr   terrain table  (LZ77)
+0x1C        u8        story background id
===========  ========  =====================================================

A *cell* is one 32x16 pixel slot of the map; a cell owns two 16x16
metatiles, so the two layers hold 2 u16 metatile indices per cell row and
the terrain block holds 2 bytes per cell.

Usage
-----
    python tools/tile_asset_rules.py rom/base.gba --stage 40
    python tools/tile_asset_rules.py rom/base.gba --stage 40 --x 3 --y 5
    python tools/tile_asset_rules.py rom/base.gba --all
    python tools/tile_asset_rules.py rom/base.gba --stage 40 --json build/x.json

``--x/--y`` only *plans*; the tool never writes to the ROM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from dataclasses import dataclass, field

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.lib.io import write_text  # noqa: E402
from tools.lib.lz77 import compress_literal, decompress as _lz77_decompress  # noqa: E402

ROM_BASE = 0x08000000
MAP_TABLE = 0x53D910
MAP_ENTRY_SIZE = 32
MAP_ENTRY_COUNT = 47          # entries 0..46 are valid; 47+ belongs to another table

TILE_BYTES = 32               # 8x8 pixels, 4bpp
METATILE_BYTES = 8            # 4 u16 tile references
BANK_BYTES = 32               # 16 colours * 2 bytes (BGR555)
BANK_COUNT = 16               # GBA BG palette RAM = 512 bytes = 16 banks
PALETTE_BYTES = BANK_COUNT * BANK_BYTES
TILE_LIMIT = 1024             # tile index field is 10 bits
METATILE_LIMIT = 1024         # editor-side ceiling on the metatile table
TERRAIN_TYPES = 16

CELL_W_PX = 32
CELL_H_PX = 16
ASSET_PIXELS = CELL_W_PX * CELL_H_PX

# EWRAM destinations used by the game loader (0x08068FF0), see the note file.
EWRAM_LAYER0 = 0x0201BE2C
EWRAM_LAYER1 = 0x0201CE2C
EWRAM_METATILES = 0x0201DE2C
PALRAM = 0x05000000

BLOCK_FIELDS = (
    ("gfx", 0x04),
    ("palette", 0x08),
    ("layer0", 0x0C),
    ("layer1", 0x10),
    ("metatiles", 0x14),
    ("terrain", 0x18),
)


# ---------------------------------------------------------------------------
# LZ77
# ---------------------------------------------------------------------------

def lz77_decompress(rom: bytes, offset: int) -> bytes:
    """Decompress a GBA LZ77 (type 0x10) block stored at ``offset``.

    Thin wrapper around the repository's shared codec in ``tools/lib/lz77.py``.
    """
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError(f"LZ77 block offset 0x{offset:X} outside ROM")
    return _lz77_decompress(rom, offset)


def u16(buf: bytes, offset: int) -> int:
    return buf[offset] | buf[offset + 1] << 8


def u16_list(buf: bytes) -> list[int]:
    return [u16(buf, i) for i in range(0, len(buf), 2)]


# ---------------------------------------------------------------------------
# Map entry
# ---------------------------------------------------------------------------

@dataclass
class MapEntry:
    index: int
    descriptor_offset: int
    raw_width: int
    raw_height: int
    background_id: int
    pointers: dict
    gfx: bytes
    palette: bytes
    layer0: bytes
    layer1: bytes | None
    metatiles: bytes
    terrain: bytes

    # -- geometry -------------------------------------------------------
    @property
    def cell_w(self) -> int:
        """Cells per row (raw width // 4)."""
        return self.raw_width // 4

    @property
    def cell_h(self) -> int:
        """Cell rows (raw height // 2)."""
        return self.raw_height // 2

    @property
    def cell_count(self) -> int:
        return self.cell_w * self.cell_h

    # -- block sizes ----------------------------------------------------
    @property
    def gfx_tiles(self) -> int:
        return len(self.gfx) // TILE_BYTES

    @property
    def metatile_count(self) -> int:
        return len(self.metatiles) // METATILE_BYTES

    @property
    def palette_banks(self) -> int:
        """Colour banks physically present in the ROM palette block."""
        return len(self.palette) // BANK_BYTES

    @property
    def has_layer1(self) -> bool:
        return self.layer1 is not None

    # -- structure checks ------------------------------------------------
    def structural_problems(self) -> list[str]:
        """Every size relation that must hold for a well formed map entry."""
        problems: list[str] = []
        if self.raw_width % 4:
            problems.append(f"raw width {self.raw_width} is not a multiple of 4")
        if self.raw_height % 2:
            problems.append(f"raw height {self.raw_height} is not a multiple of 2")
        if len(self.gfx) % TILE_BYTES:
            problems.append(f"gfx block {len(self.gfx)} B is not a multiple of {TILE_BYTES}")
        if len(self.metatiles) % METATILE_BYTES:
            problems.append(
                f"metatile block {len(self.metatiles)} B is not a multiple of {METATILE_BYTES}")
        expect_terrain = self.cell_count * 2
        if len(self.terrain) != expect_terrain:
            problems.append(
                f"terrain block {len(self.terrain)} B != cell_w*cell_h*2 = {expect_terrain}")
        expect_layer = self.cell_count * 4
        if len(self.layer0) != expect_layer:
            problems.append(
                f"layer0 block {len(self.layer0)} B != cell_w*cell_h*4 = {expect_layer}")
        if self.layer1 is not None and len(self.layer1) != expect_layer:
            problems.append(
                f"layer1 block {len(self.layer1)} B != cell_w*cell_h*4 = {expect_layer}")
        return problems

    # -- derived views ----------------------------------------------------
    def layer_indices(self) -> list[int]:
        """Metatile indices referenced by layer0 and layer1."""
        entries = u16_list(self.layer0)
        if self.layer1 is not None:
            entries += u16_list(self.layer1)
        return entries

    def used_banks(self) -> set[int]:
        """Colour banks (bits 12-15) used by every metatile the layers point at.

        This mirrors the third-party rule: only metatiles that are actually
        referenced by a layer can reserve a colour bank.
        """
        banks: set[int] = set()
        count = self.metatile_count
        for meta in self.layer_indices():
            if meta >= count:
                continue
            for j in range(4):
                banks.add(u16(self.metatiles, meta * METATILE_BYTES + j * 2) >> 12)
        return banks

    def free_banks(self) -> list[int]:
        used = self.used_banks()
        return [b for b in range(BANK_COUNT) if b not in used]

    def blank_tile(self) -> int | None:
        """Index of the first all-zero gfx tile (reusable as a clear tile)."""
        for t in range(self.gfx_tiles):
            if not any(self.gfx[t * TILE_BYTES:(t + 1) * TILE_BYTES]):
                return t
        return None

    def max_tile_index(self) -> int:
        """Highest gfx tile index referenced by any layer-referenced metatile."""
        count = self.metatile_count
        best = -1
        for meta in set(self.layer_indices()):
            if meta >= count:
                continue
            for j in range(4):
                best = max(best, u16(self.metatiles, meta * METATILE_BYTES + j * 2) & 0x03FF)
        return best

    def terrain_flags(self) -> int:
        """Bitwise OR of every terrain flag byte (byte 1 of each cell)."""
        flags = 0
        for i in range(1, len(self.terrain), 2):
            flags |= self.terrain[i]
        return flags


def load_entry(rom: bytes, index: int) -> MapEntry:
    """Parse one 32-byte map descriptor and decompress its six LZ77 blocks."""
    base = MAP_TABLE + index * MAP_ENTRY_SIZE
    if base + MAP_ENTRY_SIZE > len(rom):
        raise ValueError(f"map descriptor {index} outside ROM")
    raw_width = u16(rom, base)
    raw_height = u16(rom, base + 2)
    background_id = rom[base + 0x1C]
    pointers: dict[str, int | None] = {}
    blocks: dict[str, bytes] = {}
    for name, delta in BLOCK_FIELDS:
        ptr = struct.unpack_from("<I", rom, base + delta)[0]
        if ptr == 0:
            pointers[name] = None
            blocks[name] = b""
            continue
        file_off = ptr - ROM_BASE
        pointers[name] = file_off
        blocks[name] = lz77_decompress(rom, file_off)
    return MapEntry(
        index=index,
        descriptor_offset=base,
        raw_width=raw_width,
        raw_height=raw_height,
        background_id=background_id,
        pointers=pointers,
        gfx=blocks["gfx"],
        palette=blocks["palette"],
        layer0=blocks["layer0"],
        layer1=blocks["layer1"] if blocks["layer1"] else None,
        metatiles=blocks["metatiles"],
        terrain=blocks["terrain"],
    )


def iter_entries(rom: bytes):
    for index in range(MAP_ENTRY_COUNT):
        yield load_entry(rom, index)


# ---------------------------------------------------------------------------
# Occupancy report
# ---------------------------------------------------------------------------

def analyze(entry: MapEntry) -> dict:
    """Measure colour bank / gfx tile / metatile occupancy for one map."""
    used = entry.used_banks()
    free = [b for b in range(BANK_COUNT) if b not in used]
    blank = entry.blank_tile()
    per_cell_tiles = 8                      # 2 halves x (2x2) 8x8 tiles
    per_cell_metatiles = 3 if entry.has_layer1 else 2
    tile_headroom = (TILE_LIMIT - entry.gfx_tiles) // per_cell_tiles
    metatile_headroom = (METATILE_LIMIT - entry.metatile_count) // per_cell_metatiles
    if blank is None and entry.has_layer1:
        tile_headroom = min(tile_headroom, (TILE_LIMIT - entry.gfx_tiles - 1) // per_cell_tiles)
    bank_headroom = len(free)
    binding = min(tile_headroom, metatile_headroom, bank_headroom)
    reasons = [name for name, value in (("tiles", tile_headroom),
                                        ("metatiles", metatile_headroom),
                                        ("banks", bank_headroom)) if value == binding]
    return {
        "index": entry.index,
        "descriptor_offset": entry.descriptor_offset,
        "raw_width": entry.raw_width,
        "raw_height": entry.raw_height,
        "cell_w": entry.cell_w,
        "cell_h": entry.cell_h,
        "cell_count": entry.cell_count,
        "background_id": entry.background_id,
        "structural_problems": entry.structural_problems(),
        "gfx": {
            "bytes": len(entry.gfx),
            "tiles": entry.gfx_tiles,
            "limit": TILE_LIMIT,
            "free_tiles": TILE_LIMIT - entry.gfx_tiles,
            "max_referenced_tile": entry.max_tile_index(),
            "blank_tile": blank,
        },
        "palette": {
            "bytes": len(entry.palette),
            "banks_present": entry.palette_banks,
            "banks_writable": BANK_COUNT,
        },
        "layer0": {
            "bytes": len(entry.layer0),
            "entries": len(entry.layer0) // 2,
            "ewram_dest": f"0x{EWRAM_LAYER0:08X}",
        },
        "layer1": {
            "present": entry.has_layer1,
            "bytes": len(entry.layer1) if entry.layer1 else 0,
            "entries": len(entry.layer1) // 2 if entry.layer1 else 0,
            "ewram_dest": f"0x{EWRAM_LAYER1:08X}",
        },
        "metatiles": {
            "bytes": len(entry.metatiles),
            "count": entry.metatile_count,
            "limit": METATILE_LIMIT,
            "free": METATILE_LIMIT - entry.metatile_count,
            "ewram_dest": f"0x{EWRAM_METATILES:08X}",
        },
        "terrain": {
            "bytes": len(entry.terrain),
            "cells": len(entry.terrain) // 2,
            "flag_bits": entry.terrain_flags(),
        },
        "banks": {
            "used": sorted(used),
            "used_count": len(used),
            "free": free,
            "free_count": len(free),
        },
        "headroom_cells": {
            "tiles": tile_headroom,
            "metatiles": metatile_headroom,
            "banks": bank_headroom,
            "binding": binding,
            "binding_reason": "/".join(reasons),
        },
    }


# ---------------------------------------------------------------------------
# Single cell replacement plan
# ---------------------------------------------------------------------------

@dataclass
class Limit:
    code: str
    ok: bool
    detail: str


def build_tile_payload(indices: bytes, half: int, ty: int, tx: int) -> bytes:
    """Encode one 8x8 4bpp tile from the 32x16 asset index buffer.

    Mirrors the third-party rule: the tile at (half, ty, tx) samples the
    asset rows ``ty*8 .. ty*8+7`` and columns ``half*16+tx*8 .. +8``.
    """
    out = bytearray()
    for yy in range(8):
        row = (ty * 8 + yy) * CELL_W_PX + half * 16 + tx * 8
        for xx in range(0, 8, 2):
            out.append((indices[row + xx] & 0x0F) | ((indices[row + xx + 1] & 0x0F) << 4))
    return bytes(out)


def plan_cell(entry: MapEntry, x: int, y: int, terrain_type: int = 0,
              asset: bytes | None = None) -> dict:
    """Dry-run the third-party single-cell replacement. Never touches the ROM.

    The algorithm (verbatim order from ``P.mapData``):

    1. collect the colour banks already used by layer-referenced metatiles;
    2. give the new cell the lowest free bank and write its 16 colours there;
    3. if layer 1 exists, reuse an all-zero gfx tile and append one *clear*
       metatile pointing at it;
    4. append 2 x (2x2) new gfx tiles per half (8 tiles, 32x16 px cell);
    5. append 2 metatiles whose four references carry the new bank;
    6. rewrite the two layer0 indices and the two layer1 indices;
    7. write the 2 terrain bytes of the cell.
    """
    limits: list[Limit] = []
    result: dict = {
        "map_index": entry.index,
        "cell": [x, y],
        "cell_count": entry.cell_count,
        "limits": [],
    }

    if not (0 <= x < entry.cell_w and 0 <= y < entry.cell_h):
        limits.append(Limit("out_of_range", False,
                            f"cell ({x},{y}) outside {entry.cell_w}x{entry.cell_h} grid"))
        result["limits"] = [vars(limit) for limit in limits]
        return result
    if not (0 <= terrain_type < TERRAIN_TYPES):
        limits.append(Limit("terrain_out_of_range", False,
                            f"terrain type {terrain_type} outside 0..{TERRAIN_TYPES - 1}"))

    # --- step 1/2: colour bank -------------------------------------------
    used = entry.used_banks()
    free = [b for b in range(BANK_COUNT) if b not in used]
    bank = free[0] if free else None
    if bank is None:
        limits.append(Limit("bank_exhausted", False,
                            "all 16 colour banks are already used by this map"))
    else:
        limits.append(Limit("bank_exhausted", True,
                            f"bank {bank} of 16 is free ({len(free)} free)"))

    # --- step 3: layer 1 clear metatile ---------------------------------
    gfx_tiles = entry.gfx_tiles
    metatile_count = entry.metatile_count
    clear_tile = entry.blank_tile()
    new_blank_tile = False
    if entry.has_layer1:
        if clear_tile is None:
            if gfx_tiles >= TILE_LIMIT:
                limits.append(Limit("tile_space", False,
                                    "no all-zero gfx tile and the 1024 tile limit is reached"))
                clear_tile = None
            else:
                clear_tile = gfx_tiles
                new_blank_tile = True
                limits.append(Limit("tile_space", True,
                                    f"appending blank tile {clear_tile} for the layer1 clear metatile"))
        else:
            limits.append(Limit("tile_space", True,
                                f"reusing blank gfx tile {clear_tile} for the layer1 clear metatile"))
        if metatile_count >= METATILE_LIMIT:
            limits.append(Limit("metatile_space", False,
                                "metatile table is already at the 1024 limit"))
        else:
            limits.append(Limit("metatile_space", True,
                                f"metatile {metatile_count} of 1024 is free"))
    else:
        limits.append(Limit("tile_space", True,
                            f"layer 1 absent: no clear metatile and no blank tile needed"))
        limits.append(Limit("metatile_space", True,
                            f"metatile {metatile_count} of 1024 is free"))

    # --- step 4/5: new tiles and metatiles ------------------------------
    tiles_needed = 8 + (1 if new_blank_tile else 0)
    tiles_free = TILE_LIMIT - gfx_tiles
    if tiles_free < tiles_needed:
        limits.append(Limit("tile_space", False,
                            f"need {tiles_needed} gfx tiles, only {tiles_free} of 1024 free"))
    else:
        limits.append(Limit("tile_space", True,
                            f"{tiles_needed} gfx tiles needed, {tiles_free} of 1024 free"))

    metatiles_needed = 2 + (1 if entry.has_layer1 else 0)
    metatiles_free = METATILE_LIMIT - metatile_count
    if metatiles_free < metatiles_needed:
        limits.append(Limit("metatile_space", False,
                            f"need {metatiles_needed} metatiles, only {metatiles_free} of 1024 free"))
    else:
        limits.append(Limit("metatile_space", True,
                            f"{metatiles_needed} metatiles needed, {metatiles_free} of 1024 free"))

    # The third-party appends the layer1 clear metatile *before* the two
    # content metatiles, and the blank gfx tile before the eight content
    # tiles, so the new indices are not contiguous in the same order.
    blank_offset = 1 if new_blank_tile else 0
    content_tile_base = gfx_tiles + blank_offset
    content_tiles = [content_tile_base + half * 4 + ty * 2 + tx
                     for half in range(2) for ty in range(2) for tx in range(2)]
    gfx_tiles_appended = list(range(gfx_tiles, gfx_tiles + tiles_needed))
    clear_metatile = metatile_count if entry.has_layer1 else None
    content_metatile_base = metatile_count + (1 if entry.has_layer1 else 0)
    content_metatiles = [content_metatile_base, content_metatile_base + 1]

    # --- step 6: layer rewrites -----------------------------------------
    layer_at = (y * entry.cell_w * 2 + x * 2)
    layer_byte_offset = layer_at * 2
    terrain_pos = (y * entry.cell_w + x) * 2

    plan = {
        "bank": bank,
        "palette_byte_offset": bank * BANK_BYTES if bank is not None else None,
        "palette_bytes_after": max(len(entry.palette), PALETTE_BYTES),
        "gfx_tiles_appended": gfx_tiles_appended,
        "gfx_content_tiles": content_tiles,
        "gfx_bytes_after": (gfx_tiles + tiles_needed) * TILE_BYTES,
        "blank_tile": clear_tile,
        "blank_tile_appended": new_blank_tile,
        "clear_metatile": clear_metatile,
        "metatiles_appended": ([clear_metatile] if clear_metatile is not None else [])
                             + content_metatiles,
        "metatile_content": content_metatiles,
        "metatile_bytes_after": (metatile_count + metatiles_needed) * METATILE_BYTES,
        "layer0_u16_offset": layer_at,
        "layer0_byte_offset": layer_byte_offset,
        "layer0_new_indices": content_metatiles,
        "layer1_u16_offset": layer_at,
        "layer1_byte_offset": layer_byte_offset,
        "layer1_new_index": clear_metatile,
        "terrain_byte_offset": terrain_pos,
        "terrain_type": terrain_type,
        "terrain_flag_byte_cleared_to": 0,
    }

    if asset is not None:
        payloads = []
        for half in range(2):
            for ty in range(2):
                for tx in range(2):
                    payloads.append(build_tile_payload(asset, half, ty, tx))
        plan["tile_payloads"] = [p.hex() for p in payloads]

    # run the whole algorithm in memory and re-parse the result
    if all(limit.ok for limit in limits):
        try:
            simulation = simulate_replacement(entry, x, y, terrain_type, asset)
        except ValueError as exc:
            limits.append(Limit("simulated_structure", False, f"simulation refused: {exc}"))
        else:
            problems = check_simulated(entry, simulation)
            plan["simulated_raw_sizes"] = simulation["raw_sizes"]
            plan["simulated_compressed_sizes"] = simulation["compressed_sizes"]
            plan["simulated_problems"] = problems
            if problems:
                limits.append(Limit("simulated_structure", False, "; ".join(problems)))
            else:
                limits.append(Limit("simulated_structure", True,
                                    "simulated blocks re-parse cleanly"
                                    " (indices, tiles and banks in range)"))

    result["plan"] = plan
    result["limits"] = [vars(limit) for limit in limits]
    result["ok"] = all(limit.ok for limit in limits)
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def rom_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_map_report(entry: MapEntry, info: dict) -> None:
    print(f"=== stage {entry.index} (map descriptor #{entry.index}) ===")
    print(f"  descriptor     : file 0x{entry.descriptor_offset:06X} "
          f"(ARM 0x{ROM_BASE + entry.descriptor_offset:08X})")
    print(f"  raw size       : {entry.raw_width} x {entry.raw_height}"
          f"  ->  cell grid {entry.cell_w} x {entry.cell_h} "
          f"({entry.cell_count} cells, each {CELL_W_PX}x{CELL_H_PX} px)")
    print(f"  background id  : {entry.background_id}")
    problems = info["structural_problems"]
    print(f"  structure      : {'OK (all size relations hold)' if not problems else problems}")
    gfx = info["gfx"]
    print(f"  gfx tiles      : {gfx['tiles']} used / {TILE_LIMIT}"
          f"   free {gfx['free_tiles']}"
          f"   max referenced tile {gfx['max_referenced_tile']}")
    print(f"  blank gfx tile : {gfx['blank_tile'] if gfx['blank_tile'] is not None else 'none'}"
          f"   (reusable as layer1 clear tile)")
    print(f"  metatiles      : {info['metatiles']['count']} used / {METATILE_LIMIT}"
          f"   free {info['metatiles']['free']}")
    print(f"  colour banks   : {info['banks']['used_count']} used {info['banks']['used']}"
          f"   free {info['banks']['free_count']} {info['banks']['free']}")
    print(f"  palette block  : {info['palette']['bytes']} B"
          f" = {info['palette']['banks_present']} banks present in ROM"
          f" (writable {info['palette']['banks_writable']})")
    print(f"  layer0         : {info['layer0']['bytes']} B"
          f" = {info['layer0']['entries']} u16 -> {info['layer0']['ewram_dest']}")
    if info["layer1"]["present"]:
        print(f"  layer1         : {info['layer1']['bytes']} B"
              f" = {info['layer1']['entries']} u16 -> {info['layer1']['ewram_dest']}")
    else:
        print(f"  layer1         : absent (no clear metatile is created)")
    print(f"  terrain        : {info['terrain']['bytes']} B"
          f" = {info['terrain']['cells']} cells x 2 B"
          f"   flag bits seen 0x{info['terrain']['flag_bits']:02X}")
    head = info["headroom_cells"]
    print(f"  headroom       : {head['tiles']} cells by tiles, "
          f"{head['metatiles']} cells by metatiles, "
          f"{head['banks']} cells by colour banks"
          f"  -> binding limit: {head['binding_reason']} ({head['binding']})")
    print("                   (one bank per *distinct* palette; cells that reuse the"
          " same 16 colours share a bank)")


def print_plan(entry: MapEntry, plan_result: dict) -> None:
    print(f"--- replacement plan for cell ({plan_result['cell'][0]},"
          f"{plan_result['cell'][1]}) of stage {entry.index} (dry run, ROM untouched) ---")
    for limit in plan_result["limits"]:
        mark = "PASS" if limit["ok"] else "FAIL"
        print(f"  [{mark}] {limit['code']:<20s} {limit['detail']}")
    if "plan" not in plan_result:
        return
    plan = plan_result["plan"]
    print(f"  colour bank    : {plan['bank']}"
          f" (palette byte offset {plan['palette_byte_offset']}"
          f", palette block -> {plan['palette_bytes_after']} B)")
    print(f"  new gfx tiles  : {plan['gfx_tiles_appended']}"
          f" (content tiles {plan['gfx_content_tiles']},"
          f" gfx block -> {plan['gfx_bytes_after']} B)")
    print(f"  new metatiles  : {plan['metatiles_appended']}"
          f" (content {plan['metatile_content']},"
          f" metatile block -> {plan['metatile_bytes_after']} B)")
    print(f"  layer0 write   : u16 index {plan['layer0_u16_offset']}"
          f" (byte {plan['layer0_byte_offset']})"
          f" -> {plan['layer0_new_indices']}")
    if plan["layer1_new_index"] is None:
        print("  layer1 write   : none (layer 1 absent)")
    else:
        print(f"  layer1 write   : u16 index {plan['layer1_u16_offset']}"
              f" (byte {plan['layer1_byte_offset']})"
              f" -> clear metatile {plan['layer1_new_index']}")
    print(f"  terrain write  : byte {plan['terrain_byte_offset']}"
          f" -> [{plan['terrain_type']}, {plan['terrain_flag_byte_cleared_to']}]")
    if plan.get("tile_payloads"):
        print("  tile payloads  :")
        content = plan["gfx_content_tiles"]
        for i, hexed in enumerate(plan["tile_payloads"]):
            tile_no = content[i] if i < len(content) else i
            print(f"    tile {tile_no}: {hexed}")
    if plan.get("simulated_compressed_sizes"):
        raw = plan["simulated_raw_sizes"]
        comp = plan["simulated_compressed_sizes"]
        print("  simulated blocks (raw -> LZ77 literal):")
        for name in ("gfx", "palette", "layer0", "layer1", "metatiles", "terrain"):
            if name in raw:
                print(f"    {name:<9s}: {raw[name]:>6} -> {comp[name]:>6} B")
    print(f"  verdict        : {'OK - all limits satisfied' if plan_result['ok'] else 'REJECTED'}")


def synthetic_entry(gfx_tiles: int, metatiles: int, banks: list[int],
                    cell_w: int = 4, cell_h: int = 4,
                    blank: bool = True) -> MapEntry:
    """Build a fake map entry, used by ``--selftest`` to exercise the limits.

    Every metatile ``0..len(banks)-1`` carries one colour bank and *is*
    referenced by the layers, so the "used bank" set is exactly ``banks``.
    """
    gfx = bytes(TILE_BYTES * gfx_tiles) if blank else bytes(
        bytearray([1]) * TILE_BYTES * gfx_tiles)
    met = bytearray(METATILE_BYTES * metatiles)
    for i, bank in enumerate(banks):
        for j in range(4):
            met[i * METATILE_BYTES + j * 2 + 1] = (bank << 4) & 0xFF
    layer = bytearray()
    for i in range(cell_w * cell_h * 2):
        index = i % max(len(banks), 1)
        layer += bytes([index & 0xFF, (index >> 8) & 0xFF])
    return MapEntry(
        index=0, descriptor_offset=0, raw_width=cell_w * 4, raw_height=cell_h * 2,
        background_id=1, pointers={}, gfx=gfx, palette=bytes(384),
        layer0=bytes(layer), layer1=bytes(layer), metatiles=bytes(met),
        terrain=bytes(cell_w * cell_h * 2))


def run_selftest() -> int:
    """Exercise every documented failure condition on synthetic entries."""
    cases = (
        ("case A: 1024 gfx tiles (tile space exhausted)",
         synthetic_entry(1024, 16, [0])),
        ("case B: 1024 metatiles (metatile space exhausted)",
         synthetic_entry(10, 1024, [0])),
        ("case C: all 16 colour banks used",
         synthetic_entry(10, 16, list(range(16)))),
        ("case D: no all-zero gfx tile and the tile limit reached",
         synthetic_entry(1024, 16, [0], blank=False)),
    )
    failures = 0
    for title, entry in cases:
        print(f"--- {title} ---")
        result = plan_cell(entry, 0, 0)
        for limit in result["limits"]:
            mark = "PASS" if limit["ok"] else "FAIL"
            print(f"  [{mark}] {limit['code']:<18s} {limit['detail']}")
        print(f"  verdict: {'OK' if result['ok'] else 'REJECTED'}")
        if result["ok"]:
            failures += 1
            print("  !! expected this synthetic case to be rejected")
    print(f"\nselftest: {len(cases) - failures}/{len(cases)} synthetic cases rejected as expected")
    return 1 if failures else 0


def simulate_replacement(entry: MapEntry, x: int, y: int, terrain_type: int = 0,
                         asset: bytes | None = None,
                         palette: list[int] | None = None) -> dict:
    """Run the third-party replacement algorithm in memory and return the blocks.

    Nothing is written to the ROM.  The result is the set of blocks that
    ``P.buildExtras`` would compress and append, so the plan can quote the
    exact compressed sizes and the result can be re-parsed for consistency.

    ``palette`` is the 16 BGR555 colours of the new bank; ``asset`` is the
    32x16 palette-index buffer.  When ``asset`` is omitted the eight new tiles
    are zero filled, which is enough for size accounting.
    """
    gfx = bytearray(entry.gfx)
    pal = bytearray(entry.palette)
    meta = bytearray(entry.metatiles)
    layer0 = bytearray(entry.layer0)
    layer1 = bytearray(entry.layer1) if entry.layer1 is not None else None
    terrain = bytearray(entry.terrain)

    # 1. colour banks used by layer-referenced metatiles
    used: set[int] = set()
    for layer in (layer0, layer1):
        if layer is None:
            continue
        for k in range(0, len(layer), 2):
            m = layer[k] | layer[k + 1] << 8
            if m * METATILE_BYTES + METATILE_BYTES > len(meta):
                continue
            for j in range(4):
                off = m * METATILE_BYTES + j * 2
                used.add((meta[off] | meta[off + 1] << 8) >> 12)
    bank = next((b for b in range(BANK_COUNT) if b not in used), None)
    if bank is None:
        raise ValueError("all 16 colour banks are already used by this map")

    # 2. palette: pad to 16 banks and write the new colours
    while len(pal) < PALETTE_BYTES:
        pal.append(0)
    colors = palette or [0] * 16
    for i in range(16):
        value = colors[i] if i < len(colors) else 0
        pal[bank * BANK_BYTES + i * 2] = value & 0xFF
        pal[bank * BANK_BYTES + i * 2 + 1] = (value >> 8) & 0xFF

    # 3. layer 1 clear metatile
    clear_metatile = None
    blank_tile = None
    if layer1 is not None:
        blank_tile = entry.blank_tile()
        if blank_tile is None:
            blank_tile = len(gfx) // TILE_BYTES
            gfx += bytes(TILE_BYTES)
        clear_metatile = len(meta) // METATILE_BYTES
        for _ in range(4):
            meta += bytes([blank_tile & 0xFF, (blank_tile >> 8) & 0xFF])

    # 4/5. eight new gfx tiles and two new metatiles
    content_metatiles = []
    content_tiles = []
    for half in range(2):
        words = []
        for ty in range(2):
            for tx in range(2):
                tile = len(gfx) // TILE_BYTES
                gfx += (build_tile_payload(asset, half, ty, tx)
                        if asset is not None else bytes(TILE_BYTES))
                content_tiles.append(tile)
                words.append(tile | (bank << 12))
        meta_index = len(meta) // METATILE_BYTES
        for word in words:
            meta += bytes([word & 0xFF, (word >> 8) & 0xFF])
        content_metatiles.append(meta_index)

    # 6. layer rewrites
    base = (y * entry.cell_w * 2 + x * 2) * 2
    for h in range(2):
        at = base + h * 2
        layer0[at:at + 2] = bytes([content_metatiles[h] & 0xFF,
                                   (content_metatiles[h] >> 8) & 0xFF])
        if layer1 is not None:
            layer1[at:at + 2] = bytes([clear_metatile & 0xFF,
                                       (clear_metatile >> 8) & 0xFF])

    # 7. terrain
    pos = (y * entry.cell_w + x) * 2
    terrain[pos] = terrain_type & 0xFF
    terrain[pos + 1] = 0

    blocks = {
        "gfx": bytes(gfx),
        "palette": bytes(pal),
        "layer0": bytes(layer0),
        "layer1": bytes(layer1) if layer1 is not None else None,
        "metatiles": bytes(meta),
        "terrain": bytes(terrain),
    }
    return {
        "bank": bank,
        "blank_tile": blank_tile,
        "clear_metatile": clear_metatile,
        "content_tiles": content_tiles,
        "content_metatiles": content_metatiles,
        "blocks": blocks,
        "compressed_sizes": {
            name: (len(compress_literal(data)) if data is not None else 0)
            for name, data in blocks.items()
        },
        "raw_sizes": {name: (len(data) if data is not None else 0)
                      for name, data in blocks.items()},
    }


def check_simulated(entry: MapEntry, sim: dict) -> list[str]:
    """Re-parse a simulated result and list every structural problem found."""
    problems: list[str] = []
    blocks = sim["blocks"]
    gfx = blocks["gfx"]
    meta = blocks["metatiles"]
    if len(gfx) % TILE_BYTES:
        problems.append(f"gfx block {len(gfx)} B is not a multiple of {TILE_BYTES}")
    if len(meta) % METATILE_BYTES:
        problems.append(f"metatile block {len(meta)} B is not a multiple of {METATILE_BYTES}")
    if len(blocks["terrain"]) != entry.cell_count * 2:
        problems.append(f"terrain block grew to {len(blocks['terrain'])} B")
    if len(blocks["layer0"]) != len(entry.layer0):
        problems.append("layer0 block changed size")
    if (entry.layer1 is None) != (blocks["layer1"] is None):
        problems.append("layer1 presence changed")
    tile_count = len(gfx) // TILE_BYTES
    meta_count = len(meta) // METATILE_BYTES
    for name in ("layer0", "layer1"):
        layer = blocks[name]
        if layer is None:
            continue
        for k in range(0, len(layer), 2):
            m = layer[k] | layer[k + 1] << 8
            if m >= meta_count:
                problems.append(f"{name} index {m} >= metatile count {meta_count}")
                break
    for i in range(meta_count):
        for j in range(4):
            off = i * METATILE_BYTES + j * 2
            word = meta[off] | meta[off + 1] << 8
            tile = word & 0x03FF
            bank = word >> 12
            if tile >= tile_count:
                problems.append(f"metatile {i} ref {j} tile {tile} >= {tile_count}")
                break
            if bank >= BANK_COUNT:
                problems.append(f"metatile {i} ref {j} bank {bank} >= {BANK_COUNT}")
                break
    if len(blocks["palette"]) < PALETTE_BYTES:
        problems.append(f"palette block {len(blocks['palette'])} B < {PALETTE_BYTES}")
    return problems


def run_simulate_all(rom: bytes) -> int:
    """Simulate one replacement at cell (0,0) of every valid map."""
    failures = 0
    print(f"\n{'idx':>3}  {'bank':>4}  {'new tiles':>9}  {'new metatiles':>13}"
          f"  {'gfx raw->lz':>15}  {'meta raw->lz':>15}  re-parse")
    for entry in iter_entries(rom):
        result = plan_cell(entry, 0, 0, 0, None)
        plan = result.get("plan", {})
        sim_raw = plan.get("simulated_raw_sizes", {})
        sim_comp = plan.get("simulated_compressed_sizes", {})
        problems = plan.get("simulated_problems", [])
        ok = result["ok"] and not problems
        if not ok:
            failures += 1
        print(f"{entry.index:>3}  {plan.get('bank'):>4}"
              f"  {len(plan.get('gfx_tiles_appended', [])):>9}"
              f"  {len(plan.get('metatiles_appended', [])):>13}"
              f"  {sim_raw.get('gfx', 0):>7}->{sim_comp.get('gfx', 0):>6}"
              f"  {sim_raw.get('metatiles', 0):>7}->{sim_comp.get('metatiles', 0):>6}"
              f"  {'OK' if ok else 'PROBLEM: ' + '; '.join(problems)}")
    print(f"\nsimulate-all: {MAP_ENTRY_COUNT - failures}/{MAP_ENTRY_COUNT} maps simulated cleanly")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inspect battle-map tile assets and dry-run a single cell replacement.")
    ap.add_argument("rom", type=pathlib.Path, help="GBA ROM file")
    ap.add_argument("--stage", type=int, help="map descriptor index (0..46)")
    ap.add_argument("--x", type=int, help="cell column of the replacement")
    ap.add_argument("--y", type=int, help="cell row of the replacement")
    ap.add_argument("--terrain", type=int, default=0, help="terrain type 0..15 (default 0)")
    ap.add_argument("--asset", type=pathlib.Path,
                    help="optional raw 512-byte index buffer (32x16, values 0..15)")
    ap.add_argument("--all", action="store_true", help="report every valid map")
    ap.add_argument("--selftest", action="store_true",
                    help="run the synthetic limit-check cases and exit")
    ap.add_argument("--simulate-all", action="store_true",
                    help="simulate one replacement at cell (0,0) of every map and exit")
    ap.add_argument("--json", type=pathlib.Path, help="write the report as JSON")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.selftest:
        return run_selftest()

    if not args.rom.exists():
        print(f"error: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    rom = args.rom.read_bytes()
    if args.simulate_all:
        return run_simulate_all(rom)
    print(f"rom     : {args.rom}")
    print(f"sha256  : {rom_sha256(args.rom)}")
    print(f"map table: file 0x{MAP_TABLE:06X} (ARM 0x{ROM_BASE + MAP_TABLE:08X}),"
          f" {MAP_ENTRY_SIZE} B/entry, {MAP_ENTRY_COUNT} valid entries")

    asset = None
    if args.asset:
        asset = args.asset.read_bytes()
        if len(asset) != ASSET_PIXELS:
            print(f"error: --asset must be exactly {ASSET_PIXELS} bytes"
                  f" ({CELL_W_PX}x{CELL_H_PX} palette indices), got {len(asset)}",
                  file=sys.stderr)
            return 1
        if max(asset) > 15:
            print("error: --asset indices must be 0..15", file=sys.stderr)
            return 1

    report: dict = {
        "rom": str(args.rom),
        "sha256": rom_sha256(args.rom),
        "map_table": MAP_TABLE,
        "maps": {},
    }

    if args.all:
        rows = []
        for entry in iter_entries(rom):
            info = analyze(entry)
            report["maps"][str(entry.index)] = info
            rows.append((info["headroom_cells"]["binding"], entry.index, info))
        rows.sort()
        print(f"\n{'idx':>3}  {'cells':>9}  {'gfx tiles':>15}  {'metatiles':>15}"
              f"  {'colour banks':>17}  {'cells left':>11}")
        for binding, index, info in rows:
            head = info["headroom_cells"]
            print(f"{index:>3}  {info['cell_w']:>4}x{info['cell_h']:<4}"
                  f"  {info['gfx']['tiles']:>6} used, {info['gfx']['free_tiles']:>4} free"
                  f"  {info['metatiles']['count']:>6} used, {info['metatiles']['free']:>4} free"
                  f"  {info['banks']['used_count']:>6} used, {info['banks']['free_count']:>4} free"
                  f"  {binding:>4} ({head['binding_reason']})")
        print(f"\nmost constrained map: index {rows[0][1]}"
              f" ({rows[0][2]['cell_w']}x{rows[0][2]['cell_h']}),"
              f" binding limit = {rows[0][2]['headroom_cells']['binding_reason']}"
              f" -> {rows[0][0]} cell(s)")

    if args.stage is not None:
        if not (0 <= args.stage < MAP_ENTRY_COUNT):
            print(f"error: --stage must be 0..{MAP_ENTRY_COUNT - 1}", file=sys.stderr)
            return 1
        entry = load_entry(rom, args.stage)
        info = analyze(entry)
        report["maps"][str(entry.index)] = info
        print()
        print_map_report(entry, info)
        if args.x is not None or args.y is not None:
            if args.x is None or args.y is None:
                print("error: --x and --y must be given together", file=sys.stderr)
                return 1
            plan_result = plan_cell(entry, args.x, args.y, args.terrain, asset)
            report["plan"] = plan_result
            print()
            print_plan(entry, plan_result)
        elif asset is not None:
            print("\n(--asset given but no --x/--y: nothing planned)")

    if args.json:
        write_text(args.json, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"\nwrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
