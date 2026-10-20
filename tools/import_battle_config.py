#!/usr/bin/env python3
"""
Battle configuration patch generator for Naruto GBA Sequel.

Generates two types of patches:
  1. ROM patches — modify unit ID table and battle scenario config in the ROM
  2. WRAM cheat codes — modify battle data at runtime (when ROM patching is insufficient)

This module also hosts the **ROM-level write-back path** for the battle-side
tables: `read_*` / `write_*` pairs that copy a native entry and overwrite only
the fields whose meaning is proved (see `tools/writeback_paths.py` for the
round-trip self-check).  The model is the repository-wide one: unknown bytes
are copied raw, never invented.

ROM data layout:
  0x53D910 (32 bytes/entry, 47 entries) — battle map descriptor table
  0x53D848 (8 bytes/entry, 10 entries)  — WRAM allocation table {u32 addr, u32 size}
  0x53DF70 (4 bytes/entry, 16 entries)  — battle stage data pointer table
  0x53F140 (4 bytes/entry, 86 entries)  — scene object descriptor pointer table
  0x53F298 (2 bytes/entry, 64 entries)  — u16 offset table (see write_unit_offset)
  0x5461C4 (0xB8 bytes/record)          — battle formation matrix

Map descriptor entry (32 bytes, `notes/battle-config-format.md`):
  +0x00 u16 raw_width   +0x02 u16 raw_height
  +0x04 u32 tile_gfx    +0x08 u32 palette   +0x0C u32 layer0
  +0x10 u32 layer1     +0x14 u32 metatile  +0x18 u32 terrain
  +0x1C u8  background_id (+3 pad)

WRAM battle data layout:
  0x0201BE2A — Unit count byte + team count byte
  0x02021E2C — Unit lookup table base
  0x02024294 — Unit array start (UNIT_STRIDE bytes per unit)
  0x020240C0 — Main battle data (6084 bytes)
  0x02022E30 — Battle state (4732 bytes)
  0x02026804 — Battle control flags (8 bytes)

Usage:
  python import_battle_config.py --units sequel/content/units/sequel-units.json \\
                                 --story sequel/content/story/episode-01.json \\
                                 --output battle-patch.json
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Battle unit struct size (from code analysis of battle init at 0x0806E678)
UNIT_STRIDE = 234  # bytes per unit in the unit array at 0x02024294
MAX_UNITS = 25  # max units in battle (6084 / 234 ≈ 25)

import sys
sys.path.insert(0, str(ROOT))

from tools.lib import load_json

# ROM addresses (ARM) for battle data
ROM_UNIT_ID_TABLE_ARM = 0x0853F298
ROM_UNIT_ID_TABLE_FILE = 0x53F298
ROM_UNIT_ID_TABLE_SIZE = 128  # u16[64]

# Battle map descriptor table.  Geometry proved in
# notes/battle-config-format.md: 32 bytes per entry, base 0x53D910, no header
# (the reader at 0x08069040 computes the slot as base + id*32 and then reads
# the +0x04 graphics pointer).
ROM_BATTLE_SCENARIO_ARM = 0x0853D910
ROM_BATTLE_SCENARIO_FILE = 0x53D910
ROM_BATTLE_SCENARIO_SIZE = 47 * 32
ROM_BATTLE_SCENARIO_HEADER = 0   # proven: the first slot starts at the base
ROM_BATTLE_SCENARIO_ENTRY_SIZE = 32
ROM_BATTLE_SCENARIO_ENTRY_COUNT = 47

# Field map of one 32-byte map descriptor entry: offset -> (name, size)
MAP_ENTRY_FIELDS: tuple[tuple[int, str, int], ...] = (
    (0x00, "raw_width", 2),
    (0x02, "raw_height", 2),
    (0x04, "tile_gfx_ptr", 4),
    (0x08, "palette_ptr", 4),
    (0x0C, "layer0_ptr", 4),
    (0x10, "layer1_ptr", 4),
    (0x14, "metatile_ptr", 4),
    (0x18, "terrain_ptr", 4),
    (0x1C, "background_id", 1),
)

# Raw width/height are stored pre-scaled: tiles_x * 4 and tiles_y * 2.
MAP_RAW_WIDTH_PER_TILE = 4
MAP_RAW_HEIGHT_PER_TILE = 2

# Battle formation matrix (0x5461C4): group * 0x1AAC + variant * 0x8E4,
# 4-byte header, 12 records of 0xB8 bytes (tools/extract_positions.py).
FORMATION_TABLE_FILE = 0x5461C4
FORMATION_GROUP_STRIDE = 0x1AAC
FORMATION_VARIANT_STRIDE = 0x8E4
FORMATION_RECORD_STRIDE = 0xB8
FORMATION_RECORD_HEADER = 4
FORMATION_GROUP_COUNT = 48
FORMATION_VARIANT_COUNT = 3
FORMATION_RECORD_COUNT = 12
# Field map of one 0xB8 formation record (tools/extract_positions.py).
FORMATION_FIELDS: tuple[tuple[int, str, int], ...] = (
    (0x00, "selector", 1),
    (0x01, "affiliation", 1),
    (0x02, "x", 1),
    (0x03, "y", 1),
    (0x04, "parameter", 1),
    (0x08, "aux_u32", 4),
)

# Battle level data block table (legacy bank "cutscene-scripts", 0x53DF70).
#
# Proved by the single native reader 0x08072F0C (fn 0x08072EDC):
#   08072F10  lsls r5, r0, #3      ; stride 8, not 4
#   08072F14  ldr  r0, [r0]        ; tiles pointer
#   08072F16  ldr  r1, [pc, #0x28] ; 0x06016000  (OBJ VRAM)
#   08072F18  bl   #0x809C0E8      ; svc 0x12 = LZ77UnCompVram
#   08072F1C  adds r4, #4
#   08072F1E  adds r5, r5, r4      ; palette pointer
#   08072F20  ldr  r0, [r5]
#   08072F22  ldr  r1, [pc, #0x20] ; 0x05000380  (palette RAM)
#   08072F24  bl   #0x809C0E8
#
# So the table is **4 entries of 8 bytes**, each entry a pointer pair
# (LZ77 4bpp tiles, LZ77 16-colour palette) -- a *level data block table*,
# not a story-VM script table.  See
# `notes/evidence/cutscene-block-format-20261020.md`.
#
# The API addresses individual u32 *slots* (stride 4) so that the two
# pointers of one entry stay distinguishable; there are 8 slots in total.
# The old count of 16 was wrong and let an index reach 0x53DFB0 -- the
# start of the *next* table.
STAGE_POINTER_TABLE_FILE = 0x53DF70
STAGE_POINTER_ENTRY_COUNT = 4
STAGE_POINTER_STRIDE = 8
STAGE_POINTER_SLOT_COUNT = STAGE_POINTER_ENTRY_COUNT * 2
STAGE_POINTER_FIELDS = ("gfx_ptr", "palette_ptr")
# Kept for callers that only need the number of addressable u32 slots.
STAGE_POINTER_TABLE_COUNT = STAGE_POINTER_SLOT_COUNT

# Scene object descriptor pointer table (adjudicated base of the legacy bank
# "map-sprites", see tools/table_registry.py CONFLICTS["0x53f1dc"]).
OBJECT_DESCRIPTOR_TABLE_FILE = 0x53F140
OBJECT_DESCRIPTOR_TABLE_COUNT = 86

# WRAM allocation table (legacy bank "save-state", 0x53D848): {u32 addr, u32 size}.
WRAM_ALLOC_TABLE_FILE = 0x53D848
WRAM_ALLOC_TABLE_COUNT = 10

ROM_FUNC_PTR_TABLE_ARM = 0x0853F1C0
ROM_FUNC_PTR_TABLE_FILE = 0x53F1C0

# A 48 Mbit GBA ROM occupies 0x08000000..0x085FFFFF.
ROM_POINTER_MIN = 0x08000000
ROM_POINTER_MAX = 0x085FFFFF

# Map descriptor entry format: 32 bytes (see MAP_ENTRY_FIELDS above).
# Index formula: entry_ptr = 0x0853D910 + map_id * 32  (no header -- the
# reader at 0x08069040 computes the slot as base + id*32 and then reads the
# +0x04 graphics pointer).
# The layout below is the one proved in notes/battle-config-format.md; the
# older "8 x u32" reading (palette at +0x10, flags at +0x18) was wrong.

# Known unit ID → character name mapping
UNIT_ID_NAMES = {
    0x00: "Naruto",
    0x01: "Sasuke",
    0x02: "Sakura",
    0x03: "Sai",
    0x04: "Kakashi",
    0x05: "Shikamaru",
    0x06: "Sasuke (Naruto)",
    0x07: "Sakura (NPC)",
    0x08: "Naruto (NPC)",
    0x09: "Sasuke (NPC)",
    0x0A: "Zabuza",
    0x0B: "Haku",
    0x0C: "Enemy-12",
    0x0D: "Enemy-13",
    0x10: "Shikamaru (shadow)",
    0x11: "Sasuke (curse)",
    0x12: "Enemy-18",
    0x13: "Enemy-19",
    0x14: "Enemy-20",
    0x15: "Enemy-21",
    0x16: "Enemy-22",
    0x17: "Enemy-23",
    0x18: "Enemy-24",
    0x19: "Enemy-25",
    0x1A: "Enemy-26",
    0x1B: "Enemy-27",
    0x1C: "Enemy-28",
    0x1D: "Enemy-29",
    0x1E: "Enemy-30",
    0x1F: "Enemy-31",
    0x20: "Enemy-32",
    0x21: "Enemy-33",
    0x22: "Enemy-34",
    0x23: "Masked Scouter",
    0x24: "Ambush Member",
}

# Valid battle scenario entries (from ROM analysis at 0x53D910, corrected 2026-03-31)
# Entry size = 32 bytes, IDs 0-7, accessed as: 0x0853D910 + id * 32
# The pointer columns follow notes/battle-config-format.md:
#   tile_gfx_file -> +0x04, tilemap_file -> +0x0C (layer0),
#   tilemap_alt_file -> +0x10 (layer1), palette_file -> +0x08,
#   palette2_file -> +0x18 (terrain), flags -> +0x1C (background_id)
BATTLE_SCENARIOS = [
    {"id": 0, "h": 64, "w": 92, "tile_gfx_file": 0x0B9F80, "tilemap_file": 0x0BD608, "tilemap_alt_file": 0x0BD70C, "palette_file": 0x0BE10C, "palette2_file": 0x0BF250, "flags": 0x01},
    {"id": 1, "h": 30, "w": 60, "tile_gfx_file": 0x0BF318, "tilemap_file": 0x0C166C, "tilemap_alt_file": 0x0C1710, "palette_file": 0x0C18EC, "palette2_file": 0x0C1CAC, "flags": 0x01},
    {"id": 2, "h": 36, "w": 36, "tile_gfx_file": 0x0C1CF8, "tilemap_file": 0x0C416C, "tilemap_alt_file": 0x0C4210, "palette_file": 0x0C43E4, "palette2_file": 0x0C4844, "flags": 0x01},
    {"id": 3, "h": 40, "w": 36, "tile_gfx_file": 0x0C4880, "tilemap_file": 0x0C5F24, "tilemap_alt_file": 0x0C5FC8, "palette_file": 0x0C6140, "palette2_file": 0x0C6410, "flags": 0x01},
    {"id": 4, "h": 40, "w": 36, "tile_gfx_file": 0x0C6450, "tilemap_file": 0x0C8454, "tilemap_alt_file": 0x0C84F8, "palette_file": 0x0C86D8, "palette2_file": 0x0C8ABC, "flags": 0x01},
    {"id": 5, "h": 46, "w": 36, "tile_gfx_file": 0x0C8AF4, "tilemap_file": 0x0CAA94, "tilemap_alt_file": 0x0CAB30, "palette_file": 0x0CAD38, "palette2_file": 0x0CB138, "flags": 0x01},
    {"id": 6, "h": 32, "w": 60, "tile_gfx_file": 0x0CB18C, "tilemap_file": 0x0CCB54, "tilemap_alt_file": 0x0CCC28, "palette_file": 0x0CCE1C, "palette2_file": 0x0CD21C, "flags": 0x02},
    {"id": 7, "h": 32, "w": 60, "tile_gfx_file": 0x0CD260, "tilemap_file": 0x0D0054, "tilemap_alt_file": 0x0D0154, "palette_file": 0x0D0638, "palette2_file": 0x0D1238, "flags": 0x102},
]


from tools.lib import load_json
from tools.lib.io import write_text


def build_rom_unit_id_patch(unit_index: int, unit_id: int) -> dict[str, Any]:
    """
    Build a ROM byte patch for the unit ID mapping table.

    The table at ROM file 0x53F298 is u16[64]. Each entry maps an index
    to a character ID used by the battle system.

    .. warning::
       **Unproven semantics.**  The only native reference to this table is
       0x08080B2C (fn 0x08080814), which indexes it as a *u16 offset* table
       used by a rendering/object routine -- not as a character id table.
       ``tools/build_db_patches.py::generate_unit_patches`` therefore
       rejects editor ``char_id`` writes here as unsafe.  The sanctioned
       write-back path is :func:`write_unit_offset`, which only allows
       reusing a native offset.  This legacy builder is kept for the editor
       flow and is *not* used by the write-back self-check.
    """
    offset = ROM_UNIT_ID_TABLE_FILE + unit_index * 2
    return {
        "type": "bytes",
        "rom_file_offset": f"0x{offset:06X}",
        "rom_addr_arm": f"0x{ROM_UNIT_ID_TABLE_ARM + unit_index * 2:08X}",
        "value": unit_id,
        "size": 2,
        "encoding": "<H",
        "comment": (
            f"Unit ID table[{unit_index}] = 0x{unit_id:04X} "
            f"({UNIT_ID_NAMES.get(unit_id, 'unknown')})"
        ),
    }


def build_rom_scenario_patch(
    scenario_index: int,
    tiles_x: int,
    tiles_y: int,
    ptr1_arm: int | None = None,
    ptr2_arm: int | None = None,
    flag: int | None = None,
) -> list[dict[str, Any]]:
    """
    Build ROM byte patches for a single battle map descriptor entry.

    Each entry is 32 bytes at ROM file 0x53D910 + map_id * 32 (the 4-byte
    "header" this function used to assume does not exist: the reader at
    0x08069040 computes the slot as base + id*32 and then reads the +0x04
    graphics pointer).

    The layout is the one proved in notes/battle-config-format.md:
    +0x00 u16 raw_width, +0x02 u16 raw_height, +0x04 tile_gfx_ptr,
    +0x08 palette_ptr, +0x0C layer0_ptr, +0x10 layer1_ptr,
    +0x14 metatile_ptr, +0x18 terrain_ptr, +0x1C u8 background_id.

    ``tiles_x`` / ``tiles_y`` are tile counts; the ROM stores the pre-scaled
    raw size (x * 4, y * 2).
    """
    base_file = (
        ROM_BATTLE_SCENARIO_FILE
        + ROM_BATTLE_SCENARIO_HEADER
        + scenario_index * ROM_BATTLE_SCENARIO_ENTRY_SIZE
    )
    base_arm = base_file + 0x08000000
    patches = []

    # +0x00: u16 raw_width, +0x02: u16 raw_height (packed into one u32)
    raw_width = tiles_x * MAP_RAW_WIDTH_PER_TILE
    raw_height = tiles_y * MAP_RAW_HEIGHT_PER_TILE
    patches.append({
        "type": "bytes",
        "rom_file_offset": f"0x{base_file:06X}",
        "rom_addr_arm": f"0x{base_arm:08X}",
        "value": (raw_width & 0xFFFF) | ((raw_height & 0xFFFF) << 16),
        "size": 4,
        "encoding": "<I",
        "comment": (
            f"map[{scenario_index}] raw_width={raw_width} raw_height={raw_height} "
            f"(tiles {tiles_x}x{tiles_y})"
        ),
    })

    # +0x04: u32 tile_gfx_ptr (ROM pointer to LZ77 tile graphics)
    if ptr1_arm is not None:
        patches.append({
            "type": "bytes",
            "rom_file_offset": f"0x{base_file + 4:06X}",
            "rom_addr_arm": f"0x{base_arm + 4:08X}",
            "value": ptr1_arm,
            "size": 4,
            "encoding": "<I",
            "comment": f"map[{scenario_index}] tile_gfx_ptr = 0x{ptr1_arm:08X}",
        })

    # +0x08: u32 palette_ptr (ROM pointer to LZ77 palette)
    if ptr2_arm is not None:
        patches.append({
            "type": "bytes",
            "rom_file_offset": f"0x{base_file + 8:06X}",
            "rom_addr_arm": f"0x{base_arm + 8:08X}",
            "value": ptr2_arm,
            "size": 4,
            "encoding": "<I",
            "comment": f"map[{scenario_index}] palette_ptr = 0x{ptr2_arm:08X}",
        })

    # +0x1C: u8 background_id (story background id), 3 pad bytes copied raw
    if flag is not None:
        patches.append({
            "type": "bytes",
            "rom_file_offset": f"0x{base_file + 0x1C:06X}",
            "rom_addr_arm": f"0x{base_arm + 0x1C:08X}",
            "value": flag & 0xFF,
            "size": 1,
            "encoding": "<B",
            "comment": f"map[{scenario_index}] background_id = {flag & 0xFF}",
        })

    return patches


def build_wram_unit_patch(unit_index: int, unit_id: int, x: int, y: int, team: int) -> dict[str, Any]:
    """
    Build a WRAM patch for a single unit in the battle unit array.

    The unit array starts at 0x02024294, with UNIT_STRIDE (234) bytes per unit.
    """
    base = 0x02024294 + unit_index * UNIT_STRIDE
    patches = []

    # byte +0: existence flag (0 = not present, non-zero = present)
    patches.append({
        "wr_addr": f"0x{base:X}",
        "value": 0x01,
        "size": 1,
        "comment": f"unit[{unit_index}] existence flag",
    })

    # byte +12: init flag (set by battle init code at 0x0806E64A)
    patches.append({
        "wr_addr": f"0x{base + 12:X}",
        "value": 0x01,
        "size": 1,
        "comment": f"unit[{unit_index}] init flag",
    })

    # bytes +192 to +195: u32 battle state marker (set by battle init at 0x0806E646)
    patches.append({
        "wr_addr": f"0x{base + 192:X}",
        "value": 0x00000011,
        "size": 4,
        "comment": f"unit[{unit_index}] battle state marker",
    })

    # byte +196: character ID (read by battle init at 0x0806E654)
    patches.append({
        "wr_addr": f"0x{base + 196:X}",
        "value": unit_id,
        "size": 1,
        "comment": f"unit[{unit_index}] character ID (0x{unit_id:02X} = {UNIT_ID_NAMES.get(unit_id, 'unknown')})",
    })

    # bytes +1, +2, +3: x, y, team
    patches.append({
        "wr_addr": f"0x{base + 1:X}",
        "value": x & 0xFF,
        "size": 1,
        "comment": f"unit[{unit_index}] x position",
    })
    patches.append({
        "wr_addr": f"0x{base + 2:X}",
        "value": y & 0xFF,
        "size": 1,
        "comment": f"unit[{unit_index}] y position",
    })
    patches.append({
        "wr_addr": f"0x{base + 3:X}",
        "value": team & 0xFF,
        "size": 1,
        "comment": f"unit[{unit_index}] team (0=ally, 1=enemy)",
    })

    return {
        "unit_index": unit_index,
        "unit_id": f"0x{unit_id:02X}",
        "base": f"0x{base:X}",
        "patches": patches,
    }


def resolve_battle_config_patches(
    units_path: Path, story_path: Path, patch_id: str
) -> dict[str, Any]:
    """
    Generate battle configuration patches from episode unit definitions.

    Produces both ROM patches (for unit ID table and scenario config)
    and WRAM cheat codes (for runtime battle data modification).
    """
    units = load_json(units_path)
    story = load_json(story_path)

    wram_patches = []
    rom_patches = []

    # --- Allied units ---
    allied_party = story.get("battle_slice", {}).get("allied_party", [])
    enemy_groups = story.get("battle_slice", {}).get("enemy_groups", [])

    allied_positions = {
        "naruto": (2, 3),
        "shikamaru": (3, 4),
        "sakura": (1, 0),
        "sai": (1, 2),
    }
    allied_unit_ids = {
        "naruto": 0x00, "sasuke": 0x01, "sakura": 0x02, "sai": 0x03,
        "kakashi": 0x04, "shikamaru": 0x05,
    }

    for i, unit_name in enumerate(allied_party):
        uid = allied_unit_ids.get(unit_name, 0)
        pos = allied_positions.get(unit_name, (2 + i, 3 + i))
        x, y = pos
        patch = build_wram_unit_patch(i, uid, x, y, team=0)
        wram_patches.append(patch)

    # --- Enemy units ---
    enemy_unit_ids = {
        "masked-scouts": 0x23,
        "ambush-team-a": 0x24,
    }

    enemy_start = len(allied_party)
    for i, group_name in enumerate(enemy_groups):
        uid = enemy_unit_ids.get(group_name, 0x23 + i)
        x = 10 + i
        y = 5 + i
        patch = build_wram_unit_patch(enemy_start + i, uid, x, y, team=1)
        wram_patches.append(patch)

    # --- ROM patches: unit ID table ---
    for unit_name, uid in allied_unit_ids.items():
        rom_patches.append(build_rom_unit_id_patch(uid, uid))

    # --- ROM patches: battle scenario config ---
    # Default: use scenario index 0 (92x64 large arena)
    # The caller can override scenario_index, tiles_x, tiles_y via story.json
    battle_cfg = story.get("battle_slice", {}).get("rom_config", {})
    scenario_idx = battle_cfg.get("scenario_index", 0)

    if scenario_idx < len(BATTLE_SCENARIOS):
        scenario = BATTLE_SCENARIOS[scenario_idx]
        scenario_patches = build_rom_scenario_patch(
            scenario_index=scenario["id"],
            tiles_x=battle_cfg.get("tiles_x", scenario["w"]),
            tiles_y=battle_cfg.get("tiles_y", scenario["h"]),
            ptr1_arm=battle_cfg.get("ptr1_arm"),
            ptr2_arm=battle_cfg.get("ptr2_arm"),
            flag=battle_cfg.get("flag"),
        )
        rom_patches.extend(scenario_patches)

    return {
        "patch_id": patch_id,
        "episode_id": story["episode_id"],
        "wram_patches": wram_patches,
        "rom_patches": rom_patches,
        "available_scenarios": BATTLE_SCENARIOS,
        "notes": {
            "unit_array": f"WRAM 0x02024294, {UNIT_STRIDE} bytes/unit, max {MAX_UNITS} units",
            "unit_id_table": f"ROM 0x{ROM_UNIT_ID_TABLE_ARM:08X} (file 0x{ROM_UNIT_ID_TABLE_FILE:X}), u16[64]",
            "scenario_table": f"ROM 0x{ROM_BATTLE_SCENARIO_ARM:08X} (file 0x{ROM_BATTLE_SCENARIO_FILE:X}), 8 entries × 32 bytes (header +4)",
            "scenario_entry_format": "u32 dim(h|w), u32 tile_gfx_ptr, u32 tilemap_ptr, u32 tilemap_alt_ptr, u32 extra_ptr, u32 palette_ptr, u32 palette2_ptr, u32 flags",
            "battle_state": "WRAM 0x02022E30, 4732 bytes",
            "main_battle_data": "WRAM 0x020240C0, 6084 bytes",
            "patch_approach": (
                "ROM patches modify unit ID table and scenario config directly. "
                "WRAM patches provide runtime overrides when ROM patching is insufficient."
            ),
            "lz77_note": (
                "ptr1 data has 12-byte header (u16 stride, u16 height, u16 type, "
                "u16 0xF000, u16 0x9001, u16 subtype) followed by raw tile data. "
                "ptr2 data is LZ77-compressed (header 0x10, decompressed size 384 bytes)."
            ),
        },
    }


def summarize_battle(units_path: Path, story_path: Path) -> dict:
    units = load_json(units_path)
    story = load_json(story_path)
    slice_spec = story.get("battle_slice", {})
    return {
        "episode_id": story["episode_id"],
        "allied_party": slice_spec.get("allied_party", []),
        "enemy_groups": slice_spec.get("enemy_groups", []),
        "unit_ids": [unit["id"] for unit in units.get("units", [])],
        "win_condition": slice_spec.get("win_condition"),
        "lose_condition": slice_spec.get("lose_condition"),
        "patch_ready": True,
    }


# ---------------------------------------------------------------------------
# ROM-level write-back path
#
# The repository-wide model: copy a native entry, overwrite only the fields
# whose meaning is proved, copy everything else raw.  Every writer returns
# the normalised author input so the caller can compare it against a fresh
# read-back (see tools/writeback_paths.py).
# ---------------------------------------------------------------------------


class WriteBackError(ValueError):
    """Raised when an author change is not representable in the ROM record."""


def _u(raw: bytes, offset: int, size: int) -> int:
    return int.from_bytes(raw[offset:offset + size], "little")


def _put(buf: bytearray, offset: int, size: int, value: int) -> None:
    if not 0 <= value < (1 << (size * 8)):
        raise WriteBackError(
            f"value {value} does not fit into {size} byte(s) at 0x{offset:X}"
        )
    buf[offset:offset + size] = value.to_bytes(size, "little")


def _check_pointer(name: str, value: int) -> int:
    if value == 0:
        return value
    if not ROM_POINTER_MIN <= value <= ROM_POINTER_MAX:
        raise WriteBackError(
            f"{name} pointer 0x{value:08X} outside the 48 Mbit ROM range"
        )
    return value


# --- map descriptor table (0x53D910) ---------------------------------------

def map_entry_offset(map_id: int) -> int:
    if not 0 <= map_id < ROM_BATTLE_SCENARIO_ENTRY_COUNT:
        raise WriteBackError(
            f"map id {map_id} outside 0..{ROM_BATTLE_SCENARIO_ENTRY_COUNT - 1}"
        )
    return (
        ROM_BATTLE_SCENARIO_FILE
        + ROM_BATTLE_SCENARIO_HEADER
        + map_id * ROM_BATTLE_SCENARIO_ENTRY_SIZE
    )


def read_map_entry(rom: bytes, map_id: int) -> dict:
    """Read the known fields of one 32-byte map descriptor."""
    off = map_entry_offset(map_id)
    raw = bytes(rom[off:off + ROM_BATTLE_SCENARIO_ENTRY_SIZE])
    if len(raw) != ROM_BATTLE_SCENARIO_ENTRY_SIZE:
        raise WriteBackError("ROM too small for the map descriptor table")
    out: dict = {"map_id": map_id, "offset": off}
    for offset, name, size in MAP_ENTRY_FIELDS:
        out[name] = _u(raw, offset, size)
    return out


def write_map_entry(rom: bytearray, map_id: int, changes: dict) -> dict:
    """Apply author changes to one map descriptor, in place."""
    off = map_entry_offset(map_id)
    native = bytes(rom[off:off + ROM_BATTLE_SCENARIO_ENTRY_SIZE])
    buf = bytearray(native)
    applied: dict = {"map_id": map_id, "offset": off}
    for offset, name, size in MAP_ENTRY_FIELDS:
        if name not in changes:
            continue
        value = int(changes[name])
        if size == 4 and name.endswith("_ptr"):
            value = _check_pointer(name, value)
        _put(buf, offset, size, value)
        applied[name] = value
    unknown = set(changes) - {"map_id", "offset", *(n for _, n, _ in MAP_ENTRY_FIELDS)}
    if unknown:
        raise WriteBackError(f"unknown map entry fields: {sorted(unknown)}")
    if len(applied) == 2:
        raise WriteBackError("no map entry field to write")
    rom[off:off + ROM_BATTLE_SCENARIO_ENTRY_SIZE] = buf
    return applied


# --- battle formation matrix (0x5461C4) -----------------------------------

def formation_record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    if not 0 <= group_id < FORMATION_GROUP_COUNT:
        raise WriteBackError(f"group {group_id} outside 0..{FORMATION_GROUP_COUNT - 1}")
    if not 0 <= variant_id < FORMATION_VARIANT_COUNT:
        raise WriteBackError(
            f"variant {variant_id} outside 0..{FORMATION_VARIANT_COUNT - 1}"
        )
    if not 0 <= record_id < FORMATION_RECORD_COUNT:
        raise WriteBackError(
            f"record {record_id} outside 0..{FORMATION_RECORD_COUNT - 1}"
        )
    return (
        FORMATION_TABLE_FILE
        + group_id * FORMATION_GROUP_STRIDE
        + variant_id * FORMATION_VARIANT_STRIDE
        + FORMATION_RECORD_HEADER
        + record_id * FORMATION_RECORD_STRIDE
    )


def read_formation_record(rom: bytes, group_id: int, variant_id: int,
                          record_id: int) -> dict:
    """Read the known fields of one 0xB8 formation record."""
    off = formation_record_offset(group_id, variant_id, record_id)
    raw = bytes(rom[off:off + FORMATION_RECORD_STRIDE])
    if len(raw) != FORMATION_RECORD_STRIDE:
        raise WriteBackError("ROM too small for the battle formation matrix")
    out: dict = {
        "group_id": group_id,
        "variant_id": variant_id,
        "record_id": record_id,
        "offset": off,
    }
    for offset, name, size in FORMATION_FIELDS:
        out[name] = _u(raw, offset, size)
    return out


def write_formation_record(rom: bytearray, group_id: int, variant_id: int,
                           record_id: int, changes: dict) -> dict:
    """Apply author changes to one formation record, in place."""
    off = formation_record_offset(group_id, variant_id, record_id)
    native = bytes(rom[off:off + FORMATION_RECORD_STRIDE])
    buf = bytearray(native)
    applied: dict = {
        "group_id": group_id,
        "variant_id": variant_id,
        "record_id": record_id,
        "offset": off,
    }
    for offset, name, size in FORMATION_FIELDS:
        if name not in changes:
            continue
        value = int(changes[name])
        _put(buf, offset, size, value)
        applied[name] = value
    unknown = set(changes) - {
        "group_id", "variant_id", "record_id", "offset",
        *(n for _, n, _ in FORMATION_FIELDS),
    }
    if unknown:
        raise WriteBackError(f"unknown formation record fields: {sorted(unknown)}")
    if len(applied) == 4:
        raise WriteBackError("no formation record field to write")
    rom[off:off + FORMATION_RECORD_STRIDE] = buf
    return applied


# --- level data block table (0x53DF70) --------------------------------------

def read_stage_pointer(rom: bytes, index: int) -> dict:
    """Read one u32 pointer slot of the level data block table.

    ``index`` addresses the u32 slots (0..7).  Slot ``2*e`` is the
    ``gfx_ptr`` of entry ``e`` and slot ``2*e+1`` is its ``palette_ptr``.
    """
    if not 0 <= index < STAGE_POINTER_SLOT_COUNT:
        raise WriteBackError(
            f"stage pointer {index} outside 0..{STAGE_POINTER_SLOT_COUNT - 1}"
        )
    off = STAGE_POINTER_TABLE_FILE + index * 4
    return {
        "index": index,
        "entry": index // 2,
        "field": STAGE_POINTER_FIELDS[index % 2],
        "offset": off,
        "pointer": _u(bytes(rom), off, 4),
    }


def read_stage_entry(rom: bytes, entry: int) -> dict:
    """Read one 8-byte level data block entry (both pointers)."""
    if not 0 <= entry < STAGE_POINTER_ENTRY_COUNT:
        raise WriteBackError(
            f"stage entry {entry} outside 0..{STAGE_POINTER_ENTRY_COUNT - 1}"
        )
    off = STAGE_POINTER_TABLE_FILE + entry * STAGE_POINTER_STRIDE
    out: dict = {"entry": entry, "offset": off}
    for position, name in enumerate(STAGE_POINTER_FIELDS):
        out[name] = _u(bytes(rom), off + position * 4, 4)
    return out


def write_stage_pointer(rom: bytearray, index: int, pointer: int) -> dict:
    """Repoint one u32 slot of the level data block table.

    The table entries are pairs of u32 pointers into the ``0x0812xxxx``
    level data area: an LZ77-compressed 4bpp tile block and an LZ77
    compressed 16-colour palette.  The game copies them into VRAM and
    palette RAM with the BIOS ``LZ77UnCompVram`` call, so the safe write-back
    today is *repointing* a slot at another native block; authoring new
    block bytes needs the block format to be proved first.

    ``index`` addresses the u32 slots (0..7): ``2*e`` is the ``gfx_ptr`` of
    entry ``e``, ``2*e+1`` is its ``palette_ptr``.
    """
    if not 0 <= index < STAGE_POINTER_SLOT_COUNT:
        raise WriteBackError(
            f"stage pointer {index} outside 0..{STAGE_POINTER_SLOT_COUNT - 1}"
        )
    value = _check_pointer("stage", int(pointer))
    off = STAGE_POINTER_TABLE_FILE + index * 4
    rom[off:off + 4] = value.to_bytes(4, "little")
    return {
        "index": index,
        "entry": index // 2,
        "field": STAGE_POINTER_FIELDS[index % 2],
        "offset": off,
        "pointer": value,
    }


def write_stage_entry(rom: bytearray, entry: int, changes: dict) -> dict:
    """Repoint the named pointers of one level data block entry.

    The native entry is copied verbatim; only the pointer fields the author
    names are overwritten, the other one keeps its native bytes.
    """
    if not 0 <= entry < STAGE_POINTER_ENTRY_COUNT:
        raise WriteBackError(
            f"stage entry {entry} outside 0..{STAGE_POINTER_ENTRY_COUNT - 1}"
        )
    off = STAGE_POINTER_TABLE_FILE + entry * STAGE_POINTER_STRIDE
    native = bytes(rom[off:off + STAGE_POINTER_STRIDE])
    if len(native) != STAGE_POINTER_STRIDE:
        raise WriteBackError("ROM too small for the level data block table")
    buf = bytearray(native)
    applied: dict = {"entry": entry, "offset": off}
    for position, name in enumerate(STAGE_POINTER_FIELDS):
        if name not in changes:
            continue
        value = _check_pointer(name, int(changes[name]))
        buf[position * 4:position * 4 + 4] = value.to_bytes(4, "little")
        applied[name] = value
    unknown = set(changes) - set(STAGE_POINTER_FIELDS)
    if unknown:
        raise WriteBackError(f"unknown stage entry fields: {sorted(unknown)}")
    if len(applied) == 2:
        raise WriteBackError("no stage entry field to write")
    rom[off:off + STAGE_POINTER_STRIDE] = buf
    return applied


# --- scene object descriptor pointer table (0x53F140) ----------------------

def read_object_descriptor_pointer(rom: bytes, slot: int) -> dict:
    """Read one u32 pointer of the scene object descriptor table."""
    if not 0 <= slot < OBJECT_DESCRIPTOR_TABLE_COUNT:
        raise WriteBackError(
            f"object descriptor slot {slot} outside 0.."
            f"{OBJECT_DESCRIPTOR_TABLE_COUNT - 1}"
        )
    off = OBJECT_DESCRIPTOR_TABLE_FILE + slot * 4
    return {
        "slot": slot,
        "offset": off,
        "pointer": _u(bytes(rom), off, 4),
    }


def write_object_descriptor_pointer(rom: bytearray, slot: int, pointer: int) -> dict:
    """Repoint one slot of the scene object descriptor table.

    This is the adjudicated base of the legacy bank "map-sprites"
    (tools/table_registry.py CONFLICTS["0x53f1dc"]): 0x53F1DC was only the
    39th item of this 86-entry u32 pointer table.
    """
    if not 0 <= slot < OBJECT_DESCRIPTOR_TABLE_COUNT:
        raise WriteBackError(
            f"object descriptor slot {slot} outside 0.."
            f"{OBJECT_DESCRIPTOR_TABLE_COUNT - 1}"
        )
    value = _check_pointer("object descriptor", int(pointer))
    off = OBJECT_DESCRIPTOR_TABLE_FILE + slot * 4
    rom[off:off + 4] = value.to_bytes(4, "little")
    return {"slot": slot, "offset": off, "pointer": value}


# --- WRAM allocation table (0x53D848) --------------------------------------

def read_wram_alloc(rom: bytes, index: int) -> dict:
    """Read one {u32 wram_addr, u32 size} pair of the WRAM allocation table."""
    if not 0 <= index < WRAM_ALLOC_TABLE_COUNT:
        raise WriteBackError(
            f"wram alloc {index} outside 0..{WRAM_ALLOC_TABLE_COUNT - 1}"
        )
    off = WRAM_ALLOC_TABLE_FILE + index * 8
    raw = bytes(rom[off:off + 8])
    return {
        "index": index,
        "offset": off,
        "wram_addr": _u(raw, 0, 4),
        "size": _u(raw, 4, 4),
    }


def write_wram_alloc(rom: bytearray, index: int, wram_addr: int, size: int) -> dict:
    """Apply author changes to one WRAM allocation pair, in place.

    The legacy bank called this a "save descriptor table"; it is not one.
    It is a WRAM allocation table ({u32 wram_addr, u32 size}, 10 entries) whose
    native readers are 0x0806869A / 0x08068954 / 0x08068CC0 / 0x08068D98.
    """
    if not 0 <= index < WRAM_ALLOC_TABLE_COUNT:
        raise WriteBackError(
            f"wram alloc {index} outside 0..{WRAM_ALLOC_TABLE_COUNT - 1}"
        )
    addr = int(wram_addr)
    if not 0x02000000 <= addr <= 0x0203FFFF:
        raise WriteBackError(f"wram address 0x{addr:08X} outside the EWRAM range")
    if not 0 <= int(size) <= 0xFFFFFFFF:
        raise WriteBackError(f"size {size} outside u32 range")
    off = WRAM_ALLOC_TABLE_FILE + index * 8
    native = bytes(rom[off:off + 8])
    buf = bytearray(native)
    buf[0:4] = addr.to_bytes(4, "little")
    buf[4:8] = int(size).to_bytes(4, "little")
    rom[off:off + 8] = buf
    return {"index": index, "offset": off, "wram_addr": addr, "size": int(size)}


# --- u16 offset table (0x53F298) -------------------------------------------

def read_unit_offset(rom: bytes, slot: int) -> dict:
    """Read one u16 of the offset table at 0x53F298."""
    if not 0 <= slot < ROM_UNIT_ID_TABLE_SIZE // 2:
        raise WriteBackError(f"unit offset slot {slot} outside 0..63")
    off = ROM_UNIT_ID_TABLE_FILE + slot * 2
    return {
        "slot": slot,
        "offset": off,
        "value": _u(bytes(rom), off, 2),
    }


def write_unit_offset(rom: bytearray, slot: int, value: int) -> dict:
    """Repoint one slot of the u16 offset table at 0x53F298.

    **Constrained on purpose.**  The only native reference to this table is
    0x08080B2C (fn 0x08080814), which indexes it as a *u16 offset* table used
    by a rendering/object routine -- not as the "battle slot character id"
    table the legacy bank claimed.  ``tools/build_db_patches.py``
    (``generate_unit_patches``) therefore rejects editor char_id writes here
    as unsafe.

    Until the offset's target domain is proved, the only admissible author
    change is to point a slot at another *native* offset of the same table
    (the multiset of values stays intact, so no new target is introduced).
    """
    if not 0 <= slot < ROM_UNIT_ID_TABLE_SIZE // 2:
        raise WriteBackError(f"unit offset slot {slot} outside 0..63")
    new_value = int(value)
    if not 0 <= new_value <= 0xFFFF:
        raise WriteBackError(f"value {new_value} outside u16 range")
    native_values = {
        _u(bytes(rom), ROM_UNIT_ID_TABLE_FILE + i * 2, 2)
        for i in range(ROM_UNIT_ID_TABLE_SIZE // 2)
    }
    if new_value not in native_values:
        raise WriteBackError(
            f"value {new_value} is not a native offset of 0x{ROM_UNIT_ID_TABLE_FILE:X}; "
            f"the offset domain is not proved yet, so only native offsets may be reused"
        )
    off = ROM_UNIT_ID_TABLE_FILE + slot * 2
    rom[off:off + 2] = new_value.to_bytes(2, "little")
    return {"slot": slot, "offset": off, "value": new_value}


def _as_path(value: str) -> Path | None:
    """Path for a CLI argument, or None when it cannot be a path at all."""
    try:
        return Path(value)
    except (OSError, ValueError):
        return None


def _load_json_arg(value: str) -> dict:
    """Load a JSON object from an inline argument or from a JSON file.

    Inline JSON is awkward to pass through some shells, so a file path is
    accepted as well.
    """
    path = _as_path(value)
    if path is not None and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"--writeback expects a JSON object or a JSON file path ({exc}); "
            f"received {value!r}"
        )


def apply_writeback(rom: bytearray, spec: dict) -> dict:
    """Apply one author write-back spec to a ROM copy.

    ``spec`` is ``{"kind": ..., ...}`` where ``kind`` is one of
    ``map_entry`` / ``formation`` / ``stage_pointer`` / ``stage_entry`` /
    ``object_descriptor`` / ``wram_alloc`` / ``unit_offset``.
    """
    kind = spec.get("kind")
    if kind == "map_entry":
        applied = write_map_entry(rom, int(spec["map_id"]), spec.get("changes", {}))
        read_back = read_map_entry(rom, int(spec["map_id"]))
    elif kind == "formation":
        applied = write_formation_record(
            rom, int(spec["group_id"]), int(spec["variant_id"]),
            int(spec["record_id"]), spec.get("changes", {}),
        )
        read_back = read_formation_record(
            rom, int(spec["group_id"]), int(spec["variant_id"]), int(spec["record_id"])
        )
    elif kind == "stage_pointer":
        applied = write_stage_pointer(rom, int(spec["index"]), int(spec["pointer"]))
        read_back = read_stage_pointer(rom, int(spec["index"]))
    elif kind == "stage_entry":
        applied = write_stage_entry(rom, int(spec["entry"]), spec.get("changes", {}))
        read_back = read_stage_entry(rom, int(spec["entry"]))
    elif kind == "object_descriptor":
        applied = write_object_descriptor_pointer(
            rom, int(spec["slot"]), int(spec["pointer"])
        )
        read_back = read_object_descriptor_pointer(rom, int(spec["slot"]))
    elif kind == "wram_alloc":
        applied = write_wram_alloc(
            rom, int(spec["index"]), int(spec["wram_addr"]), int(spec["size"])
        )
        read_back = read_wram_alloc(rom, int(spec["index"]))
    elif kind == "unit_offset":
        applied = write_unit_offset(rom, int(spec["slot"]), int(spec["value"]))
        read_back = read_unit_offset(rom, int(spec["slot"]))
    else:
        raise WriteBackError(f"unknown write-back kind {kind!r}")
    return {"applied": applied, "read_back": read_back}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and summarize battle config content, or generate patches."
    )
    parser.add_argument("--units", default="sequel/content/units/sequel-units.json")
    parser.add_argument("--story", default="sequel/content/story/episode-01.json")
    parser.add_argument("--output")
    parser.add_argument("--rom", help="ROM to copy when --writeback is used")
    parser.add_argument("--writeback", help="JSON write-back spec (see apply_writeback)")
    parser.add_argument("--out", help="write the patched ROM copy here")
    args = parser.parse_args()

    if args.writeback:
        if not args.rom:
            print("--writeback needs --rom", flush=True)
            return 1
        rom_path = ROOT / args.rom if not Path(args.rom).is_absolute() else Path(args.rom)
        if not rom_path.is_file():
            print(f"ROM not found: {rom_path}", flush=True)
            return 1
        rom = bytearray(rom_path.read_bytes())
        spec = _load_json_arg(args.writeback)
        report = apply_writeback(rom, spec)
        if args.out:
            out_path = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(bytes(rom))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    units_path = ROOT / args.units
    story_path = ROOT / args.story

    if not units_path.exists():
        print(f"Warning: units file not found: {units_path}", flush=True)
        return 1
    if not story_path.exists():
        print(f"Warning: story file not found: {story_path}", flush=True)
        return 1

    summary = summarize_battle(units_path, story_path)

    patches = resolve_battle_config_patches(
        units_path, story_path, f"battle.{summary['episode_id']}"
    )

    report = {"summary": summary, "patches": patches}

    if args.output:
        output_path = ROOT / args.output
        write_text(
            output_path,
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
        import sys
        print(f"Patches written to {output_path}", file=sys.stderr)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
