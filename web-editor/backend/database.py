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
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized")