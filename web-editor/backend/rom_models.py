"""
ROM-derived models: one read-only table per Phase-5-extractable structure.

Why a separate module:
    24 of the 32 reverse-engineered structures don't have CRUD UIs
    yet (and probably never will — most are pointer tables that
    shouldn't be hand-edited). But the editor needs to *show* what
    was extracted from the ROM so the user can verify Phase 5.

    Instead of writing 24 routers + 24 stores + 24 views, we expose
    one generic GET endpoint that takes a structure name and returns
    its entries, plus a tiny per-structure SQL table for caching.

Schema:
    Each `rom_<name>` table has columns generated from bank.json
    entry_format.fields plus an `idx INTEGER` (entry index) and a
    `rom_offset INTEGER` (raw offset for audit). All fields are
    nullable because not every entry has every field populated.
"""

from pathlib import Path
import json
import sqlite3
import re

CONTENT_DIR = Path(__file__).parent.parent.parent / 'sequel' / 'content'

# Structures we extracted in Phase 5 (extracted_count > 0).
# Excludes: units (already has CRUD), audio/items/sappy-engine (dispatchers).
EXTRACTABLE = [
    'battle-config', 'battle-encounters', 'battle-handlers',
    'character-stats', 'character-stats-b', 'cutscene-scripts',
    'data-table-a', 'data-table-b', 'encounter-zones',
    'fonts', 'function-pointers',
    'levels', 'map-events', 'map-sprites', 'maps', 'positions',
    'menu-ui', 'palettes', 'resource-pointers', 'save-state',
    'skills', 'sprite-animations',
    'story', 'story-b', 'story-c', 'story-d', 'story-e',
    'tile-assets',
]


def _snake(name: str) -> str:
    """kebab-case → snake_case. e.g. 'battle-config' → 'battle_config'."""
    return name.replace('-', '_')


def _sql_type(field: dict) -> str:
    """Map entry_format field type → SQLite column type."""
    t = field.get('type', '').lower()
    if t in ('u8', 's8'):
        return 'INTEGER'
    if t in ('u16', 's16', 'u32', 's32'):
        return 'INTEGER'
    return 'TEXT'  # unknown / pointer


def get_fields(structure: str) -> list:
    """Return entry_format.fields for a structure, or [] if missing."""
    bank_path = CONTENT_DIR / structure / 'bank.json'
    if not bank_path.exists():
        return []
    data = json.loads(bank_path.read_text(encoding="utf-8"))
    ef = data.get('entry_format')
    if not isinstance(ef, dict) or 'fields' not in ef:
        return []
    return ef['fields']


def get_entries(structure: str) -> list:
    """Return the entries[] array from a structure's bank.json."""
    bank_path = CONTENT_DIR / structure / 'bank.json'
    if not bank_path.exists():
        return []
    data = json.loads(bank_path.read_text(encoding="utf-8"))
    return data.get('entries') or []


def table_name(structure: str) -> str:
    """e.g. 'character-stats' → 'rom_character_stats'."""
    return f'rom_{_snake(structure)}'


def init_rom_tables(conn: sqlite3.Connection):
    """Create one rom_<name> table per extractable structure.

    All field columns are nullable. _idx and _rom_offset are audit fields.
    No FKs, no unique constraints — these are read-only mirrors of ROM bytes.
    """
    for structure in EXTRACTABLE:
        fields = get_fields(structure)
        if not fields:
            continue
        cols = ['_idx INTEGER NOT NULL', '_rom_offset INTEGER']
        # Also dedupe field names + sanitize
        seen = set()
        for f in fields:
            name = f['name']
            if name in seen:
                continue
            seen.add(name)
            # Sanitize column name (SQLite allows most chars but be safe)
            safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
            cols.append(f'{safe} {_sql_type(f)}')
        ddl = f"""
            CREATE TABLE IF NOT EXISTS {table_name(structure)} (
                _idx INTEGER NOT NULL,
                _rom_offset INTEGER,
                {', '.join(c for c in cols if not c.startswith('_idx') and not c.startswith('_rom_offset'))},
                PRIMARY KEY (_idx)
            )
        """
        # Simpler: rebuild without the awkward leading-comma issue
        col_defs = ', '.join(cols)
        ddl = f"CREATE TABLE IF NOT EXISTS {table_name(structure)} ({col_defs}, PRIMARY KEY (_idx))"
        conn.execute(ddl)
    conn.commit()


def populate_rom_tables(conn: sqlite3.Connection, structures=None):
    """Copy entries from bank.json into rom_<name> tables.

    Returns: {structure_name: rows_inserted}
    """
    if structures is None:
        structures = EXTRACTABLE
    summary = {}
    for structure in structures:
        fields = get_fields(structure)
        entries = get_entries(structure)
        if not fields or not entries:
            summary[structure] = 0
            continue
        # Resolve column names (sanitized) for fields
        col_names = ['_idx', '_rom_offset']
        seen = set()
        for f in fields:
            n = f['name']
            if n in seen:
                continue
            seen.add(n)
            col_names.append(re.sub(r'[^a-zA-Z0-9_]', '_', n))

        tbl = table_name(structure)
        conn.execute(f'DELETE FROM {tbl}')  # idempotent
        placeholders = ','.join(['?'] * len(col_names))
        for entry in entries:
            values = [entry.get('_index'), entry.get('_raw_offset')]
            for f in fields:
                if f['name'] in seen:
                    values.append(entry.get(f['name']))
            conn.execute(
                f'INSERT INTO {tbl} ({",".join(col_names)}) VALUES ({placeholders})',
                values,
            )
        conn.commit()
        summary[structure] = len(entries)
    return summary
