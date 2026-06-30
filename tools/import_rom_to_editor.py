#!/usr/bin/env python3
"""
Phase 5.2 — Import ROM-derived entries from bank.json files into the
editor.db editable tables.

The editor.db had only 8 tables for editable content (units, dialogues,
skills, chapters, story_beats, audio_files, battle_configs, unit_positions)
and they only held seed samples + T7 verification data. After Phase 5
extracted 925 entries from ROM into sequel/content/*/bank.json, those
real ROM contents need to land in the editor's editable tables.

Strategy:
    INSERT OR IGNORE — keep existing seed/T7 rows; add ROM entries on top.
    Map bank.json fields → editor.db columns by best-effort name match.

Run idempotently. After running, the editor's CRUD views show the full
ROM content alongside any user overrides.

Usage:
    python tools/import_rom_to_editor.py [--dry-run]
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path('sequel/editor.db')
CONTENT_DIR = Path('sequel/content')


def load_entries(path: str, key: str | None = None) -> list[dict]:
    """Load entries[] from a bank.json. key=None uses top-level entries."""
    if not Path(path).exists():
        return []
    data = json.load(open(path))
    if key and isinstance(data.get(key), dict):
        return data[key].get('entries', [])
    return data.get('entries', [])


def field(entry: dict, *names: str, default=None):
    """Get first matching field from entry, trying multiple alias names."""
    for n in names:
        if n in entry and entry[n] is not None:
            return entry[n]
    return default


def import_units(conn, dry_run=False):
    """43 unit_id_table entries + battle_scenario entries → units table."""
    cur = conn.cursor()
    data = json.load(open(CONTENT_DIR / 'units' / 'bank.json'))
    inserted = 0
    for entry in data.get('unit_id_table', {}).get('entries', []):
        char_id = entry.get('char_id', 0)
        name = entry.get('name', f'Unit {char_id}')
        # Check if char_id already exists (idempotent)
        cur.execute("SELECT 1 FROM units WHERE char_id = ? AND name = ? LIMIT 1", (char_id, name))
        if cur.fetchone():
            continue
        try:
            if dry_run:
                inserted += 1
                continue
            cur.execute("""
                INSERT INTO units (char_id, name, name_ja, hp, attack, defense, speed)
                VALUES (?, ?, ?, 100, 10, 5, 5)
            """, (char_id, name, name if any(ord(c) > 127 for c in name) else None))
            inserted += 1
        except Exception as e:
            print(f'  units[{char_id}] failed: {e}')
    conn.commit()
    return inserted


def import_dialogues(conn, dry_run=False):
    """7 dialogue-bank.json entries → dialogues table."""
    cur = conn.cursor()
    entries = load_entries(CONTENT_DIR / 'text' / 'dialogue-bank.json')
    inserted = 0
    for entry in entries:
        key = entry.get('id', '')
        if not key or key.startswith('proof.'):
            continue  # skip the proof-of-write demo entry
        max_bytes = entry.get('max_bytes', 41)
        expected_hex = entry.get('expected_hex', '')
        cur.execute("SELECT 1 FROM dialogues WHERE key = ? LIMIT 1", (key,))
        if cur.fetchone():
            continue
        try:
            if dry_run:
                inserted += 1
                continue
            cur.execute("""
                INSERT INTO dialogues
                  (key, speaker, text_ja, text_zh, byte_count, max_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                key,
                None,
                expected_hex,
                None,
                len(expected_hex) // 2,
                max_bytes,
            ))
            inserted += 1
        except Exception as e:
            print(f'  dialogues[{key}] failed: {e}')
    conn.commit()
    return inserted


def import_skills(conn, dry_run=False):
    """12 skills entries → skills table."""
    cur = conn.cursor()
    data = json.load(open(CONTENT_DIR / 'skills' / 'bank.json'))
    inserted = 0
    for i, entry in enumerate(data.get('entries', [])):
        skill_id = entry.get('skill_id', i)
        value = entry.get('value', 0)
        type_id = entry.get('type_id', 0)
        cur.execute("SELECT 1 FROM skills WHERE name = ? LIMIT 1", (f'Skill {skill_id}',))
        if cur.fetchone():
            continue
        try:
            if dry_run:
                inserted += 1
                continue
            cur.execute("""
                INSERT INTO skills
                  (unit_id, name, name_ja, name_zh, damage, heal,
                   range_min, range_max, cost_hp, cost_chakra, effect_type)
                VALUES (0, ?, NULL, NULL, ?, 0, 1, 1, 0, ?, ?)
            """, (f'Skill {skill_id}', value, type_id, f'type_{type_id}'))
            inserted += 1
        except Exception as e:
            print(f'  skills[{skill_id}] failed: {e}')
    conn.commit()
    return inserted


def import_story_beats(conn, dry_run=False):
    """50 entries across story/story-b/c/d/e → story_beats table."""
    cur = conn.cursor()
    chapter_map = {
        'story':   1,
        'story-b': 2,
        'story-c': 3,
        'story-d': 4,
        'story-e': 5,
    }
    inserted = 0
    for sub, chapter_id in chapter_map.items():
        entries = load_entries(CONTENT_DIR / sub / 'bank.json')
        for i, entry in enumerate(entries):
            beat_idx = i
            beat_type = sub.replace('story-', '').replace('story', 'main')
            ptr_val = None
            for k in entry:
                if k.endswith('_ptr') or k == 'chapter_ptr' or k == 'func_ptr':
                    ptr_val = entry.get(k)
                    break
            title = f'Beat {chapter_id}.{beat_idx}' + (f' (0x{ptr_val:08X})' if ptr_val else '')
            cur.execute("SELECT 1 FROM story_beats WHERE chapter_id = ? AND beat_index = ? LIMIT 1",
                        (chapter_id, beat_idx))
            if cur.fetchone():
                continue
            try:
                if dry_run:
                    inserted += 1
                    continue
                cur.execute("""
                    INSERT INTO story_beats
                      (chapter_id, beat_index, beat_type, title, trigger_type)
                    VALUES (?, ?, ?, ?, NULL)
                """, (chapter_id, beat_idx, beat_type, title))
                inserted += 1
            except Exception as e:
                print(f'  story_beats[{sub}.{i}] failed: {e}')
    conn.commit()
    return inserted


def import_battle_configs(conn, dry_run=False):
    """32 battle-config entries → battle_configs table."""
    cur = conn.cursor()
    entries = load_entries(CONTENT_DIR / 'battle-config' / 'bank.json')
    inserted = 0
    for i, entry in enumerate(entries):
        config_id = entry.get('config_id', i)
        cur.execute("SELECT 1 FROM battle_configs WHERE name = ? LIMIT 1", (f'Battle Config {config_id}',))
        if cur.fetchone():
            continue
        try:
            if dry_run:
                inserted += 1
                continue
            cur.execute("""
                INSERT INTO battle_configs
                  (name, chapter_id, scenario_id, player_units, enemy_units,
                   terrain_mod, turn_limit, win_condition, lose_condition)
                VALUES (?, NULL, ?, '[]', '[]', NULL, NULL, NULL, NULL)
            """, (f'Battle Config {config_id}', config_id))
            inserted += 1
        except Exception as e:
            print(f'  battle_configs[{config_id}] failed: {e}')
    conn.commit()
    return inserted


def import_chapters(conn, dry_run=False):
    """5 chapters inferred from story/story-b/c/d/e mapping."""
    cur = conn.cursor()
    inserted = 0
    for chapter_id in range(1, 6):
        cur.execute("SELECT 1 FROM chapters WHERE chapter_number = ? LIMIT 1", (chapter_id,))
        if cur.fetchone():
            continue
        try:
            if dry_run:
                inserted += 1
                continue
            cur.execute("""
                INSERT INTO chapters
                  (chapter_number, title, sequence_order)
                VALUES (?, ?, ?)
            """, (chapter_id, f'Chapter {chapter_id}', chapter_id))
            inserted += 1
        except Exception as e:
            print(f'  chapters[{chapter_id}] failed: {e}')
    conn.commit()
    return inserted


def import_audio_files(conn, dry_run=False):
    """ROM audio tables — no extractable entries (dispatcher only).
    Mark as such: insert a placeholder showing ROM has audio infrastructure
    but no discrete audio_files in our extract phase."""
    # Skip — Phase 5 reported 0 audio entries
    return 0


def import_unit_positions(conn, dry_run=False):
    """Unit positions embedded in battle_scenario — skip (already 3 seed rows)."""
    return 0


def main():
    dry_run = '--dry-run' in sys.argv
    if not DB_PATH.exists():
        print(f'FATAL: editor.db not found at {DB_PATH}', file=sys.stderr)
        sys.exit(2)

    conn = sqlite3.connect(DB_PATH)
    before = {}
    cur = conn.cursor()
    for t in ['units', 'dialogues', 'skills', 'story_beats', 'chapters', 'battle_configs', 'audio_files', 'unit_positions']:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        before[t] = cur.fetchone()[0]

    print(f'{"table":18s} {"before":>7s}  {"inserted":>9s}  {"after":>7s}')
    print('-' * 50)
    tasks = [
        ('units',          import_units),
        ('dialogues',      import_dialogues),
        ('skills',         import_skills),
        ('story_beats',    import_story_beats),
        ('chapters',       import_chapters),
        ('battle_configs', import_battle_configs),
        ('audio_files',    import_audio_files),
        ('unit_positions', import_unit_positions),
    ]
    for tbl, fn in tasks:
        n = fn(conn, dry_run=dry_run)
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        after = cur.fetchone()[0]
        marker = '🔍' if dry_run else '✅'
        print(f'{marker} {tbl:17s} {before[tbl]:>7d}  {n:>9d}  {after:>7d}')

    conn.close()
    total_after = sum(b for b in before.values())
    print(f'\nTotal editor.db editable rows after import: {total_after}')


if __name__ == '__main__':
    main()