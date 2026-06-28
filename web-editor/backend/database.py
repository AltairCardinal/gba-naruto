import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
import bcrypt

ADMIN_USERNAME = "kibox"
ADMIN_PASSWORD = "Ztl159632"

def _get_db_path():
    """Resolve DB_PATH dynamically so tests can override via env var."""
    return os.environ.get("DB_PATH") or str(Path(__file__).resolve().parent.parent.parent / "sequel" / "editor.db")

# Keep a module-level alias for backward compat, but prefer _get_db_path()
DB_PATH = _get_db_path()

@contextmanager
def get_db():
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
    finally:
        conn.close()

def get_db_connection():
    """Legacy function - use get_db() context manager instead."""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    # Enable FK enforcement so ON DELETE CASCADE on user_permissions
    # actually fires when an admin deletes a user. Without this pragma,
    # SQLite accepts the FK declarations but never enforces them — leaving
    # orphan permission rows that get re-attached if a new user happens
    # to get the same id via auto-increment.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def init_db():
    conn = get_db_connection()
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dialogues (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            speaker TEXT,
            text_ja TEXT,
            text_zh TEXT,
            chapter_id INTEGER,
            byte_count INTEGER,
            max_bytes INTEGER DEFAULT 255,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY,
            char_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_ja TEXT,
            name_zh TEXT,
            hp INTEGER DEFAULT 100,
            attack INTEGER DEFAULT 10,
            defense INTEGER DEFAULT 5,
            speed INTEGER DEFAULT 5,
            chapter_id INTEGER,
            map_id TEXT,
            position_x INTEGER,
            position_y INTEGER,
            team INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY,
            unit_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_ja TEXT,
            name_zh TEXT,
            description TEXT,
            description_ja TEXT,
            description_zh TEXT,
            damage INTEGER DEFAULT 0,
            heal INTEGER DEFAULT 0,
            range_min INTEGER DEFAULT 1,
            range_max INTEGER DEFAULT 1,
            cost_hp INTEGER DEFAULT 0,
            cost_chakra INTEGER DEFAULT 0,
            effect_type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES units(id)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS story_beats (
            id INTEGER PRIMARY KEY,
            chapter_id INTEGER NOT NULL,
            beat_index INTEGER NOT NULL,
            beat_type TEXT NOT NULL,
            title TEXT,
            title_ja TEXT,
            title_zh TEXT,
            description TEXT,
            description_ja TEXT,
            description_zh TEXT,
            trigger_type TEXT,
            trigger_param TEXT,
            dialogue_key TEXT,
            battle_config_id INTEGER,
            map_id TEXT,
            position_x INTEGER,
            position_y INTEGER,
            next_beat_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audio_files (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            rom_offset INTEGER,
            size INTEGER,
            duration_seconds REAL,
            format TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS battle_configs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            chapter_id INTEGER,
            scenario_id INTEGER,
            player_units TEXT,
            enemy_units TEXT,
            terrain_mod TEXT,
            turn_limit INTEGER,
            win_condition TEXT,
            lose_condition TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'editor',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unit_positions (
            id INTEGER PRIMARY KEY,
            unit_id INTEGER NOT NULL,
            map_id TEXT NOT NULL,
            position_x INTEGER NOT NULL,
            position_y INTEGER NOT NULL,
            team INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES units(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY,
            chapter_number INTEGER NOT NULL,
            title TEXT,
            title_ja TEXT,
            title_zh TEXT,
            description TEXT,
            map_id TEXT,
            sequence_order INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # User permissions: which editor-level actions a user can perform.
    # Admin always has all 4 (enforced at app layer, not stored here).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL CHECK(permission IN ('create_file', 'modify_file', 'delete_file', 'trigger_build')),
            granted_by INTEGER,
            granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, permission),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (granted_by) REFERENCES users(id)
        )
    """)

    # Bootstrap the built-in admin account so the system always has at
    # least one admin (and a fresh DB is recoverable from credentials
    # documented in the design doc). If the account already exists with
    # the right password, leave it; if password is wrong, reset to the
    # documented one (this is a dev tool, not a customer-facing system).
    cursor = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (ADMIN_USERNAME,))
    row = cursor.fetchone()
    if row is None:
        pw_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            (ADMIN_USERNAME, pw_hash),
        )
    else:
        # row is a tuple (id, password_hash) — default row_factory
        existing_hash = row[1] or ""
        if not existing_hash or not bcrypt.checkpw(ADMIN_PASSWORD.encode("utf-8"), existing_hash.encode("utf-8")):
            pw_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            conn.execute(
                "UPDATE users SET password_hash = ?, role = 'admin', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (pw_hash, row[0]),
            )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized")