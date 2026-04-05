import sqlite3
import os

DB_PATH = "/root/gba-naruto/sequel/editor.db"

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
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
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized")