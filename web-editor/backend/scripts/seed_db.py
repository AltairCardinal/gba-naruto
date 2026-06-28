#!/usr/bin/env python3
"""Seed the editor database with demo data for development/testing.

Usage:
    cd web-editor/backend
    python3 scripts/seed_db.py

The script:
1. Initializes the database (creates tables + admin user)
2. Seeds a demo editor user (demo / demo123)
3. Seeds 3 demo dialogues from sequel/content/story/
4. Seeds 2 demo units from sequel/content/character-stats/
5. Seeds 1 demo chapter
6. Seeds 1 demo story beat
"""

import os
import sys
import pathlib
import sqlite3

# Ensure backend modules are importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from database import init_db, _get_db_path, ADMIN_USERNAME

CONTENT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "sequel" / "content"


def seed_demo_user(conn):
    """Create a demo editor user (not admin)."""
    import bcrypt
    username = "demo"
    password = "demo123"

    cursor = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        print(f"  [skip] user '{username}' already exists")
        return

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'editor')",
        (username, pw_hash),
    )
    print(f"  [create] user '{username}' (password: {password})")


def seed_chapter(conn):
    """Seed a demo chapter based on episode-01."""
    cursor = conn.execute("SELECT id FROM chapters WHERE chapter_number = 1")
    if cursor.fetchone():
        print("  [skip] chapter 1 already exists")
        return

    conn.execute(
        """INSERT INTO chapters (chapter_number, title, title_zh, description, map_id, sequence_order)
           VALUES (1, 'Episode 01', '边境异动', '建立续作主角小队，完成一章可用作ROM Hack参考的垂直切片。', 'episode-01-mountain-pass', 1)"""
    )
    print("  [create] chapter 1: 边境异动")


def seed_dialogues(conn):
    """Seed 3 demo dialogues from the story content."""
    dialogues = [
        {
            "key": "ep01_intro_01",
            "speaker": "Naruto",
            "text_ja": "カカシ先生、国境の異変について聞いたか？",
            "text_zh": "卡卡西老师，你听说边境的异变了吗？",
            "chapter_id": 1,
            "max_bytes": 255,
        },
        {
            "key": "ep01_intro_02",
            "speaker": "Kakashi",
            "text_ja": "ああ、南の警戒線で異常な查克拉反応が検知された。君たちの小隊を派遣する。",
            "text_zh": "嗯，南部警戒线检测到了异常的查克拉反应。我将派遣你们小队前往。",
            "chapter_id": 1,
            "max_bytes": 255,
        },
        {
            "key": "ep01_post_01",
            "speaker": "Shikamaru",
            "text_ja": "敵が持っていた偽造通行証...別の村のものだ。これは面倒なことになりそうだ。",
            "text_zh": "敌人持有的伪造通行文书...是其他村子的。这下麻烦大了。",
            "chapter_id": 1,
            "max_bytes": 255,
        },
    ]

    created = 0
    for d in dialogues:
        byte_count = len((d["text_ja"] or "").encode("utf-8"))
        cursor = conn.execute("SELECT id FROM dialogues WHERE key = ?", (d["key"],))
        if cursor.fetchone():
            print(f"  [skip] dialogue '{d['key']}' already exists")
            continue

        conn.execute(
            """INSERT INTO dialogues (key, speaker, text_ja, text_zh, chapter_id, byte_count, max_bytes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (d["key"], d["speaker"], d["text_ja"], d["text_zh"], d["chapter_id"], byte_count, d["max_bytes"]),
        )
        created += 1
    print(f"  [create] {created} dialogues (3 total attempted)")


def seed_units(conn):
    """Seed 2 demo units from character stats."""
    units = [
        {
            "char_id": 1,
            "name": "Naruto Uzumaki",
            "name_ja": "うずまきナルト",
            "name_zh": "漩涡鸣人",
            "hp": 100,
            "attack": 100,
            "defense": 100,
            "speed": 10,
            "chapter_id": 1,
            "map_id": "episode-01-mountain-pass",
            "position_x": 5,
            "position_y": 10,
            "team": 0,
        },
        {
            "char_id": 2,
            "name": "Shikamaru Nara",
            "name_ja": "奈良シカマル",
            "name_zh": "奈良鹿丸",
            "hp": 100,
            "attack": 100,
            "defense": 100,
            "speed": 8,
            "chapter_id": 1,
            "map_id": "episode-01-mountain-pass",
            "position_x": 6,
            "position_y": 10,
            "team": 0,
        },
    ]

    created = 0
    for u in units:
        cursor = conn.execute("SELECT id FROM units WHERE char_id = ?", (u["char_id"],))
        if cursor.fetchone():
            print(f"  [skip] unit char_id={u['char_id']} already exists")
            continue

        conn.execute(
            """INSERT INTO units (char_id, name, name_ja, name_zh, hp, attack, defense, speed,
                                  chapter_id, map_id, position_x, position_y, team)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (u["char_id"], u["name"], u["name_ja"], u["name_zh"], u["hp"], u["attack"],
             u["defense"], u["speed"], u["chapter_id"], u["map_id"],
             u["position_x"], u["position_y"], u["team"]),
        )
        created += 1
    print(f"  [create] {created} units (2 total attempted)")


def seed_story_beat(conn):
    """Seed a demo story beat for chapter 1."""
    cursor = conn.execute("SELECT id FROM story_beats WHERE chapter_id = 1 AND beat_index = 0")
    if cursor.fetchone():
        print("  [skip] story beat already exists")
        return

    conn.execute(
        """INSERT INTO story_beats (chapter_id, beat_index, beat_type, title, title_zh,
                                     description, description_zh, trigger_type, dialogue_key)
           VALUES (1, 0, 'dialogue', 'Episode 01 Intro', '边境异动 - 序幕',
                   'Border patrol detects anomaly, team dispatched.', '木叶边境巡逻情报异常，主角小队被临时派往南部警戒线。',
                   'auto', 'ep01_intro_01')"""
    )
    print("  [create] story beat: 边境异动 - 序幕")


def main():
    print("=== Editor DB Seed Script ===")
    print(f"DB path: {_get_db_path()}")
    print(f"Content dir: {CONTENT_DIR}")
    print()

    # Step 1: Initialize DB (creates tables + admin user)
    print("[1/6] Initializing database...")
    init_db()
    print("  done.")

    # Step 2-6: Seed demo data
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    print("[2/6] Seeding demo user...")
    seed_demo_user(conn)

    print("[3/6] Seeding chapter...")
    seed_chapter(conn)

    print("[4/6] Seeding dialogues...")
    seed_dialogues(conn)

    print("[5/6] Seeding units...")
    seed_units(conn)

    print("[6/6] Seeding story beats...")
    seed_story_beat(conn)

    conn.commit()
    conn.close()

    print()
    print("=== Seed complete ===")
    print(f"Admin user: {ADMIN_USERNAME}")
    print("Demo user: demo / demo123")


if __name__ == "__main__":
    main()
