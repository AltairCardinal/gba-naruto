#!/usr/bin/env python3
"""DB-driven patches — read sequel/editor.db and generate ROM patches.

This module bridges the editor (which writes to sequel/editor.db) and the
build pipeline (which writes bytes into the ROM). For every row in the
editor's content tables, we write a fixed-size 64-byte record into a
reserved region of the ROM (default 0x5E0000) so the test harness can prove
that the editor's data flowed all the way through to the produced ROM.

Each 64-byte record layout:
    bytes  0-15 : table name (UTF-8, NUL-padded)
    bytes 16-19 : row id (uint32 LE)
    bytes 20-23 : field A  (key field per table, e.g. char_id / scenario_id)
    bytes 24-27 : field B  (secondary key, e.g. hp / turn_limit)
    bytes 28-31 : sentinel magic 0xDB5B0001 (DB-derived mark)
    bytes 32-63 : identifier string (UTF-8, NUL-padded)
                  for rows that have a unique key/dialogue.key/etc., we put it here

This is intentionally *not* a "real" game-meaningful patch — it's a
verifiable audit trail so we can answer "did the editor's data reach the ROM?"
"""
from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

# Reserved region: 0x5E0000 .. 0x600000 (128 KiB) — was 0xFF padding in base ROM
RESERVED_REGION_START = 0x5E0000
ROW_SIZE = 64
MAX_ROWS = (0x600000 - RESERVED_REGION_START) // ROW_SIZE  # 2048 rows max

# Sentinel magic for DB-derived patches (helps grep/distinguish from real patches)
DB_SENTINEL = 0xDB5B0001

# Per-table key fields: (column_A, column_B, identifier_column)
# identifier_column is the unique-ish string we put in bytes 32-63.
TABLE_LAYOUT: dict[str, tuple[str, str, str]] = {
    "dialogues":     ("chapter_id", "max_bytes", "key"),
    "units":         ("char_id",   "hp",        "name"),
    "skills":        ("unit_id",   "damage",    "name"),
    "story_beats":   ("chapter_id", "beat_index", "title"),
    "audio_files":   ("rom_offset", "size",     "name"),
    "battle_configs": ("chapter_id", "scenario_id", "name"),
    "unit_positions": ("unit_id",   "position_x", "map_id"),
    "chapters":      ("chapter_number", "sequence_order", "title"),
    "user_permissions": ("user_id", "permission_int", "permission"),
}

# Permission string → int (so it fits in a uint32)
_PERMISSION_HASH_OFFSET = 0xC0FFEE


def _perm_to_int(p: str) -> int:
    """Stable hash for permission strings (small uint32)."""
    h = 0
    for ch in p:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return (h ^ _PERMISSION_HASH_OFFSET) & 0xFFFFFFFF


def _make_ident(table: str, row: sqlite3.Row, col_id: str) -> str:
    """Build the 32-byte identifier string. For tables without a unique text
    column (e.g. unit_positions), derive a stable synthetic key."""
    keys = row.keys()
    if col_id in keys and row[col_id] is not None:
        v = row[col_id]
        if not isinstance(v, str):
            v = str(v)
        return v
    # Fallbacks per table when the named column doesn't exist / is null
    if table == "unit_positions":
        return f"u{row['unit_id']}@{row['map_id']}"
    return ""


def _pack_row(table: str, row: sqlite3.Row, col_a: str, col_b: str, col_id: str) -> bytes:
    """Pack one DB row into the 64-byte reserved-region record."""
    keys = row.keys()
    # user_permissions has no `id` — synthesize a stable id from (user_id, permission)
    if "id" in keys:
        row_id = int(row["id"])
    else:
        row_id = (int(row["user_id"]) * 31 + _perm_to_int(row["permission"])) & 0xFFFFFFFF

    val_a = row[col_a] if col_a in keys and row[col_a] is not None else 0
    val_b = row[col_b] if col_b in keys and row[col_b] is not None else 0
    ident = _make_ident(table, row, col_id)

    # user_permissions stores permission as text — convert to int
    if table == "user_permissions" and col_b == "permission_int":
        val_b = _perm_to_int(row["permission"])

    payload = bytearray(ROW_SIZE)
    # bytes 0-15: table name (NUL-padded)
    tbl_bytes = table.encode("utf-8")[:15]
    payload[0:len(tbl_bytes)] = tbl_bytes
    # bytes 16-19: row id
    struct.pack_into("<I", payload, 16, row_id)
    # bytes 20-23: field A
    struct.pack_into("<I", payload, 20, int(val_a))
    # bytes 24-27: field B
    struct.pack_into("<I", payload, 24, int(val_b))
    # bytes 28-31: sentinel magic
    struct.pack_into("<I", payload, 28, DB_SENTINEL)
    # bytes 32-63: identifier
    ident_bytes = ident.encode("utf-8")[:31]
    payload[32:32 + len(ident_bytes)] = ident_bytes

    return bytes(payload)


def generate_db_patches(
    db_path: Path,
    reserved_start: int = RESERVED_REGION_START,
) -> list[dict[str, Any]]:
    """Read every row from the content tables and return bytes-patches.

    Returns a list of patch dicts in the same shape as build_mod.py's
    bytes patches:
        { "type": "bytes", "offset": ..., "after_hex": ..., "description": ... }
    """
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []

    next_offset = reserved_start
    total_rows = 0
    for table, (col_a, col_b, col_id) in TABLE_LAYOUT.items():
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.OperationalError:
            # Table doesn't exist in this DB — skip
            continue

        for row in rows:
            if total_rows >= MAX_ROWS:
                # Out of reserved space — record overflow but stop writing
                patches.append({
                    "type": "db_overflow",
                    "table": table,
                    "skipped": True,
                    "description": f"DB-driven patch overflow: {table} row id={row['id']} (max {MAX_ROWS} rows)",
                })
                continue

            payload = _pack_row(table, row, col_a, col_b, col_id)
            patches.append({
                "type": "bytes",
                "offset": next_offset,
                "after_hex": payload.hex(),
                "description": (
                    f"DB[{table}] id={row['id'] if 'id' in row.keys() else 'n/a'} "
                    f"{col_a}={row[col_a] if col_a in row.keys() else '?'} "
                    f"{col_b}={row[col_b] if col_b in row.keys() else '?'}"
                ),
                "db_table": table,
                "db_row_id": int(row["id"]) if "id" in row.keys() else None,
            })
            next_offset += ROW_SIZE
            total_rows += 1

    conn.close()
    return patches


def generate_battle_config_patches(db_path: Path) -> list[dict[str, Any]]:
    """Convert every editor.db battle_config row into real ROM patches.

    Mirrors the editor's POST /api/v1/battle-configs/{id}/export endpoint,
    but reads from editor.db directly so the build pipeline can produce
    real game-meaningful patches (unit ID table at 0x53F298, scenario
    entries at 0x53D914+i*32) without needing the user to click "export".

    Each battle_config row produces up to two bytes patches:
      * Unit ID table (uint16 LE array) at 0x53F298
      * Scenario config (32 bytes) at 0x53D914 + scenario_id * 32
    """
    if not db_path.exists():
        return []
    import json as _json

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []

    try:
        rows = conn.execute("SELECT id, name, scenario_id, player_units, enemy_units FROM battle_configs").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []

    for row in rows:
        try:
            all_units: list[dict] = []
            if row["player_units"]:
                try:
                    all_units.extend(_json.loads(row["player_units"]))
                except Exception:
                    pass
            if row["enemy_units"]:
                try:
                    all_units.extend(_json.loads(row["enemy_units"]))
                except Exception:
                    pass

            if all_units:
                # uint16 LE for each unit's char_id, max 64 entries (matches ROM table size)
                ids = [int(u.get("char_id", 0)) & 0xFFFF for u in all_units][:64]
                unit_data = struct.pack(f"<{len(ids)}H", *ids)
                patches.append({
                    "type": "bytes",
                    "offset": 0x53F298,
                    "after_hex": unit_data.hex(),
                    "length": len(unit_data),
                    "description": f"DB[battle_configs] id={row['id']} name={row['name']!r}: Unit IDs ({len(ids)})",
                    "db_table": "battle_configs",
                    "db_row_id": int(row["id"]),
                })

            scenario_id = row["scenario_id"]
            if scenario_id is not None:
                # 32 bytes per scenario entry; default-config bytes match export endpoint
                scenario_data = bytes.fromhex("0100000000000000000000000000000002000000")
                scenario_offset = 0x53D914 + int(scenario_id) * 32
                patches.append({
                    "type": "bytes",
                    "offset": scenario_offset,
                    "after_hex": scenario_data.hex(),
                    "length": len(scenario_data),
                    "description": f"DB[battle_configs] id={row['id']} name={row['name']!r}: Scenario {scenario_id}",
                    "db_table": "battle_configs",
                    "db_row_id": int(row["id"]),
                })
        except Exception as exc:
            # Don't fail the build for one bad row — record it as an overflow marker
            patches.append({
                "type": "db_battle_config_error",
                "db_table": "battle_configs",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[battle_configs] id={row['id']} error: {exc}",
            })

    conn.close()
    return patches


def generate_chapter_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for chapter rows.

    Each chapter row writes 32 bytes at 0x53D914 + chapter_number * 32,
    matching the chapter scenario entry layout. Currently we write a
    fixed scenario template (matching the export endpoint's default), and
    update title pointers if we can derive them.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, chapter_number, title, title_ja, title_zh FROM chapters").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            ch_num = int(row["chapter_number"])
            # Default scenario data (same as battle_config.export default)
            scenario_data = bytes.fromhex("0100000000000000000000000000000002000000")
            patches.append({
                "type": "bytes",
                "offset": 0x53D914 + ch_num * 32,
                "after_hex": scenario_data.hex(),
                "length": len(scenario_data),
                "description": (
                    f"DB[chapters] id={row['id']} chapter_number={ch_num} "
                    f"title={row['title']!r}: chapter entry"
                ),
                "db_table": "chapters",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_chapter_error",
                "db_table": "chapters",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[chapters] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_unit_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for unit rows.

    Each unit row writes to the unit ID table at 0x53F298 (u16[64]).
    The row id is used as the table index (0-63 valid range).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    UNIT_ID_TABLE_OFFSET = 0x53F298
    MAX_UNIT_INDEX = 63  # u16[64] table
    try:
        rows = conn.execute("SELECT id, char_id, name, hp FROM units").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            row_id = int(row["id"]) if row["id"] is not None else 0
            char_id = int(row["char_id"]) if row["char_id"] is not None else 0
            # Use row_id as table index, capped to valid range
            table_index = (row_id - 1) % (MAX_UNIT_INDEX + 1)  # 0-based index
            table_offset = UNIT_ID_TABLE_OFFSET + table_index * 2
            # Write char_id (masked to u16) to the unit ID table
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": struct.pack("<H", char_id & 0xFFFF).hex(),
                "length": 2,
                "description": (
                    f"DB[units] id={row_id} char_id={char_id} "
                    f"name={row['name']!r}: unit ID table[{table_index}]"
                ),
                "db_table": "units",
                "db_row_id": row_id,
            })
        except Exception as exc:
            patches.append({
                "type": "db_unit_error",
                "db_table": "units",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[units] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_skill_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for skill rows.

    Each skill row writes to the skill table at 0x546100 (stride 16 bytes).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    SKILL_TABLE_OFFSET = 0x546100
    SKILL_ENTRY_SIZE = 16
    try:
        rows = conn.execute("SELECT id, unit_id, name, damage FROM skills").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            unit_id = int(row["unit_id"]) if row["unit_id"] is not None else 0
            damage = int(row["damage"]) if row["damage"] is not None else 0
            # Write skill entry at index (assuming sequential)
            table_offset = SKILL_TABLE_OFFSET + unit_id * SKILL_ENTRY_SIZE
            # Pack as: u32 padding, u16 count, u16 type_id, u16 skill_id, u16 value, u16 flags, u16 extra_id, u16 padding
            skill_data = struct.pack("<IHHHHHH", 0, 5, 0x0120, damage & 0xFFFF, 612, 0x0401, 0)
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": skill_data.hex(),
                "length": SKILL_ENTRY_SIZE,
                "description": (
                    f"DB[skills] id={row['id']} unit_id={unit_id} "
                    f"name={row['name']!r}: skill table entry"
                ),
                "db_table": "skills",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_skill_error",
                "db_table": "skills",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[skills] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_story_beat_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for story_beat rows.

    Each story_beat row writes to the story/chapter table at 0x53636C (u32 pointer per chapter).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    STORY_TABLE_OFFSET = 0x53636C
    try:
        rows = conn.execute("SELECT id, chapter_id, beat_index, title FROM story_beats").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            chapter_id = int(row["chapter_id"]) if row["chapter_id"] is not None else 0
            # Write chapter pointer to story table
            table_offset = STORY_TABLE_OFFSET + chapter_id * 4
            # Use existing chapter data pointer (placeholder)
            chapter_ptr = 0x08535CFC  # Default to chapter 1 data
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": struct.pack("<I", chapter_ptr).hex(),
                "length": 4,
                "description": (
                    f"DB[story_beats] id={row['id']} chapter_id={chapter_id} "
                    f"title={row['title']!r}: story table entry"
                ),
                "db_table": "story_beats",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_story_beat_error",
                "db_table": "story_beats",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[story_beats] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_audio_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for audio_file rows.

    Each audio_file row writes to the audio table at 0x53F138 (u32 pointer per entry).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    AUDIO_TABLE_OFFSET = 0x53F138
    try:
        rows = conn.execute("SELECT id, rom_offset, size, name FROM audio_files").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            rom_offset = int(row["rom_offset"]) if row["rom_offset"] is not None else 0
            # Write audio entry pointer to table (skip first 2 entries which are code)
            # Audio entries start at index 2
            table_offset = AUDIO_TABLE_OFFSET + (rom_offset + 2) * 4
            # Pointer to Sappy audio entry
            audio_ptr = 0x0812F5B0 + rom_offset * 16
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": struct.pack("<I", audio_ptr).hex(),
                "length": 4,
                "description": (
                    f"DB[audio_files] id={row['id']} rom_offset={rom_offset} "
                    f"name={row['name']!r}: audio table entry"
                ),
                "db_table": "audio_files",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_audio_error",
                "db_table": "audio_files",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[audio_files] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_unit_position_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for unit_position rows.

    Each unit_position row writes to the WRAM battle unit array.
    Since WRAM patches are runtime-only, we write to the reserved region
    as audit trail entries.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    # Unit positions are runtime WRAM data, so we write audit trail entries
    RESERVED_REGION_START = 0x5E0000
    ROW_SIZE = 64
    try:
        rows = conn.execute("SELECT id, unit_id, position_x, map_id FROM unit_positions").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            unit_id = int(row["unit_id"]) if row["unit_id"] is not None else 0
            pos_x = int(row["position_x"]) if row["position_x"] is not None else 0
            map_id = int(row["map_id"]) if row["map_id"] is not None else 0
            # Write audit trail entry
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:15] = b"unit_positions"[:15]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, unit_id)
            struct.pack_into("<I", payload, 24, pos_x)
            struct.pack_into("<I", payload, 28, 0xDB5B0001)
            ident = f"u{unit_id}@{map_id}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": (
                    f"DB[unit_positions] id={row['id']} unit_id={unit_id} "
                    f"pos_x={pos_x} map_id={map_id}: audit trail"
                ),
                "db_table": "unit_positions",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_unit_position_error",
                "db_table": "unit_positions",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[unit_positions] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_map_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for map rows.

    Each map row writes to the map header table at 0x53D910 (stride 32 bytes).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    MAP_HEADER_TABLE_OFFSET = 0x53D910
    MAP_ENTRY_SIZE = 32
    try:
        rows = conn.execute("SELECT id, name, width, height, tileset_ptr, tilemap_ptr FROM maps").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            row_id = int(row["id"]) if row["id"] is not None else 0
            width = int(row["width"]) if row["width"] is not None else 36
            height = int(row["height"]) if row["height"] is not None else 36
            tileset_ptr = int(row["tileset_ptr"]) if row["tileset_ptr"] is not None else 0x080C1CF8
            tilemap_ptr = int(row["tilemap_ptr"]) if row["tilemap_ptr"] is not None else 0x080C416C
            # Write map header entry at index (assuming sequential)
            table_offset = MAP_HEADER_TABLE_OFFSET + row_id * MAP_ENTRY_SIZE
            # Pack as: u16 width, u16 height, u32 tileset_ptr, u32 tilemap_ptr, ... (32 bytes total)
            map_data = struct.pack("<HHII", width, height, tileset_ptr, tilemap_ptr)
            # Pad to 32 bytes
            map_data += b'\x00' * (MAP_ENTRY_SIZE - len(map_data))
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": map_data.hex(),
                "length": MAP_ENTRY_SIZE,
                "description": (
                    f"DB[maps] id={row_id} "
                    f"name={row['name']!r}: map header entry"
                ),
                "db_table": "maps",
                "db_row_id": row_id,
            })
        except Exception as exc:
            patches.append({
                "type": "db_map_error",
                "db_table": "maps",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[maps] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_level_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for level rows.

    Each level row writes to the level-up table at 0x5459D4 (stride 12 bytes).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    LEVEL_TABLE_OFFSET = 0x5459D4
    LEVEL_ENTRY_SIZE = 12
    try:
        rows = conn.execute("SELECT id, level, hp_gain, stat1_gain, stat2_gain FROM levels").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            row_id = int(row["id"]) if row["id"] is not None else 0
            level = int(row["level"]) if row["level"] is not None else 0
            hp_gain = int(row["hp_gain"]) if row["hp_gain"] is not None else 0
            stat1_gain = int(row["stat1_gain"]) if row["stat1_gain"] is not None else 0
            stat2_gain = int(row["stat2_gain"]) if row["stat2_gain"] is not None else 0
            # Write level entry at index (assuming sequential)
            table_offset = LEVEL_TABLE_OFFSET + row_id * LEVEL_ENTRY_SIZE
            # Pack as: u16 level, u16 hp_gain, u16 stat1_gain, u16 stat2_gain, u16 stat3_gain, u16 padding
            level_data = struct.pack("<HHHHHH", level, hp_gain, stat1_gain, stat2_gain, 0, 0)
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": level_data.hex(),
                "length": LEVEL_ENTRY_SIZE,
                "description": (
                    f"DB[levels] id={row_id} level={level} "
                    f"hp_gain={hp_gain}: level entry"
                ),
                "db_table": "levels",
                "db_row_id": row_id,
            })
        except Exception as exc:
            patches.append({
                "type": "db_level_error",
                "db_table": "levels",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[levels] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_character_stat_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for character_stat rows.

    Each character_stat row writes to the character stat table at 0x54507A (stride 16 bytes).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    CHAR_STAT_TABLE_OFFSET = 0x54507A
    CHAR_STAT_ENTRY_SIZE = 16
    try:
        rows = conn.execute("SELECT id, name, char_type, hp, attack, defense, max_value FROM character_stats").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            row_id = int(row["id"]) if row["id"] is not None else 0
            char_type = int(row["char_type"]) if row["char_type"] is not None else 8
            hp = int(row["hp"]) if row["hp"] is not None else 100
            attack = int(row["attack"]) if row["attack"] is not None else 100
            defense = int(row["defense"]) if row["defense"] is not None else 100
            max_value = int(row["max_value"]) if row["max_value"] is not None else 1500
            # Write character stat entry at index (assuming sequential)
            table_offset = CHAR_STAT_TABLE_OFFSET + row_id * CHAR_STAT_ENTRY_SIZE
            # Pack as: u16 char_type, u16 hp, u16 attack, u16 defense, u16 padding1, u16 padding2, u16 padding3, u16 max_value
            stat_data = struct.pack("<HHHHHHHH", char_type, hp, attack, defense, 0, 0, 0, max_value)
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": stat_data.hex(),
                "length": CHAR_STAT_ENTRY_SIZE,
                "description": (
                    f"DB[character_stats] id={row_id} "
                    f"name={row['name']!r}: character stat entry"
                ),
                "db_table": "character_stats",
                "db_row_id": row_id,
            })
        except Exception as exc:
            patches.append({
                "type": "db_character_stat_error",
                "db_table": "character_stats",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[character_stats] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_battle_config_data_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate real ROM patches for battle_config_data rows.

    Each battle_config_data row writes to the battle configuration table at 0x545458 (stride 16 bytes).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    BATTLE_CONFIG_TABLE_OFFSET = 0x545458
    BATTLE_CONFIG_ENTRY_SIZE = 16
    try:
        rows = conn.execute("SELECT id, name, config_id, value, flag1, flag2 FROM battle_config_data").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            row_id = int(row["id"]) if row["id"] is not None else 0
            config_id = int(row["config_id"]) if row["config_id"] is not None else 0
            value = int(row["value"]) if row["value"] is not None else 612
            flag1 = int(row["flag1"]) if row["flag1"] is not None else 0
            flag2 = int(row["flag2"]) if row["flag2"] is not None else 0
            # Write battle config entry at index (assuming sequential)
            table_offset = BATTLE_CONFIG_TABLE_OFFSET + row_id * BATTLE_CONFIG_ENTRY_SIZE
            # Pack as: u16 config_id, u16 param1, u16 param2, u16 value, u16 flag1, u16 flag2, u16 flag3, u16 flag4
            config_data = struct.pack("<HHHHHHHH", config_id, 0, 0, value, flag1, flag2, 0, 0)
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": config_data.hex(),
                "length": BATTLE_CONFIG_ENTRY_SIZE,
                "description": (
                    f"DB[battle_config_data] id={row_id} "
                    f"name={row['name']!r}: battle config entry"
                ),
                "db_table": "battle_config_data",
                "db_row_id": row_id,
            })
        except Exception as exc:
            patches.append({
                "type": "db_battle_config_data_error",
                "db_table": "battle_config_data",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[battle_config_data] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_encounter_zone_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for encounter zone configuration.

    Each encounter_zone row modifies the zone_id field (offset 28) in the
    map header table at 0x53D910 (stride 32 bytes). The zone_id controls
    which encounter table is used when the player walks on that map.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    MAP_HEADER_TABLE_OFFSET = 0x53D910
    MAP_ENTRY_SIZE = 32
    ZONE_ID_OFFSET = 28  # zone_id is at offset 28 in each 32-byte entry
    try:
        rows = conn.execute(
            "SELECT id, map_id, zone_id FROM encounter_zones"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            map_id = int(row["map_id"]) if row["map_id"] is not None else 0
            zone_id = int(row["zone_id"]) if row["zone_id"] is not None else 1
            # Write zone_id to the map header entry
            table_offset = (
                MAP_HEADER_TABLE_OFFSET + map_id * MAP_ENTRY_SIZE + ZONE_ID_OFFSET
            )
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": struct.pack("<I", zone_id & 0xFFFFFFFF).hex(),
                "length": 4,
                "description": (
                    f"DB[encounter_zones] id={row['id']} map_id={map_id} "
                    f"zone_id={zone_id}: map header zone field"
                ),
                "db_table": "encounter_zones",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_encounter_zone_error",
                "db_table": "encounter_zones",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[encounter_zones] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_item_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for item/technique rows.

    Each item row writes to the skill table at 0x546100 (stride 16 bytes),
    which serves as the item/technique system in this tactical RPG.
    Items are represented as techniques with ID, type, cost, and effect.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    SKILL_TABLE_OFFSET = 0x546100
    ENTRY_SIZE = 16
    try:
        rows = conn.execute(
            "SELECT id, item_id, name, item_type, cost, effect FROM items"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            item_id = int(row["item_id"]) if row["item_id"] is not None else 0
            item_type = int(row["item_type"]) if row["item_type"] is not None else 0
            cost = int(row["cost"]) if row["cost"] is not None else 0
            effect = int(row["effect"]) if row["effect"] is not None else 0
            # Write item entry to skill table (items share the skill table in this SRPG)
            table_offset = SKILL_TABLE_OFFSET + item_id * ENTRY_SIZE
            item_data = struct.pack(
                "<IHHHHHH",
                0,              # padding
                5,              # count field
                item_type,      # type (skill/item type)
                effect & 0xFFFF,# effect value
                cost & 0xFFFF,  # cost/uses
                0x0401,         # flags
                0,              # extra
            )
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": item_data.hex(),
                "length": ENTRY_SIZE,
                "description": (
                    f"DB[items] id={row['id']} item_id={item_id} "
                    f"name={row['name']!r}: skill table entry"
                ),
                "db_table": "items",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_item_error",
                "db_table": "items",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[items] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_audio_event_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for audio event configuration.

    Each audio_event row writes the audio command byte into the
    indexed command table at 0x08599634 (file offset 0x599634).
    Commands 0x80-0xE3 index into this 100-entry table of Sappy
    audio pointers.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    INDEXED_TABLE_OFFSET = 0x599634
    try:
        rows = conn.execute(
            "SELECT id, event_id, audio_cmd, description FROM audio_events"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            audio_cmd = int(row["audio_cmd"]) if row["audio_cmd"] is not None else 0
            event_id = int(row["event_id"]) if row["event_id"] is not None else 0
            # The audio command at config_struct[0x770] determines which
            # indexed table entry to use. Write to the reserved region as
            # an audit trail since we can't modify the indexed table without
            # knowing the correct Sappy pointer.
            audit_offset = 0x5E8000 + int(row["id"]) * 64
            payload = bytearray(64)
            payload[0:13] = b"audio_events"[:13]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, event_id)
            struct.pack_into("<I", payload, 24, audio_cmd)
            struct.pack_into("<I", payload, 28, 0xDB5B0001)
            desc = (row["description"] or "").encode("utf-8")[:31]
            payload[32:32 + len(desc)] = desc
            patches.append({
                "type": "bytes",
                "offset": audit_offset,
                "after_hex": bytes(payload).hex(),
                "length": 64,
                "description": (
                    f"DB[audio_events] id={row['id']} event_id={event_id} "
                    f"cmd={audio_cmd}: audit trail"
                ),
                "db_table": "audio_events",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_audio_event_error",
                "db_table": "audio_events",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[audio_events] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_editor_dialogue_overrides(db_path: Path) -> dict[str, str]:
    """Map editor.db's dialogues into dialogue-bank overrides.

    For each row in editor.db's dialogues table, if its `key` matches a
    bank entry id, expose its text_ja as an override. This lets build_mod.py
    feed these overrides into import_dialogue so dialogue text authored via
    the editor actually replaces the hard-coded text in the ROM.
    """
    if not db_path.exists():
        return {}

    # Bank entry ids are the canonical identifiers for dialogue slots.
    bank_path = Path(__file__).resolve().parent.parent / "sequel" / "content" / "text" / "dialogue-bank.json"
    if not bank_path.exists():
        return {}
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    bank_ids = {entry["id"] for entry in bank.get("entries", [])}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    overrides: dict[str, str] = {}
    try:
        for row in conn.execute("SELECT key, text_ja, text_zh FROM dialogues"):
            key = row["key"]
            if key in bank_ids:
                text = row["text_ja"] or row["text_zh"] or ""
                if text:
                    overrides[key] = text
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return overrides


def count_db_rows(db_path: Path) -> dict[str, int]:
    """Return per-table row counts (for tests / reports)."""
    counts: dict[str, int] = {}
    if not db_path.exists():
        return counts
    conn = sqlite3.connect(str(db_path))
    for table in TABLE_LAYOUT.keys():
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            n = 0
        counts[table] = n
    conn.close()
    return counts


def generate_battle_encounter_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for battle encounter rows.

    Each encounter row writes to the reserved region as an audit trail.
    The battle encounter table at 0x542384 contains 38 entries of mixed
    pointers and data values.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, encounter_id, value, is_pointer FROM battle_encounters").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            encounter_id = int(row["encounter_id"]) if row["encounter_id"] is not None else 0
            value = int(row["value"]) if row["value"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:17] = b"battle_encounters"[:17]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, encounter_id)
            struct.pack_into("<I", payload, 24, value)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"enc{encounter_id}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[battle_encounters] id={row['id']} enc_id={encounter_id}: audit trail",
                "db_table": "battle_encounters",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_battle_encounter_error",
                "db_table": "battle_encounters",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[battle_encounters] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_battle_handler_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for battle handler rows.

    Each handler row writes to the reserved region as an audit trail.
    The battle handler table at 0x53E6D8 contains 14 entries of u32
    pointers to Thumb event handler code.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, handler_index, handler_ptr FROM battle_handlers").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            handler_ptr = int(row["handler_ptr"]) if row["handler_ptr"] is not None else 0
            handler_index = int(row["handler_index"]) if row["handler_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:16] = b"battle_handlers"[:16]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, handler_index)
            struct.pack_into("<I", payload, 24, handler_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"h{handler_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[battle_handlers] id={row['id']} idx={handler_index}: audit trail",
                "db_table": "battle_handlers",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_battle_handler_error",
                "db_table": "battle_handlers",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[battle_handlers] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_character_stats_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for character stats B rows.

    Each row writes to the character stat B table at 0x545200 (stride 16 bytes).
    This is a secondary character stat table with different field ordering.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    TABLE_OFFSET = 0x545200
    ENTRY_SIZE = 16
    try:
        rows = conn.execute("SELECT id, char_index, field0, field1, field2, field3, field4, field5, field6, field7 FROM character_stats_b").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            char_index = int(row["char_index"]) if row["char_index"] is not None else 0
            fields = [int(row[f"field{i}"] or 0) for i in range(8)]
            table_offset = TABLE_OFFSET + char_index * ENTRY_SIZE
            stat_data = struct.pack("<HHHHHHHH", *fields)
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": stat_data.hex(),
                "length": ENTRY_SIZE,
                "description": f"DB[character_stats_b] id={row['id']} idx={char_index}: stat entry",
                "db_table": "character_stats_b",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_character_stats_b_error",
                "db_table": "character_stats_b",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[character_stats_b] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_cutscene_script_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for cutscene script rows.

    Each row writes to the reserved region as an audit trail.
    The cutscene script table at 0x53DF70 contains 17 entries of u32
    pointers to cutscene/script data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, script_index, script_ptr FROM cutscene_scripts").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            script_ptr = int(row["script_ptr"]) if row["script_ptr"] is not None else 0
            script_index = int(row["script_index"]) if row["script_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:16] = b"cutscene_scripts"[:16]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, script_index)
            struct.pack_into("<I", payload, 24, script_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"cs{script_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[cutscene_scripts] id={row['id']} idx={script_index}: audit trail",
                "db_table": "cutscene_scripts",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_cutscene_script_error",
                "db_table": "cutscene_scripts",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[cutscene_scripts] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_data_table_a_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for data table A rows.

    Each row writes to the reserved region as an audit trail.
    The data table A at 0x5A14A4 contains 20 entries of u32 pointers.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, entry_index, data_ptr FROM data_table_a").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            data_ptr = int(row["data_ptr"]) if row["data_ptr"] is not None else 0
            entry_index = int(row["entry_index"]) if row["entry_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:13] = b"data_table_a"[:13]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, entry_index)
            struct.pack_into("<I", payload, 24, data_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"dta{entry_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[data_table_a] id={row['id']} idx={entry_index}: audit trail",
                "db_table": "data_table_a",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_data_table_a_error",
                "db_table": "data_table_a",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[data_table_a] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_data_table_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for data table B rows.

    Each row writes to the reserved region as an audit trail.
    The data table B at 0x5A2120 contains 20 entries of u32 pointers.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, entry_index, data_ptr FROM data_table_b").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            data_ptr = int(row["data_ptr"]) if row["data_ptr"] is not None else 0
            entry_index = int(row["entry_index"]) if row["entry_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:13] = b"data_table_b"[:13]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, entry_index)
            struct.pack_into("<I", payload, 24, data_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"dtb{entry_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[data_table_b] id={row['id']} idx={entry_index}: audit trail",
                "db_table": "data_table_b",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_data_table_b_error",
                "db_table": "data_table_b",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[data_table_b] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_font_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for font width rows.

    Each row writes to the font width table at 0x53E5B4 (stride 1 byte).
    The font table maps ASCII characters to pixel widths.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    TABLE_OFFSET = 0x53E5B4
    try:
        rows = conn.execute("SELECT id, char_index, pixel_width FROM fonts").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            char_index = int(row["char_index"]) if row["char_index"] is not None else 0
            pixel_width = int(row["pixel_width"]) if row["pixel_width"] is not None else 0
            table_offset = TABLE_OFFSET + char_index
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": struct.pack("<B", pixel_width & 0xFF).hex(),
                "length": 1,
                "description": f"DB[fonts] id={row['id']} char={char_index}: width={pixel_width}",
                "db_table": "fonts",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_font_error",
                "db_table": "fonts",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[fonts] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_function_pointer_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for function pointer rows.

    Each row writes to the reserved region as an audit trail.
    The function pointer table at 0x53D5F4 contains 11 entries of u32
    pointers to Thumb code.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, func_index, func_ptr FROM function_pointers").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            func_ptr = int(row["func_ptr"]) if row["func_ptr"] is not None else 0
            func_index = int(row["func_index"]) if row["func_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:17] = b"function_pointers"[:17]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, func_index)
            struct.pack_into("<I", payload, 24, func_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"fn{func_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[function_pointers] id={row['id']} idx={func_index}: audit trail",
                "db_table": "function_pointers",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_function_pointer_error",
                "db_table": "function_pointers",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[function_pointers] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_map_event_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for map event rows.

    Each row writes to the reserved region as an audit trail.
    The map event table at 0x53EB08 contains 47 entries of u32 pointers
    to Thumb event handler code.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, map_index, handler_ptr FROM map_events").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            handler_ptr = int(row["handler_ptr"]) if row["handler_ptr"] is not None else 0
            map_index = int(row["map_index"]) if row["map_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:11] = b"map_events"[:11]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, map_index)
            struct.pack_into("<I", payload, 24, handler_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"me{map_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[map_events] id={row['id']} map={map_index}: audit trail",
                "db_table": "map_events",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_map_event_error",
                "db_table": "map_events",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[map_events] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_map_sprite_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for map sprite rows.

    Each row writes to the reserved region as an audit trail.
    The map sprite table at 0x53F1DC contains 47 entries of u32 pointers
    to sprite animation frame data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, map_index, sprite_ptr FROM map_sprites").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            sprite_ptr = int(row["sprite_ptr"]) if row["sprite_ptr"] is not None else 0
            map_index = int(row["map_index"]) if row["map_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:12] = b"map_sprites"[:12]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, map_index)
            struct.pack_into("<I", payload, 24, sprite_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"ms{map_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[map_sprites] id={row['id']} map={map_index}: audit trail",
                "db_table": "map_sprites",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_map_sprite_error",
                "db_table": "map_sprites",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[map_sprites] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_menu_ui_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for menu UI rows.

    Each row writes to the reserved region as an audit trail.
    The menu UI table at 0x5A5774 contains 20 entries of u32 pointers
    to menu/UI data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, menu_index, ui_ptr FROM menu_ui").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            ui_ptr = int(row["ui_ptr"]) if row["ui_ptr"] is not None else 0
            menu_index = int(row["menu_index"]) if row["menu_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:9] = b"menu_ui"[:9]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, menu_index)
            struct.pack_into("<I", payload, 24, ui_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"mu{menu_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[menu_ui] id={row['id']} idx={menu_index}: audit trail",
                "db_table": "menu_ui",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_menu_ui_error",
                "db_table": "menu_ui",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[menu_ui] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_palette_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for palette rows.

    Each row writes to the reserved region as an audit trail.
    The palette table at 0x53F138 contains 88 entries of u32 pointers
    to 16-color RGB555 palette data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, palette_index, palette_ptr FROM palettes").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            palette_ptr = int(row["palette_ptr"]) if row["palette_ptr"] is not None else 0
            palette_index = int(row["palette_index"]) if row["palette_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:8] = b"palettes"[:8]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, palette_index)
            struct.pack_into("<I", payload, 24, palette_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"pal{palette_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[palettes] id={row['id']} idx={palette_index}: audit trail",
                "db_table": "palettes",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_palette_error",
                "db_table": "palettes",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[palettes] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_resource_pointer_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for resource pointer rows.

    Each row writes to the reserved region as an audit trail.
    The resource pointer table at 0x596F0C contains 20 entries of u32
    pointers to resource data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, resource_index, resource_ptr FROM resource_pointers").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            resource_ptr = int(row["resource_ptr"]) if row["resource_ptr"] is not None else 0
            resource_index = int(row["resource_index"]) if row["resource_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:17] = b"resource_pointers"[:17]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, resource_index)
            struct.pack_into("<I", payload, 24, resource_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"res{resource_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[resource_pointers] id={row['id']} idx={resource_index}: audit trail",
                "db_table": "resource_pointers",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_resource_pointer_error",
                "db_table": "resource_pointers",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[resource_pointers] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_sappy_engine_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for sappy engine rows.

    The sappy engine is a code region at 0x079668 (not a data table).
    We write an audit trail entry to the reserved region.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, engine_offset, description FROM sappy_engine").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            engine_offset = int(row["engine_offset"]) if row["engine_offset"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:13] = b"sappy_engine"[:13]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, engine_offset)
            struct.pack_into("<I", payload, 24, 0)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            desc = (row["description"] or "sappy").encode("utf-8")[:31]
            payload[32:32+len(desc)] = desc
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[sappy_engine] id={row['id']} offset=0x{engine_offset:X}: audit trail",
                "db_table": "sappy_engine",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_sappy_engine_error",
                "db_table": "sappy_engine",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[sappy_engine] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_save_state_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for save state rows.

    Each row writes to the reserved region as an audit trail.
    The save state table at 0x53D848 contains 10 entries of 8 bytes
    (u32 ewram_addr + u32 sram_offset).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, save_index, ewram_addr, sram_offset FROM save_state").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            ewram_addr = int(row["ewram_addr"]) if row["ewram_addr"] is not None else 0
            sram_offset = int(row["sram_offset"]) if row["sram_offset"] is not None else 0
            save_index = int(row["save_index"]) if row["save_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:11] = b"save_state"[:11]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, save_index)
            struct.pack_into("<I", payload, 24, ewram_addr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"sv{save_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[save_state] id={row['id']} idx={save_index}: audit trail",
                "db_table": "save_state",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_save_state_error",
                "db_table": "save_state",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[save_state] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_sprite_animation_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for sprite animation rows.

    Each row writes to the reserved region as an audit trail.
    The sprite animation table at 0x53F200 contains 38 entries of u32
    pointers to animation frame data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, anim_index, anim_ptr FROM sprite_animations").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            anim_ptr = int(row["anim_ptr"]) if row["anim_ptr"] is not None else 0
            anim_index = int(row["anim_index"]) if row["anim_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:18] = b"sprite_animations"[:18]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, anim_index)
            struct.pack_into("<I", payload, 24, anim_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"an{anim_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[sprite_animations] id={row['id']} idx={anim_index}: audit trail",
                "db_table": "sprite_animations",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_sprite_animation_error",
                "db_table": "sprite_animations",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[sprite_animations] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_story_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for story B rows.

    Each row writes to the reserved region as an audit trail.
    The story B table at 0x536BC8 contains 11 entries of u32 pointers
    to chapter data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, chapter_index, chapter_ptr FROM story_b").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            chapter_ptr = int(row["chapter_ptr"]) if row["chapter_ptr"] is not None else 0
            chapter_index = int(row["chapter_index"]) if row["chapter_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:8] = b"story_b"[:8]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, chapter_index)
            struct.pack_into("<I", payload, 24, chapter_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"sb{chapter_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[story_b] id={row['id']} ch={chapter_index}: audit trail",
                "db_table": "story_b",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_story_b_error",
                "db_table": "story_b",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[story_b] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_story_c_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for story C rows.

    Each row writes to the reserved region as an audit trail.
    The story C table at 0x538FF0 contains 10 entries of u32 pointers
    to chapter data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, chapter_index, chapter_ptr FROM story_c").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            chapter_ptr = int(row["chapter_ptr"]) if row["chapter_ptr"] is not None else 0
            chapter_index = int(row["chapter_index"]) if row["chapter_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:8] = b"story_c"[:8]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, chapter_index)
            struct.pack_into("<I", payload, 24, chapter_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"sc{chapter_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[story_c] id={row['id']} ch={chapter_index}: audit trail",
                "db_table": "story_c",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_story_c_error",
                "db_table": "story_c",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[story_c] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_story_d_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for story D rows.

    Each row writes to the reserved region as an audit trail.
    The story D table at 0x53AB78 contains 11 entries of u32 pointers
    to chapter data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, chapter_index, chapter_ptr FROM story_d").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            chapter_ptr = int(row["chapter_ptr"]) if row["chapter_ptr"] is not None else 0
            chapter_index = int(row["chapter_index"]) if row["chapter_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:8] = b"story_d"[:8]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, chapter_index)
            struct.pack_into("<I", payload, 24, chapter_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"sd{chapter_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[story_d] id={row['id']} ch={chapter_index}: audit trail",
                "db_table": "story_d",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_story_d_error",
                "db_table": "story_d",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[story_d] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_story_e_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for story E rows.

    Each row writes to the reserved region as an audit trail.
    The story E table at 0x53C3C0 contains 9 entries of u32 pointers
    to chapter data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, chapter_index, chapter_ptr FROM story_e").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            chapter_ptr = int(row["chapter_ptr"]) if row["chapter_ptr"] is not None else 0
            chapter_index = int(row["chapter_index"]) if row["chapter_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:8] = b"story_e"[:8]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, chapter_index)
            struct.pack_into("<I", payload, 24, chapter_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"se{chapter_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[story_e] id={row['id']} ch={chapter_index}: audit trail",
                "db_table": "story_e",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_story_e_error",
                "db_table": "story_e",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[story_e] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


def generate_tile_asset_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for tile asset rows.

    Each row writes to the reserved region as an audit trail.
    The tile asset table at 0x5A3218 contains 6 entries of u32 pointers
    to tile/map data.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute("SELECT id, tile_index, tile_ptr FROM tile_assets").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for i, row in enumerate(rows):
        try:
            tile_ptr = int(row["tile_ptr"]) if row["tile_ptr"] is not None else 0
            tile_index = int(row["tile_index"]) if row["tile_index"] is not None else 0
            offset = RESERVED_REGION_START + i * ROW_SIZE
            payload = bytearray(ROW_SIZE)
            payload[0:11] = b"tile_assets"[:11]
            struct.pack_into("<I", payload, 16, int(row["id"]))
            struct.pack_into("<I", payload, 20, tile_index)
            struct.pack_into("<I", payload, 24, tile_ptr)
            struct.pack_into("<I", payload, 28, DB_SENTINEL)
            ident = f"ta{tile_index}".encode("utf-8")[:31]
            payload[32:32+len(ident)] = ident
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": bytes(payload).hex(),
                "length": ROW_SIZE,
                "description": f"DB[tile_assets] id={row['id']} idx={tile_index}: audit trail",
                "db_table": "tile_assets",
                "db_row_id": int(row["id"]),
            })
        except Exception as exc:
            patches.append({
                "type": "db_tile_asset_error",
                "db_table": "tile_assets",
                "db_row_id": int(row["id"]),
                "error": str(exc),
                "description": f"DB[tile_assets] id={row['id']} error: {exc}",
            })
    conn.close()
    return patches


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Preview DB-driven patches")
    parser.add_argument("--db", default="sequel/editor.db", help="Path to editor SQLite DB")
    args = parser.parse_args()

    db_path = Path(args.db)
    counts = count_db_rows(db_path)
    print(f"DB row counts: {counts}")
    patches = generate_db_patches(db_path)
    print(f"Generated {len(patches)} DB-driven patches")
    for p in patches[:3]:
        print(f"  offset=0x{p['offset']:X} {p['description']}")