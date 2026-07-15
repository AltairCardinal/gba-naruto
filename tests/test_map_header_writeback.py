import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'web-editor/backend'))
from rom_models import init_rom_tables, populate_rom_tables
from tools.build_db_patches import generate_map_header_patches


class MapHeaderWritebackTest(unittest.TestCase):
    def make_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False); tmp.close()
        path = Path(tmp.name); self.addCleanup(path.unlink, missing_ok=True)
        conn = sqlite3.connect(path); init_rom_tables(conn); populate_rom_tables(conn)
        return path, conn

    def test_width_edit_survives_refresh_and_preserves_other_bytes(self):
        path, conn = self.make_db()
        conn.execute("UPDATE rom_map_headers SET width=32 WHERE _idx=40")
        conn.commit(); populate_rom_tables(conn); conn.close()
        patch = next(p for p in generate_map_header_patches(path) if p['db_row_id'] == 40)
        base = (ROOT / 'rom/base.gba').read_bytes()[0x53DE10:0x53DE30]
        result = bytes.fromhex(patch['after_hex'])
        self.assertEqual(patch['offset'], 0x53DE10)
        self.assertEqual(result[:2], b'\x20\x00')
        self.assertEqual(result[2:], base[2:])

    def test_base_dimension_and_pointer_guards(self):
        path, conn = self.make_db()
        conn.execute("UPDATE rom_map_headers SET base_raw_hex='00' WHERE _idx=40")
        conn.execute("UPDATE rom_map_headers SET width=0 WHERE _idx=39")
        conn.execute("UPDATE rom_map_headers SET tileset_ptr=0x08000000 WHERE _idx=38")
        conn.commit(); conn.close()
        by_id = {p['db_row_id']: p for p in generate_map_header_patches(path)}
        self.assertIn('immutable base', by_id[40]['error'])
        self.assertIn('dimensions', by_id[39]['error'])
        self.assertIn('LZ header', by_id[38]['error'])


if __name__ == '__main__':
    unittest.main()
