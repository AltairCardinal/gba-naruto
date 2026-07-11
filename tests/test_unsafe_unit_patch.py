import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_unit_patches


class UnsafeUnitPatchTest(unittest.TestCase):
    def test_legacy_units_do_not_write_unproven_offset_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "editor.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE units (id INTEGER, char_id INTEGER, name TEXT, hp INTEGER)"
            )
            connection.execute("INSERT INTO units VALUES (1, 7, 'test', 10)")
            connection.commit()
            connection.close()

            patches = generate_unit_patches(db_path)

        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["type"], "db_unit_unmapped")
        self.assertNotIn("offset", patches[0])
        self.assertNotIn("after_hex", patches[0])


if __name__ == "__main__":
    unittest.main()
