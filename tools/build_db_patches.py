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

# A 48 Mbit GBA ROM occupies 0x08000000..0x085FFFFF in the cartridge
# address space.  Keep this explicit: accepting arbitrary u32 values here can
# turn an editor typo into an indirect branch/read outside the cartridge.
ROM_POINTER_MIN = 0x08000000
ROM_POINTER_MAX = 0x085FFFFF

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
    """Reject legacy battle rows without a proven ROM record identity.

    Imported ``scenario_id`` values such as 0x0101 and 0x0501 are gameplay
    values, not zero-based table indices. The old implementation multiplied
    them by 32 and wrote fixed templates over unrelated ROM regions. Lossless
    ``rom_*`` mirrors are the only safe build source until this editable schema
    stores an explicit ROM record key.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, name, scenario_id FROM battle_configs ORDER BY id"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_battle_config_unmapped",
        "db_table": "battle_configs",
        "db_row_id": int(row["id"]),
        "error": "legacy scenario_id is not a proven ROM table index",
        "description": (
            f"DB[battle_configs] id={row['id']} name={row['name']!r} "
            f"scenario_id={row['scenario_id']!r}: skipped unsafe template write"
        ),
    } for row in rows]


def generate_chapter_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject chapters without a proven ROM map/story record identity."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, chapter_number, title, title_ja, title_zh FROM chapters").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_chapter_unmapped",
        "db_table": "chapters",
        "db_row_id": int(row["id"]),
        "error": "chapter_number is not a proven ROM record index",
        "description": f"DB[chapters] id={row['id']}: skipped unsafe fixed-template write",
    } for row in rows]


def generate_unit_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy unit rows without a proven ROM character-record key.

    ``0x53F298`` was previously labelled a battle-slot character ID table.
    Its only direct code reference, at ``0x08080B2E``, instead indexes it as
    a u16 offset table used by a rendering/object routine. Writing editor
    ``char_id`` values there is unsafe. Lossless ``rom_units`` mirror rows may
    preserve the bytes, but the legacy semantic editor must not mutate them.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, char_id, name, hp FROM units").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_unit_unmapped",
        "db_table": "units",
        "db_row_id": int(row["id"]),
        "error": "legacy char_id has no proven ROM character-record mapping",
        "description": (
            f"DB[units] id={row['id']} char_id={row['char_id']!r} "
            f"name={row['name']!r}: skipped unsafe 0x53F298 write"
        ),
    } for row in rows]


def generate_skill_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject skills whose unit_id is not a proven ROM skill-row key."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, unit_id, name, damage FROM skills").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_skill_unmapped",
        "db_table": "skills",
        "db_row_id": int(row["id"]),
        "error": "unit_id is not a proven ROM skill-row index",
        "description": f"DB[skills] id={row['id']}: skipped unsafe fixed-template write",
    } for row in rows]


def generate_story_beat_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject story beats without a proven script pointer/record key."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, chapter_id, beat_index, title FROM story_beats").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_story_beat_unmapped",
        "db_table": "story_beats",
        "db_row_id": int(row["id"]),
        "error": "chapter_id/beat_index do not identify a proven ROM script pointer",
        "description": f"DB[story_beats] id={row['id']}: skipped placeholder pointer write",
    } for row in rows]


def generate_audio_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject audio rows without a proven table identity and record key."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, rom_offset, size, name FROM audio_files").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_audio_unmapped",
        "db_table": "audio_files",
        "db_row_id": int(row["id"]),
        "error": "rom_offset is not a proven audio index and 0x53F138 identity conflicts",
        "description": f"DB[audio_files] id={row['id']}: skipped synthesized pointer write",
    } for row in rows]


def generate_unit_position_patches(db_path: Path) -> list[dict[str, Any]]:
    """Write lossless ``rom_positions`` records to their proven ROM slots.

    This deliberately does not read the legacy ``unit_positions`` CRUD table:
    those rows describe runtime/editor concepts and have no proven one-row ROM
    mapping. Only the ROM mirror produced from the formation matrix is eligible.
    """
    if not db_path.exists():
        return []
    try:
        from tools.extract_positions import (
            GROUP_COUNT, RECORD_COUNT, RECORD_STRIDE, VARIANT_COUNT, record_offset,
        )
    except ModuleNotFoundError:  # direct ``python tools/build_mod.py`` execution
        from extract_positions import (
            GROUP_COUNT, RECORD_COUNT, RECORD_STRIDE, VARIANT_COUNT, record_offset,
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, raw_hex FROM rom_positions ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    entry_count = GROUP_COUNT * VARIANT_COUNT * RECORD_COUNT
    for row in rows:
        try:
            index = int(row["_idx"])
            if not 0 <= index < entry_count:
                raise ValueError(f"index {index} outside positions matrix")
            group_id, remainder = divmod(index, VARIANT_COUNT * RECORD_COUNT)
            variant_id, record_id = divmod(remainder, RECORD_COUNT)
            expected_offset = record_offset(group_id, variant_id, record_id)
            offset = int(row["_rom_offset"])
            if offset != expected_offset:
                if not (record_offset(0, 0, 0) <= offset < record_offset(
                    GROUP_COUNT - 1, VARIANT_COUNT - 1, RECORD_COUNT - 1
                ) + RECORD_STRIDE):
                    raise ValueError(f"offset 0x{offset:X} outside positions matrix")
                raise ValueError(
                    f"offset 0x{offset:X} does not match index {index} "
                    f"expected 0x{expected_offset:X}"
                )
            raw_hex = row["raw_hex"]
            if not isinstance(raw_hex, str):
                raise ValueError("raw_hex must be text")
            try:
                payload = bytes.fromhex(raw_hex)
            except ValueError as exc:
                raise ValueError(f"raw_hex is invalid: {exc}") from exc
            if len(payload) != RECORD_STRIDE:
                raise ValueError(
                    f"raw_hex must encode exactly {RECORD_STRIDE} bytes, got {len(payload)}"
                )
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": payload.hex(),
                "length": RECORD_STRIDE,
                "description": (
                    f"DB[rom_positions] index={index}: real formation record"
                ),
                "db_table": "rom_positions",
                "db_row_id": index,
            })
        except Exception as exc:
            patches.append({
                "type": "db_unit_position_error",
                "db_table": "rom_positions",
                "db_row_id": row["_idx"],
                "error": str(exc),
                "description": f"DB[rom_positions] index={row['_idx']} error: {exc}",
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


def _generate_u32_pointer_table_patches(
    db_path: Path,
    *,
    table: str,
    index_column: str,
    pointer_column: str,
    table_offset: int,
    entry_count: int,
    pointer_kind: str,
) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for an indexed u32 pointer table.

    ``pointer_kind`` is ``thumb`` for code pointers (bit 0 must be set),
    ``data`` for aligned data pointers (bit 0 must be clear), ``rom`` for
    byte-stream pointers where either low bit is a legitimate address bit, or
    ``raw`` for mixed u32 tables whose entries may be pointers or scalar tags.
    The stored ``_rom_offset`` is checked as an independent guard against a
    stale or incorrectly imported editor database.
    """
    if not db_path.exists():
        return []
    if pointer_kind not in {"thumb", "data", "rom", "raw"}:
        raise ValueError(f"unsupported pointer_kind: {pointer_kind}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f'SELECT _idx, _rom_offset, "{pointer_column}" FROM "{table}" '
            f'ORDER BY "{index_column}"'
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []

    patches: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    for row in rows:
        row_id = int(row["_idx"])
        try:
            index = int(row[index_column])
            pointer = int(row[pointer_column])
            expected_offset = table_offset + index * 4
            stored_offset = int(row["_rom_offset"])
            if not 0 <= index < entry_count:
                raise ValueError(f"index {index} outside 0..{entry_count - 1}")
            if index in seen_indices:
                raise ValueError(f"duplicate index {index}")
            seen_indices.add(index)
            if stored_offset != expected_offset:
                raise ValueError(
                    f"stale _rom_offset 0x{stored_offset:X}; expected 0x{expected_offset:X}"
                )
            if pointer_kind != "raw" and not ROM_POINTER_MIN <= pointer <= ROM_POINTER_MAX:
                raise ValueError(
                    f"pointer 0x{pointer:08X} outside 48 Mbit ROM address range"
                )
            if pointer_kind == "thumb" and pointer & 1 == 0:
                raise ValueError(f"Thumb pointer 0x{pointer:08X} has bit 0 clear")
            if pointer_kind == "data" and pointer & 1:
                raise ValueError(f"data pointer 0x{pointer:08X} has bit 0 set")

            payload = struct.pack("<I", pointer)
            patches.append({
                "type": "bytes",
                "offset": expected_offset,
                "after_hex": payload.hex(),
                "length": 4,
                "description": (
                    f"DB[{table}] index={index}: real u32 {pointer_kind} pointer"
                ),
                "db_table": table,
                "db_row_id": row_id,
            })
        except (TypeError, ValueError) as exc:
            patches.append({
                "type": "db_pointer_table_error",
                "db_table": table,
                "db_row_id": row_id,
                "error": str(exc),
                "description": f"DB[{table}] row={row_id} rejected: {exc}",
            })
    conn.close()
    return patches


def generate_battle_encounter_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for battle encounter rows.

    Each encounter row writes to the reserved region as an audit trail.
    The battle encounter table at 0x542384 contains 38 entries of mixed
    pointers and data values.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_battle_encounters", index_column="_idx",
        pointer_column="entry", table_offset=0x542384,
        entry_count=38, pointer_kind="raw",
    )
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
    """Generate validated real-ROM patches for battle handler pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The battle handler table at 0x53E6D8 contains 14 entries of u32
    pointers to Thumb event handler code.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_battle_handlers", index_column="_idx",
        pointer_column="handler_ptr", table_offset=0x53E6D8,
        entry_count=14, pointer_kind="thumb",
    )

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
        rows = conn.execute(
            "SELECT _idx, _rom_offset, hp, padding1, padding2, padding3, "
            "max_value, char_type, attack, defense FROM rom_character_stats_b "
            "ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            char_index = int(row["_idx"])
            if not 0 <= char_index < 18:
                raise ValueError(f"index {char_index} outside 0..17")
            table_offset = TABLE_OFFSET + char_index * ENTRY_SIZE
            if int(row["_rom_offset"]) != table_offset:
                raise ValueError("stale _rom_offset")
            fields = [int(row[name] or 0) for name in (
                "hp", "padding1", "padding2", "padding3", "max_value",
                "char_type", "attack", "defense",
            )]
            stat_data = struct.pack("<HHHHHHHH", *fields)
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": stat_data.hex(),
                "length": ENTRY_SIZE,
                "description": f"DB[rom_character_stats_b] idx={char_index}: stat entry",
                "db_table": "rom_character_stats_b",
                "db_row_id": char_index,
            })
        except Exception as exc:
            patches.append({
                "type": "db_character_stats_b_error",
                "db_table": "rom_character_stats_b",
                "db_row_id": int(row["_idx"]),
                "error": str(exc),
                "description": f"DB[rom_character_stats_b] idx={row['_idx']} error: {exc}",
            })
    conn.close()
    return patches


def generate_cutscene_script_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for cutscene script rows.

    Each row writes one validated u32 directly to the game-consumed table.
    The cutscene script table at 0x53DF70 contains 17 entries of u32
    pointers to cutscene/script data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_cutscene_scripts", index_column="_idx",
        pointer_column="script_ptr", table_offset=0x53DF70,
        entry_count=16, pointer_kind="data",
    )
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
    """Generate validated real-ROM patches for data table A pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The data table A at 0x5A14A4 contains 20 entries of u32 pointers.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_data_table_a", index_column="_idx",
        pointer_column="data_ptr", table_offset=0x5A14A4,
        entry_count=20, pointer_kind="data",
    )

def generate_data_table_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for data table B pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The data table B at 0x5A2120 contains 20 entries of u32 pointers.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_data_table_b", index_column="_idx",
        pointer_column="data_ptr", table_offset=0x5A2120,
        entry_count=20, pointer_kind="data",
    )

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
        rows = conn.execute(
            "SELECT _idx, _rom_offset, char_width FROM rom_fonts ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            char_index = int(row["_idx"])
            if not 0 <= char_index < 256:
                raise ValueError(f"index {char_index} outside 0..255")
            pixel_width = int(row["char_width"] or 0)
            table_offset = TABLE_OFFSET + char_index
            if int(row["_rom_offset"]) != table_offset:
                raise ValueError("stale _rom_offset")
            patches.append({
                "type": "bytes",
                "offset": table_offset,
                "after_hex": struct.pack("<B", pixel_width & 0xFF).hex(),
                "length": 1,
                "description": f"DB[rom_fonts] char={char_index}: width={pixel_width}",
                "db_table": "rom_fonts",
                "db_row_id": char_index,
            })
        except Exception as exc:
            patches.append({
                "type": "db_font_error",
                "db_table": "rom_fonts",
                "db_row_id": int(row["_idx"]),
                "error": str(exc),
                "description": f"DB[rom_fonts] idx={row['_idx']} error: {exc}",
            })
    conn.close()
    return patches


def generate_function_pointer_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for function pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The function pointer table at 0x53D5F4 contains 11 entries of u32
    pointers to Thumb code.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_function_pointers", index_column="_idx",
        pointer_column="func_ptr", table_offset=0x53D5F4,
        entry_count=11, pointer_kind="thumb",
    )

def generate_map_event_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for map event handlers.

    Each row writes one validated u32 directly to the game-consumed table.
    The map event table at 0x53EB08 contains 47 entries of u32 pointers
    to Thumb event handler code.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_map_events", index_column="_idx",
        pointer_column="handler_ptr", table_offset=0x53EB08,
        entry_count=47, pointer_kind="thumb",
    )

def generate_map_sprite_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for map sprite data pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The map sprite table at 0x53F1DC contains 47 entries of u32 pointers
    to sprite animation frame data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_map_sprites", index_column="_idx",
        pointer_column="sprite_ptr", table_offset=0x53F1DC,
        entry_count=47, pointer_kind="data",
    )

def generate_menu_ui_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for menu UI data pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The menu UI table at 0x5A5774 contains 20 entries of u32 pointers
    to menu/UI data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_menu_ui", index_column="_idx",
        pointer_column="ui_ptr", table_offset=0x5A5774,
        entry_count=20, pointer_kind="data",
    )

def generate_palette_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for palette rows.

    Each row writes one validated u32 directly to the game-consumed table.
    The palette table at 0x53F138 contains 88 entries of u32 pointers
    to 16-color RGB555 palette data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_palettes", index_column="_idx",
        pointer_column="palette_ptr", table_offset=0x53F138,
        entry_count=88, pointer_kind="rom",
    )
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
    """Generate validated real-ROM patches for resource data pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The resource pointer table at 0x596F0C contains 20 entries of u32
    pointers to resource data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_resource_pointers", index_column="_idx",
        pointer_column="resource_ptr", table_offset=0x596F0C,
        entry_count=20, pointer_kind="data",
    )

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

    Each row writes one validated u32 directly to the game-consumed table.
    The save state table at 0x53D848 contains 10 entries of 8 bytes
    (u32 ewram_addr + u32 sram_offset).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, ewram_buffer, sram_offset_field "
            "FROM rom_save_state ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            save_index = int(row["_idx"])
            if not 0 <= save_index < 10:
                raise ValueError(f"index {save_index} outside 0..9")
            offset = 0x53D848 + save_index * 8
            if int(row["_rom_offset"]) != offset:
                raise ValueError("stale _rom_offset")
            ewram_addr = int(row["ewram_buffer"] or 0)
            sram_offset = int(row["sram_offset_field"] or 0)
            payload = struct.pack("<II", ewram_addr, sram_offset)
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": payload.hex(),
                "length": 8,
                "description": f"DB[rom_save_state] idx={save_index}: save descriptor",
                "db_table": "rom_save_state",
                "db_row_id": save_index,
            })
        except Exception as exc:
            patches.append({
                "type": "db_save_state_error",
                "db_table": "rom_save_state",
                "db_row_id": int(row["_idx"]),
                "error": str(exc),
                "description": f"DB[rom_save_state] idx={row['_idx']} error: {exc}",
            })
    conn.close()
    return patches


def generate_sprite_animation_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for animation frame pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The sprite animation table at 0x53F200 contains 38 entries of u32
    pointers to animation frame data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_sprite_animations", index_column="_idx",
        pointer_column="anim_ptr", table_offset=0x53F200,
        entry_count=38, pointer_kind="data",
    )

def generate_story_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for story B byte-stream pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The story B table at 0x536BC8 contains 11 entries of u32 pointers
    to chapter data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_story_b", index_column="_idx",
        pointer_column="chapter_ptr", table_offset=0x536BC8,
        entry_count=11, pointer_kind="rom",
    )

def generate_story_c_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for story C byte-stream pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The story C table at 0x538FF0 contains 10 entries of u32 pointers
    to chapter data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_story_c", index_column="_idx",
        pointer_column="chapter_ptr", table_offset=0x538FF0,
        entry_count=10, pointer_kind="rom",
    )

def generate_story_d_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for story D byte-stream pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The story D table at 0x53AB78 contains 11 entries of u32 pointers
    to chapter data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_story_d", index_column="_idx",
        pointer_column="chapter_ptr", table_offset=0x53AB78,
        entry_count=11, pointer_kind="rom",
    )

def generate_story_e_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for story E byte-stream pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The story E table at 0x53C3C0 contains 9 entries of u32 pointers
    to chapter data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_story_e", index_column="_idx",
        pointer_column="chapter_ptr", table_offset=0x53C3C0,
        entry_count=9, pointer_kind="rom",
    )

def generate_tile_asset_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for tile asset data pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The tile asset table at 0x5A3218 contains 6 entries of u32 pointers
    to tile/map data.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_tile_assets", index_column="_idx",
        pointer_column="tile_ptr", table_offset=0x5A3218,
        entry_count=6, pointer_kind="data",
    )
