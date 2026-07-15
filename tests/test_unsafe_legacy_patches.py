import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from tools.build_db_patches import (
    generate_audio_patches,
    generate_battle_config_data_patches,
    generate_chapter_patches,
    generate_character_stat_patches,
    generate_character_stats_b_patches,
    generate_encounter_zone_patches,
    generate_item_patches,
    generate_level_patches,
    generate_map_patches,
    generate_skill_patches,
    generate_story_beat_patches,
    generate_story_b_patches,
    generate_story_c_patches,
    generate_story_d_patches,
    generate_story_e_patches,
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
        *(
            (
                generator,
                f"CREATE TABLE rom_story_{suffix} (_idx INTEGER)",
                f"INSERT INTO rom_story_{suffix} VALUES (0)",
                f"db_story_{suffix}_disproved",
            )
            for generator, suffix in (
                (generate_story_b_patches, "b"),
                (generate_story_c_patches, "c"),
                (generate_story_d_patches, "d"),
                (generate_story_e_patches, "e"),
            )
        ),
        (
            generate_audio_patches,
            "CREATE TABLE audio_files (id INTEGER, rom_offset INTEGER, size INTEGER, name TEXT)",
            "INSERT INTO audio_files VALUES (1, NULL, 0, 'audio')",
            "db_audio_unmapped",
        ),
        (
            generate_map_patches,
            "CREATE TABLE maps (id INTEGER, name TEXT, width INTEGER, height INTEGER, tileset_ptr INTEGER, tilemap_ptr INTEGER)",
            "INSERT INTO maps VALUES (1, 'map', 36, 44, 134946040, 134955372)",
            "db_map_unmapped",
        ),
        (
            generate_level_patches,
            "CREATE TABLE levels (id INTEGER, level INTEGER, hp_gain INTEGER, stat1_gain INTEGER, stat2_gain INTEGER)",
            "INSERT INTO levels VALUES (1, 2, 3, 4, 5)",
            "db_level_unmapped",
        ),
        (
            generate_character_stat_patches,
            "CREATE TABLE character_stats (id INTEGER, name TEXT, char_type INTEGER, hp INTEGER, attack INTEGER, defense INTEGER, max_value INTEGER)",
            "INSERT INTO character_stats VALUES (1, 'stat', 8, 100, 20, 10, 1500)",
            "db_character_stat_unmapped",
        ),
        (
            generate_character_stats_b_patches,
            "CREATE TABLE rom_character_stats_b (_idx INTEGER, _rom_offset INTEGER)",
            "INSERT INTO rom_character_stats_b VALUES (0, 5526016)",
            "db_character_stats_b_disproved",
        ),
        (
            generate_battle_config_data_patches,
            "CREATE TABLE battle_config_data (id INTEGER, name TEXT, config_id INTEGER, value INTEGER, flag1 INTEGER, flag2 INTEGER)",
            "INSERT INTO battle_config_data VALUES (1, 'config', 1, 612, 0, 0)",
            "db_battle_config_data_unmapped",
        ),
        (
            generate_encounter_zone_patches,
            "CREATE TABLE encounter_zones (id INTEGER, map_id INTEGER, zone_id INTEGER)",
            "INSERT INTO encounter_zones VALUES (1, 40, 7)",
            "db_encounter_zone_unmapped",
        ),
        (
            generate_item_patches,
            "CREATE TABLE items (id INTEGER, item_id INTEGER, name TEXT, item_type INTEGER, cost INTEGER, effect INTEGER)",
            "INSERT INTO items VALUES (1, 2, 'item', 3, 4, 5)",
            "db_item_unmapped",
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
