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
    """ROM-backed character definition entries → legacy editor units table.

    The units bank now stores the real 63 x 0xB4 character-definition table at
    0x54241C. ``character_id`` is the ROM table index.  The editor's legacy
    ``units`` table is still char_id-centric, so import one row per character
    definition.  Do not enrich base stats from the character-growth bank: its
    fields are level-growth rates, not base HP/attack/defense.
    """
    cur = conn.cursor()
    data = json.load(open(CONTENT_DIR / 'units' / 'bank.json'))

    inserted = 0
    entries = data.get('entries') or data.get('unit_id_table', {}).get('entries', [])
    for entry in entries:
        char_id = entry.get('character_id', entry.get('char_id', entry.get('_index', 0)))
        name = entry.get('name', f'Character {char_id:02d}')
        # Check if char_id already exists (idempotent)
        cur.execute("SELECT 1 FROM units WHERE char_id = ? AND name = ? LIMIT 1", (char_id, name))
        if cur.fetchone():
            continue
        # Conservative editor defaults. Runtime base fields live in the
        # 0x54241C character definition and need separate field semantics.
        hp, atk, df = 100, 10, 5
        try:
            if dry_run:
                inserted += 1
                continue
            cur.execute("""
                INSERT INTO units (char_id, name, name_ja, hp, attack, defense, speed)
                VALUES (?, ?, ?, ?, ?, ?, 5)
            """, (char_id, name, name if any(ord(c) > 127 for c in name) else None,
                  hp, atk, df))
            inserted += 1
        except Exception as e:
            print(f'  units[{char_id}] failed: {e}')

    conn.commit()
    return inserted


def import_dialogues(conn, dry_run=False):
    """Import ROM dialogue data from dialogue-bank-full.json.

    Three regions extracted by tools/extract_dialogue_full.py:
      1. dialogue_pointer_table @ 0x461CE8 (50 slots, 40 non-empty)
      2. 0x458000-0x460000 (258 segments — bulk of 熊组 Chinese localization)
      3. title screen text @ 0x00076D

    Note on 'garbled' text:
        GBA's native text encoding is SJIS (cp932). 熊组 2004 年的
        汉化 patch 替换了部分 dialogue bytes 为 GBK 编码中文，但
        GBA text engine 不能完美解码 GBK 双字节字符，所以 cp932 和
        GBK 两种解码都不能完美还原——编辑器里看到 '乱码' 是 ROM
        真实数据的限制。要看到流畅中文需要 ROM 字体表改造 + 逐字
        节重新编码，是 GBA 汉化的标准工作流。
    """
    cur = conn.cursor()
    full_path = CONTENT_DIR / 'text' / 'dialogue-bank-full.json'
    if not full_path.exists():
        print(f'  ⚠️  dialogue-bank-full.json missing — run tools/extract_dialogue_full.py first')
        return 0
    entries = json.load(open(full_path))
    if not isinstance(entries, list):
        entries = entries.get('entries', [])
    inserted = 0
    for entry in entries:
        if entry.get('empty'):
            continue
        # New format uses 'slot', old used 'key'
        key = entry.get('slot') or entry.get('key', '')
        if not key:
            continue
        text_ja = entry.get('text_ja', '') or ''
        text_zh = entry.get('text_zh', '') or ''
        text_len = entry.get('text_len', 0)
        # Skip empty text
        if not text_ja and not text_zh:
            continue
        # Skip if exact key already present
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
                text_ja,
                text_zh if text_zh and text_zh != text_ja else None,
                text_len,
                text_len + 8,
            ))
            inserted += 1
        except Exception as e:
            print(f'  dialogues[{key}] failed: {e}')
    conn.commit()
    return inserted


def import_skills(conn, dry_run=False):
    """Keep legacy semantic skills empty until byte fields receive UI meaning."""
    return 0


def import_story_beats(conn, dry_run=False):
    """Do not import graphics resource descriptors as story beats."""
    return 0


def import_battle_configs(conn, dry_run=False):
    """Do not map effect templates into the unrelated legacy scenario table."""
    return 0


def import_chapters(conn, dry_run=False):
    """Do not synthesize chapters until the real flow table is proven."""
    return 0


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
