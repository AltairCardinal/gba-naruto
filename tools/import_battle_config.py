#!/usr/bin/env python3
"""
Battle configuration patch generator for Naruto GBA Sequel.

Generates two types of patches:
  1. ROM patches — modify unit ID table and battle scenario config in the ROM
  2. WRAM cheat codes — modify battle data at runtime (when ROM patching is insufficient)

ROM data layout:
  0x53F298 (128 bytes) — Unit ID mapping table (u16[64])
  0x53D910 (256 bytes) — Battle scenario config table (16 entries × 16 bytes)
  0x53F1C0 (240 bytes) — Battle state machine function pointer table (u32[60])

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

# ROM addresses (ARM) for battle data
ROM_UNIT_ID_TABLE_ARM = 0x0853F298
ROM_UNIT_ID_TABLE_FILE = 0x53F298
ROM_UNIT_ID_TABLE_SIZE = 128  # u16[64]

ROM_BATTLE_SCENARIO_ARM = 0x0853D910
ROM_BATTLE_SCENARIO_FILE = 0x53D910
ROM_BATTLE_SCENARIO_SIZE = 256  # 16 entries × 16 bytes

ROM_FUNC_PTR_TABLE_ARM = 0x0853F1C0
ROM_FUNC_PTR_TABLE_FILE = 0x53F1C0

# Battle scenario entry format: 16 bytes each
# +0x00: u16 tiles_x  (battle arena width in tiles)
# +0x02: u16 tiles_y  (battle arena height in tiles)
# +0x04: u32 ptr1     (ROM pointer → compressed tilemap data)
# +0x08: u32 ptr2     (ROM pointer → LZ77 compressed palette/attribute data)
# +0x0C: u16 flag     (scenario flags)
# +0x0E: u16 extra    (extra data / padding)

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

# Valid battle scenario entries (from ROM analysis at 0x53D910)
BATTLE_SCENARIOS = [
    {"index": 0,  "w": 92, "h": 64, "ptr1_file": 0x0B9F80, "ptr2_file": 0x0BD608},
    {"index": 2,  "w": 60, "h": 30, "ptr1_file": 0x0BF318, "ptr2_file": 0x0C166C},
    {"index": 4,  "w": 36, "h": 36, "ptr1_file": 0x0C1CF8, "ptr2_file": 0x0C416C},
    {"index": 6,  "w": 36, "h": 40, "ptr1_file": 0x0C4880, "ptr2_file": 0x0C5F24},
    {"index": 8,  "w": 36, "h": 40, "ptr1_file": 0x0C6450, "ptr2_file": 0x0C8454},
    {"index": 10, "w": 36, "h": 46, "ptr1_file": 0x0C8AF4, "ptr2_file": 0x0CAA94},
    {"index": 12, "w": 60, "h": 32, "ptr1_file": 0x0CB18C, "ptr2_file": 0x0CCB54},
    {"index": 14, "w": 60, "h": 32, "ptr1_file": 0x0CD260, "ptr2_file": 0x0D0054},
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_rom_unit_id_patch(unit_index: int, unit_id: int) -> dict[str, Any]:
    """
    Build a ROM byte patch for the unit ID mapping table.

    The table at ROM file 0x53F298 is u16[64]. Each entry maps an index
    to a character ID used by the battle system.
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
    Build ROM byte patches for a single battle scenario config entry.

    Each entry is 16 bytes at ROM file 0x53D910 + scenario_index * 16.
    """
    base_file = ROM_BATTLE_SCENARIO_FILE + scenario_index * 16
    base_arm = ROM_BATTLE_SCENARIO_ARM + scenario_index * 16
    patches = []

    # +0x00: u16 tiles_x
    patches.append({
        "type": "bytes",
        "rom_file_offset": f"0x{base_file:06X}",
        "rom_addr_arm": f"0x{base_arm:08X}",
        "value": tiles_x,
        "size": 2,
        "encoding": "<H",
        "comment": f"scenario[{scenario_index}] tiles_x = {tiles_x}",
    })

    # +0x02: u16 tiles_y
    patches.append({
        "type": "bytes",
        "rom_file_offset": f"0x{base_file + 2:06X}",
        "rom_addr_arm": f"0x{base_arm + 2:08X}",
        "value": tiles_y,
        "size": 2,
        "encoding": "<H",
        "comment": f"scenario[{scenario_index}] tiles_y = {tiles_y}",
    })

    # +0x04: u32 ptr1 (ROM pointer to compressed tilemap)
    if ptr1_arm is not None:
        patches.append({
            "type": "bytes",
            "rom_file_offset": f"0x{base_file + 4:06X}",
            "rom_addr_arm": f"0x{base_arm + 4:08X}",
            "value": ptr1_arm,
            "size": 4,
            "encoding": "<I",
            "comment": f"scenario[{scenario_index}] ptr1 = 0x{ptr1_arm:08X}",
        })

    # +0x08: u32 ptr2 (ROM pointer to LZ77 compressed data)
    if ptr2_arm is not None:
        patches.append({
            "type": "bytes",
            "rom_file_offset": f"0x{base_file + 8:06X}",
            "rom_addr_arm": f"0x{base_arm + 8:08X}",
            "value": ptr2_arm,
            "size": 4,
            "encoding": "<I",
            "comment": f"scenario[{scenario_index}] ptr2 = 0x{ptr2_arm:08X}",
        })

    # +0x0C: u16 flag
    if flag is not None:
        patches.append({
            "type": "bytes",
            "rom_file_offset": f"0x{base_file + 12:06X}",
            "rom_addr_arm": f"0x{base_arm + 12:08X}",
            "value": flag,
            "size": 2,
            "encoding": "<H",
            "comment": f"scenario[{scenario_index}] flag = 0x{flag:04X}",
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
            scenario_index=scenario["index"],
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
            "scenario_table": f"ROM 0x{ROM_BATTLE_SCENARIO_ARM:08X} (file 0x{ROM_BATTLE_SCENARIO_FILE:X}), 16 entries × 16 bytes",
            "scenario_entry_format": "u16 tiles_x, u16 tiles_y, u32 ptr1, u32 ptr2, u16 flag, u16 extra",
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and summarize battle config content, or generate patches."
    )
    parser.add_argument("--units", default="sequel/content/units/sequel-units.json")
    parser.add_argument("--story", default="sequel/content/story/episode-01.json")
    parser.add_argument("--output")
    args = parser.parse_args()

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
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        import sys
        print(f"Patches written to {output_path}", file=sys.stderr)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
