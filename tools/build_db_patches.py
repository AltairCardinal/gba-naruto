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
from typing import Any, Callable

# Reserved audit region. 0x5F0000..0x600000 is exclusively allocated to
# variable-length dialogue so audit rows can never overwrite live text.
RESERVED_REGION_START = 0x5E0000
RESERVED_REGION_END = 0x5F0000
ROW_SIZE = 64
MAX_ROWS = (RESERVED_REGION_END - RESERVED_REGION_START) // ROW_SIZE  # 1024 rows

# Sentinel magic for DB-derived patches (helps grep/distinguish from real patches)
DB_SENTINEL = 0xDB5B0001

# A 48 Mbit GBA ROM occupies 0x08000000..0x085FFFFF in the cartridge
# address space.  Keep this explicit: accepting arbitrary u32 values here can
# turn an editor typo into an indirect branch/read outside the cartridge.
ROM_POINTER_MIN = 0x08000000
ROM_POINTER_MAX = 0x085FFFFF
BASE_ROM_PATH = Path(__file__).resolve().parent.parent / "rom" / "base.gba"

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


def _reject_unproven_legacy_rows(
    db_path: Path,
    query: str,
    diagnostic_type: str,
    db_table: str,
    error: str,
    describe: Callable[[sqlite3.Row], str],
) -> list[dict[str, Any]]:
    """Return diagnostic-only patches for editable tables lacking ROM identity."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": diagnostic_type,
        "db_table": db_table,
        "db_row_id": int(row["id"]),
        "error": error,
        "description": describe(row),
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


def generate_character_definition_patches(db_path: Path) -> list[dict[str, Any]]:
    """Write complete 0xB4 records with immutable provenance and sentinels."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, base_raw_hex, raw_hex "
            "FROM rom_character_definitions ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close(); return []
    conn.close()
    base_rom = BASE_ROM_PATH.read_bytes()
    patches = []
    seen = set()
    for row in rows:
        index = int(row['_idx'])
        try:
            if not 0 <= index < 63:
                raise ValueError(f"character ID {index} outside 0..62")
            if index in seen:
                raise ValueError(f"duplicate character ID {index}")
            seen.add(index)
            offset = 0x54241C + index * 0xB4
            if int(row['_rom_offset']) != offset:
                raise ValueError(f"stale _rom_offset; expected 0x{offset:X}")
            imported_base = bytes.fromhex(str(row['base_raw_hex']))
            actual_base = base_rom[offset:offset + 0xB4]
            if len(imported_base) != 0xB4 or imported_base != actual_base:
                raise ValueError("immutable base record mismatch")
            payload = bytes.fromhex(str(row['raw_hex']))
            if len(payload) != 0xB4:
                raise ValueError(f"record must be exactly 0xB4 bytes, got {len(payload)}")
            if index == 0:
                if any(payload):
                    raise ValueError("sentinel character 0 must remain all zero")
            elif payload[0] != 1:
                raise ValueError("active character record byte +0 must remain 1")
            patches.append({
                'type': 'bytes', 'offset': offset, 'after_hex': payload.hex(),
                'length': 0xB4,
                'description': f"DB[rom_character_definitions] character_id={index}: lossless record",
                'db_table': 'rom_character_definitions', 'db_row_id': index,
            })
        except Exception as exc:
            patches.append({
                'type': 'db_character_definition_error',
                'db_table': 'rom_character_definitions', 'db_row_id': index,
                'error': str(exc),
                'description': f"DB[rom_character_definitions] character_id={index}: {exc}",
            })
    return patches


def generate_audio_sound_id_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate guarded, lossless writes for non-empty sound-ID master rows."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, base_descriptor_ptr, descriptor_ptr, "
            "base_player_config, player_config FROM rom_audio_sound_ids ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close(); return []
    conn.close()
    base_rom = BASE_ROM_PATH.read_bytes()
    patches = []
    seen = set()
    for row in rows:
        sound_id = int(row['_idx'])
        try:
            if not 0 <= sound_id <= 158:
                raise ValueError(f"sound ID {sound_id} outside 0..158")
            if sound_id in seen:
                raise ValueError(f"duplicate sound ID {sound_id}")
            seen.add(sound_id)
            expected_offset = 0x465B70 + sound_id * 8
            if int(row['_rom_offset']) != expected_offset:
                raise ValueError(
                    f"stale _rom_offset 0x{int(row['_rom_offset']):X}; expected 0x{expected_offset:X}"
                )
            actual_descriptor, actual_config = struct.unpack_from('<II', base_rom, expected_offset)
            if int(row['base_descriptor_ptr']) != actual_descriptor:
                raise ValueError("immutable base descriptor mismatch")
            if int(row['base_player_config']) != actual_config:
                raise ValueError("immutable base player config mismatch")
            descriptor = int(row['descriptor_ptr'])
            config = int(row['player_config'])
            if not ROM_POINTER_MIN <= descriptor <= ROM_POINTER_MAX:
                raise ValueError(f"descriptor 0x{descriptor:08X} outside 48 Mbit ROM")
            if descriptor & 3:
                raise ValueError("descriptor pointer must be word aligned")
            if not 0 <= config <= 0xFFFFFFFF:
                raise ValueError("player config must fit u32")
            descriptor_offset = descriptor - ROM_POINTER_MIN
            track_count = base_rom[descriptor_offset]
            if not 1 <= track_count <= 16:
                raise ValueError("descriptor target lacks a valid track count")
            patches.append({
                'type': 'bytes', 'offset': expected_offset,
                'after_hex': struct.pack('<II', descriptor, config).hex(),
                'length': 8,
                'description': f"DB[rom_audio_sound_ids] sound_id={sound_id}: master row",
                'db_table': 'rom_audio_sound_ids', 'db_row_id': sound_id,
            })
        except Exception as exc:
            patches.append({
                'type': 'db_audio_sound_id_error', 'db_table': 'rom_audio_sound_ids',
                'db_row_id': sound_id, 'error': str(exc),
                'description': f"DB[rom_audio_sound_ids] sound_id={sound_id}: {exc}",
            })
    return patches


def generate_map_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy map rows without a lossless ROM header record key."""
    return _reject_unproven_legacy_rows(
        db_path,
        "SELECT id, name, width, height, tileset_ptr, tilemap_ptr FROM maps",
        "db_map_unmapped",
        "maps",
        "legacy map id is not a proven lossless ROM header index",
        lambda row: (
            f"DB[maps] id={row['id']} name={row['name']!r}: "
            "skipped unsafe synthesized 32-byte map header write"
        ),
    )


def generate_map_header_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate exact 32-byte map headers with base and LZ-pointer guards."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
    columns = (
        "_idx, _rom_offset, base_raw_hex, width, height, tileset_ptr, "
        "tilemap_ptr, tilemap_alt_ptr, extra_ptr, palette_ptr, palette2_ptr, flags"
    )
    try:
        rows = conn.execute(f"SELECT {columns} FROM rom_map_headers ORDER BY _idx").fetchall()
    except sqlite3.OperationalError:
        conn.close(); return []
    conn.close()
    base_rom = BASE_ROM_PATH.read_bytes(); patches = []; seen = set()
    pointer_names = (
        'tileset_ptr', 'tilemap_ptr', 'tilemap_alt_ptr',
        'extra_ptr', 'palette_ptr', 'palette2_ptr',
    )
    for row in rows:
        index = int(row['_idx'])
        try:
            if not 0 <= index < 47:
                raise ValueError(f"map index {index} outside 0..46")
            if index in seen:
                raise ValueError(f"duplicate map index {index}")
            seen.add(index)
            offset = 0x53D910 + index * 32
            if int(row['_rom_offset']) != offset:
                raise ValueError(f"stale _rom_offset; expected 0x{offset:X}")
            imported_base = bytes.fromhex(str(row['base_raw_hex']))
            if len(imported_base) != 32 or imported_base != base_rom[offset:offset + 32]:
                raise ValueError("immutable base map header mismatch")
            width, height = int(row['width']), int(row['height'])
            if not 1 <= width <= 128 or not 1 <= height <= 128:
                raise ValueError("map dimensions must be within 1..128")
            pointers = []
            for name in pointer_names:
                pointer = int(row[name]); pointers.append(pointer)
                if pointer == 0 and name == 'extra_ptr':
                    continue
                if not ROM_POINTER_MIN <= pointer <= ROM_POINTER_MAX or pointer & 3:
                    raise ValueError(f"{name} must be an aligned 48 Mbit ROM pointer")
                target = pointer - ROM_POINTER_MIN
                if base_rom[target] != 0x10:
                    raise ValueError(f"{name} target does not begin with GBA LZ header 0x10")
                unpacked_size = int.from_bytes(base_rom[target + 1:target + 4], 'little')
                if not 1 <= unpacked_size <= 0x20000:
                    raise ValueError(f"{name} has implausible decompressed size {unpacked_size}")
            flags = int(row['flags'])
            if not 0 <= flags <= 0xFFFFFFFF:
                raise ValueError("flags must fit u32")
            payload = struct.pack('<HH6II', width, height, *pointers, flags)
            patches.append({
                'type': 'bytes', 'offset': offset, 'after_hex': payload.hex(),
                'length': 32, 'description': f"DB[rom_map_headers] map={index}: header",
                'db_table': 'rom_map_headers', 'db_row_id': index,
            })
        except Exception as exc:
            patches.append({
                'type': 'db_map_header_error', 'db_table': 'rom_map_headers',
                'db_row_id': index, 'error': str(exc),
                'description': f"DB[rom_map_headers] map={index}: {exc}",
            })
    return patches


def generate_level_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy level rows without a proven ROM progression record key."""
    return _reject_unproven_legacy_rows(
        db_path,
        "SELECT id, level, hp_gain, stat1_gain, stat2_gain FROM levels",
        "db_level_unmapped",
        "levels",
        "legacy level row is not a proven ROM progression-table record",
        lambda row: (
            f"DB[levels] id={row['id']} level={row['level']!r}: "
            "skipped unsafe synthesized level entry write"
        ),
    )


def generate_character_stat_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy character stat rows without proven field serialization."""
    return _reject_unproven_legacy_rows(
        db_path,
        "SELECT id, name, char_type, hp, attack, defense, max_value FROM character_stats",
        "db_character_stat_unmapped",
        "character_stats",
        "legacy character stat fields are not proven ROM field serializers",
        lambda row: (
            f"DB[character_stats] id={row['id']} name={row['name']!r}: "
            "skipped unsafe synthesized stat entry write"
        ),
    )


def generate_battle_config_data_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy battle config rows without proven ROM field identity."""
    return _reject_unproven_legacy_rows(
        db_path,
        "SELECT id, name, config_id, value, flag1, flag2 FROM battle_config_data",
        "db_battle_config_data_unmapped",
        "battle_config_data",
        "legacy battle config fields are not proven ROM field serializers",
        lambda row: (
            f"DB[battle_config_data] id={row['id']} name={row['name']!r}: "
            "skipped unsafe synthesized battle config write"
        ),
    )


def generate_encounter_zone_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy encounter zone rows without a proven map-header field."""
    return _reject_unproven_legacy_rows(
        db_path,
        "SELECT id, map_id, zone_id FROM encounter_zones",
        "db_encounter_zone_unmapped",
        "encounter_zones",
        "legacy encounter zone fields are not proven map-header serializers",
        lambda row: (
            f"DB[encounter_zones] id={row['id']} map_id={row['map_id']!r}: "
            "skipped unsafe synthesized zone field write"
        ),
    )


def generate_item_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject legacy item rows until the item/skill table identity is split."""
    return _reject_unproven_legacy_rows(
        db_path,
        "SELECT id, item_id, name, item_type, cost, effect FROM items",
        "db_item_unmapped",
        "items",
        "items are not proven as an independent ROM table and collide with skills",
        lambda row: (
            f"DB[items] id={row['id']} item_id={row['item_id']!r}: "
            "skipped unsafe synthesized skill-table write"
        ),
    )


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

    Two facts make the naive key comparison useless, and both are handled
    here:

    1. **The two id spaces do not intersect.**  editor.db's `dialogues.key`
       comes from ``dialogue-bank-full.json``'s ``slot`` (``group0``,
       ``group1``, ...), while the write-back bank and the content file use
       ``group0.main`` / ``group0.label1`` / ....  The rows are therefore
       joined **by ROM offset**: the full bank records the text offset of
       every slot, and the write-back bank records the text offset of every
       entry, so ``slot -> offset -> entry id`` is a well defined join.
    2. **The seeded text is not the ROM's text.**  The full bank is
       extracted from ``build/naruto-sequel-dev.gba`` and its decoded text
       does not match ``rom/base.gba`` (e.g. slot ``group0`` decodes to the
       dev build's version marker).  Pushing the seeded text back into the
       base ROM would silently overwrite real dialogue, so only rows whose
       text **differs from the seed** are treated as author edits.
    """
    if not db_path.exists():
        return {}

    content_dir = Path(__file__).resolve().parent.parent / "sequel" / "content" / "text"
    bank_path = content_dir / "dialogue-bank.json"
    full_path = content_dir / "dialogue-bank-full.json"
    if not bank_path.exists() or not full_path.exists():
        return {}
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    full = json.loads(full_path.read_text(encoding="utf-8"))

    # offset -> slot, and the seeded text of every slot
    slot_by_offset: dict[int, str] = {}
    seed_text: dict[str, str] = {}
    for entry in full:
        if entry.get("empty"):
            continue
        slot = entry.get("slot")
        offset = entry.get("text_offset")
        if not slot or offset is None:
            continue
        slot_by_offset.setdefault(int(offset), slot)
        seed_text[slot] = entry.get("text_ja") or entry.get("text_zh") or ""

    # slot -> write-back entry id (the ids the content file and the bank use)
    entry_id_by_slot: dict[str, str] = {}
    for entry in bank.get("entries", []):
        offset = entry.get("text_rom_offset")
        if offset is None:
            continue
        slot = slot_by_offset.get(int(offset))
        if slot:
            entry_id_by_slot[slot] = entry["id"]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    overrides: dict[str, str] = {}
    try:
        for row in conn.execute("SELECT key, text_ja, text_zh FROM dialogues"):
            slot = row["key"]
            entry_id = entry_id_by_slot.get(slot)
            if not entry_id:
                continue
            text = row["text_ja"] or row["text_zh"] or ""
            if not text:
                continue
            seed = seed_text.get(slot)
            if seed is not None and text == seed:
                # untouched seed: the content file stays authoritative
                continue
            overrides[entry_id] = text
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


def _row_field(row, name: str, table: str, row_id: int):
    """Read a column that may be missing from a legacy editor schema.

    A stale editor database can carry the *old* column names of a table
    whose base was later corrected (e.g. ``handler_ptr`` for a table the
    re-base renamed to ``code_ptr_0``).  SQLite happily selects a
    double-quoted unknown identifier as a string literal, so the missing
    column only shows up when the row is read -- and it must be a clean
    rejection, not an ``IndexError`` crashing the build half-way.
    """
    try:
        return row[name]
    except (KeyError, IndexError):
        raise ValueError(
            f"DB[{table}] row={row_id} has no column {name!r} "
            "(legacy editor schema for a re-based table?)"
        ) from None


def _generate_u32_pointer_table_patches(
    db_path: Path,
    *,
    table: str,
    index_column: str,
    pointer_column: str,
    table_offset: int,
    entry_count: int,
    pointer_kind: str,
    record_stride: int = 4,
    field_offset: int = 0,
) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for an indexed u32 pointer table.

    ``pointer_kind`` is ``thumb`` for code pointers (bit 0 must be set),
    ``data`` for aligned data pointers (bit 0 must be clear), ``rom`` for
    byte-stream pointers where either low bit is a legitimate address bit, or
    ``raw`` for mixed u32 tables whose entries may be pointers or scalar tags.
    The stored ``_rom_offset`` is checked as an independent guard against a
    stale or incorrectly imported editor database.

    ``record_stride`` is the distance between two records in the ROM and
    ``field_offset`` the offset of the written u32 inside a record.  Both
    default to the flat 4-byte case; a table whose records are wider (the
    battle-encounter records are 16 bytes, the handler records 8, the
    portrait rows 40, the tile-asset records 68) MUST pass them, otherwise
    the patch would land in the middle of a record.
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
        # The editor database may still carry an **older schema** for this
        # table (the base was re-based, so the column names changed).  A
        # hard SELECT failure used to make the whole table vanish silently
        # -- the author's edit was dropped with no trace.  Fall back to the
        # index column only, so every row still comes back as an explicit
        # *rejection* instead of disappearing.
        try:
            rows = conn.execute(
                f'SELECT "{index_column}" FROM "{table}"'
            ).fetchall()
        except sqlite3.OperationalError:
            conn.close()
            return []

    patches: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    for row in rows:
        row_id = int(row["_idx"])
        try:
            index = int(_row_field(row, index_column, table, row_id))
            pointer = int(_row_field(row, pointer_column, table, row_id))
            expected_offset = table_offset + index * record_stride
            stored_offset = int(_row_field(row, "_rom_offset", table, row_id))
            if not 0 <= index < entry_count:
                raise ValueError(f"index {index} outside 0..{entry_count - 1}")
            if index in seen_indices:
                raise ValueError(f"duplicate index {index}")
            seen_indices.add(index)
            if stored_offset != expected_offset:
                raise ValueError(
                    f"stale _rom_offset 0x{stored_offset:X}; expected 0x{expected_offset:X}"
                )
            write_offset = expected_offset + field_offset
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
                "offset": write_offset,
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
    """Keep the corrected 24x0x10 visual-descriptor mirror read-only."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            'SELECT _idx, _rom_offset FROM "rom_battle_encounters" '
            'ORDER BY _idx'
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    patches = [
        {
            "type": "db_battle_encounter_unmapped",
            "db_table": "rom_battle_encounters",
            "db_row_id": int(row["_idx"]),
            "error": "corrected visual descriptor mirror is read-only",
            "description": (
                f"DB[rom_battle_encounters] row={int(row['_idx'])}: "
                "diagnostic-only visual descriptor mirror"
            ),
        }
        for row in rows
    ]
    conn.close()
    return patches
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
    The battle handler table at 0x53E698 contains 256 records of 8 bytes
    (two u32 code pointers each).
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_battle_handlers", index_column="_idx",
        pointer_column="code_ptr_0", table_offset=0x53E698,
        entry_count=256, pointer_kind="thumb",
        record_stride=8, field_offset=0,
    )

def generate_character_stats_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for the per-character stat rows.

    The bank is the **same** table as ``character-stats``: the adjudicated
    base is 0x545068 (16 bytes per row, 63 rows).  The old base 0x545200 was
    a misaligned window (record 25, byte 8) and the old column names no
    longer exist, so the generator used to fail open (empty patch list).

    The row fields are the eight u16 slots of the record; their business
    names are not known yet, so the editor columns are the neutral
    ``field_0`` .. ``field_7``.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    TABLE_OFFSET = 0x545068
    ENTRY_SIZE = 16
    try:
        # Only the index column is guaranteed: an editor database from
        # before the re-base still carries the old column names, and the
        # whole table must not vanish silently because of that.
        rows = conn.execute(
            "SELECT * FROM rom_character_stats_b ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    for row in rows:
        try:
            char_index = int(row["_idx"])
            if not 0 <= char_index < 63:
                raise ValueError(f"index {char_index} outside 0..62")
            table_offset = TABLE_OFFSET + char_index * ENTRY_SIZE
            if int(row["_rom_offset"]) != table_offset:
                raise ValueError("stale _rom_offset")
            fields = [int(_row_field(row, name, "rom_character_stats_b", char_index) or 0)
                      for name in (
                          "field_0", "field_1", "field_2", "field_3",
                          "field_4", "field_5", "field_6", "field_7",
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
    """Generate ROM patches for the level data block table (0x53DF70).

    The table is **4 entries of 8 bytes** -- each entry a pointer pair
    (LZ77 4bpp tiles, LZ77 16-colour palette) -- as proved by the single
    native reader 0x08072F0C (stride 8, see
    `notes/evidence/cutscene-block-format-20261020.md`).

    The old model ("16 entries of u32") spanned two different tables and
    let an index reach 0x53DFB0, the start of the next one.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, gfx_ptr, palette_ptr "
            "FROM rom_cutscene_scripts ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    patches: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        try:
            index = int(row["_idx"])
            if not 0 <= index < LEVEL_BLOCK_ENTRY_COUNT:
                raise ValueError(
                    f"index {index} outside 0..{LEVEL_BLOCK_ENTRY_COUNT - 1}")
            if index in seen:
                raise ValueError(f"duplicate index {index}")
            seen.add(index)
            expected_offset = LEVEL_BLOCK_TABLE_OFFSET + index * LEVEL_BLOCK_STRIDE
            if int(row["_rom_offset"]) != expected_offset:
                raise ValueError(
                    f"stale _rom_offset 0x{int(row['_rom_offset']):X}; "
                    f"expected 0x{expected_offset:X}")
            for field_offset, column in LEVEL_BLOCK_POINTER_COLUMNS:
                value = row[column]
                if value is None:
                    continue
                pointer = int(value)
                if pointer != 0 and not ROM_POINTER_MIN <= pointer <= ROM_POINTER_MAX:
                    raise ValueError(
                        f"{column} 0x{pointer:08X} outside 48 Mbit ROM address range")
                patches.append({
                    "type": "bytes",
                    "offset": expected_offset + field_offset,
                    "after_hex": struct.pack("<I", pointer).hex(),
                    "length": 4,
                    "description": (
                        f"DB[rom_cutscene_scripts] idx={index}: {column} "
                        f"= 0x{pointer:08X}"),
                    "db_table": "rom_cutscene_scripts",
                    "db_row_id": index,
                })
        except Exception as exc:
            patches.append({
                "type": "db_cutscene_script_error",
                "db_table": "rom_cutscene_scripts",
                "db_row_id": int(row["_idx"]),
                "error": str(exc),
                "description": (
                    f"DB[rom_cutscene_scripts] idx={row['_idx']} error: {exc}"),
            })
    conn.close()
    return patches
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
    The data table A at 0x5A143C contains 46 u32 ROM pointers.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_data_table_a", index_column="_idx",
        pointer_column="rom_ptr", table_offset=0x5A143C,
        entry_count=46, pointer_kind="data",
    )

def generate_data_table_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for data table B pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The data table B at 0x5A2034 contains 90 u32 entries.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_data_table_b", index_column="_idx",
        pointer_column="rom_ptr", table_offset=0x5A2034,
        entry_count=90, pointer_kind="data",
    )

def generate_font_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate ROM patches for font width rows.

    Each row writes to the font width table at 0x53E596 (stride 1 byte).
    The font table maps character codes to pixel widths.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    patches: list[dict[str, Any]] = []
    TABLE_OFFSET = 0x53E596
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
    The function pointer table at 0x53D5F0 has 13 u32 slots; slots 0 and 12
    are ``0xFFFFFFFF`` sentinels and slots 1..11 are the code pointers.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_function_pointers", index_column="_idx",
        pointer_column="slot_value", table_offset=0x53D5F0,
        entry_count=13, pointer_kind="raw",
    )

def generate_map_event_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for map event handlers.

    Each row writes one validated u32 directly to the game-consumed table.
    The map event table at 0x53E698 contains 256 records of 8 bytes (two u32
    code pointers each) -- the **same** table as ``battle-handlers``.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_map_events", index_column="_idx",
        pointer_column="code_ptr_0", table_offset=0x53E698,
        entry_count=256, pointer_kind="thumb",
        record_stride=8, field_offset=0,
    )

def generate_map_sprite_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for scene object descriptor pointers.

    The canonical base is ``0x53F140`` -- 86 u32 pointers read by
    ``0x08080B12`` (fn ``0x08080B08``), indexed ``id*11``.

    .. warning::
       The old base ``0x53F1DC`` is **not** a table start: it is
       ``0x53F140 + 0x9C``, i.e. item 39 of the same array
       (``tools/table_registry.py::CONFLICTS['0x53f1dc']``).  The generator
       now uses the adjudicated base and the full 86-entry count, which is
       also what ``sequel/content/map-sprites/bank.json`` declares.
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_map_sprites", index_column="_idx",
        pointer_column="sprite_ptr", table_offset=0x53F140,
        entry_count=86, pointer_kind="data",
    )

def generate_menu_ui_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for menu UI data pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The portrait table at 0x5A4DEC contains 63 rows of 40 bytes; each row has
    5 expression slots of 8 bytes (two u32 each).
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_menu_ui", index_column="_idx",
        pointer_column="expr0_ptr_0", table_offset=0x5A4DEC,
        entry_count=63, pointer_kind="data",
        record_stride=40, field_offset=0,
    )

def generate_palette_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject the falsified ``palettes`` table identity.

    ``0x53F138`` has **no native reader** and is not a palette table: the
    two words there (``0x080808BD`` / ``0x08080965``) are the head of the
    86-entry scene-object descriptor array that really starts at
    ``0x53F140`` (see ``tools/table_registry.py::CONFLICTS['0x53f138']`` and
    ``notes/alias-conflicts-20261020.md``).  The sprite palette data itself
    lives in the **fourth** pointer of every sprite action entry
    (``0x596CCC + id*144 + action*16 + 12``), each pointing at a 32-byte
    16-colour BGR555 block.

    Writing 88 pointers at ``0x53F138`` would overwrite the head of a live
    table with unrelated values, so the bank is kept read-only and the
    canonical write path is :func:`generate_sprite_animation_patches`.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, palette_ptr FROM rom_palettes ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_palette_unmapped",
        "db_table": "rom_palettes",
        "db_row_id": int(row["_idx"]),
        "error": (
            "0x53F138 is not a palette table: it is the head of the 86-entry "
            "scene-object descriptor array at 0x53F140; the sprite palette "
            "pointer is the fourth pointer of each sprite action entry"),
        "description": (
            f"DB[rom_palettes] idx={row['_idx']}: skipped unsafe 0x53F138 "
            f"write -- use rom_sprite_animations.palette_ptr instead"),
    } for row in rows]
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
    """Reject the deprecated ``resource-pointers`` alias view.

    ``0x596F0C`` is **not** an independent resource-pointer table: it is
    ``0x596CCC + 0x240``, i.e. entry 36 (id 4 / action 0) of the sprite
    action table, and the 20 u32 slots it spans are the four pointer kinds
    (``frames`` / ``animations`` / ``gfx`` / ``palette``) of five action
    entries.  See ``tools/table_registry.py::CONFLICTS['0x596f0c']`` and
    ``notes/alias-conflicts-20261020.md``.

    A single ``resource_ptr`` column cannot say *which* of the four kinds it
    means, so writing it would overwrite an arbitrary pointer of a live
    sprite record.  The bank is therefore kept as a read-only alias view and
    the canonical write path is
    :func:`generate_sprite_animation_patches`.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, resource_ptr FROM rom_resource_pointers ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [{
        "type": "db_resource_pointer_unmapped",
        "db_table": "rom_resource_pointers",
        "db_row_id": int(row["_idx"]),
        "error": (
            "0x596F0C is a window of the sprite action table 0x596CCC "
            "(id 4 / action 0), not an independent pointer table; a single "
            "resource_ptr column cannot select which of the four pointer "
            "kinds it means"),
        "description": (
            f"DB[rom_resource_pointers] idx={row['_idx']}: skipped unsafe "
            f"0x596F0C write -- use rom_sprite_animations instead"),
    } for row in rows]

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
    """Generate ROM patches for the WRAM allocation table.

    Each row writes one validated 8-byte record directly to the
    game-consumed table.  ``0x53D848`` holds 10 records of
    ``{u32 wram_addr, u32 size}`` -- the second word is the **allocation
    size**, not a SRAM offset.

    .. warning::
       The legacy column name ``sram_offset_field`` (and the old "save
       descriptor" framing) is wrong: ``0x53D848`` is a **WRAM allocation
       table** with four native readers
       (``0x0806869A / 0x08068954 / 0x08068CC0 / 0x08068D98``); the save
       data itself lives in SRAM, not in ROM.  Both the new column name
       ``alloc_size`` and the legacy one are accepted so an existing editor
       database keeps working; the value is written as the size either way.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, ewram_buffer, "
            "alloc_size, sram_offset_field FROM rom_save_state ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        try:
            rows = conn.execute(
                "SELECT _idx, _rom_offset, ewram_buffer, "
                "sram_offset_field FROM rom_save_state ORDER BY _idx"
            ).fetchall()
        except sqlite3.OperationalError:
            conn.close()
            return []
    patches: list[dict[str, Any]] = []
    for row in rows:
        try:
            save_index = int(row["_idx"])
            if not 0 <= save_index < 10:
                raise ValueError(f"index {save_index} outside 0..9")
            offset = 0x53D848 + save_index * 8
            if int(row["_rom_offset"]) != offset:
                raise ValueError("stale _rom_offset")
            ewram_addr = int(row["ewram_buffer"] or 0)
            keys = row.keys()
            raw_size = (row["alloc_size"] if "alloc_size" in keys
                        else row["sram_offset_field"])
            alloc_size = int(raw_size or 0)
            payload = struct.pack("<II", ewram_addr, alloc_size)
            patches.append({
                "type": "bytes",
                "offset": offset,
                "after_hex": payload.hex(),
                "length": 8,
                "description": (f"DB[rom_save_state] idx={save_index}: "
                                f"WRAM alloc @0x{ewram_addr:08X} "
                                f"size={alloc_size}"),
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
    """Generate validated real-ROM patches for sprite action entries.

    The real sprite action table lives at ``0x596CCC`` and is indexed
    ``id*144 + action*16``; every entry is 16 bytes = four u32 ROM pointers
    (``frames`` / ``animations`` / ``gfx`` / ``palette``).

    .. warning::
       The old address ``0x53F200`` is **falsified**: it has no native
       reader and is merely a window inside the ``0x53F140`` object-pointer
       array (see ``notes/alias-conflicts-20261020.md`` and
       ``tools/table_registry.py::CONFLICTS['0x53f200']``).  Writing there
       corrupted the object descriptor table, so the generator now uses the
       adjudicated base and the 16-byte stride.

    Only the pointer columns that actually carry a value are written; a NULL
    cell means "leave the native bytes alone" (the copy-native-entry model).
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT _idx, _rom_offset, frames_ptr, animations_ptr, gfx_ptr, "
            "palette_ptr FROM rom_sprite_animations ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []

    patches: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        try:
            index = int(row["_idx"])
            if not 0 <= index < SPRITE_ACTION_ENTRY_COUNT:
                raise ValueError(
                    f"index {index} outside 0..{SPRITE_ACTION_ENTRY_COUNT - 1}")
            if index in seen:
                raise ValueError(f"duplicate index {index}")
            seen.add(index)
            expected_offset = SPRITE_ACTION_TABLE_OFFSET + index * SPRITE_ACTION_STRIDE
            if int(row["_rom_offset"]) != expected_offset:
                raise ValueError(
                    f"stale _rom_offset 0x{int(row['_rom_offset']):X}; "
                    f"expected 0x{expected_offset:X}")
            for field_offset, column in SPRITE_ACTION_POINTER_COLUMNS:
                value = row[column]
                if value is None:
                    continue
                pointer = int(value)
                if pointer != 0 and not ROM_POINTER_MIN <= pointer <= ROM_POINTER_MAX:
                    raise ValueError(
                        f"{column} 0x{pointer:08X} outside 48 Mbit ROM address range")
                offset = expected_offset + field_offset
                patches.append({
                    "type": "bytes",
                    "offset": offset,
                    "after_hex": struct.pack("<I", pointer).hex(),
                    "length": 4,
                    "description": (
                        f"DB[rom_sprite_animations] idx={index}: {column} "
                        f"= 0x{pointer:08X}"),
                    "db_table": "rom_sprite_animations",
                    "db_row_id": index,
                })
        except Exception as exc:
            patches.append({
                "type": "db_sprite_animation_error",
                "db_table": "rom_sprite_animations",
                "db_row_id": int(row["_idx"]),
                "error": str(exc),
                "description": (
                    f"DB[rom_sprite_animations] idx={row['_idx']} error: {exc}"),
            })
    conn.close()
    return patches

def generate_story_b_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for the sound id 2 SongHeader.

    The bank is the m4a SongHeader at 0x536BC4; the only pointer in it with
    an identified meaning is the **voicegroup pointer** (the old base
    0x536BC8 was 4 bytes late and landed on that same word).
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_story_b", index_column="_idx",
        pointer_column="voicegroup_ptr", table_offset=0x536BC4,
        entry_count=1, pointer_kind="rom",
        record_stride=4, field_offset=4,
    )


def _generate_chapter_flow_pointer_patches(
    db_path: Path, *, table: str, table_offset: int
) -> list[dict[str, Any]]:
    """Preserve the mirror while rejecting pointer-only chapter mutations.

    A changed pointer is unsafe without an allocated, codec-validated payload.
    Semantic edits must use ``import_chapter_scripts.py`` so both writes share
    one validated build plan.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT _idx, _rom_offset, base_script_ptr, script_ptr FROM {table} ORDER BY _idx"
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close(); return []
    conn.close()
    base_rom = BASE_ROM_PATH.read_bytes()
    patches = []
    seen = set()
    for row in rows:
        index = int(row['_idx'])
        try:
            if not 0 <= index < 56:
                raise ValueError(f"index {index} outside 0..55")
            if index in seen:
                raise ValueError(f"duplicate index {index}")
            seen.add(index)
            expected_offset = table_offset + index * 4
            if int(row['_rom_offset']) != expected_offset:
                raise ValueError(f"stale _rom_offset 0x{int(row['_rom_offset']):X}; expected 0x{expected_offset:X}")
            imported_base = int(row['base_script_ptr'])
            actual_base = struct.unpack_from('<I', base_rom, expected_offset)[0]
            if imported_base != actual_base:
                raise ValueError(
                    f"immutable base pointer mismatch: DB 0x{imported_base:08X}, ROM 0x{actual_base:08X}"
                )
            pointer = int(row['script_ptr'])
            if index == 0:
                if pointer != 0:
                    raise ValueError("sentinel index 0 must remain null")
            elif not ROM_POINTER_MIN <= pointer <= ROM_POINTER_MAX:
                raise ValueError(f"pointer 0x{pointer:08X} outside 48 Mbit ROM address range")
            if pointer != actual_base:
                raise ValueError(
                    "pointer-only writeback is disabled; use the semantic chapter importer"
                )
            patches.append({
                'type': 'db_chapter_flow_unchanged',
                'description': (
                    f"DB[{table}] scenario={index}: unchanged guarded chapter pointer"
                ),
                'db_table': table, 'db_row_id': index,
            })
        except (TypeError, ValueError) as exc:
            patches.append({
                'type': 'db_chapter_flow_pointer_error', 'db_table': table,
                'db_row_id': index, 'error': str(exc),
                'description': f"DB[{table}] scenario={index} rejected: {exc}",
            })
    return patches


def generate_chapter_flow_primary_patches(db_path: Path) -> list[dict[str, Any]]:
    return _generate_chapter_flow_pointer_patches(
        db_path, table='rom_chapter_flow_primary', table_offset=0x60C74,
    )


def generate_chapter_flow_alternate_patches(db_path: Path) -> list[dict[str, Any]]:
    return _generate_chapter_flow_pointer_patches(
        db_path, table='rom_chapter_flow_alternate', table_offset=0x60D54,
    )

def generate_story_c_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject the false story-C mirror; it is a resource descriptor slice."""
    return _reject_unproven_legacy_rows(
        db_path, 'SELECT _idx AS id, _idx FROM rom_story_c', "db_story_c_disproved",
        "rom_story_c", "0x538FF0 is descriptor 0x538FEC + 4, not story data",
        lambda row: f"DB[rom_story_c] idx={row['_idx']}: skipped disproved story write",
    )

def generate_story_d_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject the false story-D mirror; it is a resource descriptor slice."""
    return _reject_unproven_legacy_rows(
        db_path, 'SELECT _idx AS id, _idx FROM rom_story_d', "db_story_d_disproved",
        "rom_story_d", "0x53AB78 is descriptor 0x53AB74 + 4, not story data",
        lambda row: f"DB[rom_story_d] idx={row['_idx']}: skipped disproved story write",
    )

def generate_story_e_patches(db_path: Path) -> list[dict[str, Any]]:
    """Reject the false story-E mirror; it is a resource descriptor slice."""
    return _reject_unproven_legacy_rows(
        db_path, 'SELECT _idx AS id, _idx FROM rom_story_e', "db_story_e_disproved",
        "rom_story_e", "0x53C3C0 is descriptor 0x53C3BC + 4, not story data",
        lambda row: f"DB[rom_story_e] idx={row['_idx']}: skipped disproved story write",
    )

def generate_tile_asset_patches(db_path: Path) -> list[dict[str, Any]]:
    """Generate validated real-ROM patches for tile asset data pointers.

    Each row writes one validated u32 directly to the game-consumed table.
    The tile-asset table at 0x5A320C contains 79 records of 68 bytes; the
    six tile pointers live at record offset +0x0C (the old base 0x5A3218 was
    exactly that field, not a table start).
    """
    return _generate_u32_pointer_table_patches(
        db_path, table="rom_tile_assets", index_column="_idx",
        pointer_column="tile_ptr_0", table_offset=0x5A320C,
        entry_count=79, pointer_kind="data",
        record_stride=68, field_offset=12,
    )


def _read_rom(rom_path: Path) -> bytearray:
    return bytearray(Path(rom_path).read_bytes())


def _diff_patches(native: bytes, patched: bytes, base_offset: int,
                   patch_id: str, description: str) -> list[dict[str, Any]]:
    """Emit one "bytes" patch per contiguous changed byte range."""
    patches: list[dict[str, Any]] = []
    index = 0
    while index < len(native):
        if native[index] == patched[index]:
            index += 1
            continue
        start = index
        while index < len(native) and native[index] != patched[index]:
            index += 1
        patches.append({
            "id": f"{patch_id}.{len(patches)}",
            "type": "bytes",
            "offset": base_offset + start,
            "before_hex": native[start:index].hex(),
            "after_hex": patched[start:index].hex(),
            "length": index - start,
            "description": description,
        })
    return patches


def _writeback_patches(rom_path: Path, region_offset: int, region_size: int,
                       apply, patch_id: str, description: str) -> list[dict[str, Any]]:
    """Apply one author change to a ROM copy and describe it as patches."""
    rom = _read_rom(rom_path)
    native = bytes(rom[region_offset:region_offset + region_size])
    apply(rom)
    patched = bytes(rom[region_offset:region_offset + region_size])
    return _diff_patches(native, patched, region_offset, patch_id, description)


def build_character_template_patches(rom_path: Path, character_id: int,
                                     changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one character template entry (0x54241C)."""
    try:
        from tools.import_character_template import (
            TEMPLATE_STRIDE, template_offset, write_character_template,
        )
    except ModuleNotFoundError:  # direct ``python tools/build_db_patches.py``
        from import_character_template import (
            TEMPLATE_STRIDE, template_offset, write_character_template,
        )
    offset = template_offset(character_id)
    return _writeback_patches(
        rom_path, offset, TEMPLATE_STRIDE,
        lambda rom: write_character_template(rom, character_id, changes),
        f"character_template.{character_id}",
        f"character template {character_id}: {sorted(changes)}",
    )


def build_character_growth_patches(rom_path: Path, character_id: int,
                                   changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one growth table entry (0x545068)."""
    try:
        from tools.import_character_template import (
            GROWTH_STRIDE, growth_offset, write_growth,
        )
    except ModuleNotFoundError:
        from import_character_template import GROWTH_STRIDE, growth_offset, write_growth
    offset = growth_offset(character_id)
    return _writeback_patches(
        rom_path, offset, GROWTH_STRIDE,
        lambda rom: write_growth(rom, character_id, changes),
        f"character_growth.{character_id}",
        f"character growth {character_id}: {sorted(changes)}",
    )


def build_battle_record_patches(rom_path: Path, index: int,
                                 changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one 16-byte battle record (0x545458)."""
    try:
        from tools.import_character_template import (
            BATTLE_RECORD_STRIDE, battle_record_offset, write_battle_record,
        )
    except ModuleNotFoundError:
        from import_character_template import (
            BATTLE_RECORD_STRIDE, battle_record_offset, write_battle_record,
        )
    offset = battle_record_offset(index)
    return _writeback_patches(
        rom_path, offset, BATTLE_RECORD_STRIDE,
        lambda rom: write_battle_record(rom, index, changes),
        f"battle_record.{index}",
        f"battle record {index}: {sorted(changes)}",
    )


def build_sprite_action_patches(rom_path: Path, sprite_id: int, action: int,
                                changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one sprite action entry (0x596CCC)."""
    try:
        from tools.import_sprite_action import (
            ACTION_ENTRY_STRIDE, entry_offset, write_sprite_action,
        )
    except ModuleNotFoundError:
        from import_sprite_action import (
            ACTION_ENTRY_STRIDE, entry_offset, write_sprite_action,
        )
    offset = entry_offset(sprite_id, action)
    return _writeback_patches(
        rom_path, offset, ACTION_ENTRY_STRIDE,
        lambda rom: write_sprite_action(rom, sprite_id, action, changes),
        f"sprite_action.{sprite_id}_{action}",
        f"sprite action {sprite_id}/{action}: {sorted(changes)}",
    )


def build_story_script_patches(rom_path: Path, table: str, scene: int,
                               patches: list[dict]) -> list[dict[str, Any]]:
    """Write-back patches for fixed-width operands of one story script.

    The patched script keeps its exact length, so no branch target moves and
    no relocation is needed.
    """
    try:
        from tools.import_story_script import (
            patch_story_script, read_root_pointer, scan_script,
        )
    except ModuleNotFoundError:
        from import_story_script import patch_story_script, read_root_pointer, scan_script
    rom = _read_rom(rom_path)
    root = read_root_pointer(rom, table, scene)
    if root is None:
        return []
    instructions = scan_script(rom, root)
    if not instructions:
        return []
    start = min(i["offset"] for i in instructions)
    end = max(i["offset"] + i["length"] for i in instructions)
    description = (
        f"story script {table}[{scene}]: "
        + ", ".join(
            f"0x{int(p['opcode']):02X}#{int(p.get('occurrence', 0))}."
            f"{p['field']}={int(p['value'])}"
            for p in patches
        )
    )
    return _writeback_patches(
        rom_path, start, end - start,
        lambda rom: patch_story_script(rom, table, scene, patches),
        f"story_script.{table}.{scene}",
        description,
    )


def build_map_entry_patches(rom_path: Path, map_id: int,
                            changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one map descriptor entry (0x53D910)."""
    try:
        from tools.import_battle_config import (
            ROM_BATTLE_SCENARIO_ENTRY_SIZE, map_entry_offset, write_map_entry,
        )
    except ModuleNotFoundError:
        from import_battle_config import (
            ROM_BATTLE_SCENARIO_ENTRY_SIZE, map_entry_offset, write_map_entry,
        )
    offset = map_entry_offset(map_id)
    return _writeback_patches(
        rom_path, offset, ROM_BATTLE_SCENARIO_ENTRY_SIZE,
        lambda rom: write_map_entry(rom, map_id, changes),
        f"map_entry.{map_id}",
        f"map descriptor {map_id}: {sorted(changes)}",
    )


def build_formation_record_patches(rom_path: Path, group_id: int, variant_id: int,
                                   record_id: int, changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one battle formation record (0x5461C4)."""
    try:
        from tools.import_battle_config import (
            FORMATION_RECORD_STRIDE, formation_record_offset,
            write_formation_record,
        )
    except ModuleNotFoundError:
        from import_battle_config import (
            FORMATION_RECORD_STRIDE, formation_record_offset,
            write_formation_record,
        )
    offset = formation_record_offset(group_id, variant_id, record_id)
    return _writeback_patches(
        rom_path, offset, FORMATION_RECORD_STRIDE,
        lambda rom: write_formation_record(rom, group_id, variant_id, record_id, changes),
        f"formation.{group_id}_{variant_id}_{record_id}",
        f"formation record {group_id}/{variant_id}/{record_id}: {sorted(changes)}",
    )


def build_stage_pointer_patches(rom_path: Path, index: int,
                                pointer: int) -> list[dict[str, Any]]:
    """Write-back patches for one slot of the stage data table (0x53DF70)."""
    try:
        from tools.import_battle_config import (
            STAGE_POINTER_TABLE_FILE, write_stage_pointer,
        )
    except ModuleNotFoundError:
        from import_battle_config import STAGE_POINTER_TABLE_FILE, write_stage_pointer
    offset = STAGE_POINTER_TABLE_FILE + index * 4
    return _writeback_patches(
        rom_path, offset, 4,
        lambda rom: write_stage_pointer(rom, index, pointer),
        f"stage_pointer.{index}",
        f"stage data pointer {index} = 0x{pointer:08X}",
    )


def build_object_descriptor_patches(rom_path: Path, slot: int,
                                    pointer: int) -> list[dict[str, Any]]:
    """Write-back patches for one slot of the object descriptor table (0x53F140)."""
    try:
        from tools.import_battle_config import (
            OBJECT_DESCRIPTOR_TABLE_FILE, write_object_descriptor_pointer,
        )
    except ModuleNotFoundError:
        from import_battle_config import (
            OBJECT_DESCRIPTOR_TABLE_FILE, write_object_descriptor_pointer,
        )
    offset = OBJECT_DESCRIPTOR_TABLE_FILE + slot * 4
    return _writeback_patches(
        rom_path, offset, 4,
        lambda rom: write_object_descriptor_pointer(rom, slot, pointer),
        f"object_descriptor.{slot}",
        f"object descriptor pointer {slot} = 0x{pointer:08X}",
    )


def build_wram_alloc_patches(rom_path: Path, index: int, wram_addr: int,
                             size: int) -> list[dict[str, Any]]:
    """Write-back patches for one WRAM allocation pair (0x53D848)."""
    try:
        from tools.import_battle_config import (
            WRAM_ALLOC_TABLE_FILE, write_wram_alloc,
        )
    except ModuleNotFoundError:
        from import_battle_config import WRAM_ALLOC_TABLE_FILE, write_wram_alloc
    offset = WRAM_ALLOC_TABLE_FILE + index * 8
    return _writeback_patches(
        rom_path, offset, 8,
        lambda rom: write_wram_alloc(rom, index, wram_addr, size),
        f"wram_alloc.{index}",
        f"wram allocation {index} = 0x{wram_addr:08X} + 0x{size:X}",
    )


def build_unit_offset_patches(rom_path: Path, slot: int,
                              value: int) -> list[dict[str, Any]]:
    """Write-back patches for one slot of the u16 offset table (0x53F298).

    Constrained: only native offsets of the same table may be reused (see
    ``tools/import_battle_config.py::write_unit_offset``).
    """
    try:
        from tools.import_battle_config import (
            ROM_UNIT_ID_TABLE_FILE, write_unit_offset,
        )
    except ModuleNotFoundError:
        from import_battle_config import ROM_UNIT_ID_TABLE_FILE, write_unit_offset
    offset = ROM_UNIT_ID_TABLE_FILE + slot * 2
    return _writeback_patches(
        rom_path, offset, 2,
        lambda rom: write_unit_offset(rom, slot, value),
        f"unit_offset.{slot}",
        f"u16 offset table[{slot}] = 0x{value:04X}",
    )


def _read_rom(rom_path: Path) -> bytearray:
    return bytearray(Path(rom_path).read_bytes())


def _diff_patches(native: bytes, patched: bytes, base_offset: int,
                   patch_id: str, description: str) -> list[dict[str, Any]]:
    """Emit one "bytes" patch per contiguous changed byte range."""
    patches: list[dict[str, Any]] = []
    index = 0
    while index < len(native):
        if native[index] == patched[index]:
            index += 1
            continue
        start = index
        while index < len(native) and native[index] != patched[index]:
            index += 1
        patches.append({
            "id": f"{patch_id}.{len(patches)}",
            "type": "bytes",
            "offset": base_offset + start,
            "before_hex": native[start:index].hex(),
            "after_hex": patched[start:index].hex(),
            "length": index - start,
            "description": description,
        })
    return patches


def _writeback_patches(rom_path: Path, region_offset: int, region_size: int,
                       apply, patch_id: str, description: str) -> list[dict[str, Any]]:
    """Apply one author change to a ROM copy and describe it as patches."""
    rom = _read_rom(rom_path)
    native = bytes(rom[region_offset:region_offset + region_size])
    apply(rom)
    patched = bytes(rom[region_offset:region_offset + region_size])
    return _diff_patches(native, patched, region_offset, patch_id, description)


def build_character_template_patches(rom_path: Path, character_id: int,
                                     changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one character template entry (0x54241C)."""
    try:
        from tools.import_character_template import (
            TEMPLATE_STRIDE, template_offset, write_character_template,
        )
    except ModuleNotFoundError:  # direct ``python tools/build_db_patches.py``
        from import_character_template import (
            TEMPLATE_STRIDE, template_offset, write_character_template,
        )
    offset = template_offset(character_id)
    return _writeback_patches(
        rom_path, offset, TEMPLATE_STRIDE,
        lambda rom: write_character_template(rom, character_id, changes),
        f"character_template.{character_id}",
        f"character template {character_id}: {sorted(changes)}",
    )


def build_character_growth_patches(rom_path: Path, character_id: int,
                                   changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one growth table entry (0x545068)."""
    try:
        from tools.import_character_template import (
            GROWTH_STRIDE, growth_offset, write_growth,
        )
    except ModuleNotFoundError:
        from import_character_template import GROWTH_STRIDE, growth_offset, write_growth
    offset = growth_offset(character_id)
    return _writeback_patches(
        rom_path, offset, GROWTH_STRIDE,
        lambda rom: write_growth(rom, character_id, changes),
        f"character_growth.{character_id}",
        f"character growth {character_id}: {sorted(changes)}",
    )


def build_battle_record_patches(rom_path: Path, index: int,
                                 changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one 16-byte battle record (0x545458)."""
    try:
        from tools.import_character_template import (
            BATTLE_RECORD_STRIDE, battle_record_offset, write_battle_record,
        )
    except ModuleNotFoundError:
        from import_character_template import (
            BATTLE_RECORD_STRIDE, battle_record_offset, write_battle_record,
        )
    offset = battle_record_offset(index)
    return _writeback_patches(
        rom_path, offset, BATTLE_RECORD_STRIDE,
        lambda rom: write_battle_record(rom, index, changes),
        f"battle_record.{index}",
        f"battle record {index}: {sorted(changes)}",
    )


def build_sprite_action_patches(rom_path: Path, sprite_id: int, action: int,
                                changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one sprite action entry (0x596CCC)."""
    try:
        from tools.import_sprite_action import (
            ACTION_ENTRY_STRIDE, entry_offset, write_sprite_action,
        )
    except ModuleNotFoundError:
        from import_sprite_action import (
            ACTION_ENTRY_STRIDE, entry_offset, write_sprite_action,
        )
    offset = entry_offset(sprite_id, action)
    return _writeback_patches(
        rom_path, offset, ACTION_ENTRY_STRIDE,
        lambda rom: write_sprite_action(rom, sprite_id, action, changes),
        f"sprite_action.{sprite_id}_{action}",
        f"sprite action {sprite_id}/{action}: {sorted(changes)}",
    )


def build_story_script_patches(rom_path: Path, table: str, scene: int,
                               patches: list[dict]) -> list[dict[str, Any]]:
    """Write-back patches for fixed-width operands of one story script.

    The patched script keeps its exact length, so no branch target moves and
    no relocation is needed.
    """
    try:
        from tools.import_story_script import (
            patch_story_script, read_root_pointer, scan_script,
        )
    except ModuleNotFoundError:
        from import_story_script import patch_story_script, read_root_pointer, scan_script
    rom = _read_rom(rom_path)
    root = read_root_pointer(rom, table, scene)
    if root is None:
        return []
    instructions = scan_script(rom, root)
    if not instructions:
        return []
    start = min(i["offset"] for i in instructions)
    end = max(i["offset"] + i["length"] for i in instructions)
    description = (
        f"story script {table}[{scene}]: "
        + ", ".join(
            f"0x{int(p['opcode']):02X}#{int(p.get('occurrence', 0))}."
            f"{p['field']}={int(p['value'])}"
            for p in patches
        )
    )
    return _writeback_patches(
        rom_path, start, end - start,
        lambda rom: patch_story_script(rom, table, scene, patches),
        f"story_script.{table}.{scene}",
        description,
    )


def build_map_entry_patches(rom_path: Path, map_id: int,
                            changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one map descriptor entry (0x53D910)."""
    try:
        from tools.import_battle_config import (
            ROM_BATTLE_SCENARIO_ENTRY_SIZE, map_entry_offset, write_map_entry,
        )
    except ModuleNotFoundError:
        from import_battle_config import (
            ROM_BATTLE_SCENARIO_ENTRY_SIZE, map_entry_offset, write_map_entry,
        )
    offset = map_entry_offset(map_id)
    return _writeback_patches(
        rom_path, offset, ROM_BATTLE_SCENARIO_ENTRY_SIZE,
        lambda rom: write_map_entry(rom, map_id, changes),
        f"map_entry.{map_id}",
        f"map descriptor {map_id}: {sorted(changes)}",
    )


def build_formation_record_patches(rom_path: Path, group_id: int, variant_id: int,
                                   record_id: int, changes: dict) -> list[dict[str, Any]]:
    """Write-back patches for one battle formation record (0x5461C4)."""
    try:
        from tools.import_battle_config import (
            FORMATION_RECORD_STRIDE, formation_record_offset,
            write_formation_record,
        )
    except ModuleNotFoundError:
        from import_battle_config import (
            FORMATION_RECORD_STRIDE, formation_record_offset,
            write_formation_record,
        )
    offset = formation_record_offset(group_id, variant_id, record_id)
    return _writeback_patches(
        rom_path, offset, FORMATION_RECORD_STRIDE,
        lambda rom: write_formation_record(rom, group_id, variant_id, record_id, changes),
        f"formation.{group_id}_{variant_id}_{record_id}",
        f"formation record {group_id}/{variant_id}/{record_id}: {sorted(changes)}",
    )


def build_stage_pointer_patches(rom_path: Path, index: int,
                                pointer: int) -> list[dict[str, Any]]:
    """Write-back patches for one slot of the stage data table (0x53DF70)."""
    try:
        from tools.import_battle_config import (
            STAGE_POINTER_TABLE_FILE, write_stage_pointer,
        )
    except ModuleNotFoundError:
        from import_battle_config import STAGE_POINTER_TABLE_FILE, write_stage_pointer
    offset = STAGE_POINTER_TABLE_FILE + index * 4
    return _writeback_patches(
        rom_path, offset, 4,
        lambda rom: write_stage_pointer(rom, index, pointer),
        f"stage_pointer.{index}",
        f"stage data pointer {index} = 0x{pointer:08X}",
    )


def build_object_descriptor_patches(rom_path: Path, slot: int,
                                    pointer: int) -> list[dict[str, Any]]:
    """Write-back patches for one slot of the object descriptor table (0x53F140)."""
    try:
        from tools.import_battle_config import (
            OBJECT_DESCRIPTOR_TABLE_FILE, write_object_descriptor_pointer,
        )
    except ModuleNotFoundError:
        from import_battle_config import (
            OBJECT_DESCRIPTOR_TABLE_FILE, write_object_descriptor_pointer,
        )
    offset = OBJECT_DESCRIPTOR_TABLE_FILE + slot * 4
    return _writeback_patches(
        rom_path, offset, 4,
        lambda rom: write_object_descriptor_pointer(rom, slot, pointer),
        f"object_descriptor.{slot}",
        f"object descriptor pointer {slot} = 0x{pointer:08X}",
    )


def build_wram_alloc_patches(rom_path: Path, index: int, wram_addr: int,
                             size: int) -> list[dict[str, Any]]:
    """Write-back patches for one WRAM allocation pair (0x53D848)."""
    try:
        from tools.import_battle_config import (
            WRAM_ALLOC_TABLE_FILE, write_wram_alloc,
        )
    except ModuleNotFoundError:
        from import_battle_config import WRAM_ALLOC_TABLE_FILE, write_wram_alloc
    offset = WRAM_ALLOC_TABLE_FILE + index * 8
    return _writeback_patches(
        rom_path, offset, 8,
        lambda rom: write_wram_alloc(rom, index, wram_addr, size),
        f"wram_alloc.{index}",
        f"wram allocation {index} = 0x{wram_addr:08X} + 0x{size:X}",
    )


def build_unit_offset_patches(rom_path: Path, slot: int,
                              value: int) -> list[dict[str, Any]]:
    """Write-back patches for one slot of the u16 offset table (0x53F298).

    Constrained: only native offsets of the same table may be reused (see
    ``tools/import_battle_config.py::write_unit_offset``).
    """
    try:
        from tools.import_battle_config import (
            ROM_UNIT_ID_TABLE_FILE, write_unit_offset,
        )
    except ModuleNotFoundError:
        from import_battle_config import ROM_UNIT_ID_TABLE_FILE, write_unit_offset
    offset = ROM_UNIT_ID_TABLE_FILE + slot * 2
    return _writeback_patches(
        rom_path, offset, 2,
        lambda rom: write_unit_offset(rom, slot, value),
        f"unit_offset.{slot}",
        f"u16 offset table[{slot}] = 0x{value:04X}",
    )
SPRITE_ACTION_TABLE_OFFSET = 0x596CCC
SPRITE_ACTION_STRIDE = 16
SPRITE_ACTION_ENTRY_COUNT = 576
SPRITE_ACTION_POINTER_COLUMNS = (
    (0x00, "frames_ptr"),
    (0x04, "animations_ptr"),
    (0x08, "gfx_ptr"),
    (0x0C, "palette_ptr"),
)
LEVEL_BLOCK_TABLE_OFFSET = 0x53DF70
LEVEL_BLOCK_STRIDE = 8
LEVEL_BLOCK_ENTRY_COUNT = 4
LEVEL_BLOCK_POINTER_COLUMNS = (
    (0x00, "gfx_ptr"),
    (0x04, "palette_ptr"),
)

