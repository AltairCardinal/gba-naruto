import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from tools.build_db_patches import (
    generate_audio_patches,
    generate_chapter_patches,
    generate_skill_patches,
    generate_story_beat_patches,
)
from build_mod import classify_db_patch


class UnsafeLegacyPatchesTest(unittest.TestCase):
    CASES = (
        (
            generate_chapter_patches,
            "CREATE TABLE chapters (id INTEGER, chapter_number INTEGER, title TEXT, title_ja TEXT, title_zh TEXT)",
            "INSERT INTO chapters VALUES (1, 99, 'chapter', '', '')",
            "db_chapter_unmapped",
        ),
        (
            generate_skill_patches,
            "CREATE TABLE skills (id INTEGER, unit_id INTEGER, name TEXT, damage INTEGER)",
            "INSERT INTO skills VALUES (1, 0, 'skill', 10)",
            "db_skill_unmapped",
        ),
        (
            generate_story_beat_patches,
            "CREATE TABLE story_beats (id INTEGER, chapter_id INTEGER, beat_index INTEGER, title TEXT)",
            "INSERT INTO story_beats VALUES (1, 1, 7, 'beat')",
            "db_story_beat_unmapped",
        ),
        (
            generate_audio_patches,
            "CREATE TABLE audio_files (id INTEGER, rom_offset INTEGER, size INTEGER, name TEXT)",
            "INSERT INTO audio_files VALUES (1, NULL, 0, 'audio')",
            "db_audio_unmapped",
        ),
    )

    def test_unproven_legacy_rows_never_generate_rom_bytes(self):
        for generator, schema, insert, diagnostic_type in self.CASES:
            with self.subTest(generator=generator.__name__), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "editor.db"
                connection = sqlite3.connect(db_path)
                connection.execute(schema)
                connection.execute(insert)
                connection.commit()
                connection.close()

                patches = generator(db_path)

                self.assertEqual(len(patches), 1)
                self.assertEqual(patches[0]["type"], diagnostic_type)
                self.assertNotIn("offset", patches[0])
                self.assertNotIn("after_hex", patches[0])
                self.assertEqual(classify_db_patch(patches[0]), "diagnostic")


if __name__ == "__main__":
    unittest.main()
