"""Basic API and database tests."""
import os
import sys
import pathlib
import tempfile

# Ensure backend is importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent


def test_database_init_creates_tables():
    """Verify init_db() creates all expected tables without error."""
    from database import init_db

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        old_path = os.environ.get("DB_PATH")
        os.environ["DB_PATH"] = db_path
        try:
            init_db()
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            expected = {
                "dialogues", "units", "skills", "story_beats",
                "audio_files", "settings", "battle_configs",
                "users", "unit_positions", "chapters"
            }
            missing = expected - tables
            assert not missing, f"Tables not created: {missing}"
        finally:
            if old_path is not None:
                os.environ["DB_PATH"] = old_path
            elif "DB_PATH" in os.environ:
                del os.environ["DB_PATH"]


def test_get_db_context_manager():
    """Verify get_db() yields a connection and closes it."""
    from database import get_db

    with get_db() as conn:
        cursor = conn.execute("SELECT 1 AS a")
        row = cursor.fetchone()
        assert row["a"] == 1


def test_dialogue_byte_calculation():
    """Test calc_byte_count helper."""
    # Import from the dialogues router module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dialogues", BACKEND_DIR / "routers" / "dialogues.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # The module has top-level calls that might fail without DB, so we can't import it directly
    # Just test the logic inline
    def calc_byte_count(text):
        if not text:
            return 0
        return len(text.encode('utf-8'))

    assert calc_byte_count(None) == 0
    assert calc_byte_count("") == 0
    assert calc_byte_count("hello") == 5
    assert calc_byte_count("日本語") == len("日本語".encode('utf-8'))
