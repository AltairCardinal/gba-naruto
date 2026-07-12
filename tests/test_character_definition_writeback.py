import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'web-editor/backend'))

from rom_models import init_rom_tables, populate_rom_tables
from tools.build_db_patches import generate_character_definition_patches


class CharacterDefinitionWritebackTest(unittest.TestCase):
    def make_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False); tmp.close()
        path = Path(tmp.name); self.addCleanup(path.unlink, missing_ok=True)
        conn = sqlite3.connect(path); init_rom_tables(conn); populate_rom_tables(conn)
        return path, conn

    def test_edit_survives_refresh_and_targets_one_complete_record(self):
        path, conn = self.make_db()
        raw = bytearray.fromhex(conn.execute(
            "SELECT raw_hex FROM rom_character_definitions WHERE _idx=1"
        ).fetchone()[0])
        raw[1] = 15
        conn.execute("UPDATE rom_character_definitions SET raw_hex=? WHERE _idx=1", (raw.hex(),))
        conn.commit(); populate_rom_tables(conn); conn.close()
        patch = next(p for p in generate_character_definition_patches(path) if p['db_row_id'] == 1)
        self.assertEqual(patch['type'], 'bytes')
        self.assertEqual(patch['offset'], 0x5424D0)
        self.assertEqual(patch['length'], 0xB4)
        self.assertEqual(bytes.fromhex(patch['after_hex'])[1], 15)

    def test_base_length_and_sentinel_guards(self):
        path, conn = self.make_db()
        conn.execute("UPDATE rom_character_definitions SET base_raw_hex='00' WHERE _idx=1")
        conn.execute("UPDATE rom_character_definitions SET raw_hex=? WHERE _idx=0", ('01' + '00' * 179,))
        conn.execute("UPDATE rom_character_definitions SET raw_hex='01' WHERE _idx=2")
        conn.commit(); conn.close()
        by_id = {p['db_row_id']: p for p in generate_character_definition_patches(path)}
        self.assertIn('immutable base', by_id[1]['error'])
        self.assertIn('sentinel', by_id[0]['error'])
        self.assertIn('exactly 0xB4', by_id[2]['error'])


if __name__ == '__main__':
    unittest.main()
